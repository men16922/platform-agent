import { readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { QueryCommand } from "@aws-sdk/lib-dynamodb";
import { getDocumentClient } from "@/lib/aws-client";

import {
  mockDeployments,
  mockAgentActivities,
  mockCloudHealth,
  type Deployment,
  type AgentActivity,
  type CloudHealth,
} from "@/lib/mock-data";

export type ActivityDataSource = "aws-live" | "local" | "hybrid" | "demo" | "demo-fallback";

// ─── Local offline store (JSONL written by the on-prem router's deploy_recorder) ──
// Keeps the on-prem path fully offline: no DynamoDB. Enabled with
// DASHBOARD_DATA_SOURCE=local and PLATFORM_ACTIVITY_FILE pointing at the same file.

function isLocalMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "local";
}

function localStorePath() {
  const p = process.env.PLATFORM_ACTIVITY_FILE || path.join(os.homedir(), ".platform-agent", "activity.jsonl");
  return p.startsWith("~/") ? path.join(os.homedir(), p.slice(2)) : p;
}

async function readLocalItems(pk: string): Promise<Record<string, unknown>[]> {
  let raw: string;
  try {
    raw = await readFile(localStorePath(), "utf-8");
  } catch {
    return []; // no file yet → empty feed
  }
  const items = raw
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => {
      try {
        return JSON.parse(line) as Record<string, unknown>;
      } catch {
        return null;
      }
    })
    .filter((x): x is Record<string, unknown> => x !== null && x.PK === pk);
  // SK is "<iso>#<id>" → lexicographic sort gives newest-first when reversed.
  items.sort((a, b) => String(b.SK ?? "").localeCompare(String(a.SK ?? "")));
  return items;
}

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

const DEFAULT_TABLE = "platform-agent-activity";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

function getTableName() {
  return process.env.DASHBOARD_ACTIVITY_TABLE ?? DEFAULT_TABLE;
}

// ─── Hybrid: merge AWS (DynamoDB) + On-Prem (local JSONL) into one feed ──

function isHybridMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "hybrid";
}

async function queryDynamoItems(pk: string, limit = 50): Promise<Record<string, unknown>[]> {
  try {
    const client = getDocumentClient();
    const result = await client.send(
      new QueryCommand({
        TableName: getTableName(),
        KeyConditionExpression: "PK = :pk",
        ExpressionAttributeValues: { ":pk": pk },
        ScanIndexForward: false,
        Limit: limit,
      }),
    );
    return result.Items ?? [];
  } catch (error) {
    // In hybrid mode a missing/unreachable AWS feed must not break the on-prem feed.
    console.error("dashboard.hybrid.dynamo_query_failed", pk, error);
    return [];
  }
}

function dedupeById<T extends { id: string }>(rows: T[]): T[] {
  const seen = new Set<string>();
  return rows.filter((r) => (seen.has(r.id) ? false : (seen.add(r.id), true)));
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
  if (isHybridMode()) {
    const [aws, local] = await Promise.all([queryDynamoItems("DEPLOY"), readLocalItems("DEPLOY")]);
    const deployments = dedupeById(
      [...aws, ...local].map(mapDeploymentItem).filter((d): d is Deployment => d !== null),
    )
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(0, 50);
    return { deployments, source: "hybrid", syncedAt };
  }
  if (isLocalMode()) {
    const deployments = (await readLocalItems("DEPLOY"))
      .map(mapDeploymentItem)
      .filter((d): d is Deployment => d !== null)
      .slice(0, 50);
    return { deployments, source: "local", syncedAt };
  }
  if (!isLiveMode()) {
    return {
      deployments: mockDeployments,
      source: "demo",
      syncedAt,
      notice: "Demo dataset. Set DASHBOARD_DATA_SOURCE=aws to enable the read-only AWS feed.",
    };
  }

  try {
    const client = getDocumentClient();
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

export interface DeploymentDetail {
  deployment: Deployment | null;
  activity: AgentActivity | null;
  source: ActivityDataSource;
}

export async function getDeploymentDetail(id: string): Promise<DeploymentDetail> {
  if (isHybridMode()) {
    const [awsDep, localDep, awsAct, localAct] = await Promise.all([
      queryDynamoItems("DEPLOY"),
      readLocalItems("DEPLOY"),
      queryDynamoItems("ACTIVITY"),
      readLocalItems("ACTIVITY"),
    ]);
    const deployment =
      [...localDep, ...awsDep].map(mapDeploymentItem).find((d): d is Deployment => d?.id === id) ?? null;
    const activity =
      [...localAct, ...awsAct].map(mapActivityItem).find((a): a is AgentActivity => a?.deployment_id === id) ?? null;
    return { deployment, activity, source: "hybrid" };
  }
  if (isLocalMode()) {
    const deployment =
      (await readLocalItems("DEPLOY")).map(mapDeploymentItem).find((d): d is Deployment => d?.id === id) ?? null;
    const activity =
      (await readLocalItems("ACTIVITY"))
        .map(mapActivityItem)
        .find((a): a is AgentActivity => a?.deployment_id === id) ?? null;
    return { deployment, activity, source: "local" };
  }
  if (!isLiveMode()) {
    return { deployment: mockDeployments.find((d) => d.id === id) ?? null, activity: null, source: "demo" };
  }
  try {
    const client = getDocumentClient();
    const query = (pk: string) =>
      client.send(
        new QueryCommand({
          TableName: getTableName(),
          KeyConditionExpression: "PK = :pk",
          FilterExpression: "deployment_id = :id",
          ExpressionAttributeValues: { ":pk": pk, ":id": id },
        }),
      );
    const [depRes, actRes] = await Promise.all([query("DEPLOY"), query("ACTIVITY")]);
    const deployment = (depRes.Items ?? []).map(mapDeploymentItem).find((d): d is Deployment => d !== null) ?? null;
    const activity = (actRes.Items ?? []).map(mapActivityItem).find((a): a is AgentActivity => a !== null) ?? null;
    return { deployment, activity, source: "aws-live" };
  } catch (error) {
    console.error("dashboard.deployment.detail_fetch_failed", error);
    return { deployment: mockDeployments.find((d) => d.id === id) ?? null, activity: null, source: "demo-fallback" };
  }
}

// ─── Agent Activity feed ────────────────────────────────────

function parseTrace(raw: unknown): AgentActivity["trace"] {
  if (typeof raw !== "string" || !raw) return undefined;
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return undefined;
    return parsed
      .filter((s): s is Record<string, unknown> => typeof s === "object" && s !== null)
      .map((s) => {
        // reasoning item
        if (s.kind === "reasoning") {
          return { kind: "reasoning" as const, text: typeof s.text === "string" ? s.text : "" };
        }
        // tool item (also the legacy shape, which had no "kind")
        return {
          kind: "tool" as const,
          tool: typeof s.tool === "string" ? s.tool : "unknown",
          args: typeof s.args === "object" && s.args !== null ? (s.args as Record<string, unknown>) : undefined,
          result: s.result,
        };
      });
  } catch {
    return undefined;
  }
}

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
    deployment_id: typeof item.deployment_id === "string" ? item.deployment_id : undefined,
    model: typeof item.model === "string" ? item.model : undefined,
    instruction: typeof item.instruction === "string" ? item.instruction : undefined,
    summary: typeof item.summary === "string" ? item.summary : undefined,
    trace: parseTrace(item.trace),
  };
}

export async function getAgentActivityFeed(): Promise<AgentActivityFeed> {
  const syncedAt = new Date().toISOString();
  if (isHybridMode()) {
    const [aws, local] = await Promise.all([queryDynamoItems("ACTIVITY"), readLocalItems("ACTIVITY")]);
    const activities = dedupeById(
      [...aws, ...local].map(mapActivityItem).filter((a): a is AgentActivity => a !== null),
    )
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(0, 50);
    return { activities, source: "hybrid", syncedAt };
  }
  if (isLocalMode()) {
    const activities = (await readLocalItems("ACTIVITY"))
      .map(mapActivityItem)
      .filter((a): a is AgentActivity => a !== null)
      .slice(0, 50);
    return { activities, source: "local", syncedAt };
  }
  if (!isLiveMode()) {
    return {
      activities: mockAgentActivities,
      source: "demo",
      syncedAt,
      notice: "Demo dataset. Set DASHBOARD_DATA_SOURCE=aws to enable the read-only AWS feed.",
    };
  }

  try {
    const client = getDocumentClient();
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
    const client = getDocumentClient();
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
