import { PutCommand, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { getDocumentClient } from "@/lib/aws-client";
import { v4 as uuidv4 } from "uuid";

export interface AuditLogEntry {
  audit_id: string;
  who: {
    username: string;
    email?: string;
  };
  what: {
    action: string;
    target: string;
  };
  result: "success" | "failed";
  error_message?: string;
  context: {
    ip?: string;
    userAgent?: string;
  };
  timestamp: string;
  ttl: number;
}

const DEFAULT_TABLE = "platform-agent-audit";
const TTL_90_DAYS = 90 * 24 * 60 * 60;

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

function getTableName() {
  return process.env.DASHBOARD_AUDIT_TABLE ?? DEFAULT_TABLE;
}

// In-memory fallback
let mockAuditLogs: AuditLogEntry[] = [];

export async function writeAuditLog(
  who: { username: string; email?: string },
  what: { action: string; target: string },
  result: "success" | "failed",
  error_message?: string,
  context?: { ip?: string; userAgent?: string }
): Promise<AuditLogEntry> {
  const audit_id = `AUD-${uuidv4().replace(/-/g, "").substring(0, 8).toUpperCase()}`;
  const timestamp = new Date().toISOString();
  const ttl = Math.floor(Date.now() / 1000) + TTL_90_DAYS;

  const entry: AuditLogEntry = {
    audit_id,
    who,
    what,
    result,
    error_message,
    context: context || {},
    timestamp,
    ttl,
  };

  if (!isLiveMode()) {
    mockAuditLogs.unshift(entry);
    return entry;
  }

  try {
    const client = getDocumentClient();
    await client.send(
      new PutCommand({
        TableName: getTableName(),
        Item: entry,
      })
    );
  } catch (error) {
    console.error("audit-data.writeAuditLog.failed", error);
    mockAuditLogs.unshift(entry);
  }

  return entry;
}

export async function listAuditLogs(): Promise<AuditLogEntry[]> {
  if (!isLiveMode()) {
    return mockAuditLogs;
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new ScanCommand({
        TableName: getTableName(),
        Limit: 100,
      })
    );
    const items = (result.Items as AuditLogEntry[]) || [];
    return items.sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
  } catch (error) {
    console.error("audit-data.listAuditLogs.failed", error);
    return mockAuditLogs;
  }
}
