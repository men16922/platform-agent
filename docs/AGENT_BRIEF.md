# AGENT_BRIEF — platform-agent

최종 갱신: 2026-07-17

> ▶ NEXT SESSION: `docs/NEXT_PLAN.md` — **gate 842.** 승인 큐 8항목 전부 완료(⑦ 라이브 스윕=로컬 MLX $0, 프롬프트 결함 발견→수정→가드, **증거 기반 선택=7B@temp0 20/20**, `docs/evidence/model-sweep-live.log`) + **레퍼런스 #7-a Helm 차트 완료**(`infra/helm/platform-agent/`+`infra/onprem/Dockerfile` 실빌드·컨테이너 스모크, RBAC 최소권한·drain 게이트, pyproject latent 버그 수정). **#7-a kind 라이브 실증 완료**(install→RBAC can-i→Alertmanager→P2 승인→execute→incident→PVC 영속, `docs/evidence/helm-kind-live-install.log`). **④ State Store 완료**(옵트인 `PLATFORM_STATE_DSN`+실 Alertmanager·멀티-레플리카 라이브, `docs/evidence/state-store-alertmanager-live.log`). **#7-b Terraform 모듈 완료**(EKS/Aurora/IRSA, validate까지·apply=사용자) → **레퍼런스 #7 전체 완결·자율 백로그 재소진**. 차트 stateStore DSN 배선 + **k3s substrate 스모크**(기존 k8s-lab VM, local-path PVC·P2 루프, env×substrate 양축 실증)까지 완료(gate 842). **자율 백로그 전면 소진** — 잔여=전부 사용자(아티클 배포·OAuth·Slack·terraform apply). 잔여 사용자 몫: 아티클 배포·OAuth 데모·Slack App. 누적 gate 748→829. 하네스: billable·보안완화는 사용자 `!`.
>
> 1분 압축 문맥. 에이전트 진입점. 이 파일은 **≤60줄**로 유지한다.

## Read Path (순서대로, bulk-read 금지)

1. `docs/AGENT_BRIEF.md` — 이 파일
2. `docs/STATUS.md` — 현재 상태 / 검증 baseline / risks
3. `docs/NEXT_PLAN.md` — 열린 작업만
4. (필요 시) `docs/PROGRESS_LOG.md` 상단 — 최신 증분
5. (필요 시) `docs/engineering/` — harness/loop/context 엔지니어링

권위 순서: `NEXT_PLAN.md` (유일한 source of truth).

## Snapshot

- **무엇:** AWS-native 플랫폼 에이전트. provision → deploy 검증 → detect → analyze → decide → execute → Slack 리포트.
- **동작하는 것:** Operations 4단계 + 3-cloud AI Agent + **On-Prem Ops**(12도구, trace) + Terraform kind/실 Multipass VM Ansible k3s Provision + kagent↔Local Qwen A2A + Agents UI. **On-Prem 오프라인 완결**: Local Qwen **7B**로 NL provision→deploy→validate ~39s, 로컬 JSONL 기록 + 대시보드 **hybrid**(AWS+On-Prem 병합) + 실 **롤백**(app/cluster). **추적 IA**: activity에 `type`(provision/deploy)·`cluster` 연결키, 대시보드 **Provisioning/Deployments/History** 분리 + **중첩 상세**(provisioning⊃deploys), 롤백 **단일-row 승계**·**teardown→deploy cascade**, 자연어 rollback/teardown도 동일 라우팅.
- **하네스:** overnight-harness 플러그인 기반 (5 engine). `make overnight-kiro-once` 로 smoke. `make dev-up`으로 로컬 스택(MLX+proxy+router+dashboard) 한 방 기동.
- **Kiro 특화:** aws-ops / cdk-dev / overnight-harness 3개 에이전트 + safety hook + AWS MCP Server.
- **검증:** `make check` → **842 passed, 1 skipped** (2026-07-17); **아키텍처 배선 ①②**(supervisor 프론트도어 `local_deploy_api` · deploy↔runtime `host` 스텝 `pipeline.py`) + **대시보드 관측 3종 노출**(cost_metrics·reconciliation·consensus/steps) + **레퍼런스 Tier 2 완결(#2·#3·#4) 라이브 실증**(agents-as-tools+self-consistency `orchestration.py` · MCP-over-HTTP+kill-switch `mcp_server.py` · cross-account STS+fallback `adapters/aws_session.py`, 3종 옵트인) + **Tier 1 반영**(reconciliation gate·비용 3단계 게이트·서킷브레이커+readiness·비용 서브메트릭) + **Agent Runtime 호스팅 3/3 클라우드 실 배포 라이브**(AgentCore/Agent Engine/Foundry) + **provisioning 4-provider parity**(GCP/Azure GKE·AKS, AKS 라이브); **On-Prem Day-2 완결**: `onprem_webhook_api` Alertmanager→in-process 4-step + P1 즉시/P2 승인게이트/P3 알림 + **대시보드 Incidents hybrid**(승인 카드 + 타임라인) + **실 executor**(`onprem_runner`, 기본 OFF·`ONPREM_EXECUTOR_LIVE`로 실 kubectl 되돌리기-가능 4조치 restart/undo/**scale**/**polite drain**, kind 라이브 실증) 라이브 실증; Dashboard `next build` 성공; Live 7B provision→deploy→validate ~39s·app/cluster 롤백·hybrid 병합·추적 IA 자연어 4스텝 라이브 실증; **A2A 라이브 E2E**: Phase 1(자체 게이트웨이) + **Phase 2 실 kagent 에이전트**(local Qwen 30B) discovery→JSON-RPC 위임→실 `k8s_get_resources` 진단(2026-07-14).
- **현재 초점:** **자율 코드 백로그 소진** — Tier 1+2 완결·라이브 실증·대시보드 관측 3종·아키텍처 배선 ①② 전부 완료. **잔여는 전부 사용자/인프라**(아티클 배포·OAuth 데모·Slack·State Store/Alertmanager·Helm/Terraform·AgentCore 패리티).

## Guardrails

- 에이전트=Python 3.11 / IaC=CDK TS / 모델은 `src/agents/models.py` 한 곳.
- IAM 최소 권한(`Resource:"*"` 금지), `Delete/Drop/Terminate` 액션은 강제 APPROVE.
- 요청 이상 기능 추가 금지. 테스트 통과 전 완료 선언 금지.
- Gate 명령: `make check`.

## Skills (overnight-harness)

- `/sync` — Read Path 따라 상태 복원(읽기 전용).
- `/checkpoint` — PROGRESS_LOG append + current docs 갱신.
- `/tidy-docs` — 문서 정리/압축.
- `/overnight-report` — 루프 결과 리포트.
- `/overnight-seed` — backlog 시드.
- `/diagnose` — 루프 실패 진단.
