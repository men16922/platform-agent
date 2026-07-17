# AGENT_BRIEF — platform-agent

최종 갱신: 2026-07-17

> ▶ NEXT SESSION: `docs/plans/a2a-delegation-hardening.md` — **⑧ A2A 위임 하드닝 안전 서브셋 완료·구조화/게이트/최소권한 3건 승인 대기.** 첫 액션 = **⑧-3 최소권한 힌트**(role별 `allowedActions` 위임 메타데이터, `action_sink_grader` 정책과 단일 소스 공유 = ⑧ 중 가장 안전). 이번 세션(gate 748→758→767→779→790→795): ⑥ 데이터셋+judge 하드닝(over-trigger 갭 2건 `classify_request` precedence 수정) · ⑤ eval 멀티-grader 스코어카드(`Verdict` PASS_SLOW·action-sink·`Scorecard.delta`·`score(trials=N)`) · ⑦ `model_sweep.py` 오프라인 스윕(cost_per_success headline·resumable·실 spend 0) · ⑧ 아웃바운드 `sanitize_instruction`(control-char strip·cap·trace). **커밋 완료**: ⑥`eef7d54`·⑤`011d4f9`·⑦`ec63915`·tidy`04b8cad` 푸시됨. ⑧은 **미커밋**(supervisor+test+plan doc+docs). **자율 코드 백로그 소진**; 잔여 = ⑧ 구조화/게이트/최소권한(승인)·⑨ SSE/메모리(설계)·⑦ 라이브 실행(실 spend=사용자)·인프라/사용자(아티클 배포·OAuth·Slack·State Store·Helm/Terraform). 하네스: billable create·보안완화는 사용자 `!` 필요.
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
- **검증:** `make check` → **748 passed, 1 skipped** (2026-07-15); **아키텍처 배선 ①②**(supervisor 프론트도어 `local_deploy_api` · deploy↔runtime `host` 스텝 `pipeline.py`) + **대시보드 관측 3종 노출**(cost_metrics·reconciliation·consensus/steps) + **레퍼런스 Tier 2 완결(#2·#3·#4) 라이브 실증**(agents-as-tools+self-consistency `orchestration.py` · MCP-over-HTTP+kill-switch `mcp_server.py` · cross-account STS+fallback `adapters/aws_session.py`, 3종 옵트인) + **Tier 1 반영**(reconciliation gate·비용 3단계 게이트·서킷브레이커+readiness·비용 서브메트릭) + **Agent Runtime 호스팅 3/3 클라우드 실 배포 라이브**(AgentCore/Agent Engine/Foundry) + **provisioning 4-provider parity**(GCP/Azure GKE·AKS, AKS 라이브); **On-Prem Day-2 완결**: `onprem_webhook_api` Alertmanager→in-process 4-step + P1 즉시/P2 승인게이트/P3 알림 + **대시보드 Incidents hybrid**(승인 카드 + 타임라인) + **실 executor**(`onprem_runner`, 기본 OFF·`ONPREM_EXECUTOR_LIVE`로 실 kubectl 되돌리기-가능 4조치 restart/undo/**scale**/**polite drain**, kind 라이브 실증) 라이브 실증; Dashboard `next build` 성공; Live 7B provision→deploy→validate ~39s·app/cluster 롤백·hybrid 병합·추적 IA 자연어 4스텝 라이브 실증; **A2A 라이브 E2E**: Phase 1(자체 게이트웨이) + **Phase 2 실 kagent 에이전트**(local Qwen 30B) discovery→JSON-RPC 위임→실 `k8s_get_resources` 진단(2026-07-14).
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
