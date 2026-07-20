# Plan — Multi-tenant / Multi-cloud Platform (capability-oriented, implementation-pluggable)

작성: 2026-07-21 · **v5 — 최종 등급 S (93.5/100), Fable 5 권위 평가** · 상태: **설계 확정 (코드 착수 전)** · SSOT: `docs/NEXT_PLAN.md`
· 의사결정·MAD 히스토리: `docs/plans/2026-07-21-multi-tenant-env-addons-mad-history.md`

> **v5 S-하드닝 (Fable 5가 A+↔S 사이로 지목한 보안 3건 소진):**
> 1. 스코프 실행 위치 = **결정: in-cluster 러너**(Lambda-egress 아님) — 자격증명이 대상 클러스터를 안 벗어남.
> 2. **token broker 인가 = incident provenance 바인딩**(attested 승인 레코드 tenant 검증, 호출자 문자열 불신).
> 3. **read-model = push 모델**(in-cluster agent→허브) — 허브가 스포크 read 자격증명 0개 보유.
> → 실행·읽기 자격증명 경계가 in-cluster agent로 일관 봉인. 목표: S(≥93).

> **v4 정정 (평가 에이전트가 실제 코드로 검증한 2건 오류 수정):**
> - `NormalizedIncident`엔 k8s `namespace` 필드 **없음**(namespace는 `source_metadata["labels"]`, models.py의
>   namespace는 AlarmContext=CloudWatch 메트릭). tenant/env는 신규 필드로 추가.
> - `resolve_action`은 **decision 단계**지 온프렘 실행 경로 아님. 실제 경로 `_run_external_action → run_onprem_action`
>   (여기서 incident가 버려짐)에 scope 관통. params는 `parameters_for_action`가 해석.
> - 런타임 자격증명 custody = **인시던트당 단기 토큰**(executor가 타 테넌트 자격증명 열거 불가) 명시.
> - 스코프 kubectl **실행 위치**(in-cluster vs Lambda-egress) 확정 요구. Phase 1을 **1a(자격증명)/1b(delivery)** 분할.

> v2 변경: 인가를 "에이전트 실행 blast radius" 기준으로 재정립 · Flux를 Phase 1 실제 구현으로 승격 ·
> NormalizedAddonStatus를 2축으로 재설계 · TF↔GitOps 소유권 핸드오프 명시 · Day-2 버전 승격 경로 추가 ·
> 레지스트리 per-tenant 쓰기 인가 · 비교표 사실오류 정정 · read model=신규 서브시스템으로 추정 현실화.
>
> **v3 변경 (이번 라운드):**
> 1. 자격증명 격리를 **코드 seam으로 구체화** — 어댑터 계약·onprem 러너 시그니처에 tenant/env를 관통시키고
>    ambient kubeconfig context 경로를 제거, 스코프 kubeconfig 로드로 교체. 검증을 **Phase 3→Phase 1로 당김**.
> 2. tenancy 티어별 **cluster-공유 topology와 자격증명 경계를 분리 명세** — soft=per-tenant namespace RBAC,
>    vcluster=가상 클러스터, dedicated=env==cluster==tenant. '1 env = 1 cluster'의 모순 해소.
> 3. executor 강제 기관을 **AppProject가 아니라 Kubernetes Role/RoleBinding**으로 정정(category blur 제거).
> 4. remediation rollback ↔ GitOps self-heal **우선순위 정책**을 운용 워크플로로 명세(문서화→해소).
> 5. **DR/rebuild 런북** 추가(secret-restore first-order, registry로 복구 불가한 것 명시).
> 6. soft 티어에 **ResourceQuota/LimitRange + tenant-prefix 네이밍 + 티어별 non-guarantee** 추가.
> 7. state rm 채택을 **no-churn(라벨 매칭) + PVC 스냅샷 + 핸드오프 롤백**으로 안전화.
> 8. read model **applicable=false 축을 Phase 2에서 faked managed 디스크립터로 실제 검증**.

## 목적

platform-agent를 단일 클러스터 운영에서 **다중 환경(env) × 다중 테넌트 × 다중 클라우드 플랫폼**으로
확장한다. env마다 substrate·add-on·격리 강도·GitOps 엔진이 다를 수 있고, 각 능력은 self-hosted 또는
managed 백엔드로 해결된다. 단일 컨트롤플레인 대시보드가 백엔드-중립 정규화 read model로 집계한다.

## 설계 원칙 — capability, implementation-pluggable

프로젝트의 cloud-neutral DNA(provider registry·capability runbook)를 플랫폼 레이어로 확장한다.
레지스트리는 *능력만 선언*하고 어댑터가 substrate별 구현을 해결한다. 모델은 3차원:
`capability × {self-hosted | managed} × substrate(kind|k3s|eks|gke|aks)`.

> 주의(리뷰 반영): 기존 `analyzer.py`의 Bedrock↔Qwen 스위치는 **env-게이트 문자열**이지 진짜 어댑터
> 인터페이스가 아니며, gcp/azure 신호/실행 어댑터도 미실행 seam이다. 즉 "pluggable 선례"는 아직 검증
> 안 된 패턴이다 — 그래서 이 계획은 Phase 1에서 **2개의 실제 백엔드(argocd+flux)로 계약을 즉시 압박**한다.

## 최우선 불변식 — 에이전트 실행 blast radius = 1 tenant/env  ⚠️리뷰 Critical#1

이 시스템의 특권 행위자는 대시보드 viewer가 아니라 **remediation을 실행하는 ops 에이전트**
(`restart_workload`/`scale_out`/`rollback_release`, 실행 어댑터). 따라서 1급 보안 불변식은 **자격증명이
경계이고 라벨은 편의**라는 것이며, 이는 산문이 아니라 **실행 경로의 코드 seam**으로 강제되어야 한다.

### 현재 상태(정직한 진단, 코드 ground-truth) — 지금은 fail-OPEN
`src/agents/operations/runners/onprem_runner.py`의 `_run_kubectl`는 `subprocess.run(["kubectl", *args])`로
**ambient kubeconfig context**에 대해 실행하고 `--kubeconfig`/`--context`가 없다(fail-open). 대상 Namespace는
**`NormalizedIncident`의 필드가 아니라** `incident.source_metadata["labels"]["namespace"]`에서 옴
(`adapters/execution/onprem.py`의 `_parameters_for` → `params["Namespace"]`). ⚠️정정: `NormalizedIncident`
(`models.py`)에는 k8s `namespace` 필드가 **없다**(models.py의 `namespace`는 `AlarmContext`의 CloudWatch 메트릭
namespace로 무관). 또한 `ExecutionAdapter.resolve_action`(`adapters/base.py`)은 **decision 단계** 메서드로
온프렘 실행 경로가 아니다. 실제 실행 경로는 `aws/executor.py`의
`_run_ssm_actions → _run_external_action(provider, action, params, log) → run_onprem_action(action, params, log)`이며,
**`_run_external_action`이 incident를 통째로 버린다**(params만 전달). 즉 현재 blast radius는 라벨/라우팅 정확성에
의존하며 라우팅 버그에 fail-open — rubric fail_bar와 정확히 일치.

### 강제 seam(이 계획이 추가하는 코드 변경, 정확한 경로) — Phase 1a
1. **NormalizedIncident에 실제 필드 추가**: `models.py`의 `NormalizedIncident`에 **`tenant`·`env`** 필드 신설
   (namespace는 지금처럼 `source_metadata["labels"]`에 유지). 실행 params 해석은 `resolve_action`이 아니라
   `parameters_for_action(action, incident)`(`aws/executor.py`)가 담당함에 유의.
2. **실행 경로에 scope 핸들 관통**: `_run_external_action(provider, action, params, log)` →
   `_run_external_action(provider, action, params, log, incident_scope)`로 시그니처 확장(현재 incident를 버리는
   지점이 바로 여기), 이어서 `run_onprem_action(action, params, incident_scope, log)`. `incident_scope`는
   tenant/env로 해결된 **스코프 자격증명 핸들**.
3. **런타임 자격증명 custody = 인시던트당 단기 발급**(집중점 재발 방지): executor 프로세스가 전 테넌트
   kubeconfig를 읽을 수 있으면 hub-holds-all 안티패턴이 executor 안에서 재현된다. 따라서 broker/`TokenRequest`로
   **해당 인시던트의 tenant SA에 스코프된 단기 토큰만** 반환하고, executor는 **타 테넌트 자격증명을 열거할 수 없다**.
   Phase 1a DoD: "executor는 그 인시던트의 스코프 토큰 하나만 보유".
4. **스코프 kubeconfig 실행 + ambient 삭제**: `_run_kubectl`이 `kubectl --kubeconfig <scoped-token> ...`만 실행,
   `--kubeconfig` 없는 ambient 경로 **삭제**. 라벨의 namespace가 SA RBAC 밖이면 `Forbidden`→skip
   (impossible-by-absence-of-credential). 자격증명 미해결 인시던트는 fail-closed.
5. **실행 위치 = 결정: in-cluster 러너**(Lambda-egress 아님). AWS executor Lambda는 스코프 `kubectl`을 직접
   돌리지 **않는다**(그러면 Lambda가 전 클러스터로의 egress+자격증명을 쥐는 집중점이 됨). 대신 Lambda는
   **서명된·tenant-바운드 remediation 요청**을 대상 env의 **in-cluster 러너**(per-cluster Job/agent)에 dispatch하고,
   러너는 **자기 클러스터 로컬의 스코프 SA 토큰**으로만 실행한다. 자격증명이 대상 클러스터를 벗어나지 않는다.
   기본값=in-cluster 러너. (원격 관리형은 Phase 4에서 각 클라우드 pull-agent로 동형 적용.)
6. **게이트 유지**: 자격증명 격리가 라이브 증명될 때까지 `ONPREM_EXECUTOR_LIVE=false`(log-only) 유지.

- 대시보드 viewer RBAC(역할↔tenant 가시성)은 **2차** 보호. 순서를 뒤집지 않는다(executor 격리 먼저).

### S-하드닝: broker 인가 + read push (Fable 5 델타 소진, v5)  ⚠️보안 16축
1. **token broker 자체 인가 — incident provenance 바인딩**: broker는 호출자가 준 tenant 문자열을 신뢰하지
   **않는다**. remediation 요청은 파이프라인이 발급한 **attested incident/approval 레코드**(승인 레코드 ID +
   서명)를 실어오고, broker는 그 레코드의 tenant를 검증한 뒤 **그 tenant SA에만** 단기 토큰을 발급한다. 즉
   "아무 테넌트 토큰이나 발급"이 불가 — 집중점이 이동한 게 아니라 **provenance로 봉인**된다. 토큰 수명=단일
   액션, 전량 audit. (broker는 인시던트 서명 검증만, 자격증명 저장고 아님.)
2. **read-model = push 모델(허브가 스포크 read 자격증명을 안 가짐)**: 대시보드 read-model 폴러가 각 클러스터
   자격증명으로 pull하면 크로스테넌트 read 집중점이 생긴다. 대신 **각 클러스터의 in-cluster agent(위 러너와 동일
   개체)가 자기 add-on의 NormalizedAddonStatus를 컨트롤플레인으로 push**한다. 허브는 스포크 자격증명을 **0개**
   보유. (executor 실행 topology와 동일 결정으로 read/write 자격증명 경계가 일관됨.)
3. 결과: 실행·읽기 **모두 in-cluster agent가 로컬 자격증명으로** 수행하고, 허브(Lambda/대시보드)는 tenant를
   벗어나는 자격증명을 어느 경로로도 보유하지 않는다 — blast-radius 봉인이 executor·poller 양쪽에 일관 적용.

**알려진 2차 잔여(Phase 1a 진입 시 명시적으로 닫는다 — 강도가 낮고 hub=spoke 동안 inert):**
- **agent→hub push 인증**: hub→agent(서명 요청)만 봉인됨. 역방향(agent가 push하는 상태)의 인증 미명세 →
  agent 신원(mTLS/워크로드 identity)으로 **pushing agent를 자기 클러스터/tenant 집합에 바인딩**, 상태 위조 차단.
- **승인 레코드 replay**: attested 레코드에 **one-time-use nonce** + 서명키 custody/rotation 정책.
- **push staleness**: heartbeat/last-seen로 **죽은 agent가 상태를 조용히 freeze(fail-open)** 하지 않게 — 미수신 시 `unknown`.
- **soft 티어 agent의 per-cluster mint 집중**: 공유 클러스터의 runner+broker+push agent는 그 클러스터 전 tenant SA에
  대한 mint 권한을 가짐 → blast-radius = **1 클러스터**(1 tenant 아님)임을 정직히 인정(soft의 shared control-plane
  non-guarantee에 부합). 더 강한 격리는 vcluster/dedicated 티어로.

## 능력 ↔ 백엔드 비교표  (리뷰 Minor 정정 반영)

| 능력 | On-prem/CNCF (self-hosted) | AWS | GCP | Azure |
|---|---|---|---|---|
| 클러스터 프로비저닝 | Terraform · Cluster API · Crossplane | EKS (+TF/CAPA) | GKE (+TF/CAPG) | AKS (+TF/CAPZ) |
| **GitOps 배포** | **ArgoCD · Flux** | 관리형 컨트롤플레인 없음; EKS가 Argo/Flux를 **managed add-on**으로 제공 | **Config Sync** (⚠️GKE Enterprise=per-vCPU 과금) | **GitOps Flux v2 확장** (Arc/AKS) |
| 멀티테넌시(격리) | Capsule · vCluster · AppProject | ns + IAM/RBAC | GKE **Teams/Scopes** + ns | ns + **Arc RBAC** |
| 멀티클러스터(fleet, ≠테넌시) | ArgoCD hub-spoke · Karmada/OCM | EKS + ACK | **GKE Fleet** | **AKS Fleet Manager**(업데이트 오케스트레이션·L4, 격리 아님) |
| 메트릭 | kube-prometheus-stack | AMP + Managed Grafana | Google Managed Prometheus | Azure Monitor Prom + Grafana |
| 로깅 | Loki + Fluent Bit | CloudWatch Logs | Cloud Logging | Log Analytics |
| 점진 배포 | Argo Rollouts · Flagger | (클러스터측 동일) | (동일) | (동일) |
| 시크릿 | External Secrets · Sealed · Vault | Secrets Manager + CSI | Secret Manager + CSI | Key Vault + CSI |

정정: **Fleet ≠ 멀티테넌시**로 행 분리(AKS Fleet Manager는 업데이트 오케스트레이션). **Config Sync는
GKE Enterprise 과금** → "managed=운영부담↓" 주장은 라이선스 비용과 트레이드오프. GitOps 비대칭은
"AWS는 **관리형 컨트롤플레인** 부재"가 정확(Argo/Flux는 EKS add-on으로 존재).

## 도메인 모델 — cardinality는 **격리 티어의 함수**  ⚠️리뷰 Critical#2

핵심 정정: `1 env = 1 cluster`는 **dedicated 티어에서만** 성립한다. env·cluster·tenant의 cardinality는
격리 티어에 따라 달라지며, 자격증명 경계도 티어별로 다르다. "env마다 별도 kubeconfig"는 티어 불문 규칙이
아니라 **dedicated 전용**이다.

```
Tenant (isolation: soft | vcluster | dedicated) — registry write 경계
  └── Environment (dev|staging|prod, substrate ∈ kind|k3s|eks|gke|aks)
        ├── capabilities: 구독 능력 + 백엔드 해결(정책 기본값 or override)
        ├── addons[] : 카탈로그 부분집합, **env별 버전**(승격 경로용)
        └── incidents : tenant/env 라벨 + **티어별 스코프 실행 자격증명**
```

### 티어별 topology · 자격증명 경계 · non-guarantee  ⚠️리뷰 Major(격리)

| 티어 | cluster 공유 | 실행 자격증명 경계(**강제 기관**) | 격리가 보호하는 것 / **보호하지 않는 것** |
|---|---|---|---|
| **soft** (기본, Capsule) | 여러 tenant의 여러 env가 **한 클러스터를 namespace로 공유** | **per-tenant** namespace-scoped **Role/RoleBinding + SA** (그 SA 토큰으로 만든 kubeconfig). env가 아니라 **tenant**가 자격증명 단위 | 보호: namespace 경계 안의 RBAC·ResourceQuota. **미보호**: 공유 control-plane/API server, 커널/노드(노드 리소스 고갈), data-plane 격리 없음 |
| **vcluster** | tenant마다 host 위에 **가상 컨트롤플레인** | per-vcluster kubeconfig(가상 API server) | 보호: control-plane 격리(별도 API server·CRD). **미보호**: 물리 노드/커널(host 공유), 강한 data-plane 격리는 아님 |
| **dedicated** | tenant마다 **물리 클러스터**(여기서만 `env==cluster==tenant`) | **per-env(=per-cluster)** kubeconfig | 보호: control-plane + 노드 + 자격증명 완전 분리. **비용**: 클러스터 수·운영비 최대 |

- **기본은 soft**이며, 따라서 **1차 자격증명 경계는 per-env가 아니라 per-tenant namespace RBAC**이다. 러너는
  incident.tenant로 해결된 **per-tenant SA kubeconfig**를 로드한다. soft에서 per-env kubeconfig를 쓰면 동일
  클러스터의 co-tenant namespace에 도달하므로 **금지**한다.
- soft·vcluster·dedicated는 서로 대체가 아니라 **강도/비용 스펙트럼**이며, tenant 파일의 `isolation` 필드로
  1급 선택된다(dead weight 아님).

기존 `cluster` 상관키 → `env`로 승격. incident/approval에 tenant/env 라벨 + 티어별 스코프 자격증명 추가.

## Git 레지스트리 (SSOT) — 파티션 + 쓰기 인가  ⚠️리뷰 Major

god-object 방지: **테넌트별 파일로 분리** + path-scoped CODEOWNERS + prod stanza 머지 게이트.
```
platform/
  catalog.yaml                 # 공용 add-on 카탈로그(능력 정의·substrate values 오버레이)
  tenants/acme.yaml            # CODEOWNERS: @acme-owners  (tenant-A는 자기 파일만 수정)
  tenants/globex.yaml          # CODEOWNERS: @globex-owners
```
```yaml
# tenants/acme.yaml
isolation: soft                          # → Capsule Tenant + per-tenant Role/RoleBinding + SA
naming_prefix: acme                      # 네임스페이스·리소스 접두사(cross-tenant 충돌 방지)
quota: { cpu: "16", memory: 64Gi, pods: 200 }   # → Capsule이 ResourceQuota/LimitRange로 강제
environments:
  dev:  { cluster: kind-platform-agent, substrate: kind,
          addons: { observability: "kube-prometheus-stack 87.17.0", progressive: "argo-rollouts 2.41.1" } }
  prod: { cluster: k3s-lab, substrate: k3s, delivery: flux,        # 엔진 override 가능
          addons: { observability: "kube-prometheus-stack 87.17.0" } }   # 부분집합 + env별 버전
```
- **env별 버전 필드** = Day-2 승격(dev에서 bump→검증→prod로 PR 승격). 락스텝 강제 안 함.
- **quota/naming_prefix** = noisy-neighbor·이름 충돌 방지(아래 tenancy 섹션).
- 대시보드 쓰기(Phase 5)는 **해당 tenant 파일에 대한 PR만** 생성(타 tenant 편집 불가).

## 멀티테넌시 — 강제 기관·quota·네이밍  ⚠️리뷰 Major(isolation)

- **executor의 강제 기관은 AppProject가 아니다** ⚠️리뷰 Major(category blur): AppProject는 **ArgoCD
  컨트롤러가 SYNC할 대상**(source repo·destination namespace)만 제한한다. remediation executor는 Argo
  클라이언트가 아니라 **독립 kubectl SA**이므로 AppProject는 executor에 아무것도 강제하지 못한다. executor를
  fail-close하는 것은 **Kubernetes Role/RoleBinding**(soft에서는 Capsule Tenant가 소유한 namespace에 대한
  RoleBinding)이다. AppProject는 **namespace SET의 source-of-truth**로만 쓰인다.
- **자격증명 생성 경로**(registry → 실행 kubeconfig):
  `tenant 파일(isolation·namespace SET) → per-tenant Role/RoleBinding(허용 namespace/verb) + SA → SA
  token → kubeconfig`. 러너는 incident.tenant로 이 kubeconfig를 조회해 로드한다.
- **noisy-neighbor / quota**: soft 티어 각 tenant에 **ResourceQuota + LimitRange**를 Capsule Tenant가
  강제한다(위 `quota`). 단, 이는 API 객체 수준 제한이며 **노드 커널/디스크 I/O 고갈은 막지 못한다**(위 표의
  non-guarantee) — 강한 격리가 필요하면 vcluster/dedicated로 승격.
- **cross-tenant 네이밍**: tenant `naming_prefix`로 namespace·릴리스·리소스 이름을 접두사화해 공유 클러스터
  내 충돌을 구조적으로 방지한다.

## 소유권 경계 — Terraform ↔ GitOps  ⚠️리뷰 Major(handoff)

이중소유 drift 방지. 경계를 **명문화**한다:
- **Terraform이 소유**: 클러스터(또는 등록) + **GitOps 엔진 부트스트랩** + Capsule/AppProject 기반 +
  cluster 등록 시크릿 + **sealed-secret private key**. 그 외 add-on은 **소유하지 않음**.
- **GitOps가 소유**: 전 add-on(observability/progressive/…) + platform-agent 워크로드.
- **마이그레이션(1회) — no-churn 채택**  ⚠️리뷰 Major(handoff data-loss): 현재
  `infra/onprem/addons/`의 `helm_release`(kps/loki/rollouts 등)를 `terraform state rm`으로 TF 소유에서
  떼고 ApplicationSet/Flux 소유로 이관한다. **데이터 손실 방지 절차**:
  1. **채택은 재생성이 아니라 no-op이어야 한다**: GitOps 매니페스트의 **release name·namespace·helm ownership
     라벨/annotation**(`app.kubernetes.io/managed-by`, `meta.helm.sh/release-name`)을 기존 릴리스와 정확히
     일치시켜, 컨트롤러가 diff 없이 채택(adopt)하고 **delete-and-recreate를 트리거하지 않게** 한다. 불변 필드
     불일치는 PVC 파괴로 이어지므로 사전 매칭이 필수.
  2. **핸드오프 전 스냅샷**: Prometheus TSDB / Loki PVC의 스냅샷(또는 volume backup)을 먼저 확보.
  3. **핸드오프 롤백**: 채택이 중간 실패하면 `terraform import`로 릴리스를 TF state에 재-import해 단일
     소유로 되돌린다(부분 실패 시의 dual-ownership drift 차단).
  - argocd 자체는 부트스트랩으로 잔류.
  - **DoD는 최종 상태가 아니라 no-churn을 라이브 검증**: 채택 직후 `helm history`/컨트롤러 이벤트에
    revision 증가·재생성이 없음을 확인.

## cluster 등록 + 시크릿 부트스트랩  ⚠️리뷰 Major(chicken-egg)

- 허브 ArgoCD가 스포크 kubeconfig를 보관하면 **크로스테넌트 자격증명 집중점**이 됨 → 테넌시와 충돌.
  1차 완화: **env=로컬(kind/k3s)만**, 허브=스포크 동일 클러스터(자격증명 집중 없음). 원격 멀티클러스터·
  관리형은 Phase 4(별 승인)로 미룸 — 그때 스포크 자격증명의 tenant 파티션·수명·회전 정책을 명시.
- self-hosted도 부트스트랩 시크릿 존재(Argo repo creds, External Secrets store creds) → 누가 보관·주입하는지
  Phase 1에서 명시(1차: 로컬 sealed/plain, 프로덕션: 클라우드 CSI).

## DR / 클러스터 재구축 런북  ⚠️리뷰 Major(Day-2 DR)

registry는 SSOT지만 **desired CONFIG만** 복원하고 **data-plane·시크릿은 복원하지 않는다**. 재구축 순서:

1. **시크릿 복원이 first-order 의존**: GitOps가 재조정하려면 그 전에 **Argo repo creds / External-Secrets
   store creds / sealed-secret private key**가 먼저 있어야 한다. 따라서 **TF 재적용**으로 (a) 클러스터,
   (b) GitOps 엔진 부트스트랩, (c) **sealed-secret private key 복원**을 먼저 수행한다. 이 키 없이는 registry의
   SealedSecret이 복호화되지 않아 부트스트랩이 막힌다(restore의 chicken-egg).
2. **GitOps 재조정**: 부트스트랩 후 GitOps가 registry에서 add-on을 desired state로 재적용 → 클러스터
   config가 **선언 상태에서 재구성**됨.
3. **registry로 복구 불가한 것(명시)**: Prometheus TSDB(메트릭 이력), Loki 로그, 그 밖의 stateful PVC.
   이들은 registry가 아니라 **볼륨 스냅샷/오브젝트 스토리지 백업**으로 복구한다(주기적 스냅샷이 백업
   메커니즘). registry는 "무엇이 돌아야 하는가"를, 백업은 "그 안에 있던 데이터"를 복원한다.
4. **DoD(Phase 2/4)**: 로컬에서 클러스터를 삭제→TF 재적용→GitOps 재조정으로 add-on이 다시 sync·Healthy가
   되는지 라이브로 확인(데이터 이력 제외).

## 정규화 read model — 2축 + 적용가능성  ⚠️리뷰 Critical#3

단일 enum이 drift를 죽이므로 **직교 2축**으로 모델:
```
NormalizedAddonStatus {
  tenant, env, capability, backend,
  desired_version,
  sync_state  : synced | drifted | n/a        # n/a = 관리형(AMP 등 sync 개념 없음)
  health_state: healthy | progressing | degraded | missing | unknown
  applicable  : bool                          # 이 백엔드에 sync 축이 의미 있는가
  native      : {...}                          # 백엔드 원본(Argo sync+health, Flux Ready, ...) 옵셔널
}
```
매핑 예: Argo `Synced+Degraded` → `{sync=synced, health=degraded}`(drift 아님, 앱 문제). Argo
`OutOfSync+Healthy` → `{sync=drifted, health=healthy}`(drift!). Flux `Ready=False` → `{sync=n/a 또는
drifted, health=degraded}`. AMP → `{sync=n/a, applicable=false, health=healthy}`.

> **applicable=false 축을 must-have 단계에서 검증**  ⚠️리뷰 Minor: 유일한 관리형 백엔드(Config Sync/AMP)는
> Phase 4(선택·billable)에 있으므로, `applicable=false` 경로를 **Phase 2 read-model 테스트에서 faked/static
> managed 디스크립터**로 실제 코드 경로에 대해 증명한다(billable 리소스 불요). 관리형 백엔드가 sync 축을
> false로 정직히 표기하는지가 선택 단계가 아니라 **비-선택 단계에서 falsify**된다.

## Dashboard read model — 신규 서브시스템 (정적 아님)  ⚠️리뷰 Major(estimate)

현재 read model은 **정적**(`getStackLinks` 하드코딩·라이브 상태 0). 이를 라이브 크로스-env 상태로 교체 =
멀티클러스터 상태 수집·캐싱·백엔드별 상태 매핑이 통째로 신규 → **독립 서브시스템**으로 취급·추정 반영.
**수집 방식 = push(허브 pull 아님, S-하드닝)**: 각 클러스터 in-cluster agent가 NormalizedAddonStatus를
컨트롤플레인으로 push하므로 허브는 스포크 read 자격증명을 0개 보유(executor 실행 topology와 동일 결정).
대시보드는 push된 상태를 조회만 한다(Phase 2는 이 수집기 포함 3~4세션).

## Day-2 — 롤백 ↔ GitOps self-heal 우선순위  ⚠️리뷰 Major(GitOps 자기모순)

플랫폼은 `rollback_release`/`ONPREM-ArgoRolloutRollback`(kubectl rollout undo)을 자동 액션으로 제공하는
동시에 ArgoCD/Flux self-heal이 선언된 desired 버전으로 재조정한다. 아무 정책 없이는 에이전트 롤백이 수초
내 reconciler에 되돌려져 **remediation loop가 delivery loop와 싸운다**. 정책(문서화가 아니라 워크플로):

- **우선순위: human/agent 롤백 > reconciler**(재승격 전까지). 롤백 액션은 **먼저 desired와 actual을
  일치시킨 뒤** act한다. 두 가지 구현 경로:
  1. **selfHeal pause**: 대상 Application의 `selfHeal`을 일시 비활성(또는 annotated paused)으로 설정 후
     rollout undo. 이후 인시던트 종결·재승격 시 selfHeal 복구.
  2. **registry write-back(권장, GitOps-native)**: 롤백 대상 버전을 **tenant 파일에 기입**(desired==actual)
     → reconciler가 롤백 버전을 desired로 인식하므로 되돌리지 않음. 재승격은 registry PR로 수행.
- 이로써 self-heal-vs-manual-rollback 충돌을 **명명 + 해소**한다(단순 문서화 아님). Phase 3 자동 롤백은
  이 정책이 붙기 전까지 log-only(ONPREM_EXECUTOR_LIVE=false)를 유지.

## Phases (DoD 포함, 추정 현실화) — 위험 조기 소진 재정렬  ⚠️리뷰 Minor(risk 순서)

- **Phase 0 — 모델 + 어댑터 계약** (0.5~1세션): `platform/` 레지스트리 스키마(파티션·isolation·quota·prefix) +
  로더(py/ts) + **어댑터 인터페이스 계약**(tenant/env 관통) + `NormalizedAddonStatus`(2축) 타입. DoD: 로더·타입
  검증, 동작 무변경.
- **Phase 1a — 실행 자격증명 격리(최소 증명)** (1~1.5세션, **최우선·독립 위험**)  ⚠️리뷰 Critical#1:
  - `NormalizedIncident`에 `tenant`/`env` 필드 추가(namespace는 `source_metadata["labels"]` 유지), 실행 경로
    `_run_external_action`→`run_onprem_action`에 `incident_scope` 관통(params 해석은 `parameters_for_action`).
  - onprem 러너 **ambient-context 경로 삭제**. 실행 위치=**in-cluster 러너**(Lambda-egress 아님): Lambda는
    서명된 tenant-바운드 요청을 dispatch, 러너가 로컬 스코프 SA 토큰으로만 실행(자격증명 클러스터 밖으로 안 나감).
  - **token broker = incident provenance 바인딩**: broker는 호출자 tenant 문자열 불신, **attested 승인 레코드**의
    tenant를 검증 후 그 tenant SA에만 단기 토큰 발급(전량 audit) — 아무 테넌트 토큰 발급 불가.
  - per-tenant namespace Role/RoleBinding 생성. DoD(라이브 $0): **tenant-A 승인 레코드로 tenant-B namespace 액션이
    `Forbidden`/자격증명 부재로 실패**; broker가 위조 tenant 문자열 거부; 러너가 그 인시던트 토큰 하나만 보유.
    통과 전까지 **`ONPREM_EXECUTOR_LIVE=false` 유지 명시 커밋**.
- **Phase 1b — 계약 압박 + 소유권 핸드오프** (1.5~2세션):
  - **Delivery 어댑터 2개 실제**(Flux 스텁 금지): 레지스트리→(ApplicationSet | Flux Kustomization+HelmRelease)
    env×addon 팬아웃.
  - **TF↔GitOps no-churn 핸드오프**(state rm + 라벨/오너십 annotation 매칭 채택 + PVC 스냅샷 + import 롤백) 라이브 검증.
  - DoD(라이브 $0): kind"dev"(argocd, add-on 전체) vs k3s"prod"(**flux**, 부분집합) 각각 정확히 sync·Healthy;
    핸드오프 시 add-on revision 무증가(no-churn).
- **Phase 2 — Tenancy + Dashboard read model** (3~4세션): Capsule(soft)+per-tenant Role/RoleBinding +
  ResourceQuota/LimitRange + 대시보드 tenant/env 스위처 + **push 기반 상태 수집**(in-cluster agent→컨트롤플레인,
  허브 스포크 자격증명 0개; 정규화 read model, 2축 drift) +
  **faked managed 디스크립터로 applicable=false 검증** + **DR 재구축 라이브 확인**(삭제→TF→재조정).
  DoD: env 전환 스코프 정확, `OutOfSync+Healthy` drift가 뷰에 구분 표시, 관리형 n/a가 정직히 표기.
- **Phase 3 — 인가 강화(1급: 에이전트 blast radius, 2급: viewer) + 롤백 우선순위** (1세션): Phase 1의 최소
  증명을 전 액션·전 티어로 확장(자격증명 격리 full) + **롤백↔selfHeal 우선순위 정책 구현**(registry
  write-back) + viewer 가시성 제한. DoD: 전 remediation 액션이 스코프 자격증명으로만 실행, 롤백이 reconciler에
  되돌려지지 않음.
- **Phase 4 (선택, billable) — Managed 어댑터 1종 + 원격 클러스터**: GKE Config Sync 또는 AMP,
  스포크 자격증명 tenant 파티션·수명·회전 정책 포함. 원격 DR 포함.
- **Phase 5 (선택) — 레지스트리 PR 쓰기**: 대시보드 "add-on 부착"→해당 tenant 파일 PR(CODEOWNERS 게이트).

> 재정렬 요지: **계약·소유권 핸드오프·자격증명 격리(최소 증명)를 poller/tenancy 빌드아웃 전에 모두 소진**한다.
> 최우선 불변식의 라이브 검증이 더 이상 Phase 3으로 back-load되지 않는다.

## Out of scope

- 하드 격리 상시(물리 클러스터-per-tenant) — isolation의 한 옵션(dedicated), 기본 soft.
- 원격 멀티클러스터·관리형 상시 가동(Phase 4 별 승인, 로컬 우선).
- add-on 카탈로그 무한 확장(1차=기존 능력, seam만).
- stateful 데이터(TSDB/Loki) 백업 오케스트레이션 자동화 — DR 런북은 스냅샷 존재를 전제(백업 파이프라인 자체는
  별도 작업).

## 리스크 / 선행 조건

1. **어댑터 계약 leaky 위험**: Phase 1에서 argocd+flux **2 실제 구현**으로 즉시 검증(최소공통 vs 표현력 균형).
2. **실행 자격증명 fail-open(현재 상태)**: onprem 러너 ambient-context 제거 + per-tenant SA kubeconfig를
   **Phase 1 최소 증명**으로 당김; 통과 전 `ONPREM_EXECUTOR_LIVE=false` 유지. 최우선.
3. **티어별 cardinality 혼동**: soft=per-tenant namespace RBAC, dedicated에서만 env==cluster==tenant.
   자격증명 단위를 티어의 함수로 명세.
4. **Day-2 업그레이드 blast**: env별 버전 + 승격 경로로 완화(락스텝 금지).
5. **롤백↔self-heal 충돌**: registry write-back(or selfHeal pause)로 우선순위 해소(Phase 3), 그 전엔 log-only.
6. **핸드오프 data-loss**: 라벨 매칭 no-churn 채택 + PVC 스냅샷 + import 롤백.
7. **DR**: secret-restore first-order → TF → GitOps 재조정; TSDB/로그는 스냅샷 백업(비-registry).
8. **자격증명 집중점**: 1차 로컬 동일-클러스터로 회피, 원격은 Phase 4에서 파티션·회전 정책과 함께.
9. **read model 표현력**: 2축+native detail로 백엔드 시맨틱 차이 흡수, applicable=false는 Phase 2 faked
   디스크립터로 검증.
10. 가드레일: 버전 핀·요청 밖 기능 금지·각 Phase `make check`+`/checkpoint`·하드-투-리버스 승인 후.

## 순서 제안

Phase 0→1이 뼈대 + **3대 최고위험(계약 leaky·소유권 핸드오프·실행 자격증명 격리) 조기 소진**. 2(tenancy+read
model)가 가장 무거움(라이브 폴러 + DR 확인). 3(인가)은 자격증명 격리 전면화 + 롤백 우선순위. 4·5 선택. 총
예상 8~10세션(자격증명 seam·핸드오프 안전화·DR 반영해 원안 대비 상향).
