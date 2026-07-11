import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";
import Credentials from "next-auth/providers/credentials";
import type { Role } from "@/lib/auth";

// Local-dev-only sign-in. Double-gated so it can NEVER be active in production:
// requires an explicit opt-in env AND the absence of the Vercel runtime flag.
// Lets you use the dashboard on localhost when GitHub OAuth callbacks are bound
// to the production domain and can't complete on http://localhost:3000.
const DEV_AUTH = process.env.DASHBOARD_DEV_AUTH === "1" && !process.env.VERCEL;

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role: Role;
      username?: string;
    };
  }
}

const ADMIN_USERS = (process.env.AUTH_ADMIN_USERS ?? "")
  .split(",")
  .map((u) => u.trim().toLowerCase())
  .filter(Boolean);

function resolveRole(username: string): Role {
  if (ADMIN_USERS.includes(username.toLowerCase())) return "admin";
  // Default to operator for authenticated users (can be tightened later)
  return "operator";
}

async function checkOrgMembership(username: string, accessToken: string): Promise<boolean> {
  const org = process.env.AUTH_ALLOWED_ORG;
  if (!org) return true; // No org limit configured

  try {
    const res = await fetch(`https://api.github.com/user/memberships/orgs/${org}`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "User-Agent": "platform-agent-dashboard",
        Accept: "application/vnd.github.v3+json",
      },
    });

    if (res.status === 200) {
      const data = await res.json();
      return data.state === "active";
    }
    return false;
  } catch (err) {
    console.error("github.org_membership.check_failed", err);
    return false;
  }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
      authorization: { params: { scope: "read:org user:email" } }, // scope for org membership check
    }),
    ...(DEV_AUTH
      ? [
          Credentials({
            id: "dev-credentials",
            name: "Local Dev (no GitHub)",
            credentials: {},
            authorize: async () => ({
              id: "local-dev",
              name: "Local Dev",
              email: "local-dev@localhost",
              username: "local-dev",
              role: "admin",
            }),
          }),
        ]
      : []),
  ],
  callbacks: {
    async signIn({ account, profile }) {
      if (account?.provider === "dev-credentials") return DEV_AUTH; // local dev only
      if (account?.provider === "github") {
        const username = (profile as { login?: string })?.login ?? "";
        const token = account.access_token;
        if (!token) return false;

        const isMember = await checkOrgMembership(username, token);
        if (!isMember) {
          console.warn(`Sign-in rejected: user ${username} not in org ${process.env.AUTH_ALLOWED_ORG}`);
          return false;
        }
      }
      return true;
    },
    async jwt({ token, account, profile }) {
      if (DEV_AUTH && account?.provider === "dev-credentials") {
        token.username = "local-dev";
        token.role = "admin";
        return token;
      }
      if (profile) {
        token.username = (profile as { login?: string }).login ?? "";
        
        // Fetch role override from DynamoDB (Auth Phase 2)
        try {
          const { getUserRecord, upsertUserRecord } = await import("@/lib/user-data");
          const userRec = await getUserRecord(token.username as string);
          
          if (userRec) {
            token.role = userRec.role;
          } else {
            const defaultRole = resolveRole(token.username as string);
            token.role = defaultRole;
            // Seed the user record in DynamoDB on first login
            await upsertUserRecord(
              token.username as string,
              defaultRole,
              token.email as string || undefined,
              token.name as string || undefined
            );
          }
        } catch (err) {
          console.error("failed to resolve user role from db, using memory resolver", err);
          token.role = resolveRole(token.username as string);
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? "";
        session.user.username = (token.username as string) ?? "";
        (session.user as { role: Role }).role =
          (token.role as Role) ?? "viewer";
      }
      return session;
    },
  },
});
