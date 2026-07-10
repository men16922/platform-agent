/**
 * Mock data simulating reads from DynamoDB (AWS), Firestore (GCP), Cosmos DB (Azure).
 * In production, these would be API routes calling the actual cloud SDKs.
 */

export interface Incident {
  id: string;
  provider: "aws" | "gcp" | "azure";
  alarm_name: string;
  severity: "P1" | "P2" | "P3";
  mode: "AUTO" | "APPROVE" | "MANUAL";
  root_cause: string;
  runbook_id: string;
  resolved: boolean;
  executed_actions: string[];
  created_at: string;
}

export interface Deployment {
  id: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  service: string;
  version: string;
  environment: string;
  status: "success" | "failed" | "rolling-back";
  agent: string;
  duration_sec: number;
  created_at: string;
}

export interface AgentActivity {
  id: string;
  agent: string;
  provider: "aws" | "gcp" | "azure" | "onprem";
  action: string;
  tool_calls: string[];
  status: "success" | "failed";
  created_at: string;
}

export interface CloudHealth {
  provider: "aws" | "gcp" | "azure" | "onprem";
  status: "healthy" | "degraded" | "down";
  active_incidents: number;
  last_deployment: string;
  last_check: string;
}

// --- Mock data ---

export const mockIncidents: Incident[] = [
  {
    id: "INC-A3F2B1C8",
    provider: "aws",
    alarm_name: "eks-pod-oom-alert",
    severity: "P1",
    mode: "AUTO",
    root_cause: "Memory leak in orders-api v1.4.1 causing OOM kills. Heap grows linearly after 2h uptime due to unclosed DB connections in connection pool.",
    runbook_id: "eks-pod-oom",
    resolved: true,
    executed_actions: ["AWS-RestartEKSPod", "AWS-ScaleNodeGroup"],
    created_at: "2026-07-10T08:23:00Z",
  },
  {
    id: "GCP-INC-7D4E9A2F",
    provider: "gcp",
    alarm_name: "pod-oom-alert",
    severity: "P2",
    mode: "APPROVE",
    root_cause: "GKE pod memory utilization above 90% due to traffic spike from marketing campaign launch.",
    runbook_id: "generic-recovery",
    resolved: true,
    executed_actions: ["GCP-RolloutRestartGKEWorkload", "GCP-ScaleGKEWorkload"],
    created_at: "2026-07-10T09:15:00Z",
  },
  {
    id: "AZ-INC-1B8C3E5D",
    provider: "azure",
    alarm_name: "aks-pod-oom-alert",
    severity: "P2",
    mode: "APPROVE",
    root_cause: "AKS pod memory pressure triggered by batch processing job consuming excessive memory.",
    runbook_id: "generic-recovery",
    resolved: true,
    executed_actions: ["AZURE-RolloutRestartAKSWorkload", "AZURE-ScaleAKSNodePool"],
    created_at: "2026-07-10T10:42:00Z",
  },
  {
    id: "INC-9F1E7B3A",
    provider: "aws",
    alarm_name: "lambda-throttle-alert",
    severity: "P2",
    mode: "AUTO",
    root_cause: "Lambda concurrent execution limit reached during peak API traffic.",
    runbook_id: "lambda-throttle",
    resolved: true,
    executed_actions: ["AWS-IncreaseLambdaConcurrency"],
    created_at: "2026-07-10T11:05:00Z",
  },
  {
    id: "GCP-INC-4A2F8C6E",
    provider: "gcp",
    alarm_name: "cloudsql-cpu-high",
    severity: "P3",
    mode: "MANUAL",
    root_cause: "Cloud SQL CPU trending upward due to unoptimized query patterns. No immediate risk.",
    runbook_id: "db-cpu-high",
    resolved: false,
    executed_actions: [],
    created_at: "2026-07-10T12:30:00Z",
  },
  {
    id: "AZ-INC-6D9B2E4A",
    provider: "azure",
    alarm_name: "sql-cpu-high-alert",
    severity: "P3",
    mode: "MANUAL",
    root_cause: "Azure SQL Database CPU above 80% during nightly ETL job. Expected behavior.",
    runbook_id: "db-cpu-high",
    resolved: false,
    executed_actions: [],
    created_at: "2026-07-10T13:15:00Z",
  },
];

export const mockDeployments: Deployment[] = [
  {
    id: "DEP-001",
    provider: "aws",
    service: "orders-api",
    version: "v1.4.2",
    environment: "production",
    status: "success",
    agent: "Strands Agent (Bedrock Claude)",
    duration_sec: 45,
    created_at: "2026-07-10T07:00:00Z",
  },
  {
    id: "DEP-002",
    provider: "gcp",
    service: "orders-api",
    version: "v1.4.2",
    environment: "production",
    status: "success",
    agent: "ADK Agent (Gemini 3.5 Flash)",
    duration_sec: 52,
    created_at: "2026-07-10T07:01:00Z",
  },
  {
    id: "DEP-003",
    provider: "azure",
    service: "orders-api",
    version: "v1.4.2",
    environment: "production",
    status: "success",
    agent: "MS Agent (GPT-5.4)",
    duration_sec: 48,
    created_at: "2026-07-10T07:02:00Z",
  },
  {
    id: "DEP-004",
    provider: "onprem",
    service: "orders-api",
    version: "v1.4.2",
    environment: "staging",
    status: "success",
    agent: "On-Prem Agent (Local LLM)",
    duration_sec: 30,
    created_at: "2026-07-10T07:03:00Z",
  },
  {
    id: "DEP-005",
    provider: "aws",
    service: "payment-service",
    version: "v2.1.0",
    environment: "staging",
    status: "failed",
    agent: "Strands Agent (Bedrock Claude)",
    duration_sec: 120,
    created_at: "2026-07-10T14:00:00Z",
  },
];

export const mockAgentActivities: AgentActivity[] = [
  {
    id: "ACT-001",
    agent: "Strands Agent",
    provider: "aws",
    action: "Deploy orders-api v1.4.2",
    tool_calls: ["aws_build_image", "aws_push_image", "aws_deploy", "validate"],
    status: "success",
    created_at: "2026-07-10T07:00:00Z",
  },
  {
    id: "ACT-002",
    agent: "ADK Agent",
    provider: "gcp",
    action: "Deploy orders-api v1.4.2",
    tool_calls: ["gcp_build_image", "gcp_push_image", "gcp_deploy", "validate"],
    status: "success",
    created_at: "2026-07-10T07:01:00Z",
  },
  {
    id: "ACT-003",
    agent: "MS Agent",
    provider: "azure",
    action: "Deploy orders-api v1.4.2",
    tool_calls: ["azure_build_image", "azure_push_image", "azure_deploy", "validate"],
    status: "success",
    created_at: "2026-07-10T07:02:00Z",
  },
  {
    id: "ACT-004",
    agent: "Detector (AWS)",
    provider: "aws",
    action: "Incident detection: eks-pod-oom-alert",
    tool_calls: ["logs:StartQuery", "xray:GetTraceSummaries", "cloudwatch:GetMetricStatistics"],
    status: "success",
    created_at: "2026-07-10T08:23:00Z",
  },
  {
    id: "ACT-005",
    agent: "Analyzer (GCP)",
    provider: "gcp",
    action: "Root cause analysis via Vertex AI Gemini",
    tool_calls: ["vertexai.generate_content", "firestore.query"],
    status: "success",
    created_at: "2026-07-10T09:15:30Z",
  },
  {
    id: "ACT-006",
    agent: "Executor (Azure)",
    provider: "azure",
    action: "Auto-remediation: AZURE-RolloutRestartAKSWorkload",
    tool_calls: ["az aks command invoke", "cosmos.upsert_item"],
    status: "success",
    created_at: "2026-07-10T10:43:00Z",
  },
];

export const mockCloudHealth: CloudHealth[] = [
  {
    provider: "aws",
    status: "healthy",
    active_incidents: 0,
    last_deployment: "2026-07-10T14:00:00Z",
    last_check: "2026-07-10T17:00:00Z",
  },
  {
    provider: "gcp",
    status: "degraded",
    active_incidents: 1,
    last_deployment: "2026-07-10T07:01:00Z",
    last_check: "2026-07-10T17:00:00Z",
  },
  {
    provider: "azure",
    status: "healthy",
    active_incidents: 1,
    last_deployment: "2026-07-10T07:02:00Z",
    last_check: "2026-07-10T17:00:00Z",
  },
  {
    provider: "onprem",
    status: "healthy",
    active_incidents: 0,
    last_deployment: "2026-07-10T07:03:00Z",
    last_check: "2026-07-10T17:00:00Z",
  },
];
