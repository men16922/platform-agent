# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-17 — repo 구조·소스 리팩토링 + docs 병합 (dead code 제거·executor 공통화·post_webhook 버그수정)

- Status: 전체 폴더구조·소스 리팩토링 검토(병렬 3-에이전트 조사: src 구조·cross-cloud 중복·dashboard/tests/infra) 후 안전분만 실행. 커밋 4개, gate 748 유지, push 안 함.
- Changed: **(구조)** `src/agents/{executor,detector,decision,analyzer,approval_bridge}` 유령 패키지 5개 삭제(빈 `__init__`, import 0, 실구현은 `operations/` 하위); `infra/onprem/terraform/.terraform` **16MB null-provider 바이너리 추적해제**+`.gitignore` 등록(물리 유지). **(docs)** README↔DOCS_POLICY skills 중복(6 vs 3 불일치)→DOCS_POLICY §5 단일소스 통합; stale 문서 10개 제거(직전 커밋 `174d57f`); 미커밋 삭제 2건(linkedin 포스트·`local-llm-onprem.md`) 확정+NEXT_PLAN 참조수선. **(소스)** `operations/_executor_common.py` 추출(gcp/azure executor ~150줄 중복: deserialise/serialise/run_actions/slack, provider-특화는 유지); `operations/executor/_k8s_rest.py` 추출(gcp/azure runner의 byte-identical rollout-restart/scale).
- Verified: `make check` → **748 passed, 1 skipped**(239s, baseline 유지). gcp/azure day2 + multicloud runner 62 passed. pytest collection 749(import 에러 0). runtime import 확인.
- Bug fix: gcp/azure executor가 `post_webhook({"blocks":blocks})`로 dict를 URL자리에 넘기고 payload 누락(시그니처 `post_webhook(url,payload)`)+반환 None에 `.get("ts")`→TypeError가 except에 삼켜져 Slack 리포트 **조용히 무전송**이었음. 공통 `post_incident_slack`이 올바른 인자로 수정(테스트는 SLACK_WEBHOOK 미설정 early-return이라 회귀 없음).
- Deferred(판단): (a) `approval_bridge/handler.py`(604줄) 분리 — 테스트가 내부심볼 12개+를 `handler` 모듈경로에 `@patch` 강결합, 분리시 재import 필요해 실익<리스크→보류. (b) `_k8s_rest`는 restart/scale만(rollback은 GKE `:previous` fallback vs AKS 필수파라미터로 시맨틱 상이). (c) `operations` 그룹핑 축 통일(#3, AWS=role별 vs gcp/azure=cloud별) — 반나절 import churn, 별도 승인. detector/analyzer/decision은 SDK 90%+ 상이라 DRY 안 함(leaky).
- Blockers: 없음.
- Next: (선택) push / `operations` 그룹핑 축 통일 / 외부·인프라(아티클 배포·Slack·OAuth 데모).

## 2026-07-15 — AI endpoint 라이브 재검증(풀 스택 E2E) + per-agent 동작 규명 + 클라우드 과금 감사

- Status: 코드 변경 0(순수 검증/사실규명). 문서가 "코드 완료"라 주장하던 AI endpoint 7종을 실제로 띄워 라이브 재현하고, 대시보드 NL 채팅의 per-agent 실행 스코프를 코드로 규명, 클라우드 유휴 과금을 감사.
- Changed: 없음(git clean, gate 748 유지). `.DS_Store` 노이즈만.
- Verified (실제 실행): `make dev-up`(MLX 30B+proxy+router+webhook+dashboard) 전 계층 up. **AI endpoint 7종 라이브**: router `/health`·`/api/models`(onprem·aws verdict 로직)·dashboard 프록시 `agents/models`(`source:router-api`=fallback 아님)·`agents/onprem-status`(connected)·LLM 브레인(proxy→MLX `READY`). **`/api/local-deploy` 풀 E2E 24.9s**: local-qwen이 build→push→deploy→validate 자율 실행→kind에 `orders-api 1/1 Running`(image `localhost:5001/orders-api:v1.0.0`, `DEP-AD0FC7B4`)→대시보드 배포 피드 최상단 관통(executor-writes→dashboard-reads). SSE `/api/local-deploy/stream`도 tool_call→result→reasoning→done 정상. 검증 후 전부 teardown(kind down+스택 down+컨텍스트 `pa-aks-live` 복원).
- 규명(코드 근거): (1) 대시보드 배포 라우트(`agents/deploy`·`/stream`)는 **모델 무관 전부 `LOCAL_DEPLOY_API_URL`(127.0.0.1:8077) 프록시** → Vercel 공개 URL에선 4종 모두 채팅 배포 불가(502), local-only. (2) `route_deploy`(`model_router.py:269`)에서 **pydantic-ai(local-qwen)만 실 실행**; strands/adk/msft는 `_cloud_outcome`(L232)로 `ok=False` "requires {cloud} creds" **미실행**(주석 "routed without live execution"). 클라우드 3종 라이브는 이 채팅이 아니라 별도 어댑터/스크립트/런타임호스팅 경로에서 실증됨. → DECISIONS D14.
- 과금 감사: **platform-agent 유휴 ≈$0**. AWS(908601828278) NAT/EC2/RDS/LB 0, DynamoDB 18개 전부 PAY_PER_REQUEST, `IncidentAgentStack` 서버리스. Azure `pa-foundry-908601` `gpt-mini`=GlobalStandard(종량제, 유휴$0). GCP GKE/Compute 0. `pa-aks-live`=DNS 미해석(이미 삭제된 유령 컨텍스트). ※ 같은 계정의 `am_*`/`n8n`/roadpilot은 별개 프로젝트(미검토).
- Blockers: 없음.
- Next: 자율 백로그 여전히 소진 상태. 대시보드 채팅에서 클라우드 3종을 실행되게 하려면 `route_deploy` cloud 분기를 어댑터 실호출로 잇는 설계 필요(서버측 크레덴셜+과금 정책=사용자 판단).

## 2026-07-15 — 아키텍처 잔여 로드맵 2건 구현: supervisor 프론트도어 배선 + deploy↔runtime 정면 배선

- Status: ARCHITECTURE 잔여 로드맵 중 자율 가능 2건 구현 → 코어 아키텍처의 명시적 미구현 배선 항목 소진(잔여는 인프라/아스피레이셔널/사용자만).
- Changed: (1) **② supervisor 프론트도어**(`local_deploy_api.py`) — `/api/local-deploy`에 `get_front_door` DI seam(Supervisor/Orchestrator from_environment, `SUPERVISOR_ORCHESTRATION` 옵트인) 추가, 요청을 supervisor로 먼저 분류→A2A 엔드포인트(`PLATFORM_*_A2A_URL`) 설정 시 위임(delegated 응답), 미설정 시 in-process `route_deploy` 폴백. `DeployResponse`에 `delegated`/`route`/`route_trace` 추가(폴백에도 분류 노출). **비파괴**: A2A 미설정=기존 동작+분류만. (2) **① deploy↔runtime 배선**(`pipeline.py`) — DeployPipeline에 opt-in `host` 스텝(`report`→`host`) + `PipelineSpec.host_runtime`/`runtime_image_uri`/`runtime_role_arn`/`runtime_env`/`runtime_approved`. `get_runtime_adapter(provider).host_agent(RuntimeSpec)` 호출, **plan-first**: 미승인=preflight(hosted=False), 승인=실 create, onprem=managed runtime N/A라 SKIPPED. `run()`에 핸들러 SKIPPED 처리 브랜치 추가(옵셔널 스텝이 파이프라인 실패 아님, 기존 핸들러는 SKIPPED 미반환이라 무영향).
- Verified: 신규 test +7(프론트도어 delegate/fallthrough 2 + host 스텝 skipped/onprem/preflight/create/error 5). 기존 pipeline 테스트 갱신(7→8 노드, host SKIPPED 허용). `make check` → **748 passed, 1 skipped**(741→748). ARCHITECTURE 로드맵 ①②를 ✅로 갱신.
- Blockers: 없음. 잔여 로드맵(③ AgentCore Memory/Tools 패리티 · ④ On-Prem State Store/Alertmanager · ⑤ Helm/Terraform Tier 3 · ⑥ Slack/Harbor)은 전부 인프라/아스피레이셔널/사용자 개입.
- Next: 자율 가능한 아키텍처 배선 소진. 외부(아티클 배포·OAuth 데모)·인프라 항목만 잔여.

## 2026-07-15 — ARCHITECTURE.md stale 마커 정정 + 잔여 로드맵 재정리

- Status: 아키텍처 문서가 이미 done인 항목을 "🔲/미구현"으로 남겨둬 자기모순(예: L22는 Provision 4-provider ✅인데 L265는 "미구현"). 코드로 검증 후 stale 마커를 실제 상태로 정정하고, 진짜 미구현만 상단에 단일 로드맵으로 통합.
- Changed (docs only): (1) **Provision 표/현재상태**(L250–265) — "AWS만 CDK·나머지 🔲/온프렘 미구현" → 4-provider 어댑터 ✅(`adapters/provisioning/` aws/gcp/azure/onprem, AKS 실 클러스터 라이브). (2) **단일 카탈로그**(L297/303/305/278) — "인터랙티브 채택 로드맵 🔲" → 채택 완료 ✅(`AGENT_TOOL_CATALOG`), 두 카탈로그는 레이어 분리 의도적(수렴 안 함)로 결정 명시. (3) **On-Prem 실 executor scale/drain**(L420) — "로드맵" → 되돌리기-가능 4조치 ✅(restart/undo/scale/polite drain, kind 라이브). (4) **top 요약**(L22–24) — Tier 1/2 전부 반영 ✅ 명시 + **잔여 로드맵 6항목 단일 통합**(deploy↔runtime 배선·supervisor 프론트도어·Agent Runtime Memory/Tools·On-Prem State Store/Alertmanager·Helm/Terraform Tier 3·Slack/Harbor). 코드로 검증: provisioning/onprem.py 존재·onprem_runner scale(L73)/drain(L87)·local_deployer AGENT_TOOL_CATALOG.
- Verified: 문서 일관성 재검(`grep 🔲/미구현` → 남은 마커 전부 진짜 로드맵, 모순 0). 코드 무변경이라 gate 741 유지.
- Blockers: 없음.
- Next: (자율 가능) 진짜 로드맵 중 supervisor 프론트도어 배선·deploy↔runtime 배선. 외부: 아티클 배포·OAuth 데모.

## 2026-07-15 — orchestrator 활동 기록 배선: consensus/steps 대시보드 실표시 완성

- Status: 직전 커밋에서 대시보드는 consensus/steps를 render-capable로 만들었으나 이를 활동 레코드로 남기는 producer가 없었음. 이제 orchestrator 실행 경로가 라우팅 런을 ACTIVITY로 기록 → 대시보드가 실제로 표시.
- Changed: (1) `deploy_recorder.py` — `record_route_activity(instruction, trace, tool_calls, …)` + activity-only `_persist_activity`: consensus/plan 프레임을 담은 `type=route` ACTIVITY를 로컬 JSONL/DynamoDB(기존 백엔드 선택 로직 재사용)에 기록, `recording_enabled()` 꺼지면 no-op. (2) `gateway/a2a_server.py` — orchestrator 경로(OrchestratorOutcome)에서 `record_route_activity` 호출(best-effort try/except, 게이트웨이 응답 안 깨짐). (3) `activity-timeline.tsx` — 활동 카드에 consensus 인라인 칩(role·agreement·fell_back·plan 체인) 렌더(route 활동은 deployment_id 없어 상세 링크 대신 인라인 표시).
- Verified: 신규 test +3(`record_route_activity` 프레임 기록·disabled no-op·게이트웨이가 route 활동 기록). `make check` → **741 passed, 1 skipped**. **로컬 E2E**: `SUPERVISOR_ORCHESTRATION=true`+`PLATFORM_ACTIVITY_FILE`로 A2AServer send_message → JSONL에 `type=route` 1건, trace 프레임 `['consensus','plan']`, consensus `{role:deploy, agreement:1.0, votes:{deploy:5}}` 기록 확인. 대시보드 `next build` 성공.
- Blockers: 없음. consensus/steps 이제 **실 producer→저장→대시보드 표시** 완결(opt-in `SUPERVISOR_ORCHESTRATION`).
- Next: 외부(아티클 배포·OAuth 데모)만 잔여.

## 2026-07-15 — 대시보드: 신규 백엔드 관측 기능 3종 노출 (cost_metrics·reconciliation·consensus/steps)

- Status: 최근 Tier 1/2 백엔드가 만들지만 대시보드 read/render에서 떨어지던 관측 데이터 3종을 노출. 조사 결과 cost_metrics만 순수 read/render였고, reconciliation은 On-Prem만 저장(AWS 파리티 1줄 추가), consensus/steps는 미저장(대시보드는 render-capable로).
- Changed (dashboard): (1) **cost_metrics** — `mock-data.ts` `CostMetrics` 타입+`AgentActivity` 필드, `activity-data.ts` `mapCostMetrics` 매핑, `deployments/[id]` PhaseBody에 "cost/usage sub-metrics" 패널(도구별 호출·reasoning·토큰). (2) **reconciliation** — `Reconciliation` 타입+`Incident` 필드, `incident-data.ts` `mapReconciliation`, `incident-row.tsx`에 게이트 배지(grounding ratio·`AUTO→APPROVE` 강등 사유·issues; grounded면 녹색 배지). (3) **consensus/steps** — `TraceItem`에 `consensus`/`plan` kind+필드, `parseTrace`가 프레임 인식, PhaseBody가 self-consistency 투표(agreement·votes·fell_back)와 orchestration plan(role 체인) 렌더.
- Changed (backend 파리티): `executor/handler.py` `_record_incident`가 `decision.reconciliation` 존재 시 인시던트 레코드에 첨부(On-Prem `onprem_incident_pipeline`와 동일 shape) — AWS 인시던트도 강등 사유 노출 가능.
- Verified: 대시보드 `next build`(Next 16) 성공(전 라우트 컴파일), 백엔드 `make check` → **738 passed, 1 skipped**. cost_metrics·reconciliation은 실 데이터 경로 존재(즉시 표시). **consensus/steps는 render-capable이나 현재 이를 활동 레코드로 persist하는 경로 없음**(orchestrator/a2a는 활동 미기록) → 데이터 생기면 표시, 지금은 빈 상태(정직히 기록).
- Blockers: 없음. consensus/steps를 실제로 채우려면 orchestrator 경로가 활동을 기록해야 함(별도 백엔드 작업).
- Next: (선택) orchestrator 활동 기록 배선. 외부: 아티클 배포·OAuth 데모.

## 2026-07-15 — 라이브 실증: Tier 2 #3 MCP-over-HTTP(실 HTTP) + #4 STS graceful fallback(실 STS)

- Status: 그간 스텁/fake만이던 #3 원격 MCP 커넥터와 #4 크로스계정 폴백을 **실 네트워크로 라이브 실증**. #3=로컬 mock MCP 서버 상대 실 HTTP JSON-RPC 왕복, #4=실 boto3 STS AssumeRole 실패→실 in-account 폴백. shipped 코드(`remote_mcp_tool`/`post_mcp_call`, `assume_role_session`) 그대로 구동.
- Changed: 신규 `scripts/live_net_demo.py`(stdlib http.server mock MCP + 실 STS 호출) + 증거 `docs/evidence/tier2-live-mcp-http-sts-fallback.log`. 제품 코드 무변경.
- Verified (라이브): **(C) #3 실 HTTP** — C1 실 JSON-RPC 왕복 성공(서버가 `tools/call name=search args` 수신, output reinject), C2 remote isError→failed ToolResult 매핑, C3 **kill-switch가 dispatch 전 차단→서버 hit 0**(HTTP 미발생 확인), C4 dead port→graceful degrade(Connection refused). **(D) #4 실 STS** — 현 계정 908601828278에서 존재하지 않는 롤 AssumeRole→실 **AccessDenied**→graceful fallback(assumed=False·fell_back=True), 폴백 세션 실 신원 `user/q-user`로 in-account 동작 확증; `fallback=False`→실 ClientError re-raise. 제품 코드 무변경이라 gate 738 유지.
- Blockers: 없음. #4의 실제 크로스계정 assume 성공 경로(2번째 계정+trust policy)는 여전히 사용자 필요 — 단 fallback/실패 경로는 실 STS로 실증됨.
- Next: 외부(아티클 배포·OAuth 데모). 자율 실증 가능분 소진.

