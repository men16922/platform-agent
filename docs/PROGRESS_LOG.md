# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-11

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-11 — Dashboard portfolio release (Task 10 완료)

- Status: 3개 항목 모두 구현·배포·검증 완료.
- Changed:
  - Open Graph: `opengraph-image.tsx` (Edge runtime 1200×630) + `twitter-image.tsx` + `layout.tsx` full OG/Twitter metadata.
  - Durable read model: `activity-model.ts` (DynamoDB 단일 테이블 PK/SK+GSI1) + `activity-data.ts` (3 feed 함수) + API routes 3개 + CDK `platform-agent-activity` 테이블.
  - Auth boundary: `docs/DASHBOARD_AUTH_DESIGN.md` (RBAC 3-role, JWT, 승인 플로우, 3-phase 구현 계획) + `dashboard/src/lib/auth.ts` (타입 모듈).
  - Pages: `page.tsx`/`deployments/page.tsx`/`agents/page.tsx`를 activity-data.ts 사용하도록 전환.
  - CDK: `platform-agent-activity` 테이블 + GSI1 + Vercel OIDC read grant 배포 완료.
- Verified:
  - `make check` → **525 passed, 1 skipped** (244.82s).
  - Dashboard `npm run build` → 11 routes 컴파일 성공 (opengraph-image, twitter-image 포함).
  - Vercel production 배포 → `platform-agent-red.vercel.app` OG image 200 OK (107KB), 전체 meta tags 확인.
  - CDK deploy → `platform-agent-activity` ACTIVE (PK/SK + GSI1), Vercel role에 read 추가.
  - AWS: `aws dynamodb describe-table` → 스키마 정확 확인.
- Blockers: 없음.
- Next: Executor에서 activity table write path 연결 → Auth.js Phase 1.

---

## 2026-07-11 — Vercel OIDC live incident production 활성화

- Status: 완료.
- Changed:
  - AWS: Vercel Team issuer OIDC Provider + `platform-agent-vercel-dashboard-read` Role 배포; `incident-history` read-only 권한.
  - Vercel: Production/Preview에 live source, region, table, role ARN env 설정; CLI root link + `.vercelignore` 추가.
  - Production `https://platform-agent-red.vercel.app` 갱신.
- Verified:
  - CloudFormation `UPDATE_COMPLETE`; OIDC trust는 team/project + production/preview subject로 제한.
  - Protected Preview와 Production API 모두 `source=aws-live`; 현재 records 0건.
  - Production Overview `LIVE · AWS` 표시, Playwright console errors 0건.
- Blockers: 없음.
- Next: Open Graph 메타/이미지 구성과 공유 미리보기 검증.

---

## 2026-07-11 — Dashboard AWS incident live read path + Vercel OIDC

- Status: 구현·로컬 live read 검증 완료.
- Changed:
  - Dashboard `/api/dashboard/incidents` + server data source: `aws-live` / `demo` / `demo-fallback` 계약과 UI 라벨 추가.
  - Executor DynamoDB record에 provider/mode/runbook/timestamp/executed_actions read-model 필드 추가.
  - CDK: Vercel team/project/environment-scoped OIDC trust + `incident-history` read-only IAM role.
- Verified:
  - `make check` → **519 passed, 1 skipped** (230.44s); 신규 persistence test 포함.
  - Dashboard lint/build pass; Playwright demo API·페이지 console error 0건.
  - 로컬 AWS mode → `source=aws-live`, 0 records; CDK TypeScript build + OIDC-context synth pass.
- Blockers: 없음.
- Next: OIDC role을 실배포해 Vercel live feed 활성화.
