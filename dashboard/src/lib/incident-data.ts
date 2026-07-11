import { ScanCommand } from "@aws-sdk/lib-dynamodb";
import { getDocumentClient } from "@/lib/aws-client";

import { mockIncidents, type Incident } from "@/lib/mock-data";

export type IncidentDataSource = "aws-live" | "demo" | "demo-fallback";

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
  return value === "aws" || value === "gcp" || value === "azure";
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
  };
}

export async function getIncidentFeed(): Promise<IncidentFeed> {
  const syncedAt = new Date().toISOString();
  if (!isLiveMode()) {
    return {
      incidents: mockIncidents,
      source: "demo",
      syncedAt,
      notice: "Demo dataset. Set DASHBOARD_DATA_SOURCE=aws to enable the read-only AWS feed.",
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

    const incidents = (result.Items ?? [])
      .map((item) => mapIncidentRecord(item))
      .filter((item): item is Incident => item !== null)
      .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));

    return { incidents, source: "aws-live", syncedAt };
  } catch (error) {
    console.error("dashboard.incidents.live_fetch_failed", error);
    return {
      incidents: mockIncidents,
      source: "demo-fallback",
      syncedAt,
      notice: "AWS feed unavailable. Showing the demo dataset.",
    };
  }
}
