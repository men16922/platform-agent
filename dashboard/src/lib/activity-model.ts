/**
 * Durable Read Model — Deployment / Agent Activity / Provider Health
 *
 * DynamoDB single-table design for the dashboard read path.
 * Table: `platform-agent-activity`
 *
 * Access patterns:
 * 1. List recent deployments (all providers, last 24h)        → PK=DEPLOY, SK=<iso-ts>#<id>  (descending scan)
 * 2. List deployments by provider                             → GSI1: provider#DEPLOY, SK=<ts>
 * 3. List agent activities (all providers, last 24h)          → PK=ACTIVITY, SK=<iso-ts>#<id>
 * 4. Get provider health summary                              → PK=HEALTH, SK=<provider>
 * 5. Get provider health history (last N checks)              → PK=HEALTH_HISTORY#<provider>, SK=<ts>
 *
 * Key schema:
 *   PK (partition key): string — entity type prefix
 *   SK (sort key): string — timestamp#id for ordering
 *
 * GSI1 (provider index):
 *   GSI1PK: <provider>#<entity_type>   e.g. "aws#DEPLOY"
 *   GSI1SK: <iso-timestamp>#<id>
 *
 * TTL: 30 days for deployment/activity records; health records never expire.
 */

// ─── Deployment record ──────────────────────────────────────

export interface DeploymentRecord {
  /** Table keys */
  PK: "DEPLOY";
  SK: string; // ISO timestamp#deployment_id (descending: invert or use reverse scan)

  /** GSI1 keys */
  GSI1PK: string; // e.g. "aws#DEPLOY"
  GSI1SK: string; // same as SK

  /** Domain fields */
  deployment_id: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  service: string;
  version: string;
  environment: string;
  status: "success" | "failed" | "rolling-back";
  agent: string;
  duration_sec: number;
  pipeline_steps: PipelineStep[];
  created_at: string; // ISO 8601
  updated_at: string;

  /** TTL — 30 days from creation */
  ttl: number;
}

export interface PipelineStep {
  name: string; // "build" | "push" | "deploy" | "validate" | "guard"
  status: "success" | "failed" | "skipped" | "running";
  started_at?: string;
  completed_at?: string;
  detail?: string;
}

// ─── Agent Activity record ──────────────────────────────────

export interface AgentActivityRecord {
  PK: "ACTIVITY";
  SK: string; // ISO timestamp#activity_id

  GSI1PK: string; // e.g. "aws#ACTIVITY"
  GSI1SK: string;

  activity_id: string;
  agent: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  action: string;
  tool_calls: string[];
  status: "success" | "failed";
  error_message?: string;
  duration_ms?: number;
  created_at: string;

  ttl: number;
}

// ─── Provider Health snapshot ───────────────────────────────

export interface ProviderHealthRecord {
  PK: "HEALTH";
  SK: string; // provider name: "aws" | "gcp" | "azure" | "onprem"

  provider: "aws" | "gcp" | "azure" | "onprem";
  status: "healthy" | "degraded" | "down";
  active_incidents: number;
  last_deployment_id?: string;
  last_deployment_at?: string;
  last_check: string;
  updated_at: string;
  // No TTL — health is always current
}

export interface ProviderHealthHistoryRecord {
  PK: string; // "HEALTH_HISTORY#aws"
  SK: string; // ISO timestamp

  provider: "aws" | "gcp" | "azure" | "onprem";
  status: "healthy" | "degraded" | "down";
  active_incidents: number;
  checked_at: string;

  ttl: number; // 90 days
}

// ─── Helper constructors ────────────────────────────────────

const TTL_30_DAYS = 30 * 24 * 60 * 60;
const TTL_90_DAYS = 90 * 24 * 60 * 60;

export function makeDeploymentRecord(
  fields: Omit<DeploymentRecord, "PK" | "SK" | "GSI1PK" | "GSI1SK" | "ttl" | "updated_at">,
): DeploymentRecord {
  const sk = `${fields.created_at}#${fields.deployment_id}`;
  return {
    ...fields,
    PK: "DEPLOY",
    SK: sk,
    GSI1PK: `${fields.provider}#DEPLOY`,
    GSI1SK: sk,
    updated_at: fields.created_at,
    ttl: Math.floor(Date.now() / 1000) + TTL_30_DAYS,
  };
}

export function makeAgentActivityRecord(
  fields: Omit<AgentActivityRecord, "PK" | "SK" | "GSI1PK" | "GSI1SK" | "ttl">,
): AgentActivityRecord {
  const sk = `${fields.created_at}#${fields.activity_id}`;
  return {
    ...fields,
    PK: "ACTIVITY",
    SK: sk,
    GSI1PK: `${fields.provider}#ACTIVITY`,
    GSI1SK: sk,
    ttl: Math.floor(Date.now() / 1000) + TTL_30_DAYS,
  };
}

export function makeProviderHealthRecord(
  fields: Omit<ProviderHealthRecord, "PK" | "SK" | "updated_at">,
): ProviderHealthRecord {
  return {
    ...fields,
    PK: "HEALTH",
    SK: fields.provider,
    updated_at: fields.last_check,
  };
}

export function makeProviderHealthHistoryRecord(
  fields: Omit<ProviderHealthHistoryRecord, "PK" | "SK" | "ttl">,
): ProviderHealthHistoryRecord {
  return {
    ...fields,
    PK: `HEALTH_HISTORY#${fields.provider}`,
    SK: fields.checked_at,
    ttl: Math.floor(Date.now() / 1000) + TTL_90_DAYS,
  };
}
