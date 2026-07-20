import { ScanCommand } from "@aws-sdk/lib-dynamodb";
import { getDocumentClient } from "@/lib/aws-client";

import { mockIncidents, type Incident } from "@/lib/mock-data";

export type IncidentDataSource = "aws-live" | "local" | "hybrid" | "demo" | "demo-fallback";

export interface IncidentFeed {
  incidents: Incident[];
  source: IncidentDataSource;
  syncedAt: string;
  notice?: string;
}

const LIVE_SOURCE = "aws";
const DEFAULT_TABLE = "incident-history";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === LIVE_SOURCE;
}

function isSeverity(value: unknown): value is Incident["severity"] {
  return value === "P1" || value === "P2" || value === "P3";
}

function isMode(value: unknown): value is Incident["mode"] {
  return value === "AUTO" || value === "APPROVE" || value === "MANUAL";
}

function isProvider(value: unknown): value is Incident["provider"] {
  return value === "aws" || value === "gcp" || value === "azure" || value === "onprem";
}

// On-prem incidents live in the offline webhook store; the dashboard merges them
// into the timeline over HTTP (same hybrid pattern as pending approvals), so no
// file paths leak into the UI and Vercel simply sees the webhook as offline.
function getOnPremWebhookUrl() {
  return process.env.ONPREM_WEBHOOK_URL ?? "http://127.0.0.1:8078";
}

async function fetchOnPremIncidents(): Promise<Incident[]> {
  try {
    const res = await fetch(`${getOnPremWebhookUrl()}/incidents`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = (await res.json()) as { incidents?: Record<string, unknown>[] };
    return (data.incidents ?? [])
      .map((item) => mapIncidentRecord(item))
      .filter((item): item is Incident => item !== null);
  } catch {
    return [];
  }
}

export function mapIncidentRecord(item: Record<string, unknown>): Incident | null {
  const id = typeof item.incident_id === "string" ? item.incident_id : null;
  const alarmName = typeof item.alarm_name === "string" ? item.alarm_name : null;
  if (!id || !alarmName) return null;

  const executed = Array.isArray(item.executed_actions)
    ? item.executed_actions
    : Array.isArray(item.executed)
      ? item.executed
      : [];

  return {
    id,
    provider: isProvider(item.provider) ? item.provider : "aws",
    alarm_name: alarmName,
    severity: isSeverity(item.severity) ? item.severity : "P3",
    mode: isMode(item.mode) ? item.mode : "MANUAL",
    root_cause: typeof item.root_cause === "string" ? item.root_cause : "No root-cause summary recorded.",
    runbook_id: typeof item.runbook_id === "string" ? item.runbook_id : "legacy-record",
    resolved: item.resolved === true,
    executed_actions: executed.filter((action): action is string => typeof action === "string"),
    created_at:
      typeof item.created_at === "string"
        ? item.created_at
        : typeof item.resolved_at === "string"
          ? item.resolved_at
          : "1970-01-01T00:00:00Z",
    reconciliation: mapReconciliation(item.reconciliation),
    confidence: typeof item.confidence === "number" ? item.confidence : undefined,
  };
}

function mapReconciliation(raw: unknown): Incident["reconciliation"] {
  if (typeof raw !== "object" || raw === null) return undefined;
  const r = raw as Record<string, unknown>;
  return {
    grounded: r.grounded === true,
    issues: Array.isArray(r.issues) ? r.issues.filter((i): i is string => typeof i === "string") : [],
    grounding_ratio: typeof r.grounding_ratio === "number" ? r.grounding_ratio : 1,
    mode_override: typeof r.mode_override === "string" ? r.mode_override : null,
  };
}

const byNewest = (left: Incident, right: Incident) =>
  Date.parse(right.created_at) - Date.parse(left.created_at);

export async function getIncidentById(
  id: string,
): Promise<{ incident: Incident | null; source: IncidentDataSource }> {
  const feed = await getIncidentFeed();
  return { incident: feed.incidents.find((i) => i.id === id) ?? null, source: feed.source };
}

export async function getIncidentFeed(): Promise<IncidentFeed> {
  const syncedAt = new Date().toISOString();
  // On-prem incidents are merged regardless of the AWS data-source mode (hybrid).
  const onprem = await fetchOnPremIncidents();

  if (!isLiveMode()) {
    return {
      incidents: [...onprem, ...mockIncidents].sort(byNewest),
      source: onprem.length ? "hybrid" : "demo",
      syncedAt,
      notice: onprem.length
        ? "On-prem incidents (live) merged with the demo dataset."
        : "Demo dataset. Set DASHBOARD_DATA_SOURCE=aws to enable the read-only AWS feed.",
    };
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new ScanCommand({
        TableName: process.env.DASHBOARD_INCIDENT_TABLE ?? DEFAULT_TABLE,
        Limit: 100,
        ProjectionExpression:
          "alarm_name, incident_id, provider, severity, #mode, root_cause, runbook_id, resolved, executed, executed_actions, created_at, resolved_at",
        ExpressionAttributeNames: { "#mode": "mode" },
      }),
    );

    const awsIncidents = (result.Items ?? [])
      .map((item) => mapIncidentRecord(item))
      .filter((item): item is Incident => item !== null);

    const incidents = [...awsIncidents, ...onprem].sort(byNewest);
    return { incidents, source: onprem.length ? "hybrid" : "aws-live", syncedAt };
  } catch (error) {
    console.error("dashboard.incidents.live_fetch_failed", error);
    return {
      incidents: [...onprem, ...mockIncidents].sort(byNewest),
      source: onprem.length ? "hybrid" : "demo-fallback",
      syncedAt,
      notice: onprem.length
        ? "AWS feed unavailable; showing on-prem incidents + demo dataset."
        : "AWS feed unavailable. Showing the demo dataset.",
    };
  }
}
