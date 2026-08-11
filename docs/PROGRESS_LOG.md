# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-09

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-11 — 맹점을 나머지 전부에 대고 물었다: 결함이 더 넓었다 (gate 1743→1769)

- Status: 어제 남긴 "`capsys` 계열 맹점은 한 건만 봤다"를 소진했다. 훑는 방향을 한 번
  바꾼 게 결정적이었다 — `readouterr` 사용처(5파일 19곳)를 뒤지면 **테스트에 이름조차
  없는 스크립트는 목록에 없다.** `git grep sys.stderr -- scripts/*.py`(11개)로 뒤집으니
  `attach_addon.py`·`preflight_gitops_handoff.py`가 나왔고 **둘 다 깨져 있었다.**
- Verified(재현, 네트워크 0·가짜 kubectl): 파이프로 읽으면 `verify_netpol_enforcement`는
  `probing context:` 한 줄, `verify_tenancy_adoption`은 `context:` 한 줄, 서명 검증기는
  **완전히 빈 출력**에 exit 2. 가장 나쁜 건 netpol — 성공 경로가 stdout에 찍은
  `baseline: … ✓` 뒤에 판정이 stderr로 가서 **독자의 마지막 줄이 ✓**다. **✓로 끝나고 멈춘
  리포트는 끝난 리포트로 읽힌다**, 그리고 그 판정이 `PROVEN_ENFORCING_SUBSTRATES` 승격을
  정한다. ⚠️기존 evidence 로그가 실제로 판정을 잃은 사례는 **없다**(잃을 수 **있었다**).
- Changed(분류가 먼저였다): 11개를 다 고치려다 멈췄다 — `render_tenancy.py`는 **처음부터
  옳다**(stdout=매니페스트, 진단은 전부 `#` 접두로 stderr). 규칙은 "stderr 금지"가 아니라
  **"독자의 스트림이 독자가 필요한 걸 날라야 한다"**이고 독자가 파서면 의무가 **거꾸로** 선다.
  `scripts/*.py` **22개 전수**를 REPORT(17)/DOCUMENT(3)/DUAL(2)로 분류.
- Changed(수정 8건, exit code 전부 유지): verify_netpol/tenant_isolation/tenancy_adoption ·
  verify_image_signature(**스트림이 실패 종류마다 달랐다**) · attach_addon(`--commit` 거부가
  diff 뒤라 **"committed 줄이 없다"가 유일한 실패 신호였다 — 없는 줄은 판정이 아니다**) ·
  watch_cloud_spend(어제 "두었다"를 뒤집었다 — 근거가 파일 사정이지 독자 사정이 아니었다) ·
  push_addon_status(**결과에 따라 스트림을 골랐다** → 한 스트림+`flush`; 같은 로그 안에서
  실패가 먼저·성공이 뭉텅이로 뒤 = **타임라인이 틀린 것**) · preflight(**모드 의존**으로).
- Verified(하중): 변이 **16건 전부 red, 생존 0**. D1~D3은 **거울 방향**(진단을 문서
  스트림에 밀어 넣는 변이)이고, A1은 **미분류 새 스크립트** — 이 훑기를 스냅샷이 아니라
  규칙으로 만드는 지점. `make check`가 낡은 가드 **정확히 3건**을 red로 잡았다(전부
  `.err`에 묻던 것) → `.out`으로. 남은 `.err` 읽기 2곳은 **둘 다 옳다**.
- Verified: `make check` **1769**(+26), 2026-08-11, 로컬 macOS·py3.13.
  증거 `report-streams-swept-across-all-clis.log`.
- Changed(덤) + Verified(같은 실수 재발): CE **요청당 $0.01**(MTD $0.27) · `spend-watch`
  하루 한 번 = 월 **~$0.30**를 프로브·워처 docstring에 명시. 가드 3개 중 하나가 **반증에서
  살아남았다** — **주장**("오늘 줄의 0은 잰 0이 아니다")만 묻고 **지시**("마지막 줄 말고 앞
  며칠을 읽어라")는 안 물었다. 물건은 맞췄고 **물건의 절반만** 물은 것. 고쳐서 둘 다 red.
- Blockers: 없음. ⚠️CI 일치는 **PR에서 확인해야 한다**(로컬 초록만으로는 Risk 12② 미배제).
- Next: `src/`의 로깅 경로는 이 훑기 **밖**이다(대상은 `scripts/` CLI 22개뿐).
  ⚠️`docs/` 3개가 예산 초과(log 138·status 130·plan 127) → `/tidy-docs` 필요.

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
