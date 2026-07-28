# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-29

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-29 — MTTR은 존재 내내 구조적으로 0이었다 (gate 1496→1520)

- Status: `resolved_at` 하나를 보러 갔는데 **한 사슬에 결함 셋**. 전부 테스트는 초록.
- Changed(`3a89e43`): ①**쓰는 쪽이 기본값을 채웠다** — 공용 클라우드 기록기가 `resolved_at`을
  무조건 `created_at`과 같은 값으로 써서 **미해소 인시던트가 해소 시각을 달고** 다녔다(온프렘은
  정반대로 아예 안 씀). ②**`_fetch_incidents_from_dynamo`가 `resolved_at`을 `started_at`·
  `resolved_at` 양쪽 끝에 넣었다** → 여태 발송된 **모든 주간 온콜 리포트의
  `average_mttr_minutes`가 0.0**. 같은 함수가 `alarm_name`을 `runbook_id`에 복사해 재발 패턴
  그룹핑도 알람별로 붕괴(런북 하나에 몰리는 서로 다른 알람 = 그 기능의 존재 이유). ③**대시보드
  Scan의 `ProjectionExpression`이 자기 리더가 읽는 4필드를 안 가져왔다**(`triggered_at`·
  `confidence`·`reconciliation`·`trace_id`) → 상세 뷰가 배포 내내 모든 AWS 인시던트에
  "confidence n/a"를 띄웠고, **아침 gate 1496의 수정이 그걸 표시할 배지 한 층 앞에서 멈춰** 있었다.
- Verified: `make check` **1520**(+24) · tsc 클린 · `next build` 성공. **BEFORE/AFTER 실측**:
  동일 입력에 `average_mttr_minutes` **0.0 → 45.0**. **라이브**(실 온프렘 웹훅 체인, 25분 전
  `startsAt`): P1/AUTO **1502초(25m)** 보존 · P3/MANUAL·P2/APPROVE→reject는 `resolved_at`
  **부재**. 반증 7건 개별 되돌림 전부 red, 복원 시 24건 통과.
  증거 `docs/evidence/incident-time-to-resolve.log`.
- Blockers: 없음.
- 품질 메모: 왜 안 잡혔나 — `test_summarizes_incidents`가 MTTR 45.0을 단언하는데 **손으로 만든
  픽스처**에서 받는다. 유일한 실제 생산자가 낼 수 없는 모양이라 **영원히 초록이었을** 것이다
  (07-29 아침에 배운 "픽스처는 실제 입력에서"의 세 번째 사례). 새 테스트는 픽스처가 아니라
  `_fetch_incidents_from_dynamo`를 통과시킨다. 그리고 **투영 가드는 키워드 목록이 아니라
  파생**이다 — 매퍼가 읽는 속성을 파싱해 Scan이 전부 가져오도록 요구하므로 **다음 필드에도**
  실패한다. 손으로 적은 목록이었다면 당시 투영에 맞춰 쓰였을 테고 이 버그를 그대로 통과했다.
  `_minutes_between`은 clamp 대신 None — 발생보다 앞선 해소(시계 어긋남)를 **완벽한 0분 복구로
  세지 않는다**. 파싱 실패도 더는 raise 안 한다(예외 하나가 리포트 전체를 죽였다).
- Next: 실 DynamoDB 왕복은 여전히 미실행(쓰기·읽기 양쪽 모두). GCP Firestore·Azure Cosmos
  기록기는 둘 다 안 쓰지만 읽는 쪽이 없어 **의도적으로 남김**.

## 2026-07-29 — 클라우드 인시던트 행도 발생 시각·confidence를 버렸다 (gate 1491→1496)

- Status: 아침의 온프렘 수정이 남긴 나머지 절반. 같은 누락이 `executor._record_incident`
  (AWS·GCP·Azure 공용)에 있었고, **`tenant`/`env`에 대해 같은 결함을 고쳤다고 적어둔 주석
  바로 아래**였다.
- Changed(`36e3b4a`): 둘 다 **읽는 쪽이 이미 있었다** — ①`triggered_at`(대시보드가 오늘
  아침부터 읽는다. 읽는 쪽이 쓰는 쪽보다 먼저 존재한 비대칭) ②`confidence`(analyzer가 매번
  만들고 상세 뷰가 늘 렌더한다 → **모든 클라우드 인시던트가 그 뷰가 존재한 내내
  "confidence n/a"를 보여줬다**).
- Verified: `make check` **1496**(+5). ②의 함정을 **가정하지 않고 확인**했다 —
  `TypeSerializer().serialize(0.98)`은 `TypeError: Float types are not supported`.
  그 예외는 기록기 자신의 `except Exception`에 잡히므로, 자연스러운 타입으로 썼다면 필드
  하나가 아니라 **레코드 전체가 조용히 사라졌을** 것이다. `Decimal(str(...))`로 저장
  (`request_store.py`가 같은 이유로 세워둔 패턴). 반증: float 되돌림 3건 · triggered_at
  제거 1건, 복원 시 9건 통과. 증거 `docs/evidence/cloud-incident-fields.log`.
- Blockers: 없음.
- 품질 메모: 반증 셋 중 하나를 **아이템 전체에 float가 없는지** 보는 가드로 뒀다 — float
  하나면 쓰기가 통째로 실패하고, 오늘 위험을 들여온 필드가 다음에도 그 필드라는 보장은 없다.
  그리고 이번 결함은 **자기 자신을 설명하는 주석 바로 아래**에 있었다: 같은 함수에서 같은
  종류를 한 번 고쳤다고 그 함수가 그 종류로부터 안전해지지 않는다.
- Next: `resolved_at`이 여전히 `created_at`과 같은 쓴 시각이라 **time-to-resolve는 아직 불가**.
  실 DynamoDB 왕복은 미실행(모킹 테이블 + 직렬화기 직접 확인까지).

## 2026-07-29 — 인시던트 기록이 "언제 터졌는지"를 몰랐다 (gate 1479→1491)

- Status: 스윕이 남긴 두 번째 실제 건. "타임라인 표시 결정 필요"로 적어뒀는데 다시 보니
  **표시는 결정이지만 값을 버리지 않는 것은 결정이 아니다** — 테넌시 때와 같은 모양.
- Changed(`78e472d`): 네 어댑터가 소스의 실제 발생 시각을 채우는데 `record_incident`가 경계에서
  버려, 행이 `created_at`(우리가 쓴 시각)만 알았다 → **탐지 소요시간 산출 불가**, 타임라인이
  인시던트를 "처리된 순간"에 배치. 저장(모르면 **부재**) + 파이프라인·웹훅 양쪽 경로 배선 +
  승인 경로가 함께 버리던 `trace_id`도 복구(어제 넣은 span origin에서) + 대시보드 optional
  필드·방어적 매핑·**`detected +Nm` 배지**. 배지는 장식이 아니라 요점이다 — 읽는 쪽 없이
  저장만 하면 스윕이 그날 찾은 결함을 하나 더 만드는 꼴이다.
- Verified: `make check` **1491**(+12) · `tsc` 클린 · `next build` 성공.
  **라이브(승인 경로 = 간격이 가장 큰 곳)**: 12분 전 발생 신고 → parking → 승인 →
  간격 **735초** 보존("detected +12m"). 트레이싱 켠 2차 실행에서 `trace_id`가 실제
  `onprem.incident_pipeline` 트레이스와 **일치**함까지 확인(주석으로 주장만 하지 않았다).
  반증: 저장 제거 2건 · 음수 억제 제거 1건, 복원 시 12건 통과.
  증거 `docs/evidence/incident-trigger-time.log`.
- Blockers: 없음.
- 품질 메모: `describeDetectionGap`이 **과장을 거부**하도록 짰다 — 발생 시각 없음/파싱 불가/
  발생보다 먼저 기록됨은 전부 렌더 안 함. 마지막은 가정이 아니다(스포크↔허브 시계 어긋남은
  정상이고, 화면의 "detected -3s"는 옆의 모든 숫자에 대한 신뢰를 배지 부재보다 크게 무너뜨린다).
- Next: 클라우드 3사 인시던트 행은 공유 executor가 DynamoDB에 쓰므로 **여전히 발생 시각을
  버린다**(스키마 변경 수반). resolve 시각 미기록이라 time-to-resolve도 아직 불가.

## 2026-07-29 — 계통 스윕: 운영자가 미리 붙인 severity를 버리고 있었다 (gate 1470→1479)

- Status: 남은 잔여가 전부 **결정 대기**라, 결정이 필요 없는 최고 가치 작업으로 **"선언됐고
  아무도 안 읽는" 결함 부류를 계통적으로 훑었다**(이틀 새 여섯 번 나왔고 전부 우연이었다).
- Changed(`0cf5da5`): `src/agents`의 모든 ClassDef 애노테이션 필드 **437개 중 20개** 후보.
  대부분 결함 아님(`TokenBroker.signing_key`는 **오탐** — `self.` 형태를 패턴이 놓쳤다;
  route_trace·slack_ts 등은 직렬화되는 응답 표면). 진짜는 둘, 이빨 있는 건 하나:
  **`severity_hint`를 네 어댑터가 전부 채우는데 아무도 안 읽는다**. 사람이 **미리** 내린
  유일한 분류가 버려지고 severity는 산문에서만 추론된다 — 그런데 severity가
  **P1→AUTO/P2→APPROVE**, 즉 사람 없이 실행할지를 정한다. analyzer 프롬프트에 **증거로**
  노출(하드 매핑은 정책 결정이라 발명 안 함, "구속력 없음 + 다르면 이유 명시").
- Verified: `make check` **1479**(+9). **라이브 A/B**(동일 알람, 라벨만 다름):
  critical→P1/AUTO **실행** · **warning→P2/APPROVE 대기** · info→P2/APPROVE.
  warning이 핵심 — 같은 페이로드가 **오늘 낮엔 P1/AUTO로 자동 실행**됐다.
  반증: 프롬프트 줄 제거 시 9건 중 6건 실패, 복원 시 통과.
  증거 `docs/evidence/declared-unconsumed-sweep.log` · 스윕은
  `scripts/find_unconsumed_fields.py`로 반복 가능하게 남김.
- Blockers: 없음.
- 품질 메모: 테스트가 **프롬프트**를 단언한다. "필드가 설정되는가"를 봤다면 이 필드가 존재한
  내내 통과했을 것이고, **그게 이게 여태 살아남은 방식이다.** 어제 배운 두 가지(호출부에서
  반증 · 픽스처는 실제 입력에서)에 이어 셋째: **소비자를 단언하라, 생산자 말고.**
- Next: `triggered_at`도 같은 상태(네 어댑터가 채우고 아무도 안 읽음 → 탐지 소요시간 불가) —
  타임라인 표시 결정 필요. 그 외 잔여는 전부 결정 대기.

## 2026-07-29 — "선택 가능"은 AWS 경로에서만이었다: 겹친 결함 3개 (gate 1454→1470)

- Status: 어제 라이브에서 본 "온프렘 알람이 새 런북에 안 걸린다"를 **매칭 설계 결정**으로
  남겼는데, 결정이 아니라 **배선 결함 3개가 쌓여** 있었다. 하나를 걷어내야 다음이 보였다.
- Changed(`b70c195`): ①`_synthetic_alarm`이 `reason`과 `metric_name`을 **둘 다
  `signal_type`**으로 채워, 매처가 "availability availability …"를 읽고 있었다. alertname·
  summary는 내내 정규화돼 저장돼 있었고 선택에만 안 닿았다(프로바이더 중립 수정).
  ②`resource_types`가 **모든 런북에 선언돼 있고 아무도 안 읽었다** — 이틀 새 다섯 번째
  "선언됐고 유효하고 소비 안 되는" 필드. 없으면 RDS 런북이 k8s 워크로드에 걸리고, 실패가
  조용하다(해결 실패 시 **런북의 하드코딩 AWS 액션 이름**으로 폴백). ③①②를 고쳐도
  라이브는 계속 달랐다: 시드된 eks-pod-oom **1점**이 빌트인 health-check-failure **3점**을
  이겼다 — 자기 카탈로그가 먼저 스캔됐다는 이유만으로. D34가 "무매칭"만 막고 "더 나쁜 매칭"은
  안 막았다 → 두 카탈로그를 **합집합에 휴리스틱 한 번**으로 통합(동점 시 운영자 우선, D35).
- Verified: `make check` **1470**(+16). **라이브**(실 웹훅+실 analyzer): 디스크→disk-full ·
  NotReady→health-check-failure · 인증서→certificate-expiry · CrashLooping→eks-pod-oom(회귀 없음).
  **전부 ONPREM-\* 액션**으로 해소 = 잘못된 프로바이더 폴백이 안 터졌다는 증거.
  반증 3종(reason 되돌림 4건 · 게이트 제거 1건 · 티어 순차 복귀 6건), 복원 시 36건 통과.
  증거 `docs/evidence/onprem-runbook-matching.log`.
- Blockers: 없음.
- 품질 메모: **이번엔 내 테스트 자체가 결함이었다.** 첫 버전이 통과하는데 라이브는 여전히
  generic-recovery였다 — 내가 쓴 summary에 런북 키워드를 심어놨기 때문이다("…, disk full
  projected in 18h"). 실제 Alertmanager는 `NodeFilesystemSpaceFillingUp`이라고 보낸다.
  **테스트가 Alertmanager가 아니라 키워드 목록에 맞춰져 있었다.** 어제 배운 "호출부에서
  반증하라"에 하나 더: **픽스처를 코드가 아니라 실제 입력에서 가져와라.**
- Next: 남은 잔여는 전부 결정 대기(배포의 테넌트 소유권 · 무스코프 MCP 읽기 ·
  Capsule `limitRanges` 경로) + 런북 DynamoDB 재시드(배포 작업).

