# PROGRESS_LOG Archive — September 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 9월 이력입니다. 최신이 위.

---

## 2026-09-01 — 테이블은 생겼는데 아무것도 안 들어 있었다 · 묻는 도구 셋이 틀렸다 (gate 2381)

- Status: 전날의 Next("`spend-check`의 GCP 줄")를 물으러 갔다가 **묻는 도구 자신의 결함 셋**이 나왔다. 셋 다 **읽어선 안 보이고 태워야 보인다**. 권위 `docs/evidence/the-table-existed-and-held-nothing.log`.
- Verified(**GCP — 켠 것·실린 것·읽히는 것은 셋 다 다르다**): 13시간 뒤 테이블이 **생겼고**(01:53Z 생성, 토글 42분 뒤) 프로브는 *"잴 수 있다"*로 바뀌었다. 그런데 **`numRows` 0**이고 `lastModifiedTime`은 **조회 4분 전**(14:08Z)이었다 — 작성기는 살아서 도는데 실린 게 없다. ⚠️**"잴 수 있다"고 말해 놓고 물으면 답이 없었다**: `MEASURABLE`이 **테이블 존재**만 보고 **행 수**를 안 봤다. 이 파일이 존재하는 이유(*빈 절은 0으로 읽힌다*)가 **한 층 위에서 재발**. ⚠️**0행을 "₩0"으로 읽지 말 것** — 결제 계정에 프로젝트가 **5개**고, 적재 미도착과 실릴 것 없음은 **지금은 구분 불가**다(판정 시점은 §3대로 **하루**).
- Verified(**GCP — 프로브가 인쇄하던 `bq` 명령은 돌지 않는다**): MEASURABLE 분기는 **라이브 내보내기가 있어야 도달**해서 **한 번도 실행된 적이 없었다** — 오늘 처음 태우니 즉시 에러. 한 줄에 결함 셋: ⓐ`project:dataset.table` **콜론**(표준 SQL은 점) ⓑ`--project_id` 없음 → **다른 프로젝트**(`claude-study-501117`)에서 실행됐다 ⓒ`SUM(cost)`만 = **크레딧 미반영**. ⚠️ⓒ는 `GCP_BILLING_EXPORT_SETUP.md` **§4가 명시한 함정**인데 **그 문서를 가리키는 도구가 그걸 인쇄하고 있었다** — 같은 명령이 **두 벌이었고 한 벌만 맞았다**. ⚠️**인쇄된 지시도 주장이다.**
- Verified(**Azure — 기록된 결론이 뒤집혔다**): 13시간 뒤에도 429(5회째)라 헤더를 봤다. 고갈된 건 **`clienttype-requests: DefaultQuota:0` 하나**고(entity 2·tenant 18·QPU 58 여유) 서버가 **`clienttype-retry-after`로 대기 시간을 말하고 있었다**(5→**40**). 40을 기다리니 **200** — ACR **₩76.67** · Cosmos DB ₩0.00(08-30 기준선과 같은 성질, 전액 남의 것). ⚠️**재시도는 두 번 다 답이었다**: 09-01의 *"이번엔 아니었다"*는 **간격이 서버 요구값 아래**(20초<40초)였던 것이고, **고정 간격 재시도는 영구 실패와 구분되지 않는다**. ⚠️`_why()`가 docstring에 적은 값어치(*"1분 뒤 재시도인지 깨진 자격증명인지"*)를 **헤더를 버리는 전송 계층(`az rest`)이 못 주고 있었다** — 이유의 **이름**은 줬고 **행동에 필요한 값**은 못 줬다.
- Changed(`probe_cloud_spend.py`): 상태 **셋→넷**(`EXPORTED_EMPTY` 신설 — MEASURABLE에 접으면 **없는 답을 약속**하고 NOT_EXPORTED에 접으면 **이미 옳게 켜진 토글로 되돌려 보낸다**) · 행 수는 **`bq show` 메타데이터**로 센다(스캔 0바이트 = **$0**; `bq query`로 셌으면 **프로브가 돌 때마다 과금** = CE가 청구서 84%가 된 그 방식) · `_export_query()`로 명령을 **한 곳에서만** 만든다 · `AZURE_429_HINT`는 **429일 때만** 붙는다.
- Verified(**⚠️새 함정 둘을 미리 막았다**): **`bq show` 실패는 0행이 아니다**(`AccessDenied`·리전 `[]`·429와 같은 부류 → MEASURABLE로 두고 질의가 독자 앞에서 시끄럽게 실패하게 둔다) · **빈 테이블이 스윕을 멈추지 않는다**(멈추면 스윕이 지우려던 **단일 위치 가정**이 되살아난다). **고친 명령은 쓰기 전에 라이브에 태웠다**(exit 0).
- Verified: `make check` **2381 passed + 2 skipped**(2368 → **+13**), 실패 0. **변이 8종 전부 red**(존재만으로 MEASURABLE·콜론 복원·`--project_id` 제거·credits 제거·힌트 제거·메타데이터 실패를 0행으로·빈 테이블이 스윕 중단·모든 실패에 힌트).
- Verified(**안 한 것도 측정이다**): AWS는 **재측정하지 않았다** — 13시간 전 값이 유효하고 **다시 묻는 것 자체가 청구서**다. GCP 확인도 `bq ls`/`bq show`(무료)로 했고 `spend-check` 전체는 안 돌렸다.
- Blockers: GCP 적재(시간) · Azure는 `az rest`가 헤더를 버리는 것 그대로(전송 계층 교체는 별도 승인).
- Next: **토글 01:11Z로부터 하루 뒤**(09-02 01:11Z) `numRows` 재확인 — **여전히 0이면 그때가 문제**다. 이제 프로브가 그 구분을 스스로 한다.

## 2026-09-01 — "비용체크"를 재다: 지출의 84%가 얼마 나가는지 물어본 값이었다 (gate 2368)

- Status: 문서 인용이 아니라 **재서** 답했다. 코드 변경 없음. 권위 `docs/evidence/the-measurement-is-the-bill.log`.
- Verified(**AWS — 서비스별로 가르니 결론이 바뀐다**, 08-20~09-01 크레딧 제외): **Cost Explorer $0.2000 = 전체 $0.2380의 84%** · EC2-Other(EBS 잔여) $0.0295 · S3 $0.0056 · ECR $0.0025 · DynamoDB $0.0004 ⇒ **진짜 인프라는 13일에 $0.038 ≈ 월 $0.09**. 바닥 $0.0034/일은 08-30과 동일하고, 봉우리는 **CE 단가 $0.01의 배수**로 뛴다(08-30·08-31이 $0.06대 = 그 이틀에 비용 조사를 했다).
- Verified(**⚠️08-30 기록의 재확인이 아니라 악화**): 그때는 *"이번 달 $0.64 중 최대 항목"*이었고 지금은 **전체의 84%**다. ⚠️**이 기록을 쓰려고 CE를 2회 더 불렀다 — $0.02가 곧 붙는다.** 관측이 관측 대상을 만드는 계정이고, **조회 남발 금지는 취향이 아니라 산수다**.
- Verified(**⚠️09-01 줄의 $0.0000은 0이 아니다**): CE 지연 이틀+. 오늘 창만 보고 답하면 틀린다.
- Verified(**Azure — 못 쟀다. 이번엔 재시도가 답이 아니었다**): spend-check 1회 + 20초 간격 3회 = **4회 연속 429**. 08-30 기록은 *"재시도가 답이었다"*였는데 **이번엔 아니었다** — ⚠️**기록된 처방이 항상 듣는 건 아니고, 안 들었다고 답이 바뀌지도 않는다**: **'0'이 아니라 '측정 실패'**다. 기준선은 08-30의 **₩7,063 전액 남의 ACR**. ⚠️`az costmanagement` 확장이 없어 손으로 우회하려던 첫 시도가 실패했다 — **레포 프로브(management.azure.com 직접 POST)를 쓰는 게 맞았다**.
- Verified(**GCP — 아직인 게 맞다**): 켠 지 **11분**(01:11→01:22 UTC), `bq ls` 테이블 0개. `GCP_BILLING_EXPORT_SETUP.md` §3이 예고한 정상 상태이고 **판정 시점은 하루 뒤**다.
- Blockers: Azure 스로틀(시간) · GCP 테이블 생성(시간). 둘 다 **지금 할 수 있는 일이 없다**.
- Next: ⚠️**세 답의 모양이 각각 다르다 — 하나로 요약하지 말 것**(AWS=쟀다/지연 · Azure=못 쟀다 · GCP=아직). **하루 뒤 `make spend-check`** 재확인이 다음 행동이다.


## 2026-09-01 — 지운 뒤에도 파이프는 계속 말을 걸고 있었다 · 결제 내보내기를 켰다 (gate 2368)

- Status: "환경이 없어서" 막혀 있던 둘을 수행했다(사용자가 Docker 기동 + 브라우저 제공). 권위 `docs/evidence/the-pipe-kept-403ing-after-the-key-was-gone.log`.
- Verified(**예고한 실패가 라이브였다**): kind를 띄우니 Prometheus가 **삭제된 워크스페이스로 계속 remote_write**했다 — `403 Forbidden: "The security token included in the request is invalid."`(지운 IAM 키). D50이 *"지우면 실패하기 시작한다"*고 적은 그것이고 **그게 결정의 내용이었다**.
- Verified(**⚠️값 파일을 고친 것만으로는 안 끝났다**): git의 값 파일엔 블록이 없는데 **배포된 helm 릴리스(rev 5)는 그대로**였다. **선언을 고치는 것과 도는 것을 고치는 것은 다르다** — 이 레포의 반복 주제가 인프라 층에서 재발.
- Changed(**helm rev 5→6**): 계획서와 같은 순서(`helm get values` 먼저). ⚠️**함정**: `--reuse-values`를 붙인 dry-run엔 **remoteWrite가 1건 남았다**(기존 릴리스 값을 병합하므로) — 그대로 적용했으면 *"고쳤다"*고 보고하며 아무것도 안 바뀌었을 것이다. 뺀 dry-run은 0건 + 알람 룰 유지 ⇒ 적용. 고아 Secret `monitoring/amp-remote-write` 삭제(`NotFound` 확인) · PrometheusRule 31개·`PlatformDemoCrashLoop` **그대로**.
- Verified(**⚠️"설정이 사라졌다"와 "도는 것이 멈췄다"도 다르다**): CR·config가 비었는데도 오류는 01:09:54까지 계속됐다(파드가 옛 설정). 그래서 **로그가 아니라 런타임 API에 물었다**(`/api/v1/status/config` → `remote_write` **0건**), 리로드(01:10:47) **이후 깨끗한 창**으로 다시 셌다 → **40초간 0건**. ⚠️`--since=90s`로는 **7건**이 나왔다 — **창이 사건보다 넓으면 지나간 실패를 현재로 읽는다**(MTD로 "지금"을 답하지 말라던 것과 같은 모양).
- Verified(**곁에서 나온 기존 고장 — 내 것이 아니다**): 오퍼레이터가 alertmanager를 `invalid URL: unsupported scheme ""`로 못 만든다. 값 파일 74행이 **렌더 안 된 `${webhook_url}`**이고 파드는 **42일간 34회 재시작**, 업그레이드 **전** 로그에도 이미 연결 거부가 있었다 ⇒ **기존 고장.** 고치려면 Terraform이 렌더해야 해서 **범위 밖이라 손대지 않았고, 기록만 남긴다.**
- Changed(**GCP 결제 내보내기 켬**): 표준 사용량 비용 → **사용 설정됨**(프로젝트 `project-ec7809f7-0fb5-45d4-b6d` · 데이터 세트 `billing_export`, 새로 안 만듦). ⚠️**첫 시도는 틀린 Chrome 프로필**이었다(아바타 "B", 페이지 로드 실패) — 문서 §1이 적어 둔 함정 그대로. ⚠️**편집 폼의 프로젝트 기본값이 `Claude Study`**여서 그대로 저장했으면 **엉뚱한 프로젝트에 켜졌다.**
- Verified(**⚠️아직 "잴 수 있다"가 아니다**): `make spend-check`는 여전히 *"아직 못 잰다 — 내보내기 테이블이 없다"*이고 **그건 문서 §3이 예고한 정상 상태**다(첫 테이블까지 수 시간). **켠 것은 확인됐고 읽히는 것은 미확인이다 — 둘을 같은 문장으로 쓰지 않는다.** ⚠️소급 안 됨(§0): 07월 GKE 비용은 복구되지 않는다.
- Blockers: 없음. **게이트 숫자 변화 없음**(코드 변경 없음).
- Next: **`make spend-check`의 GCP 줄을 수 시간 뒤 재확인**(하루가 지나도 그대로면 그때부터가 문제) · alertmanager `${webhook_url}` 미렌더(기존 고장, 인프라 결정).

## 2026-09-01 — 정적검사 결정을 닫았다: 측정 위에서, "나중에 보자"가 아니라 (gate 2368)

- Status: 08-30부터 열려 있던 **사용자/레포 결정**을 **숫자를 갖고** 물어 닫았다 → **D51**.
- Decision(**D51 — 정적검사는 게이트에 안 들어간다. 측정만 기록한다**): `gate.yml`의 *"a CI job is a bad place to introduce a standard nobody agreed to"*를 유지한다.
- Verified(**근거 ① ruff는 잡을 게 없다**): 20건, **여섯을 직접 열어** 확인 — 전부 미관/죽은 변수, **결함 0**. ⇒ 넣으면 **스타일을 집행하는 것이지 버그를 막는 게 아니다.**
- Verified(**근거 ② mypy는 신호는 있는데 비율이 나쁘고 비싸다**): 253 중 **200(79%)이 주석 부채**, **53이 실제 주장**. 그 53 중 **21건을 열어 고칠 값이 있던 건 2건**(M44 계약 갭 · M45 선언 불일치) — 나머지 19는 노이즈이거나 *"코드는 옳고 타입이 못 따라간다"*. 그리고 **`mypy src/`가 45초**로 게이트(38초)를 두 배로 만든다 ⇒ **D49가 288s→39s를 얻어낸 이유와 정면 충돌.**
- Verified(**⚠️요약 금지**): **"정적검사는 쓸모없다"가 아니다** — 이번 세션의 **실제 결함 둘을 찾은 건 mypy이고 테스트 스위트는 둘 다 놓쳤다**. 결정된 건 *가치*가 아니라 **게이트에 상주시킬 값어치가 아직 아니라는 것**이고, 여는 조건은 D51에 적었다.
- Changed: `DECISIONS` **D51** 신설 · `NEXT_PLAN`의 항목을 닫음 · `AGENT_BRIEF`의 `▶ NEXT SESSION`을 **남은 것**으로 교체(BQ 내보내기 · 고아 Secret · 4b · Phase 5 attach UI).
- Blockers: 없음. **게이트 숫자 변화 없음**(문서·결정만).
- Next: ⚠️**무과금 목록이 또 비었다 — 그게 사실이 아니라는 게 이 레포의 기록이다**(여섯 번 틀렸다). 09-01의 증분 넷은 **전부 다른 일을 하다가** 나왔다.

## 2026-09-01 — 시그니처는 필수라 했고 본문은 선택이라 했다: 그 기본값이 정책이었다 (gate 2368)

- Status: mypy 253을 **분류하다가** 나왔다. **결정은 여전히 안 내렸다.** 권위 `docs/evidence/the-signature-said-required-the-body-said-optional.log`.
- Verified(**`arg-type` 15 중 10이 한 함수**): `onprem_webhook_api`가 `summary.get(...)`를 `record_incident(severity: str, …)`의 **필수 `str`** 자리로 넘긴다. 그런데 본문은 다섯 다 **`x or "기본값"`** — **본문은 처음부터 `None`을 받도록 쓰여 있었다. 코드가 옳고 선언이 거짓이었다.**
- Verified(**`None`은 도달 가능하다**): 파이프라인 결과는 **키를 항상 갖지만 값이 `.get()` 결과**이고, 그 위에 파이프라인이 스스로 `incident = detector_out.get("normalized_incident") or {}`라 적어 뒀다 — **부재를 예상했다는 저자들 자신의 진술**이다. 없으면 `service`가 `None`으로 `alarm_name`에 도착한다. ⚠️`else: # MANUAL` 가지는 **`mode`가 `None`일 때도 걸린다**.
- Changed: 다섯을 `str | None`로. ⚠️**문을 닫는 쪽이 아니다** — 거부하면 **저하된 인시던트가 "인시던트 없음"이 된다**. `arg-type` **15→5**, mypy **253→241**.
- Changed(**⚠️진짜 발견은 그다음 — 가드 +10**): 주석을 고치는 건 **도는 것을 하나도 안 바꾼다**. 도는 것은 **기본값 부여**이고, `record_incident`를 쓰는 테스트 7개 중 **다섯 필드에 `None`을 넘기는 파일이 0개**였다 ⇒ **저하된 인시던트의 분류가 무단언**이었다. 둘은 그냥 기본값이 아니라 **축의 안전한 끝**이다: **MANUAL**=실행하지 **않는** 모드(AUTO로 기본값이 되면 **아무도 고르지 않은 조치가 나간다** — M39의 반대편) · **P3**=척도의 **바닥**(P1이면 불완전한 analyzer 출력마다 사람을 호출한다). 신규 가드는 문자열이 아니라 **어느 끝인지**를 묻고 **저장된 행까지** 읽는다(반환값만 보면 파일에 `null`이 적혀도 통과한다).
- Verified(**변이 4 red · 1은 못 쟀다**): mode→AUTO(3 failed) · severity→P1(3) · 기본값 제거(2) · 주어진 값 무시(1). ⚠️**M5(저장 건너뛰기)는 단일 호출 지점이 없어 변이가 안 붙었다** — *"안 쟀다"*로 남긴다.
- Verified(**곁가지 — mypy 오탐 하나를 격리했다**): `return-value` 4건이 전부 `x or os.getenv(k, DEF)` 모양인데, `os.getenv(k, DEF)` 단독은 `str`, `x or "literal"`도 `str`, `x or y`도 `str`인데 **`x or os.getenv(k, DEF)`만 `str | None`**이다 — `or`의 오른쪽에서 **오버로드가 첫 번째로 재해석**된다(mypy 1.14.1). **런타임엔 None이 될 수 없다** ⇒ 고치지 않았다.
- Verified(**누적 그림 — 결정에 줄 숫자**): 실제 주장 53 중 **21건을 열었다** → **실제로 고칠 값이 있던 건 2건**(M44의 계약 갭 + 이 선언 불일치), 나머지 19는 노이즈이거나 *"코드는 옳고 타입이 못 따라간다"*(오탐 4 · 도달 불가 2 · 재-export 3 · 이종 dict 2 · 이름 재선언 1 · 미설치 라이브러리 2 · 기타). **그게 이 도구의 이 레포에서의 신호 대 잡음비다.**
- Blockers: 없음.
- Next: **정적검사 게이트 편입 — 이제 숫자를 갖고 물을 수 있다**(사용자/레포 결정) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

## 2026-09-01 — 계약이 모두가 부르는 메서드를 빠뜨리고 있었다: 찾은 건 mypy였다 (gate 2358)

- Status: *"정적검사를 게이트에 넣을지"*의 **선행 실측을 다시 돌리다가** 나왔다. **결정은 내리지 않았다.** 권위 `docs/evidence/the-contract-omitted-the-method-everyone-calls.log`.
- Verified(**기록의 "전수 분류 결함 0"이 재현된다**): 가장 위험해 보이는 여섯을 실제로 열었다 — `dep_id`(넘길 파라미터가 **아예 없다**) · `azure_runner.url`(각 분기가 자기 URL을 만든다, **죽은 코드**) · F402(문자열 루프 변수와 **이름만** 겹침) · `original_guard`(**새 인스턴스**라 복원할 게 없다) · `result`(단언은 put_item 부작용에 건다) · E701 ×5(열 맞춤). **20건 전부 미관/죽은 변수.**
- Verified(**없던 반쪽 — mypy 253의 성격**): `type-arg` 71·`import-untyped` 40·`no-any-return` 36·`no-untyped-def` 32·`no-untyped-call` 21 = **200/253(79%)이 주석 부채**이고 나머지 **53이 실제 타입 주장**이다. **"253"은 절망적으로 읽히고 "200은 부채, 53이 주장"은 결정 가능하게 읽힌다.**
- Verified(**나머지 여섯은 닫았다 — "모른다"와 "도달 불가"는 다른 답이다**): 재-export 셋은 런타임 무관 · `model_router`의 `None` 역참조 둘은 **재서 도달 불가**다 — 업스트림이 *"if it has ended, otherwise None"*이라 관건은 **어디서 읽는가**이고, `result = run.result`가 `async for`를 **완주한 뒤**(본문에 `break` 없음)에 있다. 예외도 `GeneratorExit`도 그 줄에 못 닿는다. **mypy는 선언 타입에 대해 옳고 코드도 옳다** — 좁히기를 안 썼을 뿐. **다음 세션이 같은 줄을 다시 파지 않게 적어 둔다**(마른 스윕도 측정, M26).
- Verified(**⚠️그 53 중 하나가 진짜였다**): `"ExecutionAdapter" has no attribute "parameters_for_action"` — 네 어댑터가 **다 구현**하고 `aws/executor.py`가 **베이스 타입을 통해 부르는데** 계약이 선언하지 않았고 **테스트는 그 이름을 한 번도 언급하지 않는다(0건)**. ⚠️**오늘 런타임 결함은 없다**(넷 다 있다). 나쁜 건 호출부가 `except Exception: pass`라는 것 — 베이스를 만족시키는 데 `resolve_action` **하나면 충분**했으므로, 다섯째 provider가 그 조건만 채우면 `AttributeError`가 **삼켜지고 AWS 모양 파라미터**를 받는다. **에러 나지 않는 방식으로 실패한다**(Risk 8).
- Verified(**⚠️`from_alarm_context`는 고치지 않았다**): 정의가 **AWS 하나**뿐이고 호출도 `get_signal_adapter("aws")`로 **리터럴 고정**이라, 베이스에 선언하면 나머지 셋에 **거짓**이 된다. 기준은 *읽는 쪽의 provider 간 비대칭*이지 고아 선언이 아니다(M19 ⓑ) — **리터럴 고정 호출엔 틀릴 비대칭이 없다.**
- Changed(**가드 +8**): 베이스에 `parameters_for_action` 선언 + 신규 `test_adapter_contract_declares_what_callers_call.py` — **목록이 아니라 AST 유도**: provider가 **변수면 베이스가 선언해야 하고 리터럴이면 면제**(정규식으론 둘을 못 가른다) · 형제 넷이 계약 전체를 구현하는가(선언만 하면 `NotImplementedError`가 같은 `except`에 삼켜지니 **선언은 절반**).
- Verified(**⚠️내가 두 번 더 틀렸다**): ⓐ면제 테스트를 **`assert … or True`**로 끝냈다 — assertion이 아니고 무엇에 대고도 통과한다. 세션 내내 *실패할 수 없는 규칙*을 찾아 온 손이 그걸 썼다 ⇒ **면제가 실제로 무언가를 면제하는지** 묻게 고쳤다. ⓑM3(호출부 provider를 리터럴로)이 이 파일에서 초록이라 **또 한 파일에서 읽을 뻔했는데, 전체 스위트에 물으니 이번엔 진짜였다**(2356 passed — 아무것도 안 잡는다): provider를 **인자로 받은 함수가 그걸 무시하고 AWS를 하드코딩해도** 레포가 초록이다(M23과 같은 모양). **내 면제가 만든 탈출구라 내가 닫았다.**
- Verified(**변이 5종 전부 red**): 베이스 선언 제거 · gcp 구현 제거 · **호출부 리터럴화**(닫기 전엔 전체 스위트도 초록) · 스윕 공허화 · 면제 무력화. 복구는 `__pycache__` 삭제 후 확인.
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 여전히 사용자/레포 결정** — 이 증분은 *"켜라"*가 아니라 **"이 도구가 이 레포에서 무엇을 찾는가"의 한 표본**이다 · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.


## 2026-09-01 — 게이트가 안 돈 PR을 "CI 초록"으로 읽었다: 없는 것과 통과한 것이 같은 색이다 (gate 2350)

- Status: 이번 세션이 **직접 밟은** 것을 고쳤다. 권위 `.github/workflows/gate.yml` 트리거 블록 주석 · `tests/test_the_gate_runs_on_every_pull_request.py`.
- Verified(**⛔먼저 오해를 막을 것 — `main`은 무방비였던 적이 없다**): 브랜치 보호가 `check` 컨텍스트를 **요구**하고(`required_status_checks.contexts == ["check"]`), 게이트는 **main 대상 PR에선 언제나 돌았다**. **D43은 계속 성립했다.**
- Verified(**그럼 무엇이 문제였나 — 스택 PR**): `pull_request: branches: [main]` 필터 때문에 **base가 다른 브랜치인 PR엔 이 job이 아예 안 돈다**. PR **#58**(base = M39 브랜치)에서 `gh pr checks`가 *Amazon Q: pass / Vercel: pass / Vercel Preview Comments: pass*를 답했고 **`check` 행이 아예 없었다** — 그걸 "CI 초록"으로 읽었다. ⚠️**없는 것과 통과한 것은 그 목록에서 같아 보이고, 차이는 읽는 사람이 채운다.**
- Verified(**이건 이 레포가 이미 이름 붙인 실패의 한 층 위다**): Risk 12②가 *"skip은 실패가 아니라서 **검사 안 하는 게이트와 통과한 게이트가 같은 색**"*이라 적었다 — 거기선 **건너뛴 테스트**였고 여기선 **안 돈 워크플로**다. 같은 모양, 한 층 위.
- Changed: `pull_request`에서 `branches` 필터 제거 ⇒ **모든 PR이 게이트를 받는다**. CI 몇 분을 더 쓰고 **초록이 어디서나 같은 뜻이 된다**. 이유는 트리거 블록 주석에 적었다.
- Changed(**가드 +4**): 트리거가 존재하는가(공허성) · **base 필터가 없는가**(진짜 고침) · 이유 주석이 `#58`·`Risk 12`를 계속 가리키는가. ⚠️**YAML 1.1은 맨 `on:`을 불리언 `True`로 읽는다** — `wf["on"]`만 본 테스트는 KeyError로 *"트리거가 없다"*를 답했을 것이라 **둘 다** 조회한다(자기가 막는 실패와 같은 모양).
- Verified(**⚠️경계**): **게이트가 병합 조건이라는 것은 이 파일이 주장하지 않는다** — 그건 GitHub 브랜치 보호에 있지 레포에 없다. `test_signature_gate_claims`가 **배선을 앞질러 간 주장**의 표준 사례다. 레포 안에 있는 절반만 묻는다.
- Verified(**변이 4종 전부 red**): `branches` 필터 복귀 · `branches-ignore` 형태 · `pull_request` 트리거 제거 · 이유 주석 삭제.
- Changed(**재개 방지**): `docs/plans/2026-08-08-phase4-scope-and-cost.md`의 4a 절이 아직 **착수 대상**으로 읽혀 *"끝났고 접혔다"* 박스를 얹었다(§10·§11 · M38·M40 · D50 Folded를 가리킨다).
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 사용자/레포 결정**(선행 둘 다 재기 좋다) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

## 2026-09-01 — 셋째 형제는 mypy였다: 정적검사 선행을 재다가 나왔다 (gate 2346)

- Status: `NEXT_PLAN`의 *"정적검사를 게이트에 넣을지"*는 **레포의 결정**이라 묻지 않고 **선행 실측 둘만** 다시 쟀다. 재는 도중에 나왔다. 권위 `docs/evidence/the-third-sibling-was-mypy.log`.
- Verified(**기록은 둘 다 맞았다**): `make lint` **20건**(F841 8·E731 5·E701 5·F402 1·E712 1 · src 7·tests 13, ruff 0.15.10) · mypy **253 errors in 88 files (166 checked)** — 기록 *"253 across 88 of 165"*와 일치(파일이 하나 늘었다).
- Verified(**⚠️그런데 그 253은 그냥은 안 나온다**): `mypy src/`는 `cdk.out`의 **중복 모듈에서 수집 단계에 죽는다** — *"Found 1 error in 1 file (errors prevented further checking)"*. 253을 보려면 `--exclude`를 손으로 붙여야 했다 ⇒ **선언된 설정이 그대로는 실행조차 안 됐다.** `pyproject.toml`은 그 블록을 *"the settings are the target"*이라 적어 뒀는데 **못 돌리는 target은 돌려서 실패하는 target보다 약하다.**
- Verified(**⚠️Risk 12⑥ 재발 — 그것도 그 규칙을 집행하려고 만든 가드 안에서**): 08-30에 pytest↔ruff 비대칭을 고치며 만든 가드의 파일명이 **`..._from_both_tools.py`(both=둘)**였는데 같은 `pyproject.toml`에 **`[tool.mypy]`가 셋째 형제로 있었고 두 경로 중 아무것도 안 적고 있었다**. ⚠️**빠진 쪽이 하필 가장 나쁜 형제였다** — ruff의 실패는 시끄럽고 오락가락(20↔6,527)인데 mypy의 실패는 **총체적**이고(우리 코드를 한 줄도 안 본다) 문장이 *"1 error"*라 **작아 보인다**.
- Changed: `[tool.mypy] exclude` 추가 ⇒ `mypy src/`가 이제 그냥 돈다. 가드는 `..._from_every_tool.py`로 개명하고 **셋 다 순회**. ⚠️**게이트 편입은 바뀐 게 없다** — 선언을 실행 가능하게 만든 것뿐이고 결정은 그대로 레포의 것이다.
- Changed(**가드의 가드 — 변이가 시켜서 만들었다, +3**): 첫 판의 `TOOLS`는 **손으로 적은 dict**라 **M5(=TOOLS에서 mypy 제거)가 초록으로 살아남았다** — **이 파일의 주제가 이 파일에 그대로 일어났다: 세는 일 자체를 아무도 안 세고 있었다**(내 docstring은 *"derived, not listed"*라고 **코드가 안 하는 걸 주장**했다). ⇒ `pyproject`의 `[tool.*]`에서 제외 키를 **유도**해 `TOOLS`와 양방향 대조.
- Verified(**⚠️재는 동안 두 번 더 틀렸다**): ⓐ`mypy src/`가 **252**를 답한 적이 있는데 그건 **증분 캐시**였다(`--no-incremental`·캐시 삭제 둘 다 253) — 하마터면 *"기록이 틀렸다"*고 쓸 뻔했다. **캐시된 답은 측정이 아니다**(Risk 12⑦ `.pyc` 계열). ⓑ**변이를 적용하지 않고 변이를 쟀다** — 정규식이 과도 이스케이프돼 한 건도 안 지웠는데 두 후보의 시간을 쟀고, `diff`로 대조해서야 알았다. **변이 적용부터 확인하고 결과를 읽을 것.**
- Verified(**게이트 비용**): `mypy src/` **49.2s**(게이트 36초의 배)를 `mypy src/stacks/` **0.13s**로 바꿨다 — 결함이 사는 바로 그 자리이고 답이 둘뿐이라 공허하지 않다. 진짜 253은 손으로 재서 `pyproject`에 적었다. **집행 안 하기로 한 숫자를 재느라 게이트를 두 배로 만드는 건 나쁜 거래**(D49가 288s→39s를 얻은 이유).
- Verified(**변이 8종**): M1 mypy exclude 삭제 red(2) · M2 부분 드리프트 red · M3 ruff 삭제 red(3) · M4 pytest 삭제 red · **M5 red(고치기 전엔 초록)** · M6 초록—**설명됨**(위반 0건이라 꺼도 관측 불변; 하중은 M1이 재고 M1이 그 테스트를 죽인다, 귀속 확인) · M7 새 도구가 exclude 선언 red · M8 유도 무력화 red.
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 사용자/레포 결정**(선행 둘 다 이제 재기 좋다) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

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
