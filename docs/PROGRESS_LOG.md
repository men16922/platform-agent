# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-16 — `Resource:"*"` 7건의 근거를 찾아 닫았다 — 도구를 두 번 잘못 골랐다 (gate 2094)

- Status: 08-15에 *"AWS 권한 레퍼런스가 JS 렌더라 못 읽는다"*로 열어 둔 항목. **출처 없이
  코드 주석으로 단정하지 않겠다**고 했으니 출처를 찾는 게 남은 일이었다.
- Verified(⚠️**도구를 두 번 잘못 골랐다**): ①**IAM 정책 시뮬레이터** — 리소스 한정 정책이
  `implicitDeny`+`MatchedStatements: []`라 답이 나온 줄 알았는데, **대조군(`Resource:"*"`)도
  `implicitDeny`**였다. CloudWatch 메트릭은 애초에 ARN으로 주소 지정되는 자원이 아니라
  시뮬레이터가 답할 수 있는 질문이 아니다. ②첫 시도의 `--resource-arns`는 IAM root ARN이라
  **어느 액션과도 안 맞았다** — 대조군이 실패한 걸 뒤늦게 봤다.
- Verified(**되는 도구**): AWS 문서엔 **GitHub 마크다운 미러**가 있고(`awsdocs/*`), 권한
  레퍼런스는 **JSON 미러**가 있다(`iann0036/iam-dataset`, 455개 서비스). 7건 전수 대조 —
  6건은 `resource_types` **없음**, ⚠️**`cloudwatch:ListMetrics`만 `dataset`이 있다**
  (Metrics Insights용이라 메트릭 나열엔 안 맞는다). **"전부 없음"으로 뭉뚱그렸으면 틀렸다.**
- Changed: 7건 전부에 **인접 주석**으로 근거를 적었다(`ListMetrics`의 예외까지). ⚠️`if` 블록
  위에 있던 `ListStateMachines`의 이유는 **문장 옆으로 내렸다** — 참인데 읽는 사람 눈에 없었다.
- Changed(가드 +9, `test_iam_wildcard_justified.py` 신규): 추적되는 `src/stacks/*.ts`의
  모든 `resources: ['*']`가 **인접 주석**을 갖는가(`git ls-files`로 `cdk.out` 배제). 규칙이
  **prose 품질이 아니라 인접성**인 이유도 테스트로 고정했다. 변이: 주석 하나 제거 → 2 failed.
  ⚠️**그 인접성 테스트를 처음엔 손으로 다시 스캔해 짰다가 줄 인덱스를 틀렸다** — 같은 스윕을
  재사용하도록 고쳤다. **검사기와 어긋나는 검사기**가 오늘 여러 번 나온 그 모양이다.
  `make check` **2094**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: 가드레일 문구도 참으로 갱신했다(`AGENT_BRIEF`). ⚠️**같은 라운드에 내가 또 밟았다** —
  진입점 문서의 게이트 숫자를 `str.replace`로 **assert 없이** 갱신해 앵커가 안 맞자 **조용히
  no-op**이 됐고, 줄 수는 그대로라 예산 가드도 못 잡았다. **2081·2085 두 번을 2073인 채로
  커밋했다.** ⇒ **문서 치환은 앵커를 assert할 것**(오늘 코드 쪽에선 계속 그렇게 했으면서
  문서 쪽에선 안 했다). 남은 항목은 전부 외부 입력 대기 — Phase 4 승인 셋 · `.[azure]`
  업스트림 · **CI 검증(push 필요, D43)**.

## 2026-08-16 — CI가 미선언 의존성을 인라인으로 떠받치고 있었다 (gate 2085)

- Status: 내가 `azure` extra에 패키지를 더했는데 **그 extra는 해석이 안 된다**. CI가 그걸
  설치하면 내가 CI를 깬 것이라 확인했다 — **안 깼다**(CI는 `.[dev,state,observability]`만).
  ⚠️**대신 M25가 확증됐다**: 그 줄이 `fastapi "uvicorn[standard]"`를 **명령줄에 직접** 적고
  있었다. **선언이 없어서** 누군가 CI에 손으로 적은 것 — 게이트는 초록인데
  `pip install .`은 그걸 안 준다.
- Changed: CI가 `serving` extra를 **이름으로 요구**하도록 정리(`.[dev,state,observability,serving]`).
  ⚠️**설치 집합은 바꾸지 않았다** — `serving`을 `uvicorn[standard]`로 맞췄다.
- Verified(⚠️**내 근거가 도구에 안 맞았다**): 처음엔 *"코드가 `uvloop`를 임포트 안 하니
  `[standard]`는 불필요"*로 평범한 `uvicorn`을 선언했다. **틀린 추론이다** — 그건 **uvicorn이
  내부에서 쓰는 것**이지 우리 코드가 임포트하는 게 아니라, `src/` grep으로는 답할 수 없다.
  게다가 **CI를 여기서 돌려 볼 수단이 없다**. ⇒ **한 번에 하나만 바꾼다**: 우회는 제거하되
  러너에 떨어지는 패키지는 그대로.
- Verified(가드 +4, `test_optional_dependencies_declared.py` 확장): CI가 `serving`을 요구하는가 ·
  **선언된 패키지를 인라인으로 적지 않는가**(`.[...]` 안의 이름은 오탐 제외) ·
  **문서화된 예외**(`pydantic-ai-slim`은 `onprem`이 Apple 전용 mlx-lm을 끌어 고의 인라인)의
  **이유가 파일에 남아 있는가**. 변이: CI를 옛 방식으로 되돌리면 **3 failed**, 복구하면 23 passed.
  `.[serving]`·CI 조합 둘 다 dry-run 해석 OK. `make check` **2085**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: ⚠️**CI 변경을 검증하지 못했다** — 여기서 워크플로를 돌릴 수 없고 `main`은 D43으로
  push가 막혀 있다. 근거는 "설치 집합 무변경"뿐이고, 틀렸다면 되돌리기는 한 줄이다.
  **이건 측정이 아니라 논증이다.**

## 2026-08-16 — Qwen3.8-27B로 바꿀 만한가: 쟀다. 아니다 (첫 측정은 무효였다)

- Status: 사용자가 전한 요약에 *"27B가 Opus 4.6급"*이 있었는데 원문 대조에서 **비교 대상은
  Opus 4.8**이고 **비교된 건 27B가 아니라 2.4T(활성 95B)**였다. 27B에 대한 원 출처 주장은
  *"자사 Qwen3.7-Plus를 앞선다"* 하나뿐. **논쟁 대신 레포 하네스로 쟀다.**
- Verified(동일 절차 — 서버 교체→준비 대기→**워밍업**→같은 20문항×온도 2단계):
  현재 **30B-A3B 0.95(19/20) / 3.7s·4.2s** vs 후보 **27B 1.00(20/20) / 15.1s·15.6s**.
  라이브 40건·백스톱 0(양쪽). **품질 차 한 문항 = 해상도 ±5%p와 같아 노이즈와 구별 불가** ·
  지연 **최소 4배**. ⚠️재실행에서 19.9s/24.6s(+32%/+58%)라 **정확한 배수는 주장 안 한다.**
  ⚠️활성 파라미터 비 9배보다 **덜** 느렸다(4배) — **내 사전 추정도 틀렸다**(대역폭 바운드).
- Verified(⚠️**첫 측정 무효**): `live calls: 0`인데 `pass=1.00`이 나왔다 — 백스톱 점수였다.
  재현으로 원인 확정: 27B는 추론 모델이라 `max_tokens=16`을 전부 사고에 쓰고 응답에
  **`content`가 없다**(`reasoning`만) → `KeyError` → 백스톱. **하마터면 "27B 완벽"으로
  보고할 뻔했다.**
- Changed(**하네스 가드 구멍**): `if stats["mismatch"]` 가드는 *"다른 모델이 답했을 때"*만
  잡고, **호출이 그 검사에 닿기 전에 죽으면 `calls=0, mismatch=0`으로 통과**시켜 오염된
  스코어보드를 저장했다. **`calls == configs×cases×trials`를 요구**하도록 고쳤다.
  양방향 확인: 오염 조건 → `only 0 of 40 ... nothing persisted`(파일 미생성) · 정상 → 저장됨.
- Verified(재기 전 잡은 함정 넷): `chat_template.jinja` 미다운로드(`allow_patterns`가 `.jinja`
  누락) · 27B 템플릿이 시스템 프롬프트에 226자 주입(기준선은 주입 0) · ⚠️**`low`가 아니라
  `medium`이 깨끗**(직관과 반대) · 스윕의 `effort`는 reasoning이 아니라 **샘플링 온도**.
  최종적으로 **`enable_thinking=false`** 하나로 정리. `make check` **2076**, 로컬 macOS·py3.13.
  증거 `qwen38-27b-ab-measured-not-argued.log`.
- Changed(가드 +5, `test_sweep_contamination_guard.py` 신규): 고친 가드가 **`scripts/`에 있어
  게이트가 안 덮고 있었다** — 지워도 아무도 red가 안 났다. `spec_from_file_location`(레포 선례)로
  `main()`을 실제로 돌린다: 추론-only 응답 → 거부 + **파일 미생성** · 정상 응답 → 저장 ·
  **옛 mismatch 가드도 여전히 동작** · 에러가 원인(`max_tokens`/`reasoning`)을 말하는가.
  변이 5건 red(새 가드 제거 3 · 기대치 무력화 3 · mismatch 제거 1 · 상시 발화 1 · 문구 1).
- Blockers: 없음.
- Next: ⚠️**exit 0 ≠ 작업 완료** — `run_in_background` 안에 `&`를 또 써서 래퍼가 즉시 끝났고
  그 완료 알림을 측정 완료로 읽을 뻔했다. **알림이 무엇의 종료인지 확인할 것.**
  그리고 **사고 모드 품질은 못 쟀다**(하네스가 `max_tokens=16` 하드코딩 — 다른 계측기 일).

## 2026-08-15 — 세 번 어긴 규칙을 약속 대신 가드로 바꿨다 (gate 2073)

- Status: 오늘 문서 예산을 **세 번 어겼고 매번 커밋 후에 알았다**(그리고 `--amend`로 고쳤다).
  "다음부터 커밋 전에 확인하겠다"는 **약속이지 집행이 아니다** — D45가 정확히 그렇게
  참이기를 그만뒀다(→D49). 그래서 가드로 바꿨다.
- Verified(**선언은 셋, 집행은 0**): `.claude/harness-config.json`의 `budgets` ·
  `DOCS_POLICY.md`의 표 · **각 문서 헤더가 스스로 주장하는 값**(`이 파일은 **≤60줄**로 유지한다`).
  오늘은 셋이 일치하지만 **아무도 확인하지 않는다** — M19가 값을 치른 "복사본" 모양이다.
- Changed(가드 +14, `test_doc_budgets.py` 신규): 두 방향 — ①각 문서가 예산 안인가
  ②**세 선언이 서로 일치하는가**(한 곳만 고치면 red). 예산은 `harness-config.json`을
  단일 출처로 읽는다(스킬들이 이미 그걸 읽는다). **코드 변경 없음.**
- Verified: 변이 M1~M4 전부 red(STATUS 1줄 초과 · config 상향 · 표 변경 · 헤더 주장 변경).
  ⚠️**M5(비공허 검사 무력화)는 생존** — 앞과 같이 숨기지 않는다. 진짜 실패 모드를 따로 물었다:
  **예산을 통째로 비우면 2 failed**(`test_the_policy_table_has_no_extra_rows`가 잡는다) ⇒
  비공허 assert는 보호가 아니라 문서다. `make check` **2073 · 36.73s**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: ⚠️**내 가드가 자기 창을 물었다** — `_header_claim`이 앞 12줄만 봐서 `AGENT_BRIEF`의
  선언(23번째 줄, `▶ NEXT SESSION` 블록 뒤)을 "없음"으로 읽고 red를 냈다. **문서가 아니라 내
  윈도우에 대한 답이었다**(Risk 12④). 전체를 훑도록 고쳤다. 그리고 ⚠️**변이 무효가 오늘
  네 번째**(JSON을 깨뜨림) — 기준선 먼저 찍기가 매번 잡아 준다.

