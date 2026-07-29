# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-29

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-29 — 리포트 창을 시계가 아니라 보관 필드로 재고 있었다 (gate 1533→1544)

- Status: 읽기 모델 건이 연 **TTL 실마리**를 따라갔다. 거기서 `ttl` 커버리지가 writer마다
  다르다는 걸 알았으니 다음 질문은 **누가 `ttl`을 읽는가** — 두 리포트 창이 그걸 **시각처럼**
  읽고 있었다. M13의 열두 번째.
- Changed(`5988d6b`): `ttl`은 **쓴 시각 + 90일**이다. ①**일일 SLO**: 필터가
  `ttl >= now - 24h`인데 ttl은 항상 미래 90일이고 cutoff는 과거라 **만료 안 된 모든 행에 대해
  참** — "최근 24시간"이 보관 기간 전체였다(바로 다음 줄의 파이썬측 재검사도 같은 두 값이라
  항상 거짓). ②**주간 온콜**: `ttl - 90일`로 역산 — 보관 상수를 바꾸면 리포트 전체가 조용히
  밀리고, **`ttl`이 없는 행은 `now`로 기본값이 잡혀 90일 과거로 떨어져 모든 주간 리포트에서
  소리 없이 빠졌다**(`created_at`에 나이가 분명히 적혀 있는데도). 둘 다 모든 writer가 무조건
  쓰는 `created_at`으로 배치. `ttl`은 레거시 행 폴백으로만 남기되(빼면 리포트가 조용히 줄어든다)
  **writer의 `ttl` 식을 AST로 읽어 상수 일치를 강제**했다. 두 필드로도 못 구하면 **제외**(추측 금지).
- Verified: `make check` **1544**(+11). **BEFORE/AFTER 실측**(90일치 90행): 필터 통과
  **90 → 2**, 경계 포함 기대값 2와 일치. 반증 5건 개별 되돌림 전부 red, 복원 시 11건 통과.
  증거 `docs/evidence/report-windows.log`.
- Blockers: **라이브 미실행** — 둘 다 EventBridge 스케줄 Lambda 경로라 실 AWS가 필요하다
  (이미 열려 있는 승인 항목). "프로덕션에서 과대 집계돼 왔다"는 **코드·writer 포맷에서의 추론**
  이지 발송된 리포트의 관측이 아니다.
- 품질 메모: **내 가드 둘이 먼저 틀렸고 둘 다 이 마일스톤의 단골 실패 양식**이었다.
  ①`failed_requests`(원시 카운트)를 `total_requests`(×100)로 오독해 `// 100`을 넣었더니
  `90 // 100 = 0`이라 **수정 전 코드에서 통과**했다 — 형제 테스트가 같은 오독으로 깨져서야
  드러났다. ②되돌림 3이 초록이었다: 픽스처의 `ttl`과 `created_at`이 **일관돼서 두 구현이 모든
  행에 대해 같은 답**을 냈다 — 테스트가 수정과 버그를 구별 못 했다. **갈리는 경우**(created_at은
  있고 ttl 없음 = 이 수정이 겨냥한 바로 그 조용한 누락 / ttl이 다른 보관 기간)를 추가했다.
  **산문으로만 주장하고 코드로 단언하지 않은 게 있으면 그건 아직 안 고친 것이다.**
- Next(같은 세션에 확인 완료): Azure/GCP `ttl` 식 차이는 **시맨틱 차이가 맞았고**(Cosmos는
  상대 초, 그래서 Azure가 옳다) 그런데 **둘 다 집행되지 않는다** — Cosmos 컨테이너는
  `durable_functions.py`가 `--ttl` 없이 만들어 항목 `ttl`이 무효이고, Firestore는 TTL 정책이
  IaC 어디에도 없으며 필드도 **Timestamp가 아닌 정수**라 정책을 붙여도 안 걸린다. 즉 두
  스토어의 인시던트 문서는 **무기한 남는다**. 주석만 사실에 맞추고(집행 안 하는 걸 광고하지
  않는다) **동작은 안 바꿨다** — 보관을 켜는 건 실 데이터 삭제라 승인 사항이고 읽는 쪽도 없다.
  → `STATUS` Open Risk 2 · `NEXT_PLAN`.

## 2026-07-29 — 읽기 모델 문서가 존재 내내 어긋나 있었다 (gate 1528→1533)

- Status: 스윕을 **대시보드 TS 쪽**으로 확장(기존 스윕은 `src/agents`만 본다). M13의 열한 번째
  이자 **한 층 위**: 필드가 아니라 **선언 자체를 아무도 안 읽는** 경우.
- Changed(`61ee2f4`): `activity-model.ts`는 **아무도 import하지 않는다** — 그래서 어긋나도
  아무것도 안 깨졌고, 실제로 양방향으로 어긋났다. 아무도 안 쓰는 `duration_ms`·`error_message`를
  선언하면서 **배포 상세 페이지가 딛고 선 `trace`·`cost_metrics`·`deployment_id`는 없었다**.
  거짓 주장 둘: ①`ttl` 필수 + "30일 보관"이지만 `ttl`을 쓰는 건 `activity_writer`뿐이고
  실제 대부분을 쓰는 `deploy_recorder`는 안 써서 **그 행들은 만료되지 않는다** ②`GSI1`도
  절반만 채워지고 **아무도 쿼리하지 않는다** — 이 문서를 보고 provider 스코프 쿼리를 짰다면
  에이전트가 쓴 행을 전부 빠뜨린 짧은 목록을 **조용히** 받았을 것이다. writer 계열이 둘인데
  어느 쪽도 상위집합이 아니고 선언은 **둘 다와** 불일치. core/optional 분리 + 접근 패턴을
  USED/NOT USED/NOT WRITTEN으로 표기 + `make*Record` 생성자 4개 제거(배선된 적 없는 TS 쪽
  쓰기 경로 = 갈라질 일만 남은 두 번째 진실 소스).
- Verified: `make check` **1533**(+5) · tsc 클린 · `next build` 성공. 반증 5건(**원본 파일
  포함** → 5개 중 3개 red) 전부 red, 복원 시 5건 통과.
  증거 `docs/evidence/activity-read-model-drift.log`. 런타임 동작 변화 없음(importer가 0인 게 요점).
- Blockers: 없음.
- 품질 메모: 왜 안 잡혔나 — `test_activity_model_schema`가 **부분문자열 존재**만 봤다
  (`'GSI1PK:' in content`, `"TTL_30_DAYS" in content`). 키워드는 **모양을 못 본다** — 이
  마일스톤이 이미 적어둔 안티패턴이 **그 파일을 지키는 테스트에** 있었다. writer AST에서
  파생하는 가드로 교체. **그리고 내 가드도 처음엔 같은 병이었다**: `re.search`라 두 선언 중
  하나만 옵셔널이면 통과해서 되돌림 3이 초록으로 나왔다 — `any`를 쓸 자리에 `all`이 필요했다.
  전 선언 지점을 요구하도록 조인 뒤에야 빨개졌다.
- Next: TS 쪽 후보 중 `ApprovalRequest.request_kind/subject/summary`는 **이미 렌더되는
  `alarm_name`/`root_cause`의 중복**(손실 아님, 사문화). TS 후보 47건을 마저 읽은 결과
  **데이터 손실은 이 건 하나뿐**이었고 나머지는 죽은 선언 → NEXT_PLAN에 후보로 기록(고치지 않음).

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
