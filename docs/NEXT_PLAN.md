# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-11

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`를 참조한다. **≤120줄** 유지.

## 다음 작업 리스트 (2026-07-11 갱신)

- [ ] **origin push** — 현재 main이 origin 대비 ahead 20 (미푸시 커밋 정리)
- [x] ~~A2A specialist endpoint + Agent Card discovery~~ — kagent Card discovery/skill match + JSON-RPC 0.3 transport 지원 완료.
- [x] ~~kagent ↔ 로컬 Qwen 연결~~ — local Qwen ModelConfig + A2A read-only task(tool result 반환) 실증 완료.
- [ ] 클라우드 Provision 어댑터(CDK/Terraform apply) — 현재 AWS `cdk_generator`(계획 생성)만
- [ ] kagent 기본 에이전트 10개 정리(`helm uninstall`) 또는 데모용 유지 결정

### (이전 리스트 — 참고)

- [x] ~~세션 외 미커밋 변경 검토/정리~~ — models.py ServiceSpec 재수출 복구(`eaff5ac`), 나머지 chore 커밋(`5035913`) 완료.
- [x] ~~AI Model Router 채팅 live 데모 + Deployments 추적 실증~~ — MLX Qwen30B→kind 배포 + recorder→DynamoDB→대시보드 aws-live 노출까지 end-to-end 검증 완료(2026-07-11).
- [ ] 대시보드 **브라우저 UI**에서 인증된 배포 클릭 데모 — GitHub OAuth 로그인 필요(사용자 수행). 백엔드/배선/read 경로는 모두 검증됨.
- [ ] (deferred) Slack App 실 생성/토큰 설정 — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요
- [ ] (deferred) 테크 아티클(LinkedIn / Medium) 리뷰 및 소셜 채널 배포

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
