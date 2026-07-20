# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-21

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-21 — 멀티테넌트/멀티클라우드 플랫폼 설계 확정 — S(93.5) via MAD (코드 무변경, 문서)

- Status: 사용자 방향(on-prem이라도 멀티-env·env별 add-on·클라우드 무관)을 플랫폼 설계로 확정. **코드 착수 전**.
- Changed(`95f1381`): 설계 v5 `docs/plans/2026-07-21-multi-tenant-env-addons.md` + 의사결정·MAD 히스토리
  `-mad-history.md` + NEXT_PLAN 백로그. 아키텍처=**capability, implementation-pluggable**(cloud-neutral DNA 확장):
  Tenant=격리 티어 정책(soft/vcluster/dedicated), Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux 어댑터,
  SSOT=per-tenant git 레지스트리. 최우선 불변식=에이전트 실행 blast radius 1 tenant/env(자격증명이 경계 —
  in-cluster 러너·incident-provenance broker·read push로 봉인).
- Verified: **등급 확정 파이프라인** — 원칙-아키텍트 rubric(8기준·보안16 최대) → **MAD(Advocate/Critic/Judge)**
  A+(92) → **평가 에이전트 ground-truth 재리뷰**(코드 주장 2건 오류 적발: NormalizedIncident namespace 부재·
  resolve_action seam 오인) → v4 정정 Fable5 A+(91) → S-델타 3건 소진 v5 → **Fable5 재평가 = S(93.5)**. 목표 A+~S 초과.
- Blockers: 없음. 2차 잔여(Phase 1a 진입 시): agent→hub push 인증·승인레코드 one-time nonce·push heartbeat.
- Next: Phase 0(레지스트리 스키마+어댑터 계약+NormalizedAddonStatus 2축) → Phase 1a(자격증명 격리 seam).

## 2026-07-21 — 대시보드: On-Prem 분석 Qwen 우선 + 인시던트 상세뷰 + 스택 링크 + AWS데모 제거 (gate 876)

- Status: 애드온 스택 라이브 데모 중 표면화한 대시보드 개선 4건. 사용자 요청 기반.
- Changed(`4aef387`·`74d7a9d`·`7ca72ed`): (1) **analyzer LLM 백엔드 pluggable**(`ANALYZER_LLM_ENDPOINT` 있으면
  OpenAI 호환 로컬 Qwen, 없으면 Bedrock; AWS 무변경·역호환) + 파서 견고화(Qwen 트레일링 텍스트) + onprem 어댑터
  per-alert annotations 캡처 + 프롬프트 alert detail 주입 + 인시던트 confidence 영속화. Makefile onprem-webhook Qwen 배선.
  (2) **인시던트 상세 페이지** `incidents/[id]`(LLM root-cause·confidence 미터·분석 모델 귀속), 카드 클릭 링크.
  (3) **스택 바로가기**를 Provisioning "Platform add-ons"로 이관(IaC 메타·env 기반 URL, prod-safe 가드).
  (4) **AWS 데모 제거**(mock 승인/인시던트 병합 중단) + 배지 정직화(hybrid→local, 거짓 LIVE·AWS 제거).
- Verified: `make check` → **876 passed, 1 skipped**(870→876, +6). tsc 클린. **라이브($0, 로컬 Qwen 7B)**:
  OOMKilled alert → 호스트 webhook(Qwen) → confidence **0.95** + 정확한 OOM root cause → approve → INC-95C55A19
  상세뷰 렌더. DECISIONS 후보=analyzer Qwen 백엔드.
- Blockers: 없음.
- Next: (설계) 위 플랫폼 Phase 0.

## 2026-07-21 — On-Prem 애드온 스택 Phase 5 k3s 기판 패리티 스모크 (코드 무변경, gate 870 유지)

- Status: Phase 5(선택) 잔여 "k3s 패리티" 소진. **동일 addons root가 kubeconfig/context 교체만으로 k3s에 이식됨**을 실증(versions.tf가 광고하는 "kind·k3s 양기판" 계약 검증). 잔여 Phase 5 = Gateway API(필요성 재평가 후)뿐.
- Changed(repo 코드 무변경): 증거 `docs/evidence/onprem-addons-k3s-parity.log`만 추가. addons 모듈·values·테스트 전부 무변경(런타임 var만 교체).
- Verified (라이브 $0, Multipass k3s v1.31.4 on k8s-lab VM 2CPU/3.8GiB): **별도 terraform workspace `k3s`**(state 격리 → kind `default` state 무손상)에서 `terraform apply -target=helm_release.argocd -var kubeconfig_path=<k3s> -var kube_context=k3s-lab` → **ArgoCD 5/5 파드 Ready**(동일 저사양 values, server available=1). 3.8GiB VM 예산 존중해 코어(ArgoCD)로 스코프. 이후 destroy(1 destroyed)→workspace 삭제→빈 argocd ns 정리 → **VM 베이스라인 복원**, default workspace의 kind 리소스 7개 온전 재확인.
- Blockers: 없음. 메모: 전체 관측성 스택(kps+loki 등 20+파드)은 3.8GiB VM엔 과함 → 코어 패리티로 충분(값 동일·기판 이식성 입증). k3s 기본 SC=local-path(kind=standard)라 PVC 소비 컴포넌트는 storageClass 오버라이드 필요(ArgoCD는 PVC 없음).
- Next: (선택) Gateway API 로컬 등가물(필요성 재평가) · 잔여 사용자 게이트(아티클 배포).

## 2026-07-20 — On-Prem 애드온 스택 Phase 5(로깅): Loki + Fluent Bit → Grafana 데이터소스 라이브 실증 (gate 867→870)

- Status: `docs/plans/2026-07-20-onprem-platform-addons.md` Phase 5(선택) 중 **Loki/Fluent Bit 증분 완료** — 관측성 삼각 완성(metrics=Prometheus 기존 + logs=Loki 신규). 잔여 Phase 5 = k3s 패리티·Gateway API(선택).
- Changed: 신규 `logging.tf`(grafana/loki **7.1.0**=v3.6.8 SingleBinary + fluent/fluent-bit **0.57.9**=v5.0.9 DaemonSet, fluent-bit가 loki `depends_on`) + 저사양 `values/loki.yaml`(SingleBinary·filesystem·**chunks/results 캐시 off**=멀티-Gi 풋프린트 함정 회피·backend/read/write replicas 0)·`values/fluent-bit.yaml`(tail→k8s 필터→loki 출력, Auto_Kubernetes_Labels). `values/kube-prometheus-stack.yaml` grafana에 **Loki additionalDataSources** 배선. 가드 +3(SingleBinary+캐시off·fluent-bit→loki gateway·grafana Loki 데이터소스), 핀 계약 3→5.
- Verified: `terraform validate` Success · `make check` → **870 passed, 1 skipped**(867→870). **라이브($0, kind)**: apply(2 added+kps 1 changed)→loki-0 2/2·loki-gateway 1/1·fluent-bit DaemonSet 2/2 Ready. **로그 적재 확증**: Loki query API가 argocd/monitoring/default/kube-system 네임스페이스 라인 반환(k8s 레이블 enrich), 그중 **`pa-platform-agent-webhook` 자체 로그** 포함. Grafana 데이터소스 목록에 Loki 등록 확인(Alertmanager/Loki/Prometheus 3종). 증거 `docs/evidence/onprem-addons-logging-e2e.log`.
- Blockers: 없음. 메모: Grafana `/resources` 프록시 프로브가 404(프로브 URL 경로 이슈)였으나 데이터소스 등록·게이트웨이 직접 쿼리로 적재는 이미 입증 — 데이터소스 결함 아님.
- Next: (선택) Phase 5 잔여(k3s 패리티·Gateway API) · 잔여 사용자 게이트(아티클 배포).

## 2026-07-20 — On-Prem 애드온 스택 Phase 4: Argo Rollouts canary promote/abort 라이브 실증 (gate 865→867)

- Status: `docs/plans/2026-07-20-onprem-platform-addons.md` Phase 4 = IaC+라이브 증거 완결. 애드온 스택 Phase 1~4 전부 완료(Phase 5 선택만 잔여).
- Changed: 신규 `rollouts.tf`(argo-rollouts **2.41.1**=v1.9.1 컨트롤러 helm_release + 데모 canary `charts/rollouts-demo`가 컨트롤러 `depends_on`) + 저사양 `values/argo-rollouts.yaml`(대시보드 on). 데모 Rollout=weighted canary(25→50→75)에 **무기한 `pause: {}` 수동 게이트**(50%) — promote/abort 구동점. 가드 +2(데모 차트 존재·canary 수동게이트), 핀 계약 2→3. **위치 정리: DECISIONS D19**(러너=cloud-neutral 애플리케이션 레벨, Rollouts=k8s 전용 인프라 레벨 → 대체 아닌 병존, 러너 무변경).
- Verified: `terraform validate` Success · `make check` → **867 passed, 1 skipped**(865→867). **라이브($0, kind)**: 컨트롤러 Ready+Rollout Healthy(blue). **경로 A(promote)**: blue→yellow canary가 수동 게이트(50%)에서 ~60s 정지→promote→75%→100%→yellow stable. **경로 B(abort)**: yellow→red canary 25%→abort→Degraded/RolloutAborted, red 축소, **yellow stable 유지**(롤백 시맨틱)→spec 복원 후 Healthy. 증거 `docs/evidence/onprem-addons-rollouts-e2e.log`.
- Blockers: 없음.
- Next: 애드온 스택 코드 완결. (선택) Phase 5(Loki/Fluent Bit·k3s 패리티·Gateway API) · 잔여 사용자 게이트(아티클 배포).

## 2026-07-20 — On-Prem 애드온 스택 Phase 3: ArgoCD GitOps로 platform-agent 차트 관리 + 라이브 실증 (gate 861→865)

- Status: `docs/plans/2026-07-20-onprem-platform-addons.md` Phase 3 = IaC+라이브 증거 완결. Phase 4(Argo Rollouts) 대기.
- Changed(`fafacc6`): 신규 `gitops.tf`(helm_release `platform_agent_app`, argocd `depends_on`) — Application CR을 로컬 래퍼 차트 `charts/platform-agent-app`로 배포해 **plan-time argoproj.io CRD 불필요**. Application은 repoURL/path/rev/valueFiles를 values 주입, automated **selfHeal+prune**, cascade-delete finalizer. `releaseName=pa`로 Phase 2 webhook Service명(`pa-platform-agent-webhook`) 보존 → Alertmanager receiver URL 무변경. `values/argocd.yaml`에 **`application.resourceTrackingMethod=annotation`**(차트가 찍는 `app.kubernetes.io/instance` 라벨과 ArgoCD label 추적의 충돌 근본 회피, Argo 공식 권장). `variables.tf` gitops_* 6종(기본=GitHub origin main). 가드 +4.
- Verified: `terraform validate` Success · `make check` → **865 passed, 1 skipped**(861→865). **라이브($0, kind)**: apply→Application `platform-agent` **Synced/Healthy**(revision=git HEAD `25d8e89`)→기존 **6 리소스 무중단 채택**(webhook·svc·SA·PVC·Role·RB)→drift(`scale 1→3`)→**selfHeal ~16s 내 replicas=1 복원**→Alertmanager接点 보존. 증거 `docs/evidence/onprem-addons-gitops-e2e.log`.
- Blockers: 없음. 규명·해결: instance 라벨 추적 충돌 → annotation 추적 전환으로 근본 해결(DECISIONS 기록).
- Next: Phase 4(Argo Rollouts canary 승격/abort + 러너 위치 정리 DECISIONS 1건) · Phase 5 선택.

## 2026-07-20 — On-Prem 플랫폼 애드온 스택 Phase 1+2: addons IaC + Alertmanager→4-step 라이브 E2E (gate 854→861)

- Status: 신규 백로그(JOURNEY 범위 로컬 확장, `docs/plans/2026-07-20-onprem-platform-addons.md`) Phase 1·2 완료. Phase 3(GitOps)·4(Rollouts) 대기.
- Changed: 신규 `infra/onprem/addons/` terraform root — helm provider(~>3.0), kubeconfig/context 변수로 kind·k3s 양기판 적용, **argo-cd 10.1.4**(앱 v3.4.5=JOURNEY 동일)+**kube-prometheus-stack 87.17.0** 정확 핀, 저사양 values(CPU requests ≤50m 계약, kind 불가 컨트롤플레인 스크랩 4종 off). Alertmanager receiver→in-cluster `pa-platform-agent-webhook`(templatefile `webhook_url` 주입, Watchdog은 null 라우트) + 데모 룰 `PlatformDemoCrashLoop`(restarts>2/5m, for 1m). 가드 `tests/test_onprem_addons_module.py` +7(핀·저사양 계약·receiver 배선·룰 존재·validate).
- Verified: `make check` → **861 passed, 1 skipped**(229.27s, 854→861). **라이브($0)**: kind 3노드 apply→ArgoCD 5파드+모니터링 8파드 전부 Ready→UI 3종(ArgoCD/Grafana/Prometheus) 200. **E2E**: crashme 크래시루프→룰 발화(~3분)→Alertmanager 배달→webhook 4-step→P2 parking(APR-6C9CD1F2)→approve→executor(log-only)→**INC-96D41C2B resolved=true**. 증거 `docs/evidence/onprem-addons-phase1.log`·`onprem-addons-alertmanager-e2e.log`.
- Blockers: 없음. 규명 메모: 인클러스터 analyzer의 휴리스틱 폴백(Bedrock 자격증명 없음)은 설계된 오프라인 경로(`onprem_incident_pipeline` docstring) — 차트 `llm.endpoint`는 배포 플레인 router 전용, 버그 아님.
- Next: Phase 3(ArgoCD Application으로 차트 GitOps — ⚠️ 선행: push 또는 로컬 gitea) · Phase 4(Argo Rollouts canary) · Phase 5 선택.
