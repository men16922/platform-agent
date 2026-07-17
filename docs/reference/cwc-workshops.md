# Reference — Anthropic cwc-workshops (Code with Claude)

> 외부 레포 분석 노트. **platform-agent 차용 후보 패턴**만 추린다. 이식 전 검토용. 되돌리기 어려운 결정은 `DECISIONS.md`.

- **출처:** `github.com/anthropics/cwc-workshops` (로컬 `/Users/men1692/Desktop/AI/cwc-workshops`), Apache-2.0
- **검토일:** 2026-07-17 (병렬 3-Explore 조사: eval 방법론 / 오케스트레이션·프로덕션 / 메모리)
- **레포 성격:** Anthropic **Code with Claude** 워크샵 9개 모음(교육용, 유지보수/기여 안 받음). 사용자 자체 품질 리포트는 `cwc-workshops/REPORT.md`(레포 구조/CI/리스크 관점 — 이 노트와 다른 각도).

## 메타 결론 (Google 생태계 노트와 동형)

거의 전부 **Claude Managed Agents(CMA) 베타 API**(`client.beta.sessions/agents/environments`, `agent_toolset_20260401`, `callable_agents`, `ant` CLI) 위. **런타임/플럼빙은 전이 안 됨**(우리는 이미 자체 Orchestrator/A2A/MCP 스택). 전이되는 건 **계약(contract)·패턴**뿐이고, 공교롭게 **방금 만든 ④ eval 하네스**(`eval_harness.py`)와 정통으로 겹침 — 우리 eval 방향이 옳다는 독립 검증 + 구체적 다음 단계 제시.

## 차용 후보 (가치순)

### Tier 1 — eval 하네스 성숙 (스켈레톤 이미 보유)
출처: `eval-driven-agent-development/` (TS) + `agent-decomposition/evals/` (Py) + `rightmodel/references/audit.md`.
- **선언적 `Grader` 리스트 + `kind:"code"|"judge"` 분류** (`eval-driven .../graders/types.ts:13-36`, `all.ts:20-37`). 메트릭 추가=객체 append. 우리 단일 Judge → 명명 메트릭 리스트(`role-exact-match`(code)·`route-defensible`(judge)·`latency-budget`(code)).
- **PASS/FAIL/PASS-SLOW 3-상태 + budget grader + action sink** (`agent-decomposition/evals/graders.py`, `run.py:37-39`, `common.py:40-95`). 특히 **에이전트가 클러스터에 한 부수효과(kubectl/apply)를 채점**(산문 아님). `--trials N` majority vote(`run.py:74-81`)=우리 self-consistency와 동형.
- **pinned-baseline 델타 스코어카드** (`eval-driven .../eval-runner.ts:82-88,234-247`). `EvalReport`→회귀 트래커, `make check`가 diff.
- **구조화 per-criterion LLM 판정** (`judge.ts:73-124` Zod structured output, 슬라이드당 1콜 memoize). 우리 `_parse_verdict`(`eval_harness.py`) 취약한 문자열 partition을 스키마 기반으로. 결정론 fallback은 유지.
- **⚠️ 자기비판 — audit 체크리스트를 `ROUTING_EVAL_SET`에 적용**(`rightmodel/audit.md:80,180-194`): 현재 (a) **한쪽 방향뿐**(네거티브 "PROVISION 가면 안 됨" 0), (b) 카테고리 불균형(diagnose5/prov3/dep3/gap2), (c) n=13 노이즈~8pt, (d) `llm_judge` 프롬프트가 관대편향("defensible면 통과")·알려진 네거티브로 judge 캘리브레이션 가드 없음. 전부 즉시 수정 가능.

### Tier 2 — 모델/파라미터 스윕 (가장 큰 *새* 갭)
출처: `rightmodel/references/sweep.md`. 우리 "AI Model Router"는 fit **주석만, 측정 안 함.**
- `model × thinking × effort` 그리드 + 모델별 제약, LLM 호출 1지점 env-var 주입(`tau2-bench.md:22-40`).
- **headline = `cost_per_success`/`seconds_per_success`**(`sweep.md:52`) — 성공률 가중. `ROUTING_EVAL_SET`에 돌리면 라우터 정적주석→증거기반 선택. resumable(파일에 N케이스 있어야 done).

### Tier 3 — 오케스트레이션/A2A 하드닝 (계약)
출처: `agent-decomposition/agents/cma.py`, `production-ready-agent`.
- **injection-safe 위임 계약**(`cma.py:248-251,283-309`): 특화 시스템 프롬프트 **서버측 고정**(호출자 입력 아님)·**구조화 `{task_type,params}`**(자유텍스트 아님)·untrusted 문자열 sanitize/cap·최소권한 툴셋·**graceful degradation**(위임 불가 시 낮은 confidence로 폴백→게이트 에스컬레이트). → 우리 `supervisor.handle`가 특화에 **자유텍스트 instruction** 그대로 보내는 부분 하드닝.
- **TOOL→SKILL→SUBAGENT 결정 룰 + smell test**(`agent-decomposition/README.md:94-107`): tool 출력>2k토큰→코드실행, "항상 X먼저"→skill, 출력 숫자하나→subagent 아님. A2A 경계 형식화.
- **numeric confidence guard를 skill에**(`reorder-policy/SKILL.md:36-39`): confidence<T→자동실행 금지·에스컬레이트. 우리 reconciliation gate 일반화형.

### Tier 4 — 대시보드 스트리밍 + 메모리 (부차)
- **SSE 하드닝**(`production-ready-agent/lib/sse.ts`, `chat.ts:28-99`): event-id dedup·**라이브 tail 먼저 열고 history backfill**·READY 센티넬·양성 재접속 삼킴/진짜만 표시·`thread_id→agent_name` 귀속(per-agent trace 탭). + **agent-version-pinned A/B 토글**(`enable-multiagent.sh`, 솔로v1↔멀티v2).
- **메모리 2-tier**(`agents-that-remember/README.md`, CMA 호스티드라 로컬 구현 없음—개념만): 우리 `deploy_recorder` JSONL/DynamoDB=원시 trace tier. + **시그니처 키드 distilled memory tier**(incident/deploy 시그니처=hash{cloud,resource,error class,drift,K8s reason}) + 실행 시작 시 매칭 과거 인시던트 컨텍스트 주입("steering memory prompt") + **Dreaming식 주기 consolidation**(모델이 trace→dedup/요약, 증분만). 감사로그→회수가능 메모리.

## 안티패턴 (베끼지 말 것)
- **CMA 베타 API 전체 표면**·`ant` CLI — 우리 자체 스택 있음, 계약만.
- **정적 무조건 fan-out**("넷 다 병렬 위임 먼저", `deal-team.yaml:6`) — 우리 self-consistency 라우팅이 더 나음, **회귀 금지**.
- 서버평가 `evaluated_permission:"ask"` 게이팅(우리 approval gate가 더 명시적, confirm 라운드트립 UX만 참고)·Next.js/React 세부·도메인 콘텐츠(M&A·재고)·자유텍스트 `spawn_subagent`/generic bash worker(레포도 "가장 노출됨"이라 표시)·cat-files 추출 핵.

## 액션
- Tier 1(데이터셋 하드닝+멀티메트릭 스코어카드)·Tier 2(모델 스윕)=**자율 가능 코드**. Tier 3(위임 계약)·Tier 4(SSE·메모리)=설계·승인. → NEXT_PLAN "cwc-workshops 후속" 참조.
