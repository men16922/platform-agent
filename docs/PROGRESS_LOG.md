# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-13

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-13 — 같은 변명을 세 번째로 시험했다. 이번엔 참이었고, 대신 가드가 반쪽이었다 (gate 1856→1859)

- Status: `PROGRESS_LOG`가 남긴 마지막 줄 — **"로깅 문은 REPORT 4개만. DOCUMENT/DUAL은
  의무가 거꾸로라 판단이 다르고, **안 봤다**."** 같은 꼴의 문장을 두 번 시험해 결함 여섯을
  얻었으므로(증거 로그 11·13절) 세 번째도 시험했다.
- Verified(**이번엔 변명이 참이었다**): 12절의 탐지기를 **재구현하지 않고 임포트해서**
  DOCUMENT 3개·DUAL 2개에 돌렸더니 **다섯 다 WARNING+ 호출에 안 닿는다**. 기본값
  (lastResort → stderr)이 이들에겐 **이미 옳은 스트림**이라 **고칠 게 없다**.
  세 번째 시험은 결함을 안 줬다 — **그것도 결과다**(안 본 것이 **볼 게 없다는 측정**이 됐다).
- Verified(**대신 가드가 절반만 묻고 있었다**, Risk 12④ⓒ): `_clis_that_can_warn()`이
  `for name in REPORT:`다. 감사는 **REPORT의 의무**만 강제하고 **DOCUMENT의 거울 의무**는
  아무 데서도 안 묻는다 — DOCUMENT CLI가 같은 리다이렉트를 부르면 `WARNING …`이
  **kubectl이 파싱할 문서 안으로** 들어가는데 그걸 red로 만드는 게 없었다.
- Verified(결과 실증, 서브프로세스): `render_tenancy` stdout 첫 줄이 `WARNING …`이 되고
  `yaml.safe_load_all`이 **`ScannerError`로 터진다**. ⚠️`manifest_generator` 사례(4절)보다
  **시끄럽게** 깨진다 — 거긴 `{'Usage': …}`라는 **유효한 매핑**이었다.
  ⚠️**내 첫 실증이 틀렸다**: 인프로세스로 `sys.stdout`을 갈아끼웠는데 경고는 **진짜
  stdout**으로 갔다 — `basicConfig(stream=sys.stdout)`은 **호출 시점의 스트림 객체를
  붙잡는다**. **리다이렉션은 흉내 내지 말고 실제로 걸 것.**
- Changed(**테스트만, `scripts/`·`src/` 무변경**): 가드 셋 — DOCUMENT는 리다이렉트를 부르지
  않는다 · DUAL은 **무조건적으로** 부르지 않는다(`--json`이 stdout을 문서로 만든다 =
  **모드마다 의무가 뒤집힌다**) · 이 둘이 스타일이 아니라 규칙인 이유를 **행동으로** 박은
  앵커(실제 CLI + 서브프로세스 + `pytest.raises(yaml.YAMLError)`).
- Changed(**안 만든 것**): DUAL의 **모드 조건부 리다이렉트**. 둘 다 지금 경고에 못 닿아
  **아무도 태울 수 없는 가드**가 된다 — 08-12 `severity_in`과 같은 판단. 정답만 적어 뒀다.
- Verified: 변이 5건 red·생존 0. 깨끗한 변이(임포트까지 넣은 것)에선 **의도한 가드 하나만**
  실패한다. 복구 후 46 passed + diff clean. `make check` **1859**(+3), 2026-08-13,
  로컬 macOS·py3.13. 증거 `report-streams-swept-across-all-clis.log` **15절**.
- Blockers: 없음.
- Next: 파이프 뒤 나머지 일곱은 **강제할 실패 경로가 없거나 이미 옳다**(재확인 불필요).
  남은 건 `slack_live_approval` 이중 노후화 하나인데 **데모를 실제 Slack에 태워야** 확정된다.

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

