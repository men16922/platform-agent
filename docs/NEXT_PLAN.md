# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-14

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 즉시 결정 필요

- [ ] **origin push 결정** — 이번 세션 **로컬 커밋 2개**(main ahead 2, `bfae1b0` scale·`8f36bb9` catalog) 미push. 전부 gate-green(633 passed) 검증 완료. push 여부 사용자 지정. (세션 시작 시 이전 12커밋은 push 완료.)

## 열린 작업 (로드맵 — 성격별)

### 로컬·자율 가능 (리스크 있음)
- [x] ~~**인터랙티브 에이전트 MCP 단일 카탈로그 채택**~~ — **완료(2026-07-14)**: `local_deployer`가 `AGENT_TOOL_CATALOG` 단일 source-of-truth에서 dispatch+discovery 파생, 드리프트-0 불변식 테스트. 게이트웨이 `TOOL_CATALOG`와는 레이어 구분(어댑터-백드 에이전트 도구 vs raw kubectl/docker) → 별도 카탈로그. **미수행(의도적)**: 배포 경로를 게이트웨이 raw 카탈로그로 완전 병합하는 건 레이어가 달라 부적절.
- [x] ~~**실 executor scale 확장**~~ — **완료(2026-07-14)**: `onprem_runner`에 `ONPREM-ScaleWorkload`→`kubectl scale --replicas=N` 배선(양수 타깃일 때만, kind 2→5 라이브 실증). **잔여: drain** — 위험 → 정책 선행 필요, 로드맵 유지.

### 클라우드 크레덴셜/과금 필요 (자율 불가)
- [ ] **GCP/Azure Provision 어댑터** — On-Prem(Terraform/Ansible)은 완료, 클라우드 Provision은 미구현. WIF/OIDC 크레덴셜·과금 필요.
- [ ] **Agent Runtime 매니지드 호스팅** — Strands→AgentCore / ADK→Agent Engine / MSFT→Foundry. 클라우드 계정 필요.

### 외부/사용자 개입
- [ ] (deferred) **Slack App 실 생성/토큰** — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요. On-Prem 승인 게이트도 Slack 버튼 프런트엔드 연동 가능(현재는 대시보드 버튼으로 대체됨).
- [ ] (deferred) **테크 아티클(LinkedIn/Medium)** 리뷰·배포 — 데모 영상 `docs/post/local-onprem-edited.mp4` ready.
- [ ] 대시보드 **브라우저 UI 인증 배포 클릭 데모** — GitHub OAuth 로그인(사용자 수행). 백엔드/read 경로는 검증됨.

## 참고 — 2026-07-14 세션 완료 (상세는 PROGRESS_LOG)

A2A Phase 2(실 kagent 라이브+messageId 버그) · PROVISION 격리 · ARCHITECTURE 정합화 · **On-Prem Day-2 전체 vertical**(PATH B webhook→승인 게이트→대시보드 승인/타임라인 hybrid→실 executor kubectl **rollout+scale**) · MCP Gateway 단일 카탈로그 · **인터랙티브 에이전트 단일 카탈로그**(drift-0 불변식) · docs tidy.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
