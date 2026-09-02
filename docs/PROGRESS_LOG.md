# PROGRESS_LOG — platform-agent

최종 갱신: 2026-09-02

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-09.md` · `…-2026-08.md` · `…-2026-07.md`

---

## 2026-09-02 — 적재가 도착했다: 그런데 ₩0은 요율이 아니라 프로모션 크레딧이었다 (gate 2397)

- Status: 사람의 다음 수(▶ NEXT SESSION 첫 행동) — GCP 내보내기 테이블 `numRows` 판정. **완결**, M49. 권위 `docs/evidence/the-gcp-zero-is-a-promotion-credit-not-a-rate.log`.
- Verified(**판정: 0이 아니다**): `numRows` **730**(422,688바이트 · `lastModifiedTime` 09-02 06:29:40Z, 생성은 09-01 01:53:42Z). 프로브의 GCP 분기를 직접 불러 **`MEASURABLE`** 확인 — `EXPORTED_EMPTY`에서 넘어갔다(M46이 만든 넷째 상태가 제 일을 했다). 2026-07 이래 열려 있던 *"GCP 실지출은 못 읽는다"*가 닫혔다.
- Verified(**⚠️₩0의 정체 — 요율이 아니다**): 총사용액 **₩67.87** → 청구 **≈₩0**인데, 상쇄의 **99.4%(₩67.4773)**가 `FreeTrialUpgrade:…` **`type=PROMOTION`**이고 티어성 `DISCOUNT`는 **₩0.39**뿐이다. **AMP와 같은 계열의 반대 방향** — 거기선 절벽이 요율→**한도**였고 여기선 **크레딧 잔액**이다. ⛔*"GCP는 어차피 공짜"*로 요약 금지. **소진 시점은 내보내기가 말해 주지 않는다.**
- Verified(**⚠️월별 집계 하나만 봤으면 없는 백필을 적을 뻔했다**): `invoice.month=202608`이 310행에 `first_usage 2026-08-01 07:00`이라 **한 달치 백필로 읽혔다**. **일별로 가르니** 08-01은 **1행**이고 `project=null`인 **Invoice 행**이다 — 실제 사용은 **08-30부터**(41→124→548→16). ⇒ 설정 문서 **§0("소급 적용 안 됨")은 성립한다**. **집계 축을 하나만 보면 없는 것이 보인다.**
- Verified(**⚠️월 런레이트는 아직 못 잰다 — 곱하지 않았다**): 창이 **3일**이고 마지막 날은 안 찼으며 총액의 **81%가 하루치 4행**(`claude-study-501117` Cloud Storage ₩54.90, 09-01에만). 30을 곱하면 **가정이 총액을 지배**한다(4a 추정표가 100배 틀렸던 그 모양). **며칠 뒤 다시 묻는 것이 무료인 다음 측정이다.**
- Verified(**⚠️총액의 90%는 다른 프로젝트 것**): 결제계정에 프로젝트 **5개**, 비용 행이 있는 건 **3개**(`claude-study-501117` ₩59.27 · **platform-agent의 `project-ec7809f7…` ₩6.55** · `warranty-hack` ₩2.05, `gen-lang-client-*` 둘은 0행). 브리프의 *"0행은 ₩0이 아니다 — 프로젝트 5개"*가 답을 얻었다. **결제계정 총액을 이 레포 비용으로 읽으면 10배 틀린다.**
- Verified(**안 한 것도 측정이다**): **AWS Cost Explorer 호출 0건** — `make spend-check` 전체는 CE **$0.01**을 물어서 GCP 분기만 직접 불렀다. `bq show`는 메타데이터라 스캔 **0바이트**, 질의 5건 합계 **~250KB**(무료 티어 1TB/월). **증거 로그는 손으로 옮기지 않고 명령 출력을 그대로 받았다.**
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 측정과 문서만 바뀌었다).
- Blockers: 없음.
- Next: **며칠 뒤 같은 질의를 다시**(무료) — 창이 3일→7일이 되면 런레이트가 가정 없이 나온다. 그리고 `GCP_BILLING_EXPORT_SETUP.md` **§4가 예고한 것**(*"데이터가 생기면 그때 붙인다"*)이 이제 조건을 만족한다 — `spend-check`의 `MEASURABLE` 분기가 **금액을 대신 물어 주게** 할 수 있고, ⚠️그때 **`cost`만 더하면 안 된다**(위 ⓐ가 그 이유다).

## 2026-09-02 — AGENT_BRIEF도 접었다: 7,199자는 통과였지 여유가 아니었다 (gate 2397)

- Status: overnight `[auto]` 1건 — `docs/AGENT_BRIEF.md`를 문자 예산 90% 이하로. **완결**(7,606 → **7,049자** = 예산의 **88.1%** · 58줄/60). 압축 씨앗 셋(STATUS·NEXT_PLAN·BRIEF)이 다 닫혔다.
- Changed(신규 `docs/archive/brief-detail-2026-09.md`): 닫힌 항목 여섯(ⓐ·ⓒ·`rollback_release`·런북 walk ②·`slack_live_approval`·`triggered_at`) · 직전 세션 09-01 전문 + **배운 것 둘** · **▶ NEXT SESSION의 09-01 세 결함**. 줄은 **줄 번호로**, 문단은 **마커로** 잘라 **스크립트가 복사**했다 — 손으로 옮기지 않았다(09-02 STATUS 압축의 그 교훈).
- Changed(`docs/AGENT_BRIEF.md`): 네 자리를 **주장 한 줄 + archive 지목**으로 접었다. ▶ NEXT SESSION의 **첫 행동은 건드리지 않았다** — `/sync`가 그 줄을 제일 먼저 그대로 읽는다.
- Verified(**첫 판은 7,199/7,200이었다 — 한 글자**): 기준은 통과했지만 다음 세션이 한 문장만 더해도 red다. 그래서 **가장 긴 줄**(1,058자 = 파일의 15%, 문자 예산 가드가 애초에 겨눈 그 병리)을 한 번 더 접었다 ⇒ **7,049자 · 최장 줄 908**.
- Verified(**삭제 0을 두 축으로 물었고 둘 다 제 창문에 걸렸다**): ⓐ ⚠️/⛔/✅ **33조각** · ⓑ `·`·줄 **83조각** → **6건이 "없다"**로 나왔는데 전부 **이음매 artifact**였다. 조각이 내가 자른 자리를 가로지르면 앞은 archive에, 뒤는 브리프에 있어 **통짜로는 안 맞는다**. 꼬리를 떼어 따로 물어 5건 생존 확인.
- Verified(**남은 1건이 진짜 함정**): 1,659자 조각이 `LOST`로 나온 원인은 삭제가 아니라 **내가 헤더에 두 줄을 끼워 넣어 연속성이 깨진 것**이었다. 꼬리를 **줄 단위로** 다시 물으니 15줄 **0 missing**. ⚠️**연속성은 불변식이 아니다 — 생존이 불변식이다**(대조기를 안 고쳤으면 없는 결함을 되돌릴 뻔했다).
- Verified(**옮긴 것은 바이트로 물었다**): line5 슬라이스 **344자** · 줄 11(496) · 12(179) · 18(520) 넷 다 archive에 **byte-identical**. 옛 브리프 **전 줄 스윕**에서 verbatim이 아닌 줄은 **접은 line5 하나뿐**.
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 문서만 바뀌었다). 가드 초록: 문자 7,049 ≤ 8,000 · 줄 58 ≤ 60 · 게이트 숫자 정확히 1회 · 인용 M번호 전부 M0~M48 안 · `COMPLETED_SUMMARY` **M10~M46** 범위 유지 · 모델명(`Qwen3-Coder-30B`)·`$0.00`+`Always Free` 캐리어 유지.
- Verified(**안 한 것도 측정이다**): 예산 숫자(8,000)를 브리프에도 archive에도 **적지 않았다** — `harness-config.json`이 유일한 표기이고 **네 번째 표기가 드리프트**다(M19). ⚠️`next-plan-detail`은 11,000을 적고 있다(선행 사례, 이번 범위 밖).
- Blockers: 없음.
- Next: **`[auto]` 씨앗이 말랐다** — 다음 이터는 **DONE(drained)**이다. 사람의 다음 수는 여전히 **GCP 내보내기 테이블 `numRows`**(`bq show --format=json <table>`, 무료). ⚠️**브리프에 남은 여유는 151자**다 — 다음에 한 문장을 더하려면 그만큼 접어야 한다.

## 2026-09-02 — NEXT_PLAN도 접었다 · 한 줄이 조용히 날짜 하나를 잃었다 (gate 2397)

- Status: overnight `[auto]` 1건 — `docs/NEXT_PLAN.md`를 문자 예산 90% 이하로. **완결**(10,777 → **8,003자**, 목표 9,900의 81% · 줄 117 → **112**).
- Changed(신규 `docs/archive/next-plan-detail-2026-09.md`): 닫힌 항목 여덟과 열린 항목 넷의 경위·측정·⚠️/⛔ 전문. **파일을 손으로 쓰지 않고 옛 NEXT_PLAN의 줄 범위를 스크립트로 복사**했다 — 09-02 STATUS 압축이 *"압축은 재작성이고 재작성은 조용히 지운다"*를 남겼으니, **바이트 동일성은 손이 아니라 도구에게** 맡겼다.
- Changed(`docs/NEXT_PLAN.md`): 열린 `[ ]` 항목은 **전부 그대로 열려 있고**(수 변화 0), 닫힌 ⛔ 여덟은 **한 줄 목록**으로 접었다. 헤더가 archive를 **권위로 지목**하고 *"요약만 읽고 결론 내지 말 것"*을 적는다.
- Verified(**삭제 0을 두 번 다르게 물었다**): ⓐ ⚠️/⛔/✅ 마커 **55조각** 전수 대조 — 0 missing. ⓑ **옛 파일의 모든 줄**(≥12자)이 새 NEXT_PLAN+archive에 남아 있는지 — 여기서 **ⓐ가 못 본 것 하나**가 나왔다.
- Verified(**⚠️마커 검사만 했으면 놓쳤다**): Azure Foundry 줄에서 **`(08-12)`가 사라져 있었다** — ₩6,600을 **언제 잰 값인지**가 빠진 것이고, 그 줄엔 마커가 없어 ⓐ의 55조각에 애초에 들어오지 않았다. **가드는 자기 창문 밖을 못 본다**(Risk 12④) — 전수 줄 대조가 그 창문을 넓힌 쪽이다. 복원했다.
- Verified(**첫 판은 글자 예산을 통과하며 줄 예산을 깼다**): 8,028자(≤9,900 ✓)인데 **133줄**(>120 ✗). 두 예산은 **반대 방향으로 당긴다** — 문단을 넓히면 줄이 줄고 글자는 그대로다. 인접 줄을 쌍으로 이어 112줄, 최대 줄 **179자**(브리프를 만든 3,621자 병리와는 다른 자리).
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 문서만 바뀌었다). 예산 가드 넷 초록: 문자 8,003 ≤ 11,000 · 줄 112 ≤ 120 · 게이트 숫자 `gate 2397` **정확히 1회** · 인용한 M번호 전부 `COMPLETED_SUMMARY` M0~M48 안.
- Changed(`docs/PROGRESS_LOG.md`): 이 항목을 넣을 자리가 없어(11,772/12,000) 09-01 두 건(비용체크 · 지운 뒤에도)을 `docs/archive/progress-2026-09.md`로 **옮겼다**. 순서는 git 이력으로 확인했다(정적검사 D51 < 지운뒤에도 < 비용체크).
- Blockers: 없음.
- Next: **GCP 내보내기 테이블 `numRows`** — 판정 시점(09-02 01:11Z)이 지났다. `bq show --format=json <table>`(무료). 0이면 그때가 문제다. 남은 `[auto]`는 **`AGENT_BRIEF` 압축 하나**(7,606 → ≤7,200)이고 ⚠️**거기는 줄 예산이 60이라 이번 함정이 더 좁다**.

## 2026-09-02 — STATUS를 반으로 접었다: 옮긴 것이지 지운 게 아니다 (gate 2397)

- Status: overnight `[auto]` 1건 — `docs/STATUS.md`를 문자 예산 90% 이하로. **완결**(10,994 → **5,197자**, 예산 11,000의 47%).
- Changed(신규 `docs/archive/status-baseline-2026-09.md`): 09-01~09-02의 baseline 줄 여덟(2392·2381·2368·2358·2350·2346·2342·2339) **전문 그대로**. 최신 줄(2397)만 STATUS에 남겼다 — **게이트 숫자 가드가 거기서 읽는다**.
- Changed(신규 `docs/archive/status-risk-detail-2026-09.md`): Active Focus와 Risk 1~12의 경위·측정·⚠️/⛔ 문장. **위험 번호는 STATUS와 같은 번호**다 — 번호가 갈리면 두 문서가 다른 목록이 된다.
- Changed(`docs/STATUS.md`): 주장 한 줄 + 재개 조건만 남겼다. 헤더가 archive 둘을 **권위로** 지목하고 *"요약만 읽고 결론 내지 말 것"*을 적는다.
- Verified(**삭제 0을 기계로 물었다**): 옛 STATUS를 `⚠️`/`⛔`로 쪼개 **48조각**을 새 STATUS + archive 셋에 대조 — **전부 남아 있다**. ⚠️첫 판에서 한 조각(*"같은 계열이 08-15에 재발했고 D49가 일반화해 집행"*)이 실제로 빠져 있었고, 그건 내가 그 줄을 **옮기지 않고 다시 쓴** 자리였다 — **압축은 재작성이고 재작성은 조용히 지운다**. 전문으로 되돌렸다.
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 문서만 바뀌었다). 예산 가드 넷 초록: 문자 5,197 ≤ 11,000 · 줄 96 ≤ 120 · 게이트 숫자 2397 세 문서 일치 · M0~M45 범위 실존.
- Verified(**⚠️예산의 단위는 바이트가 아니다**): `wc -c`는 8,354를 말하고 가드는 5,197을 말한다 — 한글이 UTF-8에서 3바이트다. `wc`로 재면 **예산 초과로 착각한다**. 가드가 쓰는 건 `len(read_text())`다.
- Blockers: 없음.
- Next(⚠️**이건 이득만은 아니다**): 옮긴 절반은 `/sync` 읽기 경로(brief→status→plan→log)에 **없다** — 다음 세션의 기본 문맥에서 빠진다. 그게 압축의 대가고, 그래서 STATUS 헤더가 archive를 권위로 **지목만** 하고 요약하지 않는다. 남은 `[auto]` 둘(NEXT_PLAN 10,797 · AGENT_BRIEF 7,606)도 **같은 함정**이다.

## 2026-09-02 — 인쇄된 경로도 주장이다: 39개를 전수로 물었고 0개가 dangling이었다 (gate 2397)

- Status: overnight `[auto]` 1건 — M46이 남긴 교훈("인쇄된 지시도 주장이다")을 가드로 만들었다. **완결**, M48. 권위 `docs/evidence/the-printed-path-was-a-claim-nobody-checked.log`.
- Changed(`tests/test_script_printed_paths_resolve.py`, 신규): `scripts/*.py`의 **문자열 리터럴 속 레포-상대 경로 전수**가 레포에 실존하는지 묻는다. 앵커(top-level 디렉터리)는 **git에서 유도**해 새 디렉터리가 생기면 그날 스윕된다.
- Verified(**쓰기 전에 쟀다**): 23 스크립트 · **39개**(distinct) · 그중 **stdout에 닿는 것 4개** · **dangling 0**. 초록에서 시작하는 가드지 청소 과제가 아니다.
- Verified(**존재는 git에게 물었다, 이 노트북이 아니라**): `pathlib.exists()`면 여기선 초록, CI에선 red다 — `src/stacks/node_modules`가 디스크엔 있고 `.gitignore:16`에 있다. 불변식은 *"레포가 담고 있다"*지 *"내 파일시스템에 있다"*가 아니다(Risk 12②). 변이 3이 이걸 직접 태운다.
- Verified(**첫 판이 false red를 냈고, 면제 목록으로 덮지 않았다**): `probe_scope_reachability.py:116`의 `.endswith("platform/scope.py")`는 경로가 아니라 **grep 출력에 맞대는 조각**이다(`platform/`이 top-level이라 경로처럼 보였다). **쓰임으로** 갈랐다 — `startswith`/`endswith`의 인자와 `in`의 좌변은 독자에게 보여지지 않는다. ⚠️*"중의적인 top-level 이름은 뺀다"*는 규칙은 `src`(↔`dashboard/src`)까지 죽여서 안 썼다.
- Verified(**접두 매칭 함정은 양쪽에 다 있었다**): 추출 쪽 — 확장자를 `json|jsonl` 순서로 나열하면 `.jsonl`이 잘린다(실제 짝: `model-sweep-live-points.jsonl` ↔ 없는 `.json`) ⇒ 꼬리는 **탐욕적 문자 클래스 하나**. 검사 쪽 — `startswith` 멤버십이면 그 없는 `.json`이 **있는 것으로 통과**한다 ⇒ 정확 일치.
- Verified(**⚠️가드 자신이 한 번 틀렸다 — 변이 하나가 살아남았다**): 접두 함정 테스트가 `_repo_paths()`(집합)에 물었는데 dangling 검사는 **별도의 식**을 써서, 멤버십을 `startswith`로 느슨하게 해도 5개가 전부 초록이었다. **가드가 독자가 쓰는 그 물건이 아니라 제 창문에 물고 있었다**(Risk 12④). 판정을 `_in_repo()` 한 곳으로 뽑아 둘이 같은 것을 묻게 하니 red.
- Verified: `make check` **2397 passed + 2 skipped**(2392 → **+5**), 실패 0. **변이 8종 전부 red**(없는 이름 · `.jsonl`→`.json` · gitignore된 경로 · 추출기를 확장자 나열로 · 스윕 비우기 · `print()` 미인식 · 멤버십 `startswith` · 조각 예외 제거). 변이·실행·복구는 한 스크립트이고 **복구는 바이트 사본에서**(Risk 12⑦, `git checkout --` 아님).
- Verified(**기존 가드와 안 겹친다**): `test_evidence_pointers_resolve`는 `docs/evidence/*.log` **한 종류**를 `tests`·`docs`·`src`에서 훑고 **`scripts/`는 안 읽는다**. 이 파일이 나머지 절반이다.
- Verified(**안 한 것도 측정이다**): `#` 주석은 안 훑는다 — 주석에만 사는 경로를 재니 `src/stacks/node_modules` 하나였고 **의도적으로 tracked가 아니다**(훑으면 가드가 vendored 의존성을 커밋하라 요구한다). 점 top-level(`.github/` 등)은 앵커 밖 — scripts의 참조 횟수를 **0으로 쟀다**. 라이브 호출 0건.
- Changed(`docs/STATUS.md`): 문자 예산이 **10,998/11,000**이라 새 baseline 줄이 안 들어갔다 — 08-30(2332) 전문을 `docs/archive/status-baseline-2026-08.md`로 **옮겼다**(삭제 아님). ⚠️**STATUS 압축 `[auto]`(≤9,900)는 여전히 열려 있다** — 여기선 한 줄 들어갈 만큼만 비웠다.
- Blockers: 없음.
- Next: **GCP 내보내기 테이블 `numRows`** — 판정 시점(09-02 01:11Z)이 지났다. `bq show --format=json <table>`(무료). 0이면 그때가 문제다.

## 2026-09-02 — 서버는 대기 시간을 말하고 있었고 전송 계층이 그걸 버렸다 (gate 2392)

- Status: overnight `[auto]` 1건 — M46ⓒ가 남긴 잔여(Azure 429 자동 재시도). **완결**, M47.
- Changed(`probe_cloud_spend.py`): 전송 계층 **`az rest` → `curl -D -` + `az` 토큰**(`az rest`가 헤더를 버려서 이 항목이 별도였다) · `_cost_query_with_retry`가 **`clienttype-retry-after`가 말한 만큼만** 기다렸다 다시 묻는다(최대 3회, 매 대기 60초 클램프, **기다린다고 인쇄**) · `_split_http`/`_retry_after`/`_azure_token`/`_curl` 신설.
- Changed(**⚠️토큰은 argv에 두지 않았다**): `--config -`(stdin)로 넘긴다 — `ps`는 이 기계의 아무 프로세스나 읽는다. **URL은 argv에 남겼다**(비밀이 아니고 가드가 무는 게 그것이다).
- Verified(**핵심은 안 하는 쪽이다**): **헤더가 없으면 재시도하지 않는다.** 없는 간격을 지어내는 것이 애초에 429를 영구 실패로 읽게 만든 방식이다(20초<40초). 파싱 안 되는 값(`Retry-After`는 날짜도 허용)도 **0초가 아니라 재시도 없음** — 0으로 읽으면 스로틀 중인 서버에 타이트 루프를 돈다.
- Verified(**가드가 아무것도 안 보고 있었다**): `test_only_the_cost_query_endpoint_is_posted_to`가 사라진 `az rest --url`을 무는 형태라 **매치가 0이면 영원히 통과**였다. curl 계층에 대고 묻고 **POST 0건이면 red**로 바꿨다(Risk 12④의 그 모양).
- Verified: `make check` **2392 passed + 2 skipped**(2381 → **+11**), 실패 0. **변이 7종 전부 red**(URL 이동 · `-D -` 제거 · 없는 간격을 20초로 추측 · 토큰을 argv로 · 재시도 상한 완화 · 클램프 제거 · 파싱 실패를 0초로). 변이·실행·복구는 한 스크립트(Risk 12⑦).
- Verified(**안 한 것도 측정이다**): **라이브 재측정 안 함** — 429를 다시 부르는 건 그 자체로 스로틀을 쓰는 것이고, 이 변경의 내용은 **간격을 어디서 얻는가**라 오프라인에서 전부 물어진다. AWS/GCP도 안 물었다(무인 루프는 청구서를 만들지 않는다).
- Blockers: 없음.
- Next: **GCP 내보내기 테이블 `numRows`** — 판정 시점(09-02 01:11Z)이 지났다. `bq show --format=json <table>`(무료). 0이면 그때가 문제다.

