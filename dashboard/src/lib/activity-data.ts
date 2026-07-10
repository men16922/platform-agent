import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { awsCredentialsProvider } from "@vercel/oidc-aws-credentials-provider";

import {
  mockDeployments,
  mockAgentActivities,
  mockCloudHealth,
  type Deployment,
  type AgentActivity,
  type CloudHealth,
} from "@/lib/mock-data";

export type ActivityDataSource = "aws-live" | "demo" | "demo-fallback";

export interface DeploymentFeed {
  deployments: Deployment[];
  source: ActivityDataSource;
  syncedAt: string;
  notice?: string;
}

export interface AgentActivityFeed {
  activities: AgentActivity[];
  source: ActivityDataSource;
  syncedAt: string;
  notice?: string;
}

export interface ProviderHealthFeed {
  health: CloudHealth[];
  source: ActivityDataSource;
  syncedAt: string;
  notice?: string;
}

const DEFAULT_REGION = "us-east-1";
const DEFAULT_TABLE = "platform-agent-activity";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

function createDocumentClient() {
  const region = process.env.PLATFORM_AWS_REGION ?? DEFAULT_REGION;
  const roleArn = process.env.AWS_ROLE_ARN;

  if (process.env.VERCEL && !roleArn) {
    throw new Error("AWS_ROLE_ARN is required for live data on Vercel");
  }

  const client = new DynamoDBClient({
    region,
    credentials: roleArn
      ? awsCredentialsProvider({ roleArn, clientConfig: { region } })
      : undefined,
  });

  return DynamoDBDocumentClient.from(client, {
    marshallOptions: { removeUndefinedValues: true },
  });
}

function getTableName() {
  return process.env.DASHBOARD_ACTIVITY_TABLE ?? DEFAULT_TABLE;
}

// ─── Deployment feed ────────────────────────────────────────

function mapDeploymentItem(item: Record<string, unknown>): Deployment | null {
  const id = typeof item.deployment_id === "string" ? item.deployment_id : null;
  const service = typeof item.service === "string" ? item.service : null;
  if (!id || !service) return null;

  return {
    id,
    provider: isValidProvider(item.provider) ? item.provider : "aws",
    service,
    version: typeof item.version === "string" ? item.version : "unknown",
    environment: typeof item.environment === "string" ? item.environment : "production",
    status: isValidDeployStatus(item.status) ? item.status : "success",
    agent: typeof item.agent === "string" ? item.agent : "Unknown Agent",
    duration_sec: typeof item.duration_sec === "number" ? item.duration_sec : 0,
    created_at: typeof item.created_at === "string" ? item.created_at : new Date().toISOString(),
  };
}

export async function getDeploymentFeed(): Promise<DeploymentFeed> {
  const syncedAt = new Date().toISOString();
  if (!isLiveMode()) {
    return {
      deployments: mockDeployments,
      source: "demo",
      syncedAt,
      notice: "Demo dataset. Set DASHBOARD_DATA_SOURCE=aws to enable the read-only AWS feed.",
    };
  }

  try {
    const client = createDocumentClient();
    const result = await client.send(
      new QueryCommand({
        TableName: getTableName(),
        KeyConditionExpression: "PK = :pk",
        ExpressionAttributeValues: { ":pk": "DEPLOY" },
        ScanIndexForward: false, // newest first
        Limit: 50,
      }),
    );

    const deployments = (result.Items ?? [])
      .map((item) => mapDeploymentItem(item))
      .filter((item): item is Deployment => item !== null);

    return { deployments, source: "aws-live", syncedAt };
  } catch (error) {
    console.error("dashboard.deployments.live_fetch_failed", error);
    return {
      deployments: mockDeployments,
      source: "demo-fallback",
      syncedAt,
      notice: "AWS feed unavailable. Showing the demo dataset.",
    };
  }
}

// ─── Agent Activity feed ────────────────────────────────────

function mapActivityItem(item: Record<string, unknown>): AgentActivity | null {
  const id = typeof item.activity_id === "string" ? item.activity_id : null;
  const agent = typeof item.agent === "string" ? item.agent : null;
  if (!id || !agent) return null;

  return {
    id,
    agent,
    provider: isValidProvider(item.provider) ? item.provider : "aws",
    action: typeof item.action === "string" ? item.action : "Unknown action",
    tool_calls: Array.isArray(item.tool_calls)
      ? item.tool_calls.filter((t): t is string => typeof t === "string")
      : [],
    status: item.status === "failed" ? "failed" : "success",
    created_at: typeof item.created_at === "string" ? item.created_at : new Date().toISOString(),
  };
}

export async function getAgentActivityFeed(): Promise<AgentActivityFeed> {
  const syncedAt = new Date().toISOString();
  if (!isLiveMode()) {
    return {
      activities: mockAgentActivities,
      source: "demo",
      syncedAt,
      notice: "Demo dataset. Set DASHBOARD_DATA_SOURCE=aws to enable the read-only AWS feed.",
    };
  }

  try {
    const client = createDocumentClient();
    const result = await client.send(
      new QueryCommand({
        TableName: getTableName(),
        KeyConditionExpression: "PK = :pk",
        ExpressionAttributeValues: { ":pk": "ACTIVITY" },
        ScanIndexForward: false,
        Limit: 50,
      }),
    );

    const activities = (result.Items ?? [])
      .map((item) => mapActivityItem(item))
      .filter((item): item is AgentActivity => item !== null);

    return { activities, source: "aws-live", syncedAt };
  } catch (error) {
    console.error("dashboard.activities.live_fetch_failed", error);
    return {
      activities: mockAgentActivities,
      source: "demo-fallback",
      syncedAt,
      notice: "AWS feed unavailable. Showing the demo dataset.",
    };
  }
}

// ─── Provider Health feed ───────────────────────────────────

function mapHealthItem(item: Record<string, unknown>): CloudHealth | null {
  const provider = isValidProvider(item.provider) ? item.provider : null;
  if (!provider) return null;

  return {
    provider,
    status: isValidHealthStatus(item.status) ? item.status : "healthy",
    active_incidents: typeof item.active_incidents === "number" ? item.active_incidents : 0,
    last_deployment: typeof item.last_deployment_at === "string" ? item.last_deployment_at : new Date().toISOString(),
    last_check: typeof item.last_check === "string" ? item.last_check : new Date().toISOString(),
  };
}

export async function getProviderHealthFeed(): Promise<ProviderHealthFeed> {
  const syncedAt = new Date().toISOString();
  if (!isLiveMode()) {
    return {
      health: mockCloudHealth,
      source: "demo",
      syncedAt,
      notice: "Demo dataset. Set DASHBOARD_DATA_SOURCE=aws to enable the read-only AWS feed.",
    };
  }

  try {
    const client = createDocumentClient();
    const result = await client.send(
      new QueryCommand({
        TableName: getTableName(),
        KeyConditionExpression: "PK = :pk",
        ExpressionAttributeValues: { ":pk": "HEALTH" },
      }),
    );

    const health = (result.Items ?? [])
      .map((item) => mapHealthItem(item))
      .filter((item): item is CloudHealth => item !== null);

    // Ensure all 4 providers are represented, fill missing with defaults
    const providers: Array<"aws" | "gcp" | "azure" | "onprem"> = ["aws", "gcp", "azure", "onprem"];
    const healthMap = new Map(health.map((h) => [h.provider, h]));
    const fullHealth = providers.map(
      (p) =>
        healthMap.get(p) ?? {
          provider: p,
          status: "healthy" as const,
          active_incidents: 0,
          last_deployment: syncedAt,
          last_check: syncedAt,
        },
    );

    return { health: fullHealth, source: "aws-live", syncedAt };
  } catch (error) {
    console.error("dashboard.health.live_fetch_failed", error);
    return {
      health: mockCloudHealth,
      source: "demo-fallback",
      syncedAt,
      notice: "AWS feed unavailable. Showing the demo dataset.",
    };
  }
}

// ─── Type guards ────────────────────────────────────────────

function isValidProvider(v: unknown): v is "aws" | "gcp" | "azure" | "onprem" {
  return v === "aws" || v === "gcp" || v === "azure" || v === "onprem";
}

function isValidDeployStatus(v: unknown): v is "success" | "failed" | "rolling-back" {
  return v === "success" || v === "failed" || v === "rolling-back";
}

function isValidHealthStatus(v: unknown): v is "healthy" | "degraded" | "down" {
  return v === "healthy" || v === "degraded" || v === "down";
}
