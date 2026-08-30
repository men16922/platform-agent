# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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
