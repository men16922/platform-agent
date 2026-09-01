# PROGRESS_LOG Archive — September 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 9월 이력입니다. 최신이 위.

---

## 2026-09-01 — `onprem` extra의 `mlx-lm`: 선언은 있고 그걸 쓰는 곳이 없었다 (gate 2342)

- Status: `NEXT_PLAN` 08-30 항목. 기록된 근거를 먼저 다시 돌렸고 **적을 당시엔 참**이었다. 권위 `docs/evidence/the-onprem-extra-declared-a-mechanism-nobody-used.log`.
- Verified(**근거가 stale해진 게 아니라 더 나빠졌다**): PyPI 메타데이터 재측정 — 선언 하한 `mlx-lm==0.19.0`은 `mlx>=0.17.0`에 **플랫폼 마커가 없어** 리눅스 resolve가 진짜 실패한다. 그런데 `>=0.19`는 리졸버에게 **0.31.3**을 고르게 하고 거기엔 `platform_system == "Darwin"` 마커 + `py3-none-any` 휠이 있다 ⇒ **설치는 되고 엔진만 조용히 빠진다.** ⚠️**우회를 "이제 필요 없다"고 풀었으면 CI는 엔진 없는 mlx-lm을 초록으로 깔았을 것이다.**
- Verified(**그래서 우회가 아니라 선언을 물었다**): `src/`가 mlx를 임포트하는 곳 **0건**(에이전트는 MLX **서버**와 HTTP로 말한다 ⇒ 엔진은 임포트가 아니라 **프로세스**) · `.venv-mlx`엔 mlx-lm은 있고 `pydantic-ai-slim`은 없다 ⇒ **`.[onprem]`의 산물이 아니다**(08-30) · 실제 메커니즘은 `make mlx-setup`.
- Verified(**⚠️"안 쓰이니 지운다"가 아니다**): Makefile 최상단이 *"활성화된 `.venv-mlx`가 pytest를 가린다"*고 적고 인터프리터를 **탐침으로 고른다** — `.venv-mlx`가 프로젝트 env와 떨어진 건 **설계**다. `.[onprem]`이 mlx를 프로젝트 env로 들이면 그 분리를 정면으로 뒤집는다. **미사용이 아니라 틀린 메커니즘이었다.**
- Changed: `onprem`에서 `mlx-lm` 제거(근거는 주석에) · `gate.yml`이 인라인 `pydantic-ai-slim[openai]` 대신 **`.[onprem]`을 깐다** ⇒ **인라인 패키지 0개**(`serving` extra가 없앤 것과 같은 모양의 우회가 하나 남아 있었다).
- Changed(**가드 +3**): `TestMlxIsNotAProjectDependency` — 어떤 extra도 `mlx*`를 선언하지 않는다 · `src/`를 rglob으로 훑어 **전제를 코드에 묻는다** · `test_ci_requests_the_onprem_extra` + 인라인 금지 목록에 `pydantic-ai-slim` 추가.
- Verified(**⚠️내가 만든 가드 하나가 주석으로 통과했다**): *"`make mlx-setup`이 여전히 메커니즘인가"*를 `"mlx-lm" in Makefile`로 물었는데 **`MLX_BIN` 위 주석**에 그 문자열이 있어 레시피를 깨도 초록이었다. **주석이 주어인 규칙은 규칙이 아니다.**
- Verified(**⚠️그걸 "레시피 가드가 없다"로 읽은 것도 틀렸다 — Risk 12⑦ 재발**): 변이를 **이 파일에만** 물어서였다. 전체 스위트엔 red고, `test_local_stack_prerequisites.py::test_something_creates_the_venv_the_stack_runs_from`이 **레시피를 직접 읽는 옳은 자리의 옳은 질문**이었다 ⇒ 내 약한 사본은 **지우고** 어디가 그 자리인지 주석으로 적었다(두 번째 사본은 첫 번째의 그림자).
- Verified(**변이**): M1 extra 복귀 red · M2 인라인 복귀 red(2건) · M3 `src/`가 mlx 임포트 red · M4 레시피 깸 red(**전체 스위트에서**) · M5 규칙 무력화 **초록 — 설명됨**(현재 위반 0건이라 꺼도 관측 불변; 그 규칙의 하중을 재는 변이는 **M1**이고 red다).
- Blockers: 없음. ⚠️**리눅스 resolve는 로컬에서 증명 못 한다** — 이 PR의 CI 체크가 그 답이다.
- Next: **정적검사를 게이트에 넣을지**(lint 20건·mypy 253건 — **레포의 결정**) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

## 2026-09-01 — 4a를 접었다: 청구액이 $0.00이라 지운 게 아니다 — 대가는 장기 키였다 (gate 2339)

- Status: 사용자 결정으로 D50의 약속을 집행했다. **셋 다 삭제** — AMP 워크스페이스
  `ws-929b8da9…`(ap-northeast-2) · IAM 사용자 `amp-remote-write-4a` · 키 `AKIA…62VN`.
  권위 `docs/evidence/folding-4a-the-price-was-a-long-lived-key.log` · 계획서 **§11** · **D50 Folded**.
- Verified(**삭제 전 실측 — 정책이 기록과 정확히 일치했다**): 관리형 정책 **0건**, 인라인 **1건**이
  전부 `aps:RemoteWrite` **하나**를 그 워크스페이스 **하나**에. 키 마지막 사용 08-30T14:25Z `aps`.
  ⚠️**좁은 키도 장기 키다** — 그래서 지웠다. **$0.00은 지울 이유를 줄이지 않았다**(D50이 미리 그렇게 적어 뒀다).
- Verified(**"없다"를 어떻게 봤는지까지**): 8리전 스윕 전부 0 · `describe-workspace`를 **id로 직접**
  물어 `ResourceNotFoundException` · `get-user` `NoSuchEntity` · `list-users|amp` `[]`.
  ⚠️**`get-access-key-last-used`는 `AccessDenied`였고 그건 부재의 증거가 아니다** — 권한이 없어
  나온 답이라 키가 살아 있어도 같다. **증거는 소유 사용자의 부재**(키는 사용자보다 오래 못 산다).
  08-30 프로브의 429가 *"이것은 '0'이 아니다"*였던 것과 같은 모양.
- Changed(**레포에도 있었다**): `values/kube-prometheus-stack.yaml`의 `remoteWrite:` 블록 삭제 —
  안 지우면 **삭제된 워크스페이스를 가리키는 설정**이 git에 남는다. ⚠️**찾다가 내가 한 번 틀렸다**:
  `git grep`에 `| head -30`을 붙였는데 `docs/`가 `infra/`보다 먼저 정렬돼 **정작 그 파일이 잘렸고**
  "레포엔 없다"고 쓸 뻔했다 — 도구 함정이 아니라 **내 절단**이다.
- Changed(**가드를 지울 뻔했다 — 지웠으면 $180짜리 구멍**): `test_amp_cost_handles.py`의 9건은
  목적지가 사라지면 **전부 공허하게 참**이 된다(*"허용목록은 정확히 이 넷"*은 허용목록이 없을 때
  잘 통과한다). 지우는 쪽도 답이 아니다 — **D48은 4a를 접어도 안 죽고**(필터 없음 = 프리티어
  **128배**, ≈$180/월 = 4b 값 ⇒ 4a를 고른 이유가 지워진다) 그걸 적어 둔 유일한 물건이다.
  계약을 **함수로 빼** 두 호출자에 물렸다: 살아 있는 파일(목적지 **없어야** 한다) + **합성 표 9종**.
- Verified(**⚠️첫 판이 틀렸다 — 그림자로 세고 있었다**): 합성 표를 `violations != []`로만 묻자
  **와일드카드 검사를 통째로 지워도 초록**이었다(M2 생존) — `kube_.*`가 `allowlist-drift`에도
  걸려서다. **M17의 "결함을 그 그림자로 세지 말 것"** 그대로. 위반에 코드 7종을 붙이고 케이스가
  **어느 규칙이 물어야 하는지**를 지정하게 고쳤다 + 함수 본문에서 코드를 긁어 표와 대조하는
  가드(새 규칙이 케이스 없이 늘면 red). 재변이 **7종 전부 red**, 복구는 `__pycache__` 삭제 후 확인.
- Verified(**남긴 것의 이유가 바뀌었다**): KSM interval **60s 유지** — 더는 비용 손잡이가 아니고,
  데모 알람 룰이 `[5m]`로 적분하니 **60초=5샘플**(120초면 2샘플이라 `> 2`가 **원리상 도달 불가**).
  ⚠️**워크스페이스 id는 이제 안 박는다** — 없는 것을 박으면 **영원히 틀릴 수만 있는 규칙**이다.
- Blockers: 없음. 로컬 kind는 도커가 꺼져 이미 멈춰 있었다 — 다음에 띄우면 고아가 될
  `monitoring/amp-remote-write` Secret 삭제할 것.
- Next: **`onprem` extra의 `mlx-lm`**(승인 게이트 없는 유일한 코드 항목) · 정적검사 게이트 편입
  여부(레포의 결정) · BQ 결제 내보내기(콘솔 수동).
