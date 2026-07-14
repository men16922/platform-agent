# PROGRESS_LOG Archive — July 2026

이 파일은 `docs/PROGRESS_LOG.md`에서 120줄이 초과하여 아카이브된 2026년 7월 이전 이력입니다.

---

## 2026-07-14 — Agent Runtime 호스팅 어댑터 3종(AgentCore/Agent Engine/Foundry) + 라이브 preflight(AWS·GCP)

- Status: **④ Host role** 신설 — 빌드된 에이전트(Strands deployer 등)를 매니지드 런타임에 올리는 어댑터 레이어. provisioning의 plan-first/approved-gated 계약을 3-provider로 미러링. **비용 안 나가는 범위 전부 수행**: 코드+목 테스트 완결 + AWS·GCP는 **실 클라우드 read-only preflight 라이브 통과**, Azure는 설계대로 blocker 보고(과금 없음).
- Changed: 신규 `src/agents/adapters/runtime/` 패키지 — `base.py`(`RuntimeSpec`/`RuntimeResult`/protocol, provider별 create knobs용 `extra` dict), `aws.py`(AgentCore via boto3 `bedrock-agentcore-control`, **신규 의존성 0**), `gcp.py`(Vertex Agent Engine via `vertexai.agent_engines`), `azure.py`(AI Foundry via `azure-ai-projects`), `registry.py`(`["aws","gcp","azure"]`). 공통: 미승인 host=읽기전용 preflight(list, 생성 0), `approved=True`=실 create(AgentCore=ECR img+role, Agent Engine=agent_object, Foundry=model), teardown=approved 강제+이름으로 id 해석. 클라우드 SDK는 지연 import + gcp/azure extras에 기록(`google-cloud-aiplatform`, `azure-ai-projects`). `test_runtime_adapters.py` 20개.
- Verified: `pytest tests/test_runtime_adapters.py` 20 passed. `make check` → **669 passed, 1 skipped**. 커밋 `36085fc`. **라이브 read-only preflight**: 실 AWS(acct 908601828278, us-east-1)→0 runtimes / 실 GCP(project-ec7809f7, us-central1 Vertex)→0 engines. Azure=Foundry 프로젝트 부재로 preflight blocked(엔드포인트 없음, graceful). **billable create는 미실행**(승인 대기).
- Blockers: 실 create는 전부 과금/하드-투-리버스 → 사용자 허락 필요. Azure 라이브 preflight도 Foundry 프로젝트 생성(과금)이 선행이라 대기.
- Next: (사용자 결정) 3종 중 실 배포할 것 선택 — 비용 견적 제시함. 잔여 외부: Slack App·아티클.

## 2026-07-14 — GCP/Azure managed-cloud Provision 어댑터(GKE/AKS): provisioning 4-provider parity

- Status: provisioning 어댑터가 deployment/execution 레이어처럼 **4-provider parity**(onprem/aws/**gcp**/**azure**) 달성. 그간 On-Prem(Terraform/Ansible)+AWS(CDK)만 있고 클라우드 Provision이 갭이었음. AWS 어댑터의 **plan-first / approved-gated 계약을 그대로 미러링** — 하드-투-리버스(클러스터 생성/삭제)는 승인 게이팅.
- Changed: 신규 `adapters/provisioning/gcp.py`(GKE via `gcloud container clusters create/delete`, 미승인=읽기전용 `clusters list` preflight) + `azure.py`(AKS via `az aks create/delete`, 미승인=`aks list` preflight). `registry.py`→`["onprem","aws","gcp","azure"]` 라우팅. `base.py` `ProvisionSpec`에 `node_count:int=2`. config는 deployment 어댑터와 **동일 env**(`GCP_PROJECT`/`GCP_REGION`, `AZURE_RESOURCE_GROUP`/`AZURE_REGION`). **안전 기본값**: `provision_tools`가 `approved`를 미노출 → LLM 도구 호출은 cloud provider에서 **preflight-only**(과금 인프라 생성 불가), 전용 테스트로 고정. `test_provisioning_adapters.py` 10→23(registry 해결·preflight-only·approved-create argv·teardown 승인 강제·project/RG 누락·CLI-absent·도구 preflight 고정).
- Verified: `pytest tests/test_provisioning_adapters.py` 23 passed. `make check` → **649 passed, 1 skipped**. 커밋 `6baa6ee`. **라이브 미실행**: 실 GKE/AKS create는 WIF/OIDC 크레덴셜·과금 필요 → argv/게이팅만 결정론 검증, 어댑터는 credential-ready(`ProvisionSpec(...,approved=True)`로 즉시 라이브 가능).
- Blockers: 라이브 클라우드 create는 크레덴셜·과금 대기(처음부터 크레덴셜-대기 항목).
- Next: (진행 중) **Agent Runtime 매니지드 호스팅 — AgentCore**(Strands→Bedrock AgentCore, AWS라 실 배포 테스트 가능성 검토). 잔여 외부: Slack App·아티클.

## 2026-07-14 — On-Prem 실 executor 완결: polite node drain(--force 없음, PDB 존중)

- Status: On-Prem Day-2 실 executor의 **되돌리기-가능 조치 세트 완결** — restart/undo/scale에 이어 **마지막(가장 위험)** `ONPREM-DrainNode`→`kubectl drain <node>` 추가. 노드 단위라 blast-radius가 커서 **보수적 "polite drain" 정책**으로 게이팅.
- Changed: `onprem_runner.py` — DrainNode 전용 분기(`_kubectl_args`): `["drain", <node>, "--ignore-daemonsets", "--timeout=90s"]`, **`--force`·`--delete-emptydir-data` 의도적 미사용**(→ kubectl이 PodDisruptionBudget 존중, 미관리/로컬데이터 파드에선 거부=실패→executor skip; 아웃티지·데이터손실 방지), NodeName 없으면 log-only. `execution/onprem.py` — DrainNode 분기 분리, 워크로드 대신 `NodeName`(라벨 `node`/`instance`) 스레딩. 여전히 `ONPREM_EXECUTOR_LIVE` 기본 OFF. `test_onprem_runner.py` 10→13(drain args·`--force`/`--delete-emptydir-data` 부재 검증·node 누락 log-only), unwired 테스트를 CleanupDiskSpace로 교체. `test_portability_adapters.py` +1(NodeName 스레딩).
- Verified: `pytest tests/test_onprem_runner.py tests/test_portability_adapters.py` 25 passed. **실 kind 라이브 실증(3노드: control-plane+worker×2)**: nginx web 4 replicas(worker 2/worker2 2 분산) → runner로 worker drain → **노드 cordon(SchedulingDisabled)+파드 evict→worker2 재배치, deployment 4/4 Running 유지(아웃티지 0)** → 클러스터 정리. `make check` → **636 passed, 1 skipped**.
- Blockers: 없음. 공격적 force-drain은 의도적으로 사람 몫(로드맵도 아님). **On-Prem 로컬-자율 백로그 전부 소진**.
- Next: 잔여는 전부 외부/클라우드 — (deferred) Slack App·아티클, GCP/Azure Provision·Agent Runtime(크레덴셜 필요).

## 2026-07-14 — 인터랙티브 에이전트 단일 도구 카탈로그: 프롬프트↔등록 드리프트 제거

- Status: 게이트웨이의 단일-카탈로그 규율을 **인터랙티브 `local_deployer` 에이전트**에도 적용. 기존엔 시스템 프롬프트의 `## Tools` 인벤토리를 **손으로** 적고 `ALL_OPS_TOOLS`(등록)와 수동 동기화 → 게이트웨이가 고쳤던 드리프트 위험 그대로였음. **`AGENT_TOOL_CATALOG` 단일 source-of-truth** 도입: dispatch(`ALL_OPS_TOOLS`, Pydantic AI 등록)와 discovery(프롬프트 인벤토리, LLM이 안다고 듣는 도구)를 **둘 다 카탈로그에서 파생** → 도구 추가=1곳, 드리프트 불가.
- Changed: `local_deployer.py` — 프롬프트를 `_SYSTEM_PROMPT_TEMPLATE`(`__TOOLS__` 센티넬)로 분리, `AgentTool`(frozen: func+category+hint)+`AGENT_TOOL_CATALOG`(13개: investigate5/provision2/deploy5/recover1) 도입, `_render_tool_inventory()`가 `## Tools` 마크다운 생성, `ALL_OPS_TOOLS`=`[t.func for t in CATALOG]` 파생. **레이어 구분 명시**: 게이트웨이 `TOOL_CATALOG`(raw kubectl/docker MCP 핸들러)와 달리 이건 상위 어댑터-백드 LLM-튜닝 에이전트 도구 → 별도 카탈로그 유지(병합 아님). `test_local_deployer.py` +2(discovery==dispatch==catalog==source-lists union 불변식·카테고리 유효성).
- Verified: `pytest tests/test_local_deployer.py` 10 passed. **행위 보존**: 동일 13함수 등록(TestModel drive 테스트 통과), 프롬프트 인벤토리는 등가 내용으로 재생성(도구별 힌트+동일 카테고리). `make check` → **633 passed, 1 skipped**. (라이브 MLX 7B 경로 재실행 안 함 — 프롬프트 변경은 가산적 명료화, 결정론 테스트가 배선 커버.)
- Blockers: 없음. 잔여(로드맵): 배포 경로 전체 리팩터(어댑터 튜닝 도구를 게이트웨이 raw 카탈로그로 수렴)는 레이어가 달라 의도적으로 미수행.
- Next: (외부/deferred) Slack App·아티클. (로드맵) GCP/Azure Provision·Agent Runtime(크레덴셜 필요).

## 2026-07-14 — On-Prem 실 executor 확장: kubectl scale(양수 타깃 게이팅)

- Status: On-Prem Day-2 실 executor의 **세 번째 되돌리기-쉬운 조치** 추가 — rollout restart/undo에 이어 `ONPREM-ScaleWorkload`→`kubectl scale --replicas=N`. scale은 desired-state라 알림이 목표 replica를 실어와야 실행되게 게이팅.
- Changed: `execution/onprem.py` — `ONPREM-ScaleWorkload` 분기 분리, 알림 라벨(`desired_replicas`/`replicas`)에서 `DesiredReplicas` 파라미터 스레딩(없으면 `_compact`가 드롭). `onprem_runner.py` — `_kubectl_args()` 헬퍼로 argv 빌드 분리, scale은 `_positive_int()`로 **양수(≥1)일 때만** 실행(누락/0/비정수→log-only, scale-to-0=셧다운은 사람 필요). 여전히 `ONPREM_EXECUTOR_LIVE` 기본 OFF. `test_onprem_runner.py` 7→10(scale 실행·replicas 누락·scale-to-0 가드), `test_portability_adapters.py` +2(DesiredReplicas 스레딩·라벨 부재 시 생략), unwired 테스트를 DrainNode로 교체.
- Verified: `pytest tests/test_onprem_runner.py tests/test_portability_adapters.py` 22 passed. **실 kind 라이브 실증**: nginx `payments/payments-api`(2 replicas) 배포 → runner로 scale→**2→5 실제 확장**(5/5 ready) → scale-to-0은 runner가 `live_missing_target`로 log-only(replicas 5 불변) → 클러스터 정리. `make check` → **631 passed, 1 skipped**.
- Blockers: 없음. drain은 위험(정책 선행) → 로드맵 유지.
- Next: (외부/deferred) Slack App·아티클. (로드맵) 인터랙티브 에이전트 카탈로그 채택(아래 세션에서 완료).

## 2026-07-14 — MCP Gateway 단일 도구 카탈로그: 삼중 중복 → 단일 source-of-truth

- Status: ARCHITECTURE "MCP Gateway 단일 카탈로그" 타깃의 **기반 확립**. 게이트웨이가 도구를 **3곳**(구현 static 메서드 + `MCP_TOOLS` 스키마 리스트 + `MCPServer._tool_map` dispatch)에 손으로 동기화하던 걸 **단일 `TOOL_CATALOG`**(name+desc+params+handler)로 수렴 — discovery(`MCP_TOOLS`)와 dispatch를 카탈로그에서 파생. 도구 하나 추가 = 카탈로그 1곳(+구현). 외부 A2A/MCP 에이전트와 bridge가 이 단일 카탈로그를 공유.
- Changed: `gateway/mcp_server.py` — `ToolSpec`(frozen, handler 포함) + `TOOL_CATALOG` 도입, `MCP_TOOLS`=`[s.definition() for s in TOOL_CATALOG]` 파생, `MCPServer._tool_map`=카탈로그 파생(하드코딩 맵 제거). **공개 API 전부 보존**(MCPServer/KubectlTool/DockerTool/ToolResult/ToolDefinition/MCP_TOOLS/_run_cmd — bridge·테스트 무변경). `test_gateway.py` +2 불변식 테스트(discovery↔dispatch↔catalog 일치·드리프트 0, 전 도구 dispatch 검증).
- Verified: `pytest tests/test_gateway.py` 32 passed(기존 30 회귀 없음 + 신규 2). `make check` → **626 passed, 1 skipped**.
- Blockers: 없음.
- Next: (로드맵) **인터랙티브 에이전트(local_deployer)의 카탈로그 채택** — 지금은 게이트웨이(A2A/MCP)만 단일 카탈로그; 인터랙티브 in-process 도구와의 완전 수렴은 더 큰 후속 단계(배포 경로 리팩터, 리스크 큼). (외부) Slack App·아티클.

## 2026-07-14 — On-Prem 실 executor: 로그-only 스텁 → 실 kubectl 원격조치(기본 OFF 게이팅)

- Status: On-Prem Day-2의 **마지막 조각** — executor가 조치를 로그만 찍던 걸 **실제 kubectl 실행**으로. 안전을 위해 **기본 OFF 플래그**(`ONPREM_EXECUTOR_LIVE`) 뒤에 게이팅(기본 동작=로그-only 무변경), **되돌리기 쉬운 액션(rollout restart/undo)만** 실 실행 배선(scale·drain 등 위험/모호한 건 로그-only 유지).
- Changed: 신규 `src/agents/operations/executor/onprem_runner.py`(gcp_runner 패턴; `_is_live()`=플래그ON&TESTING≠True, `_LIVE_KUBECTL`={RolloutRestart→`rollout restart`, ArgoRollback→`rollout undo`}, 실패 시 raise→executor가 skip 처리). `executor/handler.py` `_run_external_action`의 onprem 분기를 stub→`run_onprem_action`. `tests/test_onprem_runner.py` 7개(기본 로그-only·live restart/undo kubectl args·unwired/누락 로그-only·TESTING 강제 OFF·실패 raise).
- Verified: `pytest` 21 passed(runner 7 + webhook 14). **실 kind 라이브 실증**: 단일노드 kind에 `payments/payments-api`(nginx, 2 replicas) 배포 → `ONPREM_EXECUTOR_LIVE=true`로 runner 실행 → `kubectl_ok`("deployment restarted") → **파드 실제 교체**(구 RS `6dc8c9cbd9`→0, 신 RS `86f76b7f49`→2). 테스트 클러스터 정리. `make check` → (아래).
- Blockers: 없음. 기본 OFF라 프로덕션 안전; scale/drain 등은 desired-state 파라미터 필요로 로드맵.
- Next: (외부/deferred) Slack App·아티클. (로드맵) MCP Gateway 단일 카탈로그·클라우드 Provision.

## 2026-07-14 — `make dev-up` 원커맨드 스택에 On-Prem Day-2 webhook 통합

- Status: On-Prem Day-2 vertical을 **운영 완결** — `make dev-up` 한 방에 MLX+proxy+router+**webhook(:8078)**+dashboard가 함께 뜨고, 대시보드(기본 `ONPREM_WEBHOOK_URL=:8078`)가 자동으로 On-Prem 승인·인시던트를 hybrid 표시.
- Changed: `Makefile` — `WEBHOOK_PORT`/`APPROVALS_FILE`/`INCIDENT_FILE` 변수 추가, `dev-up`에 webhook 기동 스텝(activity/approvals/incidents env), `dev-down`에 종료, `dev-status`에 `:8078/health` 체크. `onprem-webhook` 타깃도 변수화(INCIDENT_FILE 추가).
- Verified: `make dev-status`에 webhook 라인 표시(down), `make -n dev-up` dry-run에 webhook 스텝·env·포트 정상 파싱. (코드 무변경, gate 영향 없음 — 직전 617 passed 유효.)
- Blockers: 없음.
- Next: (외부/deferred) Slack App·아티클. 로드맵(실 executor·MCP Gateway 단일 카탈로그·클라우드 Provision).

## 2026-07-14 — 대시보드 Incidents 타임라인 On-Prem surfacing: 오프라인 인시던트 스토어 + hybrid 병합

- Status: On-Prem Day-2 인시던트를 대시보드 **Incidents 타임라인**에 표시. 기존엔 승인 카드만 On-Prem을 노출했고 타임라인은 AWS DynamoDB만 읽어(오프라인 On-Prem 인시던트 부재), executor의 DynamoDB write는 오프라인 no-op이었음. webhook 계층에 로컬 인시던트 스토어를 두어 종단 완성.
- Changed: 신규 `src/agents/ai/onprem_incidents.py`(오프라인 JSONL 인시던트 스토어, 대시보드 Incident 필드명 그대로: incident_id/alarm_name/provider/severity/mode/root_cause/runbook_id/resolved/executed_actions/created_at; `PLATFORM_INCIDENT_FILE`). `onprem_webhook_api.py`: 종단 상태에서 인시던트 기록(P1 AUTO=resolved, P3 MANUAL=unresolved, P2는 approve/reject 시점 기록—park 중 중복 방지) + `GET /incidents`. `test_onprem_webhook.py` 11→14. 대시보드: `mock-data.ts` `Incident.provider`에 `onprem` 추가, `incident-data.ts` `isProvider`+`fetchOnPremIncidents`(webhook `/incidents` HTTP)+`getIncidentFeed` hybrid 병합(source=`hybrid`), `incident-row.tsx` 라벨 `ON-PREM`(폴백 버그 수정; provider-logo는 이미 onprem 지원).
- Verified: `pytest tests/test_onprem_webhook.py` 14 passed. **webhook 라이브**: P2 alert→park(timeline 0)→approve→`/incidents` 1건(onprem/P2/resolved/INC-1121DAB7). **대시보드 라이브 헤드리스**: `next start`(ONPREM_WEBHOOK_URL=:8078)→`GET /incidents`에 On-Prem 인시던트 렌더(INC-1121DAB7·**ON-PREM 배지**·generic-recovery·source "On-prem incidents (live)"). `tsc` 0·`next build` 성공. `make check` → **617 passed, 1 skipped**.
- Blockers: 없음.
- Next: (외부/deferred) Slack App·아티클. 로드맵(실 executor·MCP Gateway 단일 카탈로그·클라우드 Provision).

## 2026-07-14 — 대시보드 On-Prem 승인 연동: Incidents 페이지 hybrid(AWS+On-Prem) + approve/reject 라우팅

- Status: 직전 On-Prem 승인 게이트를 **대시보드 화면에 연동**. Incidents 페이지의 "Pending Remediation Approvals"가 이제 AWS(DynamoDB/SFN) + On-Prem(webhook `/pending`)을 **hybrid 병합** 표시하고, Approve/Reject 클릭이 source에 따라 SFN 또는 webhook으로 라우팅됨. deployments 대시보드의 AWS+On-Prem hybrid 패턴을 승인에도 적용.
- Changed: `dashboard/src/lib/approval-data.ts` — `ApprovalRequest.source`(aws|onprem) 추가, `ONPREM_WEBHOOK_URL`(기본 `:8078`) HTTP 읽기(`fetchOnPremPending`/`mapOnPremApproval`), `listPendingApprovals`=AWS+onprem 병합, `getApprovalRequest`=onprem 우선 조회, `approve/rejectApprovalRequest`=onprem이면 webhook `/approve`·`/reject`로 분기(SFN 대신). `dashboard/src/components/pending-approvals.tsx` — source 배지(On-Prem 파랑/AWS 주황) 추가. 내 신규 `any` 제거(타입 지정) + 기존 `let mockApprovals`→`const`.
- Verified: `tsc --noEmit` 0, `next build` **Compiled successfully**(11 routes). **라이브 헤드리스 실증**: webhook(:8078)에 P2 pending(APR-34398628) 생성 → `next start`(ONPREM_WEBHOOK_URL=:8078) → `GET /incidents` HTML에 On-Prem 승인 카드 렌더 확인(approval_id·**On-Prem 배지**·payments-api·generic-recovery·ONPREM-CreateChangeRequest). read 라우트는 public이라 무인증 렌더; approve 액션은 미들웨어 인증·RBAC·감사로그 공통. webhook approve/reject 자체는 앞선 세션에서 라이브 실증.
- Blockers: 없음. (브라우저 확장 미연결로 스크린샷은 생략, HTML 렌더 검증으로 대체.)
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드(실 executor·MCP Gateway 단일 카탈로그·클라우드 Provision 어댑터).

## 2026-07-14 — On-Prem Approval Flow(P2 승인 게이트) 구현: pending 스토어 + approve/reject

- Status: ARCHITECTURE의 On-Prem Approval Flow(🔲 계획) 코어 게이트를 **구현+라이브 E2E**로 완성. 직전 webhook이 P2에 `mode=APPROVE`를 반환하지만 승인/실행 수단이 없던 루프를 닫음. Guardian severity→mode 게이팅을 webhook에 배선: **P1=즉시 실행 · P2=parking · P3=알림만**.
- Changed: `onprem_incident_pipeline.py`에 실행 분리(`run_incident_pipeline(..., execute=False)` + `execute_incident(decision)` 재생 헬퍼). 신규 `src/agents/ai/onprem_approvals.py`(오프라인 JSONL pending 스토어, deploy_recorder식 single-row 승계: create/list/get/resolve, `PLATFORM_APPROVALS_FILE`). `onprem_webhook_api.py`에 `GET /pending`·`POST /approve/{id}`(decision 재생 실행)·`POST /reject/{id}` 추가 + `PipelineResult.status`(executed/pending_approval/notified/approved/rejected). `test_onprem_webhook.py` 6→11(P1 AUTO·P2 park→approve/reject·P3 notified·404/409). Makefile approval env. ARCHITECTURE On-Prem Approval Flow 🔲→부분 ✅.
- Verified: `pytest tests/test_onprem_webhook.py` 11 passed. **실 HTTP 승인 루프 스모크**: `POST /webhook/alertmanager`(P2 heuristic)→`pending_approval`(APR-B8C3DDF2, incident_id null)→`GET /pending` count 1(전체 decision 보존)→`POST /approve/{id}`→`approved`+incident_id INC-8D539D65+executed→`/pending` count 0. `make check` → **614 passed, 1 skipped**.
- Blockers: 없음. 잔여(로드맵): Slack 버튼 프런트엔드·Temporal/Redis/PostgreSQL substrate·실 executor(MCP Gateway).
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드.

## 2026-07-14 — On-Prem PATH B webhook 구현: Alertmanager→in-process Day-2 파이프라인

- Status: ARCHITECTURE 로드맵의 On-Prem PATH B(이벤트 수신=Webhook FastAPI, 오케스트레이션=직접 호출) 🔲을 **구현+라이브 검증**으로 종료. 발견: Day-2 4핸들러(detector/analyzer/decision/executor)는 이미 on-prem을 지원(detector가 Alertmanager `alerts`/`groupLabels` 자동감지→onprem SignalAdapter, executor onprem 경로=로그-only 스텁)했고, **빠진 건 오직 이벤트 수신기+in-process 체이닝**이었음.
- Changed: 신규 `src/agents/ai/onprem_incident_pipeline.py`(`run_incident_pipeline`: 4핸들러를 출력→입력으로 in-process 체인, 클라우드 Step Functions/Workflows/Durable Functions 대응) + `src/agents/ai/onprem_webhook_api.py`(FastAPI: `POST /webhook/alertmanager`·`/webhook/incident`·`GET /health`, 컴팩트 요약 반환). `tests/test_onprem_webhook.py`(6 테스트: 실 detector/decision/executor 체인 + TestClient 엔드포인트, analyzer Bedrock은 stub·activity는 tmp 격리). Makefile `onprem-webhook` 타깃. `docs/ARCHITECTURE.md` L107(PATH B)·Day-2 On-Prem 컬럼 🔲→✅ + 구현 노트.
- Verified: `pytest tests/test_onprem_webhook.py` 6 passed. **실 HTTP 스모크**(`uvicorn onprem_webhook_api:app :8078` → curl): `/health` ok, `POST /webhook/alertmanager`(crash-loop 페이로드)→ onprem 감지·service=payments-api·resource=kubernetes-workload·heuristic severity·generic-recovery 런북(APPROVE)·onprem 로그-only 실행·incident_id 반환. `make check` → **609 passed, 1 skipped**.
- Blockers: 없음. 잔여(로드맵): Alertmanager 실연동·State Store(PostgreSQL/Redis)·실 executor(MCP Gateway)·Approval Flow.
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드 항목.

## 2026-07-14 — ARCHITECTURE.md 정합화: Orchestrator+A2A를 로드맵→구현(라이브 검증)으로 갱신

- Status: 이번 세션의 A2A Phase 1+2 실증으로 ARCHITECTURE.md가 stale해진 지점을 정합화. 문서가 supervisor+A2A를 여전히 🔲 "타깃/로드맵"으로 표기하고 있었음 → **구현·라이브 검증 완료**로 정정하되, 아직 미완인 부분(MCP Gateway 단일 카탈로그, supervisor의 local_deploy_api 배선)은 로드맵으로 명확히 분리.
- Changed: `docs/ARCHITECTURE.md` — (1) L22 구현 상태: "Orchestrator+A2A 통합 🔲" → "supervisor 라우팅+A2A discovery/위임 ✅(실 kagent 라이브)". (2) "Orchestrator + A2A" 섹션 헤더/인트로에 구현상태 블록 추가, 3개 불릿을 ✅/🔲로 정정(supervisor.py 배선·JSON-RPC 0.3·messageId·capability 격리 명시). (3) 현재/타깃 표의 "에이전트 연결 현재=각자 독립 실행" → "A2A 상호운용 ✅". (4) Gateway A2A Server 프로토콜에 JSON-RPC 0.3(kagent 카드 호환) 명시. 코드 변경 없음(문서만).
- Verified: 편집 후 문서 내 상호 참조/앵커 정합 확인(취약 앵커 링크는 텍스트 참조로 대체). 코드 무변경이라 gate 영향 없음(직전 baseline 603 passed 유효).
- Blockers: 없음.
- Next: (외부/deferred) Slack App · 아티클. 로드맵 빌드 항목(온프렘 PATH B/Day-2, 클라우드 Provision 어댑터, MCP Gateway 단일 카탈로그, Agent Runtime 매니지드 호스팅)은 스코프 큰 선택지 — 착수 시 사용자 지정.

## 2026-07-14 — A2A capability-isolation: PROVISION role 오버매칭 격리 강화

- Status: Phase 2 검증 중 관찰한 **PROVISION role 오버매칭**을 수정. discovery-only 체크에서 `matching_skills(진단카드, PROVISION)`가 `[cluster-diagnostics, observability]`를 반환 — 진단 카드가 provision 전문가로 잘못 매칭될 여지. Phase 1의 KAGENT/DEPLOY 격리와 동일 원칙 적용.
- Changed: `supervisor.py` `ROLE_SKILL_TERMS[PROVISION]`에서 generic `"cluster"` 제거 → provision-특화어 `"infrastructure"`로 교체(`provision`/`terraform`/`ansible`/`infrastructure`). KAGENT와 동일한 경고 주석 추가. `test_supervisor.py`에 회귀 테스트(`test_rejects_diagnostic_only_card_for_provision_role`): 진단-only 카드는 PROVISION에서 `[]`, KAGENT에서만 매칭, 진짜 provisioner 카드는 PROVISION 매칭 유지.
- Verified: `pytest tests/test_supervisor.py` 13 passed; `make check` → **603 passed, 1 skipped**.
- Blockers: 없음.
- Next: (외부/deferred) Slack App 실생성 · 테크 아티클 배포. 코드 백로그 소진.

## 2026-07-14 — A2A Phase 2 완료: 실 kagent 에이전트 대상 라이브 E2E + 스펙 갭 수정

- Status: open-risk #5의 **Phase 2(실제 kagent endpoint)를 라이브로 완결**. defer 권고였으나 착수 → kind+kagent 0.9.11+로컬 MLX Qwen 30B 재프로비저닝 후, supervisor가 **실 kagent 에이전트**를 discovery→match→위임하고 실 도구 진단까지 받는 end-to-end 성공.
- Changed: **버그 수정** `supervisor.py` — JSON-RPC `message/send`의 `params.message`에 A2A 스펙 필수 필드 **`messageId`(UUID) 누락**을 추가. 스펙 준수 `a2a` SDK(kagent 서버)가 `-32602`로 거부하던 것 — **Phase 1의 관대한 자체 게이트웨이는 못 잡던 실 갭**. `test_supervisor.py`에 회귀 테스트(`test_jsonrpc_message_includes_required_message_id`). 신규: `infra/onprem/kagent/local-diagnostic-agent.yaml`(read-only 진단 에이전트, local-qwen ModelConfig+k8s read tools+A2A skills), `docs/evidence/a2a-phase2-live-e2e.log`(성공 트랜스크립트).
- Verified: **라이브 E2E**(in-cluster driver 파드, supervisor.py stdlib-only 복사 실행 → 설계 의도인 카드 내부 DNS url 그대로 도달): classify=kagent → **HTTP `/.well-known/agent-card.json` discovery** → skill 매칭 `[cluster-diagnostics, observability]`(DEPLOY role은 `[]`로 격리 확인) → **JSON-RPC message/send 위임** → kagent 에이전트가 **실 `k8s_get_resources` MCP 도구 호출** → 30B가 `helm/istio/promql-agent` non-Running(0/1) **정확 진단** 반환. 과거 블로커(kind pod→host MLX)는 프록시 **0.0.0.0 바인딩**으로 해소(파드에서 `host.docker.internal:18091` 도달 확인). `make check` → **602 passed, 1 skipped**.
- Blockers: 없음. 인프라(kind `platform-agent` 3노드 + kagent 18파드 + MLX 30B)는 **실행 중 유지** — 데모/추가 검증 원하면 그대로, 정리는 `make local-cluster-down` + `pkill mlx_lm.server`/proxy.
- Next: (외부/deferred) Slack App 실생성 · 테크 아티클 배포. 코드 백로그 재소진.


## 2026-07-13 — NEXT_PUBLIC 프로덕션 인라인 이슈 실측 → 해소(stale)

- Status: risk #7(선택) 진단·실측 종결. Next 16.2.10 `next build`가 `.env.local`의 NEXT_PUBLIC를 정상 인라인함을 확인 → 과거 "미인라인" 노트는 현재 재현 안 됨(stale), 코드 수정 불필요.
- Verified: `dashboard-header.tsx`(`"use client"`)의 `process.env.NEXT_PUBLIC_DASHBOARD_DEV_AUTH`가 빌드 청크에서 `signIn("dev-credentials")`로 **상수 폴딩**(=`"1"` 인라인), `.next/static` 전체에 원문 env 참조 0건. Next 공식 문서로 메커니즘 교차확인(빌드시점 인라인·정적 참조만·/src 사용시 .env는 루트 로드). `.env.local`은 gitignore라 Vercel 빌드엔 부재→prod는 GitHub OAuth 폴백(의도대로).
- Changed: 코드 변경 없음(진단만). STATUS/NEXT_PLAN #7 해소 표기.
- Blockers: 없음.
- Next: 잔여는 A2A Phase 2(kagent, 인프라 무게로 defer 권고) + deferred 외부항목(Slack/아티클).

## 2026-07-13 — A2A Agent Card discovery 실연결(Phase 1) + 매칭 규율 강화

- Status: risk #5(A2A discovery)의 실체를 **라이브로 실연결**. supervisor의 discovery 코드는 이미 완비돼 있었고(카드 fetch+skill 매칭+HTTP/JSONRPC 위임+trace), 갭은 "살아있는 엔드포인트 대상 실증 부재"였음 → 게이트웨이 A2A 서버를 실기동해 mock 없이 E2E 실증.
- Changed: `supervisor.py` `ROLE_SKILL_TERMS[KAGENT]`에서 generic `kubernetes/cluster` 제거 → 진단 특화어(`diagnostic/troubleshoot/observability/investigat/debug/logs`)로 교체. `test_supervisor.py`에 회귀 테스트(`test_rejects_deploy_only_card_for_kagent_role`) 추가. 코드 외 실증 스크립트는 scratchpad.
- Verified: uvicorn 게이트웨이(`/.well-known/agent-card.json` = Platform Deployer Agent, 6 skills) 실기동 → supervisor `from_environment`가 **HTTP로 카드 discovery → DEPLOY skill 매칭 → 위임(delegated=True, trace matched→sent)**. 강화 후 **KAGENT role은 deploy-only 카드를 `capability_mismatch`로 거부**(delegated=False) 라이브 확인. `pytest tests/test_supervisor.py tests/test_gateway.py` 41 passed.
- Blockers: **Phase 2(실제 kagent endpoint)** 미완 — kind+kagent+MLX 재프로비저닝 필요(원커맨드 스크립트 부재, MLX 미구동). JSON-RPC 진단 task 자체는 과거 실증.
- Next: (선택/무거움) Phase 2 kagent 재프로비저닝 후 실 카드 대상 KAGENT discovery.

## 2026-07-13 — 잔여 백로그 정리: kagent(MOOT) + feat 브랜치 로컬 삭제

- Status: 남은 우선순위 소진. **kagent 정리는 MOOT**로 검증 종결, 중복 **feat 브랜치 로컬 삭제**.
- Verified: 활성 kube context 없음(`current-context` 미설정, `kind get clusters` 0개); Multipass `k8s-lab` k3s VM은 Ready(v1.31.4, 44h)이나 kagent namespace·helm·비시스템 파드 전무 → kagent 정리 대상 부재. `git branch -d feat/onprem-offline-recording-hybrid-rollback`(was 930fe98, main에 완전 머지) 로컬 삭제 완료.
- Blockers: origin `feat` 브랜치 삭제는 권한 분류기가 차단(제네릭 지시로 원격 삭제 불가) → **명시 승인 대기**. 미커밋 doc 정리분은 이 커밋으로 반영.
- Next: (승인 시) origin feat 삭제 / (deferred) Slack App·아티클.

## 2026-07-13 — AWS CDK live diff 재검증 (인프라 drift 0)

- Status: NEXT_PLAN의 "synth 미완" 블로커를 근본원인까지 진단·해소하고 live diff를 실측. **인프라/IAM drift 0** 확인.
- Root cause: `src/stacks/cdk.out`이 **1.8GB 재귀 중첩**(asset.X/src/stacks/cdk.out/asset.Y…) — `Code.fromAsset(projectRoot)`의 exclude에 `cdk.out`이 추가되기 전(수정 Jul 11 11:00)에 쌓인 stale 산출물이 synth를 사실상 무한 복사로 몰던 것. exclude는 이미 코드에 있음.
- Changed: 코드 변경 없음. stale `cdk.out` 삭제(1.8GB 회수). 문서: NEXT_PLAN/STATUS/AGENT_BRIEF에 재검증 완료 + diff context 주의 기록.
- Verified: `cdk synth IncidentAgentStack` **~17s exit 0**(새 cdk.out 37M, 99 resources); `cdk diff --no-change-set` **exit 0**. **진짜 diff = Lambda 13개 코드 asset-hash churn만**(재번들링 노이즈), 리소스/IAM add·delete 0. ⚠️ diff는 `-c vercelTeamSlug=men16922 -c vercelProjectName=platform-agent -c vercelOidcProviderArn=arn:aws:iam::908601828278:oidc-provider/oidc.vercel.com/men16922` 필수 — 없으면 조건부 `VercelDashboardReadRole`이 빠져 가짜 삭제 diff.
- Blockers: 없음. 배포는 하지 않음(재검증만).
- Next: kagent 정리 / (선택) feat 브랜치 삭제 / 미커밋 doc 정리분 커밋.

## 2026-07-13 — 추적 IA 자연어 4스텝 라이브 실증 완료

- Status: LinkedIn 데모 녹화 세션에서 자연어 4스텝을 **브라우저 end-to-end로 실증 완료**. ① `Provision ... then deploy orders-api ...`(Provisioning+Deployments 2행) → ② `Roll back orders-api ...`(단일-row 승계, 중복행 없음) → ③ History 행 클릭→중첩 상세(provisioning⊃deploy) → ④ `Tear down the on-prem cluster`(provision rolled-back + orders-api 자동 cascade rolled-back·Rollback 비활성). 이로써 open-risk #6(라이브 실증 미완) 해소.
- Changed: 코드 변경 없음(실증만). 문서 정합화: STATUS open-risk #6 해소, NEXT_PLAN 실증/커밋 항목 close, AGENT_BRIEF 스냅샷 갱신. `.claude/skills/`에 `grill-me`/`grilling` 스킬 2종 도입, `docs/reference/enterprise-ai-governance-dashboard.md` 레퍼런스 노트 추가(DECISIONS Future Reference 포인터).
- Verified: 4스텝 브라우저 실증(사용자 확인); 증거 영상 `docs/post/local-onprem-edited.mp4`(18.2s hero cut: step 1+3). IA 정리분은 커밋 `930fe98`에 이미 포함.
- Blockers: 없음. 남은 것은 `feat/onprem-offline-recording-hybrid-rollback` **push/머지 결정**(별도 승인 대기).
- Next: push/머지 결정 → (선택) AWS CDK live diff 재검증 / kagent 정리.

## 2026-07-12 — 데모 영상 편집 및 자막 버닝 완료

- Status: `docs/post/local-onprem.mov` 원본 영상을 10~20초 범위 내인 18.2초로 편집하고, 각 7개 구간의 설명 자막을 병합(burn-in)하여 `local-onprem-edited.mp4`로 저장 완료.
- Changed: `edit_video_pil.py` 스크립트를 작성하여 FFmpeg 프레임 추출 ➔ Pillow 자막 드로잉 ➔ FFmpeg 비디오 인코딩 파이프라인 구현. 자막 문구를 실제 구동 모드인 "Terraform"으로 정확하게 매핑.
- Verified: `docs/post/local-onprem-edited.mp4` 생성 (18.2초, 1.0MB, silent). 자막 문구 검증 완료.
- Blockers: 없음.
- Next: 자연어 4스텝 라이브 UI 실증 완료 후 전체 커밋 및 push/머지 결정.

## 2026-07-12 — 배포 추적 IA 정리: Provisioning/Deployments/History 분리 + 중첩 상세 + 롤백 단일-row/cascade

- Status: 추적(activity) 데이터 모델·UX를 대폭 정리. **provision/deploy `type` 분류** + **provider×environment** 일관 taxonomy, 롤백을 **단일-row 승계**(새 행 X), **cluster teardown이 그 클러스터 deploy들을 자동 rolled-back으로 cascade**, 자연어 명령(rollback/teardown)도 UI와 동일하게 승계/cascade로 라우팅.
- Changed:
  - Python `deploy_recorder`: `type`(provision/deploy)·`cluster`(연결키)·`environment`(더 이상 provider로 안 덮음) 저장, `_infer_service_version` deploy 우선(=version=kind 버그 수정), 복합 run을 provision+deploy **2행 분리**+단계별 성공판정, `record_rollback`(deployment_id supersede), `record_cluster_teardown`(provision 승계+deploy cascade), `read_deploys`(백엔드별 최신, 동일 timestamp는 나중 기록 우선), `record_deploy`가 teardown-only/rollback-only 자연어 run 라우팅. `local_deploy_api` rollback 배선(deployment_id/service/version/environment, scope=cluster→cascade).
  - Dashboard: **Provisioning**·**History**(Provisioning/Deployment Logs 2섹션·페이징) 페이지 신규, nav 워크플로순(Overview→Agents→Provisioning→Deployments→History→Incidents), **통합 중첩 상세**(상단 provisioning·하단 deploy `<details>` 아코디언, focus만 펼침), 롤백 **인앱 팝업**(Deployments=앱 전용/Provisioning=cluster teardown), 단일-row 갱신, cluster 없음/torn-down 시 Rollback 비활성화, **행 클릭→trace**(Trace 버튼 제거), `model-logo` 서버컴포넌트 onError 오류→client `model-logo-img` 분리, `getLifecycleDetail`.
  - Makefile: `dev-up`/`dev-down`/`dev-status` 한 방 스택 기동(MLX 재사용, router에 `PLATFORM_ACTIVITY_FILE`), `router-api`/`local-llm-up`에 오프라인 기록 env.
  - Docs: `linkedin-onprem-agent-20s-demo.md` 시나리오를 **자연어 명령 중심**(provision+deploy 한 문장→앱 롤백→History 중첩 상세→teardown cascade)으로 재작성.
- Verified: `make check`(anaconda) → **600 passed, 1 skipped**(recorder cascade 테스트 2개 신규); dashboard `tsc` 0 + `next build` 성공; dev 서버 `/provisioning`·`/history`·`/deployments` 200.
- Blockers: 신규 UI/자연어 cascade의 **라이브 end-to-end 실증 미완**(사용자 브라우저 테스트 예정); 미커밋(브랜치 `feat/onprem-offline-recording-hybrid-rollback`); 레거시 activity 행은 `cluster` 없어 롤백 비활성(클린슬레이트는 activity.jsonl 비우기).
- Next: 자연어 4스텝(provision+deploy→app rollback→History 상세→teardown cascade) 라이브 실증 → 전체 커밋 → 브랜치 push/머지 결정.

## 2026-07-12 — On-Prem 오프라인 기록 + Hybrid 대시보드 + 실 롤백 + Local Qwen 7B 전환

- Status: On-Prem 경로를 **기록→병합→롤백까지 오프라인으로 완결**. Local Qwen을 30B→**7B**로 전환하고 tool-call/컨텍스트 이슈를 해결해 자연어 provision→deploy→validate **~39s 자율 수행** 실증.
- Changed:
  - Python: `deploy_recorder` 로컬 JSONL 백엔드(`PLATFORM_ACTIVITY_FILE`); `local_deploy_api` `/api/local-rollback`(app rollout undo + cluster teardown); `mlx_qwen_tool_proxy` JSON/Hermes tool-call 파서(7B는 ```json 블록으로 tool call 방출); `local_deployer` `deploy_service` 복합툴 + 하드닝; provision/ops 출력 ANSI 절단(작은 모델 루프 유지).
  - Dashboard: `activity-data` **local + hybrid**(AWS DynamoDB + On-Prem JSONL 병합) read; rollback route onprem 분기(→라우터); deployments-control 버튼 provider/scope; `data-source-badge` local/hybrid; 모델 로고 4종 로컬 SVG·SELECTED 배지·timestamp `suppressHydrationWarning`.
  - 로컬 dev 로그인: `.env.local`에 `DASHBOARD_DEV_AUTH`/`NEXT_PUBLIC_DASHBOARD_DEV_AUTH`/`AUTH_SECRET`/`AUTH_TRUST_HOST`; `next dev` 구동(NEXT_PUBLIC 프로덕션 인라인 이슈 회피).
  - Makefile: pytest 가능한 인터프리터 자동 탐지(.venv-mlx 그림자 방지).
- Verified:
  - `make check`(anaconda) → **598 passed, 1 skipped**; dashboard `next build` 성공.
  - Live(7B): `provision_cluster`(~21s)→`deploy_service`→validate DONE **~39s**, orders-api 1/1 Running; **app 롤백** v2→v1(`rollout undo`); **cluster 롤백** teardown; `/api/dashboard/deployments`가 `source=hybrid`로 로컬+AWS 병합 반환(내 On-Prem 기록 포함).
  - 커밋 `0b9148c`(브랜치 `feat/onprem-offline-recording-hybrid-rollback`, 24 files/+558); tfstate gitignore.
- Blockers: 대시보드 rollback **버튼→라우트(auth 게이트)** 체인은 로그인 세션 필요해 curl 미검증(라우터 엔드포인트는 검증됨); `NEXT_PUBLIC`은 프로덕션(next start) 인라인 안 돼 `next dev` 사용; 브라우저 확장 미연결로 클릭 자동화 불가.
- Next: 로그인 후 UI Rollback 클릭 실증 → 브랜치 push/머지 결정 → (선택) NEXT_PUBLIC 프로덕션 인라인 해결.

## 2026-07-11 — On-Prem 실 k3s Provision + Agents 선택 UX + LinkedIn 데모 초안

- Status: 기존 Multipass `k8s-lab` VM에 Ansible k3s Provision을 실제 적용하고, Agents 화면을 Agent→Model→Runtime→trace 단일 선택 흐름으로 재구성.
- Changed: k3s config 디렉터리 생성/idempotency 수정, local inventory·kubeconfig ignore; On-Prem runtime panel/router 상태, Agent/Model selection, 실제 model brand asset; `docs/post/linkedin-onprem-agent-20s-demo.md` 추가.
- Verified: k3s v1.31.4 control-plane Ready; Ansible 재실행 `changed=0`; Dashboard `npm run build` 성공.
- Blockers: AWS CDK live diff는 Lambda dependency bundling이 완료되지 않아 재검증 필요; kagent 기본 agent 정리 여부 미결정.
- Next: CDK diff 재검증 → kagent 기본 agent 유지/정리 결정 → 명시 요청 시 push.

## 2026-07-11 — Supervisor 요청 라우팅 + A2A 위임 경계

- Status: Orchestrator(supervisor)의 최소 수직 슬라이스 구현 — 자연어 요청을 provision/deploy/kagent 역할로 분류하고, 등록된 specialist endpoint로만 A2A `message:send` 위임.
- Changed: `supervisor.py`(결정·trace·표준 HTTP A2A client), Gateway A2A Server의 route trace artifact, `PLATFORM_{PROVISION,DEPLOY,KAGENT}_A2A_URL` 환경변수 registry, 라우팅/위임/안전한 미등록 상태 테스트 추가.
- Verified: `pytest tests/test_supervisor.py tests/test_gateway.py -v` → 37 passed. 전체 `pytest tests/ -q`는 외부 pytest 런타임에서 종료 출력이 확보되지 않아 baseline 갱신 없이 유지.
- Blockers: 실제 kagent A2A endpoint 및 Agent Card discovery/skill 기반 라우팅 미연결; 현재 Agent Card는 Gateway `/.well-known/agent-card.json` 노출·검증만 사용.
- Next: kagent endpoint 등록 → Agent Card discovery/능력 매칭 → 로컬 Qwen ModelConfig 연결.

## 2026-07-11 — 범용 Ops 에이전트 + 관측성 + On-Prem Provision(Terraform/Ansible) + kagent + 아키텍처 정식화

- Status: AI Model Router 배포 채팅을 **범용 On-Prem Ops 에이전트**로 확장(질의→자율 tool 수행), reasoning+tool 트레이스 스트리밍/기록/상세페이지, On-Prem **Provision 역할**(Terraform kind + Ansible k3s) 구현, kagent 설치, ARCHITECTURE 통합·최신화.
- Changed:
  - **범용 Ops**: `ops_tools.py`(read-only kubectl: list_pods/get_logs/describe/rollout_status/list_namespaces) + 시스템프롬프트 일반화. 도구셋 = provision+deploy+investigate(12개).
  - **Provision(① 역할)**: `adapters/provisioning/`(base/onprem/registry) + `provision_tools.py`(provision_cluster/teardown) + `infra/onprem/terraform`(kind IaC, validate/plan ✅) + `infra/onprem/ansible`(k3s 플레이북).
  - **관측성**: `model_router.build_trace`(reasoning+tool ordered trace) + SSE `reasoning` 이벤트, `deploy_recorder` trace 저장, 배포 상세 페이지(`/deployments/[id]`) — instruction/reasoning/tool args·result/summary(markdown)/kubectl output.
  - **대시보드**: 로컬 dev 로그인(GitHub 없이 admin, prod 비활성), Agents 채팅 SSE 스트리밍+인라인 args/result, ModelLogo, Agent 카드 **Tools 팝업**(포털), 배포 상세 진입(Deployments/타임라인), 폭 확대(max-w-[1800px]), 채팅 60vh, 타임라인 10건 페이징.
  - **kagent**: kind에 helm 설치(controller/ui/postgres Running, 에이전트 10개 CRD). LLM(로컬 Qwen) 연결은 호스트 네트워킹 미해결.
  - **Make**: `local-llm-up/down/status`, `mlx-serve/mlx-proxy/router-api`.
  - **Docs**: ARCHITECTURE 통합 스택 표 + Orchestrator+A2A 타깃 + On-Prem "MCP만" 부정확 수정. DECISIONS D9.
- Verified:
  - `make check` → **584 passed, 1 skipped**; dashboard `tsc` 0; `terraform validate/plan` green.
  - **Live E2E (실 MLX Qwen30B → kind)**: NL 배포 build→push→deploy→validate + recorder→DynamoDB→대시보드 aws-live 추적, reasoning/tool SSE, "list pods" 질의는 진단만 수행 확인.
- Blockers: kagent↔로컬 Qwen 연결(kind pod→host MLX 네트워킹, MLX proxy 0.0.0.0 바인딩 필요). 클라우드 Provision/Agent Runtime 호스팅·Orchestrator+A2A 통합 = 로드맵.
- Next: (1) Orchestrator(supervisor)+A2A 통합 착수, or (2) kagent↔Qwen 연결 완성, or (3) push(현재 origin 대비 ahead 18).

## 2026-07-11 — AI Model Router + 자연어 On-Prem 배포 + 대시보드 Agents 채팅

- Status: 모델(두뇌)과 환경(대상)을 분리하는 **AI Model Router**를 구현하고, On-Prem은 Strands 대신 **Pydantic AI + MLX Qwen** 독립 에이전트로 전환. 대시보드 Agents 페이지에 모델 선택 + 자연어 배포 채팅 추가.
- Changed:
  - `model_router.py` — 모델 레지스트리(local-qwen/bedrock-claude/vertex-gemini/azure-gpt) + (model×environment) 적합도 매트릭스 + 라우팅.
  - `local_deployer.py` — Strands 무의존 Pydantic AI On-Prem 에이전트(완전 오프라인). `local_deploy_api.py` — `/api/models`(셀렉터) + `/api/local-deploy`(실행). `deploy_recorder.py` — DEPLOY+ACTIVITY 기록(executor-writes, env 게이트).
  - `mlx_qwen_tool_proxy.py` — 클라이언트 `stream` 플래그 존중(SSE/JSON 양쪽) 프레임워크 중립화.
  - Dashboard: `agents/deploy`·`agents/models` 라우트, `agent-deploy-chat.tsx`(적합도 배지+step trace), `lib/model-router.ts`(정적 fallback), `agents/page.tsx` 연동.
  - `scripts/slack_live_approval.py` — AWS 배포 없이 Slack 승인 send/simulate/full 하네스.
  - Docs: `ARCHITECTURE.md`(Model Router 섹션+프레임워크 표+On-Prem 갱신), `local-llm-onprem.md`(프레임워크 분리 기록). `pyproject.toml` `[onprem]` extra.
- Verified:
  - `make check` → **569 passed, 1 skipped** (신규 +22 테스트: router/local_deployer/local_deploy_api/deploy_recorder/proxy).
  - Dashboard `tsc --noEmit` 0 + `next build` 성공(신규 라우트 등록 확인).
  - 라우터 API live: `/api/models?provider=onprem` → local-qwen recommended 최상단, aws → bedrock-claude recommended 확인.
  - **Live E2E (신규 Pydantic AI 경로)**: MLX Qwen3-Coder-30B(.venv-mlx, :18090) + proxy(:18091) → `route_deploy("Deploy orders-api ... namespace local-llm-smoke", local-qwen, onprem)` → build→push→deploy→validate 자율 4-tool 실행, `ok=True`. kubectl 확인: `orders-api 1/1 Running`, image=`localhost:5001/orders-api:v1.5.0` 롤링 업데이트.
  - **Live 추적 실증 (Deployments 배선 완성)**: API 배포(`PLATFORM_ACTIVITY_TABLE`=platform-agent-activity, us-east-1) → recorder가 `DEP-262AC0A3`(orders-api v1.6.0)+`ACT-1C981F27` 기록 → 대시보드 `/api/dashboard/deployments`(source: aws-live)가 최신 배포로 노출 확인. kubectl: image v1.6.0. 대시보드↔라우터 API 배선도 dev 서버 live curl(`source: router-api`)로 확인.
  - Slack simulate: approve/reject E2E(실 HMAC 서명 → SFN send_task_success/failure) 통과.
- Blockers:
  - ⚠️ 워킹트리에 **세션 외 미커밋 변경** 다수(ruff autofix류). 특히 `src/agents/models.py` 재수출 제거로 `from src.agents.models import ServiceSpec` ImportError(테스트는 통과). 이번 커밋에서 제외함 — 별도 검토 필요.
  - 실 MLX 서버 기반 채팅→kind 배포 live 스텝은 운영자 수행 필요(로직은 TestModel로 검증).
- Next: 세션 외 미커밋 변경(특히 models.py) 검토/정리 → 대시보드 채팅 live 데모(MLX+kind).

## 2026-07-11 — 로컬 Qwen3-Coder 모델 기반 On-Premises E2E 자율 배포 검증 완료

- Status: MLX Qwen tool proxy의 이중 호환성(Pass-through 및 XML Fallback) 개선을 적용하고, 로컬 kind 클러스터 및 레지스트리 환경에서 strands 자율 배포 E2E 연동 테스트 통과.
- Changed:
  - Tool Proxy: `mlx_qwen_tool_proxy.py`에서 MLX-LM 서버의 네이티브 `tool_calls` JSON 구조를 무손실 중계(Pass-through)하도록 보완하고 XML 마크업 Fallback 로직을 개선.
  - Documentation: `local-llm-onprem.md`에 proxy 구조와 kind 클러스터 E2E 배포/검증 E2E 실행 결과 수록.
- Verified:
  - `make local-cluster` 기동 및 MLX Qwen proxy (:18081) 연동 테스트 완료.
  - `orders-api` 배포 E2E: 빌드(build_image) -> 푸시(push_image) -> local-llm-smoke 네임스페이스 배포(deploy_to_cluster) -> 검증(validate_deployment, 1/1 Ready) 자율 연동 성공.
  - 전체 단위/통합 테스트 (`make check`) 실행: 544 passed, 1 skipped (성공).
- Next: Slack App 대화형 인터랙티브 컴포넌트 실연동 설정 (Task 12).

## 2026-07-11 — 유저 권한 관리(Users Admin UI) 및 멀티 클라우드 장애 복원력(Failover) 연동 완료

- Status: Admin용 사용자 계정 권한 제어판 구축 및 AWS/GCP/Azure 장애 발생 시 예비 리전/클러스터 우회 복구(Multi-region Failover) 시스템 구현 완료.
- Changed:
  - Users UI: `/users` 계정 권한 설정 페이지를 신설하고 대시보드 내 `UsersTable` 클라이언트 컴포넌트를 연동. Admin 역할 사용자만 진입 가능하며 DynamoDB에 저장된 개별 세션 계정 등급(Viewer/Operator/Admin)을 실시간 편집 가능.
  - Self-lockout Protection: 관리자가 본인 역할을 실수로 강등하여 관리 콘솔에서 잠기는 잠금 방지(Lockout Protection) 기능 적용.
  - Sidebar: 로그인 세션의 역할에 따라 `admin` 권한이 있는 경우에만 "Users" 메뉴가 동적으로 노출되도록 개선.
  - AWS Failover: SSM Automation 실행 실패 시 `AWS_FAILOVER_REGION`(기본 `us-east-1`)으로 자동 스위칭하여 복구 문서를 재시도하도록 보강.
  - GCP Failover: GKE API 호출 및 Cloud Run 조작 실패 시 `GCP_FAILOVER_CLUSTER_NAME` 및 `GCP_FAILOVER_REGION`으로 우회하여 복구 동작을 연속 수행하도록 지원.
  - Azure Failover: AKS 크레덴셜 획득/API 배포 실패 시 `AZURE_FAILOVER_CLUSTER_ID` 및 `AZURE_FAILOVER_RESOURCE_ID`로 Failover하여 실행 보장.
  - MLX-LM Integration: On-Premise 타겟 배포 시 로컬 MLX-LM API 서버를 타겟팅할 수 있는 통합 연동 모듈을 `strands_deployer`에 추가하고 python 환경에 `mlx-lm` 설치 완료.
  - Tests: `test_multicloud_runners.py`에 GKE failover 복구 단위 테스트를 추가하고 전체 543개 백엔드 테스트 및 Next.js 프로덕션 빌드/배포 패스 검증 완료.
- Next: Slack 대화형 연동 가이드 정리.

## 2026-07-11 — 대시보드 감사 로그(Audit Logs) 뷰어 및 역할 기반 필터 연동 완료

- Status: 시스템 변조/승인 이력을 모니터링할 수 있는 감사 로그(Audit Logs) 조회 페이지 및 전용 API 구현 완료.
- Changed:
  - API Route: `/api/dashboard/audit` 엔드포인트를 구현하여 인증 및 역할 검증(Admin/Operator 권한 체크)을 거쳐 감사 로그를 전달하고 미들웨어 수준에서 경로 차단 보호를 적용.
  - Audit Page: `/audit` 화면을 신설하여 비인증/Viewer 등급 사용자에게는 "Access Denied" 오류 화면을 출력하고, 승인된 관리자에게는 SSR 기반의 실시간 DynamoDB 로그 리스트 렌더링.
  - Audit logs table: 클라이언트 컴포넌트(`AuditLogsTable`)를 개발하여 감사 ID, 수행한 운영자, 액션, 대상, 결과 상태(Success/Failed), 발신 IP 및 UserAgent의 대화형 검색 및 필터링 기능 추가.
  - Sidebar: 로그인한 세션 유저의 역할에 맞춰 Admin/Operator인 경우에만 좌측 네비게이션 메뉴에 "Audit Logs" 메뉴 아이템이 동적으로 렌더링되도록 개선.
  - Overview: 메인 Overview 화면의 "Incident feed" 옆 "View all →" 요소를 Next.js `Link` 컴포넌트로 연동하여 실제 Incidents 페이지로 정상 라우팅되도록 수정.
  - Deploy: Next.js 16 빌드 성공 및 최종 프로덕션 웹사이트 배포 완료.
- Next: Slack App 대화형 구성요소의 실 연동 설정 가이드 수립.

## 2026-07-11 — GCP 및 Azure 실 API 연동 및 OIDC 인증 연동 완료

- Status: AWS STS 연계를 활용한 GCP/Azure 실 REST API 연동 및 OIDC 페더레이션 크레덴셜 자격증명 모듈 구현 완료.
- Changed:
  - GCP Auth: AWS STS GetCallerIdentity 서명 정보로 GCP STS 교환 토큰을 가져오는 WIF 페더레이션 자격증명 모듈(`gcp_auth.py`) 구현 (Service Account Key 폴백 지원).
  - GCP/Azure Runners: GKE 롤아웃 재시작/스케일링/롤백 API 호출 및 Cloud Run 스케일링/트래픽 롤백 REST API 호출이 가능한 실 인프라 러너(`gcp_runner.py`, `azure_runner.py`) 개발.
  - Executors: 중앙 AWS Step Functions Executor(`handler.py`) 및 GCP Cloud Workflows Executor(`gcp/executor.py`) 양측에 신규 외부 클라우드 실 실행부 바인딩 완료.
- Verified:
  - `pytest tests/test_multicloud_runners.py` -> 5 passed (성공).
  - 전체 파이썬 테스트 슈트 -> 541 passed, 1 skipped (Mock 모드 기본 지원 확인).
- Next: Slack App interactive 구성요소의 단일 AWS 연결 설정 연계.

## 2026-07-11 — Auth Phase 2 & 3 UI Control Panels 구현 및 배포 완료

- Status: 대시보드 내 승인/배포/롤백 수행이 가능한 대화형 UI 구성 요소 개발 및 프로덕션 배포 완료.
- Changed:
  - Incidents UI: `PendingApprovals` 카드 컴포포넌트 구현하여 미해결 승인 건 목록 노출 및 즉각적인 승인/거절 기능 제공 (역할 기반 접근 체크 연동).
  - Deployments UI: `DeploymentsControl` 컴포넌트 추가하여 신규 배포 트리거 모달 양식(`service_name`, `version`, `provider`, `environment`) 및 성공한 배포 건에 대한 롤백(Rollback) 실행 버튼 연동.
  - Vercel: 로컬 빌드 및 프로덕션 사이트(`https://platform-agent-red.vercel.app`)에 최종 배포 완료.
- Verified:
  - `make check` -> 536 passed, 1 skipped (성공).
  - Dashboard `npm run build` -> Next.js 16 빌드 및 TypeScript 타입 체크 성공.
- Blockers: 없음.
- Next: 추가로 요구되는 Slack App 연동 또는 GCP/Azure 클러스터 연동 시 설정 연계.

## 2026-07-11 — Auth Phase 2 (Option 1) & Phase 3 (Option 2) 완료

- Status: Auth Phase 2 및 Phase 3에 명시된 기능 전체 구현 및 빌드 검증 성공.
- Changed:
  - CDK: `platform-agent-users` 및 `platform-agent-audit` DynamoDB 테이블 정의 및 Vercel OIDC role 권한 부여. Step Functions `SendTaskSuccess/Failure/DescribeExecution` 권한 추가.
  - Auth Phase 2: GitHub Organization 멤버십 체크 및 DynamoDB 사용자 역할 연동 (`auth.ts`, `user-data.ts`), 사용자 역할 관리를 위한 관리자 API (`/api/dashboard/users`) 구현.
  - Auth Phase 3: Step Functions 연동 approval 승인/거절 API (`/api/dashboard/incidents/[id]/approve`), deployment trigger API (`/api/dashboard/deployments/trigger`), deployment rollback API (`/api/dashboard/deployments/[id]/rollback`) 구현.
  - Audit logging: 모든 쓰기/변경 엔드포인트에 90일 보관 감사 로그 적재 (`audit-data.ts`, `platform-agent-audit` 테이블 적재).
- Verified:
  - `make check` -> 536 passed, 1 skipped.
  - Dashboard `npm run build` -> Next.js 16 빌드 및 TypeScript 타입 체크 성공.
- Blockers: 없음.
- Next: Vercel에 신규 테이블 권한이 포함된 CDK 스택 재배포 및 배포 환경 연동.

## 2026-07-11 — Dashboard live data pipeline + Auth (Task 11 [auto] 완료)

- Status: Task 11 자동 항목(Activity DB write path, Auth.js Phase 1) 구현 및 검증 완료.
- Changed:
  - Write path: `src/agents/ai/pipeline.py`에 `platform-agent-activity` 테이블 적재 로직 `_record_pipeline_result` 구현.
  - Auth: GitHub OAuth(`dashboard/src/auth.ts`), 세션 프로바이더(`auth-provider.tsx`), 대시보드 헤더 세션 연동 및 미들웨어(`/api/dashboard/:path*/approve` 등) 보호 완료.
  - Test fix: `tests/test_gcp_day2_operations.py`의 휴리스틱 테스트들이 실 Vertex AI 대신 Mock/Heuristic Fallback을 타도록 `vertexai` 모듈 mock 패치 적용.
  - Renaming: 대시보드 UI 상의 `CNCF / On-Prem` 표기를 `On-Premise`로 리네이밍.
- Verified:
  - `make check` -> 536 passed, 1 skipped (성공).
  - GCP Day2 tests -> 28 passed.
  - Dashboard `npm run build` -> Turbopack 컴파일 및 타입 검사 통과.
- Blockers: 없음.
- Next: Vercel 환경 변수 `DASHBOARD_ACTIVITY_TABLE` 추가 및 대시보드 재배포 (manual).

## 2026-07-11 — Dashboard portfolio release (Task 10 완료)

- Status: 3개 항목 모두 구현·배포·검증 완료.
- Changed:
  - Open Graph: `opengraph-image.tsx` (Edge runtime 1200×630) + `twitter-image.tsx` + `layout.tsx` full OG/Twitter metadata.
  - Durable read model: `activity-model.ts` (DynamoDB 단일 테이블 PK/SK+GSI1) + `activity-data.ts` (3 feed 함수) + API routes 3개 + CDK `platform-agent-activity` 테이블.
  - Auth boundary: `docs/DASHBOARD_AUTH_DESIGN.md` (RBAC 3-role, JWT, 승인 플로우, 3-phase 구현 계획) + `dashboard/src/lib/auth.ts` (타입 모듈).
  - Pages: `page.tsx`/`deployments/page.tsx`/`agents/page.tsx`를 activity-data.ts 사용하도록 전환.
  - CDK: `platform-agent-activity` 테이블 + GSI1 + Vercel OIDC read grant 배포 완료.
- Verified:
  - `make check` → **525 passed, 1 skipped** (244.82s).
  - Dashboard `npm run build` → 11 routes 컴파일 성공 (opengraph-image, twitter-image 포함).
  - Vercel production 배포 → `platform-agent-red.vercel.app` OG image 200 OK (107KB), 전체 meta tags 확인.
  - CDK deploy → `platform-agent-activity` ACTIVE (PK/SK + GSI1), Vercel role에 read 추가.
  - AWS: `aws dynamodb describe-table` → 스키마 정확 확인.
- Blockers: 없음.
- Next: Executor에서 activity table write path 연결 → Auth.js Phase 1.

---

## 2026-07-11 — Vercel OIDC live incident production 활성화

- Status: 완료.
- Changed:
  - AWS: Vercel Team issuer OIDC Provider + `platform-agent-vercel-dashboard-read` Role 배포; `incident-history` read-only 권한.
  - Vercel: Production/Preview에 live source, region, table, role ARN env 설정; CLI root link + `.vercelignore` 추가.
  - Production `https://platform-agent-red.vercel.app` 갱신.
- Verified:
  - CloudFormation `UPDATE_COMPLETE`; OIDC trust는 team/project + production/preview subject로 제한.
  - Protected Preview와 Production API 모두 `source=aws-live`; 현재 records 0건.
  - Production Overview `LIVE · AWS` 표시, Playwright console errors 0건.
- Blockers: 없음.
- Next: Open Graph 메타/이미지 구성과 공유 미리보기 검증.

---

## 2026-07-11 — Dashboard AWS incident live read path + Vercel OIDC

- Status: 구현·로컬 live read 검증 완료.
- Changed:
  - Dashboard `/api/dashboard/incidents` + server data source: `aws-live` / `demo` / `demo-fallback` 계약과 UI 라벨 추가.
  - Executor DynamoDB record에 provider/mode/runbook/timestamp/executed_actions read-model 필드 추가.
  - CDK: Vercel team/project/environment-scoped OIDC trust + `incident-history` read-only IAM role.
- Verified:
  - `make check` → **519 passed, 1 skipped** (230.44s); 신규 persistence test 포함.
  - Dashboard lint/build pass; Playwright demo API·페이지 console error 0건.
  - 로컬 AWS mode → `source=aws-live`, 0 records; CDK TypeScript build + OIDC-context synth pass.
- Blockers: 없음.
- Next: OIDC role을 실배포해 Vercel live feed 활성화.
