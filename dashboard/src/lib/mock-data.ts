/**
 * Mock data simulating reads from DynamoDB (AWS), Firestore (GCP), Cosmos DB (Azure).
 * In production, these would be API routes calling the actual cloud SDKs.
 */

// Reconciliation gate result (deterministic grounding check). When the analyzer's
// LLM conclusions aren't grounded in detector evidence, an AUTO decision is
// downgraded to APPROVE — this carries the "why".
export interface Reconciliation {
  grounded: boolean;
  issues: string[];
  grounding_ratio: number;
  mode_override: string | null; // e.g. "APPROVE" when downgraded
}

export interface Incident {
  id: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  alarm_name: string;
  severity: "P1" | "P2" | "P3";
  mode: "AUTO" | "APPROVE" | "MANUAL";
  root_cause: string;
  runbook_id: string;
  resolved: boolean;
  executed_actions: string[];
  created_at: string;
  reconciliation?: Reconciliation;
}

// Domain of a row (which page it belongs to). Rollback is a STATUS, not a type,
// so a rolled-back provision stays on Provisioning and a rolled-back deploy on Deployments.
export type DeploymentType = "provision" | "deploy";

export interface Deployment {
  id: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  type: DeploymentType;
  cluster: string; // correlation key: a deploy's target cluster == a provision's service
  service: string;
  version: string;
  environment: string;
  status: "success" | "failed" | "rolling-back" | "rolled-back";
  agent: string;
  duration_sec: number;
  created_at: string;
}

// One planned specialist step in an agents-as-tools orchestration.
export interface PlanStepView {
  role: string;
  instruction?: string;
  delegated?: boolean;
}

export interface TraceItem {
  kind: "reasoning" | "tool" | "consensus" | "plan";
  text?: string; // reasoning
  tool?: string; // tool
  args?: Record<string, unknown>;
  result?: unknown;
  // consensus (self-consistency routing)
  role?: string;
  agreement?: number;
  votes?: Record<string, number>;
  fell_back?: boolean;
  samples?: number;
  // plan (agents-as-tools chaining)
  steps?: PlanStepView[];
}

// Per-run cost/usage sub-metrics aggregated from the execution trace.
export interface CostMetrics {
  tool_calls_total: number;
  tool_calls_by_name: Record<string, number>;
  reasoning_steps: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface AgentActivity {
  id: string;
  agent: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  action: string;
  tool_calls: string[];
  status: "success" | "failed";
  created_at: string;
  // Observability (chat/router deploys): links + full execution trace.
  deployment_id?: string;
  model?: string;
  instruction?: string;
  summary?: string;
  trace?: TraceItem[];
  cost_metrics?: CostMetrics;
}

export interface CloudHealth {
  provider: "aws" | "gcp" | "azure" | "onprem";
  status: "healthy" | "degraded" | "down";
  active_incidents: number;
  last_deployment: string;
  last_check: string;
}

// --- Mock data ---

export const mockIncidents: Incident[] = [];

export const mockDeployments: Deployment[] = [];

export const mockAgentActivities: AgentActivity[] = [];

export const mockCloudHealth: CloudHealth[] = [];
