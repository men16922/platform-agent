# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-29

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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

