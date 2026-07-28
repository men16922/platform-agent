import { ScanCommand } from "@aws-sdk/lib-dynamodb";
import { getDocumentClient } from "@/lib/aws-client";

import { type Incident } from "@/lib/mock-data";

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
    ...(typeof item.tenant === "string" && item.tenant ? { tenant: item.tenant } : {}),
    ...(typeof item.env === "string" && item.env ? { env: item.env } : {}),
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
    trace_id: typeof item.trace_id === "string" && item.trace_id ? item.trace_id : undefined,
    triggered_at:
      typeof item.triggered_at === "string" && item.triggered_at ? item.triggered_at : undefined,
    // Undefined for open incidents — the writers omit it rather than defaulting
    // it to `created_at`, so "no resolution time" stays distinguishable from
    // "resolved in zero minutes".
    resolved_at:
      typeof item.resolved_at === "string" && item.resolved_at ? item.resolved_at : undefined,
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
    // No AWS wired up — the only real feed is the on-prem webhook. Report the
    // source honestly as ON-PREM (don't claim a hybrid AWS feed that isn't there).
    return {
      incidents: [...onprem].sort(byNewest),
      source: "local",
      syncedAt,
      notice: onprem.length
        ? undefined
        : "No on-prem incidents yet — fire an Alertmanager alert to populate the timeline.",
    };
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new ScanCommand({
        TableName: process.env.DASHBOARD_INCIDENT_TABLE ?? DEFAULT_TABLE,
        Limit: 100,
        // A Scan returns ONLY the attributes named here. Every field added to the
        // writer since this string was written has therefore been fetched as
        // undefined no matter how carefully the reader handled it — and
        // `mapIncidentRecord` below, plus the incident row and detail views, read
        // all four of the ones that were missing. `confidence` and
        // `reconciliation` have been rendered as "n/a" and "not shown" for every
        // AWS-live incident since those views shipped; `triggered_at` was fixed
        // at the writer this morning and stopped here, one layer short of the
        // badge built to display it.
        //
        // Adding a field to the writer is not done until this list names it.
        //
        // The two single-word additions are aliased. DynamoDB's reserved-word
        // list is single alphabetic tokens only, so `triggered_at`/`trace_id`
        // cannot collide, but a bare `confidence`/`reconciliation` that does
        // would throw ValidationException — and the catch below turns any throw
        // here into a silent downgrade to the on-prem-only feed, which is a
        // failure mode this dashboard has already paid for once.
        ProjectionExpression:
          "alarm_name, incident_id, provider, severity, #mode, root_cause, runbook_id, resolved, executed, executed_actions, created_at, resolved_at, triggered_at, #confidence, #reconciliation, trace_id, tenant, #env",
        ExpressionAttributeNames: {
          "#mode": "mode",
          "#env": "env",
          "#confidence": "confidence",
          "#reconciliation": "reconciliation",
        },
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
      incidents: [...onprem].sort(byNewest),
      source: "local",
      syncedAt,
      notice: "AWS feed unavailable — showing on-prem incidents only.",
    };
  }
}
