# Plan — On-Prem 플랫폼 애드온 스택 IaC (JOURNEY 범위 로컬 확장)

작성: 2026-07-20 · 상태: **진행 중 — Phase 1·2 완료(2026-07-20), Phase 3·4 대기** · 기판: 로컬 On-Prem($0) 우선
(체크 상태의 소스는 `docs/NEXT_PLAN.md` — 이 문서는 설계/DoD 상세만 담당)

## 목적

JOURNEY.md(Notiflex/GKE)가 다루는 **클러스터 위 플랫폼 레이어**(GitOps·관측성·점진 배포)를
platform-agent의 On-Prem IaC(kind/k3s)로 재현하고, 기존 인시던트 파이프라인
(`onprem_webhook_api` Alertmanager 수신 → 4-step)과 **한 루프로 연결**한다.
JOURNEY = "플랫폼을 짓는다", platform-agent = "그 플랫폼을 운영한다" — 이 접점이 핵심 산출물.

## 설계 결정 (전제)

1. **애드온 IaC는 별도 terraform root** `infra/onprem/addons/` — helm/kubernetes provider 기반,
   `kubeconfig`/`context` 변수로 kind·k3s 양쪽에 동일 적용(기판 root와 state 분리 = 수명주기 독립).
   기존 `infra/onprem/terraform/`(kind 기판)은 무변경.
2. **저사양 values 고정** — JOURNEY ch6.2 트러블슈팅 재활용: 관측성 스택 CPU requests `5m`대,
   retention 최소. Mac Docker VM 예산 내 동작이 DoD의 일부.
3. **Alertmanager → in-cluster `webhook-service`** — 차트가 이미 webhook API를 배포하므로
   receiver URL은 클러스터 내부 DNS로 지정(호스트 노출 불필요).
4. JOURNEY 항목 중 **로컬 재현 불가/무의미 항목은 명시 제외**(아래 Out of scope).

## Phases

### Phase 1 — 애드온 IaC 뼈대: ArgoCD + kube-prometheus-stack ($0)
- [ ] `infra/onprem/addons/` 신설: helm/kubernetes provider, `kubeconfig_path`·`kube_context` 변수,
      `helm_release` 2종 — **ArgoCD**(버전 핀) + **kube-prometheus-stack**(버전 핀, 저사양 values 파일).
- [ ] kind 기판에 `terraform apply` → ArgoCD·Prometheus·Grafana·Alertmanager 전 파드 Ready,
      port-forward로 UI 2종 접속 확인.
- [ ] 가드 테스트(+N): 버전 핀 존재·values 파일 정합·CPU requests 상한(저사양 계약) — aws-production 가드 패턴 준용.
- DoD: apply→Ready→destroy 왕복 + `make check` green. 증거 `docs/evidence/onprem-addons-phase1.log`.

### Phase 2 — 관측성 → 인시던트 파이프라인 연결 (접점, 최우선 가치)
- [ ] Alertmanager receiver를 차트의 `webhook-service`(in-cluster DNS)로 지정하는 values 배선.
- [ ] 데모용 PrometheusRule 1종(예: 대상 파드 다운/재시작 임계) IaC에 포함.
- [ ] 라이브 실증: 룰 발화 → Alertmanager grouping → webhook API 수신 → 4-step 판정
      (P1 즉시/P2 승인 게이트 중 1경로) → activity 기록·대시보드 Incidents 반영.
- DoD: 알람→인시던트 E2E 로그 `docs/evidence/onprem-addons-alertmanager-e2e.log`. `make check` green.

### Phase 3 — GitOps: ArgoCD가 platform-agent 차트를 관리
- [ ] ArgoCD `Application`으로 `infra/helm/platform-agent`(values-kind) 관리 — repo 소스는
      GitHub origin 사용(⚠️ 선행: push 필요 — 사용자 게이트) 또는 로컬 gitea 대체(선택지 B).
- [ ] sync → 차트 값 변경 커밋 → auto-sync 반영 실증. drift(수동 kubectl 변경) 자동 복원 실증.
- [ ] (선택) App of Apps: 애드온 자체(Phase 1 릴리스)를 ArgoCD 관리로 승격 — JOURNEY ch7.3 패리티.
- DoD: sync·drift 복원 증거 로그. `make check` green.

### Phase 4 — 점진 배포: Argo Rollouts
- [ ] addons에 **Argo Rollouts** helm_release 추가(버전 핀).
- [ ] 데모 워크로드 canary(단계 가중치→승격/abort) 라이브 실증 — JOURNEY ch5.3·6.3 패리티.
- [ ] 기존 deployment adapter의 자체 canary/rollback과의 관계는 **문서화만**(대체 아님 — 러너는
      cloud-neutral, Rollouts는 k8s 전용 옵트인이라는 위치 정리를 DECISIONS.md에 1건).
- DoD: canary 승격+abort 양 경로 증거 로그. `make check` green.

### Phase 5 — (선택/후속) 패리티 확장
- [ ] Loki + Fluent Bit(JOURNEY ch4.3) — 저사양 values, Grafana 데이터소스 연결.
- [ ] k3s substrate 패리티 스모크 — 동일 addons root를 Multipass k3s에 apply(kubeconfig만 교체).
- [ ] Gateway API 로컬 등가물(envoy-gateway 등) — JOURNEY ch5.2, 필요성 재평가 후.
- [ ] JOURNEY ch8 패리티(Kafka/OTel/CronJob) — 별도 plan으로 분리(이 계획 범위 밖).

## Out of scope (명시 제외)

- **GSM CSI + WI**(ch6.2) — GCP 전용. 로컬 시크릿 개선이 필요해지면 sealed-secrets를 별건으로.
- **Valkey**(ch6.1) — platform-agent가 캐시를 소비하지 않음. 도입 근거 없음.
- **CI**(ch3.4) — GitHub Actions는 리포 레벨에 이미 존재, IaC 범위 아님.
- **EKS(billable) 확장** — 로컬 완결 후 별도 승인 게이트로.

## 리스크 / 선행 조건

1. **로컬 리소스 예산** — kind 3노드 + 관측성 스택 + ArgoCD 동시 가동은 Docker VM 메모리에
   민감. Phase 1 DoD에 "저사양 values로 전 파드 Ready"를 포함해 조기 검증.
2. **Phase 3 repo 소스** — ArgoCD는 git 원격이 필요. GitHub origin 경로가 기본이나 로컬 main이
   ahead 상태(push=사용자 게이트). push 곤란 시 로컬 gitea로 대체(범위 +0.5일).
3. **포트 충돌** — kind ingress(80/443 매핑)·port-forward 대역 겹침 주의(기존 dev-up 스택과 병행 시).
4. 가드레일 유지: 버전 핀 필수·요청 밖 기능 금지·각 Phase 종료마다 `make check` + `/checkpoint`.

## 순서 제안

Phase 1 → 2가 최소 가치 단위(플랫폼 스택 + 운영 루프 연결). 3·4는 독립적이라 순서 교체 가능.
1회 세션 예상: Phase 1+2 = 1세션, Phase 3 = 0.5~1세션(선행 조건 해소 시), Phase 4 = 0.5세션.
