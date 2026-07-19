# Plan — A2A 위임 계약 injection-safe 하드닝 (NEXT_PLAN ⑧, Tier 3)

최종 갱신: 2026-07-17 · 상태: **✅ 승인됨(사용자 "전부 다") — 실행 중** (큐 순서: NEXT_PLAN ★)

> `Supervisor.handle`이 특화 A2A 에이전트로 위임하는 경계를 injection-safe하게 굳힌다.
> **자율로 이미 반영한 것**: 아웃바운드 명령어 **sanitize + length-cap**(`sanitize_instruction`,
> gate 790→795, 비파괴). 아래 4건은 **위임 계약/동작 변경**이라 승인 후 구현한다.

## 현재 경계 (근거)

- `supervisor.py` `Supervisor.handle`: 분류→카드 discovery→skill 매칭→JSON-RPC/HTTP 위임.
- 신뢰 경계: 호출자 자유텍스트 `instruction`이 `parts:[{"text": ...}]`로 특화에 **그대로** 전달.
  분류는 원문에, 아웃바운드는 `sanitize_instruction`으로 bounded/cleaned (완료).
- 아직 없는 것: 구조화 페이로드, 저-confidence 게이팅, 최소권한 힌트, 계약 스키마.

## 승인 필요 항목 (성격·리스크·권고)

### ⑧-1. 구조화 위임 페이로드 `{task_type, params}` (계약 변경, 중간 리스크)
- **무엇**: 자유텍스트 대신(또는 함께) `metadata.task = {type: role, params: {...}}` 구조화 필드 추가.
  특화 서버가 자유텍스트를 파싱하지 않고 구조화 필드만 신뢰하도록.
- **리스크**: 자유텍스트→params 추출기가 필요(현재 분류기는 role만 산출, params 파서 없음).
  특화 서버 측 변경도 동반(우리 클라이언트만으론 반쪽). 실 kagent(A2A SDK)는 표준 Message라
  커스텀 `metadata.task`는 무시될 뿐 안전은 함.
- **권고**: **비파괴 증분** — free-text `parts`는 유지(하위호환), `metadata.task`에 `{type, matchedSkills,
  origin:"supervisor"}` **디스크립터만** 추가(params 추출은 후속). 우리 게이트웨이 특화만 이 필드 소비.
  실 스키마화(자유텍스트 제거)는 특화 서버 재작성 동반이라 별도 마일스톤.

### ⑧-2. 저-confidence 폴백 → 게이트 (동작 변경, 중간 리스크)
- **무엇**: `handle`이 결정론 `classify_request` 대신 self-consistency(`orchestration.route_with_self_consistency`)
  결과의 agreement가 낮으면 위임을 **보류하고 승인 게이트**로 강등.
- **리스크**: `handle`은 현재 LLM 무호출(결정론·오프라인). self-consistency 배선은 LLM sampler 필요 →
  기본 경로에 LLM 의존 유입(테스트/오프라인 영향). reconciliation 철학과는 일치.
- **권고**: **옵트인** — `Supervisor(confidence_router=...)` DI seam. 미주입 시 현행 결정론(무변경).
  주입 시 low-agreement→`delegated=False, trace:{kind:"gated", reason:"low_confidence"}`. 기본 동작 0 변경.

### ⑧-3. 최소권한 힌트 (계약 변경, 낮은 리스크)
- **무엇**: 위임 메시지에 `metadata.allowedActions`(role별 화이트리스트, 예 KAGENT=read-only)를 실어
  특화가 자기 blast-radius를 알게. eval `action_sink_grader`의 정책과 **동일 소스**로 공유.
- **리스크**: 낮음(순수 additive 메타데이터, 특화가 무시해도 안전). 단 정책 소스 단일화 필요.
- **권고**: `ROLE_ALLOWED_ACTIONS` 상수 신설 → 위임 메타데이터 + `action_sink_grader(allowed=...)` 공유.
  **⑧ 중 가장 안전** — 승인 시 우선 구현 후보.

### ⑧-4. TOOL→SKILL→SUBAGENT smell-test로 A2A 경계 형식화 (문서/가드, 낮은 리스크) — ✅ 완료(2026-07-17)
- **무엇**: 언제 in-process tool vs A2A skill 위임 vs subagent인지 판단 기준을 `docs/ARCHITECTURE.md`에
  명문화(cwc-workshops smell-test 차용). 경계 회귀 방지 가드 테스트 1~2건.
- **리스크**: 낮음(문서+테스트). 코드 계약 무변경.
- **완료**: `ARCHITECTURE.md` Orchestrator+A2A 섹션에 TOOL→SKILL→SUBAGENT smell-test + 위임 안전 불변식
  명문화. 가드 테스트 `test_supervisor_never_executes_mutating_work_without_the_a2a_boundary`
  (configured=transport만 호출·unconfigured=transport 미호출+not_configured). gate 795→796.

## 권고 실행 순서 (승인 시)
1. ⑧-3 최소권한 힌트(+정책 단일화) — 가장 안전·즉시 실익.
2. ⑧-1 구조화 디스크립터(비파괴 증분, params 추출 제외).
3. ⑧-2 저-confidence 게이트(옵트인 DI, 기본 무변경).
4. ⑧-4 경계 문서화+가드.
> 자유텍스트 완전 제거·특화 서버측 시스템프롬프트 고정은 **특화 에이전트 서버 재작성**이 필요한
> 별도 마일스톤(우리 supervisor 클라이언트 범위 밖). 여기서는 클라이언트 경계 하드닝까지만.

## 이미 완료 (자율, 비파괴)
- [x] 아웃바운드 sanitize + length-cap — `sanitize_instruction`(control-char strip·4000자 cap·trace note),
  `handle`이 아웃바운드 텍스트에 적용(분류는 원문 유지). +5 test, gate 790→795.
