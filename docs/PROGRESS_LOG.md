# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-28

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-28 — executor span: 실제 경로 전부가 무추적이었다 (gate 1446→1454)

- Status: 잔여 "② executor span(선택)"을 처리. 기록은 "승인 후 경로 미측정"이었는데
  실제로는 **AUTO 경로도 무추적**이었다.
- Changed(`3939d47`): 웹훅이 `execute=False`로 파이프라인을 부르고 **루트 span이 닫힌 뒤**
  실행하므로, 클러스터를 바꾸는 단계가 **실제 알람이 타는 모든 경로에서 span을 안 냈다**.
  기존 테스트는 `run_incident_pipeline(execute=True)`로 들어가 갭보다 한 층 아래를 봤다.
  span을 `execute_incident` 안으로(호출부 3곳 공유) · 웹훅 루트 2개 ·
  승인은 **부모가 아니라 span link**(사이 간격=사람의 고민 시간. 접으면 span 길이가 대부분
  "슬랙 읽는 시간"이 되어 지연 수치가 무의미해진다) · `SpanOrigin`(trace+span id)을 parking
  레코드에 저장(trace id만으론 링크 불가) · 반쪽 origin은 **죽은 링크 대신 속성만**.
- Verified: `make check` **1454**(+8). **라이브**(실 uvicorn + 실 OTLP/gRPC; Docker 다운이라
  Tempo 대신 collector 와이어 프로토콜 구현 싱크): AUTO=**6 span 단일 트레이스**
  (analyze 5.4s/총 7.7s로 wall-clock 분해) · 승인=**트레이스 2개 + 링크 1개**, 링크가 실제로
  제안 span을 가리킴. 사람이 고민한 ~11초는 두 트레이스 어디에도 안 잡힘.
  실행: ONPREM-RolloutRestartWorkload / INC-615A4BEB / resolved=true.
  반증 3종(span 제거 5건 · 링크 제거 1건 · 웹훅 루트 제거 1건), 복원 시 8건 통과.
  증거 `docs/evidence/executor-span-approval-path.log`.
- Blockers: 없음.
- 품질 메모: 부수로 `span()`의 **조용한 충돌**을 고쳤다 — OTel 키가 점 표기라 호출자가
  `**{"a.b": v}`를 쓰는데, `**` 언팩은 명명 파라미터와 충돌해서 **"link"라는 이름의 속성이
  span link가 되어버릴** 수 있었다. 타입체커가 계속 가리키던 게 오탐이 아니었다.
- Next: 위 라이브에서 새 갭 하나가 보였다 — 선택 가능해진 런북 4개가 **온프렘 알람엔 안 걸린다**
  (디텍터가 alertname을 버리고 `metric_name=availability`로 정규화). 회귀는 아니고 매칭 설계 결정.

## 2026-07-28 — 잔여 3건 소진: grant 대조 · 선택 불가 런북 · Capsule 이관 (gate 1411→1446)

- Status: 계획에 남아 있던 **차단 없는 잔여 3건**을 우선순위대로 처리. 셋 다 기록된
  갭보다 컸고, 셋 다 **라이브가 유닛 테스트와 다른 답**을 내놓은 지점에서 진짜 결함이 나왔다.
- Changed(`63df3c5`, grant): 기록은 "대조 안 함"이었는데 실제로는 ①grant를 **줄 방법
  자체가 없었고**(라우트·스토어 둘 다 `tenants`를 안 받음 — 읽기 쪽이 아무 쓰기 경로도
  못 만드는 필드를 소비 중) ②역할 변경이 whole-item Put으로 grant를 **조용히 지웠다**.
  허브 `GET /api/platform/tenants`(레지스트리=SSOT, 못 읽으면 빈 목록 아닌 **503**) +
  `platform-roster.ts`(null=미검증) + 저장 전 대조 + `absent=유지` + users 테이블 컬럼.
- Changed(`9beda00`, 런북): 런북 4개가 BUILTIN에 없어 선택 불가 → 항목 추가. 그런데
  **라이브 전체 경로는 여전히 넷 다 generic-recovery**였다. 실 스캔 결과 시드 테이블에
  generic 행이 있어 티어 2가 티어 4의 답을 대신 냈고 **티어 3(빌트인)이 배포 환경에서
  한 번도 도달된 적 없었다**. `allow_generic=False`로 해소. 부수로
  `assert_health_check_passing` 구현(미구현 검사는 **실패**로 치므로, 안 하면 재시작
  성공에도 매번 롤백 캐스케이드).
- Changed(`278a264`, Capsule): `additionalMetadata` → `additionalMetadataList`.
  CRD에 직접 물어 확인. 제거 릴리스에서 **에러 없이 안 읽히는** 실패라 선제 이관.
- Verified: `make check` **1446**(+35 누적) · `tsc` 클린 · `next build` 성공.
  **라이브**: grant 5케이스(선언 200 / 없는 테넌트 400 지목 / 역할 변경 후 생존 /
  허브 다운 503 / 회수는 200) · 실 DynamoDB 스캔으로 런북 4개 정상 해소 ·
  kind에서 PSS 라벨 유지 + probe 라벨 전파. 증거 `docs/evidence/{phase3-tenant-grant-validation,
  runbook-selectability,capsule-deprecation-metadata}.log`.
- Blockers: 없음(아래 Next는 차단이지 실패가 아님).
- 품질 메모: **반증이 세 번 중 한 번은 내 테스트를 잡았다.** 호출부를 되돌렸는데 새 테스트
  20건이 전부 통과했다 — 전부 `_match_runbook_registry`를 플래그를 이미 준 채로 직접
  불러서, **플래그를 잊은 호출자를 볼 수 없었다**. 라이브만 잡았고, 호출부 단언을 추가했다.
  "가드도 반증하라"는 이제 "가드를 **호출부에서** 반증하라"로 좁혀야 한다.
- Next: **모델 호출 rate limit은 deployments 파티션과 같은 결정에 묶여 있다**(조사 결과) —
  로컬 모델 호출자는 `local_deployer`/`strands_deployer` 둘뿐이고 둘 다 배포 경로인데,
  배포 요청엔 테넌트가 없고 `setup_tenancy(tenant, ...)`는 **모델이 부르는 도구**다.
  즉 테넌트가 추론의 **입력이 아니라 출력**이라 헤더로 받으려면 "배포는 어느 테넌트
  소유인가"를 먼저 정해야 한다. 남은 것: 그 결정 · 무스코프 MCP 읽기 · `limitRanges` 이관 경로 결정.

## 2026-07-28 — 읽기 파티션 완결 + granted-viewer 실증 (gate 1404→1411)

- Status: 대시보드 읽기 경로 둘(플릿·인시던트)이 테넌트로 파티션되고, 오래 미뤄둔
  granted-viewer 왕복이 실증됐다.
- Changed(`0512d2b`): 파티션 불가의 원인은 읽기가 아니라 **쓰기**였다 —
  `NormalizedIncident`는 Phase 1a부터 `tenant`를 갖고 있는데 `_record_incident`가 버렸다.
  저장은 **비어 있으면 키를 안 넣는다**(부재 ≠ 빈 문자열). `visibility.ts`에 `filterRows`
  (같은 seam) · **기록 없는 행은 admin 전용** · `withheld` 카운트 반환 ·
  캐시 헤더 `public, s-maxage=30` → **`private, no-store`**(호출자마다 다른 응답을 공유
  캐시가 서빙하면 그게 유출이다).
- Changed(`2357583`): granted-viewer가 미실증이던 진짜 이유는 OAuth가 아니라 **local-dev
  우회가 `role: admin`을 하드코딩**한 것 — 인가 표면 전체가 로컬에서 검증 불가였다.
  이제 실 로그인과 같은 저장소에서 역할을 읽는다(`DASHBOARD_DEV_AUTH_USER`).
- Verified: `make check` **1411**(+7) · `tsc` 클린 · `next build` 성공.
  **라이브(빌드 산출물)**: 익명 0/3(withheld 3) · **viewer-demo(grant=['acme']) 1/3**
  (withheld 2, `private, no-store`) · admin 3/3(무태그 행 포함).
  **반증**: "기록 없는 행은 모두에게" 주입 → RowFiltering 3건 실패, 복원 시 통과.
  증거 `docs/evidence/phase3-read-partition-live.log`.
- Blockers: 없음.
- 품질 메모: 이번에도 **테스트가 낡은 정책을 고정**하고 있었다 —
  `DASHBOARD_AUTH_DESIGN.md`의 "Read path remains public"을 단언하는 테스트가 있어서,
  정책이 바뀐 뒤에도 문구가 살아남았다. 오늘만 세 번째 사례다(`ROUTE_PROTECTION` ·
  Agent Card 필드 존재 단언 · 이것).
- Next: deployments/activities 파티션은 **데이터 모델 결정 선행**(배포는 어느 테넌트
  소유인가 — 인시던트와 달리 tenant가 아예 없다) · rate limit을 모델 호출까지 ·
  무스코프 MCP 읽기.

