import { GetCommand, PutCommand, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { getDocumentClient } from "@/lib/aws-client";
import type { Role } from "@/lib/auth";

export interface UserRecord {
  username: string;
  email?: string;
  name?: string;
  role: Role;
  updated_at: string;
}

const DEFAULT_TABLE = "platform-agent-users";

function isLiveMode() {
  return process.env.DASHBOARD_DATA_SOURCE === "aws";
}

function getTableName() {
  return process.env.DASHBOARD_USERS_TABLE ?? DEFAULT_TABLE;
}

// In-memory fallback for local development or demo-fallback mode
let mockUsers: UserRecord[] = [
  { username: "men16922", name: "Lead Engineer", email: "lead@example.com", role: "admin", updated_at: new Date().toISOString() },
  { username: "operator-demo", name: "Ops Lead", email: "ops@example.com", role: "operator", updated_at: new Date().toISOString() },
  { username: "viewer-demo", name: "Guest User", email: "guest@example.com", role: "viewer", updated_at: new Date().toISOString() },
];

export async function getUserRecord(username: string): Promise<UserRecord | null> {
  const normalizedUsername = username.toLowerCase();
  
  if (!isLiveMode()) {
    const found = mockUsers.find((u) => u.username.toLowerCase() === normalizedUsername);
    return found || null;
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new GetCommand({
        TableName: getTableName(),
        Key: { username: normalizedUsername },
      })
    );
    return (result.Item as UserRecord) || null;
  } catch (error) {
    console.error("user-data.getUserRecord.failed", error);
    // Fallback to mock users in case of AWS credential issues
    const found = mockUsers.find((u) => u.username.toLowerCase() === normalizedUsername);
    return found || null;
  }
}

export async function upsertUserRecord(
  username: string,
  role: Role,
  email?: string,
  name?: string
): Promise<UserRecord> {
  const normalizedUsername = username.toLowerCase();
  const updated_at = new Date().toISOString();

  const user: UserRecord = {
    username: normalizedUsername,
    role,
    email,
    name,
    updated_at,
  };

  if (!isLiveMode()) {
    mockUsers = mockUsers.filter((u) => u.username.toLowerCase() !== normalizedUsername);
    mockUsers.push(user);
    return user;
  }

  try {
    const client = getDocumentClient();
    await client.send(
      new PutCommand({
        TableName: getTableName(),
        Item: user,
      })
    );
  } catch (error) {
    console.error("user-data.upsertUserRecord.failed", error);
    // Fallback locally
    mockUsers = mockUsers.filter((u) => u.username.toLowerCase() !== normalizedUsername);
    mockUsers.push(user);
  }

  return user;
}

export async function listUserRecords(): Promise<UserRecord[]> {
  if (!isLiveMode()) {
    return mockUsers;
  }

  try {
    const client = getDocumentClient();
    const result = await client.send(
      new ScanCommand({
        TableName: getTableName(),
        Limit: 100,
      })
    );
    return (result.Items as UserRecord[]) || [];
  } catch (error) {
    console.error("user-data.listUserRecords.failed", error);
    return mockUsers;
  }
}
