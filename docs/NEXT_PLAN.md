# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-11 (Auth Phase 2 & 3 완료)

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`를 참조한다. **≤120줄** 유지.

## 후속 수동 작업

- [ ] [manual] CDK Stack 배포 (`cdk deploy`) 하여 `platform-agent-users` 및 `platform-agent-audit` 테이블 생성 및 OIDC 권한 배포
- [ ] [manual] Vercel env에 다음 테이블 이름 환경 변수 설정 추가:
  - `DASHBOARD_USERS_TABLE=platform-agent-users`
  - `DASHBOARD_AUDIT_TABLE=platform-agent-audit`
  - `DASHBOARD_APPROVAL_TABLE=incident-approval-requests`
- [ ] [manual] Vercel에 대시보드 프로젝트 프로덕션 빌드 재배포

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
