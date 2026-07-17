# STATUS — platform-agent

최종 갱신: 2026-07-17

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 현재 요약

- 제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`.
- Operations 4단계(detect→analyze→decide→execute) 파이프라인 런타임 동작.
- 3-cloud AI Agent 실호출 완료: Bedrock Claude + Vertex AI Gemini 3.5 Flash + Azure OpenAI GPT-5.4.
- Capability-based runbook schema 구현 (cloud-neutral execution steps).
- overnight-harness 기반 자동 개발 루프 구성 완료 (5 engine 지원).
- 4 provider 코드 완비: AWS / GCP / Azure / On-Prem.

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **829 passed, 1 skipped** (2026-07-17, 263.50s) — **레퍼런스 #7-a On-Prem Helm 차트+이미지**: `infra/helm/platform-agent/`(webhook 기본 on·router opt-in·최소권한 RBAC 4조치 동사 열거·drain 별도 ClusterRole 기본 off·PVC 단일-writer·env×substrate values kind/k3s) + `infra/onprem/Dockerfile`(kubectl 내장 2엔트리포인트). 가드 +6(helm lint·RBAC `"*"` 금지·프로브 분리 등, helm 미설치 시 skip). **이미지 실빌드(881MB)+컨테이너 스모크**(`/health`·`/health/ready` 200). 부산물: **`pyproject.toml` optional-dependencies PEP 621 위반 latent 버그 수정**(이미지 빌드가 표면화). **kind 라이브 실증 완료(동일자)**: 전용 pa-helm 클러스터 helm install→pod Ready(strict readiness in-cluster)→RBAC can-i allow/deny 분리 실증→Alertmanager→P2 승인 게이트→execute→incident→PVC 영속성(pod 재시작 생존)→전량 teardown·GKE 컨텍스트 불가침. 증거 `docs/evidence/helm-kind-live-install.log`. 잔여=#7-b Terraform 모듈(클라우드).
- `make check` (pytest) → **823 passed, 1 skipped** (2026-07-17, 230.48s) — **⑦ 라이브 모델 스윕 실 실행 완료(로컬 MLX, spend $0) → 승인 큐 8항목 전부 완료(코드+실행)**: `scripts/live_model_sweep.py`가 shipped `live_router_factory`+`run_sweep`을 실 mlx_lm.server 상대로 160 라이브 호출(2모델×2 effort×20케이스×프롬프트 v1/v2, backstop 발화 0, resume 병합 실증). **라이브 런이 `_classify_prompt` 결함 표면화**(v1이 teardown을 provision으로 기술 → teardown→deploy cascade 모순, 전 config 동일 adversarial 2건 미스) → v2 재작성 → 전 config 개선(7B/low 0.80→**1.00**·30B 0.80→0.95) → 회귀 가드 +1. **증거 기반 선택: Qwen2.5-Coder-7B @ temp0 = 20/20·0.20s/success — 30B보다 정확·빠름**(정적 "큰 모델" 주석 반증). 증거 `docs/evidence/model-sweep-live.log`.
- `make check` (pytest) → **822 passed, 1 skipped** (2026-07-17, 261.76s) — **⑦ 라이브 어댑터 코드 완료**: `model_sweep.live_router_factory(call_model, backstop=)`(모델 응답→role 파싱·latency 측정·미파싱/실패 시 결정론 백스톱, `run_sweep` 드롭인). 모델 호출은 주입식이라 오프라인 테스트(+3).
- `make check` (pytest) → **819 passed, 1 skipped** (2026-07-17, 243.21s) — **승인된 실행 큐 소진(사용자 "전부 다"): ⑧-1/2/3 + ⑨ A/B 7묶음**: ⑧-3 `ROLE_ALLOWED_ACTIONS` 위임 힌트+`action_sink_grader` 단일소스 · ⑨A-1/A-2 SSE `id:`dedup·`ready`센티넬·heartbeat · ⑧-1 `metadata.task` 구조화 디스크립터 · ⑨B-1 신규 `memory_tier.py`(signature·scrub·distill·MemoryStore) · ⑧-2 `Supervisor(confidence_router=)` 옵트인 저-confidence 게이트 · ⑨B-2 recall+`augment_instruction` 옵트인 `memory=` seam(조언적) · ⑨B-3/A-3 `consolidate`/`dominant_failures`+SSE `agent`필드. 전부 비파괴(옵트인 DI·additive·SSE 하위호환), +23 test(796→819). **잔여=⑦ 라이브 스윕(실 API 과금·사용자 게이트)**.
- `make check` (pytest) → **796 passed, 1 skipped** (2026-07-17, 231.96s) — **⑧ 안전 서브셋+⑧-4: A2A 위임 하드닝**: `supervisor.sanitize_instruction`(control-char strip[tab/newline 유지]·4000자 cap·적용 transform trace) + `handle` 아웃바운드 배선(분류는 원문 유지)·`trace` 타입주석 정정. **⑧-4(완료)**: `ARCHITECTURE.md`에 TOOL→SKILL→SUBAGENT smell-test + 위임 안전 불변식 명문화 + 회귀 가드(supervisor는 mutating provision/deploy를 in-process 실행 안 함, 반드시 A2A 위임). 계약/동작 변경 3건(구조화 페이로드·저-confidence 게이트·최소권한 힌트)은 `docs/plans/a2a-delegation-hardening.md`=**승인 대기**. 비파괴 +6 test(790→796).
- `make check` (pytest) → **790 passed, 1 skipped** (2026-07-17, 218.92s) — **⑦ 오프라인 모델 스윕 스캐폴드**: 신규 `src/agents/ai/model_sweep.py`(eval_harness 위 증분, 실 API/과금 0). `SweepConfig`(model×thinking×effort)·`grid`·`run_sweep`(config별 dataset 채점→**cost_per_success/seconds_per_success** headline, `trials` self-consistency, **resumable** done-dedup)·`SweepPoint`(0성공=inf, to/from_dict 영속)·`rank/best/scoreboard`. LLM 백엔드=`router_factory` 주입(테스트=결정론 mock), 라이브 배선+실 spend=사용자 게이트. +11 test(779→790).
- `make check` (pytest) → **779 passed, 1 skipped** (2026-07-17, 232.74s) — **⑤ eval 하네스 성숙(선언적 멀티-grader 스코어카드)**: 단일-judge `grade()`/`EvalReport` 경로 무변경 위에 비파괴 증분 — 선언적 `Grader`(name+`kind:code|judge`)로 명명 메트릭 다중(role/budget/action_sink/judge), `Verdict` 3-상태(PASS/FAIL/**PASS_SLOW**=정답이나 예산초과), **action-sink grader**(read-only role이 mutate=FAIL, per-role allowed 정책=blast-radius 안전), 리치 `Observation`(decision+latency+actions)·`observing()` 브리지, `Scorecard.delta/regressions`(pinned-baseline 회귀 diff), `score(trials=N)` majority vote(self-consistency 재사용). +12 test(767→779).
- `make check` (pytest) → **767 passed, 1 skipped** (2026-07-17, 227.82s) — **⑥ eval 데이터셋+judge 하드닝**: `ROUTING_EVAL_SET` 13→**20**(카테고리 균형 + **adversarial 네거티브 5**로 precision 채점). eval가 실 라우팅 over-trigger 갭 2건 표면화("Deploy the observability stack"→KAGENT 오분류·"Investigate why the terraform apply failed"→PROVISION 오분류) → `classify_request`를 first-substring-wins에서 **precedence**(진단동사>provision>delivery-guarded 명사, 과광범 `observability` 트리거 제거)로 재설계 → 회귀가드로 전환(기존 supervisor/orchestration classify 단언 회귀 0). judge 반-관대: `_build_judge_prompt` 재작성(read-only/mutating 경계·FAIL-when-unsure) + `calibration_probe`(파괴적 provision→read-only kagent canary; PASS/에러/미파싱=관대·불신) + `llm_judge(calibrate=True)` 강등 + 빈문자열/"모름" 결정론 백스톱 테스트. +9 test(758→767). 발견→수정→가드 루프 재실증.
- `make check` (pytest) → **758 passed, 1 skipped** (2026-07-17, 233.81s) — **eval 하네스 스파이크(④)**: 신규 `src/agents/ai/eval_harness.py`(클라우드-중립·오프라인 decision-quality 평가: 라벨 데이터셋+injectable Router/Judge, `llm_judge`=LLM-as-judge with 결정론 백스톱, `EvalReport` 회귀 가드, 빌트인 `ROUTING_EVAL_SET`) +10 test. Google Agent 생태계 3자료(ADK 2.0·A2A·agents-cli) 대조의 유일 코드 후속. 결정론 classifier 스파이크에서 실제 라우팅 갭 2건(cluster-creation 동사 미커버) 표면화 → `classify_request` 수정(cluster+생성동사 조합, 회귀 0) → eval set 13/13, 갭=회귀가드. 발견→수정→가드 루프 실증. 나머지 후속 ①아티클 포지셔닝(EN+KO 수렴 섹션)·②context 격리 감사(델타 아님)·③버전 트래킹(A2A stdlib-only 규명)은 코드 무변경.
- `make check` (pytest) → **748 passed, 1 skipped** (2026-07-17) — **repo 구조·소스 리팩토링(런타임 동작 무변경)**: 유령 패키지 5개 삭제(`executor`/`detector`/`decision`/`analyzer`/`approval_bridge`, import 0)·`.terraform` 16MB 추적해제 + `operations/_executor_common.py`(gcp/azure executor ~150줄 중복 추출)·`_executor/_k8s_rest.py`(runner restart/scale 공유) + **post_webhook 오호출 버그 수정**(gcp/azure Slack 리포트 무전송 → 정정). docs: README↔DOCS_POLICY skills 병합·stale 10개 제거. baseline 수치 유지, 커밋 4개 미푸시.
- **AI endpoint 라이브 재검증(2026-07-15, 풀 스택 E2E, 코드 무변경)** → `make dev-up` 후 endpoint 7종 라이브: router `/health`·`/api/models`(verdict)·대시보드 프록시 `agents/models`(`source:router-api`)·`onprem-status`(connected)·LLM 브레인(MLX 30B). **`/api/local-deploy` 풀 E2E 24.9s**(local-qwen→build/push/deploy/validate→kind `orders-api 1/1 Running` `DEP-AD0FC7B4`→대시보드 피드 관통), SSE 스트림 정상. 검증 후 전량 teardown(유휴 $0 복원). **규명(D14)**: 채팅 배포는 모델 무관 로컬 백엔드(127.0.0.1) 프록시라 **Vercel에선 4종 전부 502**; `route_deploy`는 local-qwen만 실행, 클라우드 3종은 `_cloud_outcome` 미실행(라이브는 별도 어댑터/스크립트/런타임호스팅 경로). **과금 감사**: platform-agent 유휴 ≈$0(AWS NAT/EC2/RDS/LB 0·DynamoDB 18개 PAY_PER_REQUEST·서버리스 스택 / Azure Foundry gpt-mini=종량제 / GCP 0 / kind teardown).
- `make check` (pytest) → **748 passed, 1 skipped** (2026-07-15) — **아키텍처 잔여 로드맵 2건 구현**: ② supervisor 프론트도어(`local_deploy_api` `/api/local-deploy` 분류→A2A 위임/in-process 폴백, 비파괴) + ① deploy↔runtime 정면 배선(DeployPipeline opt-in `host` 스텝, approval-gated preflight/create, onprem skip). +7 test. 코어 아키텍처 배선 로드맵 소진(잔여=인프라/아스피레이셔널/사용자).
- `make check` (pytest) → **741 passed, 1 skipped** (2026-07-15) — **대시보드 신규 관측 3종 노출 + orchestrator 활동 기록 배선**: `cost_metrics`(배포상세 패널)·`reconciliation`(인시던트 강등 배지, AWS `_record_incident` 파리티)·`consensus/steps`(activity trace). `record_route_activity`가 orchestrator 라우팅 런을 `type=route` ACTIVITY(consensus/plan trace)로 기록→대시보드 표시. 대시보드 `next build` 성공. 로컬 E2E로 route 활동 기록 확인.
- **라이브 실증(2026-07-15, 실 HTTP + 실 STS)** → `scripts/live_net_demo.py`, 증거 `docs/evidence/tier2-live-mcp-http-sts-fallback.log`. **(C) #3 MCP-over-HTTP**: 로컬 mock MCP 서버 상대 실 JSON-RPC 왕복 성공 · remote isError 매핑 · **kill-switch가 dispatch 전 차단(서버 hit 0, HTTP 미발생)** · dead port→graceful degrade. **(D) #4 STS graceful fallback**: 실 boto3 STS로 존재X 롤 AssumeRole→실 AccessDenied→in-account 폴백(신원 `user/q-user` 확증), `fallback=False`→실 ClientError re-raise. 제품 코드 무변경(gate 738 유지).
- **라이브 실증(2026-07-15, 실 MLX Qwen3-Coder-30B)** → `scripts/live_tier2_demo.py`, 증거 `docs/evidence/tier2-live-selfconsistency-reconciliation.log`. **(A) #2 self-consistency**: 실 LLM sampler(temp1.0)→shipped `route_with_self_consistency`→실 consensus("Deploy…"5/5 deploy·"cluster off…"5/5 kagent). 8개 모호 프롬프트 프로브 전부 7/7 만장일치→이 30B는 결정적이라 fallback 라이브 미발화(강한 모델에선 confidence signal, fallback은 유닛 커버). **(B) reconciliation 게이트**: TLS만료 실 인시던트에서 grounded LLM 분석(ratio 0.62)→AUTO 유지 / hallucination LLM 추측(ratio 0.08)→**AUTO→APPROVE 강등**. 실 환각을 결정론 게이트가 포착.
- `make check` (pytest) → **738 passed, 1 skipped** (2026-07-15) — **Tier 2 #4 크로스계정 소비자 배선**: `deployment/aws.py`(CodeBuild)·`executor/handler.py`(SSM primary+failover `_ssm_client`)이 `assume_role_session(env-role)` 소비(env 미설정=in-account 무변경), +2 test. + 종합 아키텍처 아티클 `docs/post/platform-agent-architecture.md`.
- `make check` (pytest) → **736 passed, 1 skipped** (2026-07-15) — **레퍼런스 Tier 2 #3: MCP-over-HTTP 커넥터 + per-tool/글로벌 kill-switch → Tier 2 전체 완결**(#2·#3·#4). `mcp_server.py`에 `remote_mcp_tool()`(원격 MCP 서버 JSON-RPC `tools/call` intercept→reinject, 전송실패 degrade) + `MCPServer` kill-switch(`call_tool` 게이트, `disable_tool`/`set_kill_switch` + `MCP_DISABLED_TOOLS`/`MCP_KILL_SWITCH` env). 원격 커넥터도 동일 kill-switch 지배. +13 test, 비파괴(기존 gateway 29건 무변경). ARCHITECTURE 표 row#3 ✅.
- `make check` (pytest) → **723 passed, 1 skipped** (2026-07-15) — **레퍼런스 Tier 2 #4: cross-account STS AssumeRole + graceful fallback**(신규 `adapters/aws_session.py`, +9 test). `assume_role_session(role_arn, fallback=True)`: STS assume_role→타깃 계정 세션, 실패/서킷-OPEN 시 in-account 크레덴셜로 우아하게 강등(Tier 1 `CircuitBreaker` 재사용). `runtime/aws.py` `_client`가 `AWS_ASSUME_ROLE_ARN` 옵트인 소비(미설정=무변경). ARCHITECTURE 표 row#4 ✅.
- `make check` (pytest) → **714 passed, 1 skipped** (2026-07-15) — **레퍼런스 Tier 2 #2: agents-as-tools 오케스트레이션 + self-consistency**(신규 `orchestration.py`, +12 test). `route_with_self_consistency`(N-샘플 majority vote·저합의 시 결정론적 `classify_request` 폴백=reconciliation 철학) + `Orchestrator`(consensus→plan→각 step을 기존 `Supervisor.handle`로 위임=specialists-as-tools·실패 short-circuit·shared contextId). `a2a_server` 옵트인 배선(`SUPERVISOR_ORCHESTRATION`, 기본 무변경). ARCHITECTURE 표 row#2 ✅.
- `make check` (pytest) → **702 passed, 1 skipped** (2026-07-15) — **AWSome AI Gateway 레퍼런스 Tier 1 반영(4종, +30 test)**: (1) **Reconciliation gate**(`reconciliation.py`, analyzer 결론 미근거 시 AUTO→APPROVE 강등, decision handler 배선), (2) **비용 3단계 게이트**(`cost_estimator.evaluate_budget`, OK/SOFT_WARNING/THROTTLE/HARD_BLOCK), (3) **회복탄력성**(`circuit_breaker.py` + webhook `/health/ready` 503 vs `/health` 200), (4) **비용 서브메트릭**(`deploy_recorder._cost_metrics`). `docs/ARCHITECTURE.md`에 도입 매핑표. **Vercel 대시보드 영구 안정화**: `ssoProtection` 해제 → canonical URL `platform-agent-men16922s-projects.vercel.app` 공개 200(git push 무관). **대시보드 agent tool list** 백엔드 카탈로그(13개)와 정합(`26586b5`).
- `make check` (pytest) → **672 passed, 1 skipped** (2026-07-14) — **Provision 어댑터 `node_size` 지원**(GKE `--machine-type`/AKS `--node-vm-size`, 제한구독 대응, +2 test) + **AKS 실 클러스터 라이브**(어댑터 provision k8s 1.35.6 1노드 Ready→teardown). GKE preflight 라이브(create는 하네스 자동차단, AKS가 동일 패턴 실증). 전 커밋 origin push 완료(HEAD `6ad7f82`).
- `make check` (pytest) → **670 passed, 1 skipped** (2026-07-14) — **Agent Runtime 호스팅 어댑터 3종**(신규 `adapters/runtime/`: AWS AgentCore(boto3)·GCP Agent Engine(vertexai)·Azure Foundry(azure-ai-projects **v2**), plan-first/approved-gated·읽기전용 preflight·teardown 승인 강제, +21 test). **3/3 클라우드 실 배포 라이브 E2E 완결**: 어댑터 create→READY/DEPLOYED/v1→invoke/query/Responses(실 Claude/Gemini/gpt-5.4-mini 응답)→teardown, 즉시 삭제(각 <$0.50). **azure 어댑터 v1→v2 결함 수정**(설치 SDK 2.3.0 불일치→재작성). 패키징/문서: `infra/agentcore/`(arm64)·`infra/agentengine/`(custom-template)·`infra/foundry/README.md`.
- `make check` (pytest) → **649 passed, 1 skipped** (2026-07-14) — **provisioning 어댑터 4-provider parity**(신규 GCP/Azure GKE·AKS: plan-first/approved-gated·읽기전용 preflight·teardown 승인 강제·tool preflight-only, +13 test) 포함.
- `make check` (pytest) → **636 passed, 1 skipped** (2026-07-14) — On-Prem 실 executor **scale**(양수 타깃, kind 2→5 라이브) + **polite drain**(--force 없음·PDB 존중, 3노드 kind 라이브 재배치·아웃티지0) + 인터랙티브 에이전트 **단일 카탈로그**(drift-0 불변식) + A2A Phase 2/PROVISION 격리 + On-Prem PATH B webhook/승인 게이트/인시던트 스토어 포함.
- **On-Prem PATH B webhook + Approval Flow 라이브 스모크(2026-07-14)** → `uvicorn onprem_webhook_api:app :8078`. `POST /webhook/alertmanager`가 in-process 4-step(detect→analyze→decide→execute) 실행; Guardian 게이팅 **P1=즉시 실행·P2=parking·P3=알림만**. P2 라이브 루프: pending_approval→`GET /pending`→`POST /approve/{id}`(decision 재생 실행)→approved+incident_id. 완전 오프라인.
- **대시보드 On-Prem 연동(2026-07-14)** → Incidents 페이지 (1) "Pending Remediation Approvals"가 AWS+On-Prem(webhook `/pending`) **hybrid 병합**(source 배지)·Approve/Reject 소스별 SFN/webhook 라우팅, (2) **인시던트 타임라인**도 On-Prem 인시던트(webhook `/incidents`, offline 스토어 `onprem_incidents`)를 hybrid 병합(ON-PREM 배지). `tsc` 0·`next build` 성공; `next start`+webhook로 승인 카드·타임라인 인시던트 렌더 헤드리스 실증(INC-1121DAB7).
- **On-Prem 실 executor(2026-07-14)** → `onprem_runner`가 기본 로그-only, `ONPREM_EXECUTOR_LIVE=true` 시 실 kubectl. 되돌리기-가능 **4조치**: `rollout restart`/`undo` + **`scale --replicas=N`**(양수 타깃일 때만; scale-to-0=셧다운 가드) + **polite `drain <node>`**(`--force`·`--delete-emptydir-data` 미사용 → PDB 존중·데이터손실 방지, NodeName 없으면 log-only). **실 kind 라이브 실증**: restart→파드 교체, scale 2→5(5/5), **drain→노드 cordon+파드 재배치·deployment 4/4 유지(아웃티지0)**. 공격적 force-drain만 사람 몫. 기본 OFF라 프로덕션 안전.
- **단일 도구 카탈로그(2026-07-14)** → (1) **게이트웨이**: `TOOL_CATALOG`에서 `MCP_TOOLS`(discovery)+`_tool_map`(dispatch) 파생. (2) **인터랙티브 `local_deployer`**: `AGENT_TOOL_CATALOG`에서 `ALL_OPS_TOOLS`(dispatch)+시스템프롬프트 `## Tools` 인벤토리(discovery) 파생, 프롬프트↔등록 drift-0 불변식 테스트. 두 카탈로그는 레이어 구분(raw kubectl/docker MCP vs 어댑터-백드 에이전트 도구)이라 별도 유지.
- **A2A Phase 2 라이브 E2E(2026-07-14)** → 실 kagent 0.9.11 에이전트(local MLX Qwen 30B) 대상 supervisor HTTP 카드 discovery→skill 매칭→JSON-RPC 위임→실 `k8s_get_resources` 도구 진단 반환. 증거: `docs/evidence/a2a-phase2-live-e2e.log`.
- `make check` (pytest) → **600 passed, 1 skipped** (2026-07-12) — AI Model Router / Pydantic AI On-Prem 에이전트 / MLX proxy / deploy recorder(+cascade) / ops_tools / provisioning 어댑터 테스트 포함
- **LinkedIn 데모 비디오 편집(2026-07-12)** → `docs/post/local-onprem.mov` 원본 영상을 18.2초(1.0MB)로 구간 및 배속(타임랩스) 편집하고, 각 7개 주요 구간의 자막(Terraform 등 실제 실행 매핑)을 영상 하단에 병합한 `local-onprem-edited.mp4` 제작 완료.
- **배포 추적 IA 정리(2026-07-12)** → activity에 `type`(provision/deploy)·`cluster`(연결키)·`environment`(provider와 분리) 저장; 대시보드 **Provisioning/Deployments/History** 3분리 + **통합 중첩 상세**(provisioning⊃deployments); 롤백 **단일-row 승계**, **cluster teardown→deploy cascade**, 자연어 rollback/teardown도 동일 라우팅; `make dev-up` 한 방 기동. tsc0+next build 성공, `/provisioning`·`/history` 200. **라이브 실증 완료(2026-07-13, 자연어 4스텝 브라우저 end-to-end)**.
- **On-Prem 오프라인 완결(2026-07-12)** → Local Qwen **7B**로 NL provision→deploy→validate **~39s** 자율 실증; `deploy_recorder` **로컬 JSONL** 기록 + 대시보드 **hybrid**(AWS DynamoDB + On-Prem JSONL 병합) read; `/api/local-rollback`로 **app 롤백(rollout undo v2→v1)·cluster 롤백(teardown)** 실증. `mlx_qwen_tool_proxy`가 7B의 ```json/Hermes tool-call 파싱, `deploy_service` 복합툴로 LLM 왕복 축소.
- **범용 On-Prem Ops 에이전트** → provision(2)+deploy(5)+investigate(5) 12도구, reasoning+tool SSE 스트리밍, "list pods" 질의는 진단만 수행 확인
- **On-Prem Provision(① 역할)** → Terraform(kind) IaC `validate/plan` green + Ansible(k3s) 실 Multipass VM 적용: k3s v1.31.4 node Ready, 재실행 idempotent(`changed=0`); `provision_cluster`/`teardown` 에이전트 도구
- **관측성** → 배포 상세 페이지 `/deployments/[id]`(reasoning/tool args·result/summary) + DynamoDB trace 기록
- **kagent + local Qwen** → kind Pod→`host.docker.internal:18091/v1` OpenAI-compat ModelConfig 적용, `k8s-agent` A2A JSON-RPC 진단 task가 tool 결과 반환까지 실증.
- **Supervisor + A2A** → 자연어 요청을 provision/deploy/kagent로 분류하고 Agent Card discovery/skill match 후 해당 transport(JSON-RPC 포함)로 위임; Gateway 응답에 route trace 기록.
- **Dashboard Agents UX** → Agent → AI Model → Selected Runtime → Ask Agent 단일 흐름, 실제 model brand asset과 On-Prem router 상태 패널 추가; `next build` 성공.
- AI Model Router → `/api/models`(환경별 선택지) + `/api/local-deploy`(자연어 배포) live 확인; 대시보드 `tsc`+`next build` 통과
- **Live E2E (Pydantic AI + MLX Qwen3-Coder-30B)** → 자연어 "Deploy orders-api ..." → build→push→deploy→validate 자율 실행 → kind `orders-api 1/1 Running`(image v1.5.0) 검증 완료 (2026-07-11)
- **Deployments Live 추적 배선 완성** → 기록 활성 API 배포 → recorder가 DEPLOY/ACTIVITY(DEP-262AC0A3, v1.6.0) DynamoDB 기록 → 대시보드 `/api/dashboard/deployments`(aws-live)가 최신 배포로 노출 확인 (2026-07-11)
- Strands + Bedrock 이전 baseline: `make check` 544 passed (2026-07-11, 237.23s)
- GCP Day2 tests → **28 passed** (Vertex AI mock/heuristic 연동, severity=P2, confidence=0.30)
- Dashboard → lint/build 성공; 11 routes (OG/Twitter image 포함); Vercel production 배포 완료 (2026-07-11)
- CDK → `platform-agent-activity` 테이블 + GSI1 CREATE_COMPLETE; Vercel OIDC read grant UPDATE_COMPLETE (2026-07-11)
- CDK → Vercel team/project-scoped OIDC provider + DynamoDB read-only role AWS 배포 완료 (2026-07-11)
- `make local-cluster` → kind 3노드 (v1.34.0) Ready + registry push/pull → Pod Running
- `python -m src.agents.ai.orchestrator` → E2E pipeline 7-step 성공 (dev/staging)
- Strands Agent + Bedrock Claude → 자율 4-tool 호출 → 실배포 ✅
- Strands Agent + Qwen3-Coder (via tool proxy) → 로컬 kind 클러스터 자율 4-tool 배포 E2E 성공 ✅
- ADK Agent + Vertex AI Gemini 3.5 Flash → tool calling (gcp_build_image) ✅
- MSFT Agent + Azure OpenAI GPT-5.4 → tool calling (azure_build_image) ✅
- GCP/Azure 실 REST API 연동 및 OIDC 페더레이션 크레덴셜 자격증명 모듈 구현 & 테스트 완료 (2026-07-11) ✅
- AWS/GCP/Azure 다중 리전 및 백업 클러스터 자동 우회 복구(Multi-region Failover) 구현 & 테스트 완료 (2026-07-11) ✅
- CDK deploy → 97 resources CREATE_COMPLETE (us-east-1, 2026-07-10)
- GCP: Artifact Registry push + GKE Autopilot 배포 (검증 후 정리)
- Azure: ACR push + AKS 배포 (검증 후 정리)
- 리소스: 전부 정리 완료 (비용 $0)

## 동작하는 영역 (요약)

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge.
2. **3-Cloud Day2 Operations** — AWS(Step Functions) + GCP(Cloud Workflows) + Azure(Durable Functions). 각각 4-step 파이프라인 구현.
3. **Human-in-the-loop 승인** — Slack 승인 → `WaitForTaskToken` + SQS + SFN callback.
4. **Day1/1.5** — provisioning(cdk_generator/iam_designer/cost_estimator), deployment(smoke/canary/rollback), reporting(slo/oncall/capacity).
5. **Portability** — `NormalizedIncident` cloud-neutral envelope. provider registry + adapters.
6. **Runbook registry** — built-in catalog + capability-based schema + CDK seed + scan heuristic.
7. **AI Agents** — Strands(Bedrock) + ADK(Gemini 3.5 Flash) + MSFT(GPT-5.4). 3종 tool calling 검증 완료.
8. **Guardian Agent** — Policy-as-Code (APPROVE/AUTO/REJECT).
9. **MCP + A2A Gateway** — kubectl/docker MCP (9 tools) + FastAPI A2A + Bridge.
10. **On-prem K8s** — `make local-cluster` (kind 테스트용) → 3노드 + registry + NGINX ingress.
11. **Deployment Adapters** — 4 provider (onprem/aws/gcp/azure): Build→Push→Deploy→Validate→Rollback.
12. **Execution Adapters** — 4 provider: capability → provider-specific action resolution.
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지. AWS DynamoDB 연동 완료. 모든 데모 목업 데이터를 제거하고 실시간 Live 모드만 활성화. 🔐 Auth.js 기반 GitHub OAuth, Admin/Operator/Viewer 역할 부여 및 사용자 권한 관리 제어판(잠금 방지 보호 포함), 장애 복구 승인(Pending approvals), 신규 배포 트리거/롤백 액션 패널, 보안 감사 로그(Audit Logs) 뷰어 화면 프로덕션 배포 완료.

## Active Focus

- **레퍼런스 Tier 2 전체 완결(2026-07-15)**: #2 agents-as-tools 오케스트레이션+self-consistency(`orchestration.py`) · #3 MCP-over-HTTP 커넥터+kill-switch(`mcp_server.py`) · #4 cross-account STS AssumeRole+fallback(`adapters/aws_session.py`). 3종 모두 옵트인·비파괴. 잔여 레퍼런스=#7(Tier 3). 다음 우선순위=외부(Slack App·아티클·OAuth 데모) 또는 라이브 실증.
- 범용 Ops 에이전트 + 관측성 + On-Prem Provision(Terraform/Ansible) + kagent 설치 완료. ARCHITECTURE 통합·최신화(단일 스택 표 + Orchestrator+A2A 타깃).
- On-Prem 오프라인 기록/hybrid 대시보드/실 롤백 + Local Qwen 7B 전환 완료(2026-07-12).
- **배포 추적 IA 정리 완료(2026-07-12, 커밋 `930fe98`)**: Provisioning/Deployments/History 분리 + 중첩 상세 + 롤백 단일-row/teardown cascade + 자연어 라우팅 + `make dev-up`. gate 600 passed. **라이브 실증 완료(2026-07-13, 자연어 4스텝)**.
- 다음: origin `feat` 브랜치 삭제(명시 승인 필요) / (deferred) Slack App 실생성 / 테크 아티클 배포. **완료(2026-07-13)**: CDK live diff 재검증(drift 0)·kagent 정리(MOOT)·feat 로컬 삭제.
- **커밋·푸시·머지 완료**: `0b9148c`+`930fe98`가 **origin/main에 반영됨**(서버 main HEAD=`930fe98`). `feat/onprem-offline-recording-hybrid-rollback`는 main과 **동일 커밋**(중복) — 정리 대상(선택). 이번 세션 doc/스킬 변경분은 워킹트리 미커밋.

## Open Risks / Gaps

1. ~~**CDK 재배포 시 Lambda bundling**~~ — **해소(2026-07-13)**: synth "미완"은 stale 1.8GB 재귀 cdk.out 때문이었고 삭제로 해결(synth ~17s). live diff exit 0, 인프라 drift 0. ⚠️ diff/deploy 시 Vercel context 3종(`vercelTeamSlug/vercelProjectName/vercelOidcProviderArn`) 필수 — 없으면 `VercelDashboardReadRole` 가짜 삭제 diff. 로컬 pip 번들링(arm64↔amd64) 주의는 유지.
2. **Slack App 미연결** — APPROVE 승인 버튼 코드+가이드+E2E 테스트 완비, 실 Slack App 미생성 (코드 ready). OIDC 연계를 통한 Slack Webhook 송출 정상 작동.
3. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
4. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
5. ~~**A2A endpoint/card discovery**~~ — **해소(2026-07-14, Phase 2 완결)**: Phase 1(자체 게이트웨이) + **Phase 2 실 kagent 라이브 E2E** 모두 통과. kind+kagent 0.9.11+로컬 MLX Qwen 30B에서 supervisor→**실 kagent 에이전트** 카드 HTTP discovery→skill 매칭→JSON-RPC 위임→**실 `k8s_get_resources` 도구 진단** 반환(증거 `docs/evidence/a2a-phase2-live-e2e.log`). **부산물 버그 수정**: JSON-RPC 페이로드에 A2A 필수 `messageId` 누락(스펙 준수 `a2a` SDK가 `-32602` 거부) 추가 — Phase 1의 관대한 게이트웨이는 못 잡던 갭, 회귀 테스트 추가. 진단 에이전트 매니페스트 `infra/onprem/kagent/local-diagnostic-agent.yaml`. ⚠️ 인프라 실행 중 유지(정리: `make local-cluster-down`).
6. ~~**추적 IA 라이브 실증 미완**~~ — **해소(2026-07-13)**: 자연어 4스텝(provision+deploy→앱 롤백 단일-row→History 중첩 상세→teardown cascade) 브라우저 end-to-end 실증 완료. 참고: 레거시 activity 행은 `cluster` 없어 롤백 비활성 — 클린슬레이트는 `~/.platform-agent/activity.jsonl` 비우기.
7. ~~**NEXT_PUBLIC 프로덕션 인라인**~~ — **해소/stale(2026-07-13)**: Next 16.2.10 `next build` 실측 결과 `.env.local`의 `NEXT_PUBLIC_DASHBOARD_DEV_AUTH`가 클라이언트 청크에 **정상 인라인**(`signIn("dev-credentials")`로 상수 폴딩, 원문 env 참조 0). 과거 미인라인은 초기 Turbopack 이슈로 현재 재현 안 됨 → 코드 수정 불필요, `next dev` 우회 불요. (Vercel은 `.env.local` 부재라 미인라인=GitHub OAuth 폴백, 의도대로.)
