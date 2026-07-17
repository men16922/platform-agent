# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-17

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## ★ 승인된 실행 큐 (2026-07-17, 사용자 "전부 다 하자") — 위험 낮은 순

> 사용자가 ⑧·⑨ 잔여 + ⑦ 라이브를 **전부 승인**. 설계 2건(`docs/plans/a2a-delegation-hardening.md`·`sse-memory-hardening.md`)은 이제 **승인됨=실행**. 아래 순서(안전→위험)로 진행, 각 묶음마다 `make check`+커밋.

1. [x] ~~**⑧-3 최소권한 힌트**~~ — **완료(gate 796→798)**: `ROLE_ALLOWED_ACTIONS`(supervisor) 위임 `metadata.allowedActions` 힌트(KAGENT=[]) + `action_sink_grader` 기본 정책·`READ_ONLY_ROLES` 파생으로 단일 소스화(드리프트 불가). +2 test.
2. [x] ~~**⑨ A-1+A-2 SSE id/dedup + READY/heartbeat**~~ — **완료(gate 798→799)**: `_sse(event_id)` `id:` 라인(Last-Event-ID dedup) + 스트림 오픈 시 `ready` 센티넬 + `asyncio.wait_for` 15s heartbeat(`: keepalive`). 비파괴(구 클라이언트는 id/미지 type 무시). +1 stream test.
3. [x] ~~**⑧-1 구조화 위임 디스크립터**~~ — **완료(gate 809)**: `metadata.task={type,origin,skills,allowedActions}`(free-text `parts` 유지, params 추출 제외). 비파괴(kagent SDK는 미지 metadata 무시). +1 test.
4. [x] ~~**⑨ B-1 시그니처-키드 distilled 메모리**~~ — **완료(gate 799→809)**: 신규 `memory_tier.py`(오프라인·결정론) — `signature`(sha256 {provider,service,failed_step})·`scrub`(secret/PII redact)·`distill`(deploy 레코드→lesson, 방어적)·`MemoryStore`(count-consolidating·injectable·to/from_dicts). +9 test.
5. [ ] **⑧-2 저-confidence 폴백→게이트** — `Supervisor(confidence_router=...)` 옵트인 DI, 미주입=무변경.
6. [ ] **⑨ B-2 과거 인시던트 주입** — 옵트인 DI(`memory_provider`), 조언적(non-binding)·게이트 상충 없게.
7. [ ] **⑨ A-3 per-agent 귀속 / ⑨ B-3 consolidation** — Orchestrator 스트리밍·스케줄 선행 후(옵셔널 필드만 예약).
8. [ ] **⑦ 라이브 모델 스윕** — 실 API 과금. **실행 전 그리드/모델/예상비용 확인**(스캐폴드 `model_sweep.py` ready).

## 다음 우선순위 — **자율 코드 백로그 소진(2026-07-15). 잔여 = 전부 사용자/인프라.**

> 이번 세션(gate 702→**748**): Tier 2(#2·#3·#4) + 실 LLM/HTTP/STS 라이브 실증 + 대시보드 관측 3종 노출·orchestrator 활동기록 + ARCHITECTURE stale 정정 + **아키텍처 배선 ①②**(supervisor 프론트도어·deploy↔runtime `host` 스텝). 전 커밋 origin/main.

- [x] ~~**아키텍처 배선 ①② (자율 로드맵)**~~ — **완료(2026-07-15)**: ② supervisor 프론트도어(`local_deploy_api` `/api/local-deploy` 분류→A2A 위임/in-process 폴백) + ① deploy↔runtime(DeployPipeline opt-in `host` 스텝, approval-gated). +7 test, gate 748.
- [x] ~~**대시보드 관측 3종**~~ — **완료(2026-07-15)**: cost_metrics·reconciliation(AWS 파리티)·consensus/steps(orchestrator `record_route_activity` producer 완결). next build 클린.
- [x] ~~**Tier 1 반영**~~ — reconciliation gate·비용 3단계 게이트·서킷브레이커+readiness·비용 서브메트릭. (상세 `ARCHITECTURE.md` 표)
- [x] ~~#2 **agents-as-tools 오케스트레이션 + self-consistency**~~ — `orchestration.py`(N-샘플 majority vote·저합의 폴백 + `Orchestrator` 체이닝), a2a_server 옵트인. gate 714.
- [x] ~~#3 **MCP-over-HTTP 커넥터 + per-tool/글로벌 kill-switch**~~ — `mcp_server.py` `remote_mcp_tool`(intercept-reinject·전송실패 degrade) + `MCPServer` kill-switch 게이트(`MCP_DISABLED_TOOLS`/`MCP_KILL_SWITCH`), 비파괴. gate 736.
- [x] ~~#4 **cross-account STS AssumeRole + graceful fallback**~~ — `adapters/aws_session.py`(`CircuitBreaker` 재사용) + `runtime/aws.py` 옵트인. gate 723.
- **잔여 레퍼런스 = #7(Helm/Terraform 프로덕션)만 = Tier 3**(온프렘/클라우드 프로덕션화 시).
- [x] ~~#4 **크로스계정 소비자 배선**~~ — **완료(2026-07-15)**: `deployment/aws.py` CodeBuild + `executor/handler.py` SSM(primary+failover `_ssm_client`)이 `assume_role_session(env-role)` 소비, env 미설정=in-account 무변경. +2 test, gate 738.
- [x] ~~라이브 실증(#2 self-consistency · #3 MCP-over-HTTP · #4 STS graceful fallback)~~ — **완료(2026-07-15)**: 실 MLX Qwen(#2 reconciliation 포함)·실 HTTP mock MCP(#3)·실 STS(#4 폴백). 증거 `docs/evidence/tier2-live-*.log`, 스크립트 `scripts/live_*_demo.py`.
- ~~2번째 AWS 계정 cross-account **성공** 경로 라이브~~ — **계획에서 제거(2026-07-15, 사용자 결정)**. #4 코드+폴백/실패 경로는 실 STS로 실증 완료; 실 크로스계정 성공은 하지 않음.

## 열린 작업 (로드맵 — 성격별)

### Google Agent 생태계 대조 후속 (2026-07-17, `docs/reference/google-agent-ecosystem-2026.md` 근거)
> ADK 2.0("Agentic Workflows"=deterministic 그래프+LLM은 추론만) + A2A(협업 에이전트 4대 이점) + agents-cli(GCP 에이전트 빌드 메타-툴)를 우리 설계와 대조. **핵심 결론: 철학·기능 대부분 이미 우리가 구현(reconciliation gate·self-consistency 폴백·Guardian·specialists-as-tools·자체 런타임 호스팅 3종)** → 마이그레이션/채택 대상 아님. 아래 4건만 잔여.

- [x] ~~**① 아티클 포지셔닝 (자율, 낮은 리스크)**~~ — **완료(2026-07-17): 프레이밍 작성.** EN `platform-agent-architecture.md` + KO `-ko.md` 맺으며 앞에 "같은 논지, 이제 플랫폼 벤더가 출시하다" 섹션 추가(ADK 2.0 deterministic-workflow·A2A zero-context-pollution·agents-cli eval loop → 우리 reconciliation/self-consistency/최소-페이로드 위임과 수렴, 출처 3링크). ⚠️ **미검증 벤치마크(50%/20%)·버전 수치는 정성적으로만 서술, 인용 안 함.** 실제 **배포**(LinkedIn/Medium)는 여전히 사용자 몫(아래 외부/사용자 참조).
- [x] ~~**② context 격리 감사**~~ — **완료(2026-07-17): 델타 아님(no-op).** 읽기전용 감사 결과 Orchestrator step은 특화 에이전트에 `parts:[{"text": instruction}]`(그 step instruction만) 전송(`supervisor.py:171`); `context_id`는 A2A 프로토콜 `contextId` 상관관계 UUID(`:174`)지 누적 컨텍스트 페이로드 아님 → 이미 최소 스코프, shared `contextId`는 A2A "Zero Context Pollution" 정석. 초안 프레이밍(docstring 오독) 정정. 코드 무변경.
- [x] ~~**③ 버전 트래킹**~~ — **규명 완료(2026-07-17): 백로그 노트.** (a) **우리 클라이언트 A2A는 stdlib-only**(`supervisor.py` json/uuid/urllib, `a2a` SDK import 0) → A2A SDK 버전 드리프트는 우리 코드에 **무영향**(SDK는 원격 kagent 서버에만 존재, 의도적 경량 의존). (b) ADK 의존은 `google-adk>=1.0`(`pyproject.toml`), 실사용은 `adk_deployer.py`(Gemini 경로)만. **캘린더 항목**: ADK Python GA **2026-03** 후 workflow-graph API가 Gemini 서브에이전트 경로를 개선 가능한지 재평가(단 우리 Orchestrator는 클라우드-중립, ADK는 GCP라 코어 대체는 아님). 지금 액션 없음.
- [x] ~~**④ eval 하네스 스파이크**~~ — **완료(2026-07-17): 실익 확인, gate 748→758.** 신규 `src/agents/ai/eval_harness.py`(클라우드-중립·오프라인): 라벨 데이터셋(`EvalCase`)+injectable `Router`/`Judge`, `exact_match_judge`(결정론 기본)+`llm_judge`(LLM-as-judge, 파싱실패/에러 시 exact-match **결정론 백스톱**), `EvalReport`(pass_rate·카테고리별·failures·`meets(threshold)` 회귀 가드), `grade()`, 빌트인 `ROUTING_EVAL_SET`(13케이스). +10 test. **실익 실증 + 루프 완결**: 결정론 classifier 스파이크 → 11/13(84.6%), **실제 라우팅 갭 2건 표면화**("Create a GKE cluster"·"Spin up a kind cluster" → PROVISION이어야 하나 DEPLOY; 키워드가 'create a X cluster'/'spin up' 미커버). → **`classify_request` 수정**(cluster+생성동사 조합 감지, 기존 DEPLOY/KAGENT 케이스 회귀 0) → eval set **13/13**, 갭 케이스는 회귀 가드로 전환. eval 하네스 = 유닛테스트가 못 잡는 결정-품질 갭 발견→수정→회귀가드 루프 실증. 후속(선택): LLM router/judge로 모델 품질 평가 확장.
- 참고(범위 밖): A2A "Dynamic Autonomy"(수신 에이전트 되묻기/push-back)는 매력적이나 **요청 이상 기능** → 자율 추가 금지, 메모만. agents-cli는 **GCP lock-in + Pre-GA**라 툴 자체 채택 금지(방법론만).

### cwc-workshops 대조 후속 (2026-07-17, `docs/reference/cwc-workshops.md` 근거)
> Anthropic Code with Claude 워크샵 9개(병렬 3-Explore 조사). **런타임(CMA 베타)은 전이 안 됨(우리 자체 스택 보유), 계약·패턴만 전이.** 방금 만든 ④ eval 하네스와 직결 — 우리 방향 독립검증 + 다음 단계 제시.

- [x] ~~**⑤ eval 하네스 성숙**~~ — **완료(2026-07-17, gate 767→779)**: 단일-judge grade()/EvalReport 무변경 위에 선언적 멀티-grader 스코어카드 증분. (a) `Grader`(name+`kind:code|judge`), 빌트인 role/budget/action_sink/judge grader. (b) `Verdict` 3-상태(PASS/FAIL/**PASS_SLOW**) + budget grader + **action-sink grader**(read-only role mutate=FAIL blast-radius) + `Observation`(decision+latency+actions)·`observing()` 브리지. (c) `Scorecard.delta/regressions`(pinned-baseline 회귀 diff). (d) `score(trials=N)` majority vote. +12 test.
- [x] ~~**⑥ `ROUTING_EVAL_SET` + `llm_judge` 하드닝**~~ — **완료(2026-07-17, gate 758→767)**: 데이터셋 13→20·카테고리 균형·**adversarial 네거티브 5** 도입(precision 채점). eval가 over-trigger 갭 2건 표면화("Deploy the observability stack"→KAGENT, "Investigate why the terraform apply failed"→PROVISION) → `classify_request` precedence 재설계(진단동사>provision>delivery-guarded 명사, `observability` 제거) → 회귀가드. judge 반-관대: `_build_judge_prompt` 재작성(read-only/mutating 경계·FAIL-when-unsure) + `calibration_probe` canary + `llm_judge(calibrate=True)` 강등 + 빈문자열/"모름" 백스톱 테스트. +9 test.
- [~] **⑦ 모델/파라미터 스윕 → Model Router 정량화 (Tier 2)** — **오프라인 스캐폴드 완료(2026-07-17, gate 779→790)**: 신규 `src/agents/ai/model_sweep.py` — `SweepConfig`(model×thinking×effort)·`grid()`·`run_sweep()`(config별 dataset 채점→**cost_per_success/seconds_per_success** headline, `trials` self-consistency 재사용, **resumable** done-dedup)·`SweepPoint`(0성공=inf, to/from_dict)·`rank/best/scoreboard`. LLM 백엔드=`router_factory` 주입(실 호출 0). +11 test. **잔여=사용자 게이트**: 라이브 모델 배선+실 API spend 실행(정적주석→증거기반 선택).
- [~] **⑧ A2A 위임 계약 하드닝 (Tier 3)** — **안전 서브셋+⑧-4 완료(2026-07-17, gate 790→796)**: 아웃바운드 `sanitize_instruction`(control-char strip·4000자 cap·trace, 분류는 원문 유지)+`handle` 배선; ⑧-4 `ARCHITECTURE.md` TOOL→SKILL→SUBAGENT smell-test+위임 안전 불변식+회귀 가드. 비파괴 +6 test. **잔여=승인 대기** (설계=`docs/plans/a2a-delegation-hardening.md`): ⑧-3 최소권한 힌트(role별 allowedActions, `action_sink_grader` 정책 공유=가장 안전·권고 1순위) · ⑧-1 구조화 `{task_type,params}` 디스크립터(비파괴 증분) · ⑧-2 저-confidence 폴백→게이트(옵트인 DI). 자유텍스트 완전 제거·특화 서버측 시스템프롬프트 고정은 특화 서버 재작성 동반=별도 마일스톤.
- [~] **⑨ (부차) 대시보드 SSE 하드닝 + 회수가능 메모리 tier** — **설계 완료(2026-07-17)=`docs/plans/sse-memory-hardening.md`** (근거: SSE=`local_deploy_api.py:216-276` `data:`만·id/READY 없음, 메모리=`deploy_recorder` 풀 트레이스 저장하나 미주입). 권고 순서: **A-1 SSE id/dedup + A-2 READY/heartbeat**(낮은 리스크·즉시 UX·비파괴) → B-1 distilled 메모리(오프라인·injectable) → B-2 과거 주입(옵트인 DI·조언적) → A-3 per-agent/B-3 consolidation. 구현=승인 대기.
- 참고(범위 밖/안티): CMA 베타 API·`ant` CLI 채택 금지(계약만); **정적 무조건 fan-out은 우리 self-consistency 라우팅 회귀라 금지**; 자유텍스트 spawn_subagent/cat-files 핵 금지.

### 리팩토링 후속 (선택 — 2026-07-17 구조 패스에서 판단 보류)
- [ ] **`operations` 그룹핑 축 통일** — AWS=role별 서브패키지(`operations/{executor,detector,...}/`) vs gcp/azure=cloud별 패키지(`operations/{gcp,azure}/{role}.py`). 한 축으로 통일하면 일관성↑이나 import churn(테스트+CDK asset 경로) 반나절, 별도 승인.
- [ ] **`approval_bridge/handler.py`(604줄) 분리** — slack_interactive + request_store로 응집도 개선 여지. **단 테스트가 내부심볼 12개+를 `handler` 모듈경로에 `@patch` 강결합**해, 분리 시 재import로 patch 경로 보존 필요 → 실익<리스크. 하려면 테스트 patch 타깃 재작성 동반.
- 참고: `_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이라 제외). detector/analyzer/decision은 SDK 90%+ 상이라 DRY 안 함(의도적).

### 로컬·자율 가능 — ✅ 전부 소진(2026-07-14)
- [x] ~~인터랙티브 에이전트 MCP 단일 카탈로그 채택~~ · [x] ~~실 executor scale~~ · [x] ~~실 executor drain~~ 모두 완료. On-Prem 실 executor는 되돌리기-가능 4조치(restart/undo/scale/**polite drain**) 완결, 기본 OFF 게이팅. 공격적 force-drain만 의도적으로 사람 몫. **이제 자율로 진행할 순수 로컬 코드 백로그 없음.**

### 클라우드 크레덴셜/과금 필요 (자율 불가)
- [x] ~~**GCP/Azure Provision 어댑터 + 라이브**~~ — **완료(2026-07-14)**: GKE(gcloud)/AKS(az) 어댑터(`6baa6ee`) + `node_size` 지원(`f3e7952`, 제한구독 대응). **AKS 실 클러스터 라이브**(provision k8s 1.35.6 1노드 Ready→teardown, ~$0.03). GKE는 preflight 라이브·create는 하네스 자동차단(AKS가 동일 패턴 실증). 실 create/delete는 사용자 `!`로 어댑터 호출(하네스가 create 차단, delete 허용).
- [~] **Agent Runtime 매니지드 호스팅** — **코드/preflight 완료(2026-07-14, `36085fc`)**: `adapters/runtime/` 3종(AgentCore/Agent Engine/Foundry), plan-first/approved-gated. AWS·GCP는 실 클라우드 read-only preflight 라이브 통과. **잔여=실 create(billable)**: 사용자 허락 대기.
  - [x] ~~(billable) AWS AgentCore 실 배포~~ — **완료(2026-07-14, `2079c01`)**: `infra/agentcore/` arm64 이미지+exec role, 어댑터 create→READY(~12s)→invoke(실응답)→teardown 라이브 E2E, 즉시 삭제(<$0.50).
  - [x] ~~(billable) GCP Agent Engine 실 배포~~ — **완료(2026-07-14, `40fa8f6`)**: `infra/agentengine/` custom-template 에이전트, 어댑터 create→DEPLOYED→query(Gemini 실응답)→teardown 라이브 E2E, 즉시 삭제(<$0.50).
  - [x] ~~(billable) Azure Foundry 실 배포~~ — **완료(2026-07-14, `4caf7de`+`2231362`)**: 어댑터 v1→v2 결함 수정 후 실 배포. Foundry 계정/프로젝트/gpt-5.4-mini, 어댑터 create_version→Responses API 쿼리(실응답)→delete 라이브 E2E. **3/3 클라우드 완결.** `infra/foundry/README.md`에 gotcha 기록. (Azure 스택은 유휴 ≈$0라 유지 중 — 정리 선택.)

### 외부/사용자 개입
- [ ] (deferred) **Slack App 실 생성/토큰** — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요. On-Prem 승인 게이트도 Slack 버튼 프런트엔드 연동 가능(현재는 대시보드 버튼으로 대체됨).
- [ ] **테크 아티클 배포(LinkedIn/Medium)** — **작성 전부 완료(잔여=배포, 사용자)**: 종합 아키텍처 글 EN `docs/post/platform-agent-architecture.md` + **KO 전문판 `-ko.md`** + **짧은 LinkedIn 컷(EN/KO) `platform-agent-linkedin-cut.md`** + 데모 영상 `local-onprem-edited.mp4`.
- [ ] 대시보드 **브라우저 UI 인증 배포 클릭 데모** — GitHub OAuth 로그인(사용자 수행). 백엔드/read 경로는 검증됨.

## 참고 — 2026-07-14 세션 완료 (상세는 PROGRESS_LOG)

A2A Phase 2(실 kagent 라이브+messageId 버그) · PROVISION 격리 · ARCHITECTURE 정합화 · **On-Prem Day-2 전체 vertical**(PATH B webhook→승인 게이트→대시보드 승인/타임라인 hybrid→실 executor kubectl **rollout+scale+polite drain**, 되돌리기-가능 4조치 완결) · MCP Gateway 단일 카탈로그 · **인터랙티브 에이전트 단일 카탈로그**(drift-0 불변식) · docs tidy.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
