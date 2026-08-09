# STATUS 검증 Baseline Archive — July 2026

> `docs/STATUS.md` 검증 Baseline에서 예산(≤120줄) 초과로 아카이브된 과거 이력
> (2026-07-10~29, **gate 1533 이하**). gate 내림차순으로 정렬돼 있다 — 이전에는 아카이브
> 배치 순으로 append돼 1114~1017 블록이 파일 끝에 있었다(2026-07-28 정렬).

- `make check` → **1496** (2026-07-29, +5) — **클라우드 인시던트 필드**(`36e3b4a`):
  `triggered_at`·`confidence` 둘 다 **읽는 쪽이 이미 있었다**. **함정**: boto3는 float를 거부하고
  그 예외가 기록기 `except`에 잡혀 **레코드 전체가 사라졌을** 것(→`Decimal`).
  증거 `docs/evidence/cloud-incident-fields.log`.
- `make check` → **1491** (2026-07-29, +12) — **인시던트 발생 시각**(`78e472d`): 네 어댑터가
  채우는 `triggered_at`을 `record_incident`가 경계에서 버렸다. 저장 + 양쪽 경로 배선 +
  `detected +Nm` 배지. 라이브 승인 경로에서 735초 보존.
  증거 `docs/evidence/incident-trigger-time.log`.
- `make check` → **1520** (2026-07-29, 1496→1520, +24) —
  **time-to-resolve**(`3a89e43`): 한 사슬에 결함 셋. ①공용 클라우드 기록기가 `resolved_at`을
  무조건 `created_at`과 같은 값으로 써 **미해소 인시던트가 해소 시각을 달고** 다녔다(온프렘은
  아예 안 씀) ②`_fetch_incidents_from_dynamo`가 `resolved_at`을 **양쪽 끝에** 넣어 **여태
  발송된 모든 주간 온콜 리포트의 MTTR이 0.0**이었다(+`runbook_id`에 `alarm_name` 복사 →
  재발 패턴 그룹핑 붕괴) ③대시보드 Scan 투영이 **자기 리더가 읽는 4필드**를 안 가져와
  아침 수정이 배지 한 층 앞에서 멈춰 있었다. 실측 **0.0 → 45.0**, 라이브 P1/AUTO **1502초**
  보존·열린 인시던트는 부재. 증거 `docs/evidence/incident-time-to-resolve.log`.
- `make check` → **1528** (2026-07-29, 1520→1528, +8) —
  **롤백 비용 패널**(`db41874`): M13의 **반대 방향** 첫 사례 — 읽는 쪽은 멀쩡한데 ACTIVITY를
  쓰는 셋 중 `record_rollback`만 `cost_metrics`를 안 썼다. `mergeActivity`가 trace만
  합집합으로 두고 나머지를 `{...latest}`로 가져가 **롤백되는 순간 도구/추론/토큰 수가 페이지에서
  사라졌다**(패널이 조건부라 무예외·무영). 라이브 BEFORE 미렌더 → AFTER `tool calls 5 ·
  tokens 920`, 내역이 두 실행에 걸침. 새 도구 `scripts/find_unwritten_keys.py`(대시보드가
  읽는데 생산자가 없는 키)로 발견. 증거 `docs/evidence/rollback-cost-metrics.log`.
- `make check` → **1533** (2026-07-29, 1528→1533, +5) —
  **읽기 모델 문서 드리프트**(`61ee2f4`): `activity-model.ts`를 **아무도 import하지 않아**
  존재 내내 양방향으로 어긋났다 — 아무도 안 쓰는 `duration_ms`를 선언하고, 상세 페이지가
  딛고 선 `trace`·`cost_metrics`·`deployment_id`는 빠뜨렸다. **거짓 주장 둘**: `ttl` "30일
  보관"은 주 writer가 안 써서 **그 행들은 만료 안 됨** · `GSI1`은 절반만 채워지고 아무도
  쿼리하지 않아, 이 문서대로 provider 쿼리를 짰다면 **조용히 짧은 목록**을 받았을 것.
  지키던 테스트가 부분문자열 존재만 봤다 → writer AST 파생 가드로 교체.
  런타임 변화 없음. 증거 `docs/evidence/activity-read-model-drift.log`.
- **라이브 실증(2026-07-26, `b07523b`, 수 무변경)** — 기본 OFF로 남겨둔 3건 완주: ①canary 자동판정 **양방향**(나쁜 canary=`failed(3)>limit(2)`→사람 개입 0으로 ~105s auto-abort·stable 4/4 유지 / 좋은 canary=3연속 Successful→abort 안 됨) · ②Tempo 트레이스(query API·Grafana 프록시 양쪽 200, **5026ms 중 analyze 4136ms=MTTR의 82%가 로컬 LLM 추론**) · ⑥kindnet=**ENFORCED**+차트 정책 테넌트 시맨틱(same 통과/cross 차단). 증거 `docs/evidence/onprem-{addons-rollouts-analysis,tracing-tempo,netpol-tenancy}-e2e.log`. 라이브가 검증기 자체 버그 2건도 적발(agnhost `connect` http/URL 불가 · 파드 Ready≠포트 바인딩).
- `make check` (pytest) → **1355 passed, 1 skipped** (2026-07-27, 1341→1355, +14) — **Phase 3①
  자격증명 격리 full**(`bb091e1`): 가드가 `scope.py` 한 곳(`guard_scoped_action`)이고 세 러너가
  같은 구현을 부른다 · `resolve_incident_scope` 이관으로 **GCP Cloud Workflows 경로의 스코프 부재**
  해소(디스패치 경로가 둘인데 로직이 `aws/executor.py`에만 있었다) · seam이 전 분기에 전달하고
  네 번째 클라우드를 스코프 없이 추가하면 구조 가드가 실패한다. **라이브가 Phase 1a 증명의 구멍을
  적발**: `render_rbac`가 바인딩 대상 SA를 렌더하지 않아 **RoleBinding이 없는 SA를 가리키고
  있었다**(fail-closed라 안 드러남 → RBAC 팔이 한 번도 행사된 적 없음). **라이브(kind, $0)**:
  실 토큰으로 자기 ns `yes` / 이웃 테넌트·클러스터 스코프 `Forbidden`(**API 서버**가 판정) ·
  실 러너 in-scope 재시작 성공 · gcp/azure 4케이스 인증·네트워크 이전 거부.
  증거 `docs/evidence/phase3-scoped-credentials-all-runners.log`.
- `make check` (pytest) → **1341 passed, 1 skipped** (2026-07-26, 1322→1341, +19) — **자연어가 테넌트를
  세운다 + 풀스택 30초 영상**: 에이전트 도구 2개 신설(`tenancy_tools.py` = `setup_tenancy` ·
  `install_tenant_addons`)로 "레지스트리에 다 적혀 있는데 사람만 적용할 수 있던" 마지막 두 걸음 해소.
  `cluster_io.py`가 렌더된 객체가 클러스터를 만지는 유일한 자리이고, `render_*` 스크립트와 **같은
  구현**을 쓴다(복사본 0, `render_tenancy.py` 출력이 HEAD와 완전 동일함을 대조로 증명). 자연어 도구는
  되물을 수 없으므로 **kubectl 컨텍스트 ≠ 레지스트리 클러스터면 아무것도 쓰지 않고 거부**.
  **라이브(실제 브라우저)**: 빈칸 → 문장 1줄 → 체인 2단(17.6s) → `4 / 4`·4축 ✓ → `1500m / 16` →
  실제 ArgoCD Synced/Healthy → netpol 1개 삭제 시 network만 ✕(globex 무영향) → 복구 ✓.
  영상 `docs/post/media/multitenancy-fullstack-30s.mp4`(30.03s, 오버레이 없음, 원본 153.8s→10컷).
  라이브가 결함 4건 적발(경고→실패 오기록 · 도구 완료 오판정 · 녹화 세션 부재 · 자격증명 파일).
- `make check` (pytest) → **1322 passed, 1 skipped** (2026-07-26, 1302→1322, +20) — **시연 가능 레벨**: 영상 시나리오를 격리 반증으로 재작성하고 그 대본이 찍히는 상태까지 구축. 준비가 구조적 갭을 드러냄 — repo URL이 TF에만 있어 **레지스트리만으로는 애드온을 설치할 수 없었다**(매 라이브 설치가 손으로 조립됨) → 카탈로그 `self_hosted_repo`(유일한 복사, TF 대조 가드로 안전화) + `scripts/render_addons.py` + `make demo-baseline`. **라이브**: 테넌트 스코프 loki+tempo Synced/Healthy(쿼터가 소비를 셈 cpu 2/16), netpol 1/4 삭제 시 network 축만 ✕·이웃 테넌트 무영향·복구 시 ✓, 실측 지연 18s/61s/59s. 증거 `docs/evidence/demo-isolation-falsification.log`.
- `make check` (pytest) → **1302 passed, 1 skipped** (2026-07-26, 1290→1302, +12) — **대시보드 멀티테넌시 관제 + 검증 훅**(`654c7e5`·`eebc19e`·`bad2642`): 격리 4축·티어·쿼터·네임스페이스를 **기존 push 경로**에 실어 대시보드로(직접 조회는 D26 위반) · 플릿 표 + 티어별 분리/공유/미보장 명시 · Add-ons 누락 4건(Loki·Fluent Bit·Tempo·Capsule) 추가 · Stop 훅 `make check` + PostToolUse 훅 `tsc`. **라이브 반증**: NetworkPolicy 삭제 시 network 축이 False로 뒤집히고 복구 시 True. `tsc` 클린 · `next build` 성공.
- `make check` (pytest) → **1290 passed, 1 skipped** (2026-07-26, 1281→1290, +9) — **Phase 2 완결(M11)**(`c6d930d`): managed 백엔드는 카탈로그에서 파생해 `applicable=false`(조회 안 한 백엔드에 health를 단언하지 않는다, faked 디스크립터로 과금 0 증명) · **DR 드릴** globex/dev 실제 파괴 후 레지스트리만으로 재구축(라벨 완전 동일, 10초 뒤 쿼터 선언값 일치) · 채택 검증기 신설. 증거 `docs/evidence/phase2-managed-and-dr.log`.
- `make check` (pytest) → **1281 passed, 1 skipped** (2026-07-26, 1271→1281, +10) — **어댑터 helm values seam**(`01d3c6d`): 카탈로그가 values 파일을 가리키고(복사 금지) 두 엔진이 같은 dict를 싣는다. 라이브가 결함 2건을 더 드러냈다 — **PSS restricted 테넌트 네임스페이스가 우리 애드온을 거부**(Argo는 Synced/Progressing인데 파드 0개; `monitoring`엔 PSS 라벨이 없어 지금까지 안 보였다) · **구독 해지가 테넌트 데이터를 파괴**(차트가 `whenDeleted: Delete`로 k8s 기본값 Retain을 뒤집음). 둘 다 근본수정. **라이브**: acme-dev-logging이 PSS+쿼터+NetworkPolicy 아래 Synced/Healthy — Phase 2 첫 진짜 테넌트 스코프 설치. 증거 `docs/evidence/phase2-values-seam.log`.
- `make check` (pytest) → **1271 passed, 1 skipped** (2026-07-26, 1267→1271, +4) — **삭제 cascade**(`e1ea15f`): 계약이 삭제 의미를 말하게 하고(Flux=uninstall vs ArgoCD=고아라 같은 의도가 엔진마다 반대 결과) argocd 렌더러가 resources-finalizer를 붙인다. **라이브 A/B**: 파이널라이저만 다른 Application 2개를 삭제 → 있는 쪽 소멸, 없는 쪽은 소유자 없이 Running. 덮지 않는 것: StatefulSet PVC는 남는다. 증거 `docs/evidence/phase2-deletion-cascade.log`.
- `make check` (pytest) → **1267 passed, 1 skipped** (2026-07-26, 1251→1267, +16) — **capability scope 축**(`bb7a819`): 카탈로그에 `scope: cluster|namespace`를 두고 delivery **계약**이 클러스터 싱글턴의 테넌트별 렌더를 거부한다(엔진마다 복제하면 세 번째 엔진이 빠뜨린다). 수집기는 공유 설치물을 테넌트 drift로 세지 않고(`applicable=False`), 안 보이면 MISSING이 아니라 UNKNOWN. 미선언은 cluster로 fail-safe. **라이브**: 직전 세션에 컨트롤러 충돌을 냈던 그 매니페스트를 argocd·flux 둘 다 거부, namespace scope 2개는 정상 렌더. 증거 `docs/evidence/phase2-capability-scope.log`.
- `make check` (pytest) → **1251 passed, 1 skipped** (2026-07-26, 1216→1251, +35) — **Phase 2 잔여 3건: ⑥ NetworkPolicy 실제 활성화 + push 기반 2축 drift 수집기 + 대시보드 tenant/env 스위처**(`3dbc572`·`b2b52fc`). ⑥이 막혀 있던 진짜 이유는 네임스페이스 부재가 아니라 **차트가 켤 수 있는 물건이 아니었던 것**(16개 데카르트 곱 vs 레지스트리 구독 6개, 설치하는 helm_release 없음) → 레지스트리 기반 렌더링으로 대체하고 집행이 증명된 기판에만 렌더. 수집기는 push 전용이라 허브에 스포크 read 자격증명이 0이고, 신원은 서명을 검증한 키다. **라이브(kind, $0)**: 정책 5개 + 격리 4종 통과 · 스포크→허브→대시보드 왕복 실증. `tsc` 클린 · `next build` 성공. 증거 `docs/evidence/phase2-{netpol-activation,push-collector-and-switcher}.log`.
- `make check` (pytest) → **1216 passed, 1 skipped** (2026-07-26, 1191→1216, +25) — **Phase 2 첫 슬라이스: soft-tier tenancy + Capsule**(`440f3a0`). ⑥이 기다리던 tenant 라벨 네임스페이스를 레지스트리에서 렌더·적용. 라이브가 3건을 잡았고 셋 다 거짓 보증 자리 — 특히 **Capsule은 admin이 만든 네임스페이스를 채택하지 않아** Tenant가 Active인데 NAMESPACE COUNT=0(쿼터가 아무것도 안 묶는데 정상으로 보임), 그리고 **쿼터 합산은 정적 조회로는 4배 버그처럼 보이지만** 소비하면 `limited: 6`(=16−10)으로 잔여가 재기록된다(설계는 옳았고 내 첫 결론이 틀렸다).
- `make check` (pytest) → **1191 passed, 1 skipped** (2026-07-26, 1168→1191, +23) — **capability step을 executor가 실제 소비**(`c4816fd`). 스키마가 표현하던 순서·조건·on_failure·per-step verify를 아무도 읽지 않던 갭 해소 + `CAPABILITY_RUNBOOKS`(9런북, 죽은 데이터였음) 연결. **유닛 테스트가 구조적으로 못 잡는 결함 1건 포함**: `_deserialise_decision`이 `steps`를 버려 executor가 조용히 flat 경로로 회귀 — 유닛 테스트는 객체를 메모리에서 만들어 직렬화 경계를 안 넘는다. 라이브 before/after: 필요 없는 노드 스케일아웃 → `executed=[restart] skipped=[scale] resolved=True`.
- `make check` (pytest) → **1168 passed, 1 skipped** (2026-07-26, 1159→1168, +9) — **Phase 1b 핸드오프 실행**(`7033db3`): rollouts-demo 소유권 TF→ArgoCD. 채택이 no-op이 아니었는데 원인은 라이브 드리프트(`--type=merge`가 컨테이너 배열 통째 교체)였고 ArgoCD가 **복구**한 것 → 프리플라이트 5번째 검사 `live-matches-rendered` 추가.
- `make check` (pytest) → **1159 passed, 1 skipped** (2026-07-26, 1114→1159, +45) — **① 게이트 완결(3종 판별) + ⑥ PSS/Cosign + ⑦ 스위퍼 CronJob**(`8e549bf`·`d96b888`·`69f149d`·`5015810`, **origin push 완료**). ①은 pass 경로를 여는 과정에서 **연쇄 결함 3건**이 드러나 전부 근본수정: (a) `llm.endpoint`를 router만 소비하고 webhook은 못 받아 **모든 판정이 unknown**이던 것(모델 부재가 아니라 배선 부재), (b) 템플릿이 firing 알럿을 **합성**해 보내 정상 canary가 conf 0.80으로 `fail`이던 것 → 호출자는 **신원만** 보내고 게이트가 Alertmanager를 직접 조회(`None`=못 봄 ≠ `[]`=조용함), (c) kps 파드 룰이 `for: 15m`이라 2~3분짜리 canary엔 발화 자체가 없어 크래시 canary도 pass이던 것 → canary 시간 스케일 룰 동봉. **라이브 3종 판별**: 정상→`pass`x3 abort 없음 / 크래시→`pass→fail→fail` **165s auto-abort**(stable 4/4, Available=True 내내) / 관측 불가→`unknown` 차단. ⑥ 양방향(비준수 설치는 API 서버가 4개 위반 적시하며 forbidden / 준수 설치는 `uid=10001` Running) + Cosign(서명은 **태그가 아니라 다이제스트**에 붙음을 라이브가 정정 → 차트 `image.digest`). ⑦은 CLI 부재가 `clean(exit 0)`이던 것을 **exit 2(coverage incomplete)** 로. 증거 `docs/evidence/onprem-{canary-agent-gate,pss-restricted-and-sweeper}-e2e.log`.
- `make check` (pytest) → **1114 passed, 1 skipped** (2026-07-26, 1095→1114, +19) — **① 2단계: 에이전트를 릴리스 게이트로**(`b9eafb0`). `canary_judge` + `POST /canary/judge` + `web` provider AnalysisTemplate. 판정 3규칙이 전부 안전한 방향 기본값(**저신뢰→unknown이 P1보다 우선**, `successCondition: result == "pass"`라 unknown은 승격 안 됨), 게이트는 **분석만**(execute=False). 라이브 부분: 이미지 재빌드→kind load→**인클러스터 `POST /canary/judge` 200**에 `verdict=unknown`(모델 부재 폴백) — "판단 불가 ≠ 승인" 실증. canary 전체 E2E는 미실행.
- `make check` (pytest) → **1095 passed, 1 skipped** (2026-07-26, 1058→1095, +37) — **TF→GitOps 핸드오프 프리플라이트**(`e48c5f6`) + **인시던트→Tempo 딥링크**(`90a92ba`). 프리플라이트는 `state rm` 전에 ownership·stateful·source-reachable·baseline 4검사로 안전성을 증명하고 롤백 명령을 선출력 — 라이브 read-only에서 **ownership 전 릴리스 통과**(최대 미지수 해소), 잔여 블로커는 스냅샷 부재와 미푸시 소스. 딥링크는 prod-safe(미설정이면 링크 없음) + 라이브 Tempo 200. 증거 `docs/evidence/gitops-handoff-preflight.log`.
- `make check` (pytest) → **1058 passed, 1 skipped** (2026-07-26, 1017→1058, +41) — **③ 사후검증 provider 실행부**(`d68fe6b`) + **Phase 1b delivery 어댑터 2개**(`738c812`). ③: `onprem_verify`가 액션과 **같은 스코프 자격증명으로** rollout status/readyReplicas/cordon을 읽어 `resolved`를 증거 기반으로. 라이브 양방향 — healthy→resolved=True / broken→**dispatched=True인데 resolved=False**(`docs/evidence/onprem-verification-e2e.log`). 1b: argocd/flux가 순서 원시형·상태 어휘·객체 형태 세 압박점을 각자 만족(wave→`sync-wave`/`dependsOn` = **TF `depends_on` 대체물**).
- `make check` (pytest) → **1017 passed, 1 skipped** (2026-07-26, 983→1017, +34) — **Phase 1a 자격증명 격리**(`0bb993f`, +24)와 **런북 전량 무력화 결함 근본수정**(`b078094`, +10). Phase 1a: `IncidentScope`+provenance 바인딩 `TokenBroker`(호출자 tenant 불신, attested 레코드로만 발급, nonce 1회용) + `NormalizedIncident.tenant/env` 1급 필드 + 실행 경로 scope 관통 + **ambient kubeconfig 삭제**. 라이브 DoD: **advisory 가드를 꺼도 API 서버가 `Forbidden`**(자격증명이 경계임을 RBAC로 증명). Decimal 결함: DynamoDB가 숫자를 `Decimal`로 반환해 `rto_sec`을 선언한 **모든 런북이 후보에서 탈락**→매 인시던트 알림-only 폴백이던 것을 읽기 경계 coerce로 수정(라이브 1/5→**5/5**, generic-recovery→**eks-pod-oom**). 증거 `docs/evidence/{phase1a-credential-isolation,runbook-decimal-rto-fix}.log`.
- `make check` (pytest) → **983 passed, 1 skipped** (2026-07-25, 876→983, +107) — **GitAIOps 실습서 대조 갭 6건 + 멀티테넌트 Phase 0**(`5fba0af`~`7b4231a`, 8커밋): ③런북 `verify` 슬롯+`resolution_verdict` 2축(검증 없으면 verified=None, 역호환) · ④권한통제 3단(포괄 `gcloud:*`→조회 allow 104+billable ask 30) + GKE TTL 워치독 · ①Rollouts AnalysisTemplate(수동 게이트에 가산, 기본 OFF) · ②OTel 4단계 span + `tracing.tf`(무-의존 폴백) · **Phase 0**(`platform/` 레지스트리+로더+`DeliveryAdapter` 계약+`NormalizedAddonStatus` 2축, py+ts) · ⑦고아 클러스터 스위퍼 · ⑥NetworkPolicy+CNI 집행 검증기(기본 OFF). `tsc` 클린 · `terraform validate` Success · **라이브 read-only**: 2 GCP 프로젝트 방치 클러스터 0건 확증. `helm template`이 Tempo 버그 2건 적발(포트 3100→3200, `resources` 위치). 상세 → `PROGRESS_LOG` 2026-07-25.
- `make check` (pytest) → **876 passed, 1 skipped** (2026-07-21, 870→876) — **대시보드 On-Prem 분석 Qwen 우선 + 인시던트 상세뷰 + 스택링크 + AWS데모 제거**(`4aef387`·`74d7a9d`·`7ca72ed`): analyzer LLM 백엔드 pluggable(ANALYZER_LLM_ENDPOINT=로컬 Qwen, 없으면 Bedrock·역호환) + 파서 견고화·어댑터 annotations·프롬프트 detail·confidence 영속화(+6). **라이브($0)**: OOMKilled→Qwen confidence 0.95+정확 root cause→INC-95C55A19 상세뷰. 인시던트 상세페이지 신설, 스택링크 Provisioning 이관(prod-safe).
- `make check` (pytest) → **870 passed, 1 skipped** (2026-07-20, 867→870) — **On-Prem 애드온 스택 Phase 5(로깅)**: `logging.tf`(loki 7.1.0 SingleBinary+캐시off + fluent-bit 0.57.9 DaemonSet) + grafana Loki 데이터소스. 가드 +3, 핀 3→5. **라이브($0)**: 파드 Ready→Loki query API가 `pa-platform-agent-webhook` 포함 다수 네임스페이스 로그 반환→Grafana Loki 데이터소스 등록 확인. 증거 `docs/evidence/onprem-addons-logging-e2e.log`.
- `make check` (pytest) → **867 passed, 1 skipped** (2026-07-20, 865→867) — **On-Prem 애드온 스택 Phase 4(Argo Rollouts)**: `rollouts.tf`(argo-rollouts 2.41.1 컨트롤러 + 데모 canary, 무기한 pause 수동게이트). 가드 +2, 핀 2→3. DECISIONS D19(러너 vs Rollouts 병존). **라이브($0)**: promote(blue→yellow, 게이트 60s→75%→100% stable)·abort(yellow→red 25%→Degraded, yellow stable 유지) 양경로. 증거 `docs/evidence/onprem-addons-rollouts-e2e.log`.
- `make check` (pytest) → **865 passed, 1 skipped** (2026-07-20, 233.46s, 861→865) — **On-Prem 애드온 스택 Phase 3(GitOps)**(`fafacc6`): `gitops.tf`가 ArgoCD `Application`(로컬 래퍼 차트, argocd depends_on)로 platform-agent 차트를 GitHub origin main에서 auto-sync·selfHeal 관리. `application.resourceTrackingMethod=annotation`으로 instance 라벨 추적 충돌 근본 회피, `releaseName=pa`로 Phase 2 접점 보존. 가드 +4. **라이브($0)**: apply→Synced/Healthy(rev=git HEAD)→6 리소스 무중단 채택→drift(scale 1→3)→selfHeal ~16s 복원. 증거 `docs/evidence/onprem-addons-gitops-e2e.log`.
- `make check` (pytest) → **861 passed, 1 skipped** (2026-07-20, 229.27s, 854→861) — **On-Prem 플랫폼 애드온 스택 Phase 1+2**: 신규 `infra/onprem/addons/` root(argo-cd 10.1.4·kps 87.17.0 핀, 저사양 values, kind·k3s 양기판) apply→전 파드 Ready→UI 3종 200 + Alertmanager receiver→in-cluster webhook 배선 라이브 E2E(crashme 크래시루프→룰 발화→배달→4-step→P2 승인→INC-96D41C2B resolved, $0). 가드 +7. 증거 `docs/evidence/onprem-addons-{phase1,alertmanager-e2e}.log`.
- `make check` (pytest) → **854 passed, 1 skipped** (2026-07-20, 256.62s, 수 무변경) — **리팩토링 후속 2건**(`8792c9c`): operations 그룹핑 cloud축 통일(`aws/`·`runners/` 신설, CDK 핸들러 경로 7종 정합) + approval_bridge 610줄 handler → 4모듈 분리(handler/request_store/slack_interactive/payloads). 순수 구조 개편(동작·테스트 수 무변경).
- `make check` (pytest) → **854 passed, 1 skipped** (2026-07-19, 232.03s, 847→854) — **On-Prem P2 승인 Slack 버튼 연동**(`617839b`): DynamoDB 공유 매체+옵트인 폴러, 라이브 왕복(P2 parking→Slack ONPREM 카드→Approve 클릭→APPROVED→폴러 실행→INC-FA2143AF resolved, 증거 `docs/evidence/onprem-slack-approval-live.log`). **동일자 terraform aws-production 실 apply→검증→destroy 완주**(코드 무변경): EKS 노드 2 Ready·Aurora `platform_state` available·IRSA trust 재배선 확증 후 29개 destroy·잔존 0·≈$0.5 미만(증거 `docs/evidence/terraform-aws-production-apply-live.log`) — #7-b 전 단계 실증 완결.
- `make check` (pytest) → **847 passed, 1 skipped** (2026-07-19, 232.55s, 844→847) — **Slack E2E발 후속 2건 근본수정+라이브 검증**: (a) **Bedrock 무효 모델 ID**(`9a56949`) — 스택이 `.env` 무시·무효 ID 하드코딩으로 매 인시던트 휴리스틱 폴백 강등되던 latent 결함 → `us.anthropic.claude-sonnet-4-6` 프로파일+정확-ARN IAM(프로파일+3리전 하위 모델), 라이브 `analyzer.llm_done`(실 Claude root cause가 Slack 카드에 표시). (b) **유령 SSM 문서**(`55de55e`) — `AWS-SendSlackAlert` 미실존으로 generic-recovery 구조적 `resolved=False` → `_NOTIFICATION_ACTIONS` in-process 1급 처리(+3 test), 라이브 실 LLM **P1/AUTO** 판정→`executor.notify.in_process`→**`resolved=True`**(INC-E15BA62E, DynamoDB 확증). 동일 세션에서 P3/MANUAL·P2/APPROVE 경로도 관측(LLM 심각도 3단 실증).
- `make check` (pytest) → **844 passed, 1 skipped** (2026-07-19, 234.56s) — **Slack App 실 생성 + 인터랙티브 승인 버튼 라이브 E2E 완주**: 알람 ALARM→SFN WaitForApproval→Slack `#platform-test` 버튼 메시지→**Approve 클릭**(브라우저)→서명 검증→DynamoDB claim(APR-8BC7E7E95B9A=APPROVED)→`SendTaskSuccess`→SFN **SUCCEEDED**(INC-2AC4B6C9). 라이브가 표면화한 프로덕션 버그 2건 근본수정(`0f99420`): (a) detector `_SIGNAL_ADAPTER` NameError=AWS 경로 전면 불능→`get_signal_adapter("aws")`+AWS 경로 회귀 가드, (b) approval_bridge confidence float→DynamoDB TypeError=승인 요청 전량 소실→`Decimal`+e2e 페이크에 float 거부 계약. 증거 `docs/evidence/slack-interactive-approval-live.log`.
- `make check` (pytest) → **843 passed, 1 skipped** (2026-07-18, 236.08s) — **OAuth 대시보드 배포 트리거 라이브 E2E + 프로덕션 장애 2건 근본수정**: (a) `.vercelignore` 무앵커 `src/`가 git 트리거 Vercel 배포를 전부 404 빌드로 만들던 결함 수정(canonical 200 복구), (b) CloudTrail로 07-11 **Vercel OIDC provider 삭제** 규명→CDK로 재생성(실 slug `men16922s-projects`)+정확-ARN `StartExecution` grant→대시보드 **DEMO FALLBACK→LIVE·AWS** 복구, (c) 라이브 클릭이 표면화한 `smoke_tester` `base_url` KeyError 수정+가드(+1 test). **E2E**: GitHub OAuth(operator)→Start Release→SFN `deploy-dep-1f054864` **SUCCEEDED**. 증거 `docs/evidence/oauth-deploy-trigger-live.log`.
- `make check` (pytest) → **842 passed, 1 skipped** (2026-07-17, 234.42s) — **차트 stateStore 배선(④↔#7 마무리)**: `stateStore.{dsn,existingSecret}` values(secretKeyRef=프로덕션·plain=dev, secret 우선), persistence off→RollingUpdate·replicas>1 해금, Dockerfile `.[state]`(psycopg2) 재빌드 검증. 차트 가드 +3. JSONL 기본값 무변경. **k3s substrate 스모크(동일자, 코드 무변경)**: 기존 k8s-lab VM에 helm install→`local-path` PVC Bound→P2 승인 루프→원상 복원 — env×substrate 양축(kind/k3s) 실증 완결(`docs/evidence/helm-k3s-substrate-smoke.log`).
- `make check` (pytest) → **839 passed, 1 skipped** (2026-07-17, 238.51s) — **레퍼런스 #7-b Terraform 모듈 → #7 전체 완결(Helm+Terraform)**: 신규 `infra/terraform/aws-production/`(VPC·EKS 1.31·**Aurora Serverless v2 `platform_state`**=④ DSN seam 정합·**IRSA**=차트 SA 전용 trust+DynamoDB activity 테이블 정확-ARN 유일 grant). Redis/Cognito=미소비 의도적 제외. `terraform init+fmt+validate` Success(spend 0, **apply 안 함**=사용자 게이트). 가드 +5(bare `"*"` 금지 등). 이로써 AWSome 레퍼런스 8항목 전부 소화.
- `make check` (pytest) → **834 passed, 1 skipped** (2026-07-17, 242.90s) — **로드맵 ④ SQL State Store(옵트인)+실 Alertmanager 라이브**: 신규 `state_store.py`(`PLATFORM_STATE_DSN` 옵트인, DB-API 주입식, append-only+latest-wins=JSONL 시맨틱 동일, sqlite 오프라인 테스트 +5) + approvals/incidents 양방향 배선. **라이브(docker $0)**: 실 Alertmanager grouping→배달→P2 parking→PostgreSQL, **레플리카 2개 상태 공유**(replica-2 승인→replica-1 즉시 반영=JSONL 불가), 전 프로세스 재기동 생존, psql ground-truth 3 rows. 증거 `docs/evidence/state-store-alertmanager-live.log`. JSONL 기본값 무변경(비오염 테스트 양방향).
- `make check` (pytest) → **829 passed, 1 skipped** (2026-07-17, 263.50s) — **레퍼런스 #7-a On-Prem Helm 차트+이미지**: `infra/helm/platform-agent/`(webhook 기본 on·router opt-in·최소권한 RBAC 4조치 동사 열거·drain 별도 ClusterRole 기본 off·PVC 단일-writer·env×substrate values kind/k3s) + `infra/onprem/Dockerfile`(kubectl 내장 2엔트리포인트). 가드 +6(helm lint·RBAC `"*"` 금지·프로브 분리 등, helm 미설치 시 skip). **이미지 실빌드(881MB)+컨테이너 스모크**(`/health`·`/health/ready` 200). 부산물: **`pyproject.toml` optional-dependencies PEP 621 위반 latent 버그 수정**(이미지 빌드가 표면화). **kind 라이브 실증 완료(동일자)**: 전용 pa-helm 클러스터 helm install→pod Ready(strict readiness in-cluster)→RBAC can-i allow/deny 분리 실증→Alertmanager→P2 승인 게이트→execute→incident→PVC 영속성(pod 재시작 생존)→전량 teardown·GKE 컨텍스트 불가침. 증거 `docs/evidence/helm-kind-live-install.log`. 잔여=#7-b Terraform 모듈(클라우드).
- `make check` (pytest) → **823 passed, 1 skipped** (2026-07-17, 230.48s) — **⑦ 라이브 모델 스윕 실 실행 완료(로컬 MLX, spend $0) → 승인 큐 8항목 전부 완료(코드+실행)**: `scripts/live_model_sweep.py`가 shipped `live_router_factory`+`run_sweep`을 실 mlx_lm.server 상대로 160 라이브 호출(2모델×2 effort×20케이스×프롬프트 v1/v2, backstop 발화 0, resume 병합 실증). **라이브 런이 `_classify_prompt` 결함 표면화**(v1이 teardown을 provision으로 기술 → teardown→deploy cascade 모순, 전 config 동일 adversarial 2건 미스) → v2 재작성 → 전 config 개선(7B/low 0.80→**1.00**·30B 0.80→0.95) → 회귀 가드 +1. **증거 기반 선택: Qwen2.5-Coder-7B @ temp0 = 20/20·0.20s/success — 30B보다 정확·빠름**(정적 "큰 모델" 주석 반증). 증거 `docs/evidence/model-sweep-live.log`.
- `make check` (pytest) → **822 passed, 1 skipped** (2026-07-17, 261.76s) — **⑦ 라이브 어댑터 코드 완료**: `model_sweep.live_router_factory(call_model, backstop=)`(모델 응답→role 파싱·latency 측정·미파싱/실패 시 결정론 백스톱, `run_sweep` 드롭인). 모델 호출은 주입식이라 오프라인 테스트(+3).
- `make check` (pytest) → **819 passed, 1 skipped** (2026-07-17, 243.21s) — **승인된 실행 큐 소진(사용자 "전부 다"): ⑧-1/2/3 + ⑨ A/B 7묶음**: ⑧-3 `ROLE_ALLOWED_ACTIONS` 위임 힌트+`action_sink_grader` 단일소스 · ⑨A-1/A-2 SSE `id:`dedup·`ready`센티넬·heartbeat · ⑧-1 `metadata.task` 구조화 디스크립터 · ⑨B-1 신규 `memory_tier.py`(signature·scrub·distill·MemoryStore) · ⑧-2 `Supervisor(confidence_router=)` 옵트인 저-confidence 게이트 · ⑨B-2 recall+`augment_instruction` 옵트인 `memory=` seam(조언적) · ⑨B-3/A-3 `consolidate`/`dominant_failures`+SSE `agent`필드. 전부 비파괴(옵트인 DI·additive·SSE 하위호환), +23 test(796→819). **잔여=⑦ 라이브 스윕(실 API 과금·사용자 게이트)**.
- `make check` (pytest) → **796 passed, 1 skipped** (2026-07-17, 231.96s) — **⑧ 안전 서브셋+⑧-4: A2A 위임 하드닝**: `supervisor.sanitize_instruction`(control-char strip[tab/newline 유지]·4000자 cap·적용 transform trace) + `handle` 아웃바운드 배선(분류는 원문 유지)·`trace` 타입주석 정정. **⑧-4(완료)**: `ARCHITECTURE.md`에 TOOL→SKILL→SUBAGENT smell-test + 위임 안전 불변식 명문화 + 회귀 가드(supervisor는 mutating provision/deploy를 in-process 실행 안 함, 반드시 A2A 위임). 계약/동작 변경 3건(구조화 페이로드·저-confidence 게이트·최소권한 힌트)은 `docs/plans/a2a-delegation-hardening.md`=**승인 대기**. 비파괴 +6 test(790→796).
- `make check` (pytest) → **790 passed, 1 skipped** (2026-07-17, 218.92s) — **⑦ 오프라인 모델 스윕 스캐폴드**: 신규 `src/agents/ai/model_sweep.py`(eval_harness 위 증분, 실 API/과금 0). `SweepConfig`(model×thinking×effort)·`grid`·`run_sweep`(config별 dataset 채점→**cost_per_success/seconds_per_success** headline, `trials` self-consistency, **resumable** done-dedup)·`SweepPoint`(0성공=inf, to/from_dict 영속)·`rank/best/scoreboard`. LLM 백엔드=`router_factory` 주입(테스트=결정론 mock), 라이브 배선+실 spend=사용자 게이트. +11 test(779→790).
- `make check` (pytest) → **779 passed, 1 skipped** (2026-07-17, 232.74s) — **⑤ eval 하네스 성숙(선언적 멀티-grader 스코어카드)**: 단일-judge `grade()`/`EvalReport` 경로 무변경 위에 비파괴 증분 — 선언적 `Grader`(name+`kind:code|judge`)로 명명 메트릭 다중(role/budget/action_sink/judge), `Verdict` 3-상태(PASS/FAIL/**PASS_SLOW**=정답이나 예산초과), **action-sink grader**(read-only role이 mutate=FAIL, per-role allowed 정책=blast-radius 안전), 리치 `Observation`(decision+latency+actions)·`observing()` 브리지, `Scorecard.delta/regressions`(pinned-baseline 회귀 diff), `score(trials=N)` majority vote(self-consistency 재사용). +12 test(767→779).
- `make check` (pytest) → **767 passed, 1 skipped** (2026-07-17, 227.82s) — **⑥ eval 데이터셋+judge 하드닝**: `ROUTING_EVAL_SET` 13→**20**(카테고리 균형 + **adversarial 네거티브 5**로 precision 채점). eval가 실 라우팅 over-trigger 갭 2건 표면화("Deploy the observability stack"→KAGENT 오분류·"Investigate why the terraform apply failed"→PROVISION 오분류) → `classify_request`를 first-substring-wins에서 **precedence**(진단동사>provision>delivery-guarded 명사, 과광범 `observability` 트리거 제거)로 재설계 → 회귀가드로 전환(기존 supervisor/orchestration classify 단언 회귀 0). judge 반-관대: `_build_judge_prompt` 재작성(read-only/mutating 경계·FAIL-when-unsure) + `calibration_probe`(파괴적 provision→read-only kagent canary; PASS/에러/미파싱=관대·불신) + `llm_judge(calibrate=True)` 강등 + 빈문자열/"모름" 결정론 백스톱 테스트. +9 test(758→767). 발견→수정→가드 루프 재실증.
- `make check` (pytest) → **758 passed, 1 skipped** (2026-07-17, 233.81s) — **eval 하네스 스파이크(④)**: 신규 `src/agents/ai/eval_harness.py`(클라우드-중립·오프라인 decision-quality 평가: 라벨 데이터셋+injectable Router/Judge, `llm_judge`=LLM-as-judge with 결정론 백스톱, `EvalReport` 회귀 가드, 빌트인 `ROUTING_EVAL_SET`) +10 test. Google Agent 생태계 3자료(ADK 2.0·A2A·agents-cli) 대조의 유일 코드 후속. 결정론 classifier 스파이크에서 실제 라우팅 갭 2건(cluster-creation 동사 미커버) 표면화 → `classify_request` 수정(cluster+생성동사 조합, 회귀 0) → eval set 13/13, 갭=회귀가드. 발견→수정→가드 루프 실증. 나머지 후속 ①아티클 포지셔닝(EN+KO 수렴 섹션)·②context 격리 감사(델타 아님)·③버전 트래킹(A2A stdlib-only 규명)은 코드 무변경.
- `make check` (pytest) → **748 passed, 1 skipped** (2026-07-17) — **repo 구조·소스 리팩토링(런타임 동작 무변경)**: 유령 패키지 5개 삭제(`executor`/`detector`/`decision`/`analyzer`/`approval_bridge`, import 0)·`.terraform` 16MB 추적해제 + `operations/_executor_common.py`(gcp/azure executor ~150줄 중복 추출)·`_executor/_k8s_rest.py`(runner restart/scale 공유) + **post_webhook 오호출 버그 수정**(gcp/azure Slack 리포트 무전송 → 정정). docs: README↔DOCS_POLICY skills 병합·stale 10개 제거. baseline 수치 유지, 커밋 4개 미푸시.
- `make check` (pytest) → **748 passed, 1 skipped** (2026-07-15) — **아키텍처 잔여 로드맵 2건 구현**: ② supervisor 프론트도어(`local_deploy_api` `/api/local-deploy` 분류→A2A 위임/in-process 폴백, 비파괴) + ① deploy↔runtime 정면 배선(DeployPipeline opt-in `host` 스텝, approval-gated preflight/create, onprem skip). +7 test. 코어 아키텍처 배선 로드맵 소진(잔여=인프라/아스피레이셔널/사용자).
- `make check` (pytest) → **741 passed, 1 skipped** (2026-07-15) — **대시보드 신규 관측 3종 노출 + orchestrator 활동 기록 배선**: `cost_metrics`(배포상세 패널)·`reconciliation`(인시던트 강등 배지, AWS `_record_incident` 파리티)·`consensus/steps`(activity trace). `record_route_activity`가 orchestrator 라우팅 런을 `type=route` ACTIVITY(consensus/plan trace)로 기록→대시보드 표시. 대시보드 `next build` 성공. 로컬 E2E로 route 활동 기록 확인.
- `make check` (pytest) → **738 passed, 1 skipped** (2026-07-15) — **Tier 2 #4 크로스계정 소비자 배선**: `deployment/aws.py`(CodeBuild)·`executor/handler.py`(SSM primary+failover `_ssm_client`)이 `assume_role_session(env-role)` 소비(env 미설정=in-account 무변경), +2 test. + 종합 아키텍처 아티클 `docs/post/platform-agent-architecture.md`.
- `make check` (pytest) → **736 passed, 1 skipped** (2026-07-15) — **레퍼런스 Tier 2 #3: MCP-over-HTTP 커넥터 + per-tool/글로벌 kill-switch → Tier 2 전체 완결**(#2·#3·#4). `mcp_server.py`에 `remote_mcp_tool()`(원격 MCP 서버 JSON-RPC `tools/call` intercept→reinject, 전송실패 degrade) + `MCPServer` kill-switch(`call_tool` 게이트, `disable_tool`/`set_kill_switch` + `MCP_DISABLED_TOOLS`/`MCP_KILL_SWITCH` env). 원격 커넥터도 동일 kill-switch 지배. +13 test, 비파괴(기존 gateway 29건 무변경). ARCHITECTURE 표 row#3 ✅.
- `make check` (pytest) → **723 passed, 1 skipped** (2026-07-15) — **레퍼런스 Tier 2 #4: cross-account STS AssumeRole + graceful fallback**(신규 `adapters/aws_session.py`, +9 test). `assume_role_session(role_arn, fallback=True)`: STS assume_role→타깃 계정 세션, 실패/서킷-OPEN 시 in-account 크레덴셜로 우아하게 강등(Tier 1 `CircuitBreaker` 재사용). `runtime/aws.py` `_client`가 `AWS_ASSUME_ROLE_ARN` 옵트인 소비(미설정=무변경). ARCHITECTURE 표 row#4 ✅.
- `make check` (pytest) → **714 passed, 1 skipped** (2026-07-15) — **레퍼런스 Tier 2 #2: agents-as-tools 오케스트레이션 + self-consistency**(신규 `orchestration.py`, +12 test). `route_with_self_consistency`(N-샘플 majority vote·저합의 시 결정론적 `classify_request` 폴백=reconciliation 철학) + `Orchestrator`(consensus→plan→각 step을 기존 `Supervisor.handle`로 위임=specialists-as-tools·실패 short-circuit·shared contextId). `a2a_server` 옵트인 배선(`SUPERVISOR_ORCHESTRATION`, 기본 무변경). ARCHITECTURE 표 row#2 ✅.
- `make check` (pytest) → **702 passed, 1 skipped** (2026-07-15) — **AWSome AI Gateway 레퍼런스 Tier 1 반영(4종, +30 test)**: (1) **Reconciliation gate**(`reconciliation.py`, analyzer 결론 미근거 시 AUTO→APPROVE 강등, decision handler 배선), (2) **비용 3단계 게이트**(`cost_estimator.evaluate_budget`, OK/SOFT_WARNING/THROTTLE/HARD_BLOCK), (3) **회복탄력성**(`circuit_breaker.py` + webhook `/health/ready` 503 vs `/health` 200), (4) **비용 서브메트릭**(`deploy_recorder._cost_metrics`). `docs/ARCHITECTURE.md`에 도입 매핑표. **Vercel 대시보드 영구 안정화**: `ssoProtection` 해제 → canonical URL `platform-agent-men16922s-projects.vercel.app` 공개 200(git push 무관). **대시보드 agent tool list** 백엔드 카탈로그(13개)와 정합(`26586b5`).
- `make check` (pytest) → **672 passed, 1 skipped** (2026-07-14) — **Provision 어댑터 `node_size` 지원**(GKE `--machine-type`/AKS `--node-vm-size`, 제한구독 대응, +2 test) + **AKS 실 클러스터 라이브**(어댑터 provision k8s 1.35.6 1노드 Ready→teardown). GKE preflight 라이브(create는 하네스 자동차단, AKS가 동일 패턴 실증). 전 커밋 origin push 완료(HEAD `6ad7f82`).
- `make check` (pytest) → **670 passed, 1 skipped** (2026-07-14) — **Agent Runtime 호스팅 어댑터 3종**(신규 `adapters/runtime/`: AWS AgentCore(boto3)·GCP Agent Engine(vertexai)·Azure Foundry(azure-ai-projects **v2**), plan-first/approved-gated·읽기전용 preflight·teardown 승인 강제, +21 test). **3/3 클라우드 실 배포 라이브 E2E 완결**: 어댑터 create→READY/DEPLOYED/v1→invoke/query/Responses(실 Claude/Gemini/gpt-5.4-mini 응답)→teardown, 즉시 삭제(각 <$0.50). **azure 어댑터 v1→v2 결함 수정**(설치 SDK 2.3.0 불일치→재작성). 패키징/문서: `infra/agentcore/`(arm64)·`infra/agentengine/`(custom-template)·`infra/foundry/README.md`.
- `make check` (pytest) → **649 passed, 1 skipped** (2026-07-14) — **provisioning 어댑터 4-provider parity**(신규 GCP/Azure GKE·AKS: plan-first/approved-gated·읽기전용 preflight·teardown 승인 강제·tool preflight-only, +13 test) 포함.
- `make check` (pytest) → **636 passed, 1 skipped** (2026-07-14) — On-Prem 실 executor **scale**(양수 타깃, kind 2→5 라이브) + **polite drain**(--force 없음·PDB 존중, 3노드 kind 라이브 재배치·아웃티지0) + 인터랙티브 에이전트 **단일 카탈로그**(drift-0 불변식) + A2A Phase 2/PROVISION 격리 + On-Prem PATH B webhook/승인 게이트/인시던트 스토어 포함.
- `make check` (pytest) → **600 passed, 1 skipped** (2026-07-12) — AI Model Router / Pydantic AI On-Prem 에이전트 / MLX proxy / deploy recorder(+cascade) / ops_tools / provisioning 어댑터 테스트 포함


---

## 2026-08-02까지의 baseline (STATUS에서 밀려남, 2026-08-08 정리)

- `make check` (pytest) → **1617 passed, 1 skipped** (2026-08-02, +3) — **푸시 읽기 신원**:
  push 인증은 **이미 완료**였고(계획이 일주일째 스테일), 실제로 열린 건 **스포크의 읽기**다 —
  맨 kubectl + 공유 `argocd` ns라 테넌트 구분이 **코드 필터**다. 쓰기는 허브가 401로 막는다
  (라이브 4종). 시끄럽게만 해 둠. 증거 `docs/evidence/push-identity-ambient.log`.
- `make check` → **1614** (2026-08-02, +6) — **결정 6 = D42**: 승인
  재사용을 **TTL로 묶었다**(서명이 덮는 `issued_at`, 기본 900초, 끄는 스위치 없음). one-time-use는
  **틀린 수정**이었다(실행기가 같은 인시던트로 두 번 해석). 라이브: 만료·미래 스탬프·시각 위조
  전부 거부, TTL 안 재사용은 **가능하고 그렇게 적었다**. 증거
  `docs/evidence/approval-ttl-replay-bound.log`.
- `make check` → **1608** (2026-08-02, +1) — **결정 3 = D41**: Capsule `limitRanges`를 대체 없이
  **객체 직접 렌더**(→ Risk 9). 라이브 3단(Capsule 회수 · 없으면 `must specify limits.cpu`
  Forbidden · 전체 리싱크 생존), 경고 2→**0**. 증거 `docs/evidence/capsule-limitranges-direct.log`.
- `make check` → **1607** (2026-08-01, +2) — **결정 4 = D40**: k3s는 proven 기판에 넣지 않는다
  (→ Risk 5). 가드 `tests/test_substrate_promotion_reachable.py`.
- `make check` → **1605** (2026-07-31, +9) — **무스코프 MCP 읽기 차단**(D39): 근거 **"익명
  kagent 왕복이 이걸 쓴다"가 사실이 아니었다**(`src/`에 `MCPServer` 생성자 0 → 그 경로를 돌리던
  유일한 코드는 **그것을 고정하던 테스트**). `resource`가 자유 문자열이라 반경은 ambient
  =cluster-admin이었다(라이브 `secrets -n kube-system`·`nodes` 성공 → 차단). 증거
  `docs/evidence/unscoped-mcp-read-closed.log`.
- `make check` → **1596·1572** (2026-07-30~31) — **결정 5 A·B**(D38, 배포 신원 축소 + 스코프
  생산자, **둘 다 옵트인**) + 그 조사(**생산자 없는 메커니즘은 테스트에서 영원히 초록**).
  증거 `docs/evidence/{deploy-identity-reduction,scope-producer-live,deploy-path-authorization}.log`.
- `make check` → **1565·1552·1544** (2026-07-29~30) — M13의 마지막 셋: 배포 네임스페이스
  출처(D37, 라이브에서 `rollout undo -n default`가 **엉뚱한 워크로드를 되돌리고 성공을 보고**) ·
  tier 발명 제거(D36) · 리포트 창(`ttl`을 시각으로, 90→2, **라이브 미실행**).
  상세 → `COMPLETED_SUMMARY` M13.
- (이전 이력: gate **1533** 이하 · 2026-07-10~29 → **이 파일 위쪽 섹션** 및
  `docs/archive/progress-2026-07.md` · `docs/archive/progress-2026-08.md`.)


---

## 2026-08-08 baseline 중 STATUS에서 밀려난 것 (2026-08-08 정리)

- `make check` (pytest) → **1636 passed, 1 skipped** (2026-08-08, +18) — **서명키 회전**:
  결함은 암호가 아니라 **배포 위상**이었다 — 서명자와 검증자가 다른 프로세스인데 키가 하나라
  교체가 원자적일 수 없고, 그 실패가 `failed attestation`(=위조로 읽힘)이라 **회전은 장애
  아니면 오경보**였다. `PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING`(검증 전용, 절대 서명 안 함) +
  **겹침을 유한하게 만드는 건 D42의 TTL**. 반증 4종 red(특히 retiring 레코드에 TTL 미적용).
  **custody는 미해결이고 거짓 주장도 아니다**(→ `STATUS` Risk 3).
  상세 → `archive/progress-2026-08.md`("서명키는 회전할 수 없었다").
- `make check` (pytest) → **1618 passed, 1 skipped** (2026-08-08, +1) — **테스트가 상했다**:
  `test_incident_time_to_resolve.py`는 **수정된 적이 없는데** red가 됐다. 픽스처가
  `created_at`을 하드코딩(`2026-07-29`)하는데 생산자는 **살아 있는 시계**로 7일 창을 건다 →
  **08-05에 이미 깨져 있었다**. `now` 기준 상대 배치로 교체 + 가드 1건.
  **게이트 숫자에는 측정 날짜가 붙어야 한다** → `STATUS` Risk 12①.
  상세 → `archive/progress-2026-08.md`("달력이 움직이자 red가 됐다").
- **실 AWS 왕복**(2026-08-08, gate 무관 — 프로브) — 인시던트 속성 6종이 실 `incident-history`를
  왕복해 **타입까지 보존**됨. `confidence`=`Decimal`(DynamoDB N)이라 대시보드의
  `typeof === "number"`가 참이 된다. **모킹으로는 원리상 못 잡는 검증**(목은 float를 받고,
  실제로는 boto3 예외가 `except`에 잡혀 행이 통째로 사라진다).
  `scripts/probe_incident_roundtrip.py` · 증거 `docs/evidence/incident-fields-dynamo-roundtrip.log`.

- `make check` → **1668** (2026-08-08, +17) — **Phase 5 경계**: 헤더가 Phase 0부터 "이 흐름은
  오직 이 파일만 PR한다"고 적어 뒀는데 **반증할 수단이 0**이었다. 반증 4종 red.
  ⚠️**안전망을 통째로 지워도 14개가 초록**이었다 — 전부 행복 경로만 태웠다(→ `STATUS` Risk 12③).
  상세 → `archive/progress-2026-08.md`("Phase 5의 경계부터").
- **실 AWS 왕복**(2026-08-08, gate 무관 — 프로브) — 인시던트 속성 6종이 실 `incident-history`를
  왕복해 **타입까지 보존**됨(`confidence`=`Decimal`). **모킹으로는 원리상 못 잡는 검증**이다.
  ⚠️**남은 한 칸(열린 항목)**: 대시보드 TS 리더 미검증.
- **CI와 로컬이 이제 같은 숫자다 — 그 전엔 아니었다**(2026-08-08) — CI **1666/3** ↔ 로컬
  **1668/1**, 넘어간 둘이 하필 terraform 검증이었다(`.terraform/`가 gitignore라 **설치만 해도
  skip**). 교훈은 `STATUS` Risk 12②, 증거는 `docs/evidence/ci-terraform-validate-skipped.log`.
- `make check` → **1676** (2026-08-08, +8, 로컬·CI 일치) — **커밋을 경로에 한정**:
  `attach_addon.py`가 시키던 `git commit -am`은 **수정된 모든 추적 파일**을 담아, "한 파일만"
  불변식을 세우려는 도구가 **자기 지시로 그걸 깨는 경로**를 들고 있었다. 반증 3+2건 red.
  ⚠️**깨끗한 트리에선 `-a`와 `-- <path>`가 구별되지 않는다** — 가드는 **일부러 더럽힌 채** 잰다.
- `make check` → **1685** (2026-08-09, +9, 로컬·CI 일치) — **managed 백엔드를 세 경로가 다르게
  알고 있었다**: 읽기는 알아보고, 쓰기는 만들 수 없고, **렌더는 몰랐다**(백엔드를 Helm 차트
  이름으로 넘겨 `logging: cloudwatch-logs`가 Grafana 저장소에서 그 차트를 찾게 된다).
  `ManagedBackendNotRenderable`로 거부. 막히지 않는 조합은 **네임스페이스 스코프 + managed**뿐.
