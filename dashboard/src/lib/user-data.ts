import { GetCommand, UpdateCommand, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { getDocumentClient } from "@/lib/aws-client";
import type { Role } from "@/lib/auth";
import { userRoleUpdate } from "@/lib/user-role-update";

export interface UserRecord {
  username: string;
  email?: string;
  name?: string;
  role: Role;
  /**
   * Tenants this user may see (Phase 3③). Absent or empty means **none** for
   * non-admins — the read side fails closed the same way the write side does.
   * Admins are not gated on this: they assign the grants, so requiring one
   * would make the system unadministrable after the first mistake.
   */
  tenants?: string[];
  /** Managed separately. Role/read-grant edits must preserve this attribute. */
  registry_write_tenants?: string[];
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
  // Grants are deliberately narrow in the mock so the fleet view demonstrates
  // partitioning rather than showing everyone everything.
  { username: "operator-demo", name: "Ops Lead", email: "ops@example.com", role: "operator", tenants: ["acme", "globex"], updated_at: new Date().toISOString() },
  { username: "viewer-demo", name: "Guest User", email: "guest@example.com", role: "viewer", tenants: ["acme"], updated_at: new Date().toISOString() },
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

/**
 * Create or update a user record.
 *
 * `tenants` is **absent-means-keep**, not absent-means-none. The write is a
 * whole-item Put originally, so the first version silently revoked every
 * grant a user had the moment an admin changed their role — the two controls sit
 * next to each other in the same panel, and nothing on screen said one erased
 * the other. Passing `[]` still revokes; that has to stay expressible.
 */
export async function upsertUserRecord(
  username: string,
  role: Role,
  email?: string,
  name?: string,
  tenants?: string[]
): Promise<UserRecord> {
  const normalizedUsername = username.toLowerCase();
  const updated_at = new Date().toISOString();

  if (isLiveMode()) {
    // Atomic partial update: a concurrent write-grant change is preserved too.
    // Storage failure must not become a successful demo update.
    const result = await getDocumentClient().send(new UpdateCommand({
      TableName: getTableName(),
      ...userRoleUpdate(normalizedUsername, role, updated_at, email, name, tenants),
      ReturnValues: "ALL_NEW",
    }));
    if (!result.Attributes) throw new Error("User update returned no record");
    return result.Attributes as UserRecord;
  }
  const existing = await getUserRecord(normalizedUsername);
  // tenants === undefined means keep on the demo side as well.
  const grants = tenants ?? existing?.tenants;

  const user: UserRecord = {
    username: normalizedUsername,
    role,
    email,
    name,
    updated_at,
  };
  // Absent, not empty: a user with no grants should not carry a `tenants: []`
  // key that reads as a deliberate revocation in the table and in audit diffs.
  if (grants && grants.length > 0) user.tenants = grants;
  if (existing?.registry_write_tenants !== undefined)
    user.registry_write_tenants = [...existing.registry_write_tenants];

  mockUsers = mockUsers.filter((u) => u.username.toLowerCase() !== normalizedUsername);
  mockUsers.push(user);
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
