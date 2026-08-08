# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-02

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---

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
