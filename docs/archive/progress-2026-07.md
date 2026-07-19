# PROGRESS_LOG Archive — July 2026

이 파일은 `docs/PROGRESS_LOG.md`에서 120줄이 초과하여 아카이브된 2026년 7월 이전 이력입니다.

---

## 2026-07-17 — 차트 k3s substrate 스모크: env×substrate 양축 실증 완결 (코드 무변경, gate 842 유지)

- Status: 마지막 선택 소품 수행. **기존** Multipass `k8s-lab`(k3s v1.31.4, Ansible 프로비전 자산) 재사용 — 클러스터 생성 없음, 릴리스 설치→검증→제거·반입 이미지 정리로 VM 원상 복원.
- Changed: `docs/evidence/helm-k3s-substrate-smoke.log`만.
- Verified (라이브): 이미지 tar 전송→`k3s ctr import`(199MB; exec-stdin 스트림은 EOF라 tar 경로가 정석) → `helm install -f values-k3s.yaml` → pod 1/1 Ready ~29s → **PVC가 `local-path`로 Bound**(k3s 오버레이의 핵심 검증; kind는 `standard`) → `/health/ready` 200 → Alertmanager 페이로드→P2 parking(APR-0515026F)→approve→INC-3219D4A8 resolved → uninstall·이미지 제거. **동일 차트가 kind/k3s 양 substrate에서 오버레이만 바꿔 동일 동작 — 레퍼런스 #7 env×substrate 레이아웃 양축 실증 완결.**
- Blockers: 없음.
- Next: **자율 백로그 전면 소진.** 잔여=전부 사용자 게이트(아티클 배포·OAuth 데모·Slack App·terraform apply).

## 2026-07-17 — 차트 State Store 배선(④↔#7 연결 마무리): stateStore values + DSN 멀티-레플리카 모드 (gate 839→842)

- Status: ④(SQL State Store)와 #7(Helm/Terraform)을 잇는 마지막 소품. 차트가 DSN 모드를 1급 values로 지원 — JSONL 기본값 무변경.
- Changed: (1) `values.yaml` `stateStore.{dsn,existingSecret,secretKey}` — **existingSecret(secretKeyRef)=프로덕션 경로**(values에 평문 DSN 금지), plain `dsn`=dev/kind 편의, secret이 plain보다 우선. (2) `_helpers.tpl` `stateStoreEnv`+`strategy`(persistence off→**RollingUpdate**, JSONL RWO일 때만 Recreate) — webhook/router 양쪽 주입. (3) **`infra/onprem/Dockerfile` `.[state]` 설치**(psycopg2 — 없으면 DSN 모드 이미지가 실동작 불가, 재빌드+import 검증). (4) README 2종: 차트=DSN 모드 사용법(라이브 증거 링크), Terraform=`kubectl create secret`+`stateStore.existingSecret` 스니펫(extraEnv 핵 대체). (5) 차트 가드 +3: 기본=DSN env 부재·dsn/secret 모드(secret 우선·평문 무노출)·**DSN 모드=PVC 없음+replicas 2+RollingUpdate**.
- Verified: helm lint 통과, `make check` → **842 passed, 1 skipped**(234.42s, 839→842). 이미지 재빌드 후 `import psycopg2` OK.
- Blockers: 없음.
- Next: 자율 백로그 소진. 잔여=사용자(아티클 배포·OAuth·Slack·terraform apply)·선택(k3s 스모크).

## 2026-07-17 — 레퍼런스 #7-b Terraform 모듈(EKS/Aurora/IRSA) → #7 전체 완결 (gate 834→839, apply 없음·spend 0)

- Status: 레퍼런스 #7 잔여 Terraform 파트 구현·오프라인 검증(사용자 승인 "다음 수행"). apply는 하지 않음(billable=사용자 게이트). 이로써 **레퍼런스 #7 = Helm(#7-a)+Terraform(#7-b) 전체 완결** — AWSome AI Gateway 레퍼런스 8항목 전부 소화(Tier 1 4종+Tier 2 3종+#7).
- Changed: 신규 `infra/terraform/aws-production/`(7파일) — VPC(2AZ·public/private·NAT 1) + EKS 1.31(managed node group, AWS-managed 정책만 ARN attach) + **Aurora PostgreSQL Serverless v2**(min 0.5 ACU·`database_name=platform_state`=④ `PLATFORM_STATE_DSN` seam 정합·`manage_master_user_password`=Secrets Manager, 평문 무노출) + **IRSA**(OIDC provider+차트 SA 전용 trust[sub+aud]·**유일 grant=DynamoDB activity 테이블 정확 ARN**+index, deploy_recorder가 실 소비자) + outputs(DSN 템플릿·IRSA arn·helm 배선 스니펫 README). Redis/Cognito는 **미소비라 의도적 제외** 명시. `tests/test_terraform_module.py` +5(구성 완비·**bare `"*"` 금지**[주석 제외]·state seam 정합·IRSA trust 스코프·validate[init 시]).
- Verified: `terraform init`+`fmt -check`+**`validate` Success**(크레덴셜/spend 0). `make check` → **839 passed, 1 skipped**(238.51s, 834→839). ARCHITECTURE 표 #7 ✅.
- Blockers: `terraform apply`=billable(EKS ~$0.10/h+노드+NAT+Aurora) — 사용자 게이트.
- Next: 자율 코드/인프라 백로그 재소진 — 잔여는 사용자 몫(아티클 배포·OAuth·Slack·apply류) + 선택 소품(k3s 스모크·차트 DSN values).

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

## 2026-07-17 — Google Agent 생태계 3자료 대조 → reference 노트 + NEXT_PLAN 후속 4건 (코드 무변경)

- Status: ADK 2.0·A2A·agents-cli(구글 developer 블로그+레포) 3자료를 우리 설계와 대조. **핵심 결론: 철학/기능 대부분 이미 구현**(reconciliation gate·self-consistency 폴백·Guardian·specialists-as-tools·자체 런타임 호스팅 3종)이라 마이그레이션/채택 대상 아님. 순수 문서 작업.
- Changed: 신규 `docs/reference/google-agent-ecosystem-2026.md`(A: ADK 2.0 deterministic-workflow 철학 대조표+유일 델타=context 격리 · B: A2A 4대 이점 vs 우리 상태(Zero Context Pollution=부분·Dynamic Autonomy=갭) · C: agents-cli 레이어차·유일 차용후보=eval 하네스 · 액션 4). `NEXT_PLAN.md`에 "Google 생태계 후속" 블록(①아티클 포지셔닝 ②context 격리 감사 ③버전 트래킹 ④eval 하네스, ①④=자율가능·②=감사→승인게이트).
- Verified: 코드 무변경(gate 748 유지, 미실행). 문서 라인수 NEXT_PLAN 61/120·reference 82. ⚠️ A2A SDK 버전표·벤치마크 50%/20%는 요약모델 추출값이라 아티클 인용 전 원문 재확인 필요(문서에 명기).
- Audit(②, 읽기전용 수행): **델타 아님(no-op).** Orchestrator step은 특화 에이전트에 `parts:[{"text": instruction}]`(그 step instruction만) 전송(`supervisor.py:171`), `context_id`는 A2A `contextId` 상관관계 UUID(`:174`)지 누적 컨텍스트 아님 → 이미 최소 스코프, shared `contextId`는 A2A "Zero Context Pollution" 정석. 초안의 "shared context_id=오염" 프레이밍(docstring 오독) 정정. 코드 무변경. reference §A/§B + NEXT_PLAN ② 갱신.
- Blockers: 없음.
- Next: 잔여 자율=④eval 하네스 스파이크·①아티클 포지셔닝. ③버전 트래킹(백로그). 인프라/사용자 항목 잔여.

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

## 2026-07-15 — 라이브 실증: Tier 2 #2 self-consistency + Tier 1 reconciliation (실 MLX Qwen 30B)

- Status: 그간 유닛(스텁)만이던 #2 self-consistency와 reconciliation 게이트를 **실 로컬 LLM(MLX Qwen3-Coder-30B)으로 라이브 실증**. 스텁이 아니라 shipped 코드 경로(`route_with_self_consistency`, `reconcile`/`apply_gate`)를 실 모델 출력으로 구동.
- Changed: 신규 `scripts/live_tier2_demo.py`(실 LLM sampler=temp1.0 분류기로 self-consistency 구동 + 실 LLM 분석으로 reconciliation 게이트 구동) + 증거 `docs/evidence/tier2-live-selfconsistency-reconciliation.log`. 제품 코드 무변경.
- Verified (라이브): **(A) self-consistency** — "Deploy orders-api…"→5/5 deploy(agreement1.00), "cluster looks off…"→5/5 kagent. 실 sampler→shipped 라우터→실 consensus 동작. **fallback 브랜치 프로브**: 8개 모호/2액션 프롬프트×7샘플 전부 만장일치(7/7) → 이 30B는 내부 일관성이 강해 fallback 라이브 미발화(=self-consistency가 강한 모델에선 **confidence signal**로 기능, fallback은 약한 모델용 안전망; fallback 자체는 유닛 `test_low_agreement_falls_back…` 커버). **(B) reconciliation** — TLS 만료 증거 있는 실 인시던트에서: grounded(LLM이 증거 봄→root_cause "expired SSL certificate", ratio **0.62**→게이트 **AUTO 유지**) vs hallucination(LLM이 증거 없이 추측→"resource/DB pool exhaustion", ratio **0.08**→게이트 **AUTO→APPROVE 강등**). 실 환각을 결정론 게이트가 포착. 제품 코드 무변경이라 gate 738 유지.
- Blockers: 없음. #3(원격 MCP SigV4)·#4(2nd AWS 계정) 라이브는 여전히 사용자 엔드포인트/크레덴셜 필요.
- Next: 외부(아티클 배포·OAuth 데모)·(선택)#3/#4 실 라이브.

## 2026-07-15 — Tier 2 #4 크로스계정 소비자 배선 + 종합 아키텍처 아티클

- Status: #4 `assume_role_session`을 실 소비자 2곳에 배선(그간 헬퍼+runtime만) + 레퍼런스 반영 스토리를 담은 종합 아키텍처 테크 아티클 작성.
- Changed: (1) `adapters/deployment/aws.py` `AwsBuildAdapter.build` CodeBuild 클라이언트를 `assume_role_session(env-role).session.client("codebuild")`로 구성(boto3 부재는 ImportError→기존 BuildResult 에러 유지). (2) `operations/executor/handler.py` `_ssm_client(region)` 헬퍼 신설 — 모듈-레벨 `_SSM`(primary) + 리전-페일오버 클라이언트 둘 다 이 헬퍼 경유(assume-role+graceful fallback, env 미설정=in-account 무변경). (3) 신규 `docs/post/platform-agent-architecture.md` — 결정론적 가드레일 중심의 종합 아키텍처 아티클(Tier 1/2 레퍼런스 반영 스토리·설계 원칙·검증 문화). 배포는 사용자 몫.
- Verified: `tests/test_aws_session.py` +2(deployment build·executor `_ssm_client`이 env-role로 assume_role_session 소비). `make check` → **738 passed, 1 skipped**(736→738). 기존 executor/deployment 스위트 무변경=비파괴.
- Blockers: 없음. 실 크로스계정(2nd 계정+trust)·아티클 배포는 사용자 개입.
- Next: main 병합+push. 이후 외부(아티클 배포·OAuth 데모)·라이브 실증만 잔여.

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
