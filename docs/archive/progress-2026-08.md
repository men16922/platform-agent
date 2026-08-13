# PROGRESS_LOG Archive — August 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 8월 이력입니다. 최신이 위.

---

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
