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
  // Which backend owns this approval: AWS (Step Functions task token) or the
  // on-prem webhook (offline JSONL store). Drives the approve/reject routing.
  source?: "aws" | "onprem";
}

const DEFAULT_TABLE = "incident-approval-requests";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

function getTableName() {
  return process.env.DASHBOARD_APPROVAL_TABLE ?? DEFAULT_TABLE;
}

// ---------------------------------------------------------------------------
// On-Prem approvals (hybrid) — the on-prem PATH B webhook parks P2 remediations
// in an offline store and exposes them over HTTP, mirroring how the deployments
// dashboard merges AWS DynamoDB with the on-prem runtime. Reads/actions go to
// the webhook over HTTP (like agents/onprem-status), so no file paths leak into
// the dashboard and Vercel simply sees the webhook as offline.
// ---------------------------------------------------------------------------

function getOnPremWebhookUrl() {
  return process.env.ONPREM_WEBHOOK_URL ?? "http://127.0.0.1:8078";
}

interface OnPremPendingRecord {
  approval_id: string;
  status?: string;
  service?: string;
  severity?: "P1" | "P2" | "P3";
  runbook_id?: string;
  actions?: string[];
  created_at?: string;
  updated_at?: string;
  decision?: { analyzer?: { root_cause?: string; confidence?: number } };
}

function mapOnPremApproval(record: OnPremPendingRecord): ApprovalRequest {
  const analyzer = record.decision?.analyzer ?? {};
  return {
    approval_id: record.approval_id,
    status: "PENDING",
    task_token: "",
    runbook_id: record.runbook_id ?? "generic-recovery",
    actions: record.actions ?? [],
    severity: record.severity ?? "P3",
    alarm_name: record.service ?? "on-prem incident",
    root_cause: analyzer.root_cause ?? "On-prem Day-2 remediation awaiting approval.",
    confidence: typeof analyzer.confidence === "number" ? analyzer.confidence : 0,
    request_kind: "onprem-incident",
    request_subject: record.service ?? undefined,
    request_summary: analyzer.root_cause ?? undefined,
    created_at: record.created_at ?? new Date().toISOString(),
    updated_at: record.updated_at ?? record.created_at ?? new Date().toISOString(),
    source: "onprem",
  };
}

async function fetchOnPremPending(): Promise<ApprovalRequest[]> {
  try {
    const res = await fetch(`${getOnPremWebhookUrl()}/pending`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = (await res.json()) as { pending?: OnPremPendingRecord[] };
    return (data.pending ?? []).map(mapOnPremApproval);
  } catch {
    // The on-prem webhook is a local service; absent on Vercel — treat as none.
    return [];
  }
}

async function getOnPremApproval(approvalId: string): Promise<ApprovalRequest | null> {
  const pending = await fetchOnPremPending();
  return pending.find((a) => a.approval_id === approvalId) ?? null;
}

async function decideOnPrem(approvalId: string, decision: "approve" | "reject"): Promise<boolean> {
  const res = await fetch(`${getOnPremWebhookUrl()}/${decision}/${approvalId}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`On-prem webhook ${decision} failed (${res.status}): ${detail}`);
  }
  return true;
}

// In-memory fallback
const mockApprovals: ApprovalRequest[] = [
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
  // On-prem approvals are merged in regardless of the AWS data-source mode, so a
  // local operator sees on-prem P2 gates even without AWS wired up (hybrid).
  const onprem = await fetchOnPremPending();

  if (!isLiveMode()) {
    const aws = mockApprovals.filter((a) => a.status === "PENDING").map((a) => ({ ...a, source: "aws" as const }));
    return [...aws, ...onprem];
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
    const aws = ((result.Items as ApprovalRequest[]) || []).map((a) => ({ ...a, source: "aws" as const }));
    return [...aws, ...onprem];
  } catch (error) {
    console.error("approval-data.listPendingApprovals.failed", error);
    const aws = mockApprovals.filter((a) => a.status === "PENDING").map((a) => ({ ...a, source: "aws" as const }));
    return [...aws, ...onprem];
  }
}

export async function getApprovalRequest(approvalId: string): Promise<ApprovalRequest | null> {
  // On-prem approvals live in the webhook's pending list; check there first so
  // the approve/reject routing knows to call the webhook rather than SFN.
  const onprem = await getOnPremApproval(approvalId);
  if (onprem) return onprem;

  if (!isLiveMode()) {
    const found = mockApprovals.find((a) => a.approval_id === approvalId);
    return found ? { ...found, source: "aws" } : null;
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new GetCommand({
        TableName: getTableName(),
        Key: { approval_id: approvalId },
      })
    );
    return result.Item ? { ...(result.Item as ApprovalRequest), source: "aws" } : null;
  } catch (error) {
    console.error("approval-data.getApprovalRequest.failed", error);
    const found = mockApprovals.find((a) => a.approval_id === approvalId);
    return found ? { ...found, source: "aws" } : null;
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

  // On-prem: replay the parked decision through the executor via the webhook.
  if (request.source === "onprem") {
    return decideOnPrem(approvalId, "approve");
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

  // On-prem: reject the parked decision via the webhook (no execution).
  if (request.source === "onprem") {
    return decideOnPrem(approvalId, "reject");
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
