import { GetCommand, ScanCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { SendTaskSuccessCommand, SendTaskFailureCommand } from "@aws-sdk/client-sfn";
import { getDocumentClient, getSFNClient } from "@/lib/aws-client";

export interface ApprovalRequest {
  approval_id: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | "PROCESSING";
  task_token: string;
  runbook_id: string;
  actions: string[];
  severity: "P1" | "P2" | "P3";
  alarm_name: string;
  root_cause: string;
  confidence: number;
  request_kind?: string;
  request_subject?: string;
  request_summary?: string;
  created_at: string;
  updated_at: string;
  responded_by?: string;
  responded_at?: string;
}

const DEFAULT_TABLE = "incident-approval-requests";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

function getTableName() {
  return process.env.DASHBOARD_APPROVAL_TABLE ?? DEFAULT_TABLE;
}

// In-memory fallback
let mockApprovals: ApprovalRequest[] = [
  {
    approval_id: "APR-TEST1234",
    status: "PENDING",
    task_token: "token-1234",
    runbook_id: "generic-recovery",
    actions: ["GCP-RolloutRestartGKEWorkload", "GCP-ScaleGKEWorkload"],
    severity: "P2",
    alarm_name: "pod-oom-alert",
    root_cause: "GKE pod memory utilization above 90% due to traffic spike.",
    confidence: 0.85,
    request_kind: "incident",
    request_subject: "pod-oom-alert",
    request_summary: "GKE pod memory utilization above 90% due to traffic spike.",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export async function listPendingApprovals(): Promise<ApprovalRequest[]> {
  if (!isLiveMode()) {
    return mockApprovals.filter((a) => a.status === "PENDING");
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new ScanCommand({
        TableName: getTableName(),
        FilterExpression: "#status = :pending",
        ExpressionAttributeNames: { "#status": "status" },
        ExpressionAttributeValues: { ":pending": "PENDING" },
      })
    );
    return (result.Items as ApprovalRequest[]) || [];
  } catch (error) {
    console.error("approval-data.listPendingApprovals.failed", error);
    return mockApprovals.filter((a) => a.status === "PENDING");
  }
}

export async function getApprovalRequest(approvalId: string): Promise<ApprovalRequest | null> {
  if (!isLiveMode()) {
    return mockApprovals.find((a) => a.approval_id === approvalId) || null;
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new GetCommand({
        TableName: getTableName(),
        Key: { approval_id: approvalId },
      })
    );
    return (result.Item as ApprovalRequest) || null;
  } catch (error) {
    console.error("approval-data.getApprovalRequest.failed", error);
    return mockApprovals.find((a) => a.approval_id === approvalId) || null;
  }
}

export async function approveApprovalRequest(
  approvalId: string,
  username: string
): Promise<boolean> {
  const now = new Date().toISOString();

  // Retrieve task token and info
  const request = await getApprovalRequest(approvalId);
  if (!request) {
    throw new Error(`Approval request ${approvalId} not found`);
  }
  if (request.status !== "PENDING") {
    throw new Error(`Approval request ${approvalId} is already processed (${request.status})`);
  }

  if (!isLiveMode()) {
    const index = mockApprovals.findIndex((a) => a.approval_id === approvalId);
    if (index >= 0) {
      mockApprovals[index] = {
        ...mockApprovals[index],
        status: "APPROVED",
        responded_by: username,
        responded_at: now,
        updated_at: now,
      };
    }
    return true;
  }

  try {
    // 1. Claim and update status in DynamoDB (optimistic locking)
    const dbClient = getDocumentClient();
    await dbClient.send(
      new UpdateCommand({
        TableName: getTableName(),
        Key: { approval_id: approvalId },
        UpdateExpression: "SET #status = :status, responded_by = :user, responded_at = :now, updated_at = :now",
        ConditionExpression: "attribute_exists(approval_id) AND #status = :pending",
        ExpressionAttributeNames: { "#status": "status" },
        ExpressionAttributeValues: {
          ":status": "APPROVED",
          ":user": username,
          ":now": now,
          ":pending": "PENDING",
        },
      })
    );

    // 2. Call Step Functions SendTaskSuccess
    const sfnClient = getSFNClient();
    await sfnClient.send(
      new SendTaskSuccessCommand({
        taskToken: request.task_token,
        output: JSON.stringify({
          approved: true,
          decision: "approve",
          approved_by: username,
          approved_at: now,
        }),
      })
    );

    return true;
  } catch (error) {
    console.error("approval-data.approveApprovalRequest.failed", error);
    
    // In case of failure, reset request status in DB if update succeeded but SFN failed
    try {
      if (isLiveMode()) {
        const dbClient = getDocumentClient();
        await dbClient.send(
          new UpdateCommand({
            TableName: getTableName(),
            Key: { approval_id: approvalId },
            UpdateExpression: "SET #status = :pending, updated_at = :now REMOVE responded_by, responded_at",
            ExpressionAttributeNames: { "#status": "status" },
            ExpressionAttributeValues: {
              ":pending": "PENDING",
              ":now": now,
            },
          })
        );
      }
    } catch (dbErr) {
      console.error("failed to reset approval request status", dbErr);
    }
    
    throw error;
  }
}

export async function rejectApprovalRequest(
  approvalId: string,
  username: string,
  reason: string
): Promise<boolean> {
  const now = new Date().toISOString();

  const request = await getApprovalRequest(approvalId);
  if (!request) {
    throw new Error(`Approval request ${approvalId} not found`);
  }
  if (request.status !== "PENDING") {
    throw new Error(`Approval request ${approvalId} is already processed (${request.status})`);
  }

  if (!isLiveMode()) {
    const index = mockApprovals.findIndex((a) => a.approval_id === approvalId);
    if (index >= 0) {
      mockApprovals[index] = {
        ...mockApprovals[index],
        status: "REJECTED",
        responded_by: username,
        responded_at: now,
        updated_at: now,
      };
    }
    return true;
  }

  try {
    // 1. Claim and update status in DynamoDB (optimistic locking)
    const dbClient = getDocumentClient();
    await dbClient.send(
      new UpdateCommand({
        TableName: getTableName(),
        Key: { approval_id: approvalId },
        UpdateExpression: "SET #status = :status, responded_by = :user, responded_at = :now, updated_at = :now",
        ConditionExpression: "attribute_exists(approval_id) AND #status = :pending",
        ExpressionAttributeNames: { "#status": "status" },
        ExpressionAttributeValues: {
          ":status": "REJECTED",
          ":user": username,
          ":now": now,
          ":pending": "PENDING",
        },
      })
    );

    // 2. Call Step Functions SendTaskFailure
    const sfnClient = getSFNClient();
    await sfnClient.send(
      new SendTaskFailureCommand({
        taskToken: request.task_token,
        error: "ApprovalRejected",
        cause: `Rejected by ${username}: ${reason}`,
      })
    );

    return true;
  } catch (error) {
    console.error("approval-data.rejectApprovalRequest.failed", error);
    
    try {
      if (isLiveMode()) {
        const dbClient = getDocumentClient();
        await dbClient.send(
          new UpdateCommand({
            TableName: getTableName(),
            Key: { approval_id: approvalId },
            UpdateExpression: "SET #status = :pending, updated_at = :now REMOVE responded_by, responded_at",
            ExpressionAttributeNames: { "#status": "status" },
            ExpressionAttributeValues: {
              ":pending": "PENDING",
              ":now": now,
            },
          })
        );
      }
    } catch (dbErr) {
      console.error("failed to reset approval request status", dbErr);
    }
    
    throw error;
  }
}
