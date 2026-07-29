# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-29

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-29 — 롤백된 배포는 비용 패널을 통째로 잃었다 (gate 1520→1528)

- Status: M13의 열 번째. 앞의 아홉이 "선언됐는데 아무도 안 읽음"이었다면 이번은 **반대
  방향** — 읽는 쪽은 멀쩡한데 **셋 중 한 생산자만 침묵**했다. 기존 스윕이 구조적으로 볼 수
  없는 부류라 반대 방향 도구를 새로 만들어 찾았다.
- Changed(`db41874`): ①`record_rollback`이 `cost_metrics`를 안 썼다(`steps`를 이미 쥐고
  있어 `_cost_metrics` 호출만 빠진 상태). ②그 자체론 과소보고인데, `mergeActivity`가
  **trace만 합집합**으로 두고 나머지를 `{...latest}`로 최신 행에서 가져간다 → 롤백되는
  순간 도구/추론/토큰 수가 **페이지에서 사라졌다**. 패널이 조건부라 예외도 "0"도 없었고,
  **바로 아래 트레이스는 두 실행을 합쳐 오히려 길어진** 채였다. writer만 고치면 롤백의 2회를
  배포 전체 수치로 보고하게 되어 부정합이 바뀔 뿐이라 읽는 쪽도 함께 고쳤다
  (`sumCostMetrics`가 접힌 모든 행을 합산 + per-tool 내역 병합 = trace와 같은 규칙).
- Verified: `make check` **1528**(+8) · tsc 클린 · `next build` 성공. **라이브**(빌드된
  대시보드 local 모드, 실 recorder가 쓴 JSONL, HTTP GET): BEFORE 양쪽 되돌려 재빌드 →
  200인데 **패널 미렌더**(트레이스 도구명은 10회 표시) / AFTER → `tool calls 5 ·
  reasoning 1 · tokens 920(800 in/120 out)`, 내역이 **두 실행에 걸침**. 반증 4건 개별
  되돌림 전부 red, 복원 시 8건 통과. 증거 `docs/evidence/rollback-cost-metrics.log`.
- Blockers: 없음.
- 품질 메모: 왜 안 잡혔나 — `test_record_deploy_attaches_cost_metrics`가 **동작하는 생산자만**
  단언했고, 병합 규칙엔 테스트가 아예 없었다. 양쪽 절반은 각각 방어 가능했고 **둘이 겹칠 때만**
  터졌으며 **페이지에서만** 보였다. 가드는 또 파생: **`deployment_id`를 쓰는 ACTIVITY 행은
  반드시 `cost_metrics`를 쓴다**(그 키가 곧 상세 페이지로 라우팅되는 조건이므로, 모듈 목록이
  아니라 키가 의무를 만든다). AST가 아무것도 못 잡으면 공허하게 통과하므로 **가드의 가드**도 뒀다.
  새 도구는 첫 실행에서 신뢰를 잃지 않도록 `item["k"]=v` 첨자 대입까지 writer로 인정한다 —
  없으면 **이미 고친 `triggered_at`을 미생산으로 오보고**한다.
- Next: `record_route_activity`·`record_agent_activity`는 `deployment_id`가 없어 이 뷰에
  닿지 않으므로 **의도적으로 안 고침**(넣으면 소비자 없는 필드). 문서 예산 초과는 같은 날
  `/tidy-docs`로 해소(log 164→112, status 133→118).

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
