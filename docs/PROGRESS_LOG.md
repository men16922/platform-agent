# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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
