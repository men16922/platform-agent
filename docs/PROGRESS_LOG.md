# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-14

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-14 — Azure AI Foundry 실 배포 라이브 E2E + v1→v2 어댑터 결함 수정: 3/3 클라우드 완결

- Status: Runtime 호스팅 **3/3 클라우드 라이브 완결**(AWS+GCP에 이어 Azure). 도중 **실 코드 결함 발견·수정**: azure 어댑터가 v1 API(`create_agent`) 기준이었는데 설치 SDK는 `azure-ai-projects` **2.3.0(v2)** — v1 호출은 `AttributeError`로 실 환경에서 절대 동작 불가(목 테스트가 가림). v2로 재작성 후 실 배포까지 실증.
- Changed: (1) `azure.py` v2 재작성 — preflight `agents.list()`, host `agents.create_version(agent_name, definition=PromptAgentDefinition(model, instructions))`, teardown `agents.delete(name)`; `_prompt_definition` seam으로 테스트 SDK-독립. `test_runtime_adapters.py` azure 섹션 v2로 갱신(+1). (2) 신규 `infra/foundry/README.md` — 셋업 + 라이브에서 겪은 gotcha 5종(데이터플레인 RBAC≠Owner·MSA `--assignee-object-id`·모델 deprecation/SKU·에이전트명 하이픈(AgentCore는 언더스코어)·Responses API `agent_reference` 호출). 커밋 `4caf7de`(fix)·`2231362`(README).
- Verified: `make check` → **670 passed, 1 skipped**. 실 Azure eastus: Foundry 계정+프로젝트+gpt-5.4-mini 배포, **Cognitive Services User** 역할(사용자가 `!`로 부여), 어댑터 preflight→list, `host_agent(approved=True)`→`create_version`(v1)→**Responses API 쿼리** 응답 `"...hosted as an API agent on Azure AI Foundry"`→`teardown_agent(approved=True)`→삭제(0 agents). Standard 배포라 유휴 과금 ≈$0.
- Blockers: 없음. Azure 라이브가 오래 막혔던 원인=데이터플레인 RBAC(하네스가 IAM 부여 차단→사용자가 직접 실행). 
- Next: (선택) Azure Foundry 스택(계정/프로젝트/모델, ≈$0 유휴) 유지 or 삭제. origin push(로컬 10커밋).

## 2026-07-14 — GCP Vertex Agent Engine 실 배포 라이브 E2E: 어댑터 create→DEPLOYED→query→teardown (billable, 승인 후)

- Status: Runtime 호스팅 어댑터의 **GCP Agent Engine 실 배포 라이프사이클을 실 클라우드에서 실증** — AWS AgentCore에 이어 **2/3 클라우드 라이브 완결**. 사용자 승인 후 billable create → 호스팅된 reasoning engine이 Gemini로 실제 응답 → 즉시 삭제.
- Changed: 신규 `infra/agentengine/deployer_agent.py` — Agent Engine custom-template 에이전트(`set_up`+`query`, Gemini 2.5 Flash 호출, `hosted_on=vertex-agent-engine` 태깅). (어댑터 코드 자체는 `36085fc`.)
- Verified: 실 GCP us-central1(project-ec7809f7). GCS staging 버킷 생성, `cloudpickle.register_pickle_by_value`로 에이전트 직렬화, 어댑터 `host_agent(approved=True)`→`agent_engines.create`→**DEPLOYED**(reasoningEngines/6487926195169001472)→`query` 응답 `{"result":"...","model":"gemini-2.5-flash","hosted_on":"vertex-agent-engine"}`→`teardown_agent(approved=True)`→삭제→**list 0 완전 삭제**. 커밋 `40fa8f6`. 총비용 <$0.50(엔진 삭제 완료, staging 버킷 잔여=무시 가능).
- Blockers: 없음(GCP). Azure Foundry 실 create만 남음(Foundry 프로젝트 생성 선행 필요).
- Next: (선택) Azure Foundry 실 배포 or 외부(Slack App/아티클). origin push 대기(로컬 8커밋).

## 2026-07-14 — AWS AgentCore 실 배포 라이브 E2E: 어댑터 create→READY→invoke→teardown (billable, 승인 후)

- Status: Runtime 호스팅 어댑터의 **AWS AgentCore 실 배포 전 라이프사이클을 실 클라우드에서 실증**. 사용자 승인 후 billable create 실행 → 호스팅된 에이전트가 실제 응답 → 즉시 삭제(비용 최소화). 어댑터 create/teardown 경로가 목이 아닌 **실 API로 검증**됨.
- Changed: 신규 `infra/agentcore/` 패키징 — `app.py`(AgentCore 런타임 컨트랙트 `/invocations`+`/ping`, `bedrock-agentcore` SDK로 minimal Claude Haiku 4.5 converse 에이전트 래핑), `Dockerfile`(linux/arm64), `requirements.txt`. (어댑터 코드 자체는 앞 커밋 `36085fc`.)
- Verified: 실 AWS us-east-1(acct 908601828278). ARM64 이미지 build→ECR push(단일 매니페스트), 최소권한 exec role 생성, 어댑터 `host_agent(approved=True)`→`CreateAgentRuntime`→**READY(~12s)**→`invoke_agent_runtime` 응답 `{"result":"...hosted on Amazon Bedrock AgentCore","model":"claude-haiku-4-5"}`→`teardown_agent(approved=True)`→DELETING→**count 0 완전 삭제**. 커밋 `2079c01`. 총비용 <$0.50(런타임 삭제 완료, 잔여=ECR 이미지 ~$0.007/월+무료 IAM role).
- Blockers: 없음(AWS). GCP Agent Engine/Azure Foundry 실 create는 여전히 승인·(Azure는 프로젝트 생성) 대기.
- Next: (선택) ECR 이미지/IAM role 정리 or 유지, origin push. 잔여 외부: Slack App·아티클.

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
