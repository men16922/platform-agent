# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-11 (Task 10 portfolio release 완료)

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`를 참조한다. **≤120줄** 유지.

## Task 11: Dashboard live data pipeline + Auth

- [ ] [auto] Executor에서 `platform-agent-activity` 테이블에 deployment/activity 기록 write path 구현
- [ ] [auto] Auth.js Phase 1: GitHub OAuth + 세션 미들웨어 + 보호 라우트 적용
- [ ] [manual] Vercel env에 `DASHBOARD_ACTIVITY_TABLE=platform-agent-activity` 추가 + 재배포

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
