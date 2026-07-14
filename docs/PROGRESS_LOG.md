# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 2 #3: MCP-over-HTTP 커넥터 + per-tool/글로벌 kill-switch (Tier 2 완결)

- Status: Tier 2 **#3 완료 → Tier 2(#2·#3·#4) 전체 완결**. MCP 게이트웨이에 (1) 원격 MCP 서버를 카탈로그 도구로 노출하는 intercept-reinject 커넥터, (2) 도구별·글로벌 kill-switch 추가. 모두 기존 단일 카탈로그/디스패치 위에 얹어 비파괴.
- Changed: `src/agents/ai/gateway/mcp_server.py` — (1) **remote MCP 커넥터**: `post_mcp_call(endpoint, tool, args)`(JSON-RPC `tools/call` over HTTP, stdlib urllib) + `_reinject()`(MCP content/isError/JSON-RPC error→`ToolResult`) + `remote_mcp_tool(name, …, endpoint, remote_tool=…, transport=…)` 팩토리(핸들러가 tool_use 가로채→원격 호출→재주입, 전송 실패 시 raise 대신 error ToolResult로 **degrade**). (2) **kill-switch**: `MCPServer(*, extra_tools, disabled_tools, kill_switch)` — `call_tool`이 존재검사(unknown→ValueError 유지) **후** kill-switch 게이트(글로벌=전 도구 차단, per-tool=해당 도구만 차단, 둘 다 핸들러 미실행 blocked ToolResult). `disable_tool`/`enable_tool`/`set_kill_switch` + `MCP_DISABLED_TOOLS`/`MCP_KILL_SWITCH` env. `tools`/`_tool_map`은 base 카탈로그+`extra_tools` 병합, 원격 커넥터도 동일 kill-switch 지배. `docs/ARCHITECTURE.md` 표 row#3 ✅ + Tier 2 완결 표기.
- Verified: 신규 `tests/test_mcp_connector.py` +13(글로벌/per-tool kill-switch 핸들러 미실행·enable 되돌림·env 파싱·unknown 우선 raise·base 카탈로그 불변(9)·extra_tools 디스커버리+디스패치·remote forward/reinject·isError·JSON-RPC error·전송실패 degrade·원격도 kill-switch 지배). `make check` → **736 passed, 1 skipped**(723→736). 기존 `test_gateway.py` 29건 무변경 통과=비파괴.
- Blockers: 없음. 실 원격 MCP 서버(SigV4/IRSA 인증) 라이브 연동은 사용자 엔드포인트 필요=자율 범위 밖; intercept-reinject 경로는 stub transport로 완결 검증. (SigV4 서명은 필요 시 `#4`의 `assume_role_session`/`gcp_auth.py` SigV4 선례 재사용 가능.)
- Next: **Tier 2 전체 완결.** 잔여 레퍼런스=#7(Helm/Terraform 프로덕션, Tier 3). 외부: Slack App 실 생성·아티클 배포·대시보드 OAuth 로그인 데모. (선택) 실 로컬 MLX-Qwen sampler self-consistency 라이브 실증.

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 2 #4: cross-account STS AssumeRole + graceful fallback

- Status: Tier 2 **#4 완료**. 크로스계정 조치를 위한 STS AssumeRole 헬퍼 + **회복탄력성 폴백**(실패/서킷-OPEN 시 in-account 크레덴셜로 우아하게 강등). Tier 1 `CircuitBreaker`를 재사용해 리질리언스 재구현 회피. 어댑터-로컬이라 규모 작음.
- Changed: (1) 신규 `src/agents/adapters/aws_session.py` — `assume_role_session(role_arn, *, region, external_id, fallback=True, breaker=None) -> SessionResult`: STS `assume_role`로 타깃 계정 임시 크레덴셜→boto3 `Session` 구성, 실패 시 `_in_account_session`으로 **graceful fallback**(`fallback=False`면 raise). 공유 `_BREAKER`(threshold3/60s)로 반복 실패 시 fast-fail. `_sts_client`/`_in_account_session` 모듈-함수 seam(monkeypatch 주입, moto 불요). `SessionResult(assumed/fell_back)`로 트레이스. `assume_role_arn_from_env()`(`AWS_ASSUME_ROLE_ARN`). (2) `adapters/runtime/aws.py` `_client` **옵트인 소비** — 세션을 `assume_role_session(env-role)`로 구성 후 `.client(_SERVICE)`; env 미설정 시 role=""→in-account, `boto3.client(...)`와 동치(무변경). (3) `docs/ARCHITECTURE.md` 표 row#4 → ✅.
- Verified: 신규 `tests/test_aws_session.py` +9(assume 성공·실패 폴백·`fallback=False` raise·빈 role passthrough(STS 미호출)·external_id 스레딩·반복실패 서킷 OPEN+fast-fail·env 헬퍼·runtime `_client` 옵트인 2종). `make check` → **723 passed, 1 skipped**(714→723). 기존 runtime/circuit_breaker 스위트 무변경 통과=비파괴 확인.
- Blockers: 없음. (Pyright 신규모듈 stale-index 경고는 런타임/pytest 무관.) 실 크로스계정 라이브(2번째 AWS 계정+trust policy)는 사용자 크레덴셜 필요=자율 범위 밖; 어댑터 경로는 stub으로 완결 검증.
- Next: 잔여 Tier 2 = **#3 MCP-over-HTTP 커넥터 + per-tool kill-switch**(앵커 `gateway/mcp_server.py` `TOOL_CATALOG`, intercept-reinject). (선택) 다른 크로스계정 소비자 배선(`deployment/aws.py` CodeBuild, executor SSM).

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 2 #2: agents-as-tools 오케스트레이션 + self-consistency

- Status: Tier 2 최우선 항목 **#2 완료**. 단일-샷 결정론적 라우터(supervisor) 위에 **오케스트레이터 레이어**를 추가 — self-consistency 투표 라우팅 + 전문가-as-tools 체이닝. **비파괴**: 기본 sampler/planner가 결정론적이라 기본 동작은 `Supervisor.handle`과 동일.
- Changed: (1) 신규 `src/agents/ai/orchestration.py` — `route_with_self_consistency()`(sampler를 N회 호출→plurality 투표, `agreement<min_agreement`면 결정론적 `classify_request`로 폴백=reconciliation 게이트 철학, `fell_back` 플래그) + `RouteConsensus`(to_dict/trace_frame) + `PlanStep`/`single_step_planner` + `Orchestrator`(consensus→plan→각 step을 **기존 `Supervisor.handle`로 위임**=specialists-as-tools, 실패 step에서 **short-circuit**, step 간 **shared contextId**) + `OrchestratorOutcome`(SupervisorOutcome를 duck-type). (2) `gateway/a2a_server.py` **옵트인 배선** — 주입 가능 `orchestrator` 파라미터 + `SUPERVISOR_ORCHESTRATION` env 플래그, 활성 시 아티팩트 data에 `consensus`/`steps` 추가(기존 `route`/`trace`의 하위호환 superset), 플래그 미설정 시 기존 경로 무변경. (3) `docs/ARCHITECTURE.md` 레퍼런스 표 row#2 → ✅ 구현완료.
- Verified: 신규 `tests/test_orchestration.py` +12(majority vote·저합의 폴백·기본 sampler 만장일치 회귀가드·multi-step 순서/contextId 스레딩·실패 step short-circuit·게이트웨이 옵트인 stash·기본 경로 consensus 부재·to_dict). `make check` → **714 passed, 1 skipped**(702→714). 런타임 import 확인.
- Blockers: 없음. (Pyright가 신규 모듈 stale-index로 "could not be resolve" 경고하나 런타임/pytest 무관.)
- Next: 잔여 Tier 2 — #3 MCP-over-HTTP 커넥터 + per-tool kill-switch, #4 cross-account STS AssumeRole+fallback(각 별도 세션 권장). (선택) 실 로컬 MLX-Qwen sampler로 self-consistency 라이브 실증(머신러리는 sampler-agnostic이라 옵트인).

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 1 반영(4종) + Vercel 404 수정 + GKE 라이브

- Status: 외부 레퍼런스(aws-samples AWSome AI Gateway) 패턴을 코드로 **Tier 1 4종 반영**. 아울러 Vercel 대시보드 404 진단·수정, GKE 실 provision(어댑터 `node_size`)까지.
- Changed (Tier 1): (1) **Reconciliation gate**(`8f1878f`) — `reconciliation.py`: analyzer의 severity/root_cause가 detector 증거(firing state·metrics·logs·grounding overlap)에 근거하는지 검증, 미근거 시 decision을 **AUTO→APPROVE 강등**(환각 기반 자율조치 차단). `DecisionOutput.reconciliation` 필드+decision handler 배선+파이프라인 surface. 구조적 evidence 없을 땐 vocabulary 체크 skip(on-prem thin-evidence 오탐 방지). (2) **비용 3단계 게이트**(`0a18794`) — `cost_estimator.evaluate_budget()`: OK<SOFT_WARNING(≥80%)<THROTTLE(≥100%·승인필요)<HARD_BLOCK(≥150%), `PLATFORM_MONTHLY_BUDGET_USD`. (3) **회복탄력성**(`de4b92c`) — `circuit_breaker.py`(CLOSED/OPEN/HALF_OPEN, fail-fast+fallback, injectable clock) + webhook `/health/ready`(strict 503) vs `/health`(lenient 200). (4) **비용 서브메트릭**(`6bc541c`) — `deploy_recorder._cost_metrics()`: 트레이스에서 도구별 호출수·reasoning steps·토큰 usage 집계→ACTIVITY `cost_metrics`. `docs/ARCHITECTURE.md`에 레퍼런스 도입 매핑표+Tier 1 완료 표기.
- Changed (기타): **Vercel 대시보드 완전 복구·영구 안정화** — (1) 404 원인=프로덕션 alias(`platform-agent-red`) stale 바인딩 + 매뉴얼 배포가 `.venv-mlx` 100MB+ metallib 업로드 실패 → `.vercelignore` 수정(`3e7762e`)+`vercel --prod` 재배포로 200 복구. (2) **근본원인 확정·영구수정**: `ssoProtection=all_except_custom_domains`(모든 `.vercel.app`에 Vercel 인증) 때문에 canonical URL 302+`-red` git-push flapping → 사용자가 API로 `ssoProtection=null` 해제 → **`platform-agent-men16922s-projects.vercel.app` 안정적 공개 200**(git push에도 안 깨짐). (3) **대시보드 agent tool list 드리프트 수정**(`26586b5`) — `agent-tools.ts`가 백엔드 `AGENT_TOOL_CATALOG`(13개)와 불일치(`deploy_service` 누락·rollback 오분류)→정합(Investigate5/Provision2/Deploy5/Recover1), tsc 통과·라이브. GKE 실 provision(`node_size` `f3e7952`)→즉시 teardown(비용$0).
- Verified: 신규 테스트 +30(reconciliation9+budget9+cb6+readiness2+cost_metrics4). `make check` → **702 passed, 1 skipped**. 실 Vercel canonical URL 200 공개 안정화·대시보드 렌더 확인·GKE 삭제·현재 실시간 과금 $0.
- Blockers: 없음. 잔여 레퍼런스 Tier 2(agents-as-tools·MCP-over-HTTP·cross-account STS)는 supervisor/gateway 리팩터라 규모 커 별도 세션 권장. PROGRESS_LOG 169줄>budget120 → `/tidy-docs` 필요.
- Next: (선택) Tier 2 레퍼런스(새 세션). 외부: Slack App·아티클·대시보드 OAuth 로그인 데모.

## 2026-07-14 — Provision 어댑터 라이브: AKS 실 클러스터 provision→검증→teardown + node_size 지원 추가

- Status: provisioning 어댑터(GKE/AKS)를 **실 클러스터로 라이브 검증**(그간 코드+테스트만). Azure 구독의 기본 VM 크기가 제한돼 create가 실패 → **어댑터에 `node_size` 지원 추가**(실 개선)로 해결 후 AKS 실 provision 성공. teardown까지 어댑터로 실증.
- Changed: `provisioning/base.py` `ProvisionSpec`에 `node_size:str=""` 추가. `azure.py` provision에 `--node-vm-size`(node_size 시), `gcp.py` provision에 `--machine-type`(node_size 시) 스레딩. `test_provisioning_adapters.py` +2(gcp `--machine-type`·azure `--node-vm-size` 스레딩). 제한 구독에서 기본 크기 미가용 시에도 provision 가능해짐.
- Verified: `make check` → (아래 gate). **실 Azure eastus AKS 라이브**: 어댑터 `provision_cluster(approved=True, node_count=1, node_size="Standard_D2als_v7")`→클러스터 생성 성공(k8s 1.35.6, 1 node Ready, Ubuntu 24.04)→`kubectl get nodes` 확인→어댑터 `teardown_cluster(approved=True)`→삭제 완료(list `[]`). billable create는 하네스가 자동차단→사용자 `!`로 어댑터 호출 실행(delete는 미차단). 총비용 ≈$0.03(1노드 ~10분).
- Blockers: 없음. 하네스 자동모드가 billable IaC create를 차단(delete/push는 허용) → 실 create는 사람이 실행하는 설계. GKE create/self-permission 모두 자동차단 확인 → **GKE 실 create는 자율 범위 밖**.
- Next: 없음(Provision 라이브 objective 종결). **GKE는 AKS가 동일 어댑터 경로를 실 클러스터로 실증하여 검증 충족**; preflight 라이브 통과; 실 2차 클러스터 확인은 선택(헬퍼 `scripts/provision_gke_live.py` 준비, 사람이 실행). 전 커밋 origin push 완료.

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
