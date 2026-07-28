# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-28

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M10=GitAIOps 7/7+멀티테넌트 Phase 0·1a·1b+공급망,
> M9=eval·하드닝, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 (2026-07-28, gate 1446)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **차단 없는 잔여 소진**. 남은 잔여는 작업이 아니라 **결정** 3건.
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.

## 사용자 게이트 (열린 것만)

- [ ] **⚠️ 결정 1: "배포는 어느 테넌트 소유인가"** — deployments/activities 파티션과 **모델 호출
  rate limit을 동시에** 막고 있다(아래 두 항목 참조). 발명 금지라 결정 없이는 둘 다 진행 불가.
- [ ] **⚠️ 결정 2: 무스코프 MCP 읽기를 닫을 것인가** — 닫으면 검증된 익명 kagent 왕복이 깨진다.
- [ ] **⚠️ 결정 3: Capsule `limitRanges` 이관 경로** — 클러스터 스코프(D30 위반) vs 새 SA+RBAC.
- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=책의 GitAIOps는 AI 자리에 사람이 프롬프트를 넣지만
  우리는 **오프라인 Qwen 에이전트로 루프를 무인으로 닫는다**. 차별 소재는 **자동화하면 새로 깨지는 것들**:
  ①롤백↔selfHeal 충돌 ②자격증명=blast radius ③"실행됨≠나아졌음" ④권한 게이트 부재의 과금 누출.
  **새 소재**: "선언은 됐는데 아무도 소비하지 않는 코드"가 반복해서 나왔고 전부 테스트는 초록이었다 —
  라이브 실행만이 소비 부재를 드러냈다(2026-07-28에 세 건 더: grant·런북 티어·Capsule 필드).
  **집필·발행은 이 계획에만 남기고 착수하지 않는다**(사용자 지시 2026-07-25).
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0라 유지 중.

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5 = S 93.5) ·
**의사결정·MAD 히스토리**: `docs/plans/2026-07-21-multi-tenant-env-addons-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책(soft/vcluster/dedicated),
Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: 에이전트 실행 blast radius=1 tenant/env(자격증명이 경계) — Phase 1a에서 강제 완료.

- [x] **Phase 2 완결(M11, gate 1290)** · **Phase 3 완결(M12, gate 1411)** — 상세 → `COMPLETED_SUMMARY.md`.
- [x] **Phase 3 ①②③ + 인시던트 파티션·granted-viewer(gate 1355→1411, 2026-07-27~28)** —
  상세는 `COMPLETED_SUMMARY.md` M12 및 `docs/evidence/phase3-*.log`.
- [ ] **deployments/activities 파티션 — 데이터 모델 결정 필요(버그 아님)** — 인시던트는 tenant가
  *있는데 버려진* 것이었지만, 배포 기록은 `provider/service/version/environment`뿐이고
  `environment`는 레지스트리의 tenant/env 쌍이 아니라 자유 문자열("production")이다.
  **배포는 어느 테넌트 소유인가**를 먼저 정해야 한다 — 발명하지 않고 남긴다.
- [x] **grant 레지스트리 대조(gate 1425, 2026-07-28)** — 기록된 갭은 절반이었다: grant를
  **줄 방법 자체가 없었고**(라우트·스토어 둘 다 `tenants` 미수용) 역할 변경이 whole-item
  Put으로 grant를 조용히 지웠다. 허브 `GET /api/platform/tenants`(못 읽으면 **503**) +
  저장 전 대조 + `absent=유지`. 증거 `docs/evidence/phase3-tenant-grant-validation.log`.
- [ ] **Phase 4**(managed 어댑터, billable)·**5**(레지스트리 PR 쓰기) = 다음 후보.
  Phase 5가 열리면 3②를 GitOps-native로 다시 닫을 수 있다(D32 재검토 조건).
  **Phase 4로 넘긴 것(명시)**: GCP/Azure 자격증명의 테넌트 바인딩. 현재 GCP는 프로젝트 전역 신원,
  Azure는 ARM에서 **cluster-admin kubeconfig**를 받아온다 — 스코프는 네임스페이스만 좁힌다.
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 기본 부재).
  rollouts-demo는 데이터 위험 0이라 먼저 했고, 나머지 셋은 실패 비용이 가용성이 아니라 데이터다.
- **S 달성(93.5) 근거**: ①실행위치=in-cluster 러너 ②token broker=incident provenance 바인딩
  ③read=push(허브 read 자격증명 0). **2차 잔여**: agent→hub push 인증 · 서명키 custody·rotation ·
  push heartbeat(staleness).

## 잔여 — 완료 항목에서 의도적으로 남긴 것

- [x] **② executor span(gate 1454, 2026-07-28)** — 기록보다 넓었다: 웹훅이 `execute=False`로
  부르고 **루트 span이 닫힌 뒤** 실행해서, AUTO·승인 **양쪽 모두** executor span이 없었다.
  span을 `execute_incident` 안으로 이동 + 웹훅 루트 2개 + 승인은 **부모가 아니라 링크**
  (사이 간격이 사람의 고민 시간이라 접으면 지연 수치가 무의미해진다).
  증거 `docs/evidence/executor-span-approval-path.log`.
- [ ] **선택 가능해진 런북 4개가 온프렘 알람엔 안 걸린다**(위 라이브 중 발견, 회귀 아님) —
  온프렘 디텍터가 모든 Alertmanager 알람을 `namespace=ONPREM/kubernetes-workload`·
  `metric_name=availability`로 정규화해서 **alertname이 매처에 닿지 않는다**. 네 런북은
  CloudWatch 네임스페이스/메트릭 이름 기준이라 온프렘에선 root_cause 텍스트로만 매칭된다.
  "온프렘 alertname을 매처에 넣을 것인가"는 매칭 설계 결정이라 발명하지 않고 남긴다.
- [ ] **⑥ k3s 검증기 재실행**(선택) — flannel은 NetworkPolicy 집행이 전이되지 않으므로 기판별 재확인 필요.
- [x] **선택 불가 런북 4개 + 티어 셰도잉(gate 1445, 2026-07-28)** — BUILTIN 항목을 넣어도
  **라이브는 넷 다 generic-recovery**였다: 시드 테이블에 generic 행이 있어 티어 2가 티어 4의
  답을 대신 냈고 **티어 3(빌트인)이 배포 환경에서 한 번도 도달된 적 없었다**.
  `allow_generic=False` + `assert_health_check_passing` 구현.
  증거 `docs/evidence/runbook-selectability.log`.
  **잔여**: 배포된 테이블엔 여전히 원래 5행뿐 — 동작에는 문제없지만 운영자가 DynamoDB에서
  4개를 override하려면 다음 배포의 재시드가 필요(코드가 아니라 배포 작업).
- [x] **MCP 게이트웨이 ambient 자격증명 차단(gate 1395, 2026-07-28)** — 갭을 파보니 신원 부재보다
  컸다: 모든 도구가 맨 `kubectl`을 쐈고 `kubectl_apply`는 임의 매니페스트를 임의 ns에 썼다.
  이제 argv가 스코프 kubeconfig로 고정되고 변경 도구는 fail-closed.
  증거 `docs/evidence/mcp-gateway-scope.log`.
- [x] **테넌트별 call budget(gate 1404, 2026-07-28)** — `platform/ratelimit.py`(sliding window,
  레지스트리 `quota.calls_per_min`에서 선언, 미선언=무제한이라 additive). MCP 도구 호출에 배선.
- [ ] **rate limit을 모델 호출까지 확장 — 위 데이터 모델 결정에 묶여 있다(2026-07-28 조사)**.
  로컬 모델 호출자는 `local_deployer`/`strands_deployer` **둘뿐이고 둘 다 배포 경로**다.
  배포 요청(`DeployRequest`)엔 테넌트가 없고, `setup_tenancy(tenant, env)`는 **모델이 부르는
  도구** — 즉 테넌트는 추론의 **입력이 아니라 출력**이다. 추론에서 알아낸 테넌트로 그 추론을
  과금할 수는 없으므로, 호출자가 미리 선언해야 하고 그게 곧 "배포는 어느 테넌트 소유인가"다.
  인시던트 경로는 테넌트가 있지만 로컬 모델을 쓰지 않는다.
- [ ] **무스코프 MCP 읽기는 여전히 ambient** — 검증된 익명 kagent 왕복을 살리려는 의도적 예외다.
  닫으려면 kagent 경로에 먼저 스코프를 줘야 한다. 읽기가 무해해서가 아니다(남의 로그 = 유출).
- [ ] **A2A 인증 실집행 결정** — 카드가 광고하던 bearer/JWT를 서버가 검사하지 않던 것은 해소했다
  (`A2A_BEARER_TOKEN` 미설정 시 광고도 안 한다). 남은 결정은 **기본값을 on으로 돌릴지** —
  지금은 라이브 kagent 왕복이 익명이라 opt-in이다.
- [x] **Capsule `additionalMetadata` 이관(gate 1446, 2026-07-28)** — `additionalMetadataList`로.
  CRD에 직접 물어 확인했고, 라이브에서 probe 라벨 전파까지 반증.
  증거 `docs/evidence/capsule-deprecation-metadata.log`.
- [ ] **Capsule `limitRanges` 이관 — 경로 결정 필요(기계적 포팅 아님)**.
  `GlobalTenantResource`는 **클러스터 스코프**라 에이전트 변경 범위를 테넌트 밖으로 밀어
  **D30 위반**이고, `TenantResource`는 테넌트 안에 머물지만 **SA+RBAC 새 권한 표면**이 필요하다.
  지금은 동작하고 경고만 뜬다(2건→1건).
- [ ] **Cosign 어드미션 집행**(승인 필요) — 현재는 CI/사람용 검증 게이트까지다. API 서버가 미서명
  이미지를 거부하려면 policy controller(sigstore/Kyverno)라는 새 클러스터 의존성이 필요 → Phase 2와 함께.

## 유지 규약 (완료된 리팩토링에서 나온 "하지 말 것")

`_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이). detector/analyzer/decision은 SDK가 90%+
상이해 **의도적으로 DRY 안 함**. `approval_bridge` 추가 분해도 하지 않는다. 근거 → `DECISIONS.md` D15.
포괄 `gcloud:*`류 권한 allow를 되살리지 않는다(D16 우회 재발) → D22.

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 재평가 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴 메모(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지(계약/방법론만); 정적 무조건 fan-out은 self-consistency 라우팅 회귀라 금지; 자유텍스트 spawn_subagent 핵 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
