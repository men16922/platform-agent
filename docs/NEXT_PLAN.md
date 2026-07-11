# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-11

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`를 참조한다. **≤120줄** 유지.

## 다음 작업 리스트

- [x] ~~세션 외 미커밋 변경 검토/정리~~ — models.py ServiceSpec 재수출 복구(`eaff5ac`), 나머지 chore 커밋(`5035913`) 완료.
- [x] ~~AI Model Router 채팅 live 데모 + Deployments 추적 실증~~ — MLX Qwen30B→kind 배포 + recorder→DynamoDB→대시보드 aws-live 노출까지 end-to-end 검증 완료(2026-07-11).
- [ ] 대시보드 **브라우저 UI**에서 인증된 배포 클릭 데모 — GitHub OAuth 로그인 필요(사용자 수행). 백엔드/배선/read 경로는 모두 검증됨.
- [ ] (deferred) Slack App 실 생성/토큰 설정 — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요
- [ ] (deferred) 테크 아티클(LinkedIn / Medium) 리뷰 및 소셜 채널 배포

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
