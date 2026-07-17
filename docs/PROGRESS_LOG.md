# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-17 — 로드맵 ④: SQL State Store(옵트인) + 실 Alertmanager 라이브 E2E — 멀티-레플리카 실증 (gate 829→834)

- Status: ARCHITECTURE 잔여 ④(On-Prem State Store·Alertmanager 실연동)를 로컬 docker($0)로 완결. JSONL 단일-writer 제약(Helm 차트 replicas:1의 근거)을 푸는 productionization seam.
- Changed: (1) 신규 `src/agents/ai/state_store.py` — `SQLStateStore`(DB-API connect 주입·placeholder/autoincrement 파라미터·append-only+latest-wins=JSONL 시맨틱 동일)·`from_dsn`(postgresql→psycopg2, sqlite://→stdlib)·`configured_store`(`PLATFORM_STATE_DSN` 옵트인, 미설정=None=JSONL 무변경). (2) `onprem_approvals`/`onprem_incidents` 읽기·쓰기 양쪽에 seam 배선. (3) pyproject `state = ["psycopg2-binary>=2.9"]` extra. (4) `tests/test_state_store.py` +5(sqlite 오프라인: 시맨틱·라우팅·JSONL 비오염 양방향).
- Verified: `make check` → **834 passed, 1 skipped**(242.90s, 829→834). **라이브 E2E**(docker postgres:16 + prom/alertmanager:v0.28.1): ① **실 Alertmanager가 자체 grouping 후 native 페이로드 배달**(손 페이로드 아님)→4-step→P2 parking→**PostgreSQL row**. ② **레플리카 2개**(동일 DSN, 별개 프로세스): replica-2가 pending 조회·**승인 실행**→replica-1 즉시 pending 0+incident 반영(JSONL 불가능한 것). ③ 양 프로세스 kill→재기동→상태 생존. ④ psql ground truth 3 rows(pending→approved append-only→incident). 전량 teardown. 증거 `docs/evidence/state-store-alertmanager-live.log`.
- Blockers: 없음. Helm 차트에서 DSN 설정 시 replicas>1 해금(차트 values 배선은 후속 소품).
- Next: #7-b Terraform 모듈(클라우드=승인) or 사용자 항목(아티클/OAuth/Slack).

## 2026-07-17 — 레퍼런스 #7-a Helm 차트 kind 라이브 실증 (코드 무변경, gate 829 유지)

- Status: 방금 만든 차트를 전용 kind 클러스터(`pa-helm`)에 실 `helm install`로 end-to-end 실증(사용자 승인). 외부 GKE 컨텍스트 불가침(전 kubectl `--context` 핀), 실증 후 전량 teardown + 원 컨텍스트 복원.
- Changed: `docs/evidence/helm-kind-live-install.log`만(코드 무변경).
- Verified (전부 라이브): (1) `kind load`+`helm install` → deployed·NOTES 정상. (2) webhook pod **1/1 Ready ~12s**(strict `/health/ready` readiness in-cluster 그린)·PVC Bound 1Gi. (3) **RBAC 최소권한 auth can-i 실증**: SA로 patch deployments/get replicasets/patch scale=**yes** · patch nodes/delete pods/create pods\/eviction/delete deployments=**no**(drain off 기본). (4) **Day-2 E2E**: 실 Alertmanager 페이로드 POST → in-pod 4-step(휴리스틱 폴백, Bedrock creds 무=설계) → **P2 APPROVE parking**(APR-284A4249) → `/pending`→`/approve` → executed+resolved(INC-5D000FBD) → `/incidents` 기록. (5) **PVC 영속성**: pod 삭제→새 pod가 동일 인시던트 서빙.
- Blockers: 없음. 잔여=#7 k3s substrate 스모크(선택)·#7-b Terraform 모듈(클라우드=승인).
- Next: ④ State Store/Alertmanager 실연동(로컬 docker) or #7-b or 사용자 항목(아티클/OAuth/Slack).

## 2026-07-17 — 레퍼런스 #7-a: On-Prem Helm 차트 + 컨테이너 이미지 (gate 823→829, pyproject latent 버그 수정)

- Status: ARCHITECTURE 잔여 ⑤(레퍼런스 #7 Helm/Terraform 프로덕션, Tier 3) 중 **Helm 파트** 구현. 로컬·$0·오프라인 검증 가능 범위만 자율 수행(kind 라이브 설치=클러스터 생성이라 승인 게이트).
- Changed: (1) `infra/onprem/Dockerfile` — python3.11-slim + kubectl v1.31.4(Day-2 runner가 subprocess로 침) + `pip install .` 단일 이미지, 2엔트리포인트(webhook/router). (2) `infra/helm/platform-agent/` — webhook(기본 on, liveness `/health`·readiness `/health/ready`=서킷브레이커 인지 Tier1 #6 반영) + router(opt-in, 빌드툴 부재 명시·PVC 공유 시 podAffinity 핀) + **최소권한 RBAC**(4조치 동사 열거: 네임스페이스 Role=restart/undo/scale, **drain은 별도 ClusterRole·`allowDrain` 기본 off**) + PVC 단일-writer(replicas 1·Recreate, State Store가 멀티 경로임을 명시) + env×substrate values(kind/k3s) + NOTES/README. (3) `tests/test_helm_chart.py` +6 — helm lint·기본=webhook-only+노드 불가침·**RBAC `"*"` 금지**(fully-armed도)·drain 표면 정확성(cordon만, eviction API)·프로브 분리·단일-writer(helm 미설치 시 skip). (4) **`pyproject.toml` latent 버그 수정**: `[project.optional-dependencies.<name>]`+`dependencies=` 형식이 PEP 621 위반 — 아무도 `pip install .` 안 해서 잠복, 이미지 빌드가 표면화 → extras 배열로 정정.
- Verified: `make check` → **829 passed, 1 skipped**(263.50s, 823→829, +6). helm lint 통과·기본/풀 렌더 검증(기본=ClusterRole 없음, 풀=drain CR+k3s LLM endpoint 배선). **이미지 실빌드 성공(881MB)** + 컨테이너 스모크: kubectl v1.31.4·양 API import OK·webhook 기동→`/health` 200·`/health/ready` 200(checks ok)→정리.
- Blockers: kind/k3s **라이브 helm install은 클러스터 생성 필요 = 승인 대기**. Terraform 모듈(#7-b, EKS/Aurora)은 클라우드·별도 묶음.
- Next: (승인 시) kind 라이브 설치 실증 / #7-b Terraform 모듈 / ④ State Store·Alertmanager 실연동(로컬 docker 가능).

## 2026-07-17 — ⑦ 라이브 모델 스윕 실 실행 완료 (로컬 MLX, spend $0): 프롬프트 결함 발견→수정→가드 (gate 822→823)

- Status: 승인 큐 마지막 잔여였던 ⑦ 라이브 실행을 **A 로컬 MLX 경로**(무과금)로 완료. 신규 `scripts/live_model_sweep.py`가 shipped `live_router_factory`+`run_sweep`을 실 mlx_lm.server(:18090, per-request 동적 모델 로드) 상대로 구동. 총 **160 라이브 호출**(2모델×2 effort×20케이스×프롬프트 v1/v2), 미파싱→backstop 발화 0.
- Changed: (1) `scripts/live_model_sweep.py` 신규 — effort→temperature 매핑(low=0.0/high=1.0), points JSONL resume(모델별 순차 실행 병합 실증), 응답 `model` 에코 검증+오염 시 미기록 가드. (2) **`model_sweep.py` `_classify_prompt` 결함 수정** — 라이브 런이 표면화: v1 프롬프트가 "provision=create/**tear down**"으로 teardown→deploy cascade 제품 시맨틱과 모순 + 진단동사 우선 미명시 → 전 config가 동일 adversarial 2건 미스("Investigate why the terraform apply failed"→provision·"Tear down the staging cluster"→provision). 모델이 아니라 프롬프트가 틀렸음. v2로 재작성. (3) 회귀 가드 `test_classify_prompt_matches_product_routing_semantics` 추가.
- Verified: `make check` → **823 passed, 1 skipped**(230s, 822→823, +1). 라이브 v1→v2 델타(프롬프트 수정만): 7B/low 0.80→**1.00**·7B/high 0.75→0.90·30B/low 0.80→0.95·30B/high 0.80→0.95. **증거 기반 선택: Qwen2.5-Coder-7B @ temp0 = 20/20(100%)·최속(0.20s/success)** — "라우팅엔 큰 모델" 정적 주석은 측정으로 반증(30B보다 7B가 정확·빠름). 증거: `docs/evidence/model-sweep-live.log` + points JSONL 2종(v1 baseline/v2). MLX 서버는 실행 후 종료(유휴 $0 복원).
- Blockers: 없음. **승인된 실행 큐 8항목 전부 완료(코드+실행).**
- Next: 잔여는 전부 인프라/사용자 — 아티클 배포·OAuth 데모·Slack App·State Store·Helm/Terraform(#7 Tier 3).

## 2026-07-17 — 승인된 실행 큐 8항목 코드 전부 완료: ⑧-1/2/3 + ⑨ A/B + ⑦ 어댑터 (gate 796→822, 사용자 "전부 다")

- Status: 사용자가 ⑧·⑨ 잔여 + ⑦를 전부 승인("전부 다 하자"). 위험 낮은 순 큐로 8개 코드 묶음을 순차 구현·게이트·커밋. ⑦는 어댑터 코드까지 완료, 실 실행(과금)만 사용자 게이트로 잔존.
- Changed (8 커밋, 전부 origin/main): **⑧-3**(`e79bf94`) `ROLE_ALLOWED_ACTIONS` 위임 `allowedActions` 힌트+`action_sink_grader` 단일소스. **⑨A-1/A-2**(`0050129`) SSE `id:` dedup·`ready` 센티넬·`asyncio.wait_for` heartbeat. **⑧-1**(`fdf9e11`) `metadata.task` 구조화 디스크립터. **⑨B-1**(`1184ee5`) 신규 `memory_tier.py`(signature·scrub·distill·MemoryStore). **⑧-2**(`13d1352`) `Supervisor(confidence_router=)` 옵트인 저-confidence 게이트(구조적 Protocol=cycle 회피). **⑨B-2**(`ccc8a47`) recall+`augment_instruction` 옵트인 `memory=` seam(조언적). **⑨B-3/A-3**(`3b4cbd9`) `consolidate`/`dominant_failures` + SSE `agent` 필드. **⑦ 어댑터**(`57d2aa7`) `live_router_factory(call_model, backstop=)`(모델응답→role 파싱·latency 측정·결정론 백스톱, `run_sweep` 드롭인).
- Verified: `make check` 각 묶음 그린 → **822 passed, 1 skipped**(261s, 796→822, **+26 test**). 전부 비파괴(옵트인 DI·additive 메타데이터·SSE 하위호환·주입식 모델호출). 설계 2건(`docs/plans/a2a-delegation-hardening.md`·`sse-memory-hardening.md`) 승인·실행 반영.
- Blockers: **⑦ 실 실행만 잔존**(코드 완비) = 실 `call_model`+creds+과금(클라우드), or 로컬 MLX=무과금이나 `make dev-up` 스택 기동 필요. 사용자 결정 대기(A 로컬무과금/B 클라우드~$0.05/C 멈춤).
- Next: ⑦ 실 실행(사용자 선택) or 인프라/사용자(아티클 배포·OAuth·Slack·State Store·Helm/Terraform).

## 2026-07-17 — cwc-workshops 후속 ⑨: SSE 하드닝 + 회수가능 메모리 tier 설계 제안 (문서만, 코드 무변경)

- Status: ⑨(설계 항목)의 설계 제안서 작성. 실 코드(SSE 스트림·deploy_recorder) 근거로 그라운딩, 구현은 승인 대기(런타임 표면 개입이라). 자율 코드 백로그 실질 소진 후 남은 설계 작업.
- Changed (docs only): 신규 `docs/plans/sse-memory-hardening.md` — (A) SSE: A-1 event-id/dedup·A-2 READY 센티넬+heartbeat·A-3 per-agent 귀속(각 리스크/권고), (B) 메모리: B-1 시그니처-키드 distilled tier·B-2 실행시작 과거 주입(옵트인 DI·조언적)·B-3 주기 consolidation. 근거 file:line(`local_deploy_api.py:216-276`=`data:`만·id/READY 없음, `deploy_recorder`=풀 트레이스 저장하나 미주입). `NEXT_PLAN.md` ⑨ [~]로 갱신·설계 링크.
- Verified: 코드 무변경(gate 796 유지, 미실행). 권고 1순위=A-1+A-2(비파괴·즉시 UX). 안티: 정적 무조건 주입 금지·SSE replay 버퍼 상한·distilled 메모리 PII/시크릿 스크럽 선행.
- Blockers: 없음. ⑨ 전 항목 구현=승인 대기.
- Next: **자율 코드/설계 백로그 소진.** 잔여는 전부 승인/스펜드/인프라: ⑧-1/2/3(승인)·⑨ A/B(승인)·⑦ 라이브(실 spend)·아티클 배포·OAuth·Slack·State Store·Helm/Terraform.

## 2026-07-17 — cwc-workshops 후속 ⑧(안전 서브셋+⑧-4): A2A 위임 sanitize+cap · 경계 smell-test 가드 · 설계 제안 (gate 790→796)

- Status: ⑧(A2A 위임 injection-safe, Tier 3 설계·승인) 중 **비파괴 안전 서브셋**만 자율 구현하고, 계약/동작 변경 4건은 설계 제안서로 분리(승인 대기). supervisor 위임 경계=호출자 자유텍스트가 특화에 raw 전달이던 것을 bounded/cleaned로.
- Changed: `supervisor.py` — 신규 `sanitize_instruction(text, max_len=4000)`(C0/C1 control-char strip[tab/newline 유지]·length cap+truncation 마커·적용 transform 리스트 반환, 클린 입력=무변경). `handle`이 **아웃바운드** 명령어에 적용(분류는 원문 유지)·적용 시 `trace{kind:"sanitize"}` 기록. `trace` 지역변수 타입 주석 `list[dict[str,Any]]`(기존 latent pyright 경고 동반 수정). 신규 `docs/plans/a2a-delegation-hardening.md`(⑧-1 구조화 페이로드·⑧-2 저-confidence 게이트·⑧-3 최소권한 힌트·⑧-4 경계 smell-test, 각 리스크·권고·순서). **⑧-4(승인 무관, 완료)**: `ARCHITECTURE.md`에 **TOOL→SKILL→SUBAGENT smell-test** + 위임 안전 불변식 명문화 + **회귀 가드 테스트**(supervisor는 mutating provision/deploy를 in-process 실행 안 함, 반드시 A2A transport로 위임·미설정 시 refuse).
- Verified: `make check` → **796 passed, 1 skipped**(231.96s, 790→796, +6). sanitize: 클린=무변경·control-char strip·length cap 마커. 위임: 아웃바운드 텍스트 sanitized(`\x07` 제거 확인)+trace 기록·클린 입력은 sanitize trace 없음. ⑧-4 가드: configured=transport만 호출·unconfigured=transport 미호출+not_configured. 기존 delegation/JSONRPC/messageId 회귀 0.
- Blockers: 없음. ⑧-1/2/3(구조화/게이트/최소권한)은 **승인 대기**(`docs/plans/a2a-delegation-hardening.md`); ⑧-4는 완료.
- Next: (승인 시) ⑧-3 최소권한 힌트(가장 안전) → ⑧-1 구조화 디스크립터 → ⑧-2 저-confidence 게이트. or ⑨ SSE/메모리(설계) / ⑦ 라이브 스윕(실 spend=사용자).

## 2026-07-17 — cwc-workshops 후속 ⑦(스캐폴드): 오프라인 모델/파라미터 스윕 러너 (gate 779→790, 실 spend 0)

- Status: NEXT_PLAN ⑦(모델 스윕→Model Router 정량화)의 **자율 가능 오프라인 스캐폴드** 구현. 실 API 호출/과금 코드 없음 — LLM 백엔드는 `router_factory` 주입(테스트=결정론 mock), 라이브 모델 배선+실 spend은 사용자 게이트.
- Changed: 신규 `src/agents/ai/model_sweep.py`(eval_harness 위 증분) — `SweepConfig`(model×thinking×effort)+`grid()` 카테시안, `run_sweep()`(config별 dataset 채점→**cost_per_success/seconds_per_success** headline, `_majority_observation`로 `trials` self-consistency 재사용), **resumable**(`done=` 재투입 시 config.key dedup으로 스킵·기존 포인트 front 보존), `SweepPoint`(pass_rate/cost_per_success/seconds_per_success, 0성공=inf, to/from_dict 영속), `rank()/best()/scoreboard()`(cost/seconds/pass_rate 키, 결정론 tie-break). +11 test(`tests/test_model_sweep.py`, mock 백엔드).
- Verified: `make check` → **790 passed, 1 skipped**(218.92s, 779→790, +11). 스모크: good 모델(=classify)=20/20·cost_usd=price×calls·trials=3→3N calls·resume는 done config에서 factory 미호출(폭발 팩토리로 확증)·rank best-first.
- Blockers: 없음. ⑦ 라이브 실행(실 model 호출·과금)만 사용자 판단 잔여.
- Next: (설계·승인) ⑧ A2A 위임 injection-safe or ⑨ SSE/메모리 tier. **⚠️ PROGRESS_LOG 120줄 초과 임박 → `/tidy-docs` 권장.**

## 2026-07-17 — cwc-workshops 후속 ⑤: eval 하네스 성숙 — 선언적 멀티 grader 스코어카드 (gate 767→779, 비파괴 증분)

- Status: NEXT_PLAN ⑤(eval 성숙, 자율 코드) 수행. 단일-judge grade()/EvalReport 경로는 무변경으로 두고 그 위에 선언적 멀티-grader 스코어카드 레이어를 증분 추가. cwc eval-멀티메트릭 방법론 반영.
- Changed (`eval_harness.py`, 비파괴): (a) **선언적 `Grader`**(name+kind `code`|`judge`) — 단일 Judge→명명 메트릭 다중. 빌트인 `role_match_grader`·`budget_grader`·`action_sink_grader`(code) + `judge_grader`(기존 Judge 래핑=judge). (b) **`Verdict` 3-상태**(PASS/FAIL/**PASS_SLOW**=정답이나 예산초과) + **budget grader**(latency>budget→PASS_SLOW) + **action-sink grader**(read-only role이 mutate=FAIL·per-role allowed 정책=blast-radius 안전 메트릭). 리치 `Observation`(decision+latency_s+actions)와 `observing()` 브리지로 결정론 classifier를 무변경 투입. (c) **pinned-baseline 델타**: `Scorecard.metrics()`/`delta(baseline)`/`regressions()`(회귀 diff, 신규 메트릭=baseline None). (d) **`score(..., trials=N)` majority vote**(self-consistency 재사용; 결정론 라우터엔 no-op). `__all__` 확장, docstring 갱신.
- Verified: `make check` → **779 passed, 1 skipped**(232.74s, 767→779, **+12 test**). 표적(eval+supervisor+orchestration) 57 passed. 스모크: dataset 3메트릭(role/latency/blast_radius) 전부 1.0·PASS_SLOW(slow 라우터)·action-sink FAIL(read-only kagent가 rollout restart)·delta regressed True. 기존 grade()/EvalReport/judge 경로 회귀 0.
- Blockers: 없음. NEXT_PLAN ⑤ 완료 마킹.
- Next: (자율) ⑦ 모델/파라미터 스윕(실 API spend=사용자 판단) or ⑧ A2A 위임 injection-safe(설계·승인) / 세션 누적 커밋.

## 2026-07-17 — cwc-workshops 후속 ⑥: ROUTING_EVAL_SET + llm_judge 하드닝 (gate 758→767, over-trigger 갭 2건 수정)

- Status: NEXT_PLAN ⑥(데이터셋+judge 하드닝, 즉시 실익·자율) 수행. eval 하네스가 실 라우팅 over-trigger 갭 2건 표면화 → `classify_request` 정밀도 수정 → 회귀가드로 전환. 발견→수정→가드 루프 재실증.
- Changed: **(dataset)** `ROUTING_EVAL_SET` 13→**20**, 카테고리 균형(provision 4·deploy 4·diagnose 5·cluster-creation-verb 2·**adversarial 5**) + **네거티브(adversarial) 케이스** 도입(hot 키워드가 한쪽 가리키나 의도는 다른 쪽 → precision 채점, recall만 아님). **(classify_request)** first-substring-wins → **precedence**: ① 진단 동사(diagnose/investigate/troubleshoot/debug/why is/are/did)=KAGENT가 provision 명사보다 우선 · ② provision(기존 유지) · ③ 약한 investigation 명사(logs/pods/namespace/istio/status)는 delivery 동사(deploy/ship/install/release/roll out/promote) 선행 시 억제 → DEPLOY. 과광범 `observability` 트리거 제거. **(judge 반-관대)** `_build_judge_prompt` 재작성(read-only/mutating 경계 명시·확신없으면 FAIL) + 신규 `calibration_probe`(파괴적 provision→read-only kagent 컨트롤 canary; PASS/에러/미파싱=관대·불신) + `llm_judge(calibrate=True)`(canary 실패 grader를 exact-match로 강등). 빈문자열/"모름"/"don't know"=결정론 백스톱 유지.
- Verified: `make check` → **767 passed, 1 skipped**(227.82s, 758→767, **+9 test**). 표적 스위트(eval+supervisor+orchestration) 45 passed. 데이터셋 grade **20/20 100%**, by_category 전부 1.0. probe: lenient→False·discerning→True. 기존 supervisor/orchestration classify 단언(4건) 회귀 0. over-trigger 수정 확인: "Deploy the observability stack"=KAGENT→**DEPLOY**, "Investigate why the terraform apply failed"=PROVISION→**KAGENT**.
- Blockers: 없음. NEXT_PLAN ⑥ 완료 마킹.
- Next: (자율) ⑤ eval 멀티메트릭(선언적 Grader·PASS-SLOW·pinned baseline) or ⑦ 모델 스윕(실 API spend=사용자) / 세션 누적 4 커밋 미푸시(origin +3 + 이번분).

## 2026-07-17 — cwc-workshops(Anthropic Code with Claude) 대조 → reference 노트 + NEXT_PLAN 후속 ⑤~⑨ (코드 무변경)

- Status: 사용자 요청으로 `/Users/men1692/Desktop/AI/cwc-workshops`(Anthropic 공식 워크샵 9개) 대조. 병렬 3-Explore(eval 방법론·오케스트레이션/프로덕션·메모리)로 platform-agent 차용 후보만 추출. 방금 만든 ④ eval 하네스와 직결.
- Changed (docs only): 신규 `docs/reference/cwc-workshops.md`(메타결론: CMA 베타 런타임 전이X·계약만; Tier1 eval 성숙·Tier2 모델스윕·Tier3 A2A 위임계약·Tier4 SSE/메모리, file:line 인용 + `ROUTING_EVAL_SET` 자기비판). `NEXT_PLAN.md` "cwc-workshops 후속" 블록 ⑤~⑨(⑤eval 멀티메트릭/PASS-SLOW/action-sink·⑥데이터셋+llm_judge 하드닝·⑦모델 스윕 정량화=자율가능, ⑧A2A injection-safe 위임·⑨SSE/회수가능 메모리=설계). `AGENT_BRIEF.md` NEXT SESSION 포인터 갱신.
- Verified: 코드 무변경(gate 758 유지, 미실행). 문서 라인수 NEXT_PLAN 71/120·brief 42/60·cwc-workshops 44. 핵심 규명: 워크샵 전부 CMA 베타 API 위라 런타임 전이 불가(우리 자체 Orchestrator/A2A/MCP 스택), **계약·패턴만** 전이. eval 방법론 워크샵들이 우리 하네스 방향 독립검증+다음단계 제시.
- Blockers: 없음.
- Next: (자율) ⑥ 데이터셋+llm_judge 하드닝(즉시 실익) or ⑤ eval 멀티메트릭 or ⑦ 모델 스윕 / 세션 누적분 커밋(문서 다수 + eval_harness/supervisor 코드).

## 2026-07-17 — Google 생태계 후속 ①③④ 완료: 아티클 포지셔닝 + 버전 규명 + eval 하네스 스파이크 (gate 748→758)

- Status: `/goal 나머지 완료시까지 수행`으로 Google Agent 생태계 대조의 잔여 자율 항목을 완결. ②(context 격리)는 직전에 no-op 규명, 이번엔 ①③④ 수행.
- Changed: **①(docs)** EN `platform-agent-architecture.md` + KO `-ko.md` 맺으며 앞에 "같은 논지, 이제 플랫폼 벤더가 출시하다" 수렴 섹션(ADK 2.0 deterministic-workflow·A2A zero-context-pollution·agents-cli eval loop ↔ 우리 reconciliation/self-consistency/최소-페이로드 위임, 출처 3링크; 미검증 벤치마크는 정성 서술만). **④(code)** 신규 `src/agents/ai/eval_harness.py`: 클라우드-중립·오프라인 decision-quality 평가 계층 — `EvalCase` 라벨 데이터셋 + injectable `Router`/`Judge`, `exact_match_judge`(결정론) + `llm_judge`(LLM-as-judge, 파싱실패/에러 시 exact-match **결정론 백스톱**), `EvalReport`(pass_rate·카테고리별·`meets(threshold)` 회귀 가드), 빌트인 `ROUTING_EVAL_SET`(13). +10 test(`tests/test_eval_harness.py`, 하네스 메커니즘만 검증).
- Verified: `make check` → **758 passed, 1 skipped**(229.91s, 748→758). **④ 실익 실증 + 루프 완결**: 결정론 classifier 스파이크 → 11/13(84.6%), **실제 라우팅 갭 2건 표면화**("Create a GKE cluster"·"Spin up a kind cluster" → PROVISION이어야 하나 DEPLOY; classifier 키워드가 'create a X cluster'/'spin up' 미커버) → **`supervisor.classify_request` 수정**(cluster+생성동사 조합 감지, 기존 DEPLOY/KAGENT 케이스 회귀 0 확인) → eval set **13/13**, 갭 케이스는 회귀 가드로 전환. 유닛테스트가 못 잡는 결정-품질 갭을 발견→수정→가드로 닫는 루프 실증. **③ 규명**: 우리 클라이언트 A2A=stdlib-only(`a2a` SDK import 0, `supervisor.py`)라 A2A SDK 드리프트 무영향; ADK=`google-adk>=1.0`(`adk_deployer.py` Gemini 경로만), ADK Python GA 2026-03 후 재평가는 캘린더 항목.
- Blockers: 없음. reference 노트+NEXT_PLAN ①②③④ 전부 완료 마킹.
- Next: (선택) LLM router/judge로 eval 확장 / 커밋·푸시 / 잔여 인프라·사용자(아티클 배포·Slack·OAuth 데모·State Store·Helm/Terraform).
