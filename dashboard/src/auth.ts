import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";
import type { Role } from "@/lib/auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role: Role;
    };
  }
}

const ADMIN_USERS = (process.env.AUTH_ADMIN_USERS ?? "")
  .split(",")
  .map((u) => u.trim().toLowerCase())
  .filter(Boolean);

const ALLOWED_ORG = process.env.AUTH_ALLOWED_ORG ?? "";

function resolveRole(username: string): Role {
  if (ADMIN_USERS.includes(username.toLowerCase())) return "admin";
  // Default to operator for authenticated users (can be tightened later)
  return "operator";
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
    }),
  ],
  callbacks: {
    async jwt({ token, profile }) {
      if (profile) {
        token.username = (profile as { login?: string }).login ?? "";
        token.role = resolveRole(token.username as string);
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? "";
        (session.user as { role: Role }).role =
          (token.role as Role) ?? "viewer";
      }
      return session;
    },
  },
});
