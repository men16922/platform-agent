# COMPLETED_SUMMARY — platform-agent

최종 갱신: 2026-08-15

> 완료된 milestone 압축. current docs 에는 링크만, 상세 체크리스트는 여기로 압축.
> 도메인 원문 상세는 `bin/docs/archive/`.

---

## M0 — Operations 파이프라인 기준선 (완료)

Detector / Analyzer / Decision / Executor 4단계 + Approval Bridge. CloudWatch Alarm → Logs Insights / X-Ray / Bedrock RCA → 런북 선택 → SSM Automation → Slack 리포트 → DynamoDB 기록(90일 TTL). canonical 경로 `src/agents/operations/`, flat import 은 compatibility shim 으로 보존. Step Functions pipeline 과 handler 경로 일치.
상세: `bin/docs/archive/agents.md`, `bin/docs/archive/architecture.md`.

## M1 — Human-in-the-loop 승인 (완료)

P2 severity 흐름에 Slack interactive approval. `WaitForTaskToken` + SQS + approval bridge + Step Functions callback(`SendTaskSuccess`/`SendTaskFailure`). Approve/Reject 버튼으로 파이프라인 재개. 인터랙티브 미설정 환경은 `APPROVAL_DEFAULT_DECISION` 폴백.

## M2 — Harness / handoff 레이어 (완료)

`TaskQueue`(.harness/tasks.json), `ContextStore`(.harness/context.json), `TaskRouter`, `AgentHarness`, client 추상화. `python -m harness.handoff` 로 `.harness/handoff.md` 자동 생성(빈 상태면 워크스페이스 스캔 seed). Claude Code ↔ Codex 툴 전환 컨텍스트 보존.

## M3 — Portability runtime seam (완료)

`NormalizedIncident` cloud-neutral envelope. detector 가 alarm context 와 함께 생성 → analyzer RCA prompt 반영 → decision 이 capability 기반 runbook metadata 를 AWS action 으로 해석 → executor 가 normalized incident 기준 SSM 파라미터 우선 구성.

## M4 — 멀티클라우드/온프렘 scaffold (완료, 런타임 미연결)

provider registry + signal adapters(aws/gcp/azure/onprem) + execution adapters(aws/gcp/azure/onprem). 비-AWS 는 normalized incident / capability mapping 검증용 scaffold + 단위 테스트. 실제 provider API 호출은 NEXT_PLAN P1.

## M5 — Runbook registry bootstrap + override 계약 (완료)

`src/agents/runbooks/catalog.py` built-in capability 기반 catalog(eks-pod-oom / lambda-throttle / rds-cpu-high / kafka-lag-spike / generic-recovery). CDK custom resource 가 `incident-runbooks` 에 seed. decision 은 exact `alarm_name` lookup 실패 시 catalog scan heuristic 으로 재매칭. 코드 fallback ≡ DynamoDB 초기값.
override 계약: `src/agents/runbooks/schema.py`(`validate_runbook`). seed 시 malformed skip+로깅, decision 시 malformed 무시+경고 후 heuristic 폴백.
상세: `bin/docs/archive/agents.md` (런북 스키마 표).

## M6 — CDK deprecation 정리 (완료)

DynamoDB `pointInTimeRecovery` → `pointInTimeRecoverySpecification`. Lambda `logRetention` → 함수별 전용 `logs.LogGroup` 을 `logGroup` 으로 주입. legacy `Custom::LogRetention` 커스텀 리소스 + 부수 IAM Role 제거. `npm run synth` deprecation 13건 → 0건.

## M19 — 런북이 "이 자원엔 안 맞는다"고 선언해 뒀는데 두 provider가 그 줄을 안 읽었다 (완료, 2026-08-15)

**목적**: `NEXT_PLAN`의 열린 항목 **ⓑ**("`renew_certificate`가 GCP/Azure 어댑터에 매핑
없음")를 "기록된 이유를 한 번 돌려 보고 시작할 것"에 따라 시험했다. 시작 전에 **직전
세션의 M18/D47 문서 체크포인트가 커밋 안 된 채** 트리에 있어 먼저 닫았다(PR #33).

**결과 — ⓑ는 틀렸고, 그 옆에 진짜 결함이 있었다**
- **ⓑ는 오기였다(stale 아님)**: 읽지 말고 **돌려서** 재니 **네 provider 전부** 풀린다.
  `git log -L`로 매핑은 **2026-07-09**부터 — 그 기록이 쓰인 08-14 커밋보다 **한 달 앞선다**.
- **#34 결함(고침)**: 티어 2가 런북의 **`resource_types`를 안 읽는다**. AWS는
  `_fits_resource`로 **이미 배제 중**이고, 어긋난 쌍 **67 / 81**이 GCP/Azure에선 그대로
  선택된다. ⚠️**AWS보다 조용하다**: AWS는 하드코딩 액션으로 폴백해 **다른 provider의
  액션**을 넘기지만(시끄럽다), GCP/Azure는 풀리지 않는 capability를 **버리고 짧아진 목록**을
  돌려준다 → `certificate-expiry`가 kubernetes-workload에 선택되고 **RTO 600을 단 채
  notify만 한다**. 규칙은 `runbooks/schema.py::fits_resource` **한 곳**으로(세 provider가
  읽고 AWS는 위임) — **공유되는 게 SDK가 아니라 계약**인 블록이라 복사본을 안 늘렸다.
- **가드 +32**: ground truth를 **함수가 아니라 카탈로그가 선언한 데이터**에 댔다(두 구현이
  똑같이 틀리면 통과하는 가드를 피하려고). 전수 스윕(9타입 × 전 런북 × 2 provider) +
  **역방향 셋**(선언한 타입은 뽑힌다 · unknown은 아무것도 배제 안 한다 · **폴백은 게이팅
  안 된다** — AWS엔 있고 여기엔 없던 짝). 역방향이 없으면 **"전부 배제"가 통과한다**.

**검증**: `make check` **1862 → 1892 → 1894**(+32, 2026-08-15, 로컬 macOS·py3.13;
**CI도 1894 — 숫자 일치**). 변이 **6건 전부 red, 생존 0**, 복구 후 0 modified.

**⚠️ 내가 틀린 것 셋**: **형제 함정 네 번째** — 두 파일에 같은 필터를 넣었는데 **Azure만
import가 되돌아가** 죽어 있었다(GCP만 초록인 걸 보고서야 알았다) · **변이 "생존"을 잘못
읽었다** — **틀린 테스트 파일**에 물었고 실제 가드는 `test_runbook_selectability.py`에
있었다(*"생존"은 어디에 물었는지까지 말할 것*) · **대기 조건이 "출력 파일이 비어 있지
않다"**여서 pytest가 도는 중에 트리를 되돌렸다(*변이·실행·복구는 한 스크립트 안에*).
그리고 **기존 테스트 2건이 red가 됐고 그게 옳았다** — 픽스처가 모든 런북을 **k8s인 척** 물었다.

**⚠️ 남긴 것 — 그리고 건드리면 안 되는 것**: ⓐ(`kafka-lag-spike` 두 dict 불일치)·ⓒ(첫-매치-
승리)는 **정책 사안**. 계약 필드 일곱을 훑어 보니 **`provider`는 AWS 포함 아무도 안 읽는데
빌트인 9개가 전부 `"aws"`**라, 읽기 시작하면 GCP/Azure는 **전부 `generic-recovery`로
떨어진다**(=#30 이전). ⇒ **"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다. 기준은 읽는
쪽의 provider 간 비대칭이다.**

증거 `docs/evidence/resource-types-declared-and-unread.log` · PR #33·#34

## M18 — 가드가 형제 집합 중 **하나만** 순회하고 있었다 (완료, 2026-08-13)

**목적**: 직전 세션이 남긴 Next("`BUILTIN_RUNBOOKS`를 덮는 테스트가 있나")를 그대로 따라간
것이 시작이다. 답은 **"있다, 5개 파일"**이었는데 **전부 dict의 모양만** 물었다(길이·키
집합·deepcopy). **읽는 쪽으로 가니 죽은 코드가 있었다.** 그 뒤 같은 모양이 두 번 더 나왔고,
셋을 묶는 것은 하나다 — **가드가 형제 중 하나만 순회하면 나머지는 안 물어진 채다.**

**결과 — PR 3건, 진짜 결함은 하나**
- **#30 결함(고침)**: GCP/Azure `_select_runbook` **티어 2가 원리상 도달 불가**였다. 같은 12줄이
  **두 파일에 복사**된 채 결함 셋이 겹쳐 있었다 — ①`if not validate_runbook(rb)`(그 함수는
  **문제의 목록**을 돌려주니 빈 리스트=유효 → **유효한 런북마다 skip**) ②`rb.get("steps")`
  (`steps`는 `CAPABILITY_RUNBOOKS` 것) ③`estimated_rto_sec`(계약은 `rto_sec` → **D47**).
  ⚠️**터지지 않는 게 핵심**: actions는 티어 3에서 정상 resolve되니 결정은 채워져 보이고,
  **자기가 따른다고 주장하는 런북과 RTO만** 틀렸다 = **모든 GCP/Azure 인시던트가
  `generic-recovery`**. 기존 커버리지는 `"runbook_id" in result`와 `!= ""` 두 줄로,
  **둘 다 `"generic-recovery"`에 영원히 참**이었다.
- **#31 범위(`src/` 무변경)**: "로깅 문은 DOCUMENT/DUAL을 **안 봤다**"를 시험했더니 **변명이
  참**(다섯 다 WARNING+에 안 닿음 = 고칠 것 없음). **대신 감사가 `for name in REPORT:`**라
  **DOCUMENT의 거울 의무**를 안 물었다 — DOCUMENT CLI가 같은 리다이렉트를 부르면
  `yaml.safe_load_all`이 **ScannerError**로 터진다(실증). 가드 3건.
- **#32 범위(`src/` 무변경)**: capability **17종 × provider 4종** 전수 행렬 — 구멍은 **이미
  알려진 정당한 skip 하나**뿐. **검증(`verify`)이 onprem 한정**인 것은 **기록된 경계**이고
  코드가 정직하다(`verified=None`) → 틀린 건 **이 파일의 무조건 주장 한 줄**이라 한정했다.
  가드 4건(선언처가 **둘**이므로 **양쪽을 읽는지 자체가 ground truth**).

**검증**: `make check` **1825 → 1856 → 1859 → 1862**(+37, 2026-08-13, 로컬 macOS·py3.13;
CI도 세 지점 전부 통과). 변이 **8+5+5 = 18건 전부 red, 생존 0**, 복구 후 diff clean.

**⚠️ 내가 틀린 것 넷 — 전부 증거 로그에 있다**: 변이 하네스의 `restore()`가 `git checkout --`라
**커밋 안 된 고침을 날렸다**(*초록으로 안 돌아오는 복구는 복구가 아니다*) · 새 RTO 가드의
픽스처가 **틀린 기본값과 같은 300**이라 결함을 통과시켰다(*기본값과 같은 값을 고른 픽스처는
가드가 아니다*) · `basicConfig(stream=sys.stdout)`이 **호출 시점의 스트림을 붙잡는** 걸 놓쳐
첫 실증이 헛돌았다(*리다이렉션은 흉내 내지 말고 실제로 걸 것*) · `verify`를 **틀린 해소기**에
물었다. 그리고 **선언처가 둘인데 하나만 본 것 — 그걸 찾으려고 만든 스윕 안에서**.

**남긴 것(정책 판단이라 발명 안 함)**: `kafka-lag-spike`의 두 dict 불일치 ·
`renew_certificate`의 GCP/Azure 어댑터 매핑 부재 · 티어 2의 첫-매치-승리 ·
DUAL의 모드 조건부 리다이렉트(**하중을 못 받는 가드**) · `assert_concurrency_applied`(도달 불가).

증거 `docs/evidence/{gcp-azure-capability-scan-was-unreachable,
report-streams-swept-across-all-clis(15절),verify-capabilities-declared-vs-implemented}.log`

## M17 — 리포트가 독자에게 갈린 채 도착하고 있었다 (완료, 2026-08-10~11)

**목적**: 비용 프로브가 본문을 stdout, 판정을 stderr로 내보내 **파이프에서 세 절이 전부 비어**
있었다(TTY에선 멀쩡 = 저자가 본 것). 고치고 나니 **가드가 못 잡은 이유**가 더 컸다 — `capsys`가
`.out`/`.err`를 갈라 주므로 `.err`에 묻는 테스트는 **독자의 사본이 갈라진 걸 원리상 못 본다**
(STATUS Risk 12④). 그 맹점을 `scripts/` CLI **22개 전수**에 대고 물었다.

**결과**
- **분류가 먼저였다** — "stderr 금지"가 아니라 **"독자의 스트림이 독자가 필요한 걸 날라야
  한다"**이고, 독자가 파서면 의무가 거꾸로 선다. `scripts/*.py` 22개 = **REPORT(17) /
  DOCUMENT(3) / DUAL(2)**, 미분류 신규 스크립트는 red. `render_tenancy.py`는 처음부터 옳았다.
- **수정 9건**(exit code 전부 유지) — verify_netpol/tenant_isolation/tenancy_adoption ·
  verify_image_signature(**스트림이 실패 종류마다 달랐다**) · attach_addon(`--commit` 거부가
  diff 뒤 = **없는 줄이 유일한 실패 신호**) · watch_cloud_spend · push_addon_status(한 스트림
  +flush) · preflight(모드 의존) · **`src/`의 manifest_generator**(인자 없이 리다이렉트하면
  usage가 **유효 YAML 매핑**으로 파일에 앉고 exit 0).
- **덤**: CE **요청당 $0.01** · `spend-watch` 월 **~$0.30** · "당일 줄의 0은 잰 0이 아니다"를
  명시(아무 문서에도 없었다).

**검증**: 변이 **24건 전부 red, 생존 0**(거울 방향 3 · 미분류 스크립트 1 · `src/` 3 포함 —
단 **1건은 처음에 살아남았다**, 아래) · 낡은 가드 정확히 3건이 red로 잡혀 `.out`으로 ·
**실제 서브프로세스 파이프**로 교차 확인(고친 것을 되돌리면 `capsys` 가드와 파이프 가드가
**함께** red) · `verify_netpol_enforcement`는 kind에 **라이브로 돌려** ENFORCED 전문이
stdout에 도착함을 확인. `make check` **1743 → … → 1789**, CI가 **다섯 지점 전부 숫자까지 일치**(#24~#28). 증거
`docs/evidence/{spend-probe-report-split-across-streams,report-streams-swept-across-all-clis}.log`.

**세 번째 문(08-11 추가)**: `src/`는 `sys.stderr` **0건**인데 **로깅 핸들러도 0건**이라
`logger.warning`이 `logging.lastResort`로 **stderr에 나간다** — `print`가 없는 경로라 스트림
훑기로는 **원리상 못 찾는다**. 실제로 `push_addon_status`가 읽기 경로에서
`warn_if_ambient_read`("스포크는 아무 자격증명이나 들고 읽는다")를 그리로 흘리고 있었다.
`main`이 로깅을 stdout으로. 가드는 **서브프로세스**로 돌린다 — 인프로세스면 pytest 핸들러가
`lastResort`를 가려 **버그가 원리상 안 보인다**(`capsys` 맹점의 한 층 아래 판박이).

**넷째 문(08-11 추가) — 잡히지 않은 예외**: "나머지는 클러스터가 필요하다"를 **시험했더니**
넷은 아니었고 **넷 다 깨져 있었다**. `PATH`를 벗기면 트레이스백으로 죽어 stdout 0B·**exit 1**
— `probe_cloud_spend`는 헤딩만 찍고 죽어 08-10의 결함이 다른 문으로 돌아왔고,
`watch_cloud_spend`의 exit 1은 "**새로 과금되기 시작했다**"라 **못 쟀는데 경보를 울린다**.
원인이 정확했다: `_run`은 처음부터 막고 "never raises"라 적었는데 **형제 `_aws`가 안 했다**.

**남긴 경계**: 실제 파이프 뒤 **11 invocation / 9 CLI**(4→8 REPORT는 "클러스터 필요"를 시험한
결과) · 나머지는 라이브 자격증명·기동한 스택이 필요하거나 **강제할 실패 경로가 없다** ·
로깅 문은 **REPORT 4개만** · **`slack_live_approval`은 안 고쳤다**(임포트가 untracked
`cdk.out`에만 있는 경로 + 덮어쓰는 이름 6개 중 4개 부재 → 고치면 **돌아가면서 조용히
아무것도 안 한다**. 올바른 이름은 데모를 Slack에 태워야 안다 → 발명하지 않았다).

## M16 — 비용 관측: 세 클라우드가 다 "안심시키는 0"을 주고 있었다 (완료, 2026-08-09)

**목적**: "AWS 8월 $0"을 두 번 보고했고 둘 다 틀린 뒤(실제 $8.81), **측정 자체를 믿을 수 있게** 만든다.

**같은 실패가 세 번, 매번 다른 얼굴로 — 셋 다 호출은 성공하고 결과도 그럴듯하다:**

| provider | 안심시키는 기본값 | 실제 |
|---|---|---|
| AWS | `aws ce`가 **크레딧 상계** → 순액 ≈$0 | **$8.81** (t3.medium 18일째) |
| Azure | `az consumption usage list`가 **28행 전부 `pretaxCost` null** → 합계 0 | **₩1,989** MTD (7월 ₩22,630) |
| GCP | 프로브에 **provider 자체가 없음** → 잰 0과 구별 불가 | **여전히 못 잼**(비용 API 부재) |

**산출**: `make spend-check`(3 provider, 크레딧 필터·전 리전/구독/프로젝트 스윕) ·
`make spend-watch`(**무엇이 새로** 과금되기 시작했는가 — 임계값 없음) + 셸 훅(하루 한 번) ·
`docs/GCP_BILLING_EXPORT_SETUP.md`(콘솔 5클릭 + 함정) · GCP 예산 ₩20 → **₩28,000** ·
결정 **D44~D46** · 증거 5건(`aws-spend-hand-check-was-zero` · `gcp-budget-always-firing-fixed` ·
`gcp-actual-spend-has-no-api` · `azure-consumption-cli-returns-null-cost` ·
`azure-credit-netting-does-not-apply-yet` · `spend-watch-launchd-blocked-by-tcc`).

**검증**: gate **1699 → 1737**(로컬 macOS·py3.13 **↔ CI 일치**) · 변이 **22건 전부 red, 생존 0**.

**과대 해석 금지**: GCP는 **여전히 못 잰다**(콘솔 토글 하나에 막혀 있다) · Azure 크레딧 상계는
**"지금 없다"지 "없는 성질"이 아니다**(예약을 사면 갈린다) · **터미널을 안 열면 검사도 없다**
(launchd는 TCC로 막힌다) · ACR 월 ~₩6,600은 **다른 프로젝트 것이라 두었다**.

**내가 틀린 것 3건(전부 기록)**: 게이트에서 **라이브 gcloud를 부르는 가드**(21.97s → 0.02s) ·
`mtime` 초 단위에 속아 **정상 동작을 실패로 읽은 테스트** · **CI에 없는 `/bin/zsh`**
— Risk 12②를 **인용해 가며 짠 커밋에서** 그대로 밟았고, CI가 잡았다.

## M15 — 공급망을 0에서 집행까지 + Phase 5 경계 + `main` 보호 (완료, 2026-08-08)

**gate 1617 → 1668 (+51), 커밋 23건.** 하루 전체를 관통한 패턴 하나: **문서에 적힌 이유가
진짜 구속 조건이 아니었다** — 게이트 red(달력) · 서명키(배포 위상) · 보관(데이터 0) ·
Cosign(서명 자체가 없음) · 어드미션(cosign 버전).

- **승인 3건을 쟀다** — ①실 DynamoDB 왕복 **통과**(`confidence`가 `Decimal`로 왕복 = 문자열이면
  화면만 영원히 "n/a", float면 boto3 예외가 `except`에 잡혀 **행 전체 소실**. 목으로는 원리상
  못 잡는다) ②GCP/Azure 보관은 **질문이 틀렸다**(스토어가 아예 없어 **지울 데이터 0** → 승인이
  아니라 프로비저닝 선행 = Phase 4) ③Cosign만 진짜 승인이었다.
- **공급망 0 → 집행**: 서명 생산자(`make sign-image`) → 배포 직전 **소비자**(`image_trust`,
  exit 2도 거부) → **CI**(`gate.yml`) → **키리스**(Fulcio 단명 인증서 = **custody의 답**).
  CI가 첫날 세 건을 잡았고 셋 다 진짜 결함(임의로 넓힌 lint · **미선언 OTel exporter** ·
  **미검증 `>=3.11`**). **어드미션은 업스트림 대기** — cosign v3 서명을 policy-controller가
  v0.15.1로도 못 읽고, v2로 서명하면 통과함을 **양방향 실증**했다.
- **서명키 rotation**(D42 TTL이 겹침 창을 유한하게) · **테스트 시효**(소스 무변경 red) ·
  **레포 원고 동기화**(원고의 "다음 단계" 3건이 이미 사실이 아니었다).
- **Phase 5 = 경계까지**: UI가 아니라 **"PR은 그 테넌트 파일 하나만 건드린다"**를 세웠다 —
  Phase 0부터 헤더에 적혀 있었지만 **반증할 수단이 0**이던 문장. 텍스트로 편집·의미로 검증.
- **`main` 보호 = 집행 확인**(D43) · **TS 닫힌 섬 제거**(인가 규칙의 **두 번째 진실 공급원**).
- **교훈 3종**: 게이트 숫자는 **날짜 없이는 주장이 아니다**· 게이트가 **말해지지 않은 환경** 위에서
  통과하고 있었다 · **행복 경로만 태운 가드는 하중을 받지 않는다**(전부 → Risk 12 — 안전망을 통째로 지워도 14개가 초록이었다). 그리고 **내 가드가 네 번 틀렸다**.
- 상세 → `PROGRESS_LOG` / `docs/archive/progress-2026-08.md` / `docs/evidence/*` / D43.

## M14 — 열린 결정 6건 전부 닫힘 (완료, 2026-07-29~08-02)

**gate 1565 → 1617 (+52).** 열려 있던 결정을 전부 닫았고(마지막 하나는 조사 중 새로 열려
같은 세션에 닫혔다), **여섯 번 다 조사가 질문을 바꿨다** — 어느 것도 "선택지 중 하나를
고르는" 일이 아니었다.

- **D36**(결정 1) — 배포는 테넌트 소유가 아니다. 한 개인 줄 알았던 게 **셋**(귀속·인가·과금)이었고
  과금은 결정이 아니라 **구조 대기**였다. 무파티션 + 테넌트별 모델 rate limit 안 함 확정.
- **D38**(결정 5) — **두 경로가 반대 방향으로 고장**이었다: 인시던트는 게이트가 옳은데 **생산자가
  테스트뿐**이라 열 수 없었고, 배포는 **가드 없이 cluster-admin**이었다. A(스코프 생산자)+B(배포
  신원 축소) 둘 다 실행, **둘 다 옵트인**(→ `STATUS` Risk 3).
- **D39**(결정 2) — 예외를 붙잡던 **근거가 사실이 아니었다**. `src/`에 `MCPServer` 생성자가 0이라
  무스코프 경로를 실행하던 유일한 코드는 **그것을 고정하던 테스트**였다. 읽기도 기본 거부.
- **D40**(결정 4) — **막는 게 하나가 아니었다**(넷). 기록된 하나는 가장 먼저 걸리지도 않았고,
  그 아래 **순환 게이트**가 있었다: 승격 도구가 proven 집합을 전제해 **새 기판을 승격시킬 수 없다**.
  k3s는 넣지 않음(재개 조건: k3s-lab에 실제 워크로드).
- **D41**(결정 3) — **선택지가 둘이 아니라 셋**이었고 셋째는 **같은 증거 로그 40행 위**에 있었다
  (형제 필드 `networkPolicies`는 이미 객체 직접 렌더). Capsule 폐기 경고 2→**0**.
- **D42**(결정 6, Phase 5를 재다가 열렸다) — `nonce`가 one-time-use라고 **적혀만 있었다**:
  `_spent`가 인스턴스 상태인데 프로덕션이 브로커를 매번 새로 만들어 **3/3 발급**됐고, **수호
  테스트가 broker 하나를 잡아 유일한 성립 조건을 제공**했다. 진짜 1회용은 **틀린 수정**이었다
  (실행기가 같은 인시던트로 두 번 해석). **TTL로 대체** — 약속이 줄었고 대신 지켜진다.
- **부수(결정 아님)** — `2차 잔여`의 "push 인증"은 **일주일째 스테일**이었고(07-26 완료),
  그 자리의 진짜 구멍은 **스포크의 읽기 신원**이었다: 맨 kubectl + 공유 `argocd` ns라 테넌트
  구분이 **코드 필터**다. 쓰기는 허브가 401로 막는다(라이브 4종).

**교훈**: 예외의 근거는 **코드로**, 게이트의 근거는 **측정으로** 확인하라 · **질문이 주는
선택지·블로커 개수를 세지 말 것**(두 번 다 답이 이미 레포 안에 있었다) · **없는 것은 테스트에서
영원히 초록이다** · 가드는 **파생**시켜라(열거하면 새 경계를 놓친다) · **폐기됐다고 사문화된 건
아니다** · 가드는 **자기 상태가 살아남는 수명에서만** 집행된다 · **계획 문서도 측정 대상이다**
(닫힌 항목이 열린 채면 다음 사람은 이미 된 일을 하거나 그 옆의 진짜 구멍을 못 본다) ·
**픽스처도 측정하라**(필드명 하나 틀린 픽스처가 오탐을 만들었다).

**새 가드 5종** — 전부 반증을 개별로 확인했다: `test_carveout_consumers_exist.py`(D39, 예외의
근거로 인용된 소비자가 실재하는가) · `test_substrate_promotion_reachable.py`(D40, 멤버십 주장이
현재 레지스트리로 반증 가능한가) · 파생 LimitRange 가드(D41, 쿼터가 `limits.`를 선언하면 그
렌더의 **모든** 네임스페이스가 기본값을 가져야 한다) · `test_scope_replay_reachability.py`(D42,
**프로덕션 함수로** 단언 — 재사용이 실제로 거부되기 시작하면 일부러 red) ·
`test_push_read_identity.py`(읽기가 ambient임을 프로세스가 말하는가).
증거 `docs/evidence/{unscoped-mcp-read-closed,deploy-identity-reduction,scope-producer-live,
k3s-netpol-enforcement,capsule-limitranges-direct,approval-ttl-replay-bound,
push-identity-ambient}.log`, 조사 `docs/plans/2026-07-29~2026-08-02-*`.

## M13 — "선언됐지만 아무도 읽지 않는 것들" 14건 (완료, 2026-07-28~30)

**gate 1411 → 1565 (+154).** 증거 `docs/evidence/{phase3-tenant-grant-validation,
runbook-selectability,capsule-deprecation-metadata,executor-span-approval-path,
onprem-runbook-matching,declared-unconsumed-sweep,incident-trigger-time,
cloud-incident-fields,incident-time-to-resolve,rollback-cost-metrics,
activity-read-model-drift,report-windows,deployment-environment-absence,
deployment-namespace-provenance}.log`.
결정 → `DECISIONS` D33·D34·D35.

Phase 3가 인가를 닫은 뒤 남은 잔여를 우선순위대로 소진했는데, **아홉 건이 전부 같은
결함**이었다: 필드나 계획이 **선언되고, 채워지고, 저장되고, 아무도 읽지 않는다.** 테스트는
아홉 번 다 초록이었다 — 전부 *생산자*를 단언했기 때문이다. 아홉 번 다 **라이브 실행만이**
드러냈고, 그중 네 번은 유닛 테스트가 통과하는 동안 라이브가 다른 답을 냈다.

그 뒤 같은 축의 **변형 두 건**이 더 나왔고, 둘 다 스윕을 **새 방향으로 넓혀서** 찾았다:
**⑩반대 방향**("읽는데 아무도 안 씀" — 생산자 셋 중 하나만 침묵) · **⑪한 층 위**(필드가
아니라 **선언 자체를 아무도 안 읽음** — importer 0인 스키마 문서가 양방향으로 드리프트).

- **grant 대조(1425)**: 기록은 "대조 안 함"이었지만 grant를 **줄 방법 자체가 없었고**(읽기 쪽이
  아무 쓰기 경로도 만들 수 없는 필드를 소비 중) 역할 변경이 whole-item Put으로 grant를 지웠다.
  허브 로스터(못 읽으면 **503**, 회수만 예외) + 저장 전 대조 → D33.
- **런북 선택성(1445)·티어(1470)**: 런북 4개가 BUILTIN에 없어 선택 불가 → 넣었더니 라이브는
  여전히 generic-recovery. 시드 테이블의 generic 행이 티어 4의 답을 대신 내서 **빌트인 티어가
  배포 환경에서 한 번도 도달된 적 없었다**(D34). 고쳤더니 이번엔 **더 나쁜 매칭**이 이겼다 —
  1점짜리 시드 행이 3점짜리 빌트인을 눌렀다(D35, 합집합 휴리스틱).
- **온프렘 매칭(1470)**: `reason`이 `metric_name`의 **복사본**이라 매처가
  "availability availability…"를 읽었고, `resource_types`는 모든 런북에 선언돼 있고 **미소비**라
  엉뚱한 런북이 걸려도 하드코딩 AWS 액션으로 조용히 폴백했다.
- **Capsule metadata(1446)**: `additionalMetadata`는 제거 릴리스에서 **에러 없이 안 읽히는**
  쪽으로 실패할 필드라 선제 이관(라이브에서 probe 라벨 전파로 반증).
- **executor span(1454)**: 웹훅이 루트 span을 닫은 뒤 실행해 **AUTO·승인 양쪽 다 무추적**.
  승인은 부모가 아니라 **링크** — 사이 간격이 사람의 고민 시간이라 접으면 지연 수치가 무의미해진다.
- **severity_hint(1479)**: 우연을 그만두려 **계통 스윕**(437 필드 → 20 후보). 네 어댑터가 전부
  채우는데 아무도 안 읽어, 사람이 **미리** 내린 분류가 버려지고 **AUTO/APPROVE를 정하는 축**이
  산문에서만 추론됐다. 라이브 A/B: warning이 자동실행 → 승인대기로.
- **인시던트 발생 시각(1491·1496)**: 행이 "우리가 쓴 시각"만 알아 탐지 소요시간이 산출 불가.
  온프렘·클라우드 양쪽 + `detected +Nm` 배지(**읽는 쪽 없이 저장만 하면 같은 결함을 하나 더
  만드는 것**). 클라우드 `confidence`는 float라 그냥 넣었으면 boto3 예외가 기록기의 `except`에
  잡혀 **레코드 전체가 사라졌을** 것 → `Decimal`.
- **time-to-resolve(1520)**: 이 부류의 **가장 비싼 변종** — 앞의 여덟은 값이 *버려졌지만*
  이번엔 값이 **있는 척했다.** `resolved_at`이 `created_at`의 복사본이라 주간 온콜 리포트가
  **존재 내내 "MTTR 0.0분"을 자신 있게 발송**했다(fetch가 한 키를 `started_at`·`resolved_at`
  양쪽 끝에 넣었다). 부재는 눈에 띄지만 **그럴듯한 기본값은 안 띈다.** 같이 나온 둘:
  `runbook_id`에 `alarm_name` 복사 → 재발 패턴 그룹핑 붕괴 · 대시보드 Scan 투영이 **자기
  리더가 읽는 4필드**를 안 불러 전날 수정이 배지 한 층 앞에서 멈춰 있었다.
  실측 0.0→45.0, 라이브 P1/AUTO 1502초 보존·열린 인시던트는 부재.
- **롤백 비용 패널(1528)**: 이 부류가 **반대 방향으로도** 열린 첫 사례 — 읽는 쪽은 멀쩡한데
  ACTIVITY를 쓰는 셋 중 `record_rollback`만 `cost_metrics`를 빠뜨렸다. 그 자체론 과소보고인데,
  reader `mergeActivity`가 **trace만 합집합**으로 두고 나머지를 `{...latest}`로 최신 행에서
  가져가 **롤백되는 순간 도구/추론/토큰 수가 페이지에서 사라졌다**(패널이 조건부라 예외도
  "0"도 없이, 바로 아래 트레이스는 오히려 길어진 채). 라이브 BEFORE 미렌더 → AFTER
  `tool calls 5 · tokens 920`, 내역이 두 실행에 걸침. **절반씩은 각각 방어 가능한데 겹칠
  때만 터진다** · 생산자가 여럿이면 **하나만 침묵해도** 나머지가 정상을 계속 증명해준다.
- **읽기 모델 문서 드리프트(1533)**: 한 층 위 — 필드가 아니라 **선언 자체를 아무도 안 읽는**
  경우. `activity-model.ts`는 **importer가 0**이라 어긋나도 안 깨졌고, 아무도 안 쓰는
  `duration_ms`를 선언하면서 상세 페이지가 딛고 선 `trace`·`cost_metrics`·`deployment_id`는
  빠뜨렸다. 거짓 주장 둘(**`ttl` "30일 보관"인데 주 writer가 안 써서 만료 안 됨** · `GSI1`은
  절반만 채워지고 무쿼리라 그대로 짰으면 **조용히 짧은 목록**). 지키던 테스트가 **부분문자열
  존재만** 봤다 — 이 마일스톤이 적어둔 안티패턴이 **그 파일의 수호 테스트에** 있었다.
- **리포트 창(1544)**: 위 건이 연 TTL 실마리를 따라가 나왔다 — `ttl`("쓴 시각+90일")을 두
  리포트가 **시각처럼** 읽었다. 일일 SLO 필터 `ttl >= now-24h`는 만료 안 된 모든 행에 참이라
  **24시간 창이 보관 기간 전체**였고(90행 중 90 → 2), 주간은 `ttl-90일` 역산이라 상수가 바뀌면
  조용히 밀리고 **`ttl` 없는 행은 90일 과거로 떨어져 늘 누락**됐다. `created_at`으로 배치 +
  폴백 상수를 **writer AST에서 파생 검증**. **라이브 미실행**(스케줄 Lambda) — 과대집계는 추론.
- **배포 tier 발명(1552, D36)**: 이 부류의 **양층 변종** — 대시보드 NL 배포가 `environment`를
  안 보내는데 **HTTP 경계가 `"dev"`를, 매퍼가 같은 부재를 `"production"`을** 채웠다. 한 미상값에
  두 층이 서로 다른 답을 자신 있게 발명한 것. 부재를 끝까지 보존. **내 가드가 잡으려던 홀을
  자기가 갖고 있었다** — 조건부 저장(`item["k"]=v`)을 dict 리터럴 walker가 못 봐서, 그대로
  뒀으면 가드가 **버그 쪽을 편들었을** 것이다(무조건/조건부 분리로 수정).
- **배포 네임스페이스 출처(1565)**: 위 건과 **같은 축의 반대 면** — 티어는 미상이라 발명이
  틀렸고, 네임스페이스는 **실행기가 알고 있었는데 안 적었다**(`--namespace`를 정한 게 자기고
  어댑터가 돌려주기까지 했다). 그래서 하류 **네 층이 각자 `"default"`를** 채웠다: 롤백 버튼 ·
  Next 라우트 · `RollbackRequest` · 그리고 `ServiceSpec`(유일하게 정당한 곳). **라이브 kind
  3노드**: 같은 이름이 두 ns에 있으면 `rollout undo -n default`는 **실패하지 않는다** — 찾아서
  되돌리고 **성공을 보고한다, 엉뚱한 쪽을**(BEFORE default 1.28→1.27, 대상은 1.28 그대로 =
  운영자가 누른 그 서비스 / AFTER 실 배포→실 행→실 HTTP 롤백→대상만, default 무변). 승계도
  이어받게 했다 — 사라지는 게 **다음 롤백의 조준값**이라 한 번의 롤백이 다음 것을 위해
  **버그를 재장전**한다(`cost_metrics` 교훈의 날 선 판본). 그리고 **D36이 세 번째·네 번째
  경계에서 살아 있었다**: D36 가드가 두 경계를 **열거**해 롤백·트리거 라우트의
  `environment = "production"`이 남아 있었고, 파생 스윕으로 바꾸니 즉시 나왔다(교훈 ⑤의 실증).

**반복된 교훈(테스트 규율 7종)**: ①가드를 쓰면 **호출부에서** 반증하라 — 새 테스트 20건이
전부 통과하는데 호출자만 플래그를 잊은 상태였다. ②픽스처는 코드가 아니라 **실제 입력**에서
가져와라 — 내가 쓴 summary에 런북 키워드를 심어놔 유닛은 초록인데 라이브는 계속 틀렸다.
③**소비자를 단언하라, 생산자 말고** — `severity_hint`를 "설정되는가"로 봤다면 그 필드가 존재한
내내 통과했을 것이고, 그게 이 부류가 여태 살아남은 방식이다. ④**투영/스키마 계층도 소비자다**
— `ProjectionExpression`이 부르지 않은 속성은 리더가 아무리 방어적으로 짜여도 복구할 수 없다.
⑤**가드는 파생시켜라, 열거하지 말고** — 매퍼가 읽는 속성을 파싱해 Scan에 요구하면 *다음*
필드에도 실패한다. 손으로 적은 목록이었다면 당시 투영에 맞춰 쓰였을 테고 그대로 통과했다.
⑥**생산자가 여럿이면 다수결이 결함을 가린다** — 셋 중 하나만 침묵하면 나머지 둘이 그 필드가
정상이라고 계속 증명해준다. 열 번째 건은 그래서 ③(소비자를 단언하라)으로도 안 잡혔다:
소비자는 멀쩡했다. ⑦**수호 테스트 자신이 안티패턴일 수 있다** — 열한 번째 건에서 파일을
지키던 테스트가 `'GSI1PK:' in content` 식 **부분문자열 존재**만 봤다. 키워드는 모양을 못 보므로
그 파일이 얼마나 어긋나든 초록이었다. **덧붙여 내가 새로 쓴 가드도 처음엔 같은 병이었다**:
두 곳에 선언된 필드를 `re.search`로 봐서 **한 곳만 옵셔널이면 통과**했다 — `any`를 쓸 자리에
`all`이 필요했고, 반증을 돌리지 않았으면 그대로 뒀을 것이다.
스윕은 두 방향 모두 반복 가능하게 남겼다(후보≠결함) —
`scripts/find_unconsumed_fields.py`(선언됐는데 안 읽힘) ·
`scripts/find_unwritten_keys.py`(읽는데 생산자 없음).

## M12 — 멀티테넌트 Phase 3(인가 강화) 완결 + 읽기 경계 (완료, 2026-07-27~28)

**gate 1290 → 1411.** 증거 `docs/evidence/phase3-*.log` · `mcp-gateway-scope.log`.
결정 → `DECISIONS` D31·D32.

Phase 2가 "테넌트 하나의 잘못이 이웃에게 안 번지게"를 클러스터 안에서 증명했다면,
Phase 3는 **누가 무엇을 할 수 있고 볼 수 있는가**를 닫았다. 그리고 이 단계에서 나온
결함은 거의 전부 **앞문은 잠갔는데 옆문이 열려 있던** 형태였다.

- **①자격증명 격리 full**: fail-closed 가드를 `guard_scoped_action` 하나로 모으고 세 러너가
  그것을 부른다(닮은꼴 금지). `resolve_incident_scope` 이관으로 **GCP Cloud Workflows 경로의
  스코프 부재** 해소 — 디스패치 경로가 둘인데 로직이 한쪽에만 있었다. 라이브가 Phase 1a
  증명 자체의 구멍을 적발: `render_rbac`가 바인딩 대상 **ServiceAccount를 렌더하지 않아**
  RoleBinding이 없는 신원을 가리키고 있었다(fail-closed라 안 드러남 → RBAC 팔이 한 번도
  행사된 적 없음). DoD가 "Forbidden **또는** 자격증명 부재"라 약한 쪽으로 통과 중이었다.
- **②reconciler 충돌 거부**: `rollout undo`는 0을 반환하고 `resolved=True`가 기록된 뒤
  깨진 버전이 돌아온다 — out-of-band 변경이 **10초 만에** selfHeal에 되돌려짐을 먼저 실증한
  위에서 거부를 세웠다. 되돌리는 액션만 막는다(restart·scale은 desired로 수렴).
  **selfHeal pause는 채택 안 함**: Application이 `argocd` ns에 있어 테넌트 스코프
  자격증명으로 도달 불가(D32). 설계의 권장안(registry write-back)은 Phase 5 의존 —
  계획 자체의 순서 충돌.
- **③읽기 쪽 테넌트 경계**: `visibility.ts` 단일 seam(플릿 + 인시던트). 인시던트 파티션이
  막혀 있던 원인은 읽기가 아니라 **쓰기**였다 — `NormalizedIncident.tenant`가 Phase 1a부터
  있는데 기록 시점에 버려졌다. 기록 없는 행은 admin 전용, `withheld` 카운트 반환,
  캐시 `public, s-maxage` → **`private, no-store`**.
- **MCP 게이트웨이 옆문**: 모든 도구가 맨 `kubectl`을 쐈고 `kubectl_apply`는 임의 매니페스트를
  임의 ns에 썼다. Phase 1a가 executor에서 없앤 fail-open이 그대로 있었다. argv를 스코프
  kubeconfig로 고정(ContextVar — 도구 인자로 두면 **호출자가 자기 자격증명을 지명**한다),
  변경 도구는 fail-closed. 라이브: 스코프 안 ns인데도 `secrets`는 **API 서버**가 `Forbidden`.
- **테넌트 call budget**: 쿼터는 무엇을 *보유*하는지만 묶었다. sliding window, 레지스트리
  `quota.calls_per_min` 선언, 미선언=무제한(additive).
- **외부 대조**(Qwiklabs GENAI120 · GCP Architecture Center · Developers Blog): Agent Card가
  **가상 주소**와 **집행하지 않는 인증**을 광고하던 것 적발·수정. → `docs/reference/`.

**반복된 교훈**: 이 단계의 결함은 전부 **테스트가 선언을 단언해서** 살아남았다
(`assert "supportedInterfaces" in card` · `ROUTE_PROTECTION` 존재 단언 ·
"Read path remains public" 문구 고정). 값이 어디를 가리키는지, 누가 그것을 소비하는지를
묻지 않는 가드는 정책보다 오래 산다. 그리고 **가드를 쓰면 가드도 반증해야 한다** —
rate-limit 테스트 하나가 결함을 주입해도 통과했다(재시도를 시계 멈춘 순간에 해서
아무것도 단언하지 않고 있었다).

## M11 — 멀티테넌트 Phase 2 완결 (완료, 2026-07-26)

**gate 1191 → 1290.** 증거 `docs/evidence/phase2-*.log`. 설계 →
`docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5).

소프트 티어가 선언에서 **실측된 격리**가 됐다. 목적은 테넌트 하나의 잘못이 이웃에게
번지지 않게 하는 것이고, 이번 단계에서 그 경계가 네임스페이스·쿼터·데이터플레인·자격증명
네 층에서 각각 라이브로 증명됐다.

- **tenancy + Capsule**: 레지스트리가 Namespace(tenant/env/capability + PSS 라벨)·Capsule
  Tenant(`scope: Tenant` 합산 쿼터)·네임스페이스 스코프 RBAC를 렌더. 쿼터 합산은 정지
  조회로는 4배 버그로 보이고 **소비 실험만이 사실을 말한다**(`limited: 6` = 16−10).
- **⑥ 데이터플레인 격리**: 손수 관리하던 차트(데카르트 곱 16 vs 구독 6, 설치 주체 없음)를
  폐기하고 네임스페이스와 **같은 호출**에서 렌더 → 두 집합이 구성상 동일. 집행이 실험으로
  증명된 기판에만 렌더. 라이브 4종(same 통과·cross 차단·kubelet 프로브 생존·DNS 무영향).
- **push 2축 수집기 + 대시보드 스위처**: 허브는 스포크 read 자격증명 0, 신원=서명을 검증한
  키, 침묵은 UNKNOWN 강등. UI가 허브 불가/미푸시/침묵을 구분한다.
- **capability scope 축**: 클러스터 싱글턴을 테넌트별로 렌더하면 컨트롤러 둘이 같은 객체를
  조정한다(라이브에서 발생). 거부 가드는 어댑터가 아니라 **계약**에 둔다.
- **삭제 cascade + values seam**: 삭제 의미를 계약이 말하게 하고(엔진 기본값이 정반대),
  values는 복사하지 않고 가리킨다. 라이브가 **PSS restricted가 우리 애드온을 거부**
  (Argo는 Synced인데 파드 0개)하고 **구독 해지가 데이터를 파괴**(차트가 k8s 기본값을 뒤집음)
  하는 것을 잡아 둘 다 근본수정.
- **managed 경로 + DR**: faked 디스크립터로 과금 없이 `applicable=false` 증명(조회 안 한
  백엔드에 health를 단언하지 않는다). globex/dev를 실제 파괴 후 레지스트리만으로 재구축 —
  라벨 완전 동일, 채택 검증기 신설(`verify_tenancy_adoption.py`).

**반복된 교훈**: 라이브가 잡은 결함 대부분은 "테스트는 초록인데 아무 효과가 없는 코드"와
"정지 조회가 거짓말하는 상태"였다. 그리고 검증기 자신이 거짓 초록/거짓 경보를 낸 사례가
세 번 있었다(`dns-suffix`가 질의를 안 보냄 · 다른 클러스터를 broken으로 보고 · scope 누락을
fail-closed로 올려 게이트 27개 파손).

## M10 — GitAIOps 대조 7/7 + 멀티테넌트 Phase 0·1a·1b + 공급망 하드닝 (완료, 2026-07-20~26)

**gate 870 → 1191.** 상세 이력 → `PROGRESS_LOG.md`(최신 3–5건) · `docs/archive/progress-2026-07.md` ·
증거 `docs/evidence/*`. 설계 → `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5, S 93.5).

- **On-Prem 애드온 스택 IaC** Phase 1~5(ArgoCD GitOps · kube-prometheus-stack · Argo Rollouts ·
  Loki/Fluent Bit) + k3s 기판 패리티. Gateway API는 소비처 부재로 의도적 보류.
- **GitAIOps 실습서 대조 7/7**: ①Rollouts AnalysisTemplate + **에이전트 릴리스 게이트 3종 판별**
  (정상→pass / 크래시→165s auto-abort / 관측 불가→unknown) · ②OTel→Tempo + 인시던트 딥링크
  (MTTR의 82%가 로컬 LLM 추론) · ③런북 사후검증 provider 실행부 · ④권한 통제 3단 ·
  ⑤Sync Wave(Phase 1b 흡수) · ⑥NetworkPolicy 집행 + **PSS restricted · Cosign** ·
  ⑦고아 클러스터 스위퍼 + **CronJob·coverage 정직성**.
- **멀티테넌트 플랫폼**: Phase 0(레지스트리·로더·`DeliveryAdapter` 계약) · Phase 1a(자격증명이 경계 —
  `IncidentScope` + provenance 바인딩 `TokenBroker`, 라이브 RBAC `Forbidden`으로 증명) ·
  Phase 1b(argocd/flux 어댑터 2개 + 핸드오프 프리플라이트 5검사 + **rollouts-demo 소유권 TF→ArgoCD 이관 실행**).
- **런북이 선언대로 실행됨**: capability step(순서·조건·on_failure·per-step verify)을 executor가 실제 소비.
  ⚠️**단 `verify`가 실제로 도는 건 onprem뿐이다**(`executor.py:221` `if provider == "onprem"`) —
  AWS/GCP/Azure는 계획에 싣고 실행하지 않으며, 그래서 `verified`를 True가 아니라 **None(unknown)**
  으로 정직하게 보고한다(코드가 명시·가드도 있음). 2026-08-13에 **잰 것**이고, 그 전까지 이
  줄은 무조건이었다 — "과대 해석 금지"는 완료 요약에도 걸린다.

**이 마일스톤에서 반복해 나온 결함 형태 — 전부 "선언은 됐는데 소비/전달이 없음":**
`llm.endpoint`(차트에 있는데 webhook이 못 받음 → 모든 판정 unknown) · `capability_schema.steps`
(스키마에 있는데 executor가 안 읽음) · `_deserialise_decision`(steps를 직렬화 경계에서 버림) ·
`CAPABILITY_RUNBOOKS`(9런북이 죽은 데이터) · `scripts/`(이미지에 미포함) · 스위퍼 `_run_json`
(CLI 부재를 clean으로) · DynamoDB `Decimal`(rto 선언 런북 전량 탈락).
**공통점: 테스트는 선언을 검증해 초록이었고, 라이브 실행이 소비 부재를 드러냈다.**

## M9 — eval·하드닝 스프린트 + 라이브 E2E 2종: 자율 백로그 전면 소진 (완료, 2026-07-19)

**목적:** Google 생태계·cwc-workshops 대조 후속(①~⑦)과 승인된 실행 큐 8건(⑧⑨ 잔여+⑦ 라이브)을 소진하고, 남은 사용자 게이트 2종(OAuth 배포 클릭·Slack App)을 라이브 E2E로 완주. gate 748→847, spend ~$0.
**산출:** (a) **eval 하네스 시리즈(④⑤⑥)** — `eval_harness.py`(injectable Router/Judge·결정론 백스톱)→멀티-grader 스코어카드(PASS_SLOW·action-sink·Scorecard.delta)→데이터셋 20케이스+adversarial 5·judge 반-관대(calibration_probe); 라우팅 갭 4건 발견→`classify_request` precedence 재설계→회귀 가드. (b) **모델 스윕(⑦)** `model_sweep.py`+라이브 160콜(M8 참조). (c) **A2A/SSE/메모리 하드닝(⑧⑨ 8건)** — sanitize·최소권한 힌트·구조화 디스크립터·저-confidence 게이트·SSE id/ready/heartbeat·`memory_tier.py`(distill/recall/consolidate), 전부 옵트인·비파괴. (d) **OAuth 배포 클릭 E2E**(07-18) + **Slack 인터랙티브 승인 E2E**(07-19) — 이 라이브들이 프로덕션 버그 7건 표면화→전부 근본수정(`.vercelignore` 404·OIDC provider 삭제 복구·smoke_tester base_url·detector NameError·approval_bridge float→Decimal·Bedrock 무효 모델 ID·유령 SSM 문서→D17 in-process 알림).
**검증:** `make check` 847 passed. 라이브 증거 `docs/evidence/{oauth-deploy-trigger-live,slack-interactive-approval-live}.log`, SFN SUCCEEDED 3회·DynamoDB APPROVED/resolved 확증, 실 LLM 심각도 P1/P2/P3 3단 관측. 상세 이력: `docs/archive/progress-2026-07.md`·`status-baseline-2026-07.md`.

## M8 — 프로덕션 패키징 + State Store: AWSome 레퍼런스 8/8 완결 (완료, 2026-07-17)

**목적:** 레퍼런스 잔여 #7(Helm/Terraform)과 로드맵 ④(State Store/Alertmanager)를 닫아 AWSome AI Gateway 레퍼런스 전 항목(Tier 1 4종 + Tier 2 3종 + #7)을 소화. gate 822→842(+20 test), 커밋 9개 전부 origin/main, 클라우드 spend $0.
**산출:** (a) **⑦ 라이브 모델 스윕**(로컬 MLX 160콜) — `_classify_prompt` teardown/진단동사 결함 발견→수정→가드, 증거 기반 선택 **7B@temp0=20/20**(30B 반증). (b) **#7-a Helm 차트** `infra/helm/platform-agent/` + 이미지 `infra/onprem/Dockerfile`(kubectl 내장) — 최소권한 RBAC(4조치 동사 열거·drain 별도 게이트)·strict/lenient 프로브 분리·env×substrate values. (c) **④ SQL State Store** `state_store.py`(`PLATFORM_STATE_DSN` 옵트인, 미설정=JSONL 무변경) + 차트 `stateStore` values(secretKeyRef 우선, DSN 모드=RollingUpdate·replicas>1 해금). (d) **#7-b Terraform** `infra/terraform/aws-production/`(VPC/EKS 1.31/**Aurora Serverless v2 `platform_state`**=DSN seam 정합/IRSA 정확-ARN grant; Redis·Cognito=미소비 제외). (e) 부산물 버그 2건: pyproject optional-deps PEP 621 위반(이미지 빌드가 표면화)·이미지 psycopg2 누락.
**검증:** 라이브 4건 — kind 실 install(RBAC can-i allow/deny·P2 승인 루프·PVC 영속), **실 Alertmanager→멀티-레플리카 상태 공유**(docker PG, replica-2 승인→replica-1 즉시 반영), k3s substrate(기존 k8s-lab VM, `local-path` Bound), terraform init+validate. 증거 `docs/evidence/{model-sweep-live,helm-kind-live-install,state-store-alertmanager-live,helm-k3s-substrate-smoke}.log`. 가드 테스트 +20(helm/terraform/state/sweep). 잔여=사용자 게이트만(terraform apply·아티클·OAuth·Slack).

## M7 — 문서·컨텍스트 하네스 이식 (완료, 2026-06-11)

harness.md 기반으로 `harness/CORE_MANDATES.md` + `CONTEXT_BRIDGE.md`, `docs/` current-doc 체계, `.claude/skills/{sync,checkpoint,tidy-docs}` 구축. 기존 도메인 문서는 `bin/docs/archive/` 로 이관.
