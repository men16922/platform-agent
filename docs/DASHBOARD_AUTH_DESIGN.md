# Dashboard Authentication & Authorization Boundary Design

최종 갱신: 2026-07-11

## Overview

이 문서는 platform-agent 대시보드에서 **쓰기/승인 UI를 활성화하기 전** 필요한 인증(AuthN) 및 인가(AuthZ) 경계를 정의한다.

현재 대시보드는 **읽기 전용**이며, Vercel OIDC를 통해 AWS DynamoDB에서 데이터를 안전하게 읽는다.
쓰기/승인 기능을 추가하려면 아래 설계를 먼저 구현해야 한다.

---

## Threat Model

| Threat | Impact | Mitigation |
|--------|--------|-----------|
| Unauthorized approval of P1 incident remediation | Production damage | RBAC + MFA for approve actions |
| Session hijack → write access | Unauthorized deployment triggers | Short-lived tokens + CSRF protection |
| Privilege escalation (viewer → admin) | Data mutation | Server-side role enforcement |
| Replay of approval tokens | Duplicate execution | Idempotent approval IDs + TTL |

---

## Authentication (AuthN)

### Provider: NextAuth.js (Auth.js v5)

선택 이유:
- Next.js App Router 네이티브 지원
- Edge Runtime 호환 (Vercel 배포)
- Multiple OAuth provider 지원 (GitHub, Google, SAML)
- JWT + Session 모두 지원

### Identity Providers (IdP)

| Provider | Use Case | Notes |
|----------|----------|-------|
| GitHub OAuth | Developer/SRE access | Org membership 검증 |
| Google Workspace | Enterprise SSO | Domain 제한 가능 |
| SAML/OIDC (future) | Enterprise IdP 통합 | Okta, Azure AD 등 |

### Session Strategy

```
Browser → NextAuth.js → JWT (httpOnly, secure, SameSite=Strict)
         ↓
       Session: { user_id, email, role, org, exp }
         ↓
       Server Component / API Route → role check → action
```

- **Token type:** JWT (stateless, Edge-compatible)
- **Lifetime:** 1 hour access, 7 day refresh (sliding)
- **Storage:** httpOnly cookie (no localStorage)
- **CSRF:** Double-submit cookie pattern (built into Auth.js)

---

## Authorization (AuthZ)

### Role-Based Access Control (RBAC)

| Role | Read | Approve P3 | Approve P2 | Approve P1 | Admin |
|------|------|-----------|-----------|-----------|-------|
| `viewer` | ✓ | ✗ | ✗ | ✗ | ✗ |
| `operator` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `admin` | ✓ | ✓ | ✓ | ✓ | ✓ |

### Permission Model

```typescript
type Permission =
  | "incidents:read"
  | "incidents:approve:p3"
  | "incidents:approve:p2"
  | "incidents:approve:p1"
  | "deployments:read"
  | "deployments:trigger"
  | "deployments:rollback"
  | "agents:read"
  | "settings:read"
  | "settings:write";

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  viewer: ["incidents:read", "deployments:read", "agents:read", "settings:read"],
  operator: [
    "incidents:read", "incidents:approve:p3", "incidents:approve:p2",
    "deployments:read", "deployments:trigger", "deployments:rollback",
    "agents:read", "settings:read",
  ],
  admin: [
    "incidents:read", "incidents:approve:p3", "incidents:approve:p2", "incidents:approve:p1",
    "deployments:read", "deployments:trigger", "deployments:rollback",
    "agents:read", "settings:read", "settings:write",
  ],
};
```

### Enforcement Points

1. **Middleware (Edge):** Session validity + role presence → 401/403 redirect
2. **API Route (Server):** Permission check before mutation → 403 JSON
3. **UI (Client):** Hide/disable controls based on role (defense in depth, not primary)

---

## API Security Boundary

### Read path (current — no auth required)

```
GET /api/dashboard/incidents   → public (read-only feed)
GET /api/dashboard/deployments → public (read-only feed)
GET /api/dashboard/activities  → public (read-only feed)
GET /api/dashboard/health      → public (read-only feed)
```

### Write path (future — auth required)

```
POST /api/dashboard/incidents/:id/approve   → operator+ | 403
POST /api/dashboard/deployments/trigger     → operator+ | 403
POST /api/dashboard/deployments/:id/rollback → operator+ | 403
PUT  /api/dashboard/settings                → admin    | 403
```

### Approval Flow (Step Functions callback)

```
User clicks "Approve" in UI
  → POST /api/dashboard/incidents/:id/approve
    → Middleware: verify session + role ≥ operator (P2/P3) or admin (P1)
    → Server: validate approval_id exists + not expired (TTL)
    → Server: SFN SendTaskSuccess(taskToken, { approved_by, decision })
    → DynamoDB: update approval record (idempotent)
    → Response: 200 { status: "approved" }
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│ Browser                                             │
│  ┌──────────┐     ┌──────────────────────────────┐  │
│  │ Auth.js  │────→│ JWT Cookie (httpOnly/secure) │  │
│  └──────────┘     └──────────────────────────────┘  │
└────────────────────────────┬────────────────────────┘
                             │
                ┌────────────▼────────────┐
                │ Next.js Middleware       │
                │ • Session validation     │
                │ • Role extraction        │
                │ • Route protection       │
                └────────────┬────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
    │ Read API    │  │ Write API   │  │ Approval API│
    │ (public)    │  │ (authed)    │  │ (authed)    │
    │             │  │ role≥oper   │  │ role≥oper   │
    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
           │                 │                 │
    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
    │ DynamoDB    │  │ DynamoDB    │  │ Step Fns    │
    │ (OIDC read) │  │ (write role)│  │ (callback)  │
    └─────────────┘  └─────────────┘  └─────────────┘
```

---

## Implementation Plan

### Phase 1: Auth infrastructure (prerequisite for any write UI)

1. Install `next-auth@5` (Auth.js v5)
2. Configure GitHub OAuth provider
3. Add session middleware to protected routes
4. Create `src/lib/auth.ts` with role definitions and permission checks
5. Create `src/middleware.ts` for route protection

### Phase 2: Role assignment

1. Define role mapping rules (GitHub org membership → role)
2. Store role overrides in DynamoDB (`platform-agent-users` table)
3. Implement admin UI for role management

### Phase 3: Write endpoints

1. Implement approval endpoint with SFN callback
2. Implement deployment trigger endpoint
3. Add audit logging for all mutations

---

## Environment Variables (Auth)

```env
# Auth.js
AUTH_SECRET=<random-32-byte-secret>
AUTH_GITHUB_ID=<oauth-app-client-id>
AUTH_GITHUB_SECRET=<oauth-app-client-secret>
AUTH_TRUST_HOST=true

# Role mapping
AUTH_ALLOWED_ORG=<github-org-slug>
AUTH_ADMIN_USERS=<comma-separated-github-usernames>
```

---

## Constraints & Decisions

| Decision | Rationale |
|----------|-----------|
| JWT over database sessions | Edge Runtime 호환 + 외부 DB 의존성 없음 |
| Read path remains public | Dashboard는 portfolio 용도; incident 데이터는 이미 CloudWatch에 공개 |
| P1 approval requires admin | AUTO 모드 override는 최고 권한만 허용 |
| GitHub OAuth first | 개발자 중심 프로젝트; 추후 SAML 추가 용이 |
| No write UI until Phase 1 complete | 인증 없는 mutation은 금지 (AGENT_BRIEF guardrail) |

---

## Audit & Compliance

모든 write action은 다음을 기록한다:
- `who`: user_id + email
- `what`: action + target resource
- `when`: ISO timestamp
- `result`: success/failure + error
- `context`: request IP, user-agent (PII 최소화)

DynamoDB `platform-agent-audit` 테이블에 90일 보관 (TTL).
