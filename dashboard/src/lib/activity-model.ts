/**
 * Durable Read Model — Deployment / Agent Activity / Provider Health
 *
 * DynamoDB single-table design for the dashboard read path.
 * Table: `platform-agent-activity`
 *
 * THIS FILE IS DOCUMENTATION. Nothing imports it. Rows are written by Python
 * (`src/agents/`) and read by `activity-data.ts`, which maps untyped records
 * defensively rather than through these types. It is kept because the key
 * design is not written down anywhere else — and it is guarded by
 * `tests/test_activity_read_model_matches_writers.py`, which derives the real
 * shapes from the writers, because an unread declaration drifts silently. It
 * had: it described a `duration_ms` nobody writes while omitting `trace`,
 * `cost_metrics` and `deployment_id`, the three fields the deployment detail
 * page is built on.
 *
 * TWO WRITER FAMILIES, NEITHER A SUPERSET OF THE OTHER
 *
 *   agent path — `ai/deploy_recorder.py` (_write_row, record_rollback,
 *     record_route_activity). Writes almost every row in practice. Adds the
 *     tracing/correlation fields (`type`, `cluster`, `deployment_id`, `model`,
 *     `trace`, `cost_metrics`). Writes NO `ttl` and NO GSI1 keys.
 *
 *   lambda path — `operations/activity_writer.py` (record_deployment,
 *     record_agent_activity, update_provider_health). Adds `ttl`, GSI1 keys and
 *     `pipeline_steps`. Writes none of the agent path's correlation fields.
 *
 * Access patterns — what actually exists:
 *   1. List recent deployments      → PK=DEPLOY,   SK=<iso-ts>#<id>   USED
 *   2. List recent agent activities → PK=ACTIVITY, SK=<iso-ts>#<id>   USED
 *   3. Provider health summary      → PK=HEALTH,   SK=<provider>      USED
 *   4. List deployments by provider → GSI1                            NOT USED
 *   5. Provider health history      → PK=HEALTH_HISTORY#<provider>    NOT WRITTEN
 *
 * ⚠️ GSI1 is populated by the lambda path only, and queried by nothing. A
 *    provider-scoped query added today would silently return that subset and
 *    miss every row the agent wrote. Either backfill the keys in
 *    `deploy_recorder` first, or do not add the query.
 *
 * ⚠️ TTL is likewise lambda-path only. Rows written by the agent path carry no
 *    `ttl` attribute and therefore NEVER EXPIRE. The "30 day retention" this
 *    file used to state as fact does not hold for the dominant writer.
 *
 * Key schema:
 *   PK: entity type prefix — "DEPLOY" | "ACTIVITY" | "HEALTH"
 *   SK: "<iso-timestamp>#<id>" for DEPLOY/ACTIVITY (lexicographic = chronological),
 *       the provider name for HEALTH.
 *   Reads are Scans/Queries by PK with newest-first sorting done client-side;
 *   `mergeActivity` folds every ACTIVITY row sharing a `deployment_id`.
 */

// ─── Deployment record (PK=DEPLOY) ──────────────────────────

/** Written by every DEPLOY writer. */
export interface DeploymentRecordCore {
  PK: "DEPLOY";
  SK: string; // "<iso-ts>#<deployment_id>"

  deployment_id: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  service: string;
  version: string;
  status: "success" | "failed" | "rolling-back" | "rolled-back";
  agent: string;
  duration_sec: number;
  created_at: string; // ISO 8601
}

export interface DeploymentRecord extends DeploymentRecordCore {
  /**
   * The tier the caller declared — free text ("production"), NOT a registry
   * tenant/env pair. Optional because the agent path stores it only when the
   * caller actually declared one: the dashboard's natural-language deploy sends
   * no environment at all, and defaulting it here meant every such row claimed
   * a tier nobody chose. Absent means "not declared", which is a different fact
   * from any particular tier. See DECISIONS D36.
   */
  environment?: string;

  /** agent path only — the lifecycle/correlation keys the dashboard IA needs. */
  type?: "deploy" | "provision";
  /** agent path only — links a deploy to the provisioning that made its cluster. */
  cluster?: string;

  /** lambda path only. */
  GSI1PK?: string; // "<provider>#DEPLOY"
  GSI1SK?: string; // same as SK
  pipeline_steps?: PipelineStep[];
  updated_at?: string;
  ttl?: number; // absent on agent-path rows — see the TTL warning above
}

export interface PipelineStep {
  name: string; // "build" | "push" | "deploy" | "validate" | "guard"
  status: "success" | "failed" | "skipped" | "running";
  started_at?: string;
  completed_at?: string;
  detail?: string;
}

// ─── Agent Activity record (PK=ACTIVITY) ────────────────────

/** Written by every ACTIVITY writer. */
export interface AgentActivityRecordCore {
  PK: "ACTIVITY";
  SK: string; // "<iso-ts>#<activity_id>"

  activity_id: string;
  agent: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  action: string;
  tool_calls: string[];
  status: "success" | "failed";
  created_at: string;
}

export interface AgentActivityRecord extends AgentActivityRecordCore {
  /** agent path only. */
  type?: "deploy" | "provision" | "route";
  instruction?: string;
  summary?: string;
  trace?: string; // JSON-encoded ordered trace, truncated at 350k

  /**
   * agent path, and only on rows scoped to a deployment. `deployment_id` is
   * what routes a row into `mergeActivity` and onto the deployment detail
   * page, which is why a row carrying it must also carry `cost_metrics` —
   * being the newest row, one without it blanks the panel for the whole
   * deployment. Guarded in tests/test_rollback_cost_metrics.py.
   */
  deployment_id?: string;
  cost_metrics?: CostMetrics;
  model?: string;

  /** lambda path only. */
  GSI1PK?: string; // "<provider>#ACTIVITY"
  GSI1SK?: string;
  ttl?: number;
}

/** Per-run sub-metrics derived from the trace, never estimated. */
export interface CostMetrics {
  tool_calls_total: number;
  tool_calls_by_name: Record<string, number>;
  reasoning_steps: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

// ─── Provider Health snapshot (PK=HEALTH) ───────────────────

export interface ProviderHealthRecord {
  PK: "HEALTH";
  SK: string; // the provider name

  provider: "aws" | "gcp" | "azure" | "onprem";
  status: "healthy" | "degraded" | "down";
  active_incidents: number;
  last_check: string;
  updated_at: string;
  // No TTL — health is always current, and this is the one row type where the
  // absence is intended rather than an omission.
}
