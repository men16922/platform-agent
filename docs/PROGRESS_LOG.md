# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-13

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
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

