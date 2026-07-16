# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-15

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 다음 우선순위 — **자율 코드 백로그 소진(2026-07-15). 잔여 = 전부 사용자/인프라.**

> 이번 세션(gate 702→**748**): Tier 2(#2·#3·#4) + 실 LLM/HTTP/STS 라이브 실증 + 대시보드 관측 3종 노출·orchestrator 활동기록 + ARCHITECTURE stale 정정 + **아키텍처 배선 ①②**(supervisor 프론트도어·deploy↔runtime `host` 스텝). 전 커밋 origin/main.

- [x] ~~**아키텍처 배선 ①② (자율 로드맵)**~~ — **완료(2026-07-15)**: ② supervisor 프론트도어(`local_deploy_api` `/api/local-deploy` 분류→A2A 위임/in-process 폴백) + ① deploy↔runtime(DeployPipeline opt-in `host` 스텝, approval-gated). +7 test, gate 748.
- [x] ~~**대시보드 관측 3종**~~ — **완료(2026-07-15)**: cost_metrics·reconciliation(AWS 파리티)·consensus/steps(orchestrator `record_route_activity` producer 완결). next build 클린.
- [x] ~~**Tier 1 반영**~~ — reconciliation gate·비용 3단계 게이트·서킷브레이커+readiness·비용 서브메트릭. (상세 `ARCHITECTURE.md` 표)
- [x] ~~#2 **agents-as-tools 오케스트레이션 + self-consistency**~~ — `orchestration.py`(N-샘플 majority vote·저합의 폴백 + `Orchestrator` 체이닝), a2a_server 옵트인. gate 714.
- [x] ~~#3 **MCP-over-HTTP 커넥터 + per-tool/글로벌 kill-switch**~~ — `mcp_server.py` `remote_mcp_tool`(intercept-reinject·전송실패 degrade) + `MCPServer` kill-switch 게이트(`MCP_DISABLED_TOOLS`/`MCP_KILL_SWITCH`), 비파괴. gate 736.
- [x] ~~#4 **cross-account STS AssumeRole + graceful fallback**~~ — `adapters/aws_session.py`(`CircuitBreaker` 재사용) + `runtime/aws.py` 옵트인. gate 723.
- **잔여 레퍼런스 = #7(Helm/Terraform 프로덕션)만 = Tier 3**(온프렘/클라우드 프로덕션화 시).
- [x] ~~#4 **크로스계정 소비자 배선**~~ — **완료(2026-07-15)**: `deployment/aws.py` CodeBuild + `executor/handler.py` SSM(primary+failover `_ssm_client`)이 `assume_role_session(env-role)` 소비, env 미설정=in-account 무변경. +2 test, gate 738.
- [x] ~~라이브 실증(#2 self-consistency · #3 MCP-over-HTTP · #4 STS graceful fallback)~~ — **완료(2026-07-15)**: 실 MLX Qwen(#2 reconciliation 포함)·실 HTTP mock MCP(#3)·실 STS(#4 폴백). 증거 `docs/evidence/tier2-live-*.log`, 스크립트 `scripts/live_*_demo.py`.
- ~~2번째 AWS 계정 cross-account **성공** 경로 라이브~~ — **계획에서 제거(2026-07-15, 사용자 결정)**. #4 코드+폴백/실패 경로는 실 STS로 실증 완료; 실 크로스계정 성공은 하지 않음.

## 열린 작업 (로드맵 — 성격별)

### 로컬·자율 가능 — ✅ 전부 소진(2026-07-14)
- [x] ~~인터랙티브 에이전트 MCP 단일 카탈로그 채택~~ · [x] ~~실 executor scale~~ · [x] ~~실 executor drain~~ 모두 완료. On-Prem 실 executor는 되돌리기-가능 4조치(restart/undo/scale/**polite drain**) 완결, 기본 OFF 게이팅. 공격적 force-drain만 의도적으로 사람 몫. **이제 자율로 진행할 순수 로컬 코드 백로그 없음.**

### 클라우드 크레덴셜/과금 필요 (자율 불가)
- [x] ~~**GCP/Azure Provision 어댑터 + 라이브**~~ — **완료(2026-07-14)**: GKE(gcloud)/AKS(az) 어댑터(`6baa6ee`) + `node_size` 지원(`f3e7952`, 제한구독 대응). **AKS 실 클러스터 라이브**(provision k8s 1.35.6 1노드 Ready→teardown, ~$0.03). GKE는 preflight 라이브·create는 하네스 자동차단(AKS가 동일 패턴 실증). 실 create/delete는 사용자 `!`로 어댑터 호출(하네스가 create 차단, delete 허용).
- [~] **Agent Runtime 매니지드 호스팅** — **코드/preflight 완료(2026-07-14, `36085fc`)**: `adapters/runtime/` 3종(AgentCore/Agent Engine/Foundry), plan-first/approved-gated. AWS·GCP는 실 클라우드 read-only preflight 라이브 통과. **잔여=실 create(billable)**: 사용자 허락 대기.
  - [x] ~~(billable) AWS AgentCore 실 배포~~ — **완료(2026-07-14, `2079c01`)**: `infra/agentcore/` arm64 이미지+exec role, 어댑터 create→READY(~12s)→invoke(실응답)→teardown 라이브 E2E, 즉시 삭제(<$0.50).
  - [x] ~~(billable) GCP Agent Engine 실 배포~~ — **완료(2026-07-14, `40fa8f6`)**: `infra/agentengine/` custom-template 에이전트, 어댑터 create→DEPLOYED→query(Gemini 실응답)→teardown 라이브 E2E, 즉시 삭제(<$0.50).
  - [x] ~~(billable) Azure Foundry 실 배포~~ — **완료(2026-07-14, `4caf7de`+`2231362`)**: 어댑터 v1→v2 결함 수정 후 실 배포. Foundry 계정/프로젝트/gpt-5.4-mini, 어댑터 create_version→Responses API 쿼리(실응답)→delete 라이브 E2E. **3/3 클라우드 완결.** `infra/foundry/README.md`에 gotcha 기록. (Azure 스택은 유휴 ≈$0라 유지 중 — 정리 선택.)

### 외부/사용자 개입
- [ ] (deferred) **Slack App 실 생성/토큰** — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요. On-Prem 승인 게이트도 Slack 버튼 프런트엔드 연동 가능(현재는 대시보드 버튼으로 대체됨).
- [ ] **테크 아티클 배포(LinkedIn/Medium)** — **작성 전부 완료(잔여=배포, 사용자)**: 종합 아키텍처 글 EN `docs/post/platform-agent-architecture.md` + **KO 전문판 `-ko.md`** + **짧은 LinkedIn 컷(EN/KO) `platform-agent-linkedin-cut.md`** + 데모 영상 `local-onprem-edited.mp4`.
- [ ] 대시보드 **브라우저 UI 인증 배포 클릭 데모** — GitHub OAuth 로그인(사용자 수행). 백엔드/read 경로는 검증됨.

## 참고 — 2026-07-14 세션 완료 (상세는 PROGRESS_LOG)

A2A Phase 2(실 kagent 라이브+messageId 버그) · PROVISION 격리 · ARCHITECTURE 정합화 · **On-Prem Day-2 전체 vertical**(PATH B webhook→승인 게이트→대시보드 승인/타임라인 hybrid→실 executor kubectl **rollout+scale+polite drain**, 되돌리기-가능 4조치 완결) · MCP Gateway 단일 카탈로그 · **인터랙티브 에이전트 단일 카탈로그**(drift-0 불변식) · docs tidy.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
