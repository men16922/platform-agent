# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-13

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-13 — 형제 집합 중 하나만 도는 가드를 사냥하다, 그 도구 안에서 같은 함정을 밟았다 (gate 1859→1862)

- Status: 오늘 두 건이 **같은 모양**이었다 — 가드가 **쓰는 쪽만**(티어 2) · 감사가
  **`for name in REPORT:`**(로깅 문). 목록을 다시 읽는 대신 **그 패턴 자체**를 물었다:
  형제가 N개인 집합을 **진부분집합만 도는 가드**가 또 있는가.
- Verified(**내 자신부터**): 새 가드의 `PROVIDERS = ["gcp","azure"]`가 좁은 게 아닌지 봤다 —
  `decision.py`는 셋뿐이고 onprem은 `runners/`를 타며 **AWS는 같은 블록이 아니라 다른
  구현**(점수제)이다. **둘이 맞다.**
- Verified(**전수 행렬, 아무도 잰 적 없다**): capability 17종 × provider 4종. 실행 어댑터가
  못 푸는 건 `increase_function_concurrency`/**onprem 하나뿐**이고 그건 **이미 알려진 정당한
  skip**이다(게이트의 `2 skipped`) → 감사가 **알려진 참을 재현** = 비공허.
  ⚠️`assert_*` 넷이 "아무도 못 푼다"로 나온 건 **내 탐지기가 틀린 것** — `verify`는 실행
  어댑터가 아니라 **별도 레지스트리 `_CHECKS`**가 푼다. **틀린 해소기에 물었다.**
- Verified(**그러다 진짜 질문**): `executor.py:221`이 `if provider == "onprem":`다 —
  **검증은 onprem에서만 돈다.** 나머지 셋은 `verify`를 계획에 싣고 실행하지 않는다.
  **그런데 결함이 아니다**: 코드가 경계를 **명시**하고(`executor.py:75`) `verified`를 True가
  아니라 **None(unknown)**으로 정직하게 보고하며, **그 정직성도 이미 가드돼 있다**.
- Changed(**문서 한 줄 — `src/` 무변경**): `COMPLETED_SUMMARY`가 *"per-step verify를 executor가
  실제 소비"*를 **무조건**으로 적고 있었다. 코드는 말하는데 요약은 안 해서, 그 줄만 읽는
  독자는 넷 다 검증한다고 믿는다 → **onprem 한정**임을 명시. **"과대 해석 금지"는 `STATUS`
  에만 걸리는 규칙이 아니다.**
- Verified(⚠️**스윕이 나에게 걸렸다 — 오늘 세 번째, 그것을 찾는 도구 안에서**): 카탈로그의
  `verify.capability`와 `_CHECKS`를 맞대 "구현됐는데 아무도 선언 안 함:
  `assert_node_unschedulable`"이 나왔는데 **틀렸다** — `verify_onprem_action:237`이
  `capability or VERIFY_FOR_ACTION.get(action)`라 **선언처가 둘**이고 나는 그 표를 안 봤다.
  **형제 집합은 세는 순간 전부 세지 않으면 하나가 조용히 빠진다.**
- Changed(정정 후 가드 4건, `TestEveryDeclaredCheckIsImplemented`): 진짜 불일치는
  **`assert_concurrency_applied` 하나**(구현 없음, 단 온프렘이 lambda 스텝을 못 resolve해
  **도달 불가**). 감사는 **선언처 둘을 다 읽고**, **양쪽을 읽는지 자체를 ground truth로**
  묻고, 예외는 `KNOWN_UNIMPLEMENTED`에 **이유와 함께** 두되 **이유보다 오래 못 살게** 한다.
- Verified: 변이 5건 red·생존 0, 복구 후 diff clean. `make check` **1862**(+3), 2026-08-13,
  로컬 macOS·py3.13. 증거 `verify-capabilities-declared-vs-implemented.log`.
- Blockers: 없음.
- Next: **패턴 사냥이 준 것은 결함이 아니라 범위였다**(오늘 두 번째). `src/`는 안 바꿨고
  **고칠 게 없다는 것도 측정**이다. 남은 무과금 항목은 전부 정책 판단이거나 외부 자원 대기.

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

