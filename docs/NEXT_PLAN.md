# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-14

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 즉시 결정 필요

- [ ] **origin push 결정** — 이번 세션 **로컬 커밋 1개**(main ahead 1, `c6c509c` drain) 미push. gate-green(636 passed) 검증 완료. push 여부 사용자 지정. (앞선 scale·catalog·docs 3커밋은 push 완료.)

## 열린 작업 (로드맵 — 성격별)

### 로컬·자율 가능 — ✅ 전부 소진(2026-07-14)
- [x] ~~인터랙티브 에이전트 MCP 단일 카탈로그 채택~~ · [x] ~~실 executor scale~~ · [x] ~~실 executor drain~~ 모두 완료. On-Prem 실 executor는 되돌리기-가능 4조치(restart/undo/scale/**polite drain**) 완결, 기본 OFF 게이팅. 공격적 force-drain만 의도적으로 사람 몫. **이제 자율로 진행할 순수 로컬 코드 백로그 없음.**

### 클라우드 크레덴셜/과금 필요 (자율 불가)
- [x] ~~**GCP/Azure Provision 어댑터**~~ — **완료(2026-07-14, `6baa6ee`)**: GKE(gcloud)/AKS(az) 어댑터, plan-first/approved-gated, provisioning 4-provider parity. 코드+테스트 완결, 실 create만 크레덴셜 대기.
- [~] **Agent Runtime 매니지드 호스팅** — **코드/preflight 완료(2026-07-14, `36085fc`)**: `adapters/runtime/` 3종(AgentCore/Agent Engine/Foundry), plan-first/approved-gated. AWS·GCP는 실 클라우드 read-only preflight 라이브 통과. **잔여=실 create(billable)**: 사용자 허락 대기.
  - [x] ~~(billable) AWS AgentCore 실 배포~~ — **완료(2026-07-14, `2079c01`)**: `infra/agentcore/` arm64 이미지+exec role, 어댑터 create→READY(~12s)→invoke(실응답)→teardown 라이브 E2E, 즉시 삭제(<$0.50).
  - [x] ~~(billable) GCP Agent Engine 실 배포~~ — **완료(2026-07-14, `40fa8f6`)**: `infra/agentengine/` custom-template 에이전트, 어댑터 create→DEPLOYED→query(Gemini 실응답)→teardown 라이브 E2E, 즉시 삭제(<$0.50).
  - [ ] (billable, 승인 필요) Azure Foundry — Foundry 프로젝트 생성(선행)+model deployment+create_agent.

### 외부/사용자 개입
- [ ] (deferred) **Slack App 실 생성/토큰** — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요. On-Prem 승인 게이트도 Slack 버튼 프런트엔드 연동 가능(현재는 대시보드 버튼으로 대체됨).
- [ ] (deferred) **테크 아티클(LinkedIn/Medium)** 리뷰·배포 — 데모 영상 `docs/post/local-onprem-edited.mp4` ready.
- [ ] 대시보드 **브라우저 UI 인증 배포 클릭 데모** — GitHub OAuth 로그인(사용자 수행). 백엔드/read 경로는 검증됨.

## 참고 — 2026-07-14 세션 완료 (상세는 PROGRESS_LOG)

A2A Phase 2(실 kagent 라이브+messageId 버그) · PROVISION 격리 · ARCHITECTURE 정합화 · **On-Prem Day-2 전체 vertical**(PATH B webhook→승인 게이트→대시보드 승인/타임라인 hybrid→실 executor kubectl **rollout+scale+polite drain**, 되돌리기-가능 4조치 완결) · MCP Gateway 단일 카탈로그 · **인터랙티브 에이전트 단일 카탈로그**(drift-0 불변식) · docs tidy.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
