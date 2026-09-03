# PROGRESS_LOG — platform-agent

최종 갱신: 2026-09-03

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-09.md` · `…-2026-08.md` · `…-2026-07.md`

---

## 2026-09-03 — harness 1.4.0: 무인 루프의 기본값이 바뀌었고, 새 문서는 가드가 먼저 잡았다 (gate 2410)

- Status: overnight-harness **1.2.0 → 1.4.0**. Makefile harness 블록을 새 스니펫으로 교체(모델 라우팅 actor `claude-sonnet-5` / critic `claude-fable-5-1`, ledger·resume·trajectory 타깃), `docs/LESSONS.md` 생성, `harness-config`에 `lessons` 경로·예산(40줄) 추가. 설치기가 되살린 `docs/engineering/`은 b078094에서 지운 경로라 다시 뺐다.
- Behavior change (1.4.0 기본값, Claude 엔진): `OVERNIGHT_CONTRACT=auto`(lean WorkContract), `OVERNIGHT_CRITIC` 빈 값 = `auto`, 턴 예산 초과는 **기록만**(되돌리지 않음, `OVERNIGHT_TURN_FAIL_CLOSE=1`로 복원). 다음 `make overnight`부터 적용.
- Verified: `make check` **2410 passed + 2 skipped**(2407 → **+3**). 첫 실행은 **4 red** — 새 `lessons` 예산이 세 선언 검사(정책표·머리말·vacuity 집합)에 없었고 진입점 gate 숫자가 2409≠2412였다. 가드가 설계대로 잡은 것이라 숫자 대신 선언을 맞췄다. `harness-init.sh --check` OK, `make overnight-where` → 1.4.0.

## 2026-09-03 — 씨앗을 다시 채웠다: 넷은 초록에서 시작하는 가드다 (gate 2407)

- Status: 09-02에 `[auto]`가 5/5 소진돼 무인 루프가 집어갈 것이 **0**이었다. `/overnight-seed`로 판단하고 **다섯**을 기록했다(PR #73). 이 체크포인트로 ①은 **닫혔다** ⇒ 남은 씨앗 **넷**.
- Changed(`docs/NEXT_PLAN.md`): ①`PROGRESS_LOG` 압축 · ②진입점 문서의 `docs/**/*.md` 지목 실존 가드 · ③진입점 문서의 `D<번호>` 실존 가드 · ④문자 예산 숫자의 **유일 표기** 가드 · ⑤`STATUS` **줄** 예산 회복. ②③은 **오늘 dangling 0 / 14개 전부 실재** — **초록에서 시작하는 가드**지 청소 과제가 아니다.
- Verified(**⚠️씨앗을 만들다 세는 함정을 밟고 잡았다**): ②를 처음 재니 dangling **11건**이었는데 그중 **3건은 내 정규식이 만든 것**이다 — `bin/docs/archive/agents.md`에서 `docs/…`만 잘라냈다. 경계를 넣으니 **8건**이고 전부 **2026-07 archive**가 가리키는 사라진 파일이라 **진입점 기준으로는 0**이다. **잘못 센 수치로 씨앗을 만들면 루프가 한 이터를 버린다** ⇒ 그 함정을 씨앗 줄에 같이 적었다.
- Verified(**"없다"를 실측으로 적는다**): 린트 부채 쪽엔 씨앗이 **없다** — 추적 소스에 `type: ignore` **1건**, TODO/FIXME/XXX/HACK **0건**. 첫 조사에서 3,026건이 나온 건 vendored 경로가 섞인 것이다.
- Verified(**⚠️분량은 벽시계가 아니라 씨앗 수다**): 러너 로그 실측 — 실작업 이터 **8.7·9.0·9.9·15.0·15.5분**(평균 **~12분**), 이터당 **$2.99~$7.19**. *"몇 분"이 아니다.* 넷이면 **~48분·대략 $20**이고 **마르면 멈춘다**(정상). `MAX_ITER`는 씨앗 수보다 크게.
- Changed(`docs/PROGRESS_LOG.md`): 이 항목 자리를 내려고 09-02 두 건(NEXT_PLAN 압축·STATUS 압축)을 `docs/archive/progress-2026-09.md`로 **옮겼다**(삭제 아님) ⇒ 씨앗 ①의 Done 기준(≤10,800자)을 **여기서 충족했다**. 그래서 ①을 열어 둔 채로 두지 않고 **닫고 결과를 적었다**.
- Changed(`docs/AGENT_BRIEF.md`): ▶ NEXT SESSION이 **이미 끝난 일**(M50)을 가리키고 있어 교체했다 — 다음 세션의 첫 행동은 **씨앗 절**이다.
- Verified: `make check` **2407 passed + 2 skipped**(변동 0 — 계획·기록 문서만 바뀌었다). 세션 전체로는 **2397 → 2407**(M50의 +10)이고 M49·M51은 측정이라 게이트 변동이 없다.
- Blockers: 없음. ⚠️**루프는 돌리지 않았다** — 이터당 실비가 붙는 무인 실행이라 시작은 사람 신호를 받는다.
- Next: **씨앗 넷 중 하나**(`NEXT_PLAN`의 «Overnight 씨앗» 절) 또는 `MAX_ITER=7 make overnight`. 그리고 **며칠 뒤 `make spend-check`** — 창이 3일→7일이면 GCP 런레이트가 가정 없이 나온다.

## 2026-09-02 — 재개 조건이 2년 전에 멈춘 이슈를 보고 있었다 (gate 2407)

- Status: 열린 항목 중 **날짜가 박힌 재확인 지시**를 단 유일한 것(Risk 6 / Cosign 어드미션, *"이 날짜부터 볼 것"*)을 판정했다. **완결**, M51. 권위 `docs/evidence/the-resume-condition-was-watching-a-dead-issue.log`.
- Verified(**결론은 유지된다**): 어드미션은 **아직 못 켠다**. 08-08 kind 실측이 *"서명된 것도 no signatures found"*였고 그 판정은 그대로다.
- Verified(**⚠️근거는 틀렸다 — 물고 있던 신호가 죽어 있었다**): 재개 조건이던 `policy-controller#1406`은 **2024-09-30 이후 갱신이 없다**. 그 이슈가 요구하던 구현은 **`#1725`로 2025-04-23에 머지**됐다. **"이슈가 열려 있다"는 "지원이 없다"의 증거가 아니었다** — Risk 4의 *"'없다'는 어떻게 봤는지까지"*가 업스트림 쪽에서 재발한 모양이다.
- Verified(**⚠️그럼 고치기 전 버전을 시험한 것인가 — 아니다**): 08-08에 쓴 chart **0.10.6**의 appVersion은 **0.13.1**(2025-09-17)로 **`#1725` 머지 이후**다. 즉 **지원이 들어간 버전에서 이미 실패했다.** 이 확인을 안 했으면 *"낡은 버전을 시험했다"*는 틀린 이야기를 적을 뻔했다.
- Verified(**진짜 신호는 따로 있었다**): `#1899`(*"cosign v3.0.2 서명을 policy-controller **0.13.1**이 검증 못 한다"*, **open**)가 **우리 조합 그대로**이고, 고침은 `#1968`(*"fix: Support cosign v3 signature verification"*, **미머지**)이다. ⇒ **새 조건 = `#1968` 머지 또는 `#2007`(2026-08-24 머지)을 담은 릴리스** — 최신 v0.15.1은 **2026-03-26**이고 그 뒤 **51 커밋이 미출시**다.
- Verified(**cosign 쪽 기록은 정확했고, 더 넓게 참이다**): `--new-bundle-format`은 v3.1.2의 **여섯 하위 명령**(`sign`·`sign-blob`·`attest`·`attest-blob`·`verify`·`verify-blob`) **어디에도 없다** — v2의 옵트인 플래그였고 v3에선 그 형식이 기본이라 사라졌다. ⇒ **간극은 서명하는 쪽이 아니라 검증하는 쪽**이고, `#2007`(policy-controller를 cosign v3.1.3으로 올림)이 그 방향을 가리킨다.
- Verified(**안 한 것도 측정이다**): **클러스터를 건드리지 않았다** — 재시도는 kind 변경이라 승인 후다. 클라우드 호출 **0건**(GitHub API와 로컬 `cosign --help`뿐). `make check` **2407 passed + 2 skipped**(변동 0 — 문서와 증거만 바뀌었다).
- Blockers: 업스트림. **단 이제 기다리는 대상이 살아 있는 것으로 바뀌었다.**
- Next: 며칠 뒤 **`make spend-check`**(창 3일→7일이면 GCP 런레이트가 가정 없이 나온다) · Risk 6은 **`#1968`/릴리스**를 볼 것.

## 2026-09-02 — `MEASURABLE`이 금액을 대신 묻는다: 첫 가드는 한 글자 때문에 변이를 놓쳤다 (gate 2407)

- Status: 브리프가 지목한 다음 행동 — 설정문서 §4가 *"데이터가 생기면 그때 붙인다"*로 미뤄 둔 분기. **완결**, M50. 권위 `docs/evidence/the-guard-let-the-mutation-through-because-of-one-character.log`.
- Changed(`scripts/probe_cloud_spend.py`): `MEASURABLE`이 **질의를 돌린다**(`_export_sql`/`_export_spend`/`_print_gcp_amounts` 신설, `bq show`는 `_table_meta` 한 곳으로). 인쇄는 프로젝트별 **총사용액·PROMOTION·기타크레딧·청구** 넷 + 창 + 스캔 바이트.
- Changed(**크레딧을 한 컬럼으로 합치지 않았다**): 프로모션은 **마르는 잔액**이고 `DISCOUNT`는 **요율의 성질**인데, 합치면 화면이 똑같아지고 독자는 *"GCP는 싸다"*로 읽는다 — **잔액이 다할 때까지만 참인 문장**이다. 질의가 `= 'PROMOTION'`과 `!= 'PROMOTION'`을 따로 센다.
- Verified(**⚠️첫 가드가 그 변이를 통과시켰다 — 한 글자다**): `"= 'PROMOTION'" in sql`은 **`!= 'PROMOTION'`에도 참**이라, promo 컬럼을 전 크레딧으로 넓혀도 **남은 반쪽이 사라진 반쪽 대신 답했다**. 부등호를 가르는 lookbehind로 고쳤다. **M48의 접두 매칭 함정과 같은 계열**(Risk 12④) — 이번에도 가드가 **제 창문**에 물고 있었다.
- Verified(**⚠️프로브가 제가 경고하는 오독을 하고 있었다**): 첫 판이 인쇄한 창은 `2026-08-01 ~ 2026-09-02` — **한 달**이다. 그 08-01은 `project`가 없는 **Invoice 행 하나**이고 실사용은 08-30부터다(**M49 ⓑ가 적은 바로 그 행**). ⇒ 창은 **계정 수준 행을 뺀** 사용 행에서만 잰다: `08-30 ~ 09-02 (729행, 계정 수준 1행 제외)`. **경고를 문서에 적는 것과 도구가 그 함정을 피하는 것은 다른 일이다.**
- Verified(**안 하는 쪽도 정했다**): 질의 실패는 **0이 아니라** *"직접 물어볼 것"* + 붙여넣을 명령 · `--project_id`를 넘긴다(없으면 **다른 프로젝트에 과금**, 09-01 실측) · **스캔 바이트를 인쇄한다** — 이 프로브에서 **유일하게 과금되는 호출**이고, CE가 청구서의 84%가 된 방식이 *"반복해서 물은 것"*이다.
- Verified: `make check` **2407 passed + 2 skipped**(2397 → **+10**), 실패 0. **변이 12종 전부 red**. 변이·실행·복구는 한 스크립트, **복구는 바이트 사본에서**(Risk 12⑦). 라이브 확인은 **`report_gcp()` 직접 호출**(BQ 질의 1건 ~40KB) — **AWS CE 0건**.
- Changed(`docs/AGENT_BRIEF.md`): 7,265→**6,935자**. 증분 내역의 산문(M40~M48 열거)을 접었다 — **`STATUS` Baseline이 이미 권위**이고 브리프가 복제하고 있었다. ⚠️중간에 **7,200 정확히**에 앉았는데, 직전 세션이 *"7,199는 통과였지 여유가 아니었다"*를 적어 둔 그 자리라 더 접었다.
- Blockers: 없음.
- Next: **며칠 뒤 `make spend-check`를 그냥 돌려 볼 것** — 창이 3일→7일이 되면 런레이트가 가정 없이 나온다. ⚠️단 `spend-check` 전체는 **AWS CE $0.01**을 문다(GCP만 보려면 `report_gcp()` 직접 호출).

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
