# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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
