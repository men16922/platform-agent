# PROGRESS_LOG Archive — August 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 8월 이력입니다. 최신이 위.

---

## 2026-08-30 — Azure는 하지 않은 조치를 "해결됨"으로 보고했다 — 배선했고, 게이트 숫자가 내려갔다 (gate 2332)

- Status: 승인 사안이었다(08-16 발견, 배선하면 라이브 ARM/AKS를 친다). 사용자 승인 후 배선.
  진입점 셋이 13일간 `▶ NEXT SESSION` 첫 행동으로 가리켜 온 항목이다.
- Verified(**기록된 근거를 먼저 다시 돌렸다**): 디스패치 비대칭 유효(gcp 325줄 러너를 부르고
  azure 311줄은 안 부른다) · `_execute_aks_call`의 롤백 분기가 **patch 직전 이미 GET을 한다**
  ⇒ Phase 3② 배선도 **추가 API 호출 0**, GCP에서 성립한 근거가 그대로 성립.
- Changed(**배선**): `azure/executor.py`가 `run_azure_action`을 `resolve_incident_scope`와 함께
  부른다(GCP와 같은 모양, 발명 없음). 미구현 11종은 러너의 `ValueError`가 `except`를 타고
  **`success: False`**가 된다 — 조용한 성공이 안 된다. `azure_runner` AKS 롤백에 `guard_rollback`.
- Changed(**기록 둘이 같은 커밋에서 움직였다 — 설계된 결합**): `EXPECTED`의 azure 면제 →
  `{run_azure_action}` · `JUSTIFIED_GAPS` **비었다**(그 항목이 자기 만료 조건을 적어 뒀고
  `test_a_justified_gap_that_closed_must_be_removed`가 집행했다).
- Changed(**가드 +9**): 신규 `test_executor_reports_only_what_the_runner_did.py`(**+7**) —
  AST는 *"호출이 소스에 있나"*는 물어도 ***"성공이라 보고한 것이 실제로 일어났나"는 못 묻는다***.
  gcp·azure 둘 다에 대고 러너 호출·실패 전파·`resolved` 판정을 묻는다(형제 하나만 순회 금지,
  `WIRED`가 디스패치 표와 어긋나면 red). 면제 표가 비어 **하중 없는 규칙이 된 둘**은 합성 표에
  대고 한 번 더 물었다(**+2**) — **실패할 수 없는 규칙은 규칙이 아니다**(Risk 12③).
- Verified(**⚠️예상 못 한 것 — 비대칭 7건이 한 번에 닫혔다**): `test_contract_symbol_parity`가
  red. 배선이 Azure를 스코프/reconciler 계약 표면에 닿게 만들어 `guard_rollback`·`IncidentScope`·
  `resolve_incident_scope`·`guard_scoped_action`·`IsolationTier`·`Registry`·`load_registry`의
  정당화가 stale이 됐다. M29의 *"one cause, six symptoms"*가 **반대 방향으로 확인된 것**이다.
  ⚠️그 파일의 공허성 검사(`>= 20`)가 26→19로 red가 됐고 **초록으로 가는 길이 숫자를 내려 적는
  것뿐**이었다 — 그건 이 파일이 스스로 이름 붙인 *allowlist nobody prunes*다. **구조적 양성
  대조로 교체**(`paginated_scan=={aws}` · `run_gcp_action=={aws,gcp}`) — 결함이 닫혀도 안 낡는다.
- Verified(**변이 6종 red, 생존 0**): 호출 삭제(**4 failed** — AST 표 + 행동 셋이 다른 각도로
  잡는다) · except가 success:True · `guard_rollback` 삭제 · `WIRED`에서 azure 제거 · 면제 규칙 둘
  무력화. 기준선 먼저 찍고 `__pycache__` 삭제 후 복구 확인(35 passed, 기준선과 동일).
- Verified: `make check` **2332 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
  ⚠️**숫자가 내려갔다**(2337에서 −5) — 분해: 정당화 7건 해소 **−14**(parity가 양쪽에
  파라미터라이즈) · 새 행동 가드 **+7** · 공허성 둘 **+2**. **결함이 닫히면 그 결함을 설명하던
  줄도 사라진다** ⇒ 게이트 숫자는 단조증가 지표가 아니다. **줄어든 숫자는 분해해 적을 것.**
- Blockers: 없음. **blast radius는 오늘 0**(러너가 만지는 AKS·FunctionApp 둘 다 구독에 0개) —
  ⚠️**오늘의 사실이지 불변식이 아니다**. 자격증명 테넌트 바인딩은 여전히 Phase 4(Risk 10).
- Next: **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정) · **Phase 3② AWS 잔여**
  (SSM Automation 경로라 러너가 없다 — 가드가 그 사실을 박아 뒀다).

## 2026-08-30 — 인용된 마일스톤 넷이 기록된 적이 없었다 (gate 2337)

- Status: `/tidy-docs` 3단계(완료분을 `COMPLETED_SUMMARY`로 압축)를 하려다, **진입점이 M34~M37을
  인용하는데 `COMPLETED_SUMMARY`는 M33에서 끝나 있는 것**을 봤다.
- Verified(**가드가 있었는데 이 모양을 못 봤다**): `test_milestone_pointer_claims`는 바로 그 실패
  (*"/checkpoint의 compress-into-completed 단계가 여섯 번 건너뛰어졌다"*)를 위해 쓰인 파일인데,
  **`COMPLETED_SUMMARY **Ma~Mb**` 범위 인용만** 검사한다. 문서가 그사이 **개별 이름(`M35`)으로
  가리키게** 바뀌었고, 그래서 **넷이 빠진 채로 초록**이었다. 오늘 `test_amp_bill_claims`가 §10은
  검사하면서 경로를 자기가 들고 있어 문서의 경로 상실을 못 본 것과 **같은 모양**이다 —
  **한 형식을 검사하는 가드는 다른 형식을 안 본다.**
- Changed(**M34~M37 기록**): archive의 원본 증분에서 뽑아 형식대로 썼다. M34=계약 세 형식 중 walk가
  둘만 물었다(도크스트링은 셋을 정확히 열거했다) · M35=ⓐ는 현행 유지, 스윕이 결함 넷(⚠️**내 픽스처가
  한 번 틀렸다** — 쌍 키를 잘못 걸어 "전부 미구현"으로 읽었고 주장 전에 잡았다) · M36=가드가
  **생산에서 도달 불가한 입력**으로만 통과했다 · M37=티어 2가 **조건 평가 없이** 추천에서 액션.
- Changed(**M38 = 오늘의 4a 종료**): 청구 $0.00 · 사유는 `Always Free` 40M · 교차 확인 2.4% ·
  유출 0 · ⚠️믿으면 안 되는 요약 둘("어차피 공짜"·"$1.42"). 이걸로 `NEXT_PLAN`의 닫힌 4a 블록을
  **4줄 → 2줄 포인터**로 줄였다(120 → 118줄).
- Changed(**가드 +4**): 같은 파일에 **맨 `Mnn` 인용도 실재해야 한다**를 더했다(BRIEF·STATUS·NEXT_PLAN).
  ⚠️`\bM(\d+)\b`는 `40M`·`15.8M`을 안 잡는다(숫자가 M 뒤에 와야 한다) — 라이브 문서에 대고 확인하고 박았다.
- Verified(**변이 3종 red**): **M34~M37 다시 지우기**(오늘 이전 상태 재현) · M35 제목만 깨뜨리기 ·
  인용 정규식 무력화. 복구 확인 전에 `__pycache__` 삭제.
- Verified: `make check` **2337 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. **예산**: brief 60/60·6,698자 · status 120/120·9,074자 · plan **118**/120·9,417자 · log 99/120.
- Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정).

## 2026-08-30 — /tidy-docs: 줄 예산은 통과하는데 글자가 불고 있었다 (gate 2333)

- Status: 예산 **초과는 없었다**(brief 60/60 · status 120/120 · plan 120/120 · log 71/120).
  그런데 **줄 수는 예산 지표일 뿐 실제 컨텍스트 비용이 아니다**. 글자로 재니 다른 그림이 나왔다.
- Verified(**가드가 볼 수 없는 곳에서 자랐다**): `AGENT_BRIEF`가 **9,783자**였고 **한 줄이 3,621자**
  (파일의 **37%**) — 오늘 내가 여덟 번 늘린 `직전 세션` 줄이다. 스스로를 *"1분 압축 문맥"*이라
  부르는 문서가 그럴 수 없는데, **가드는 개행만 세어서 볼 수 없었다.** Risk 12④ 계열
  (*가드가 문서가 아니라 자기 창에 대해 답한다*)이 예산 가드 자신에게서 났다.
- Changed(**압축**): 그 줄을 **3,621자 → 472자**로 줄이고 상세는 `PROGRESS_LOG`·archive를 가리키게
  했다. ⚠️**먼저 아홉 묶음이 전부 log 또는 archive에 있는지 확인하고** 줄였다(전부 있었다).
  진입점 4개 합계 **32,569자 → 29,549자**.
- Verified(**⚠️압축이 만든 dangling 포인터를 잡았다**): 세 문서가 전부 *"계획서 §9/§10이 권위"*라고
  하는데 **어느 계획서인지 아무도 안 적고 있었다** — 오늘 줄을 줄이며 파일명을 떨어뜨렸다.
  `docs/plans/2026-08-15-4a-remote-write-allowlist.md`를 셋 다 복원했다. ⚠️`test_amp_bill_claims`가
  그 §10을 검사하지만 **경로를 자기가 들고 있어** 문서가 경로를 잃어도 초록이었다.
- Verified(**plans는 안 옮겼다 — 이득이 없다**): 12개 중 참조 0인 건 **3개뿐**이고 나머지는
  **테스트·DECISIONS가 참조**한다(`test_iam_wildcard_justified` → `2026-08-08-phase4-scope-and-cost`).
  게다가 plans는 **시작 컨텍스트에 안 실린다** ⇒ 옮겨도 컨텍스트가 안 줄고 참조만 깨질 수 있다.
- Changed(**가드 +5, 사용자 승인**): `char_budgets`를 config에 **한 곳만** 선언하고
  (brief 8,000 · status/plan 11,000 · log 12,000) `TestEveryDocIsWithinItsCharacterBudget`가 집행한다.
  ⚠️**네 번째 철자를 만들지 않았다** — 줄 수는 이미 config·`DOCS_POLICY`·각 문서 머리말에 세 번 있다(M19).
- Verified(**변이 3종 red**): **줄 수를 그대로 두고 BRIEF만 3,100자 늘리기**(오늘 아침 상태 재현) ·
  `char_budgets` 키 삭제 · 형제 셋 누락(공허 방지). ⚠️복구 확인 전에 `__pycache__`를 지웠다 —
  오늘 배운 것을 바로 썼다.
- Verified: `make check` **2333 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. **여유**: brief 1,317자 · status 1,941자 · plan 1,412자 · log 7,781자.
- Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정).

## 2026-08-30 — 체크포인트가 잡은 것: 문서 셋이 자기 자신과 모순이었다 (gate 2328)

- Status: `/checkpoint` 절차대로 상태를 수집하다 **진입점 셋의 `최종 갱신`이 그대로**인 걸 봤다.
  오늘 아홉 번 내용을 고쳤는데(게이트 숫자·리스크 정정·항목 닫기) 머리말은 08-18/08-17이었다.
- Verified(**문서가 자기 자신과 어긋난다**): `STATUS` 3줄은 *"최종 갱신: 2026-08-18"*인데 11줄은
  **2026-08-30**에 돌린 게이트를 기록한다. `AGENT_BRIEF`·`NEXT_PLAN`도 같다. ⚠️`AGENT_BRIEF` 자신이
  **"게이트 숫자는 날짜와 잰 기계 없이는 주장이 아니다"**(Risk 12①②)라고 적어 뒀고, 그 **날짜 쪽을
  검사하는 가드가 없었다** — `test_gate_number_claims`는 **숫자만** 본다(그건 의도적이다: *"a test
  cannot re-run yesterday"*).
- Changed: 세 머리말을 **2026-08-30**으로 고쳤다. 그리고 `test_doc_freshness_claims.py`(+9) —
  **`최종 갱신`이 그 문서가 스스로 말하는 가장 늦은 날짜보다 이르면 red**. ⚠️"그 날짜에 정말
  쟀는가"는 여전히 **안 묻는다**(기계가 어제를 다시 돌 수 없다) — **내부 모순만** 묻는다. 그건
  전부 기계적이고, 오늘 실제로 일어난 드리프트를 정확히 잡는다. 짧은 형식(`08-15에`)은 **일부러
  무시**한다: 연도 없는 날짜를 머리말과 견주려면 연도를 **추측**해야 하고, 추측하는 가드는 1월에 틀린다.
- Verified(**변이 4종 red**): 오늘 실제로 있던 상태(STATUS 날짜만 되돌리기) · 머리말 문구 변경
  (찾을 수 없는 주장) · 날짜 정규식 무력화(공허 방지) · 공허 검사 자체.
- Verified(**⚠️내 복구 확인이 `.pyc`에 속았다 — 08-09에 기록된 그 함정**): 변이 하네스가 복구 후
  **"1 failed"**를 답해 *"초록으로 안 돌아오는 복구는 복구가 아니다"*(Risk 12⑤)로 읽었는데,
  디스크의 파일은 **정상 복구돼 있었다.** `__pycache__`를 지우니 **9 passed**. ⇒ 변이 하네스의
  **복구 확인 앞에 캐시를 지울 것** — Risk 12⑦(변이 하네스 자신이 틀린다)에 하나 더.
- Verified: `make check` **2328 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. 이 세션의 나머지 증분은 이미 각자 기록·병합됐다(PR #44~#53).
- Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정) ·
  **analyzer/decision 계약 추출**(승인).

## 2026-08-30 — "SDK가 90%+ 상이"를 재다: detector엔 맞고, 나머지 둘엔 다른 걸 말한다 (gate 2319)

- Status: 유지 규약이 구조적 결정(**DRY 안 함**)을 **수**로 떠받치는데 잰 기록이 없었다. 쟀다.
  증거 `docs/evidence/the-dry-exemption-was-right-about-detector-and-quiet-about-two.log`.
- Verified(**SDK는 3~5%다**): provider SDK 심볼에 닿는 줄은 aws **2.9%** · gcp **4.7%** · azure **3.9%**.
  "SDK가 90%+ 상이"는 **SDK 부분에 대해선 참일 수 있지만 그 부분이 파일의 4%**다.
- Verified(**그래서 나머지는 절반 넘게 같다**): 8줄 이상 **글자 그대로 같은** 블록(gcp↔azure) —
  `detector` **0줄**(D15 말 그대로) · `analyzer` **95줄=51%** · `decision` **135줄=56%**.
  ⇒ **detector엔 규약이 옳고**, 나머지 둘에 대해선 **다른 것**을 말하고 있다(다른 건 SDK가 맞지만
  같은 부분은 **계약**이다).
- Verified(**⚠️유사도를 의미로 읽지 말 것**): 가장 달라 보인 `_determine_mode`(27.4%)를 제일 먼저
  열었는데 — 그게 **D48(파괴적 액션 강제 APPROVE)을 집행하는 함수**다. 셋이 **의미상 동일**했고
  차이는 docstring과 dict-조회 vs if/elif뿐이었다. **낮은 유사도가 결함 신호가 아니고 높은 유사도가
  안전 신호도 아니다.** 반대로 94%/89.8%로 닮은 `_build_prompt`·`_select_runbook`의 차이는 **전부
  정당한 SDK 어휘**였다(Cloud Logging↔Log Analytics 필드명, Firestore↔Cosmos 조회).
- Verified(**진짜 비대칭 하나 — 그리고 이미 닫혀 있다**): `_fallback_analysis`가 **gcp·azure에만** 있다.
  LLM이 죽으면 gcp/azure는 reason 키워드로 **P1**(conf 0.3)을 내고 `_determine_mode`는 **P1→AUTO**다
  (AWS는 P2 하드코딩 → APPROVE). 끝까지 따라가니 **닫혀 있다**: `reconciliation.py:98`이
  `P1 and confidence < 0.5`를 잡고 `apply_gate`가 **AUTO→APPROVE로 내리기만 한다**. 그 게이트는
  08-16에 gcp/azure로 확장된 것이고 주석이 *"P1 asserted at low confidence"*를 이미 명시한다.
  **도착지는 AWS와 같고 경로만 다르다 — 결함 없음.**
- Verified(**⚠️내 도구가 거짓 음성을 냈다 — 세는 함정 셋째**): 위를 조사하며
  `git grep -nE "confidence\s*[<>]..."`로 물었더니 **0건**이라 "임계값이 없다"로 읽을 뻔했다.
  **`git grep -E`는 POSIX ERE라 `\s`가 없다** — `[[:space:]]`나 `-P`로 물으니 바로 나온다.
  `NEXT_PLAN`의 세는 함정 목록에 **셋째로** 적었다(`cdk.out` · docstring 예시 다음).
- Changed(**추출이 아니라 가드, +8**): 230줄 구조 변경은 작업 규칙상 승인 후라 **안 했다.** 대신
  M18/M19 이후 레포가 스스로 적은 정제를 적용했다 — **바이트 동일 7쌍**을
  `test_cross_provider_contract_parity.py`가 **표로** 박는다. ⚠️**스윕이 아니라 표**다(우연히 같은
  함수를 훑으면 조용히 자라고 의도적 분기가 미스터리 실패가 된다). 규약 문구도 고쳤다 —
  **결정은 유지하고 근거만 정확히**.
- Verified(**변이 3종 red**): ⓐ**gcp `_fallback_analysis`에만 키워드 추가**(정확히 "한쪽만 닿는 고침") ·
  ⓑazure `_deserialise_analyzer` 이름 변경 · ⓒ표 비우기(공허 통과 방지). 복구 후 8 passed.
- Verified: `make check` **2319 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. ⚠️`_build_prompt`의 **레이블이 세 갈래**(`reason`: Reason/**Summary**/Reason)인 건
  물었지만 **결함으로 세지 않았다** — provider마다 **다른 LLM**을 쓰고 영향을 보이려면 모델 셋을
  돌려야 한다(D49가 네트워크를 막는다).
- Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정) ·
  **analyzer/decision 계약 추출**(승인 — 표가 그때까지 드리프트를 막는다).


## 2026-08-30 — 문서화된 `make dev-up`이 새 클론에서 못 돌았다 (gate 2311)

- Status: `AGENT_BRIEF`가 *"`make dev-up`으로 로컬 스택 **한 방 기동**"*이라 적어 뒀다. 그 약속을
  **새 클론 관점**에서 물었다. 증거 `docs/evidence/make-dev-up-launched-a-venv-nothing-created.log`.
- Verified(**쓰는 곳 셋, 만드는 곳 0**): `mlx-serve`·`local-llm-up`·`dev-up`이 `.venv-mlx/bin/mlx_lm.server`를
  띄우는데 **그 venv를 만드는 타깃이 없다**. gitignore돼 있고 이 기계에 **손으로** 만들어져 있었다.
- Verified(**`.[onprem]`의 산물도 아니다**): 그 venv엔 mlx-lm·mlx가 있고 **`platform-agent`도
  `pydantic-ai-slim`도 없다**(36개). ⇒ **`onprem` extra는 mlx-lm이 설치되는 경로가 아니다.** ⚠️그런데 그
  항목이 **CI에 비용을 물린다** — `gate.yml`이 그것 때문에 `pydantic-ai-slim`을 **인라인으로** 적는다
  (fastapi에 대해 이미 한 번 고친 우회). 그리고 그 근거 *"linux에서 resolve 안 된다"*는 **하한 0.19.0엔
  참**이었고(당시 `mlx>=0.17.0`에 마커 없음) **지금은 거짓**이다(현재 `mlx`에 Darwin 마커 → **설치되고
  엔진만 조용히 빠진다**). **실패 모양이 시끄러운 것에서 조용한 것으로 바뀌었다.**
- Verified(**그래서 조용히 깨진다**): 세 지점 중 **둘이 `nohup ... &` + stdout을 로그로** 보낸다. 새
  클론의 `dev-up`은 *"model load takes ~30-60s"*를 찍고 **계속 진행**하며, 프록시는 그다음 **아무것도 없는
  곳에 말을 건다.** Risk 7·8과 같은 계열이다.
- Changed: `make mlx-setup`(없을 때만 생성) + 세 지점에 **실행 전 검사**. ⚠️`dev-up`의 검사는 **실제로
  띄우려는 분기 안**에 뒀다 — 이미 떠 있는 MLX를 재사용하는 경로엔 venv가 필요 없고, 거기서 막으면
  **없는 요구사항을 만드는 것**이다. 실측으로 확인했다(venv를 잠시 옮겨 두고 `mlx-serve`·`dev-up` 둘 다 red).
- Verified(**⚠️내가 만든 가드가 한 번 틀렸다 — 그대로 기록한다**): `mlx-setup` 첫 판이
  `@test ! -x ... || { echo; exit 0; }`를 **자기 줄에** 뒀는데 **Make는 레시피 줄마다 셸이 따로**라 그
  `exit 0`이 다음 줄을 못 막았고 **pip가 기존 venv에 그대로 돌았다**(최신이라 아무것도 안 바뀌었음을
  36개 패키지·서버 바이너리로 확인). ⇒ **뒤따르는 것을 막지 못하는 검사는 검사가 아니다** — 이 레포가
  한 층 위에서 계속 찾던 그 모양이 내 손에서 났다. 한 셸 블록으로 고쳤다.
- Changed(**가드 +5**): `test_local_stack_prerequisites.py` — 만드는 타깃이 있는가 · **모든 실행 지점이
  실행 전에** 검사하는가(**순서까지**) · 실행 지점이 셋 이상 찾아지는가(공허 방지).
  ⚠️`.venv-mlx` **존재는 일부러 단언하지 않는다**(gitignore·기계별·Apple Silicon 전용 — CI에서 red가 나면
  약속이 깨진 게 아니라 **가드가 틀린 것**이다). 변이 4종 red(타깃 삭제 · 검사 제거 · **검사를 실행 뒤로
  이동** · 경로 철자 깨기).
- Verified: `make check` **2311 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. `onprem` extra의 `mlx-lm` 처리는 **결정 사안**으로 `NEXT_PLAN`에 올렸다(⚠️`mlx`가 CUDA
  리눅스도 지원한다고 해서 Darwin 마커가 옳은지는 자명하지 않다).
- Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정).


## 2026-08-30 — 두 번 "미검증"이라 적어 둔 주장을 재다: 거짓이었다 (gate 2306)

- Status: `AGENT_BRIEF`와 `STATUS` Risk 12②가 **두 번** *"`requires-python = ">=3.11"`은 아무도
  확인한 적 없는 주장"*이라 적어 뒀다. 이 기계에 python3.11이 있는 걸 보고 **처음으로 쟀다**.
  증거 `docs/evidence/requires-python-was-an-unverified-claim-and-it-was-false.log`.
- Verified(**첫 시도는 내 잘못 — 기록해 둔다**): `.[dev]`만 깔고 돌리니 **수집 에러 7개**(`fastapi` 5 ·
  `pydantic_ai` 2)가 나 M25 계열로 보였다. **아니었다** — `fastapi`는 `serving`, `pydantic-ai-slim`은
  `onprem`에 **선언돼 있고** CI는 `.[dev,state,observability,serving]`+`pydantic-ai-slim[openai]`를 깐다.
  ⚠️**"게이트가 red다"라고 말하기 전에 CI와 같은 줄로 깔았는지부터 물을 것.**
- Verified(**3.11은 red**): CI와 같은 줄로 다시 깔고 → **2 failed, 2300 passed**. ①SSE 스트림이
  `done` 대신 `error`로 끝난다(anyio *"exit cancel scope in a different task"*) ②monkeypatch가
  `time.sleep`에 심은 `StopIteration`이 루프를 빠져나온다.
- Verified(**⚠️결론 전에 교란 요인을 지웠다**): 3.11 venv는 오늘 새로 해석돼 이 기계의 오래된 3.13보다
  **최신 패키지**를 받았다(starlette **1.6.0 vs 1.3.1** · pytest **9.1.1 vs 8.3.4**). 그래서 실패가
  **인터프리터 탓인지 의존성 최신화 탓인지 아직 몰랐다.** ⇒ **fresh 3.13**을 같은 줄로 만들었더니
  **3.11과 같은 버전으로 해석**되고 **2302 passed 초록**이었다. **같은 의존성·다른 인터프리터** ⇒
  **인터프리터 탓이고 주장은 거짓**이다. ⚠️곁가지: 이 기계의 상시 3.13 환경이 **stale**하다는 것도
  드러났다(둘 다 초록이라 다행이지만, **그건 확인해서 안 것이지 가정한 게 아니다**).
- Changed(**선언을 측정에 맞췄다**): `requires-python` `>=3.11`→**`>=3.13`** · ruff `target-version`
  `py311`→`py313` · mypy `python_version` `3.11`→`3.13`. **셋은 한 결정의 세 철자**였고 셋 다 틀린 수를
  들고 있었다(M19). ⚠️**좁혀도 안전한지 먼저 물었다** — 워크플로가 둘이고 **파이썬이 다르다**
  (`gate.yml` 3.13 · **`sign-image.yml` 3.11**). 형제를 안 셌으면 여기서 깨졌다: 실측 결과 그 워크플로엔
  **`pip install`이 0개**고 돌리는 스크립트가 **표준 라이브러리만** 쓴다 ⇒ 영향 없다.
- Verified(**곁가지 — `[tool.mypy] strict = true`는 아무도 안 돈다**): Makefile·CI·scripts·pre-commit
  어디에도 mypy 호출이 없다(`.mypy_cache` 흔적만). 실측 **253 errors / 88 of 165 files**. **안 지웠다** —
  게이트에 넣는 건 `gate.yml`이 lint에 대해 적어 둔 것과 같은 결정이다(*"a CI job is a bad place to
  introduce a standard nobody agreed to"*). 대신 **주석으로 사실을 적고** 가드가 그 주석을 지키게 했다.
- Changed(**가드 +4**): `test_pyproject_claims.py` — 세 버전 선언 일치 · 바닥이 돌리는 인터프리터보다
  높지 않음 · **`[tool.X]`는 불리거나 왜 안 불리는지 적혀 있어야** · 공허 방지. ⚠️게이트가 선언된
  바닥에서 통과하는지는 **일부러 단언하지 않는다**(스위트 안에서 다른 인터프리터로 스위트를 도는 일).
- Verified: `make check` **2306 passed, 2 skipped**(로컬 macOS·py3.13) · ruff 20으로 결정론 유지.
- Blockers: 없음. Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) ·
  **mypy/lint를 게이트에 넣을지**(결정 — 각각 253·20건이 선행).

## 2026-08-30 — Tier B 수행: 대시보드 취약점 8 → 0, 그리고 "새 소견 0"을 재서 말했다 (gate 2302)

- Status: 승인 후 Tier B(`next 16.2.10 → 16.3.3`)를 적용했다. **소스 변경 0** — `package.json` 2줄과
  lockfile뿐이다. 증거는 같은 로그의 **§Tier B 수행**.
- Verified(**8 → 0**): `npm audit`이 **critical 0 · high 0 · total 0**. Tier A(`audit fix`)가 critical 2를
  0으로 내렸고 남아 있던 high 3(next·postcss·sharp)이 전부 이 업그레이드에 달려 있었다. peer는 맞는다
  (16.3.3이 `react ^19.0.0`을 요구하고 대시보드는 **19.2.4**).
- Verified(**조용히 실패하는 쪽을 겨눴다**): `tsc` 통과 · `build` **exit 0** · ⚠️**라우트 매니페스트를
  before/after로 대조**해 **17개 완전 동일**을 확인했다. Risk 7·8이 가르친 모양이다 — 타입은 초록인데
  런타임이 죽고, 차트는 Synced인데 파드가 0개였다. **빌드가 통과했다는 것과 같은 걸 냈다는 건 다르다.**
- Verified(**⚠️"기존 것"을 가정하지 않고 쟀다**): `npm run lint`가 **41 problems**를 낸다. 소스를 안
  건드렸으니 기존 것이라 **말할 수는 있었지만**, `react-hooks/set-state-in-effect`가 새 룰일 수 있어
  `git worktree`로 **main을 따로 체크아웃해 `npm ci` 후 같은 명령**을 돌렸다 → **41 problems (33 errors,
  8 warnings)**로 **완전히 동일**, 룰 분포까지 같다. ⇒ **새 소견 0.** 의심을 사실로 바꾸는 데 worktree
  하나면 충분했다. (대시보드 eslint는 게이트도 CI도 아니다 — `gate.yml`이 그 이유를 적어 뒀다.)
- Changed: `STATUS` Risk 11 **해소**로 전환하되 ⚠️**"기록이 세 군데 다 틀렸다"는 남겼다** — 결론이
  닫혔다고 그 항목이 왜 틀렸는지가 지워지면 같은 방식으로 다시 닫힌다. `NEXT_PLAN`의 Tier B 결정 항목은
  ⛔닫힘으로 옮겼다.
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13) — py 쪽 변경 0.
- Blockers: 없음.
- Next: **Azure executor 배선**(승인 — 근거는 08-30에 다시 세워 뒀다) · **BQ 결제 내보내기**(콘솔 수동) ·
  **`make lint` 20건 처리 여부**(결정).


## 2026-08-30 — "업스트림 대기" 둘의 재개 조건을 재다: 하나는 열렸고, 하나는 다른 리스크였다 (gate 2302)

- Status: 남은 항목이 승인·콘솔 수동에 몰려 있어, **닫혀 있던 "업스트림 대기" 항목들의 재개 조건**을
  쟀다. 둘 다 기록이 낡아 있었고 **한쪽은 리스크의 성격 자체가 달랐다**. 증거 둘:
  `the-azure-extra-cannot-be-installed.log`(기존, 조건 갱신) ·
  `docs/evidence/the-dashboard-audit-record-described-a-different-risk.log`(신규).
- Verified(**`.[azure]` — 재개 조건 ①은 충족됐다**): 격리 venv(py3.13)에서 `pip install .[azure]`가
  **31.5초에 성공**한다. 08-15엔 `agent-framework>=1.0` 단독으로 **150초 타임아웃**이었다
  (`core[all]` 강제 → 무한 역추적). 지금은 **1.16.0**이고 `Provides-Extra: []` — 업스트림이 풀었다.
- Verified(**②는 미충족이고, 버전 지연이 아니다**): 진짜 라이브러리에 대고 태우니 `msft_deployer.py:19`가
  `ImportError: cannot import name 'AzureOpenAIResponsesClient'`로 죽는다. 설치 트리를 훑으니
  **`AzureOpenAI*Client` 클래스가 0개**고, 그 이름은 **업스트림 자신의 docstring 한 줄**에만 있다
  (`agent_framework_azure_contentunderstanding/_file_search.py:78`). ⇒ **여전히 안 고친다 — 대체 심볼이
  없으므로 추측은 발명.** 형제 스윕: adk/local은 **자기 extra 미설치**일 뿐이고(둘 다 선언돼 있다)
  strands는 임포트된다 — **자기 extra가 깔린 채 죽는 건 msft 하나**다.
- Verified(**⚠️Risk 11 — 기록이 세 군데 다 틀렸다**): *"PostCSS moderate 2건 · 패치 없음 · 빌드타임이라
  런타임 위험 낮음"*인데 실측은 **critical 2 · high 6**이고 **런타임**이다. `next-auth`가 *"auth checks
  **fail open**"*(critical)인데 **런타임 8파일**에 있고 그중 하나가 **승인 UI**(`pending-approvals`) ·
  next는 **미들웨어 우회·SSRF·내부 Server Function 노출** · PostCSS조차 이제 **high**(임의 `.map` 읽기).
  ⚠️**기록의 반증 실험이 `--force` 하나였다** — non-force는 **메이저 강등이 없다**. 하나의 경로에서 얻은
  답을 항목 전체의 성질로 쓴 것이고, 08-18의 *"거부가 러너 하나의 성질이었다"*와 같은 모양이다.
- Changed(**Tier A만 적용**): `npm audit fix` → **critical 2 → 0**(총 8→3). 변경은 **lockfile 32줄**이고
  **package.json은 그대로**다. `npx tsc --noEmit` 통과 · `npm run build` **exit 0**(라우트 전부 생성).
  ⛔**Tier B는 안 했다**: 남은 high 3(next·postcss·sharp)이 **`next@16.3.3`**에 달렸는데 major는 아니어도
  **프레임워크 마이너 업**이고 이 대시보드는 **조용히 강등된 이력**이 있다(Risk 1) → **결정 사안**.
- Changed(**측정이 남긴 것도 치웠다**): `pip install .`이 리포 루트에 **`build/`를 남기는데 gitignore에
  없었다** — 지우고 `.gitignore`에 넣었다(커밋될 수 있던 함정).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. ⚠️**Risk 11을 "upstream 대기"로 다시 닫지 말 것** — 업스트림은 이미 고쳤다.
- Next: **Tier B 결정**(`next@16.3.3`) · Azure executor 배선(승인) · BQ 결제 내보내기(콘솔 수동).


## 2026-08-30 — 승인 대기 항목의 근거를 재다: 결론은 살아남고, 적힌 목록이 틀렸다 (gate 2302)

- Status: 남은 항목이 대부분 승인·업스트림·콘솔 수동이라, **가장 값싼 다음 수 = 승인을 떠받치는
  기록된 근거를 재는 것**이었다. Azure executor 항목의 근거 셋을 물었다. 코드 변경 0.
  증거는 `docs/evidence/azure-executor-reports-resolved-without-executing.log` **§정정 2026-08-30**.
- Verified(**디스패치 비대칭은 유효**): 러너 파일은 gcp 325 · azure 311 · onprem 226줄, aws는 없다
  (SSM 경로). **executor가 자기 러너를 부르는 건 GCP 하나** — 08-16 그대로이고 `test_executor_
  dispatches_to_runner.py`가 AST 호출로 집행한다.
- Verified(**⚠️"순수 잠재"의 근거가 틀렸다 — 결론은 아니다**): 08-16이 적은 *"구독에 Function App·
  AKS·Cosmos 전부 없다"*를 재니 FunctionApp **0** · AKS **0**은 맞고 **Cosmos는 1개 있다**
  (`cosmos-roadpilot`). `az cosmosdb list`의 `systemData.createdAt`이 **2026-07-14** —
  그 측정보다 **한 달 먼저**다. ⇒ **stale이 아니라 쓰일 때부터 틀린 기록**(08-15 ⓑ와 같은 모양:
  *"언제부터 있었는지까지 물어야 stale과 오기를 가른다"*). ⚠️그리고 `rg-roadpilot`은 **남의
  프로젝트**다 — 태그·RG를 안 읽으면 남의 자원을 우리 잔재로 설명하게 된다.
- Verified(**그런데 Cosmos는 애초에 러너의 능력 밖이었다**): `azure_runner`가 분기하는 액션은
  **다섯, 리소스 타입 둘**(AKS 3 · FunctionApp 2)이고 그 밖은 `raise ValueError`. **Cosmos 액션은
  하나도 없다.** ⇒ 08-16의 근거는 **세 타입을 손으로 적었는데 하나는 러너가 만질 수 없는 것**이었다
  (Risk 12④ⓐ — 목록이 무엇의 그림자인지부터). **결론은 더 나은 근거로 다시 선다**: 러너가 실제로
  닿는 두 타입이 **둘 다 0** = 배선 시 blast radius **대상 0개**. ⚠️**오늘의 사실이지 불변식은 아니다.**
- Verified(**곁가지 — 선언 16 vs 구현 5는 결함이 아니다**): aws 16/0(러너 없음) · gcp 16/5 ·
  azure 16/5 · onprem 12/4로 **네 provider가 같은 모양**이라 Azure 고유가 아니다. 그리고 **배선된
  쪽의 읽는 지점이 정직하다** — `gcp/executor.py`가 러너의 `ValueError`를 `except`로 받아
  **`success: False`**를 돌린다. 미구현 액션이 "실행됨"으로 보고되지 않는다. ⇒ Azure 배선의
  안전성 논거가 하나 늘었다.
- Changed: 증거 로그에 **§정정** 추가 · `NEXT_PLAN`의 Azure 항목이 이제 **러너 액션에서 유도한
  근거**를 든다. **src 변경 0 · 가드 변경 0**(기존 가드가 목록을 하드코딩하지 않아 손댈 게 없었다).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: **승인 사안 그대로**. 바뀐 건 결론이 아니라 **근거의 질**이다.
- Next: 승인이 오면 Azure 배선(+ **Phase 3② 면제 삭제** — 가드가 red로 요구한다). 무과금 잔여는
  **BQ 결제 내보내기**(콘솔 수동)와 **`make lint` 20건 처리 여부**(신규 결정).

## 2026-08-30 — 같은 함정을 pytest에만 막아 뒀다: ruff는 실행마다 답이 달랐다 (gate 2302)

- Status: 위 증분이 **"미수정, 범위 밖"으로 기록만** 한 항목을 재서 닫았다. 증거
  `docs/evidence/ruff-and-pytest-did-not-exclude-the-same-vendored-trees.log`.
- Verified(**재현 — 같은 명령, 같은 트리, 다른 답**): `ruff check src/ tests/` 10회가
  **20 · 6527 · 20 · 6527 · 6527 · 6527 · 20 · 6527 · 6527 · 20**. 초과분 6,507건이 **전부
  `src/stacks/cdk.out`**(벤더 CDK 자산 4,703 py파일). 캐시를 지우면 첫 실행만 20이고 다시 흔들린다.
- Verified(**원인 = 선언이 아니라 추론**): 두 경로 다 gitignore인데 **pytest만 소리 내어 말했다**
  (`norecursedirs`). `[tool.ruff]`엔 대응 항목이 **없었다**. ⇒ **Risk 12②가 두 번째 도구에서
  재발**(선언되지 않은 것 위에서 통과)이자 **12⑥ 형제 집합의 설정 판** — 같은 함정을 한쪽에만
  막아 뒀다. ⚠️NEXT_PLAN은 **이미 `cdk.out`을 "세는 함정"으로 적어 뒀다**(MCP 항목): 같은
  디렉터리·같은 함정·다른 도구인데 기록이 도구 하나에만 적용돼 있었다.
- Changed: `[tool.ruff] extend-exclude`에 두 경로를 **선언**했다 → 10회 **전부 20**. ⚠️**게이트는
  아니다**(`check: test`) — 나쁜 건 CI가 아니라 `make lint`를 돌린 사람이 실행마다 다른 답을 받고,
  흔들리는 쪽이 **진짜 소견 20건을 벤더 6,507건 밑에 묻었다**는 것이다. **읽을 수 없는 신호는 읽지 않게 된다.**
- Verified(**묻혀 있던 20건 전수 분류 — 결함 0**): F841 8 · E731 5 · E701 5 · F402 1 · E712 1.
  "단언이 빠진 모양"인 **아홉 건을 개별로** 물었다. `azure_runner:275 url`=죽은 변수(분기마다 자기
  URL) · F402=그 함수가 dataclass `field`를 안 씀 · `test_pipeline original_guard`=지역 인스턴스라
  오염 없음 · `test_activity_writer result`=mock의 `put_item`을 단언한다. ⚠️**가장 그럴듯했던 건
  `pipeline.py:218 dep_id`** — `record_deployment()`가 돌려준 id를 버리고 **바로 다음 줄**에서
  ACTIVITY 행을 쓴다(08-18에 "쓸 수 있는데 안 쓴다"로 읽혔던 그 모양). 물어 보니
  **`record_agent_activity`에 `deployment_id` 매개변수가 아예 없다** ⇒ 08-18이 **읽는 쪽**에서
  내린 경계가 **쓰는 쪽에서 독립으로 재확인**됐다. **결함이 아니라 경계다** — 시험은 범위를 줄 때도 값이 있다.
- Changed(**가드 +3**): `test_vendored_paths_are_excluded_from_both_tools.py` — 형제 일치 · 공허
  방지 · **도구에 직접 묻기**(`ruff check --show-settings`). ⚠️**TOML 키는 오타가 나도 파싱된다**:
  `extend_exclude`(밑줄)로 쓰면 ruff가 파일을 받고 키를 **조용히 무시**한다 — 선언을 읽으면 누가
  타이핑했다가, resolved settings를 읽어야 **도구가 동의했다**가 증명된다.
- Verified(**변이 4종 red**): 제외 통째 삭제 · ruff만 한 경로 누락 · **키 오타**(세 번째 방향이
  사는 지점) · **양쪽 다 빈 목록**(형제 일치는 **통과**하고 공허 방지만 red — 그 칸을 메우는 게 요지).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13, 38.0s).
- Blockers: 없음. 20건은 **안 고쳤다**(스타일 · 열 파일 · 범위 밖) — 이제 **읽을 수 있으니**
  고칠지는 결정 사안이고, `make lint`를 게이트에 넣으려면 그게 선행이다.
- Next: **Azure executor 디스패치**(승인 사안) — 그 전에 기록된 근거 *"순수 잠재: 구독에 리소스 없음"*(08-16)을 재는 게 값싸다.


## 2026-08-30 — 4a 마지막 칸: 청구액은 $0.00이었고, 프리티어를 배제한 근거의 전건이 거짓이었다 (gate 2299)

- Status: 13일간 세 진입점이 가리켜 온 마지막 미측정 항목("08-19 이후 AMP 실제 청구액")을 실행했다.
  **PR #44**(Phase DoD 전수 검증)는 CI 초록 확인 후 squash 병합(`4fb4185`). 권위는 계획서 **§10**과
  `docs/evidence/amp-actual-bill-is-zero-and-the-free-tier-reason-was-inverted.log`.
- Verified(**$0.00이고, "목록에 없어서 0"이 아니다**): CE를 **크레딧 제외 필터**로 물으니 AMP는
  08-17부터 **13일 전부 그룹이 존재**하고 금액만 0. `RECORD_TYPE`으로 가르니 **`Credit` 행이 없다**
  — 상쇄가 아니라 **Usage 행 자체가 $0**이다. 계량 **798,331 샘플**·0.0005 GB-Mo·쿼리 920.
  ⚠️계량되고 0인 것과 계량조차 안 된 것은 다른 사실이다.
- Changed(**사유 — 기록의 전건이 거짓이었다**): `aws freetier get-free-tier-usage`가 AMP 행 셋을
  전부 **`freeTierType: "Always Free"`**(40M/월 · 10GB · 200B)로 답한다. §3과 D50은 *"12개월
  한정**이면** 안 붙는다"*는 **조건문**을 세우고 전건을 참이라 가정했다. ⚠️**틀린 기록이 아니다** —
  추론임을 명시했고 **무엇이 확정할지 지목했다**(*"AMP를 켠 뒤 첫 청구서"*). 다만 답은 **이미 그
  계정 데이터 안에 있었다**: 당시 12건이 **전부 "Always Free"**였고 "12 Month Free 0건"은 "창을
  지났다"로도 **"이 계정 프리티어 행은 원래 그 종류뿐"**으로도 읽힌다 — 같은 데이터가 두 결론을
  지탱했고 **비싼 쪽을 골랐다**(보수적이라 안전했다). §3에 정정 박스, §10 신설.
- Verified(**교차 확인 2.4%**): AMP에 직접 물어 잰 실가동 **41.3 수집-시간** × 설계 부하 19,800/h
  = **817,740** vs AWS 계량 **798,331** — 파이프 모델과 청구 계량이 서로를 확인한다.
- Verified(**허용목록 유출 0**): 전체 창에서 workspace가 아는 메트릭 이름이 **정확히 4개**, 시계열은
  **08-17T08:00Z·08-27T12:00Z 두 시점 모두 308**(22/50/220/16 — §2의 네 칸 그대로).
- Verified(**⚠️두 번째 발견 — 파이프는 연속이 아니고 지금 죽어 있다**): 13일 중 **4일만**(11.1h ·
  10.0h · 3.6h · 16.7h), 마지막 샘플 **08-27T19:55Z** — 로컬 **kind**가 Docker와 함께 뜬다(오늘
  `docker info` 실패). duty cycle **13%** ⇒ **$1.42는 720h 연속 가동 가정**이라 이 환경에선 원리상
  안 난다(프리티어가 없었어도 **$0.07**). **가정이 지배하는 추정은 그 가정이다** — 08-15엔 시계열 수, 오늘은 **가동 시간**에서 재성립.
- Changed(**가드 +8**): `test_amp_bill_claims.py`(+6) — 진입점이 **$1.42를 정정 없이 다시 적으면**
  red(±3줄 근접). ⚠️**첫 판은 하중이 없었다**: 문서 단위로 마커를 찾아 한번 고쳐진 문서엔 다시
  red가 안 났다(Risk 12③ 그 모양) → **근접 창으로 바꿨다.** `test_evidence_pointers_resolve.py`(+2)
  — 인용된 `docs/evidence/*.log` 실재 스윕(**측정 후 작성**: 68건·dangling 0). `test_amp_cost_handles.py`는
  계약 그대로 두고 **금액을 한도 대비로** 고쳤다 — 절벽이 40M 한도로 옮겼을 뿐 필터 없음은 **128배 초과**.
- Verified(**변이 7종 전부 red**, 변이·실행·복구 한 스크립트 + 디스크 백업): BRIEF에 정정 없는
  $1.42 삽입 · 세 진입점에서 측정 결과 제거 · 증거 로그 삭제 · §10 제목 변경 · 한도 40M 제거 ·
  인용 정규식 무력화(공허 통과 방지) · 없는 증거 로그 인용. 복구 후 8 passed, 워킹트리 깨끗.
- Verified: `make check` **2299 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13, 36.4s).
  ⚠️**새 가드가 그 자리에서 일했다** — BRIEF를 아직 안 고친 채 처음 돌리자 정확히 그 주장을 red로 잡았다.
- Observed: `make lint`가 실행마다 **20 ↔ 6,527**을 오간다(⛔같은 날 아래 증분이 재서 닫았다).
- Blockers: 없음. ⚠️측정 비용 = CE 2회 $0.02 · 창 전체에서 **CE $0.17이 이 계정 최대 항목**(2위
  EC2-Other $0.0462) — **"무엇이 도는가"를 묻는 게 도는 것보다 비싸다.**
- Next: **Azure executor 디스패치**(승인 사안) — 고치면 **Phase 3② 면제도 같이 지울 것**.


## 2026-08-18 — Phase DoD 전수 검증: Phase 0의 ts 절반과 Phase 3②의 배선이 비어 있었다 (gate 2285)

- Status: 지시 "최대한 많은 phase 검증". 권위는 설계 계획서 §Phases의 **DoD 문장 그 자체**로
  두고, 각 절을 그것을 단언하는 테스트에 맞댔다. 전체 판정표는 증거 로그가 권위.
  `docs/evidence/phase-dod-verification-2026-08-18.log`.
- Verified(**0·1a·2·5 성립**): 1a는 DoD 세 절이 이름 붙은 테스트로 있고 ⚠️**형제를 세는 가드까지
  있다**(`test_every_provider_branch_is_covered_by_the_test_above`) · 2는 `applicable=false`를
  **돈 쓰기 전에** faked 디스크립터로 실증 · 5는 "diff가 단 한 줄 추가"·"관계없는 dirt는 dirty인
  채로"까지 단언한다.
- Changed(**Phase 0 — ts 절반은 아무도 안 물었다**, 가드 +6): DoD가 "로더·타입 검증 **(py/ts)**"인데
  TS를 읽는 테스트가 **0개**였다(같은 기법을 쓰는 파일이 이미 **15개**인데 이 쌍만 빠졌다).
  먼저 "TS가 두 번째 로더인가"를 물었고 **아니었다** — 그 파일이 스스로 *"Deliberately NOT a YAML
  reader"*라 적는다. 그래도 **계약은 네트워크를 건넌다**(`to_dict()` → `interface`). 실측: 필드 9·
  Sync 4값·Health 5값이 **정확히 일치**한다. ⇒ 결함이 아니라 **집행 부재**이고, TS가 두 축을
  **union literal**로 적기 때문에 실패가 날카롭다: py에 값을 하나 더하면(M37이 `n/a`로 실제로 한
  변경) 대시보드 타입이 "존재할 수 없다"는 값이 도착하는데 **`tsc`는 계속 초록**이다(Risk 7).
- Verified(**변이 5종 전부 red**): py enum 값 추가 · ts union에서 `n/a` 제거 · py `to_dict`에 새 키 ·
  ts interface에서 `applicable` 제거 · **interface 이름을 바꿔 파서 무력화**(공허 통과 방지가 산다).
  복구 후 초록, 워킹트리 깨끗.
- Verified(**Phase 3② — 구현은 있고 묻는 쪽이 하나뿐이다**, 미수정·승인 사안): `guard_rollback`을
  부르는 러너는 **`onprem_runner` 하나**인데 `ROLLBACK_ACTIONS`는 **네 provider 7종을 다 안다**.
  ⚠️**M31이 고친 건 목록이고, 호출 지점을 세는 가드는 없다** — M18 계열이 한 층 위에서 재발했다
  (세는 대상이 액션이 아니라 **러너**였다). 건너뛸 근거 둘을 다 물었고 **둘 다 성립하지 않는다**:
  gcp/azure 러너는 롤백 직전 **매니페스트를 이미 GET한다**(배선 비용 = 추가 호출 0) · 레지스트리가
  kind/k3s만 선언한 건 그 모듈이 **"소유권은 라이브 마커에서 읽는다"**고 명시하므로 근거가 아니다.
  ⛔안 고쳤다 → **승인받아 GCP만 배선했다**: 롤백 walk가 이미 GET하던 매니페스트를 그대로
  넘긴다(**추가 호출 0**), 거부는 `patch` 앞이다. Azure는 `JUSTIFIED_GAPS`(러너를 안 부르니
  하중이 없다 — 그 항목이 닫히면 **면제를 지우라고 가드가 red를 낸다**), AWS는 **러너가 없다**
  (SSM 경로 — 그 사실을 가드에 박았다). ⚠️**가드가 한 번 틀렸다**: 문자열 검사라 **호출을 지워도
  import 줄이 남아 통과**했다 → **AST로 실제 호출**을 센다(같은 변이가 1건→**2건 red**).
- Verified(**Phase 1b는 정적만**): flux는 134줄 실구현, 두 어댑터가 `wave`를 각자 시맨틱으로 렌더.
  라이브는 **오늘 재현 불가** — Docker 데몬 down(kind), k3s `k8s-lab`은 살아 있으나 **네임스페이스가
  기본 4개뿐**(flux·워크로드 없음). `STATUS` Risk 5의 "여는 조건: k3s-lab에 워크로드"를 **측정이
  확인**했다. ⚠️"한때 통과했다"와 "지금 재현된다"는 다르며 이 기록은 후자만 주장하지 않는다.
- Verified: `make check` **2291 passed, 2 skipped**(2026-08-18 로컬 macOS·py3.13, 37.4s) — 가드 **+12**.
  ⚠️게이트가 스스로를 잡았다 — `test_gate_number_claims`가 **진입점 셋이 다 같은 숫자를 말할 때까지**
  red였다(brief·STATUS만 고치고 NEXT_PLAN을 빠뜨리자 그 자리에서 실패).
- Blockers: 없음. Phase 1b 라이브는 **정적 검증으로 남기기로 결정**(Docker down · k3s-lab 비어 있음).
- Next: 08-19 이후 AMP 청구액 대조 · Azure executor 디스패치를 고치면 **Phase 3② 면제도 함께 지울 것**.


## 2026-08-18 — `cost_metrics` 잔여: 기록된 이유가 맞았고, 면제는 목록이 아니라 경계였다 (gate 2279)

- Status: 08-19 전까지 AMP 청구액은 원리상 못 잰다. 그래서 잔여 목록의 **`cost_metrics`**
  (*"`deployment_id`가 없어 렌더하는 뷰에 안 닿는다", 08-08*)를 규율대로 시험했다.
  **PR #43**(3커밋, capability 스캔 셋)은 CI 초록 확인 후 squash 병합했다(`a9331bb`).
- Verified(**쓰는 쪽 형제는 넷이고 하나는 다른 모듈에 있다**): ACTIVITY 행 writer는
  `record_route_activity`·`_write_row`·`record_rollback`(deploy_recorder) + **`record_agent_activity`
  (`operations/activity_writer.py`)**. 그중 둘만 `cost_metrics`를 쓴다. ⚠️`record_route_activity`는
  **350KB짜리 trace를 쓰면서** 그것만 안 쓴다 — `_cost_metrics`가 바로 그 trace에서 유도하므로
  "쓸 수 있는데 안 쓴다"로 읽히는 모양이다.
- Verified(**읽는 쪽으로 가니 결함이 아니라 범위였다**): cost를 렌더하는 곳은 **한 곳뿐**
  (`deployments/[id]/page.tsx`)이고 그걸 먹이는 `mergeActivity`의 선택 규칙은 `deployment_id === id`
  한 줄이다. route·provider-activity 행은 그 키가 없어 **원리상 그 뷰에 못 닿는다.** 더하면 이
  저장소가 반복해 값을 치른 **"선언됐는데 아무도 안 읽는 필드"**가 하나 는다. ⇒ **현행 유지.**
- Verified(**면제가 손으로 고른 목록인지**): 아니다. 가드가 의무를 **읽는 쪽 선택 규칙에서
  유도**하고(모듈이 아니라 `deployment_id` 보유가 기준) 범위는 `SRC_AGENTS.rglob("*.py")`라
  **전 모듈**을 덮는다 — 넷째 writer가 다른 모듈에 있어도 잡힌다. 공허 통과 방지도 있다(`>= 4`).
- Verified(**변이 3종 전부 red**, 변이·실행·복구 한 스크립트): 롤백 행에서 `cost_metrics` 제거
  (4건, db41874가 고친 그 결함) · **route에 `deployment_id` 부여**(1건 — 경계를 넘는 순간 의무가
  생긴다는 게 요지) · `"PK": "ACTIVITY"` 리터럴을 깨 스윕 무력화(1건, 공허 통과 방지가 산다).
  복구 후 8 passed, `git diff --stat` 비어 있음. 증거
  `docs/evidence/cost-metrics-exemption-is-derived-and-load-bearing.log`.
- Changed: **src 변경 0.** `NEXT_PLAN`에서 열린 잔여 → ⛔닫힘으로 이동. 진입점 stale도 고쳤다 —
  brief가 이미 닫힌 ⓒ·`rollback_release`를 무과금 다음 수로 가리키고 있었고, 4a DoD ①②는
  brief·STATUS 양쪽에서 "남은 설계 결정"인 채였다(M37이 결정·구현했다).
- Verified: `make check` **2279 passed, 2 skipped**(2026-08-18 로컬 macOS·py3.13, 35.8s) —
  08-17 숫자를 오늘 같은 기계에서 재측정해 baseline에 날짜와 기계를 적었다(Risk 12②).
- Blockers: 없음. AMP 청구액은 **08-19 이후**(CE 2일 지연 · ⚠️크레딧 제외 필터).
- Next: 08-19 이후 AMP 실제 청구액 대조.


## 2026-08-17 — 추천안 셋 수행: 점수제·조건 준수·관리형 렌더 (gate 2279)

- Status: 열려 있던 판단 셋을 **추천안대로 실행**했다. ⓒ 판별 수단 · `rollback_release`
  정책 · 4a DoD ①②. ⚠️**둘째의 전제가 측정에서 무너져 답이 바뀌었다.**
- Changed(**#1 판별 수단**): 점수 로직을 **계약 모듈**에 한 벌 두고(`schema.score_runbook`
  ·`match_text`) 세 provider가 읽는다. GCP/Azure 티어 2가 **첫 매치 대신 점수**로 고른다 →
  세 provider가 같은 인시던트에 **같은 답**(health-check = `health-check-failure`/rto **240**).
  키워드 어휘는 이미 클라우드-중립이라 **없던 건 데이터가 아니라 읽는 쪽**이었다.
- Verified(**#2의 답이 바뀌었다 — 추천 목록이 아니라 티어 2가 문제였다**): 티어 2는 액션을
  **조건 평가 없이** 추천에서 만든다. 카탈로그에서 **에스컬레이션에만 존재**하는 capability는
  넷(`expand_storage`·`rebalance_consumer`·`rollback_release`·`scale_database_read`)이고,
  그중 **둘이 GCP/Azure에서 first-response로 실행**되고 있었다 — **같은 모듈의 티어 1은 조건을
  평가한다**(M21 모양: 형제가 provider가 아니라 진입점). AWS·onprem은 추천이 액션이 안 되므로
  같은 목록이 무해하다. ⇒ **티어 2가 승자의 steps에서 액션을 만들게 고쳤다**(에스컬레이션은
  `condition_false` 로그와 함께 제외). `rollback_release`는 **추천에 넣지 않는다**(현행 유지).
  ⚠️**티어 2 액션을 단언하는 테스트가 0개였다** — 그래서 조건 무시도, 이 고침도 red를 안 냈다.
- Changed(**#3 4a DoD ①②**): 결정 = **관리형은 매니페스트를 내지 않고 read model이 부재를
  설명한다**(`applicable=False`·sync **n/a**). **새 매니페스트 종류는 발명하지 않았다.**
  ①`globex/dev`가 `amazon-managed-prometheus`를 **실제로 선언**한다(①이 ②의 하중이다) ·
  ②`DesiredAddon.managed`를 두 어댑터가 읽고 건너뛴다 · **관리형은 싱글턴 문제가 아니다**
  (설치가 없으니 두 번째 컨트롤러가 없다 — 계획서 정정 박스가 *"Prometheus CR을 주라"*는
  따를 수 없는 안내를 남긴 지점) · `ManagedBackendNotRenderable`는 **삭제**(결정이 났다).
- Verified(**변이 16종 전부 red**): 점수제 되돌리기(3·3) · 조건 무시로 되돌리기(2·2) · 공유
  점수 함수 가중 죽이기(1·15) · 관리형 표시 제거(5) · 두 어댑터가 차트를 내게(2·1) · 싱글턴이
  관리형을 삼키게(3) · **선언 되돌리기(4)** · **read model이 sync를 꾸며내게(4)**.
  `make check` **2279 passed, 2 skipped**(로컬 macOS·py3.13), ruff 신규 0.
- Blockers: 없음. ⚠️도중에 **ruff 비교용 `git stash`/`pop`이 `git rm`을 언스테이지**해
  `git ls-files`엔 있고 디스크엔 없는 파일이 생겼다 — **그걸 스캔하는 가드가 잡았다.**
- Next: 08-19 이후 AMP 청구액 대조(4a의 마지막 미측정).


## 2026-08-17 — ⓒ: 앞쪽은 맞았고 "테스트가 고정했다"가 틀렸다 (gate 2269)

- Status: 마지막 미측정 항목 **ⓒ**(*"티어 2는 첫 매치가 이긴다(AWS는 점수제) — 테스트가
  고정했으니 우연이 아니라 결정이다"*). **앞쪽은 정확하고 뒤쪽이 틀렸다.**
- Verified(**기존 가드가 생산 경로를 한 번도 안 물었다**): `test_capability_catalog_scan`의
  케이스는 **후보를 유일하게 가리는 capability 집합을 손으로 골랐다**(`["rollback_release"]` →
  health-check-failure, `["drain_node"]` → network-latency-high). ⚠️**어떤 signal 어댑터도
  그런 집합을 안 낸다** — `kubernetes-workload`엔 전부 `restart_workload`+`scale_out`을 내고
  그건 **후보 셋과 동시에 겹친다.** 즉 **첫-매치 구현과 점수제 구현이 답이 같은 경우만
  태웠다**(Risk 12⑤). 게다가 `["rollback_release"]`는 **그 세 provider가 추천하지 않는 값**이다
  (오늘 M35에서 측정) — 생산에서 도달 불가한 입력으로 통과하고 있었다.
- Verified(**실제 집합으로 물은 결과**): GCP/Azure는 OOM·health-check·latency **셋 다**
  `eks-pod-oom`/**rto 180**을 보고한다. AWS는 namespace(+2)·keyword(+1) 점수로 **셋을
  구분한다** — health-check는 `health-check-failure`/**rto 240**. 액션은 추천에서 오므로
  같지만 **운영자에게 보고되는 runbook_id·rto_sec이 다르다**(M22 계열: 사람에게 틀린 걸 보여준다).
- Verified(**catalog 규약의 안전 속성이 provider마다 다르다**): *"appending은 선택을 못
  바꾼다"*는 주석은 **AWS 점수 동점 규칙**에 대한 것이다. GCP/Azure는 점수가 없어 **순서가 곧
  알고리즘**이라, 앞에 끼운 런북이 **모든 선택을 훔친다**(실측: `thief`/rto 9999). 주석에
  provider 범위를 적고 가드로 집행했다.
- Changed: `catalog.py` 주석에 **AWS-scoped임과 "append, never insert"**를 명시. `src` 동작
  변경은 **0** — 판별 수단을 줄지는 **설계 결정**이라 손대지 않았다(`NEXT_PLAN` ⓒ).
- Changed(가드 +12, `test_tier2_selection_is_ordered_not_scored.py` 신규): 입력을 **어댑터에서
  직접 읽어** 픽스처가 생산과 어긋날 수 없게 했다 · 전제(후보>1)를 먼저 묻는다 · GCP/Azure ×
  세 인시던트 · AWS가 셋을 구분함 · **앞에 끼우면 훔치고 뒤에 붙이면 안 훔친다.**
- Verified(**변이 4종 전부 red**): 첫→마지막 매치(9건) · overlap 게이트 제거(6건) · 추천 집합
  축소로 모호성 제거(4건) · **AWS namespace 점수 죽이기(1건)**. ⚠️**마지막이 1건인 게 요지다** —
  AWS 점수제가 셋을 구분한다는 사실을 잡는 건 **오늘 만든 가드 하나뿐**이었다.
  `make check` **2269 passed, 2 skipped**(로컬 macOS·py3.13).
- Blockers: 없음. ⛔설계 결정 하나가 열렸다(GCP/Azure 판별 수단) + M35의 `rollback_release` 정책.
- Next: 08-19 이후 AMP 청구액 대조.

## 2026-08-17 — ⓐ를 시험하니 답은 "현행 유지"였고, 스윕이 결함 넷을 냈다 (gate 2257)

- Status: 무과금 목록에 남은 **capability 스캔 ⓐ·ⓒ**. 규율대로 **기록된 이유부터 시험**했다.
- Verified(**ⓐ의 주장은 성립**): `kafka-lag-spike`가 유일하고 어긋남은 **한 방향뿐**(반대 0건 —
  ⚠️처음엔 한 방향만 물었다). ⚠️**내 픽스처가 한 번 틀렸다**: resolve는 **(capability,
  resource_type) 쌍**으로 키를 거는데 `kafka-topic`으로 물어 *"네 provider 전부 미구현"*으로
  읽었다. 올바른 `streaming-consumer`로는 **전부 resolve된다.** 주장 전에 잡았다.
- Verified(**두 선택지는 대칭이 아니다** — 08-12엔 "둘 다 동작 변경"이었다): 티어 2(GCP/Azure)는
  액션을 **steps가 아니라 `recommended_capabilities`에서** 만들고 `capabilities`는 **매치
  게이트일 뿐**이다. `scale_out_workers`가 이미 겹쳐 **더해도 관측 변화 0**, **빼면 네 provider가
  다 resolve하는 에스컬레이션 스텝을 잃는다.** ⇒ **현행 유지로 닫는다.**
- Verified(**스윕이 결함 넷 — 찾던 건 하나였다**): 네 signal 어댑터 × 전 resource_type을 AST로
  훑고 **빠진 capability가 그 provider에서 resolve되는지**까지 물었다. ①`streaming-consumer`/
  `rebalance_consumer`가 **Azure만 없다**(3대1)는데 Azure는 **구현하고 있다**. 네 어댑터는 **같은
  커밋 `a22a283`에서 태어났고 Azure는 처음부터 빠져 있었다**(stale이 아니라 **쓰일 때부터 틀림**).
  ②③④`kubernetes-workload`/`rollback_release`는 **onprem만 추천**하고 셋은 구현했는데 안 한다 —
  ⚠️**1대3, 소수가 갖고 있다**. 롤백은 파괴적이라 **내가 정할 게 아니라** 알로리스트에 이유를
  달아 **사람 결정으로 남겼다.**
- Changed: Azure 추천에 `rebalance_consumer` 하나(+이유). ⚠️**Azure executor가 실행 없이
  resolved를 보고하는 열린 항목과 맞닿는다** — 클레임이 하나 늘지만 **라이브 변경은 없다**(no-op).
  그 항목을 고칠 이유이지, 구현을 못 쓰게 둘 이유는 아니다.
- Changed(가드 +6, `test_signal_capability_parity.py` 신규): 규칙은 **"추천 안 해도 되는 건 실행
  못 하는 것뿐"**. 알로리스트는 이유 없으면 못 넣고 ⚠️**현실과 어긋나면 red**. 공허 통과 방지도
  뒀다 — **AST가 아무것도 못 읽으면 나머지가 저절로 통과**한다(내가 그 함정에 빠졌다).
- Verified(**변이 4종 전부 red**): 고침 되돌리기 · 다른 provider에 새 구멍 심기 · 알로리스트 한
  줄 비우기(=실재하는 구멍을 덮고 있다) · 알로리스트 stale화. `make check` **2257 passed, 2 skipped**.
- Blockers: 없음. ⛔남은 정책 결정(`rollback_release`)은 `NEXT_PLAN`에 있다.
- Next: 08-19 이후 AMP 청구액 대조 · ⓒ(첫-매치 vs 점수제)는 **미측정**.

## 2026-08-17 — 검증을 세운 그 커밋이 같은 결함을 한 문 옆에 남겼다 (gate 2251)

- Status: 앞 증분(조건 검증)에 **ultrareview**를 돌렸다. 결함 하나(normal)와 죽은
  참조 하나(nit)가 나왔고 **둘 다 성립했다**. 재현해서 확인하고 고쳤다.
- Verified(**리뷰가 맞았다**): `steps: null`은 `_step_problems`가 **0 problems로 통과**
  시키는데, GCP/Azure walk가 `runbook.get("steps", [])`로 읽는다 — **기본값은 키가
  없을 때만** 쓰이므로 저장된 `None`이 그대로 나오고 `for step in None`이 **TypeError**.
  ⚠️**내가 "막겠다"고 주석에 적어 둔 바로 그 500을, 그 주석을 쓴 커밋이 만들었다.**
- Verified(**리뷰보다 넓었다 — 형제를 다시 셌다**): `steps`를 읽는 자리는 넷이고
  **AWS만 `or []`로 None-safe**였다 = **읽는 쪽의 provider 간 비대칭**(이 레포가 정한
  "진짜 결함" 기준). 리뷰가 지적한 둘 외에 **`CapabilityRunbook.from_dict`도 같이
  터진다**(실측). 넷째(`executor.py`)는 생산자가 `default_factory=list`라 도달 불가지만
  **홀수를 남기지 않으려고** 같이 고쳤다.
- Changed: 넷 다 `get("steps") or []` · `schema.py` 계약 도크스트링에 **null 허용**을
  명시(에러 메시지는 "list or null"인데 도크스트링은 `list[dict]`이라 **두 출처가
  달랐다**) · nit: `CONDITION_KEYS` 주석이 **없는 파일**을 가리키고 있었다(드리프트
  가드는 `test_store_runbook_validation.py` 안에 있다) → 실제 이름으로 고쳤다.
- Changed(가드 +4, `test_steps_reads_are_none_safe.py` 신규): 행동 셋(GCP·Azure 라이브
  경로 + `from_dict`) + **구조 하나** — `src` 추적 파일을 AST로 훑어 `get("steps", …)`
  형태를 금지한다. ⚠️**`glob`로 짰다가 터졌다**: `src/stacks/node_modules/`의 CDK 템플릿
  6개가 `%name.PascalCased%` 때문에 파싱 불가다 — 조용히 건너뛰면 진짜 reader를 놓치니
  **`git ls-files`로 스캔 면을 좁혔다**(레포가 이미 쓰는 방식).
- Verified(**변이 5종, 전부 red**): 네 고침을 하나씩 되돌리면 red(R1~R3는 2건씩,
  R4는 구조 가드만 — 그 경로에 행동 테스트가 없는 게 정직하다) · ⚠️**공허 통과 방지로
  위반을 일부러 심었더니**(R5) red = 스캔이 정말 파일을 열어 본다.
  `make check` **2251 passed, 2 skipped**(로컬 macOS·py3.13).
- Blockers: PR #42는 **병합 권한이 막혀** 열려 있다.
- Next: 08-19 이후 AMP 실제 청구액 대조.

## 2026-08-17 — 계약을 읽는 쪽만 고쳤더니, 쓰는 쪽이 아무것도 안 물었다 (gate 2247)

- Status: 직전 증분이 남긴 기준(**"조건은 계약이다"**)으로 **쓰는 쪽**을 물었다.
  `validate_runbook`은 최상위 필드를 전부 검증하는데 **`steps` 안은 아예 안 본다** —
  즉 M28이 "변조될 수 있는 쪽"(운영자 스토어=티어 1)을 검증하게 만든 건 껍데기였고,
  조건이 사는 곳은 무검증으로 walk에 넘어갔다.
- Verified(**측정**): 오타 조건 키 `previous_step_fail`은 **검증 0 problems + 평가 True**
  = 에스컬레이션 스텝(`rollback_release`)이 **모든 인시던트에서 실행**된다. 08-16에 고친
  그 결함을 **반대쪽 문**으로 다시 만든다(그때는 조건을 안 읽어서, 이번엔 **아무 뜻도 없는
  조건을 읽어서**). 비-dict 조건은 walk의 try **밖에서** TypeError → 티어 1 주석이
  *"막겠다"*고 적어 둔 바로 그 500. `severity_in: "P12"`는 **부분문자열 매칭**이 되어
  P1 인시던트가 통과한다.
- Verified(⚠️**엄격한 스텝 검증기는 이미 있었다 — 테스트만 부른다**):
  `capability_schema.validate_capability_runbook`은 `src/`에서 **호출처 0**. 검증기가 둘이고
  **실제 경로가 쓰는 건 느슨한 쪽**이었다.
- Changed: 조건 절을 **공유 계약 모듈**(`schema.py::_step_problems`)에 한 벌 넣었다 —
  세 provider가 다 읽는 곳이다. 키 집합 `CONDITION_KEYS`는 **읽는 쪽 옆**에 두고
  validator가 임포트한다(복제 금지). 거절은 M28의 기존 선택대로 **런북 단위**(휴리스틱 폴백).
- Changed(가드 +23): `MALFORMED`를 넓히니 **세 provider 전부**가 이미 있는 형제 기계로
  자동 커버된다 · **잘 형성된 조건 4형식은 여전히 따라가야 한다**(과잉 엄격이 티어 1을
  닫는 방향 — `require_alarm_name` 함정의 한 층 아래) · `CONDITION_KEYS`와 평가기를
  **AST로 대조**해 드리프트를 막는다.
- Verified(**변이 7종, 전부 red**): 절마다 하나씩 · 과잉 엄격(조건 전면 금지) **12건 죽음** ·
  드리프트(평가기에 넷째 형식) **5건 죽음**. ⚠️**`steps` 타입 절은 처음엔 생존했다** —
  픽스처를 `"restart"`로 잡았는데 **문자열은 순회가 되어** 절이 없어도 거절됐다(Risk 12⑤).
  **정수 5**로 바꾸니 절 없이는 **검증기가 TypeError로 터진다**("never raises" 위반) → red.
  `make check` **2247 passed, 2 skipped**(로컬 macOS·py3.13), 건드린 3파일 ruff 깨끗.
- Blockers: 없음. ⚠️PR #42는 **병합 권한이 막혀** 열려 있다.
- Next: 08-19 이후 AMP 실제 청구액 대조.

## 2026-08-17 — 계약이 세 형식인데 walk는 둘만 물었다 (gate 2224)

- Status: 열린 항목 **"런북 walk ②(`severity` 축)"**를 시험했다. **닫혔다 — 두 겹으로.**
  ①`severity` 축 자체는 **M33이 08-16에 닫았다**(가드가 GCP·Azure·AWS 셋 다 있고 양방향).
  ②e2e walk가 `severity="P2"`로 고정인 건 **결함이 아니라 범위**다: 카탈로그 9런북 16스텝을
  세어 보니 **조건 키는 `previous_step_failed` 하나뿐**(6스텝) — 08-12의 *"없는 문제에 대한
  가드는 하중을 못 받는다"*는 **아직 참**이다.
- Verified(**닫으러 갔다가 옆에서 나왔다**): `evaluate_condition`이 문서화한 형식은 **셋**
  (`previous_step_failed`·`severity_in`·`provider`)인데 walk 자리에서 물어진 건 **둘**이었다.
  `provider`는 **순수함수 단위 테스트**(직접 만든 컨텍스트)에만 있었다 — Risk 12④ⓒ.
  ⚠️**`test_step_condition_is_read.py`의 도크스트링이 세 형식을 정확히 열거하면서 둘만 물었다**
  — M20과 같은 모양(**산문이 참이어도 물은 것이 범위다**).
- Verified(**변이 8종, 전부 red · 기준선 먼저**): 대조군으로 세 컨텍스트 dict에서
  `"severity"`를 지우면 red(하네스가 맞는 dict를 겨냥했다는 증거) · **`"provider"`를 지우면
  세 walk 전부 GREEN 생존**(=가드 없음, 2218 그대로) → 가드 추가 후 **지우기 셋·`"aws"`로
  굳히기 셋 = 여섯 전부 red**. `-x` 없이 다시 재니 **정확히 1건**이 죽고 이름은
  `test_the_provider_form_is_honoured[own-provider-runs-gcp]` — **예측대로 하중은 양성 방향
  하나가 진다**(음성 방향은 깨진 구현과 답이 같아 혼자서는 살아남는다, Risk 12⑤).
  ⚠️변이·실행·복구를 한 스크립트에 두고 **복구는 git이 아니라 디스크 백업**으로 했다.
- Changed(가드 +6, `src/` **무변경**): `test_step_condition_is_read.py`에 provider 형식을
  GCP·Azure × 양방향으로(+4) · `test_executor_capability_steps.py`에 **gcp 인시던트가
  `provider: gcp` 스텝을 만족하는지**(+2 — AWS walk는 `normalized_incident`가 없으면
  `"aws"`로 폴백하므로 **인시던트 자신의 provider를 읽는지**를 물어야 하중을 받는다).
- Verified: `make check` **2224 passed, 2 skipped**(로컬 macOS·py3.13) · 두 파일 ruff 깨끗.
  ⚠️**게이트 숫자 가드가 먼저 red를 냈다** — `test_gate_number_claims`가 진입점 셋의 숫자
  일치까지 묻는다. 셋을 같은 커밋에서 고쳤다(**이 가드가 제 일을 했다**).
- Blockers: 없음.
- Next: 08-19 이후 AMP 실제 청구액 대조(4a를 닫는 유일한 남은 측정).

## 2026-08-17 — 4a가 라이브가 됐다: AMP가 계획서의 네 숫자를 그대로 돌려준다 (gate 2218)

- Status: 승인 셋(메트릭 4종·60초·리전)을 받아 4a에 착수. **DoD 네 단계 중 ③(remote_write
  성공)을 넘었다.** ①②는 계획서가 *"무엇을 렌더할지는 일부러 발명하지 않았다 — Phase 4
  결정"*이라 미룬 설계 사안이라 손대지 않았고, ④는 `from_managed`로 이미 서 있다.
- Changed: 워크스페이스 `ws-929b8da9…`(ap-northeast-2) · IAM 사용자 `amp-remote-write-4a`
  (정책 전부 = `aps:RemoteWrite` **하나**를 그 워크스페이스 **하나**에) · 키는 k8s Secret으로만
  존재(**git·로컬 파일 어디에도 안 씀**) · values에 remoteWrite+허용목록 · **간격은 전역이
  아니라 `kube-state-metrics` ServiceMonitor만 60초**(308 중 287이 거기서 온다) · 가드 2종.
- Verified: `make check` **2218 passed, 2 skipped**(로컬 macOS·py3.13, CI 일치) · 적용 전
  `helm template`로 두 키가 **실제로 읽히는지** 확인(Risk 8) + `helm get values`로 파일 밖
  값 없음 확인 · 파이프 `samples_total 319 / failed 0 / dropped 69,076`(99.5% 필터) ·
  **AMP 직접 조회가 §2의 22·50·220·16 = 308을 그대로 반환** · 변이 4종 모두 red.
- Blockers: ⛔**실제 청구액 미측정** — CE 2일 지연이라 **08-19 이후** 크레딧 제외 필터로
  대조해야 4a가 닫힌다. 그전까지 $1.42는 **산수지 측정이 아니다**. ⛔4a ①②는 설계 결정 대기.
- Next: PR #41 병합 → 08-19 청구액 대조 → 관리형 observability를 무엇으로 렌더할지 결정.

## 2026-08-16 — 08-11부터 묶여 있던 항목: 기록된 차단 이유가 틀렸다 (gate 2102)

- Status: `slack_live_approval.py`는 *"고치면 조용히 no-op"*이라 08-11부터 안 고치고 있었고,
  기록은 *"올바른 이름은 **Slack 데모를 태워야 확정**된다"*였다. **이 레포는 오늘 이미 그런
  기록 하나가 틀린 걸 봤으니**(M19 ⓑ) 믿지 말고 시험했다.
- Verified(**①은 참, ②는 근사했다**): 임포트 경로
  `src.agents.operations.approval_bridge`는 **추적 트리에 없다** — 패키지가 `aws/` 아래로
  이사했고 옛 경로는 **untracked `cdk.out/`에만** 남아 있다(그래서 `cdk synth`를 돌린 머신에서만
  임포트가 됐다). ⚠️기록은 *"여섯 중 넷 부재"*였는데 실제로는 **5/6이 부재**(`_SFN`만 존재)이고
  **호출하는 셋은 전부 존재**한다.
- Verified(**"데모 선행"은 틀렸다**): 사라진 다섯은 서브모듈 분해로 옮겨졌고 **각각 정확히
  한 곳**에 있다(`slack_interactive` 셋 · `request_store` 둘) — 추측 여지가 없다. 그리고
  `_post_slack_request`가 **호출 시점에 모듈 전역을 읽으므로** setattr이 실제로 먹는다.
- Changed: 임포트를 `aws/` 경로로 고치고 다섯 대입을 **값이 실제로 사는 서브모듈**로 돌렸다.
  `handler._SFN`은 **그대로** — 거기서 읽는다(`handler.py:207,220`). 왜 서브모듈이어야 하는지를
  임포트 옆 주석에 적었다.
- Verified(**오프라인 실증**): 스크립트 자신의 `simulate`가 문서상 완전 오프라인이라 그걸로
  끝까지 돌렸다 — SQS 요청→PENDING 저장→**실제 HMAC 서명** 버튼 콜백→HTTP 200→SFN
  resume→**APPROVED**. **Slack 없이 확정됐다.**
- Changed(가드 +8, `test_harness_patch_targets_exist.py` 신규): 스크립트가 대입하는 이름을
  **AST로 뽑아** 대상 모듈에 실재하는지 묻는다(웹훅·자격증명 없이 성립). 호출 진입점 셋 ·
  옛 임포트 경로 부재도 함께. 변이: 대입 하나를 `handler`로 되돌리면 red.
  `make check` **2102**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: ⚠️**"기록된 이유"가 오늘만 세 번 틀렸다**(M19 ⓑ · `Resource:"*"` 전면 금지 · 이번 것).
  전부 **시험하면 값이 났다**. 남은 것: DUAL 모드 조건부 리다이렉트는 **여전히 안 만든다**
  (둘 다 경고에 못 닿아 하중을 못 받는 가드가 된다 — 이건 시험해서 확인한 게 아니라 기록 유지).

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

## 2026-08-15 — 렌즈의 마지막 층: "resolved"는 셋이 같은 뜻이었다. 우연히 그랬다 (gate 2059)

- Status: 렌즈를 한 층씩 내려 왔다(`AlarmContext`→`AnalyzerOutput`→`DecisionOutput`→게이트
  자신→의존성 선언). 마지막 층 `ExecutorOutput`을 물었다 — **필드는 셋이 글자 그대로 동일**하다.
  그래서 **값 축**으로 물었다: `resolved`는 계산되고 `resolved_at`·MTTR로 이어진다.
- Verified(**계산은 달랐다, 그런데 결함은 아니다**): aws는 `resolution_verdict(...).resolved`,
  gcp/azure는 `bool(executed) and not skipped` **하드코딩**. AWS 주석이 *"so both axes have one
  definition"*이라 쓰는데 **둘이 그 정의를 안 썼다**. ⚠️단 **오늘 동작은 같다** — 검증이 없으면
  계약이 정확히 그 규칙이고, **gcp/azure엔 verify 경로가 0건**이다(`git grep "verif"`).
  ⇒ M23의 `steps`와 같은 판정: **도달 불가 분기가 아니라 일관된 부재**.
- Changed(**동작 변경 0**): 그래도 계약으로 모았다 — `NEXT_PLAN` 유지 규약이 금지하는 모양
  (*"복사본 둘은 다음 고침이 한쪽에만 닿는 방식"*)이고, **계약 모듈은 이미 있었고 AWS는 이미
  읽고 있었다**. 값은 **미래 드리프트 제거**이고 그 대가는 M19가 이미 지불했다(67/81).
- Verified(가드 +13, `test_resolution_parity.py` 신규): **오늘의 답이 안 움직였는가**(5케이스) ·
  `verified`가 None(unknown)인가 · 셋 다 계약을 임포트하는가 · **하드코딩 사본이 다시 생기지
  않았는가** · 셋이 같은 답인가. 변이 **5건 red·생존 0**(기준선 108).
  `make check` **2059 · 32.35s**, 2026-08-15, 로컬 macOS·py3.13.
  증거 `resolved-meant-the-same-thing-by-accident.log`.
- Blockers: 없음.
- Next: ⚠️**변이 M4 첫 시도가 또 무효였다 — 오늘 세 번째**(함수 이름을 바꿔 `2 errors` 수집 실패).
  절차에 넣은 **기준선 먼저 찍기**가 잡았다. ⇒ **이름을 바꾸는 변이는 의미 변이가 아니라 문법
  변이다.** 그리고 **렌즈 결산**: 다섯 층에서 다섯 결함, **여섯째에서 멈췄다** — 마르는 지점을
  적어 두는 건 다음 세션이 같은 자리에 다시 대지 않게 하려는 것이다(증거 §5).

## 2026-08-15 — 08-08에 배운 교훈을 한 패키지에만 적용했다. 형제 여섯을 안 셌다 (gate 2046)

- Status: D49의 원인이 *"`except ImportError` 폴백이 원리상 도달 불가"*였다 — **그 패턴을
  일반화해** 물었다. `pyproject.toml`이 이미 그 교훈을 **한 패키지 분량으로** 적어 두고 있었다
  (08-08 opentelemetry: *"게이트가 선언되지 않은 패키지 위에서 통과하고 있었다"*). **형제를 안 셌다.**
- Verified(전수 스윕, AST + `git ls-files`): `try/except ImportError` 뒤 서드파티 임포트 13종 중
  **여섯이 어느 extra에도 없다** — `google-cloud-{firestore,logging,monitoring}` ·
  `azure-cosmos` · `azure-monitor-query` · **`openai`**(azure analyzer의 **LLM 자체**) ·
  `fastapi`/`uvicorn`(**`make dev-up`이 쓰는데 아무도 선언 안 했다**).
- Verified(**왜 조용한가**): 폴백이 전부 **에러가 아니라 warning**이다. 선언이 빠져도 설치가
  실패하지 않고 **팔다리 없는 에이전트가 배포된다** — `.[gcp]`는 로그·메트릭·스토어가 없고,
  `.[azure]`는 **LLM·스토어·로그가 없다**. `AGENT_BRIEF`가 광고하는 `make dev-up`은
  **새 클론에서 안 돈다**. CI도 못 잡는다(거기서도 조용히 폴백한다).
- Changed(**선언만**, 코드 무변경): gcp/azure extra 보강 + `serving` extra 신규. 폴백은 그대로
  유효하다 — 바뀐 건 *"설치하겠다고 말한 것을 실제로 설치한다"*뿐이다.
- Verified(가드 +19, `test_optional_dependencies_declared.py` 신규): **설치 상태가 아니라
  소스↔선언을 비교**한다("여기선 되는데"가 이걸 숨겼다). 방어선은
  **`test_no_guarded_import_is_unmapped`** — 소스에 새 optional 임포트가 생기면 red다.
  변이 5건 red. ⚠️**M6(비공허 검사 무력화)은 생존했고 숨기지 않는다** — 가드의 가드는 없다.
  대신 **진짜 실패 모드**를 따로 물어 red를 확인했다(스윕이 `{}` → 2 failed · stdlib 필터
  상실 → 1 failed). ⇒ **생존한 변이는 "가드가 없다"가 아니라 "무엇이 진짜 보호인지"를 묻게 한다.**
  `make check` **2046 · 38.81s**, 2026-08-15, 로컬 macOS·py3.13.
  증거 `six-optional-imports-nobody-declared.log`.
- Blockers: 없음.
- Next: ⚠️**설치해서 확인하지는 않았다** — 빈 환경에서 `pip install .[gcp]`를 돌려 정말 로그를
  못 읽는지는 **미검증**이고, 근거는 선언↔임포트 대조다. 이 머신엔 전이 의존으로 전부 깔려
  있어 증상이 안 보인다 — **바로 그게 이 결함이 오래 산 이유다.** 버전 하한도 관례로 골랐다.

## 2026-08-15 — "느린 테스트"를 열었더니 게이트가 테스트마다 Gemini를 과금 호출하고 있었다 (288s→39s)

- Status: M23의 변이 범위를 정하려고 파일별 시간을 쟀다 — **결함을 찾을 생각이 아니었다.**
  형제 둘이 같은 28건을 도는데 `test_gcp_day2_operations` **200.66s** vs
  `test_azure_day2_operations` **0.43s**(466배). 28건이 **균일하게** 13~23초 = 공통 호출이다.
- Verified(**원인**): `gcp/analyzer.py::_analyse`가 함수 안에서 `import vertexai`를 하는데
  **패키지가 설치돼 있어 `except ImportError` 폴백이 원리상 도달 불가**다. 격리 재현에서
  실제 HTTP가 잡혔다 — `gemini-2.5-flash:generateContent` **→ 200**. **게이트가 테스트마다
  Gemini 추론을 사고 있었다.** ⚠️**D45 위반**(*"게이트는 라이브 클라우드에 의존하지 않는다"*) —
  결정은 있었고 **집행이 없어 참이기를 그만뒀다**. `STATUS` Risk 4의 "Vertex ~₩48K/월" 일부다.
- Verified(⚠️**더 나쁜 절반**): 자격증명만 숨기고 같은 테스트 → **16.55s(라이브) vs 0.90s(폴백),
  둘 다 통과**. 단언은 모델을 필요로 한 적이 없고, **머신에 무엇이 인증됐느냐로 코드 경로가
  갈렸다**(Risk 12②) — **양쪽 다 초록이라 안 보였다**. Azure도 **같은 구멍**이고 Azure
  자격증명이 없어서 안 보였을 뿐이다(AWS만 제대로 모킹해 0.22초).
- Changed: provider별 모킹이 아니라 **스위트의 성질**로 — `tests/conftest.py`(신규)가 세션
  autouse로 **외부 egress 차단**(`connect`+`connect_ex` 둘 다 · 루프백 허용 · 에러가 목적지와
  D45를 말한다). **프로덕션 코드 무변경** — 각 모듈이 이미 가진 폴백이 결정적으로 걸리게 했다.
  **D49**로 기록.
- Verified: 대상 파일 **200.66s→1.42s**, 전체 게이트 **288.56s→38.69s**(2021 passed 동일).
  ⚠️**차단으로 깨진 테스트 0건 = D45는 내내 만족 가능했다.** 가드 +6
  (`test_gate_has_no_network.py`: 차단 발화 · `connect_ex`도 · 에러 내용 · **루프백 생존** ·
  `_analyse`가 폴백을 타는가 · **폴백이 조용히 비어 있지 않은가**). 변이 **5건 red·생존 0**.
  `make check` **2027 / 39.75s**, 2026-08-15, 로컬 macOS·py3.13.
  증거 `the-gate-was-paying-for-gemini-once-per-test.log`.
- Blockers: 없음.
- Next: ⚠️**변이 첫 판이 무효였다** — 5건 전부 "RED"였는데 출력이 `no tests ran in 0.00s`였다.
  범위에 **없는 파일 이름**을 적어 pytest가 수집에서 죽었고 하네스가 종료코드만 보고 red로 셌다.
  M22가 남긴 *"red의 이유를 안 보면 변이는 자기기만이 된다"* 덕에 잡았다. ⇒ **변이 하네스는
  기준선을 먼저 찍고 "몇 건이 죽었는지"까지 볼 것** — 종료코드는 수집 실패와 가드 발화를 못 가린다.

## 2026-08-15 — 파괴 액션 하나가 두 클라우드에선 APPROVE였고 세 번째에선 AUTO였다 (gate 1942→2021)

- Status: 렌즈를 또 한 층 아래(`DecisionOutput`)로. **먼저 나온 건 범위였다** — `steps`·
  `reconciliation`은 AWS만 채우고 AWS만 읽는데, 공유 executor에도 gcp/azure executor에도
  **steps 처리 코드가 아예 없다** → 도달 불가 분기가 아니라 **일관된 부재**(AWS 전용 기능).
- Verified(**가장 위험한 필드를 열었더니 나왔다**): `remediation_mode`의 severity 매핑은 셋 다
  동일한데 **안전 오버라이드가 다르다** — gcp·azure는 `{Delete,Drop,Terminate,Destroy}` **4개**,
  **aws만 인라인 3개**로 **`Destroy`가 빠졌다**. 실행 확인: `DestroyCluster` P1 →
  **aws=AUTO · gcp/azure=APPROVE**. `Severity` 정의대로 **AUTO = 사람 없이 실행**이다.
  `AGENT_BRIEF` 가드레일 문구("Delete/Drop/Terminate 강제 APPROVE")는 **AWS 그대로였고 나머지
  둘은 이미 그것을 넘어 자라 있었다** — **뒤처진 쪽이 하필 파괴 경로**다.
- Verified(도달 가능성, 정직하게): 빌트인 카탈로그는 전부 `AWS-PascalCase` 12종이고
  `Destroy` 계열이 **없다** → 오늘은 도달 불가. **그러나 런북은 운영자가 등록한다**
  (`schema.py` 도크스트링 · 스캔 티어가 그 테이블을 읽는다) → `AWS-DestroyStack`은
  **운영자가 만드는 이름**이고 그게 이 갭이 열리는 자리다. **가설이 아니라 이미 어긋난 세 구현.**
  ⚠️**소문자는 안 고쳤다**(`destroy-stack`은 셋 다 AUTO) — 네 실행 어댑터 전부
  `PROVIDER-PascalCase`만 낸다(4×~29 매핑 전수). **아무도 만들지 않는 형태의 가드는 하중을
  못 받는다.** 대신 **그 전제를 가드로 고정**했다.
- Changed: `runbooks/schema.py`에 `DESTRUCTIVE_ACTION_PATTERNS` + `is_destructive_action()`
  한 벌, 세 decision이 읽는다(M19의 `fits_resource`와 같은 자리·같은 이유). **발명 아님** —
  4번째 동사는 GCP·Azure가 이미 쓰던 것이다. ⚠️네 번째 사본도 있다:
  `deploy-policy.yaml:42`(소문자, **다른 서브시스템**) — 정본 의도가 4개임을 보여 준다.
- Verified(가드 +79, `test_destructive_action_gate.py` 신규): 4동사×3provider×3severity 전수 ·
  역방향(**상시 발화 게이트는 게이트가 아니다**) · 셋이 같은 답인가 · 사본 0인가 ·
  **대소문자 결정의 전제**(어댑터가 PascalCase를 내는가). 변이 **8건 red·생존 0**.
  `make check` **2021**(+79), 2026-08-15, 로컬 macOS·py3.13.
  증거 `destroy-was-approve-on-two-clouds-and-auto-on-the-third.log`.
- Blockers: 없음.
- Next: ⚠️**내 가드가 `cdk.out` 함정을 밟았다** — `rglob`로 "누가 정의하나"를 세니 untracked
  빌드 사본 22건이 잡혀 red. 레포가 적어 둔 **`git grep`을 쓸 것** 그대로다. **더 나쁜 건
  M21의 같은 가드도 같은 결함이었고 상수가 새것이라 우연히 초록이었다** — 다음 `cdk synth`에
  red였을 것이다. 둘 다 `git ls-files` 기반으로 고쳤다. ⇒ **"누가 정의하나"를 파일시스템에
  묻지 말 것.** 그리고 ⚠️**열린 항목 하나**: `test_gcp_day2_operations.py`가 **200초**로
  게이트 288초의 대부분이다(Azure 대응 파일은 **0.43초**, 같은 28건) — **형제 중 하나만 느리다.**

## 2026-08-15 — 승인자에게 "과거 유사 인시던트"라고 보여 준 다섯 건은 랜덤 ID 사전순 최대였다 (gate 1929→1942)

- Status: M21이 `AlarmContext`를 닫았으니 **같은 렌즈를 한 층 아래**(`AnalyzerOutput`)에 댔다.
  `similar_incidents`는 셋 다 채우는데 **시그니처가 달랐다** — AWS만 `severity`를 받고
  **본문에서 안 읽는다**. 그걸 보러 갔다가 **정렬 축이 다르다**는 것을 봤다.
- Verified(**주석이 거짓이었다**): aws는 `ScanIndexForward=False, Limit=5` + 주석 *"most recent
  first"*. 정렬 키가 **`incident_id`**(`incident_agent_stack.ts:30`) = **`INC-<랜덤 hex>`**
  (`executor.py:62`) → **16진수 사전 역순, 시간 무관.** GCP·Azure는 `created_at` 정렬 — **옳았다.**
- Verified(재현, 시드 고정): 한 alarm 12건에서 **최신 5와 겹치는 건 2/5**. ⚠️**"랜덤"보다 나쁘다 —
  안정적이다**: 새 건이 들어갈 확률이 **`5/N`으로 떨어져 이력이 쌓일수록 목록이 얼어붙는다**.
  읽는 사람이 듣는 것("최근")의 정반대다.
- Verified(**읽는 쪽은 사람이다**): `executor.py:458` Slack 승인 메시지 — **무인 조치를 승인할지
  판단하는 사람**이 "선례"로 읽는다. 오류도 빈 목록도 아니라 **조용히 실패한다.**
- Changed: `created_at`은 **이미 모든 행에 있었다** — 없던 건 데이터가 아니라 **그걸로 정렬하는
  코드**다. 서버 측 `Limit=5`(임의의 5건을 먼저 자른다)를 빼고 파티션 페이징
  (`_SIMILAR_SCAN_CAP=500`, 걸리면 **로그로 말한다**) → `created_at` 역순 5건. **발명 아님**:
  정렬 축은 GCP·Azure가 이미 쓰던 것이다. `severity`는 **의미를 주지 않고 제거**했다.
- Verified(가드 +13, `test_similar_incidents_recency.py` 신규): 옛 동작을 **결함으로 고정** ·
  `ScanIndexForward`를 **아예 안 묻는가** · 페이징 · 캡이 시끄러운가 · **세 시그니처 일치** ·
  **이미 옳던 둘이 뒤집히지 않는가**. 변이 **7건 red·생존 0**. ⚠️**M5 첫 시도는 무효였다** —
  red였지만 **내 변이가 문법을 깬 것**(`1 error in 0.06s`)이라 `if False:`로 의미만 바꿔 다시
  물었다. **red의 이유를 안 보면 변이는 자기기만이 된다.** `make check` **1942**(+13),
  2026-08-15, 로컬 macOS·py3.13. 증거 `similar-incidents-were-sorted-by-random-id.log`.
- Blockers: 없음.
- Next: **직전 교훈이 값을 했다** — 변이 원문을 **디스크에 먼저 백업**해 복구가 프로세스보다
  오래 살게 했고 `diff -q`로 바이트 동일을 확인했다 ⇒ **복구 수단은 복구가 필요한 상황보다
  오래 살아야 한다.** 렌즈는 아직 안 말랐다 — **한 층 내려갈 때마다 나온다**
  (AlarmContext → AnalyzerOutput). 다음은 `DecisionOutput`.

## 2026-08-15 — 레포는 GCP/Azure의 정답을 이미 갖고 있었다. 한쪽 진입 경로에만 있었다 (gate 1912→1929)

- Status: `▶ NEXT SESSION`이 가리킨 `observations`를 물었더니 **이미 닫혀 있었다**(M20).
  **그 옆 detector 층에 진짜가 있었다** — 08-15에 이걸로 두 번째다(적힌 항목이 틀려도 값이 난다).
- Verified(**산문이 참인데 범위가 달랐다**): `aws/detector.py::_incident_reason`의 도크스트링이
  *"Provider-neutral by construction"*이라 쓰고 **GCP `policy_name`/`condition_name`·Azure
  `alert_rule`을 이름으로 부른다.** 전수로 세니 **호출자 하나(`aws/detector.py:133`) · 테스트 0개**.
  GCP/Azure는 각각 `summary`/`description` **한 키**로 때웠다.
- Verified(⚠️**더 날카로운 것 — 형제가 provider가 아니라 진입점이었다**): `aws/detector.py:79`의
  `_synthetic_alarm`이 **non-AWS 이벤트에 대해 이미 맞게** 하고 있었다. 즉 같은 GCP 알림이
  **AWS 통합 핸들러로 오면 풍부, 네이티브 GCP 핸들러로 오면 얇은** reason을 받았다.
  **결함은 "안 읽었다"가 아니라 "정답을 한쪽 경로에만 뒀다"이다.**
- Verified(**읽는 쪽까지 갔다**): GCP/Azure엔 AWS에 **없는** 소비자 `_fallback_analysis`가 있고
  `reason`의 낱말로 등급을 정한다. 규칙명 `"checkout service outage"` + 중립 summary로 재현 →
  **P3(사람 승인) ↔ P1(자동 실행)이 뒤집힌다.** M20의 `severity_hint`와 **같은 축·같은 두 provider**.
  ⚠️첫 시도는 안 뒤집혔다 — `signal_type=="reliability"` 분기가 먼저 걸려 낱말 축에 **도달을 안 했다**.
- Changed: 규칙을 `adapters/base.py::incident_reason` **한 벌**로 옮기고 세 detector가 읽는다
  (AWS는 위임). M19의 `runbooks/schema.py::fits_resource`와 같은 선례. **낱말→P1/P2 매핑은
  안 건드렸다**(정책) — 규칙 이름을 reason에 넣은 것은 AWS의 결정을 **옮긴 것**이다.
- Verified(가드 +17, `test_incident_reason_parity.py` 신규): 두 진입 경로 일치 · **읽는 쪽에 대고**
  등급 물음 · 역방향 셋 · **`_RULE_NAME_KEYS` 정의 모듈이 정확히 하나인가**. 변이 **7건 전부
  red·생존 0**(물은 대상 = 신규 + **변경 모듈을 임포트하는 테스트 13개**, `git grep -l`로 산출).
  `make check` **1929**(+17), 2026-08-15, 로컬 macOS·py3.13. 증거
  `incident-reason-two-entry-points-disagreed.log`.
- Blockers: 없음.
- Next(⚠️**Risk 12⑤ 재현**): 변이 하네스가 10분 타임아웃에 잘려 `finally`가 못 돌아 `base.py`가
  변이로 남았다 — `git checkout --`은 피했는데 **프로세스가 죽으면 메모리도 죽는다**를 안 봤다
  ⇒ **복구는 프로세스 밖에도**. **스윕도 닫았다(직전 줄이 틀렸다)**: `AlarmContext` 8필드를 읽는
  쪽까지 세니 **`reason`만 닿았고 일곱은 범위** — ⛔`triggered_at`(AWS 역경로 하나) ⛔`metric_name`
  (빌트인이 AWS 모양이라 살려도 폴백). **더 큰 사실이 덮는 차이는 고쳐도 관측되지 않는다.** 증거 §8.

## 2026-08-15 — 4a를 "비용 최소화"로 승인하고 그 비용을 처음 쟀더니, 전제가 100배 틀렸다 (코드 변경 없음)

- Status: 사용자가 **비용 근거로 4a를 승인**했다(≈$5/월, 4b의 1/40). 승인이 났으니 계획서가
  스스로 적어 둔 *"승인 전 재확인할 것"*을 수행했다. **재확인해야 했던 건 정가가 아니라
  그 옆 칸의 가정이었다.**
- Verified(실측 2회, 재현): `kind-platform-agent`에 직접 물었다 — **52,275→52,438 시계열**,
  **1,979.7→1,981.0 samples/sec** = **월 5.13 B 샘플**. 역산 스크랩 간격 26.4초로 차트
  기본 30초와 일치(두 측정이 서로를 교차검증). §4 가정 "랩 규모 수백 시계열"의 **약 100배**.
- Verified(가격): AMP 정가 $0.90/1천만 샘플은 **맞았다**(AWS 자체 예시 892.8M→$80.93로 교차
  확인). ⚠️**2B 초과 요율은 페이지에 표가 없어 미확인** → 총액은 **하한**이다.
  프리티어(40M)는 **기대지 않는다**: `aws freetier get-free-tier-usage`가 이 계정에서
  "Always Free" 12건 · **"12 Month Free" 0건** → 첫 12개월 창을 지났다.
- Verified(허용목록 견적): job별 분해에서 **apiserver+kubelet이 67%**. 데모 룰이 쓰는 메트릭은
  `kube_pod_container_status_restarts_total` **하나(50 시계열)**. 후보별 월비용@60s —
  A+D(72개) **$0.28** · C(2,671) $10.39 · **E=kube-state-metrics 전부(4,188) $16.28** ·
  **필터 없음(52,361) ≥$180**. ⚠️**필터 없는 4a는 4b($185)보다 비싸다** = 승인 근거가 소멸한다.
- Changed(문서만): 증거 `4a-cost-assumed-a-hundredth-of-the-cluster.log` 신규 ·
  계획서 §4·§5·§7 정정(**틀린 표는 남겨 두고 정정 박스를 얹었다**) · 진입점 3곳의 "≈$5/월".
  **코드·게이트 무관**(1912 그대로, 안 돌렸다).
- Blockers: 없음. **단 4a 착수 전 결정이 하나 생겼다** — `write_relabel_configs` 허용목록.
  승인받은 $5는 **60초 간격에서 약 1,285 시계열**(전체의 2.5%)을 산다.
- Next: **추정표는 어느 칸이 측정이고 어느 칸이 가정인지 표시할 것.** 총액을 지배한 건
  가정 쪽이었다. ⚠️그리고 **권위 문서가 틀리면 복제본이 그걸 사실로 굳힌다** — 진입점
  3곳이 "$5"를 복제해 승인까지 갔다. **복제 금지 규약이 겨냥한 실패가 실제로 일어났다.**

## 2026-08-15 — 직전 고침이 남긴 기준을 다음 계약에 댔더니, 형제 집합이 다섯 번째로 걸렸다 (gate 1894→1912)

- Status: M19의 결론(**판단 기준은 읽는 쪽의 provider 간 비대칭**)을 `NormalizedIncident`에
  그대로 적용했다. `severity_hint`는 **네 시그널 어댑터가 전부 채우는데**(Azure
  `essentials.severity` · GCP `incident.severity` · onprem 라벨 · AWS 알람 상태) **읽는 곳은
  `aws/analyzer.py:200` 하나**였다.
- Verified(⚠️**레포가 스스로 적어 뒀는데 가드가 안 지켰다**): `test_analyzer_prompt_evidence.py`
  도크스트링이 **네 어댑터를 정확히 열거**하고 *"severity가 AUTO냐 APPROVE냐를 정한다 —
  07-29 라이브 관측: `warning` 규칙이 P1으로 등급 매겨져 즉시 조치됐다"*라고 쓴다. 그런데
  그 파일의 임포트는 **`aws.analyzer` 한 줄**이다 → **산문이 참이어도 임포트 줄이 범위다.**
- Verified(재현): 실제 `_build_prompt` — aws는 severity·alert detail 둘 다 YES,
  **gcp/azure는 둘 다 NO**. 두 정규화 블록은 **AWS의 고치기 전 다섯 줄과 글자 그대로 같다**.
  onprem은 `onprem_incident_pipeline.py:34`가 AWS analyzer를 임포트해 **이미 덮인다**.
- Changed: 프롬프트 두 줄 + **시스템 프롬프트 안전장치**("강한 증거지만 **구속력은 없다**")를
  같이 이식. ⚠️**안전장치 없이 라벨만 넣으면 구멍보다 나쁘다** — 라벨이 지시로 읽혀
  AUTO/APPROVE를 혼자 정한다. 어휘 → P1/P2/P3 **매핑은 안 한다**(정책, AWS도 안 했다).
- Changed(가드 +18): 기존 파일을 세 analyzer로 parametrize — 이식 전 **16 red**, **AWS 11은
  내내 초록**. 역방향 둘(힌트 없으면 줄 안 붙임 · 시스템 프롬프트가 "not binding"을 말함).
  onprem을 목록에서 뺀 이유를 **코드에 적었다**(빠진 것과 덮인 것은 구별돼야 한다).
- Verified: 변이 **6건 전부 red·생존 0**(무조건 붙이기 · 안전장치 제거 · 어휘 정규화 포함),
  복구 후 0 modified. `make check` **1912**(+18) · CI도 **1912** — 일치. 2026-08-15,
  로컬 macOS·py3.13. 증거 `operator-severity-never-reached-two-models.log`. PR #37.
- Blockers: 없음.
- Next: **"무과금 소진"이 일곱 번째로 틀렸고, 이번엔 목록 밖이 아니라 목록이 만든 기준에서
  나왔다.** 다음 수도 같은 자리에 있다 — **가드 파일의 임포트를 그 파일이 주장하는 범위와
  맞대 볼 것**(`observations`·`triggered_at`도 AWS만 읽는다).

## 2026-08-15 — 틀린 기록을 시험하러 갔더니, 옆에서 AWS가 이미 닫은 결함이 두 provider에 살아 있었다 (gate 1862→1894)

- Status: 먼저 **직전 세션의 문서 체크포인트가 커밋 안 된 채** 트리에 있었다(코드는
  `main`, 진입점 문서는 로컬만) → PR #33으로 닫았다. 그다음 `NEXT_PLAN`의 열린 항목
  **ⓑ**("`renew_certificate`가 GCP/Azure 어댑터에 매핑 없음")를 시험했다.
- Verified(**ⓑ는 틀렸다 — stale이 아니라 쓰일 때부터**): 읽지 말고 돌려서 쟀더니
  **네 provider 전부** 풀린다(`actions=[]` 없음). `git log -L`로 매핑은 **2026-07-09**부터
  있었다 — 그 기록이 쓰인 08-14 커밋보다 **한 달 앞선다**.
- Verified(**그 자리에 있던 진짜 결함**): 티어 2가 런북의 `resource_types`를 **안 읽는다**.
  AWS는 `_fits_resource`로 **이미 닫아 뒀고**, 어긋난 쌍 **67/81**이 GCP/Azure에선 그대로
  선택된다. ⚠️**AWS보다 조용하다** — AWS는 하드코딩 액션으로 폴백(시끄러움), GCP/Azure는
  풀리지 않는 capability를 **버리고 짧아진 목록**을 준다 → `certificate-expiry`가
  kubernetes-workload에 선택되고 **RTO 600을 달고 notify만 한다**.
- Changed: 규칙을 `runbooks/schema.py::fits_resource` **한 곳**에 두고 세 provider가 읽는다
  (AWS는 위임). 복사본을 안 늘린 건 `NEXT_PLAN` 유지 규약이 **이 티어를 예로** 적어 둔 그대로다.
  "양쪽 unknown이면 배제 안 함"은 AWS의 결정을 **옮긴 것**(발명 아님).
- Changed(가드 +32): ground truth를 **함수가 아니라 카탈로그가 선언한 데이터**에 댔다.
  전수 스윕(9타입 × 전 런북 × 2 provider) + 역방향 셋(선언한 타입은 뽑힌다 · unknown은
  아무것도 배제 안 한다 · **폴백은 게이팅 안 된다** — AWS엔 있고 여기엔 없던 짝).
  ⚠️**기존 테스트 2건이 red가 됐고 옳았다**: 픽스처가 모든 런북을 **k8s인 척** 물었다.
- Verified: 변이 **6건 전부 red·생존 0**, 복구 후 63 초록·0 modified. `make check`
  **1894**(+32) · CI도 **1894** — 로컬↔CI 일치. 2026-08-15, 로컬 macOS·py3.13.
  증거 `resource-types-declared-and-unread.log`. PR #33·#34.
- Blockers: 없음.
- Next: ⚠️**"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다.** 계약 필드 일곱을 훑어 보니
  **`provider`도 아무도 안 읽는데** 빌트인 9개가 **전부 `"aws"`**라, 읽기 시작하면 GCP/Azure는
  **전부 `generic-recovery`로 떨어진다**(=#30 이전 상태). 판단 기준은 **읽는 쪽의 비대칭**이지
  선언의 고아 상태가 아니다. 남은 무과금은 ⓐ·ⓒ(정책) · `slack_live_approval`(Slack 데모 선행).

## 2026-08-13 — 형제 집합 중 하나만 도는 가드를 사냥하다, 그 도구 안에서 같은 함정을 밟았다 (gate 1859→1862)

- Status: 오늘 두 건이 **같은 모양**이었다 — 가드가 **쓰는 쪽만**(티어 2) · 감사가
  **`for name in REPORT:`**(로깅 문). 목록을 다시 읽는 대신 **그 패턴 자체**를 물었다:
  형제가 N개인 집합을 **진부분집합만 도는 가드**가 또 있는가.
- Verified(**내 자신부터**): 새 가드의 `PROVIDERS = ["gcp","azure"]`가 좁은 게 아닌지 봤다 —
  `decision.py`는 셋뿐이고 onprem은 `runners/`를 타며 **AWS는 같은 블록이 아니라 다른
  구현**(점수제)이다. **둘이 맞다.**
- Verified(**전수 행렬, 아무도 잰 적 없다**): capability 17종 × provider 4종. 실행 어댑터가
  못 푸는 건 `increase_function_concurrency`/**onprem 하나뿐**이고 그건 **이미 알려진 정당한
  skip**이다(게이트의 `2 skipped`) → 감사가 **알려진 참을 재현** = 비공허.
  ⚠️`assert_*` 넷이 "아무도 못 푼다"로 나온 건 **내 탐지기가 틀린 것** — `verify`는 실행
  어댑터가 아니라 **별도 레지스트리 `_CHECKS`**가 푼다. **틀린 해소기에 물었다.**
- Verified(**그러다 진짜 질문**): `executor.py:221`이 `if provider == "onprem":`다 —
  **검증은 onprem에서만 돈다.** 나머지 셋은 `verify`를 계획에 싣고 실행하지 않는다.
  **그런데 결함이 아니다**: 코드가 경계를 **명시**하고(`executor.py:75`) `verified`를 True가
  아니라 **None(unknown)**으로 정직하게 보고하며, **그 정직성도 이미 가드돼 있다**.
- Changed(**문서 한 줄 — `src/` 무변경**): `COMPLETED_SUMMARY`가 *"per-step verify를 executor가
  실제 소비"*를 **무조건**으로 적고 있었다. 코드는 말하는데 요약은 안 해서, 그 줄만 읽는
  독자는 넷 다 검증한다고 믿는다 → **onprem 한정**임을 명시. **"과대 해석 금지"는 `STATUS`
  에만 걸리는 규칙이 아니다.**
- Verified(⚠️**스윕이 나에게 걸렸다 — 오늘 세 번째, 그것을 찾는 도구 안에서**): 카탈로그의
  `verify.capability`와 `_CHECKS`를 맞대 "구현됐는데 아무도 선언 안 함:
  `assert_node_unschedulable`"이 나왔는데 **틀렸다** — `verify_onprem_action:237`이
  `capability or VERIFY_FOR_ACTION.get(action)`라 **선언처가 둘**이고 나는 그 표를 안 봤다.
  **형제 집합은 세는 순간 전부 세지 않으면 하나가 조용히 빠진다.**
- Changed(정정 후 가드 4건, `TestEveryDeclaredCheckIsImplemented`): 진짜 불일치는
  **`assert_concurrency_applied` 하나**(구현 없음, 단 온프렘이 lambda 스텝을 못 resolve해
  **도달 불가**). 감사는 **선언처 둘을 다 읽고**, **양쪽을 읽는지 자체를 ground truth로**
  묻고, 예외는 `KNOWN_UNIMPLEMENTED`에 **이유와 함께** 두되 **이유보다 오래 못 살게** 한다.
- Verified: 변이 5건 red·생존 0, 복구 후 diff clean. `make check` **1862**(+3), 2026-08-13,
  로컬 macOS·py3.13. 증거 `verify-capabilities-declared-vs-implemented.log`.
- Blockers: 없음.
- Next: **패턴 사냥이 준 것은 결함이 아니라 범위였다**(오늘 두 번째). `src/`는 안 바꿨고
  **고칠 게 없다는 것도 측정**이다. 남은 무과금 항목은 전부 정책 판단이거나 외부 자원 대기.

## 2026-08-13 — 같은 변명을 세 번째로 시험했다. 이번엔 참이었고, 대신 가드가 반쪽이었다 (gate 1856→1859)

- Status: `PROGRESS_LOG`가 남긴 마지막 줄 — **"로깅 문은 REPORT 4개만. DOCUMENT/DUAL은
  의무가 거꾸로라 판단이 다르고, **안 봤다**."** 같은 꼴의 문장을 두 번 시험해 결함 여섯을
  얻었으므로(증거 로그 11·13절) 세 번째도 시험했다.
- Verified(**이번엔 변명이 참이었다**): 12절의 탐지기를 **재구현하지 않고 임포트해서**
  DOCUMENT 3개·DUAL 2개에 돌렸더니 **다섯 다 WARNING+ 호출에 안 닿는다**. 기본값
  (lastResort → stderr)이 이들에겐 **이미 옳은 스트림**이라 **고칠 게 없다**.
  세 번째 시험은 결함을 안 줬다 — **그것도 결과다**(안 본 것이 **볼 게 없다는 측정**이 됐다).
- Verified(**대신 가드가 절반만 묻고 있었다**, Risk 12④ⓒ): `_clis_that_can_warn()`이
  `for name in REPORT:`다. 감사는 **REPORT의 의무**만 강제하고 **DOCUMENT의 거울 의무**는
  아무 데서도 안 묻는다 — DOCUMENT CLI가 같은 리다이렉트를 부르면 `WARNING …`이
  **kubectl이 파싱할 문서 안으로** 들어가는데 그걸 red로 만드는 게 없었다.
- Verified(결과 실증, 서브프로세스): `render_tenancy` stdout 첫 줄이 `WARNING …`이 되고
  `yaml.safe_load_all`이 **`ScannerError`로 터진다**. ⚠️`manifest_generator` 사례(4절)보다
  **시끄럽게** 깨진다 — 거긴 `{'Usage': …}`라는 **유효한 매핑**이었다.
  ⚠️**내 첫 실증이 틀렸다**: 인프로세스로 `sys.stdout`을 갈아끼웠는데 경고는 **진짜
  stdout**으로 갔다 — `basicConfig(stream=sys.stdout)`은 **호출 시점의 스트림 객체를
  붙잡는다**. **리다이렉션은 흉내 내지 말고 실제로 걸 것.**
- Changed(**테스트만, `scripts/`·`src/` 무변경**): 가드 셋 — DOCUMENT는 리다이렉트를 부르지
  않는다 · DUAL은 **무조건적으로** 부르지 않는다(`--json`이 stdout을 문서로 만든다 =
  **모드마다 의무가 뒤집힌다**) · 이 둘이 스타일이 아니라 규칙인 이유를 **행동으로** 박은
  앵커(실제 CLI + 서브프로세스 + `pytest.raises(yaml.YAMLError)`).
- Changed(**안 만든 것**): DUAL의 **모드 조건부 리다이렉트**. 둘 다 지금 경고에 못 닿아
  **아무도 태울 수 없는 가드**가 된다 — 08-12 `severity_in`과 같은 판단. 정답만 적어 뒀다.
- Verified: 변이 5건 red·생존 0. 깨끗한 변이(임포트까지 넣은 것)에선 **의도한 가드 하나만**
  실패한다. 복구 후 46 passed + diff clean. `make check` **1859**(+3), 2026-08-13,
  로컬 macOS·py3.13. 증거 `report-streams-swept-across-all-clis.log` **15절**.
- Blockers: 없음.
- Next: 파이프 뒤 나머지 일곱은 **강제할 실패 경로가 없거나 이미 옳다**(재확인 불필요).
  남은 건 `slack_live_approval` 이중 노후화 하나인데 **데모를 실제 Slack에 태워야** 확정된다.

## 2026-08-13 — 레거시 dict를 덮는 테스트를 찾다가, 그 dict를 읽는 코드가 죽어 있었다 (gate 1825→1856)

- Status: 직전 세션의 Next를 **그대로** 따라갔다 — "`BUILTIN_RUNBOOKS`를 덮는 테스트가 있나".
  답은 **"있다, 5개 파일"**이었는데 전부 **dict의 모양**만 물었다(길이·키 집합·deepcopy).
  **읽는 쪽으로 갔더니** 거기서 나왔다.
- Verified(재현 먼저): GCP/Azure `_select_runbook` **티어 2(capability 카탈로그 스캔)가
  원리상 도달 불가**였다 — 같은 블록이 두 파일에 복사돼 있고 **열두 줄에 결함 셋**이다.
  ①`if not validate_runbook(rb)` — 그 함수는 **문제의 목록**을 돌려주니 빈 리스트=유효 →
  **유효한 런북마다 continue**(`schema.py:79`에 불리언용 `is_valid_runbook`이 있고 AWS는
  극성이 맞다) · ②`rb.get("steps", [])` — `steps`는 `CAPABILITY_RUNBOOKS` 것이고 built-in은
  `capabilities`를 선언한다 → 9개 전부 파생 집합이 `set()` · ③`estimated_rto_sec`는
  **출력 쪽 이름**, 계약 필드는 `rto_sec`. 결과: **GCP·Azure의 모든 인시던트가
  `generic-recovery`로 떨어진다.** ⚠️**안 터진다** — actions는 티어 3에서 정상 resolve되니
  결정은 채워져 보이고, **자기가 따른다고 주장하는 런북과 RTO만** 틀렸다.
- Verified(왜 못 봤나): 이 경로 커버리지는 `assert "runbook_id" in result`와 `!= ""` 두 줄.
  **둘 다 `"generic-recovery"`에 영원히 참이다** — Risk 12④ 그대로, 가드가 **독자가 읽는
  그 물건**(어느 런북이 골렸나)이 아니라 필드의 존재를 물었다.
- Changed(`src/` 양쪽 동형): 극성 정정 · 매치 면을 계약이 선언한 `capabilities`로 ·
  `rto_sec`으로. 기본값 300은 **없앴다**(안 돌던 티어라 보존할 동작이 없고, 이제
  `generic-recovery`에서 티어 2·3이 같은 답을 준다). **티어 1도** `rto_sec`으로 — 단
  **잠복이지 라이브 아님**(Firestore/Cosmos에 문서 0개, 시더 없음 → Risk 2와 같은 모양).
- Verified(하중, 변이 8 · 생존 0). ⚠️**두 번 틀렸다.** ⓐ**변이 하네스가 고장나 있었다** —
  `restore()`가 `git checkout --`라 **커밋 안 된 고침**을 날렸다 → M2 이후는 원본을
  변이시킨 것이고 red가 아무 의미 없었다. 알아챈 건 마지막 줄 "restored → 24 failed":
  **초록으로 안 돌아오는 복구는 복구가 아니다.** ⓑ**내 RTO 가드가 결함을 통과시켰다**
  (M3·M8 생존) — 픽스처로 고른 `disk-full`의 `rto_sec`이 **하필 300**, ③의 기본값과
  같은 값이었다. **기본값과 같은 값을 고른 픽스처는 가드가 아니다** → 여덟 케이스
  (RTO 여섯 종) 전부에서 단언하고, 카탈로그가 서로 다른 RTO를 갖는지도 가드로 물었다.
- Verified: `make check` **1856 passed, 2 skipped**(2026-08-13, 로컬 macOS·py3.13, +31).
  새 파일 `tests/test_capability_catalog_scan.py` 32건 — **두 provider가 같은 런북을
  고르는지**까지 묻는다(결함이 "한 블록 두 파일"이었으므로 한쪽만 고치는 게 이게
  살아남는 방식이다). 증거 `gcp-azure-capability-scan-was-unreachable.log`.
- Blockers: 없음.
- Next: 남긴 셋(고치지 않음, 증거 7절) — ⓐ`kafka-lag-spike`만 두 dict가 어긋난다
  (스텝에 `rebalance_consumer`, `capabilities`엔 없음 — **어긋난 쪽이 또 에스컬레이션
  스텝**이다). 어느 쪽이 진실인지는 정책 결정 · ⓑ`renew_certificate`가 GCP/Azure 어댑터에
  **매핑 없음** → `certificate-expiry`가 선택은 되는데 `actions=[]`(회귀 아님, 라벨이
  정직해져서 **이제 보인다**) · ⓒ티어 2는 **첫 매치가 이긴다**(AWS는 점수제) — 지금
  테스트가 고정했으니 우연이 아니라 결정이다.

## 2026-08-12 — "지금 비용 나가는 거 있어?" — MTD는 그 질문에 답하지 않는다

- Status: 코드 변경 없음, **측정 세션**. 세 클라우드에 "지금 도는 것"을 물었다.
- Verified(AWS): MTD **$9.73**을 그대로 읽으면 틀린다 — 일별로 가르니 **$8.03(EC2 Compute)은
  전부 08-09 중지 이전 누적**이고 08-10부터 0, 도는 인스턴스 전 리전 **0대**. "이번 달"로
  "지금"을 답하면 **15배쯤 크게** 본다. 남는 건 **중지된 인스턴스에 붙은 EBS 8GB**
  (~**$0.64/월** — **중지는 볼륨을 끄지 않는다**) + RDS 수동 스냅샷 1개. 미연결 EIP는 없다.
- Verified(**경고를 실물로 확인했고, 동시에 그 경고가 부정확했다**): `EC2-Other`가 08-11·08-12에
  0으로 찍혔는데 **볼륨은 지금도 `in-use`다** → 그 0은 **CE 지연**. 08-10에 적어 둔
  "당일 줄의 0은 잰 0이 아니다"가 처음으로 **증명 대상을 갖췄고**, 동시에 **지연은 하루가
  아니라 이틀 이상**임이 드러났다(문서는 "당일"이라고 썼다).
- Verified(**GCP를 처음 전수 조사**, `.env`의 `project-ec7809f7-…`): **금액은 여전히 못 잰다**
  (`billing_export` 데이터셋은 있고 **테이블 0개** — 콘솔 토글 미완). 대신 자원을 물었다:
  GKE·VM·디스크·고정IP·LB·**Vertex 엔드포인트**·CloudSQL·AlloyDB **전부 0**(7월 GKE 방치
  잔재 없음). **상시 과금은 스토리지뿐 ~$0.72/월** — Artifact Registry **7.31GB**(그중
  `cloud-run-source-deploy` **6.85GB**, 리비전 **84개** 누적) + GCS 1.88GB.
  Cloud Run `mythos-api`는 **scale-to-zero**(마지막 활동 08-10) → 메모리가 적은 "지속 지출
  = Vertex ~₩48K/월"은 **사용량 기반이고 지금은 발생 안 함**. 단 같은 메모리의 *"지속 지출은
  Vertex뿐"*은 **불완전**하다 — 스토리지가 호출과 무관하게 돈다.
- Verified(방법): **`PATH`를 벗기는 건 "오프라인"이 아니다** — boto3는 `PATH`가 아니라
  `~/.aws`를 본다. 08-11에 그렇게 돌린 `probe_incident_roundtrip`은 **실제 DynamoDB에
  write/read/delete를 했다**(설계된 동작, 자동 정리, 비용 무시 가능). 자격증명까지 벗기려면
  `AWS_PROFILE=__nonexistent__ AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null`.
- Blockers: **GCP 금액**은 콘솔 토글 전까지 못 잰다(사용자 몫). 조치는 **아무것도 안 했다** —
  EBS·스냅샷·AR 이미지는 되돌릴 수 없는 삭제이고, 인스턴스와 ACR은 **다른 프로젝트 소유**다.
- Next: **BQ 결제 내보내기 토글이 여전히 최우선**($0, 콘솔 수동, Phase 4 선행).
  ⚠️`.env`가 대화에 노출됐다 — `.gitignore:21`이 잡고 히스토리에도 없어 **레포는 깨끗**하지만
  세션 로그에는 남았다(AWS 키·Slack 웹훅·GitHub OAuth·서명 시크릿) → 회전 권고.
  증거 `what-is-actually-billing-2026-08-12.log`.


## 2026-08-12 — 게이트 줄의 `1 skipped`를 이름 불렀더니 62%짜리 walk가 나왔다 (gate 1789→1825)

- Status: `NEXT_PLAN`의 열린 항목이 전부 승인·외부 자원 대기라 "무과금 소진"으로 보였다.
  그 문서 자신이 **"소진은 목록의 상태지 사실이 아니다"**를 네 번 적어 놨으므로, 목록을 다시
  읽는 대신 **매번 인용하면서 아무도 이름 부른 적 없는 것**을 골랐다 — `1 skipped`.
- Verified(탐지기 둘, 결과 0): `find_unwritten_keys` 9 + `find_unconsumed_fields` 19 = **28건
  전부 이미 판정된 것**. 추정 없이 따라갔다 — `grounded`/`grounding_ratio`는 체인이 **완결**
  (`reconciliation.py:118`→`decision.py:87`→`executor.py:558`→`incident-data.ts:100`)이고
  탐지기가 놓친 건 **docstring이 예고한 nested-literal 한계**. `slack_ts`는 **M13이 이미 판정**
  (DTO surface, unread by design). **탐지기가 덮는 범위는 깨끗하다** → 덮지 않는 곳으로.
- Verified(skip은 정당): 지워 보니 `0 = len([])`로 red. 온프렘은 lambda 런북의 어떤 스텝도
  resolve 못 하므로 **안 도는 검사를 숨긴 게 아니다**. 이 게이트 줄의 Risk 12② 질문은 닫혔다.
- Verified(**그걸 읽다가 진짜가 나왔다**): `test_walk_all_steps`는 이름과 docstring이
  "every step"인데 단언이 **`>= 1`**이었고, 선언된 **16스텝 중 10개(62%)**만 걸었다.
  **안 걷는 6개는 예외 없이 `previous_step_failed: True` 분기** = **에스컬레이션 스텝 전부**
  (`rollback_release`·`open_change_request` 포함). 도달 불가였던 이유가 핵심 — 플래그가
  **`except ValueError` 안에서만** True가 되니 **뭔가 이미 깨져야** 둘째 분기가 열리는데,
  그 6스텝은 4 provider에서 **24/24 전부 resolve된다**. 행복 경로만 태운 walk에서 둘째
  분기는 **원리상 도달 불가**(Risk 12③).
- Changed(**전부 테스트 쪽, `src/` 무변경 — 구현은 처음부터 옳았다**): `started_failed` 축으로
  **양 분기를 명시적으로** 걷는다(깨지길 기다리지 않는다) · 단언을 **"조건이 맞은 모든 스텝이
  resolve"**로, `ValueError`는 **삼키지 않고 모아서 보고**(예전엔 "resolve 못 함"과 "도달 안
  함"이 구별되지 않았다) · `>= 1`은 **공허 통과 방지용으로 존치** · 반공허 가드로 **둘째
  분기가 실제로 스텝을 더 걷는지**와 `BRANCHES`가 양쪽을 덮는지를 묻는다.
- Verified(하중): W1·W2(카탈로그의 에스컬레이션 capability 오타) **red 5건·4건** · W3
  (`BRANCHES=[False,False]`) red · W4는 클린 상태에서 생존이 **정상**이고, 결함이 있을 때
  **5건 중 4건을 그 단언이 책임진다**(W4′). ⚠️**내 변이가 두 번 틀렸다** — `replace(...,1)`이
  첫 등장만 바꿔 **레거시 `BUILTIN_RUNBOOKS`의 메타데이터**를 쳤고, 그 오발을 쫓다
  "리터럴 vs 파생 9/9 불일치"라는 **틀린 측정**까지 갔다. 구조를 확인하니 두 dict는 **다른
  모양이고 `decision.py:135`가 갈라 쓴다** — 발산이 아니다. **주장 전에 확인해서 안 적었다.**
- Verified: `make check` **1825**(+36), 2026-08-12, 로컬 macOS·py3.13. 해당 파일 **85→120**.
  skip 1→2는 정상(onprem/lambda가 양 분기에서 각각 걸리고 사유는 양쪽 다 참).
  증거 `runbook-walk-skipped-the-escalation-branch.log`.
- Blockers: 없음.
- Next: **`BUILTIN_RUNBOOKS`(레거시 dict)를 덮는 테스트가 있는지 안 봤다** — 4절의 오발이
  거길 고쳐도 안 깨진다는 걸 보여 줬다. 그리고 조건 축은 `previous_step_failed`만 넓혔고
  **`severity`는 여전히 `"P2"` 고정**이라, `severity_in` 스텝이 생기면 같은 함정이 재발한다
  (지금 카탈로그엔 없어서 **가드를 안 만들었다** — 없는 문제의 가드는 하중을 못 받는다).


## 2026-08-11 — 맹점을 나머지 전부에 대고 물었다: 결함이 더 넓었다 (gate 1743→1787)

- Status: 어제 남긴 "`capsys` 맹점은 한 건만 봤다"를 소진했다. **훑는 방향을 뒤집은 게
  결정적** — `readouterr` 사용처(5파일 19곳)를 뒤지면 **테스트에 이름조차 없는 스크립트는
  목록에 없다.** `git grep sys.stderr -- scripts/*.py`로 물으니 attach_addon ·
  preflight가 나왔고 **둘 다 깨져 있었다.**
- Verified(재현, 네트워크 0·가짜 kubectl): 파이프로 읽으면 두 verify는 `context:` 한 줄,
  서명 검증기는 **완전히 빈 출력**에 exit 2. 가장 나쁜 건 netpol — stdout에 찍은
  `baseline: … ✓` 뒤에 판정이 stderr로 가서 **독자의 마지막 줄이 ✓**다. **✓로 끝나고 멈춘
  리포트는 끝난 리포트로 읽히고**, 그 판정이 `PROVEN_ENFORCING_SUBSTRATES` 승격을 정한다.
  ⚠️기존 evidence 로그가 실제로 판정을 잃은 사례는 **없다**(잃을 수 **있었다**).
- Changed(분류가 먼저였다 — 수정 목록·근거는 **M17이 권위**): 11개를 다 고치려다 멈췄다 —
  `render_tenancy.py`는 **처음부터 옳다**. 규칙은 "stderr 금지"가 아니라 **"독자의 스트림이
  독자가 필요한 걸 날라야 한다"**이고 독자가 파서면 의무가 **거꾸로** 선다. `scripts/*.py`
  **22개 전수**를 REPORT(17)/DOCUMENT(3)/DUAL(2)로 분류하고 미분류를 red로 막았다.
  수정 9건(+`src/` 1건), exit code 전부 유지. 대표적으로 attach_addon은 `--commit` 거부가
  diff 뒤라 **"committed 줄이 없다"가 유일한 실패 신호였다 — 없는 줄은 판정이 아니다**.
- Verified(하중): 변이 **16건 red, 생존 0** — D1~D3은 **거울 방향**, A1은 **미분류 새
  스크립트**. 게이트가 낡은 가드 **정확히 3건**을 잡았고 전부 `.err`에 묻던 것 → `.out`.
- Changed(덤) + Verified(같은 실수 재발): CE **요청당 $0.01** · `spend-watch` 월 **~$0.30**을
  프로브·워처 docstring에 명시. 가드 3개 중 하나가 **반증에서 살아남았다** — **주장**("오늘
  줄의 0은 잰 0이 아니다")만 묻고 **지시**("앞 며칠을 읽어라")는 안 물었다. 물건은 맞췄고
  **물건의 절반만** 물었다. 고쳐서 둘 다 red.
- Verified(같은 날 후속 — 남겨 둔 경계 셋을 전부 닫았다):
  ①**`src/`는 밖이 아니라 확인 대상이었다** — `sys.stderr` **0건**이라 REPORT 계열 결함은
  **없다**. 다만 DOCUMENT 진입점 **하나**가 깨져 있었다: `manifest_generator`를 인자 없이
  리다이렉트하면 usage가 파일에 앉고 **exit 0**인데 `yaml.safe_load`는 그걸 **`{'Usage': …}`
  유효 매핑**으로 읽는다 — **`kind` 없는 매니페스트로 한참 뒤에** 터진다. 변이 S1~S3 red.
  ②**버퍼링을 실제로 쟀다**(`stderr == ""`는 논증이었다) — 진짜 서브프로세스·파이프로.
  ③**verify_* 3종 전부 라이브**(클러스터에 이미 테넌시가 서 있어 **아무것도 안 바꿨다**):
  netpol **ENFORCED** · adoption **둘 다 ✓** · isolation **ISOLATION HOLDS**(4/4).
- Verified(**세 번째 문 — `print`가 없는 곳에서도 스트림은 골라진다**): "`src/` 로깅은 훑기
  밖"이라 적어 놓고 확인하니 **밖이 아니었다**. `src/`엔 **핸들러가 0줄**이라 레코드가
  `logging.lastResort`로 떨어지고 그건 **WARNING+ 를 stderr로 쓴다**. 임포트 그래프 감사 →
  17개 중 **4개**가 닿는다(`push_addon_status`=ambient read · `live_net_demo`=**STS 폴백,
  in-account 자격증명으로 내려감** · `probe_scope_reachability` · `probe_incident_roundtrip`).
  **둘 다 자격증명 경계 사건**이다. 넷 다 `_report_logging.send_library_logs_to_the_report()`.
  ⚠️**감사 자신이 먼저 틀렸다** — 첫 판이 `push_addon_status`를 "안전"으로 봤다(수신자가
  `log or logging.getLogger(...)`라 `ast.Name` 매칭이 놓쳤다). **알려진 양성이 없었으면 빈
  감사가 초록으로 지나갔다** → 그 양성을 가드로 박았다(변이 A2 red).
- Verified(**넷째 문 — 잡히지 않은 예외**; "나머지는 클러스터가 필요하다"를 시험한 결과):
  그건 **기록된 이유지 잰 이유가 아니었다**. `PATH`를 벗기니 넷이 **트레이스백으로 죽었다**
  (stdout 0B·**exit 1**). `probe_cloud_spend`는 **헤딩만 찍고 죽어** 08-10의 결함이 다른 문으로
  돌아왔고, `watch_cloud_spend`의 exit **1**은 "**새로 과금되기 시작했다**" — 못 쟀는데 경보다.
  원인이 정확했다: `_run`은 처음부터 막고 "never raises"라 적었는데 **형제 `_aws`가 안 했다**.
  ⚠️**변이 T4가 처음에 살아남았다** — 같은 가드가 `verify_tenant_isolation`에선 **닿는 행이
  없어 하중을 안 받고 있었다**(Risk 12③). 덤: 다섯은 **자기 docstring의 실행법이
  ModuleNotFoundError로 죽었다**(넷은 부트스트랩; `slack_live_approval`은 → NEXT_PLAN).
- Changed(문서): `/tidy-docs` — 08-09 3건을 `archive/progress-2026-08.md`로(최신이 위 유지) ·
  status의 baseline 5건은 M16 포인터로, "동작하는 영역"은 `AGENT_BRIEF` Snapshot과 **중복이라
  접었다** · 완료 2건 → **M17 신설**. **넷 다 예산 내.**
- Verified(**같은 변명을 두 번째로 시험했다 — 또 틀렸다**): 11절에서 "클러스터가 필요하다"를
  깨고도 남은 것들에 **같은 종류의 문장**을 다시 썼다("자격증명·기동한 스택이 필요하다").
  그 문장은 **성공 경로**를 묘사하고 있었다 — **실패 경로는 공짜다.** `live_tier2_demo`(포트
  거부)와 `probe_incident_roundtrip`(없는 프로필) 둘 다 **트레이스백·exit 1**이었고 고쳤다.
  후자는 **`main()` 전에** 죽는다(`reporting`이 임포트 시점에 boto3 리소스를 만든다) → 가드를
  임포트에 걸었다. 변이 V1~V4 red. ⚠️`live_tier2_demo` 가드는 **포트 1로 고정**했다(기본
  엔드포인트면 `make dev-up`을 띄운 개발자에게 성공 경로로 가 flaky) · 없는 프로필은
  **클라이언트 생성 중** 터져 **네트워크에 안 닿는다**(게이트가 라이브 AWS를 부르지 않는다).
- Verified(**기록해야 할 실수**): 10절 감사 때 `PATH`만 벗기고 `probe_incident_roundtrip`을
  돌렸는데 **`PATH`는 boto3 자격증명을 안 벗긴다** — 그 실행은 **실제 DynamoDB에
  write/read/delete를 했다**(설계된 동작, 스스로 정리, 비용 무시 가능). 의도한 라이브 호출이
  아니었다. **"오프라인으로 돌렸다"도 어떻게 확인했는지까지 말해야 한다.**
- Verified: `make check` **1743 → … → 1789**(+46), 2026-08-11, 로컬 macOS·py3.13; CI가
  #24~#28 **다섯 지점 전부 숫자까지 일치** — 초록이 아니라 **같은 숫자**로 Risk 12②를
  배제한다. 변이 누계 **45건 red, 생존 0**(T4는 1회 생존 후 하중을 붙여 red). 파이프 뒤
  **4 → 8 → 13 invocation / 11 CLI** — 두 번의 "시험해 보니 아니었다"가 **결함 6건**을 가져왔다.
  증거 `report-streams-swept-across-all-clis.log`.
- Blockers: 없음.
- Next: **못 하는 것과 안 한 것을 구분해 남긴다**(상세는 증거 로그 13절) — 못 함: 남은 CLI는
  라이브 자격증명·기동한 스택이 필요하거나 **강제할 실패 경로가 없다**(빈 레포에서도 exit 0);
  그걸 요구하는 가드는 **skip되는 가드**라 Risk 12②를 새로 만든다. ⚠️`live_tier2_demo`는
  스택이 없으면 본문 stdout + 트레이스백 stderr로 **같은 결함**인데, 고치려면 검증 수단(기동한
  스택)이 선행. 안 함: **`slack_live_approval` 이중 노후화** · 로깅 문은 **REPORT 4개만**.
  Phase 4는 **사용자 결정 대기**.

## 2026-08-10 — 비용 리포터가 리포트의 실패를 자기가 저질렀다 (gate 1737→1743)

- Status: `/sync` 뒤 프로브를 그냥 한 번 돌렸다. Azure가 429로 실패했는데 리포트의
  **`Azure 실사용` 헤딩 아래가 비어 있었다** — 판정은 맨 위, AWS 절보다도 앞에.
- Verified(재현, 네트워크 0): 세 CLI를 exit 1 스텁으로 바꾸니 **AWS·EC2·Azure 세 절이 전부
  빈다**. 본문은 stdout, 판정·이유는 stderr인데 **TTY에선 줄 버퍼링이라 멀쩡하다** = 저자가
  만들며 본 것. 읽는 경로는 전부 파이프(evidence 로그·`| tee`·캡처) → **읽히는 모든 경로에서
  깨져 있었다.** 멀쩡하던 절은 GCP뿐인데 GCP만 "상태를 절 안에서 stdout에" 찍고 있었다.
- Verified(가드가 못 잡은 이유가 더 크다): PR #19의 `..._reaches_the_reader`가
  `capsys.readouterr().err`를 봤다. **capsys는 두 스트림을 갈라 주므로 독자의 사본이 갈라진
  걸 원리상 못 본다** → **Risk 12의 넷째 얼굴 = 관측 지점**(①시간 ②환경 ③하중에 이어).
  ⚠️`capsys` 계열 전반이 같은 맹점 — **한 건만 봤다.**
- Changed: 본문을 **stdout 한 스트림**으로(`_unmeasured()` 한 곳, 이유는 절 안). **exit 2는
  그대로** · **측정값은 안 건드렸다** · `watch_cloud_spend.py:108`은 한 줄 찍고 즉시 return이라
  **두었다**. 새 가드 `TestTheReportIsOneStream`은 `main()`을 통째로 돌려 **독자가 읽는
  스트림**에 묻는다. 정적 가드 `assert "…'$0'이 아니다" in source`도 갈아치웠다 — 문구가
  조립되니 **소스 grep은 어떤 실행도 찍지 않는 문자열에 초록**을 준다.
- Verified: 변이 **M1~M6 전부 red, 생존 0**. `make check` **1743**(+6), 2026-08-10, 로컬
  macOS·py3.13 **↔ CI 1743 일치**(PR #22). 증거 `spend-probe-report-split-across-streams.log`.
- Verified(실측 2건, 코드 아님): ①**08-09 중지가 먹혔다** — EC2 Compute 일 **$0.998 → $0.043
  → 0**, VPC $0.12 → $0.005, 도는 인스턴스 0대(MTD $9.64는 거의 전부 중지 이전 누적).
  ②**측정 자체가 과금된다** — Cost Explorer **요청당 $0.01**(3건=$0.03 · 24건=$0.24 ·
  MTD $0.27), `spend-watch` 하루 한 번 = 월 ~$0.30. **아무 문서에도 없었다.**
- Blockers: 없음. 관측 구멍은 여전히 **GCP 하나**(콘솔 토글).
- Next: CE 요청당 $0.01을 프로브에 명시할지 · 나머지 `capsys` 가드 훑기.
  ⚠️**CE는 당일치를 늦게 보고한다** — 오늘 줄의 0은 잰 0이 아니다.

## 2026-08-09 — 정기 실행을 붙이다 진짜 구속 조건을 만났다 (macOS TCC, gate 1719→1737)

- Status: 세 클라우드를 다 재 놓고 남은 구멍은 **아무도 안 돌린다**는 것이었다(07-22 인스턴스를
  잡은 건 점검이 아니라 **18일 뒤 예산 경보**). 정기 실행을 붙이다 막혔고, **막힌 이유가
  기록할 값이 있다**.
- Changed: `scripts/watch_cloud_spend.py` + `make spend-watch`. 프로브와 같은 측정을 하되
  **임포트한다(다시 구현하지 않는다)** — 두 번째 진실 공급원의 재발 방지. **임계값은 발명하지
  않았다**: 예산이 "얼마나"를 답하고 08-09에 **실제로 작동했다**. 못 답하는 건 "그중 무엇이
  새 것인가"이고 그건 **새 줄이 생기는가**로 임계값 없이 답한다. 규칙 셋 — 첫 실행은 기준선만 ·
  측정 실패는 스냅샷을 **안 덮는다**(한 밤이 "새 것"의 기준을 리셋한다) · **사라진 건 발견이 아니다**.
- Blockers(실측): LaunchAgent를 등록하고 **실제로 쐈더니 exit 127**. 비보호 위치에 진단
  에이전트를 띄워 가르니 **`Operation not permitted` — 레포 읽기 자체가 거부**된다. 레포가
  `~/Desktop` 아래라 **macOS TCC**가 막는다(대화형 셸은 exit 0 — 이미 승인돼 있다).
  뚫으려면 `/bin/zsh`에 **Full Disk Access** = 이 기계의 **모든 zsh 스크립트에 전체 디스크**.
  비용 리포트 하나에 치를 값이 아니다. cron도 같은 벽 · CI 스케줄은 **세 클라우드 자격증명을
  시크릿으로** 올리는 큰 결정 · `make check`에 거는 건 **금지**(오늘 비판한 Risk 12② 그 자체).
- Changed(해법): **이미 허가된 것 위에 태웠다** — 터미널 열 때 하루 한 번. `~/.zshrc`에
  표시된 블록, `spend-watch-uninstall`이 **그 블록만** 지운다. ⚠️**깨진 `~/.zshrc`가 최악의
  결과**라 붙이기 전에 스크래치에서 `zsh -n` 통과를 확인하고, 붙인 뒤 로그인 셸 기동까지 확인.
- Verified: 스탬프 없음→돈다 · 같은 날→안 돈다 · 이틀 전→다시 돈다 · uninstall은 블록만 제거.
  ⚠️**한 번은 내 테스트가 틀렸다** — `mtime`이 초 단위라 1·3회차가 **같은 초**에 들어가
  "안 돌았다"로 보였다. **✗가 나오면 코드부터 의심하지 말 것.**
- Verified(조용함이 기능): 만들다 **429를 실제로 맞았고**, 매번 알리면 ₩20 예산의 반복이다 →
  **래퍼가 한 번 참았다 다시 묻고** 그래도 실패할 때만 말한다(대화형은 즉시 사실대로).
  알림은 **워처 밖**에 뒀다 — 안에 넣으면 "워처는 스스로 프로세스를 안 부른다" 가드를 내가 깬다.
  라이브에서 재시도 분기가 **안 탔으므로**(429가 풀렸다) 스텁으로 **가드에서 태웠다**.
  변이 **W1~W6·X1~X4 전부 red, 생존 0**. `make check` **1737**(+18).
  증거 `spend-watch-launchd-blocked-by-tcc.log`.
- Verified(CI가 나를 잡았다): 래퍼를 zsh로 쓰고 가드도 `/bin/zsh`로 불렀더니 **로컬 1737
  초록 / CI FAILURE 1733** — **Linux엔 `/bin/zsh`가 없다**. Risk 12②를 **그 문서를 인용해
  가며 짠 커밋에서** 그대로 밟았다. `skipif`는 **더 나쁘다**(skip과 pass가 같은 색) →
  래퍼를 **POSIX `sh`**로 바꾸고(`sh -n`·`dash -n` 통과) 가드는 **경로로 직접 호출**한다.
  고친 뒤 **CI 1737 = 로컬 1737** — 네 가드가 이제 양쪽 기계에서 진짜로 돈다.
- Next: **레포가 `~/Desktop` 밖으로 가면 launchd가 다시 열린다**(터미널을 안 여는 날에도 돈다).
  지금 구조의 한계가 정확히 그것 — **터미널을 안 열면 검사도 없다.**

## 2026-08-09 — 남겨 둔 미확인 가정 하나를 닫았다 (Azure 크레딧, gate 1718→1719)

- Status: PR #18에서 **"Azure의 크레딧 상계는 물어본 적 없어 적지 않았다"**고 남겼다.
  오늘 짠 코드에 남은 **유일한 미확인 가정**이라 물어봤다.
- Verified(네 각도, 같은 숫자): 2026-07 `ActualCost` = `AmortizedCost` =
  **22,630.5746347082 KRW**(소수점 열째 자리까지 동일) · ChargeType은 **`Usage` 한 행**
  (Refund/Purchase/Adjustment **0건**) · PublisherType은 `Microsoft` 한 행.
  → **프로브가 출력하는 숫자는 지금 아무것에도 상계되지 않는다.**
- 과대 해석 금지: 두 값이 같은 건 **예약·절약 플랜이 없어서**지 API가 크레딧을 무시해서가
  아니다(선불 구매가 있으면 Actual은 **구매한 달에 한 번에**, Amortized는 **나눠서** 잡힌다).
  **"Azure엔 AWS 같은 크레딧 함정이 없다"는 측정하지 않았다.** 다시 볼 조건 = 예약을 사는 것.
  AWS는 크레딧 필터를 **코드에 박아야** 했지만 여기선 **박을 필터가 없다** — 없는 문제에
  대한 가드는 하중을 못 받으므로 **조건만 적었다**.
- Changed(덤으로 나온 것): 측정 중 **Cost Management가 429를 뱉었다**(연속 서너 번이면 걸린다,
  75초 백오프로 통과). 프로브의 exit 2는 이미 옳았는데 **왜 실패했는지를 말하지 않았다** —
  구독별 질의 경로만 이유를 삼키고 있었다. 429는 **일시적이고 대응이 "1분 뒤 다시"**인데
  이유 없는 "측정하지 못했다"는 **자격증명이 깨진 것처럼 보인다**. `_why()`로 네 경로의
  실패 메시지를 통일(기존 `[-1:]` 리스트 repr도 정리). **자동 재시도는 안 넣었다** — 조용히
  75초 자는 프로브는 30초 명령의 계약을 바꾼다.
- Verified: 반증 — 이유를 다시 삼키면 `test_the_reason_for_a_failure_reaches_the_reader`만
  red. `make check` **1719**(+1), 2026-08-09, 로컬 macOS·py3.13.
  증거 `azure-credit-netting-does-not-apply-yet.log`.
- Next: 비용 관측의 구멍은 **GCP 콘솔 토글 하나**뿐이다.

## 2026-08-09 — Azure는 잴 수 있었다, 이름이 맞는 명령이 0을 줄 뿐 (gate 1709→1718)

- Status: 어제 Azure를 **일부러 남겼다** — "못 잰다"가 아니라 "안 쟀다"였고 확인 없이 적지
  않았다. 확인했다: **잴 수 있고, 쓰고 있었고, 아무도 못 보고 있었다.**
- Verified(같은 창, 두 명령, 다른 답): `az consumption usage list`는 08-01~08-09에 **28행을
  exit 0으로** 돌려주는데 **`pretaxCost`가 28행 전부 null** → 합계 **정확히 0**. 같은 창을
  Cost Management로 물으면 **₩1,989.33**. 이 레포 **세 번째** 같은 계열이고 가장 깨끗한 표본
  (AWS=크레딧 상계 · GCP=provider 누락 · Azure=cost 없는 행) — **셋 다 호출이 성공한다.**
- Verified(실지출): 7월 **₩22,630**(Foundry Models 17,950 · ACR 4,394 · VM 134 · 그 외).
  8월 MTD **₩1,989 전부 `acrroadpilot23842f7d`**(Container Registry **Basic**, `rg-roadpilot`,
  07-14 생성) = **월 ~₩6,600 고정 요금**. ⚠️**다른 프로젝트 리소스**라 slackops 때와 같이
  **보고만 하고 두었다**(종료는 소유자 판단).
- Verified(기록 하나는 성립): "**Azure Foundry 유휴 ≈$0**"은 **참**이다 — 8월 MTD ₩0이고
  7월 ₩17,950은 유휴가 아니라 **실사용**(소비 기반). 단 "Azure=≈$0"으로 **넓혀 읽으면 틀린다**
  (ACR 고정 요금은 유휴와 무관).
- Changed: 프로브가 **세 provider를 전부** 답한다. Cost Management API 사용(가드가 **호출
  인자에 `consumption`이 나오면 red** — 문자열이 아니라 실제 호출을 본다) · **전 구독 스윕** ·
  **창을 명시 전달**(`TheLastMonth`는 API가 **거부**한다 → 과거를 묻는 순간 깨진다) ·
  **통화를 들고 다닌다**($ 가정 시 한 리포트에 두 단위가 섞인다) · POST는 **query 엔드포인트
  하나로 URL 고정**. 실패는 **exit 2**(GCP와 다른 이유: 읽을 API가 **있는데** 못 읽은 것).
- Verified(하중): 변이 **7건 전부 red, 생존 0**. `make check` **1718**(+9), 2026-08-09,
  로컬 macOS·py3.13. 증거 `azure-consumption-cli-returns-null-cost.log`.
- Next: 비용 관측의 구멍은 **GCP 하나**뿐 — 콘솔 토글에 막혀 있다. Azure의 크레딧 상계
  (`ActualCost` vs `AmortizedCost`) 여부는 **물어본 적 없어 적지 않았다**.

## 2026-08-09 — 콘솔 수동 작업에 절차와 확인법을 붙였다 (gate 1708→1709)

- Status: 남은 $0 선행(BQ 결제 내보내기)은 **API가 없어 손으로 해야 한다**는 게 확정됐으니,
  손으로 하는 것에 **절차·검증·함정**을 붙였다. `docs/GCP_BILLING_EXPORT_SETUP.md`
  (`SLACK_APP_SETUP.md` 선례와 같은 자리).
- Verified(문서에 들어간 값은 전부 실측): 결제 계정 `010556-A2B7AE-292490`(예산 ₩14,000·
  ₩28,000 확인) · 대상 프로젝트에 **BigQuery API 활성** · `billing_export` 데이터셋
  asia-northeast3, OWNER `yeongsigchoe7@gmail.com` · **새로 만들 것 없음**.
- Changed(가장 중요한 한 줄): **내보내기는 소급 적용이 안 된다** — 켠 시점부터 쌓인다.
  **07월 GKE 방치 비용은 이걸로도 복구되지 않는다.** 미루면 그만큼이 영구 조회 불가로 남는다.
- Changed(함정 예고): 쿼리에서 `cost`만 더하면 **크레딧 미반영 총사용액**이다 — AWS에서
  크레딧 때문에 "$0"을 두 번 보고한 것과 **정확히 반대 방향의 같은 함정**이다.
  그리고 **첫 테이블까지 수 시간** 걸리므로 저장 직후의 "아직 못 잰다"는 실패가 아니다.
- Changed(프로브): GCP 절이 이제 그 문서를 가리킨다. + **가드**: 프로브가 가리키는
  `docs/*.md`가 **실재하는지** 검사한다 — 죽은 포인터는 없는 포인터보다 나쁘다(권위를 달고
  아무 데도 안 보낸다). 반증: 문서를 옮기면 **그 가드만 red**.
- Verified: `make check` **1709**(+1), 2026-08-09, **로컬 macOS·py3.13과 CI 일치**(PR #17).
- Next: 토글은 사용자 몫(콘솔). 켜면 `make spend-check`의 GCP 줄이 바뀐다.

## 2026-08-09 — spend-check가 GCP를 통째로 빼먹고 있었다 (gate 1699→1708)

- Status: "BQ 내보내기가 유일한 길"이라는 기록을 **먼저 돌려 봤다**(레포 규약). 이번엔
  **3건 전부 성립** — 그런데 확인하다 다른 게 나왔다.
- Verified(기록 재측정): Cloud Billing v1 discovery = **19 메서드, `export`/`bigquery` 0건**
  (`services.skus.list`는 가격표지 사용량이 아니다) · Budgets `Budget` 스키마 8필드 중
  실지출 readout **없음**(`spendBasis`는 규칙 기준 enum) · `gcloud billing` 그룹 =
  accounts/budgets/projects **뿐** · `billing_export` 데이터셋은 있고 **테이블 0개**(07-21 생성).
- Changed(진짜 발견): `probe_cloud_spend.py`에 `gcp|azure` 언급 **0건**이었다. 4-provider
  플랫폼에서 `make spend-check`는 AWS만 답했고 — **빠진 provider는 잰 0과 구별되지 않는다**.
  08-09에 고친 "못 봤다가 $0으로 렌더된다"를 **한 칸 옆에서 반복**하고 있었다. GCP에 대해
  **숫자가 아니라 상태**를 출력하게 했다(잴 수 있나/없나 + 왜 + 켜는 경로).
- Changed(설계 판단): **exit 2로 안 만들었다** — "질의가 실패했다"(AWS)와 "질의가 존재하지
  않는다"(GCP)는 다르고, 매번 빨간 프로브는 **건너뛰는 습관**을 만든다. 이번 주에 고친
  **상시 발화 ₩20 예산과 같은 계열**이다. 또 데이터셋 이름이 아니라 **테이블 이름**으로 찾고
  (콘솔이 대상 데이터셋을 아무 이름으로나 고르게 한다), **프로젝트를 훑는다**(활성 하나만
  보는 건 EC2 단일 리전과 같은 실패). **부수 효과**: 사용자의 콘솔 토글이 먹혔는지 **확인할
  수단이 생겼다** — 지금까진 없었다.
- Verified(하중): 변이 **5건 전부 red, 생존 0**(스윕 제거·데이터셋명 판정·문장 삭제·파싱
  실패를 "찾음"으로·AWS 실패 시 early return). `make check` **1708**(+9), 2026-08-09,
  **로컬 macOS·py3.13과 CI가 일치**(PR #16 — 두 기계에서 같은 숫자, Risk 12②). 증거 `gcp-actual-spend-has-no-api.log`.
- 품질 메모: 처음 쓴 가드 하나가 `_run`을 대체하지 않아 **게이트가 라이브 gcloud를 호출**했다
  (파일 하나 **21.97s** → 대체 후 **0.02s**). 자격증명 없는 기계에선 답이 달라진다 = Risk 12②.
  빈 데이터셋의 `bq ls`는 `[]`가 아니라 **무출력**이라 파싱이 예외를 던진다 — 그걸 "찾음"으로
  처리하면 거짓 초록(M4가 잡는다).
- Next: BQ 내보내기 토글(콘솔, 사용자 몫) · 4a 승인. **Azure는 손대지 않았다** — GCP와 달리
  실지출 API가 있다고 알려져 있어 **"못 잰다"가 아니라 "안 쟀다"**고, 확인 없이 적지 않는다.

## 2026-08-09 — 거짓말하던 예산 경보를 참말하게 (GCP, 클라우드 변경 1건)

- Status: 추천안 1순위(GCP 예산 재보정)를 수행했다. 코드 변경 없음, 클라우드 설정 1건.
- Changed: 계정 전체 예산 `Smart-EV demo budget 20USD`가 이름과 **약 1,400배** 어긋난
  **₩20**(≈$0.015)이라 **매달 확정적으로 발화**하고 있었다 → **₩28,000**($20 상당)으로 수정.
  임계값(50%/100%) 보존 확인. 롤백은 `--budget-amount=20KRW`.
- Changed(범위 축소는 **불가능했다**): 좁히려던 대상 **Smart-EV 프로젝트가 계정에 없다**
  (`gcloud projects list` 4개 중 없음). 즉 그 예산은 **존재하지 않는 대상의 이름을 달고**
  계정 전체에 걸려 있었고, `monthly-10usd-alert`가 주지 않는 신호를 **하나도 더 주지 않았다**.
- Verified: 적용 후 다시 읽어 확인(저장≠집행). 삭제하지 않은 이유 — 남의 이름을 단 예산이고
  삭제는 되돌리기 어렵다. **금액 수정이 맞는 이유**: ₩20에선 발화가 **항상 거짓**, ₩28,000에선
  **발화하면 참**이다(그때는 ₩14,000 예산도 이미 울렸을 것이므로 둘이 같은 진실을 말한다).
- Blockers(정정 포함): **GCP 실지출은 여전히 못 잰다.** ⚠️내 이전 권고가 부정확했다 —
  **Cloud Billing API를 켜도 비용 상세는 안 나오고**(계정·프로젝트 연결만), **GCP Budgets API는
  AWS와 달리 `ActualSpend`를 돌려주지 않는다**. **BQ 결제 내보내기(콘솔 수동)가 유일한 길**이다.
- 품질 메모: 조회 자체가 기본값으로는 실패한다 — `gcloud billing budgets list`는 **활성
  프로젝트**를 쿼터 프로젝트로 쓰는데 거기 API가 꺼져 있다. `--billing-project`로 지정해야
  보인다. 오늘 목록에 하나 더 추가된 셈이다(기본값이 틀린 답 또는 실패를 준다).
- Next: BQ 내보내기 토글 · 4a 승인 — 둘 다 사용자 몫.

## 2026-08-09 — docstring이 코드보다 오래된 모델을 가리키고 있었다 (gate 1697→1699)

- Status: 외부 문의(해커톤 요건 적합도)를 재다가 찾았다. 필수 요건이 "Gemini 3.5 이상"이라
  실제 모델 ID를 확인했더니 **문서와 코드가 달랐다**.
- Changed: `adk_deployer.py` docstring이 기본값을 `gemini-2.5-flash`라 적었는데 **코드는
  `gemini-3.5-flash`**였다. docstring 보고 설정하는 사람은 **더 낡은 모델을 고정**하게 된다.
  모델 ID는 능력·비용·요건 판정에 다 걸리므로 사소하지 않다.
- Changed(가드): 기존 `test_default_model`은 **`"gemini" in model`**만 봤다 — 2.5든 3.5든
  통과하니 이 드리프트를 **원리상 못 잡는다**. 문서가 적은 기본값과 코드의 기본값을 **서로에게**
  고정하는 가드로 교체(+ env 오버라이드 가드). 반증: docstring만 되돌리면 그 가드만 red.
- Verified: `make check` **1699**(+2). 계열인지 확인하려 `src/`의 env 기본값 전수 스윕 →
  **후보 2건 중 1건은 오탐**(`local_deployer`의 `:18081`은 일치) → **이번 건은 단발**이다.
- 품질 메모: 반증 중에 **가드가 아니라 도구에 속았다** — `2.5`와 `3.5`는 **바이트 수가 같아서**
  같은 초 안에 두 번 고치면 Python이 `.pyc`를 유효하다고 보고 **낡은 바이트코드를 쓴다**
  (mtime+size로만 검증). 원복했는데도 red가 나서 코드를 의심할 뻔했다. **반증 루프는 캐시를
  지우고 돌려야 한다.** 오늘 반복된 것과 같은 계열 — 도구의 기본값이 틀린 답을 준다.
- Next: 사용자 결정 대기(4a 승인 · GCP 예산 재보정 · 결제 내보내기).

## 2026-08-09 — 측정법을 산문이 아니라 프로브로 (gate 1685→1697)

- Status: 비용 오보 재발을 막는 건 승인이 필요 없다. 문서에만 적어 두면 다음에 또 손으로
  잘못 묻는다 — 레포의 프로브 관례로 박았다.
- Changed: `scripts/probe_cloud_spend.py` + `make spend-check`. **크레딧 제외 필터**
  (`Not RECORD_TYPE in [Credit,Refund]`)와 **전 리전 스윕**을 코드에 고정. 조회 실패는
  **exit 2** — "못 봤다"가 "$0"으로 렌더되는 것이 이 사건의 전부였다. 읽기 전용이고
  아무것도 중지·종료하지 않는다(가드가 mutating 동사 부재를 확인한다).
- Verified: 라이브 — 손으로 물으면 $0이던 계정이 프로브로는 **$8.80**. 반증 2건: 필터를
  빼면 `test_the_cost_call_actually_passes_it`, 단일 리전으로 바꾸면
  `test_the_instance_query_is_run_per_region`만 red(**해당 가드만** 정확히 반응).
  `make check` **1697**(+12). 증거 `docs/evidence/aws-spend-hand-check-was-zero.log`.
- Blockers: 없음. GCP 예산 재보정·결제 내보내기는 콘솔 수동이라 사용자 몫.
- 품질 메모: **네 metric(Unblended/NetUnblended/Amortized/Blended)을 전부 시도해도 ≈0이었다**
  — metric을 바꾸는 것으로는 안 나온다. 필터가 문제였고, 그래서 가드도 metric이 아니라
  **필터의 존재와 실제 전달**을 잰다(상수만 선언하고 안 쓰는 것도 red).
- Next: 4a 승인(≈$5/월) 또는 GCP $0 선행 — 둘 다 사용자 결정.

## 2026-08-09 — "AWS 이번 달 $0"을 두 번 보고했고 두 번 다 틀렸다 (실제 $8.81)

- Status: 사용자가 AWS 예산 경보($8.50 임계, 실제 $8.81)를 전달했다. 내가 같은 날 두 번
  "AWS 8월 $0"이라고 보고한 직후다. **점검이 아니라 경보가 잡았다.**
- Changed(원인 2개, 둘 다 안심시키는 방향): ①`aws ce get-cost-and-usage`는 **크레딧을 포함**해
  집계한다 — 크레딧이 사용액을 상계해 **순액 ≈$0**이 나왔다. 예산은
  `Not RECORD_TYPE in [Credit,Refund]`로 **총사용액**을 잰다. **두 숫자는 다른 질문의 답**이고
  (얼마가 청구되나 vs 얼마를 쓰고 있나) 방치 리소스는 후자로만 보인다. ②EKS·AMP만 보고
  **EC2를 안 봤다**. 전 리전 스윕이 필요했다.
- Verified(실측): 8월 실사용 **$8.81**(EC2 $7.54 · VPC 공인IPv4 $0.92 · 나머지 $0.33),
  월말 예측 ~$35.6. 원인은 **`slackops-devops-agent`(t3.medium, us-east-1)가 07-22부터
  18일째** 실행. 전 리전 스윕에서 running은 그 하나뿐, NAT/EIP/VPC엔드포인트 0.
- Changed(조치): **중지**(종료 아님 — 되돌릴 수 있다). `stopped` + 공인 IP 해제 확인,
  남는 건 gp3 8GB ~$0.64/월. 중지 후 전 리전 running **0대**. 남은 21일 ~$24 절감.
  다른 프로젝트(`Project=slackops-devops-agent`) 리소스라 **종료는 소유자 판단**으로 남겼다.
- Blockers: 이 레포의 07월 과금 감사 기록은 "slackops **EBS 월~$5만 잔존**"이라고 적었다 —
  그건 인스턴스가 꺼져 있다는 전제다. 기록과 실제가 달랐다.
- 품질 메모: **기본값이 안심시키는 답을 주는 도구가 셋이었다** — 크레딧 포함 집계 · `head`로
  자른 출력 · 단일 리전 조회. 오늘 산정 문서가 밟은 함정 셋이 전부 같은 계열이고 전부
  **"없다"를 성급히 주장**했다(관측 수단 0 · managed 어댑터 없음 · AWS $0). **"없다"는
  "안 보였다"보다 강한 주장이라 어떻게 봤는지를 같이 적어야 한다.**
- Next: GCP ₩20 예산(상시 발화) 재보정이 더 급해졌다 — AWS 경보는 작동했지만 GCP는 그
  채널이 이미 포화다.

## 2026-08-09 — managed 백엔드를 세 경로가 다르게 알고 있었다 (gate 1676→1685)

- Status: 추천안 2번(4a)의 **과금 없는 코드 부분**을 진행하려다, 4a 코드가 이미 대부분
  있다는 것과 **렌더 경로 하나만 비어 있다**는 것을 찾았다.
- Changed(정정): 어제 산정 문서의 *"managed 어댑터 구현 없다"*는 부정확했다. `from_managed`
  (`applicable=False`)도 `collector.py:451`의 managed 분기도 이미 있다 — 설계 문서가 Phase 2에서
  faked 디스크립터로 증명하라던 게 실제로 되어 있었다. **세션에서 "없다"를 세 번째로 잘못 말했다.**
- Changed(진짜 구멍): 세 경로가 서로 다르게 안다 — **읽기**는 알아보고, **쓰기**는 만들 수 없고
  (`registry_write`가 `managed=True` 없이 해석), **렌더는 모른다**. `desired_addons`가 백엔드를
  Helm 차트 이름으로 그대로 넘겨(`argocd.py`: `"chart": addon.backend`), `logging: cloudwatch-logs`
  선언 시 GitOps가 **Grafana 저장소에서 `cloudwatch-logs` 차트를 찾는다**(라이브 실증).
  `ManagedBackendNotRenderable`로 거부하고, `is_managed`를 **collector와 같은 콜러블**로 받는다
  (두 경로가 "managed인가"에 두 답을 갖지 않도록 — 431aeab가 지운 모양).
- Verified: 반증 2건 red(가드 제거 시). `make check` **1685**(+9).
  ⚠️정밀화 2회: `observability`로 재려다 **클러스터 스코프라 싱글턴 가드가 먼저 잡는 것**을
  발견 → 막히지 않는 조합은 **네임스페이스 스코프 + managed**(`logging`·`tracing`)뿐이라 그걸로
  교체 · 현재 레지스트리엔 **클라우드 substrate가 0**이라(kind·k3s) 이 경로가 도달 불가여서
  테스트가 env를 **짓는다** — 그게 정확히 Phase 4가 만드는 것이다.
- Blockers: 4a의 나머지는 **과금**이다(AMP 워크스페이스). 승인 대기.
- 품질 메모: 클러스터 스코프 managed는 싱글턴 가드가 잡되 **안내가 틀린다**("Prometheus CR을
  주라" — 관리형엔 설치할 것이 없다). 고치지 않고 기록했다 — 가드 순서를 바꾸면 기존 에러의
  정체가 바뀌고, 그건 "managed가 무엇을 렌더해야 하는가"라는 Phase 4 결정과 같이 가야 한다.
  **무엇을 렌더할지는 일부러 발명하지 않았다.**
- Next: 4a 승인(≈$5/월) 또는 $0 선행(예산 재보정·결제 내보내기) — 둘 다 사용자 몫.

## 2026-08-08 — 커밋을 경로에 한정 + 막힌 근거 재측정 (gate 1668→1676)

- Status: attach UI를 재려다 **그 앞의 구멍**을 먼저 찾았고, 이어서 남은 막힌 항목의
  근거를 돌려 봤다. PR #6·#7 병합.
- Changed(**구멍**): `attach_addon.py`가 조작자에게 `git commit -am`을 시켰다. `-a`는
  **수정된 모든 추적 파일**을 담으므로, 다른 게 더러우면 계획이 이름 댄 적 없는 파일까지 든
  PR이 열린다 — **"한 파일만" 불변식을 세우려고 존재하는 도구가 자기 지시로 그걸 깨는 경로**를
  들고 있었다. `commit_attachment`로 **경로 한정 커밋**(`-- <path>`) + `--commit`.
  브랜치 선점검은 **파일을 쓰기 전에** 돈다(아니면 "거부했는데 편집은 남는다").
  push·API는 그대로 조작자 몫.
- Verified: 반증 — `-- <path>`→`-a`로 **3건 red**, 브랜치 가드 제거로 **2건 red**.
  테스트는 트리를 **일부러 더럽힌 채** 잰다(**깨끗한 트리에선 두 방식이 구별되지 않고, 그래서
  안 보였다**). 라이브(임시 클론, 3파일 더럽힘): 커밋에 담긴 파일 **1개**, push 0 —
  하필 그 더러운 둘이 **이 도구의 소스**였다. `make check` **1676**(CI 일치, 새 git 테스트
  8건 리눅스에서도 PASSED).
- Verified(내 가드가 또 틀렸다): 처음 쓴 브랜치 테스트는 **가드를 지워도 초록**이었다 —
  `switch -c`가 내는 **git 자신의** 메시지에도 `already exists`가 있어 match가 그걸 받았다.
  그리고 "같은 첨부 두 번"은 이 가드의 시나리오가 아니었다(**플래너가 한 층 먼저** 거부).
- Changed(**근거 재측정**): attach UI가 막힌 이유가 "Next+FastAPI 두 층"이 아니다 —
  **FastAPI 층이 아예 없다**(Next→OIDC→DynamoDB). 진짜 구속 조건은 쓰기 대상이 git 파일인데
  UI는 Vercel이라 파일시스템·git·python이 없다는 것 → 같은 줄의 "실제 PR 생성"은 별개 잔여가
  아니라 **이 항목의 구속 조건**이다. MCP 항목도 근거만 틀렸다(생성자 0이 아니라 `bridge.py:35`
  하나, 그걸 만드는 건 테스트뿐). **성립한 근거 3건**(cost_metrics·kind 스냅샷·Cosign/k3s)은
  그대로 뒀다 — **성립하는 것도 결과다.**
- Blockers: 남은 항목은 전부 **승인·비용 / 정책 결정 / 외부 조건 / 선행 인프라 / 보류 지시**.
- 품질 메모: **세는 함정 둘을 실제로 밟았다** — `src/stacks/cdk.out`은 untracked인데 파일
  grep은 무시된 디렉터리까지 훑고(첫 측정 10건이 전부 빌드 사본), **docstring 사용 예시가
  호출로 보인다**. 후자는 **D39가 이미 밟은 함정**이라 이번엔 결론이 아니라 **세는 방법**을
  계획에 적었다.
- Next: Phase 4(billable, 별 승인)와 attach UI(플래너를 어디서 돌릴지) 둘 다 승인 사안.


## 2026-08-08 — 게이트가 검사하지 않는 것과 통과하는 것이 같은 색이었다

- Status: 미커밋 `/tidy-docs` 증분을 PR로 랜딩하다가(**PR #2**) CI 로그에서 문서와
  어긋나는 숫자를 봤다 — 문서 baseline `1668 passed, 1 skipped`인데 CI는 **1666/3**.
- Changed(원인): 수집 총계는 1669로 같고 **2개가 pass→skip**이었다. 하필
  `test_terraform_module`·`test_onprem_addons_module`의 `test_terraform_validate_passes`
  = **이 레포가 배포하는 IaC를 검증하는 둘**. `skipif` 조건이 **`terraform 미설치 OR
  모듈 미초기화`**인데 러너가 **두 절을 다** 만족했다(바이너리 없음 + `.terraform/`는
  gitignore라 새 체크아웃은 초기화된 적 없음 → **설치만 해도 여전히 skip**).
  즉 **D43이 병합 조건으로 삼은 게이트가 자기가 대체한 기계보다 적게 검사했다.**
- Changed(수정, **PR #3**): `gate.yml`에 `setup-terraform` **1.15.8 핀**
  (python 3.13 핀과 같은 이유=로컬에서 검증된 버전) + `terraform_wrapper: false`
  (테스트가 subprocess로 파싱) + `init -backend=false` **두 모듈만**
  (`infra/onprem/terraform`을 주장하는 테스트는 없다). 버전은 **커밋된 lock 파일**이
  고정하므로 자격증명 없이 결정적이다.
- Verified(반증 먼저 선언): *"init을 지우면 1666/3으로 돌아간다"* → 수정 후 CI가
  **1668/1**, 두 테스트 **PASSED**, 남은 skip 1건은 의도된 인-테스트 skip.
  run `31250113860`(전)↔`31250493800`(후). 증거
  `docs/evidence/ci-terraform-validate-skipped.log`. PR #2·#3 병합 완료.
- Changed(정리 중): 아카이브가 **자기 자신**을 "이전 이력"으로 가리키던 순환 포인터 1건 정정.
- Blockers: 없음. 남은 건 Phase 4(billable, 별 승인).
- 품질 메모: **skip은 실패가 아니라서, 검사하지 않는 게이트와 통과한 게이트가 같은
  색이다.** Risk 12②와 같은 계열이되 방향이 반대다 — 12②는 "로컬만 통과"였는데 이건
  **로컬이 통과시키고 CI가 안 도는** 쪽. 그래서 게이트 숫자에는 날짜(12①)뿐 아니라
  **어느 기계에서 쟀는지**도 붙어야 한다.
- Next: Phase 4(billable, 별 승인)만 남았다.


## 2026-08-08 — 문서 정리: 예산보다 진입점이 문제였다

- Status: 하루치 증분이 쌓여 `PROGRESS_LOG` 329줄(예산 2.7배) 등 3종이 초과 → `/tidy-docs`.
  **삭제 없음**, 전부 아카이브 이동 또는 압축.
- Changed: log 329→**80**(최신 2건 유지 + Cosign 항목 90→18 압축, 6건은
  `archive/progress-2026-08.md`로) · plan 192→**118**(완료 `[x]` 5건 제거 → M15) ·
  status 201→**126**(baseline 12→5건, Active Focus 재작성, 역량 목록 압축) ·
  `COMPLETED_SUMMARY` **M15 신설** · `DECISIONS` **D43**.
- Changed(리스크 병합): Risk **12·13·14**가 전부 *"게이트의 초록에는 조건이 붙는다"*는
  한 계열이라 **Risk 12 ①시간 ②환경 ③하중**으로 합치고 참조를 정정했다.
- Verified: `make check` **1668**. 참조 무결성 확인(아카이브 2종 · M10/M12/M13/M14/M15 전부 존재).
  예산: brief 43/60 · plan 118/120 · log 80/120 ✅, **status 126/120 (+6)**.
- Changed(정리 중 드러난 사실 오류 2건): `AGENT_BRIEF` 가드레일의 **"에이전트=Python 3.11"**은
  오늘 측정과 어긋난다(3.11에서 2건 red) → "게이트는 **3.13에서만 검증됨**"으로 교체 ·
  `NEXT_PLAN` 완료 이력 포인터가 M14까지만 가리켜 M15 추가.
- Blockers: `main`이 보호되어 이 문서 변경은 **PR로만** 들어간다. status +6줄은 더 줄이려면
  현재 판단에 필요한 정보를 깎아야 해서 남겨 뒀다.
- 품질 메모: **줄 수는 예산 안이어도 진입점은 죽어 있을 수 있다.** `AGENT_BRIEF`는 42줄로
  통과였지만 `▶ NEXT SESSION` **한 줄이 6,057자**로 10세션치 이력을 안고 있었다 — `/sync`가
  가장 먼저 읽는 파일인데 1분 문맥 역할을 못 했다. 최장 줄 **6,057→533자**. **예산은 줄 수가
  아니라 읽는 데 드는 시간으로 재야 한다.**
- Next: Phase 4(billable, 별 승인)만 남았다.


## 2026-08-08 — 게이트를 집행으로: 브랜치 보호 + TS의 두 번째 진실 공급원 제거

- Status: 무과금으로 남은 두 항목을 소진. 오늘 세운 CI를 **실제 병합 조건**으로 만들고,
  선행 조건이 갖춰진 TS 스윕 잔여를 닫았다.
- Changed(TS 닫힌 섬): NEXT_PLAN이 요구한 **실 레지스트리 대조**를 하니 기록보다 컸다 —
  타입 5종뿐 아니라 **`namespaceFor`·`credentialScope`도 호출자 0**이었고, 둘은 **살아 있는
  파이썬 규칙의 복제본**이다(`Tenant.namespace_for`=`delivery.py`+스코프 민팅 ·
  `IsolationTier.credential_scope`=`registry.py`). **지운 이유는 죽은 코드라서가 아니라 두 번째
  진실 공급원이라서다** — 아무도 실행하지 않는 인가 규칙은 조용히 어긋나고 나중에 배선하는
  사람은 그걸 믿는다. `Quota`의 "외부 참조" 1건은 **JSX 텍스트**였다. `tsc` clean.
- Changed(브랜치 보호): `main`에 **PR 필수 + `check`(=`make check`) 통과 필수**, 관리자 포함,
  force push·브랜치 삭제 금지. ⚠️**`require code owner review`는 일부러 껐다** — 협업자가
  1명이라 자기 PR을 승인할 수 없어 **만족 불가능한 규칙**이 되고, **우회해야 동작하는 규칙은
  우회를 습관으로 만든다**. 즉 집행하는 건 **게이트(기계)**이고 소유권은 아직 **라우팅**이다.
- Verified: 설정 API의 200은 "저장됐다"이지 "막는다"가 아니라 **일부러 직접 push**를 시도했다 →
  `Changes must be made through a pull request` + `Required status check "check" is expected` →
  `[remote rejected]`. **두 규칙 모두 발화.** 프로브 커밋은 되돌렸다. 이어서 남은 문서를
  **PR #1**로 올려 CI 통과→`MERGEABLE/CLEAN`→squash 병합까지 **새 흐름을 끝까지 돌렸다**.
  `make check` **1668**, 증거 `docs/evidence/branch-protection-enforced.log`.
- Blockers: **`main` 직접 push 불가 — 나를 포함해서.** 이후 변경은 PR로 들어간다.
  되돌리기는 설정 하나(`gh api -X DELETE .../branches/main/protection`).
- 품질 메모: **켰다고 말하기 전에 막는지 물어봐야 한다.** 설정이 저장된 것과 집행되는 것은
  다르고, 그 차이는 오늘만 네 번 나왔다(서명/소비자/어드미션/보호). 그리고 **만족 불가능한
  규칙을 켜지 않은 것**도 같은 규율이다 — 집행하지 않는 것을 광고하지 않는 것과, 광고만 하려고
  집행을 흉내 내지 않는 것은 한 가지다.
- Next: **Phase 4(billable)만 남았다** — 별 승인 사항.


## 2026-08-08 — Phase 5의 경계부터: 문장이던 불변식을 반증 가능하게 (gate 1651→1668)

- Status: 무과금으로 갈 수 있는 유일한 항목이 Phase 5라 착수. **UI가 아니라 경계부터** 세웠다.
- Verified(조사): 레지스트리는 레포 안 `platform/tenants/*.yaml`이고, **모든 테넌트 파일 헤더가
  Phase 0부터 이렇게 적어 두고 있었다** — "path-scoped CODEOWNERS가 쓰기를 막고, 대시보드의
  Phase 5 attach 흐름은 **오직 이 파일만** PR할 수 있다". 그런데 **그걸 반증할 수 있는 게
  아무것도 없었다**(CODEOWNERS 0 · PR 코드 0 · UI 0).
- Changed: `src/agents/platform/registry_write.py` — **텍스트로 편집하고 의미로 검증**한다.
  이 파일들은 대부분이 주석이고 그 주석이 이 레포가 재발견에 값을 치른 근거라 YAML
  재직렬화는 **전부 지운다**(유효한 파일을 만들면서). 그래서 삽입은 외과적이고, 그건 그것대로
  깨지기 쉬우므로 **결과를 다시 파싱해 원본과 데이터로 비교**한다 — 허용되는 차이는 **키 하나**뿐.
  테넌트 이름은 **경로가 되기 전에** 슬러그로 검증하고(`../globex` 거부), 만들어진 경로가
  tenants 디렉터리 안인지 **한 번 더** 본다(규칙 하나 + 리팩터링 대비 가드 하나).
  **attach는 upgrade가 아니다** — 이미 선언된 capability는 거부(조용히 버전 올리면 PR이
  적혀 있지 않은 것에 승인된다). `scripts/attach_addon.py`(기본 dry-run) · `.github/CODEOWNERS`.
- Verified: `make check` **1668**(+17). 반증 4종 개별 red — 경로 검증 · 착지 위치 검증 ·
  "한 키만" 비교 · attach/upgrade 구분.
- 품질 메모: **반증 패스가 진짜 구멍을 찾았다.** `_assert_only_change`를 통째로 지워도
  **14개가 전부 초록**이었다 — 전부 **행복 경로**만 태워서 그 안전망이 한 번도 하중을 받지
  않았기 때문이다. "아무 문제 없을 때만 성립하는 가드는 가드가 아니다." 편집을 **일부러
  틀리게** 만드는 테스트 3종을 추가하고 나서야 red가 됐다. 그리고 반증 스크립트 자체도 한 번
  틀렸다(들여쓰기가 안 맞아 치환이 조용히 no-op) — **반증도 측정해야 한다.**
- Blockers: 대시보드 UI와 실제 PR 생성은 안 했다(후자는 외부 동작). ⚠️**CODEOWNERS는
  리뷰어를 지정할 뿐 아무것도 막지 않는다** — 브랜치 보호가 없고, 팀 이름이 틀려도 GitHub는
  **조용히 무시**한다(틀린 규칙이 동작하는 규칙과 똑같이 보인다). 파일에 그대로 적었다.
- Next: Phase 4(billable)만 남았다.


## 2026-08-08 — Cosign은 게이트가 아니었다 → 서명 경로·소비자·CI 키리스까지 (gate 1636→1651)

- Status: 마지막 열린 승인(Cosign 어드미션)을 kind에서 세워 보려다, **기록된 이유가 구속
  조건이 아님**을 또 발견했다. **네 번째 같은 계열.**
- Verified(조사): 기록은 "현재는 CI/사람용 게이트까지. 어드미션엔 policy controller라는 새
  의존성이 필요"였다. 둘째 문장은 참이고 **첫째 문장은 아예 사실이 아니었다** — ①`cosign
  sign`이 레포에 **0건**(워크플로·Makefile·스크립트 어디에도 없다) ②`.github/workflows/`가
  **없다** → "CI 게이트"는 **돌 수 없는 단계**였다 ③`verify_image_signature.py`의 유일한
  호출자는 **자기 테스트**다(나머지 두 언급은 docstring과 values.yaml 주석) — **D39와 같은
  모양** ④차트가 `platform-agent:0.1.0`을 **레지스트리 호스트 없는 맨 태그**로 배포하고
  `digest: ""`다. 서명은 레지스트리의 **다이제스트 옆**에 사는 아티팩트이므로(검증기 자신의
  docstring이 그렇게 적어 뒀다) **놓일 주소조차 없다**.
- Verified(승인의 전제가 뒤집힌다): policy controller를 지금 넣으면 서명을 **강제**하는 게
  아니라 **모든 워크로드를 거부**한다 — 찾을 서명이 없으므로. 그리고 그 실패는 Risk 8의
  모양으로 나타난다(**Argo는 Synced인데 파드 0개**). 즉 승인 사항이 아니라 **작업 선행**이다:
  ①레지스트리에 다이제스트로 push → ②`cosign sign` → ③차트가 다이제스트 핀 → ④그때 어드미션.
- Changed: 거짓 주장 3곳(STATUS Risk 6 · NEXT_PLAN · AGENT_BRIEF)을 측정된 사실로 교체 ·
  가드 `tests/test_signature_gate_claims.py` 4종 — 문서는 **없는 CI 게이트를 주장할 수 없고**,
  검증기에 호출자가 생기면 **일부러 red**(문구를 승격하라는 신호), 어드미션 설정이 서명
  생산자보다 **먼저 들어올 수 없고**, `digest`가 핀되면 red(그때 서명이 가능해진다).
- Verified: `make check` **1640**(+4). 반증: STATUS에 "CI/사람용 게이트" 문구를 되살리자
  정확히 그 가드만 red.
- 품질 메모: **가드를 쓰다가 내가 오탐을 냈다** — 첫 실행이 values.yaml의 **주석 한 줄**을
  프로덕션 호출자로 셌다. 산문을 호출로 세는 건 이 파일이 다루는 결함의 **거울상**이라,
  탐지기도 측정해서 주석을 제외했다(푸시-신원 때 똑같은 실수를 했고 그때도 증거에 남겼다).
  그리고 이번 건의 본질: **검증 도구가 있는 것과 게이트가 도는 것은 다르다.** 도구는
  잘 만들어져 있었다 — "could not check"를 "fine"으로 강등하지 않는 것까지. 다만 **아무도
  부르지 않았다.**
- Changed(같은 날 후속, gate 1640→1641): **서명 경로를 세웠다**. `make sign-image` /
  `scripts/build_and_sign_image.sh` — ①`infra/onprem/Dockerfile` 빌드 ②로컬 레지스트리
  (`localhost:5001`)에 push하고 **push 출력에서 다이제스트를 읽는다**(로컬 id는 레지스트리가
  들고 있는 매니페스트 다이제스트와 다를 수 있고, 틀린 걸 서명하면 **아무 데서도 검증되지 않는
  서명**이 나온다) ③**다이제스트에** `cosign sign`(태그는 움직이는 포인터다) ④검증은
  `cosign verify`를 다시 부르지 않고 **`scripts/verify_image_signature.py`로** 한다 — 그 스크립트가
  이미 "could not check"를 "fine"으로 강등하지 않으므로, 여기서 또 검사하면 **검증의 의미가 두
  군데서 갈릴** 수 있다.
- Verified(라이브): 빌드→push→서명→**VERIFIED**까지 통과
  (`sha256:510619af...`). 반증: **같은 빌드의 image manifest 다이제스트**(서명한 건 manifest
  list다)로 검증하면 `NOT SIGNED` exit 1. 레지스트리에 `tampered`·`unsigned` 태그와 cosign
  서명 아티팩트가 **이미 남아 있었다** — 라이브 검증은 과거에 **수동으로 한 번** 있었고,
  레포에 그걸 재현할 경로가 없었던 것이다.
- Changed(가드 반전): `test_the_verifier_has_no_production_caller`는 **쓴 날 뒤집혔다**.
  참인 명제가 바뀌었으니("호출자가 없다" → "있다") 지키는 명제도 바꿨다 — 이제 **서명 생산자와
  검증 호출자가 사라지면 red**다.
- Blockers(남은 것, 과대 해석 금지): 키는 **로컬 dev 전용**(빈 암호) · **CI 없음**(사람이 `make`를
  쳐야 돈다) · 차트 `digest`는 **비워 둔다**(로컬 다이제스트 커밋 = 아무도 못 가진 이미지에 대한
  주장) · **어드미션 집행은 여전히 미도입**.
- 품질 메모(두 번째): **내 가드에 구멍이 있었다.** `git grep`이 기본적으로 **추적된 파일만**
  본다 — 그래서 새로 쓴 `build_and_sign_image.sh`가 검증기를 부르는데도 가드가 **초록**이었다.
  가드가 말해야 할 바로 그 순간에 눈이 멀어 있던 것이다. `--untracked`로 고쳤다. 오늘만
  **가드 자신이 두 번**(주석을 호출로 셈 · 미추적 파일을 못 봄) 측정 대상이 됐다.
- Changed(세 번째, gate 1641→1651): **소비자를 붙였다.** 서명 경로만 만든 시점에서 나는
  **이 레포가 온종일 사냥한 결함을 새로 만든 상태**였다 — **소비자 없는 생산자**. 서명이
  찍히는데 **쓰는 시점에 아무도 읽지 않으면** 통제가 아니라 빌드 아티팩트다.
  `src/agents/platform/image_trust.py` + `deploy_to_cluster` 배선:
  ①판정은 **검증기의 종료 코드**가 그대로다(0/1/2) — 여기서 다시 판정하면 "검증됨"의 의미가
  두 군데서 갈린다 ②**exit 2("검사 못 함")도 거부**한다. cosign 부재·레지스트리 불통은
  이미지가 괜찮다는 증거가 아니고, fail-open하면 하류 전체가 검사됐다고 믿는다 ③다만 메시지는
  구분한다 — 운영자가 **고장 난 검사기를 위조로 오진하면 안 된다**.
- Verified(라이브, 모킹 없음): 실 레지스트리·실 cosign·실 키로 서명 다이제스트는 통과,
  미서명은 거부. 미서명 표본은 꾸며 낸 값이 아니라 **같은 빌드의 image manifest**다(서명한 건
  manifest **list**). 실 배포 진입점에서 `cluster.deploy called=False` — **거부가 클러스터 호출
  앞에서** 일어난다(뒤에 도는 검사는 게이트가 아니다). `make check` **1651**(+12).
  증거 `docs/evidence/image-signature-deploy-gate.log`.
- Blockers(과대 해석 금지): **옵트인**(`PLATFORM_REQUIRE_SIGNED_IMAGES` 미설정=검사 0) ·
  **온프렘 진입점 하나**만 덮는다(클라우드 3종·ArgoCD가 직접 당기는 이미지는 안 지난다) ·
  **어드미션이 아니다**(API 서버는 여전히 받는다) · 키는 로컬 dev 전용 · CI 없음.
- Changed(네 번째, 같은 날): **CI + 키리스 서명**. 두 결정(CI · 키 custody)은 **사실 하나**였다 —
  **키리스가 키를 없애서 custody를 푼다**(Fulcio 단명 인증서, 보관·회전할 것이 없다).
  `gate.yml`(게이트를 기계가 돌린다) · `sign-image.yml`(빌드→GHCR→키리스 서명→**레포 자신의
  게이트로 검증**, 신원을 이 워크플로의 정확한 ref에 고정 — 아무 신원이나 받으면 Fulcio에 닿을
  수 있는 누구의 서명이든 통과한다). 라이브 첫 실행 **VERIFIED**
  `ghcr.io/men16922/platform-agent@sha256:112dd9b5...`.
- Verified(CI가 세 번 red였고 **세 번 다 진짜 결함**): ①lint 399건 — **내가 게이트를 임의로
  넓혔다**(이 레포의 게이트는 `make check`이고 `make lint`는 포함된 적 없으며 로컬에서도 20건
  실패 중이다. CI는 아무도 합의하지 않은 기준을 들여오기에 나쁜 자리다) ②tracing 17건 —
  **게이트가 선언되지 않은 패키지 위에서 통과하고 있었다**: strands가 OTel api+sdk를 끌고 와
  skipif가 건너뛰지 않는데 **exporter는 미선언**이라 ImportError가 의도적 `except`에 삼켜지고
  트레이싱이 **조용히 no-op**이 된다 → 새 클론에서는 아무도 통과 못 한다(→ `observability`
  extra) ③2건 — **`requires-python = ">=3.11"`은 아무도 확인한 적 없는 주장**(3.11 red /
  3.13 green). floor를 **조용히 올리지 않고** CI를 검증된 버전에 고정했다.
  증거 `docs/evidence/ci-keyless-signing.log` → Risk 13.
- Blockers: **어드미션 하나만 남았다**. Rekor는 **영구 공개·철회 불가**이고, 로컬
  `make sign-image`는 여전히 빈 암호 dev 키다(키리스는 CI 경로만 덮는다).
- 품질 메모: **CI가 잡은 세 건은 로컬에서 원리상 드러나지 않는다.** 특히 ②는 "게이트는
  상한다"(Risk 12)의 공간축 버전이다 — 통과가 코드가 아니라 **말해지지 않은 환경**에 달려
  있었다. 그리고 ①은 내 실수였다: 게이트를 집행하러 가서 **게이트를 넓혔다**.
- Next: **④어드미션만 승인 사항**(kind 선행 권고). Phase 4/5는 그대로.

## 2026-08-08 — 승인 3건을 쟀다: 하나는 통과, 하나는 질문이 틀렸고, 하나는 보류

- Status: 사용자 지시("추천안에 따라 승인할테니 해")로 승인 3건 처리. 먼저 푸시(54커밋,
  `655369f..3908159`) — 그때까지 origin은 **6일 뒤처져** 있었다.
- Verified(①실 DynamoDB 왕복 = **통과**): 생산자 `_record_incident`가 실 `incident-history`에
  행을 남기고(18속성), 여섯 속성이 **타입까지 보존**된다. 핵심은 `confidence`가 `Decimal`로
  돌아온 것 — DynamoDB N 타입이라 대시보드의 `typeof item.confidence === "number"`가 참이 된다.
  **문자열이었다면 파이썬 쪽은 통과하면서 화면엔 영원히 "n/a"**가 떴을 것이다. 그리고 애초에
  float를 넣었으면 boto3 예외가 `except`에 잡혀 **행 전체가 사라졌을** 것이다 — 목은 float를
  군말 없이 받으므로 이건 모킹으로 **원리상** 못 잡는다. 생산 리더의 `started_at`도
  `triggered_at`에서 온다. 프로브는 자기 행을 지운다. `scripts/probe_incident_roundtrip.py`,
  증거 `docs/evidence/incident-fields-dynamo-roundtrip.log`. **남은 한 칸**: 대시보드 TS
  리더로는 안 읽었다(속성명·예약어 별칭 대조까지).
- Verified(②GCP/Azure 보관 = **질문이 틀렸다**): "켜는 건 실 데이터 삭제"의 **뒷절반이 한 번도
  측정된 적이 없었다**. GCP는 platform-agent 프로젝트(`project-ec7809f7`)에 **Firestore API가
  켜진 적조차 없고**, Azure엔 `platform-agent` DB가 없다 → **지울 데이터 0**. 없는 컨테이너에
  `DefaultTimeToLive`를 걸 수 없으므로 **구속 조건이 기록과 반대**다: 보관을 켜려면 **먼저
  프로비저닝**해야 하고 그건 billable → Phase 4. ⚠️처음에 **엉뚱한 프로젝트**
  (`claude-study-501117`)를 보고 결론낼 뻔했고 메모리의 결제 매핑이 잡아 줬다 — 그래서 나머지
  3개 프로젝트도 스윕했다. 증거 `docs/evidence/gcp-azure-retention-nothing-to-delete.log`.
- Blockers(③Cosign 어드미션 = **보류 권고, 미실행**): policy controller라는 **새 클러스터
  의존성**이고, 잘못 서면 Risk 8의 모양으로 실패한다(**Argo는 Synced인데 파드 0개**).
  승인 3건 중 유일하게 되돌리기 비용이 크다 → kind 선행 + Phase 4와 묶기.
- 품질 메모: **승인 항목도 측정 대상이다.** 셋 중 하나는 통과, 하나는 **질문 자체가 사실이
  아니었고**(9일간 "파괴적 승인"으로 대기), 하나만 진짜 승인이 필요했다. D40·D41과 같은
  계열이다 — 그럴듯한 이유가 문서를 건너 복사되는 동안 **아무도 쿼리를 돌리지 않았다**.
- Next: Phase 4/5. 열린 승인은 Cosign 하나.

## 2026-08-08 — 서명키는 회전할 수 없었다: 같은 키를 요구하던 문장이 곧 제약이었다 (gate 1618→1636)

- Status: 우선순위 2 = 서명키 custody·rotation. **rotation을 닫았고 custody는 안 건드렸다**(아래).
- Verified(조사): 결함은 암호가 아니라 **배포 위상**이었다. 서명자(`attest_decision`, 승인
  경로)와 검증자(`TokenBroker`, 실행기)가 **다른 프로세스**인데 같은
  `PLATFORM_APPROVAL_SIGNING_KEY` 하나를 읽는다 → 교체가 **원자적일 수 없다**. 먼저 롤한 쪽이
  만든 레코드는 상대가 거부하고, 그 거부가 하필 **`failed attestation`** — 즉 **위조로 읽힌다**.
  결과: 회전은 장애 아니면 오경보라서 **실제로는 한 번도 회전하지 않는다**. Makefile의
  "the key must be the same for whoever signs and whoever verifies"는 **설명이 아니라 제약**이었다.
- Changed: `PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING`(콤마 구분) — **검증 전용, 절대 서명 안 함**.
  `_accepted_keys()`(active + retiring) · `_verifying_key_index()`(어느 키로 통과했는지) ·
  `verify()`는 bool 계약 유지 · **설정이 회전을 흉내 내지 못하게**(active 키를 retiring에
  나열 = 두 반쪽 다 no-op인데 둘 다 한 것처럼 보인다 → 거부 · 중복 → 거부) ·
  `_signed_by_a_pre_ttl_version`도 retiring 키를 본다(롤아웃 스큐와 회전이 겹치면 **또 위조로
  오진**된다) · Makefile에 3단 절차 기록.
- Verified: **겹침 창을 유한하게 만드는 건 D42의 TTL이다** — 새 암호가 아니라. 옛 키는 그 키로
  서명된 레코드가 **만료될 때까지만** 살아 있으면 된다. 가드로 고정: 만료된 레코드는 retiring
  키로도 거부되고, 서명이 `issued_at`을 덮으므로 **백데이트로 TTL을 빠져나갈 수 없다**.
- Verified: `make check` **1636**(+18). 반증 4종 개별 red — retiring 미수용(6 red) · 로그 제거
  (1 red) · 설정 검증 제거(2 red) · **retiring 레코드에 TTL 미적용**(1 red, 겹침이 무한해지는
  바로 그 오구현). ruff clean.
- Blockers: **custody는 안 닫았다 — 그리고 그건 거짓 주장이 아니었다.** `Makefile:256`이
  "Local development only… NOT a secret-management story"라고 정확히 라벨해 뒀다. 닫으려면
  시크릿 매니저를 고르는 **인프라·정책 결정**(+과금)이라 발명하지 않았다.
- 품질 메모: **집행할 수 없는 절차는 관측 가능하게 만든다.** 3단계(옛 키 제거)는 코드가 강제할
  수 없다 — 나열된 키는 나열된 동안 유효하다. 대신 옛 키로 통과한 레코드마다 로그를 남겨
  "회전이 끝났나?"를 **믿음이 아니라 측정**으로 답하게 했다. **침묵이 그 측정이다.**
  그리고 이번 것도 계열이 같다: 문서가 **제약을 설명으로 적어 두면** 아무도 그게 막고 있는
  줄 모른다.
- Next: 승인 3건 → Phase 4/5. custody는 인프라 결정 대기.

## 2026-08-08 — 달력이 움직이자 red가 됐다: 하드코딩 픽스처가 창 밖으로 밀렸다 (gate 1617→1618)

- Status: `/sync` 직후 Stop 훅의 `make check`가 **5 failed**. 미커밋 소스
  (`collector.py`·`scope.py`·`tenancy.py`)가 범인처럼 보였으나 **무관**이었다.
- Verified(진단): 실패한 `tests/test_incident_time_to_resolve.py`는 **수정된 적이 없다**
  (gate 1520에 커밋된 그대로). `_row()`가 `created_at="2026-07-29T00:30:00Z"`를 하드코딩하는데
  생산자 `_fetch_incidents_from_dynamo(days=7)`는 **살아 있는 시계**로 `_in_window`를 건다.
  실측: 그 행은 **9.96일** 되어 창 `[07-31, 08-07]` 밖 → `_fetch`가 `[]` → `IndexError` /
  MTTR `0.0`. 즉 **2026-08-05에 코드 한 줄 안 바뀌고 red가 됐다**. 문서의 1617은 거짓이
  아니라 **유효기간이 지난 것**이었다.
- Changed: 픽스처를 `now` 기준 상대 배치로 — **이미 green이던 형제**
  `test_report_windows.py`(`_row(age_days)`)가 쓰던 그 모양. 측정 대상은 **duration이지
  placement가 아니라서** 오프셋(45.0/20.0/30.0)은 그대로 정확하다 · `_BASE`는 import 시
  1회 고정(픽스처와 단언이 초 경계를 straddle하지 않게) · 가드 1건(창 밖으로 밀리면
  `IndexError` 대신 **이름으로** 먼저 실패 — 빈 리스트발 `IndexError`는 리더 버그처럼
  읽히는데 아니다).
- Verified: `make check` **1618**(+1). 창 필터를 타는 테스트는 이 **둘뿐**이고 둘 다 통과.
  나머지 26개 하드코딩 날짜 파일은 살아 있는 시계를 안 탄다 — **후보이지 결함이 아니다**.
- Changed(정리): 워킹트리에만 있던 gate 1607~1618분을 **커밋 5건**으로 분리
  (D42 · D41+D40 · 푸시 읽기 신원 · 이번 수정 · 체크포인트). 직전 커밋은 `ed36b30`(1605)였다.
- Blockers: 없음. **origin 대비 미푸시**는 남아 있다(푸시는 별도 승인).
- 품질 메모: **이 계열의 시간축 변종이다.** "없는 것은 테스트에서 영원히 초록"이 아니라
  **달력이 움직이기 전까지만 초록**이었다. 그리고 훅이 지목한 파일 목록(미커밋 소스)은
  **상관관계지 인과가 아니었다** — 실패 파일이 unmodified인지 먼저 물었으면 1분이었다.
  게이트 결과에는 **측정 시점이 붙어야 한다**: "1617 passed"는 날짜 없이는 주장이 아니다.
- Next: 우선순위 2 = **서명키 custody·rotation**(D42의 TTL 900초로 선행 해소).

## 2026-08-02 — 계획이 스테일이었다: 막힌 건 푸시 인증이 아니라 스포크의 읽기 (gate 1614→1617)

- Status: `2차 잔여` 첫 항목("agent→hub push 인증")을 잰 결과 **일주일째 스테일**이었고,
  그 자리에 **다른 구멍**이 있었다.
- Verified(라이브, 실 허브 라우트): 쓰기 쪽은 **이미 집행된다** — ①올바른 서명 200
  ②무서명 401 ③틀린 키 401 ④globex 키로 acme 자칭 401 ⑤acme 키에 globex 행 섞기
  → 401 `carries rows for ['globex/dev']`. 2026-07-26(gate 1219→1251)에 이미 끝나 있었다.
  ⚠️**첫 ⑤는 200이 나와 진짜 구멍처럼 보였다** — 내 페이로드가 행을 `addons` 키로 보냈는데
  `StatusReport`는 `statuses`를 읽어 **행이 파싱조차 안 된 빈 보고서**였다. 픽스처를 실제
  생산자 모양(`to_dict()`)으로 바꾸자 정상 거부. **잘못된 픽스처발 오탐은 이 레포가 쫓는
  결함의 거울상**이라 지우지 않고 증거에 남겼다.
- Verified(진짜 구멍): 읽기 쪽은 **자격증명이 경계가 아니다** — `_kubectl`이 맨 kubectl이고
  (`--kubeconfig`/`--context` 없음, D38이 배포에서 닫은 그 모양), 읽는 대상이 **공유 `argocd`
  네임스페이스**라 테넌트 구분이 **파이썬 라벨 필터**다. 게다가 `infra/helm`에 **스포크
  배포 매니페스트가 없다**(router·webhook·orphan-sweeper뿐) — 즉 "각 클러스터가 에이전트를
  돌린다"는 서술은 **의도된 배포지 존재하는 배포가 아니다**.
- Changed: 모듈 docstring의 과장("읽기 경로에서도 blast radius가 1 tenant/env")을 **측정된
  사실로 교체** · `warn_if_ambient_read()`(프로세스당 **한 번**, `--interval 60` 루프가 로그
  노이즈가 되지 않게) · `_kubectl`이 그걸 부르게 해서 **문구가 동작에서 떨어질 수 없게** ·
  가드 3종 · NEXT_PLAN의 스테일 항목 2개를 사실로 교체.
- Verified: `make check` **1617**(+3). 반증 3종 개별 red(경고 우회 · 문구 약화 · 래치 제거).
  증거 `docs/evidence/push-identity-ambient.log`.
- Blockers: 없음. **seam은 일부러 안 만들었다** — D38이 `make deploy-identity`(민팅 경로)와
  함께 나온 이유가 그것이고, 채울 수 없는 env var를 추가하면 **같은 결함에 새 이름**을 붙이는
  것이다. 스코프된 읽기 신원은 **인클러스터 배포가 선행**이라 인프라 결정.
- 품질 메모: **계획 문서도 측정 대상이다.** 닫힌 항목이 열린 채 남아 있으면 다음 사람은 이미
  된 일을 하거나, 더 나쁘게 **그 옆의 진짜 구멍을 못 본다**. 그리고 이번엔 **내가 오탐을
  냈다** — 필드명 하나 틀린 픽스처로. 측정은 도구가 아니라 습관이라 픽스처도 측정해야 한다.
- Next: 승인 3건 + Phase 4/5. 남은 2차 잔여는 스포크 읽기 신원(인프라 선행) · 서명키 rotation.

## 2026-08-02 — 결정 6 = D42: 승인은 1회용이 아니라 상하는 것 (gate 1611→1614)

- Status: 사용자 지시("우선순위 & 추천안에 따라 수행")대로 결정 6을 **추천안 C**로 실행.
- Changed: `AttestedApproval.issued_at`을 **서명 payload에 포함**(시각을 키 없이 앞당길 수
  없다) · 브로커가 TTL 초과·미래 스탬프·`issued_at=0`을 거부 ·
  `PLATFORM_APPROVAL_TTL_SECONDS`(기본 **900초**, `<=0`은 설정 오류로 거부 = **끄는 스위치
  없음**) · 생산자(`attest_decision`)와 소비자(`resolve_incident_scope`) **양쪽 배선**(저장만
  하면 M13을 하나 더 만드는 것) · 가드 6종.
- Verified(라이브, 프로덕션 진입점): ①갓 발행 승인 3회 재사용 → **3회 MINTED**(실행기가 실제로
  두 번 해석하는 패턴이라 이게 정상) ②TTL 초과 → `960s old, past the 900s TTL` ③시각만
  앞당김 → 서명 불일치 ④24시간 미래 스탬프 → 거부 ⑤레포 프로브 `probe_scope_reachability.py`
  → resolve MINTED, 게이트 **PERMITTED**. `make check` **1614**(+6). 반증 3종 개별 red(나이
  검사 제거=3 red · payload에서 `issued_at` 제거=2 red · 스큐 진단을 수락으로=1 red).
- Blockers: 없음. **행동 단위 1회용(옵션 B)**은 실행기 3종 상태 저장이 필요 → Phase 4와 함께.
- 품질 메모: **900초를 발명하지 않았다** — 서명은 인가가 성립하는 순간에 찍히고 실행기가 같은
  흐름에서 소비하므로 **사이에 사람 대기가 없고**, 들어가야 하는 건 기계 시간뿐이라는 경로의
  모양에서 나왔다. 그리고 **첫 구현에 도달 불가능한 분기를 만들 뻔했다**: "구버전 레코드"
  분기를 넣었는데 측정해 보니 `issued_at`이 서명에 들어가 그 레코드는 `verify()`에서 먼저
  죽는다 — 즉 그 주석이 설명하는 상황에 **영원히 닿지 못한다**. 이번 계열에서 배운 걸 내가
  바로 반복할 뻔했다. 거부는 유지하되 **이유를 스큐로 분류**하게 고쳤다(롤링 배포 중 "failed
  attestation"은 위조로 오진된다). **약속이 줄었고 대신 지켜진다** — TTL 안 재사용은
  가능하고, docstring·계획·테스트에 **그렇게 적었다**.
- Next: 승인 3건 + Phase 4/5. 열린 결정 없음.

## 2026-08-02 — Phase 5를 재다가 재사용 가드를 찾았다: 상태가 살아남지 못한다 (gate 1608→1611)

- Status: 다음 우선순위(Phase 4·5)를 집으려 실체를 재는 중 **Phase 5는 완전 그린필드**이고
  설계상 **(선택)**임을 확인, 대신 "선행이 안 끝났는데 이미 출하된" 항목(서명키 custody —
  결정 5-A의 선행)을 재다가 **옆에서 구멍이 나왔다**. **여섯 번째로 전제가 깨졌다.**
- Verified(조사): 서명키 자체는 **거짓 주장이 아니었다** — `Makefile:256`이 "Local development
  only… NOT a secret-management story"라고 정확히 라벨해 두었다. 깨진 건 그 옆
  `AttestedApproval.nonce`의 **"One-time-use marker; the broker rejects a replayed nonce"**다:
  ①`_spent`가 **인스턴스 속성**인데 유일한 프로덕션 호출자 `resolve_incident_scope`가 호출마다
  `TokenBroker.from_env()`를 **새로 만든다** → 프로덕션 경로로 같은 레코드 3회 제출에 **3회
  발급** ②`test_nonce_replay_is_refused`는 broker 픽스처 **하나**를 잡고 두 번 부른다 —
  **수호 테스트가 홀을 놓친 게 아니라 유일한 성립 조건을 제공**했다(이 계열 첫 사례)
  ③그리고 **지금 켜면 정당한 호출자가 깨진다**: `aws/executor.py`가 같은 인시던트로 스코프를
  **두 번** 해석하고(런북·액션 경로) SFN 재시도가 더 겹친다. 즉 "영속화하자"가 아니라
  **"1회의 단위가 무엇인가"** 문제다.
- Verified(영향): **테넌트 경계는 안 깨진다** — 서명이 tenant를 덮어 재사용해도 같은 스코프가
  다시 나올 뿐이다(가드에 단언으로 고정). 깨지는 건 **감사 주장**("이 승인은 정확히 한 번의
  행동을 인가했다")이고, 재사용된 행동은 **옛 `approval_id`로 귀속**된다.
- Changed(모호하지 않은 절반만): 주장 3곳을 사실로 교체(`nonce` 주석 · `_spent` · `mint`) ·
  기존 테스트 이름을 `..._within_one_broker_instance`로(이름 자체가 주장이었다) · 새 가드
  `tests/test_scope_replay_reachability.py`는 **프로덕션 함수로** 단언하고, 재사용이 실제로
  거부되기 시작하면 **일부러 red**가 된다.
- Verified: `make check` **1611**(+3). 반증: 브로커를 모듈 캐시로 바꾸자 두 가드가 정확히 red.
  ruff 변경 파일 clean. 조사 `docs/plans/2026-08-02-nonce-replay-scope.md`.
- Blockers: **결정 6**(소비 단위) — A=인시던트 1회 · **C=TTL로 대체(추천)** · B=행동 1회(영속
  저장, 실행기 3종 새 의존성 → Phase 4와 함께). TTL 길이·소비 단위는 **정책**이라 발명하지 않음.
- 품질 메모: **가드는 자기 상태가 살아남는 수명에서만 집행된다.** 그리고 이번엔 **테스트가 그
  수명을 만들어 줬다** — "수호 테스트 자신이 안티패턴일 수 있다"의 가장 나쁜 형태다. 고칠 때
  **집행을 켜는 쪽으로 먼저 가지 않은 이유**도 측정에서 나왔다: 켰으면 정상 실행이 깨졌다.
- Next: 결정 6 + 승인 3건. Phase 5는 그린필드·선택이라 뒤로.

## 2026-08-02 — 결정 3: 선택지가 둘이 아니라 셋이었다 (gate 1607→1608)

- Status: 마지막 사용자 게이트(결정 3 = Capsule `limitRanges` 이관 경로)를 조사 → 승인 →
  라이브 검증 → 실행. **다섯 번째로 전제가 깨졌다** — 이번엔 **선택지 개수**였다.
- Verified(조사): 네 문서가 두 갈래(`GlobalTenantResource`=D30 위반 / `TenantResource`=새
  SA+RBAC)만 놓고 "둘 다 비싸다"고 적었는데, **같은 증거 로그 26행이 세 번째 답을 이미 적어
  두었다**: *"`networkPolicies`는 우리에게 해당 없음 — 이 레포는 Tenant spec 대신 객체를 직접
  렌더한다."* 같은 릴리스에 폐기된 형제 필드다. `LimitRange`는 **네임스페이스 스코프**라 D30
  무관, **새 권한 표면도 없다** — `TenantResource`가 SA를 요구하는 건 **Capsule이 대신 쓰기
  때문**이고 직접 쓰면 대리인이 없다.
- Verified(라이브 kind, 3단): ①`spec.limitRanges` 제거 → **Capsule이 자기 LimitRange 4개를
  회수**(globex 것은 유지 = 중복 없음) ②없는 상태에서 limits 없는 파드 → `must specify
  limits.cpu for: c` **Forbidden** — 애드온 values 4종 중 limits를 두는 게 **하나도 없어**
  전 워크로드가 여기 의존하고, 그 거부는 **Argo가 Synced로 보이는**(Risk 8) 자리에서 난다
  ③직접 렌더 후 다시 통과하고, Capsule이 `managed-by` 라벨을 찍었음에도 **컨트롤러 재시작
  전체 리싱크를 견딘다**(8회 샘플 120초, 5/5 생존). 부수: apply stderr **0바이트** — 폐기
  경고 2→0.
- Changed: `spec.limitRanges` 제거 + `render_limit_ranges()` 추가(`render_tenancy`가 Capsule
  Tenant를 낼 때만 방출 — `limits.*` 쿼터가 있을 때가 정확히 그때다) · 가드 2종(하나는
  **파생**: 쿼터가 `limits.`를 선언하면 그 렌더의 **모든** 네임스페이스가 기본값을 가져야 한다,
  나중에 추가될 ns까지 잡힌다) · **스테일 픽스처 라벨링**(`CAPSULE_WARNINGS`는 이제 클러스터가
  만들지 않는 stderr다 — 조용히 갱신하지 않고 HISTORICAL로 명시).
- Verified: `make check` **1608**(+1). 반증 2건 개별 red. ruff 변경 파일 clean. 증거
  `docs/evidence/capsule-limitranges-direct.log`, 조사
  `docs/plans/2026-08-02-capsule-limitranges-path.md`, 결정 **D41**.
- Blockers: 없음. 라이브 변경은 로컬 kind에 국한(테넌트 2개 재적용 + 프로브 파드 정리 완료).
- 품질 메모: **질문이 주는 선택지를 세지 말 것.** D40은 "막는 게 하나"라던 게 넷이었고,
  이번엔 "선택지가 둘"이라던 게 셋이었다. 둘 다 **답이 이미 레포 안에** 있었다 — 이번 것은
  같은 파일 40행 위에. 그리고 **폐기됐다고 사문화된 건 아니다**: 이 필드는 쿼터를 admission
  요구로 바꾸는 축이었고, 없으면 조용히가 아니라 **Forbidden**으로 깨지는데 그 소리가 들리는
  곳이 하필 Argo가 Synced를 보여 주는 자리였다.
- Next: **사용자 게이트 전부 닫힘.** 남은 건 승인 3건 + Phase 4/5.

## 2026-08-01 — 결정 4: 승격 도구가 승격을 못 한다 (gate 1605→1607)

- Status: 브리프의 ⓪순위(결정 4 = k3s를 proven 기판에)를 조사 → 사용자 승인(옵션 C) → 실행.
  **네 번째로 전제가 깨졌다** — 이번엔 **막는 것이 하나가 아니었고**, 기록된 하나는 가장 먼저
  걸리지도 않았다.
- Verified(조사): 네 문서가 반복하던 "k3s-lab에 피어 테넌트가 없다"는 **참이지만 구속력이
  없었다**. 실제 프로브 실행 → `acme/prod has 1 namespace(s); the same-tenant leg needs two`
  로 **피어를 보기 전에** 멈춘다(애드온 1개 = 네임스페이스 1개). 임시 레지스트리로 ①②를
  제거해도 ③에서 멈춘다: `network_policies_apply_to(acme,'prod')=False` — 프로브가 proven
  집합을 전제하고 그 집합을 정하는 게 프로브다. **승격하려면 먼저 승격해야 한다**(kind가
  통과한 건 이미 안에 있어서고, 실제로 한 건 승격이 아니라 회귀 테스트). ④ 라이브 k8s-lab
  (20d): 네임스페이스 4개(전부 기본), netpol 0, Capsule·Flux CRD 없음, kube-system 밖 파드 0,
  `acme-prod-*` **한 번도 존재한 적 없음**. 비용도 반대로 적혀 있었다 — **이 클러스터를 보는
  컨트롤러가 없어 레지스트리 편집은 아무것도 프로비저닝하지 않는다**. 즉 오늘 넣으면 **보호
  대상이 0**이다.
- Changed(승인된 옵션 C): 집합은 `{"kind"}` 유지 · **닫는 이유를 사실로 교체**(tenancy.py
  주석 · STATUS Risk 5 · NEXT_PLAN 결정 4/잔여 · 증거 로그 FOLLOW-UP) · **D40** ·
  새 가드 `tests/test_substrate_promotion_reachable.py`(**멤버십 주장은 현재 레지스트리로
  반증 가능해야 한다** + 순환을 코드에 고정) · 조사 문서
  `docs/plans/2026-08-01-k3s-proven-substrate.md`.
- Verified: `make check` **1607**(+2). 반증 2건 개별 red — k3s를 넣으면 `'k3s' is claimed
  PROVEN, but no tenant/env on it can be run ... acme/prod: 1 namespace(s)`, globex를 다른
  클러스터로 옮기면 kind가 red. 반증 1은 **두 번째 가드까지** red(미증명 기판이 사라지면
  가드를 약화하지 말고 폐기하라는 신호). ruff: 변경 파일 clean.
- Blockers: 없음. **클러스터 변경 0건**(읽기만).
- 품질 메모: M13(**소비자 없는 필드**) → D38(**생산자 없는 메커니즘**) → D39(**사용처 없는
  예외**) → D40(**도달 불가능한 검증기**). 네 번째가 가장 은밀했다 — 프로브는 잘 쓰였고 4개
  주장이 전부 반증 가능한데 **자기가 판정해야 할 대상에는 절대 못 닿는다**. 넷 다 테스트는
  초록이었다. 그리고 **부정확한 근거가 네 파일에 복사돼 3일을 살았다** — D39가 "예외의 근거를
  코드로 확인하라"였다면 이건 **"게이트의 근거는 측정으로 확인하라"**다. 한 번만 돌려 봤으면
  첫 줄에서 드러났다.
- Next: 잔여는 **결정 1건(3: Capsule `limitRanges`)** + 승인 3건. 그 뒤 Phase 4/5.
