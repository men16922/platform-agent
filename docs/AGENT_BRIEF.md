# AGENT_BRIEF — platform-agent

최종 갱신: 2026-07-28

> ▶ NEXT SESSION: **Phase 4(managed 어댑터, billable)** 또는 **Phase 5(레지스트리 쓰기)** 중 선택 — **Phase 5가 열려야 Phase 3②를 GitOps-native로 닫는다**(현재는 거부까지가 최종, D32). **즉시 착수 가능한 잔여**: grant 있는 viewer의 브라우저 왕복 실증(Phase 3③에서 유일하게 미실증) · incidents/deployments/activities 무파티션 해소(읽기 모델에 테넌트 라벨 추가 = 데이터모델 변경). **주의**: 푸시/네트워크 신규 필드는 항상 optional+폴백(`tsc`가 못 잡는다) · 새 애드온은 PSS를 `--dry-run=server`로 먼저 확인 · 새 백엔드는 `self_hosted_repo`도 함께 · 에이전트 mutating 범위는 **테넌트 스코프까지**(D30) · **자격증명이 테넌트-바운드인 것은 온프렘뿐**(GCP=프로젝트 전역, Azure=cluster-admin kubeconfig → Phase 4, D31) · 대시보드에서 테넌트 파티션이 걸린 읽기는 **플릿 뷰 하나뿐**이다 · 대시보드 코드는 `dashboard/AGENTS.md`대로 **Next 문서를 먼저 읽는다**(그래서 `middleware`→`proxy` deprecation을 잡았다). **직전 완료**: Phase 3 완결(①자격증명 격리 full ②reconciler 충돌 거부 ③읽기 쪽 테넌트 경계) — gate **1377**, 로컬 3커밋 미푸시.
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
- **검증:** `make check` → **1377 passed, 1 skipped** (2026-07-28); **Phase 3 완결** — ①자격증명 격리 full(가드 1곳을 세 러너가 공유, 라이브에서 **API 서버가** 이웃 테넌트를 `Forbidden`으로 판정) · ②reconciler가 되돌릴 롤백 거부(out-of-band 변경이 **10초 만에** selfHeal에 되돌려짐을 먼저 실증) · ③읽기 쪽 테넌트 경계(익명 curl → `restricted:true`, fail-open 주입 반증); **자연어 → 테넌트 경계 + 애드온 설치 체인**(`tenancy_tools.py` 2도구, 라이브 브라우저 실검증, 컨텍스트 불일치 시 거부); **아키텍처 배선 ①②**(supervisor 프론트도어 `local_deploy_api` · deploy↔runtime `host` 스텝 `pipeline.py`) + **대시보드 관측 3종 노출**(cost_metrics·reconciliation·consensus/steps) + **레퍼런스 Tier 2 완결(#2·#3·#4) 라이브 실증**(agents-as-tools+self-consistency `orchestration.py` · MCP-over-HTTP+kill-switch `mcp_server.py` · cross-account STS+fallback `adapters/aws_session.py`, 3종 옵트인) + **Tier 1 반영**(reconciliation gate·비용 3단계 게이트·서킷브레이커+readiness·비용 서브메트릭) + **Agent Runtime 호스팅 3/3 클라우드 실 배포 라이브**(AgentCore/Agent Engine/Foundry) + **provisioning 4-provider parity**(GCP/Azure GKE·AKS, AKS 라이브); **On-Prem Day-2 완결**: `onprem_webhook_api` Alertmanager→in-process 4-step + P1 즉시/P2 승인게이트/P3 알림 + **대시보드 Incidents hybrid**(승인 카드 + 타임라인) + **실 executor**(`onprem_runner`, 기본 OFF·`ONPREM_EXECUTOR_LIVE`로 실 kubectl 되돌리기-가능 4조치 restart/undo/**scale**/**polite drain**, kind 라이브 실증) 라이브 실증; Dashboard `next build` 성공; Live 7B provision→deploy→validate ~39s·app/cluster 롤백·hybrid 병합·추적 IA 자연어 4스텝 라이브 실증; **A2A 라이브 E2E**: Phase 1(자체 게이트웨이) + **Phase 2 실 kagent 에이전트**(local Qwen 30B) discovery→JSON-RPC 위임→실 `k8s_get_resources` 진단(2026-07-14).
- **현재 초점:** **Phase 3 = 완결**. 다음은 **Phase 4**(managed, billable) 또는 **Phase 5**(레지스트리 쓰기). 발행 3종(Notion 전문 · YouTube Shorts · LinkedIn)은 **전부 완료**(2026-07-28), 레포 원고 동기화만 잔여. **자연어 한 문장이 테넌트를 세운다** — 에이전트 mutating 범위는 테넌트 스코프까지고 공유 스택 9개는 TF 소유(D30). 시연은 `make dev-up` → `make demo-baseline` 두 줄로 재현되고, 격리 반증(netpol 1개 삭제 → network 축만 ✕ → 복구)까지 실증됐다. 대시보드가 멀티테넌시를 관제하고(플릿 표+격리 4축), 검증은 훅으로 강제된다(Stop→make check, PostToolUse→tsc). Phase 2 완결 — 소프트 티어 격리가 네 층(네임스페이스·쿼터·데이터플레인·자격증명)에서 라이브 실측됨. 소프트 티어는 이제 네임스페이스+쿼터(Capsule)에 더해 **데이터플레인 격리**까지 실측됐고(same 통과/cross 차단/kubelet·DNS 무영향), 2축 상태는 각 클러스터의 **push**로 모인다(허브 read 자격증명 0). Phase 1b rollouts-demo 이관 완료(stateful 3건은 스냅샷 선행). 런북은 **선언한 순서·조건·검증대로 실행**된다. 관측성은 metrics+logs+**traces** 삼각(OTel→Tempo). 과금 가드 3중(모두 report-only). 공급망: PSS restricted 기본 ON + Cosign 검증 게이트(어드미션 집행은 미도입, 의도적).

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
