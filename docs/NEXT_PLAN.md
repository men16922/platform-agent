# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-20

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M9=eval·하드닝 스프린트+라이브 E2E, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 — 자율 백로그 전면 소진 (2026-07-19, gate 847)

승인된 실행 큐 8건·Google/cwc 대조 후속 ①~⑦·레퍼런스 8항목·라이브 E2E 2종(OAuth 배포 클릭·Slack 인터랙티브 승인)·표면화 버그 7건 근본수정까지 전부 완료 → `COMPLETED_SUMMARY.md` M8/M9. **아래는 전부 사용자 결정/외부 의존.**

## 사용자 게이트

- [ ] **push 여부** — 로컬 main이 origin 대비 ahead(Slack E2E~tidy 커밋들). 승인 시 `git push`.
- [x] ~~**테크 아티클 배포(LinkedIn/Medium)**~~ — **발행 완료(2026-07-25 사용자 확인)**. 원고·LinkedIn 컷·편집
  영상은 발행 후 `docs/post/`에서 제거(git 이력에 잔존, 필요 시 `git show <sha>:docs/post/…`로 복구).
  미추적 원본 녹화 `docs/post/local-onprem.mov`(22MB, gitignore)는 재편집 마스터로 **보존**.
- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=책의 GitAIOps는 AI 자리에 사람이 프롬프트를 넣지만
  우리는 **오프라인 Qwen 에이전트로 루프를 무인으로 닫는다**. 차별 소재는 자랑이 아니라 **자동화하면 새로
  깨지는 것들**: ①롤백↔selfHeal 충돌 ②자격증명=blast radius ③"실행됨≠나아짐"(`resolution_verdict`)
  ④권한 게이트 부재의 과금 누출. 재료는 이미 라이브 증거(`docs/evidence/onprem-addons-*`,
  Qwen conf 0.95 INC-95C55A19). **집필·발행은 이 계획에만 남기고 착수하지 않는다**(사용자 지시 2026-07-25).
  신규 녹화가 필요하면 Docker+kind+애드온+MLX Qwen 기동이 선행되며, ①의 auto-abort 라이브 검증을 겸할 수 있음.
- [x] ~~(billable) `terraform apply`~~ — **완료(2026-07-19)**: 실 apply(재개 포함)→EKS 노드 Ready·Aurora available·IRSA trust 재배선 검증→destroy 29개·잔존 0, ≈$0.5 미만. 증거 `docs/evidence/terraform-aws-production-apply-live.log`. **#7-b 전 단계 실증 완결.**
- [x] ~~(선택) On-Prem 승인 게이트 Slack 버튼 연동~~ — **완료(2026-07-19, `617839b`, gate 854)**: DynamoDB 공유 매체 + 옵트인 폴러, 라이브 왕복(APR-3E6D2540→INC-FA2143AF resolved). 증거 `docs/evidence/onprem-slack-approval-live.log`.
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0라 유지 중.

## 신규 백로그 — On-Prem 플랫폼 애드온 스택 IaC (2026-07-20 시드, 승인 대기)

JOURNEY.md 범위(GitOps·관측성·점진 배포)를 로컬 On-Prem($0)으로 확장.
상세: `docs/plans/2026-07-20-onprem-platform-addons.md` (Phase 1~5, DoD/리스크 포함).

- [x] ~~**Phase 1**~~ — **완료(2026-07-20)**: `infra/onprem/addons/` root(helm provider, argo-cd 10.1.4=앱 v3.4.5·kps 87.17.0 핀, 저사양 values) apply→전 파드 Ready→UI 3종 200. 가드 +7. 증거 `docs/evidence/onprem-addons-phase1.log`.
- [x] ~~**Phase 2**~~ — **완료(2026-07-20)**: Alertmanager receiver→in-cluster `webhook-service`(templatefile 주입) + 데모 룰. 라이브: crashme 크래시루프→룰 발화(~3분)→배달→4-step→P2 parking(APR-6C9CD1F2)→approve→INC-96D41C2B resolved. 증거 `docs/evidence/onprem-addons-alertmanager-e2e.log`. (analyzer 휴리스틱 폴백=설계된 오프라인 경로.)
- [x] ~~**Phase 3**~~ — **완료(2026-07-20, `fafacc6`, gate 865)**: `gitops.tf`가 ArgoCD `Application`(로컬 래퍼 차트, argocd depends_on)로 platform-agent 차트를 GitHub origin main에서 auto-sync·selfHeal 관리. annotation 추적으로 instance 라벨 충돌 회피·`releaseName=pa`로 Phase 2 접점 보존. 라이브: Synced/Healthy→6 리소스 채택→drift selfHeal ~16s. 증거 `docs/evidence/onprem-addons-gitops-e2e.log`.
- [x] ~~**Phase 4**~~ — **완료(2026-07-20, gate 867)**: `rollouts.tf`(argo-rollouts 2.41.1 컨트롤러 + 데모 canary, 무기한 pause 수동게이트). 라이브 promote(→yellow stable)·abort(→yellow 롤백 유지) 양경로. 위치 정리 = **DECISIONS D19**(러너 무변경, k8s 전용 병존). 증거 `docs/evidence/onprem-addons-rollouts-e2e.log`.
- [~] **Phase 5**(선택) — **Loki/Fluent Bit + k3s 패리티 완료(2026-07-20~21, gate 870)**: (a) `logging.tf`(loki 7.1.0 SingleBinary·캐시off + fluent-bit 0.57.9) + grafana Loki 데이터소스 라이브(`pa-platform-agent-webhook` 로그까지 Loki 적재). (b) **k3s 기판 패리티 스모크**: 동일 root를 별도 workspace+kubeconfig 교체로 k3s(v1.31.4)에 apply→ArgoCD 5/5 Ready→destroy·VM 복원(`docs/evidence/onprem-addons-k3s-parity.log`, kind default state 무손상).
  - **Gateway API 로컬 등가물 = 보류(2026-07-21 재평가)**: platform-agent 워크로드는 in-cluster ClusterIP 서비스만 소비하고 외부 라우팅 소비처가 없음 → 데모용 envoy-gateway 설치는 소비처 없는 스코프-크립+kind 풋프린트 부담. 실 소비처(외부 노출 필요) 생기면 재개. → **애드온 스택 백로그 소진.**

## 신규 백로그 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on (2026-07-21 설계 v4 확정, 착수 대기)

사용자 방향: on-prem이라도 여러 env에 동시 배포, env마다 add-on·격리·GitOps엔진 상이(어느 클라우드든 동일).
**설계 문서**: `docs/plans/2026-07-21-multi-tenant-env-addons.md` (v5) · **의사결정·MAD 히스토리**: `docs/plans/2026-07-21-multi-tenant-env-addons-mad-history.md`. **등급 확정 파이프라인**: 원칙-아키텍트
rubric(8기준) → **MAD(Advocate/Critic, Judge)** 수렴 A+(92) → **평가 에이전트 ground-truth 재리뷰**(코드 주장 2건
오류 적발) → v4 정정 → Fable 5 A+(91) → **S-델타 3건(실행위치·broker 인가·read push) 소진 v5** → **Fable 5 재평가 = S (93.5/100)**. 목표 A+~S **초과 달성(S)**.
확정 아키텍처: **capability, implementation-pluggable**(cloud-neutral DNA 확장) — Tenant=격리 티어 정책
(soft/vcluster/dedicated), Env=cluster(멀티클라우드), Delivery=ArgoCD|Fl|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: 에이전트 실행 blast radius=1 tenant/env(자격증명이 경계, 실행 경로 코드 seam으로 강제).

- [ ] **Phase 0**: `platform/` 레지스트리 스키마(파티션) + 로더(py/ts) + 어댑터 계약 + NormalizedAddonStatus(2축) 타입.
- [ ] **Phase 1a**: 실행 자격증명 격리(최소 증명) — `_run_external_action→run_onprem_action` scope 관통, ambient 삭제,
  인시던트당 단기 토큰, 크로스테넌트 액션 Forbidden 라이브 증명. (S 잔여: broker 인가·kubectl 실행위치 결정)
- [ ] **Phase 1b**: Delivery 어댑터 2개 실제(argocd+flux) + TF↔GitOps no-churn 핸드오프 + **순서 보장 이관**
  (핸드오프로 사라지는 TF `depends_on`의 대체 = ArgoCD `sync-wave` / Flux `dependsOn`, 2026-07-25 추가).
- [ ] **Phase 2**: Capsule(soft)+RBAC + 대시보드 tenant/env 스위처 + 라이브 상태 폴러(2축 drift).
- [ ] Phase 3(인가 강화)·4(managed 어댑터, billable)·5(레지스트리 PR 쓰기) = 후속.
- **S 달성(93.5)** = ①실행위치=in-cluster 러너 ②token broker=incident provenance 바인딩 ③read=push(허브 read 자격증명 0). Phase 1a 진입 시 명시할 2차 잔여: agent→hub push 인증·승인레코드 one-time nonce·push heartbeat(staleness).

## 신규 백로그 — GitAIOps 실습서 대조 후속 (2026-07-25 시드)

상세·근거·안티패턴: `docs/reference/gitaiops-notiflex-book.md`. 멀티테넌트 Phase 0과 **독립**이라 끼워넣기 가능.

- [x] ~~**① Rollouts AnalysisTemplate**(1단계)~~ — **라이브 실증 완료(2026-07-26, `b07523b`)**: 양방향 —
  나쁜 canary는 `failed(3)>failureLimit(2)`로 **사람 개입 0, ~105초 auto-abort**(stable 4/4 유지), 좋은 canary는
  3연속 Successful로 **abort 안 됨**(false-negative 기계 아님). `var.rollouts_demo_analysis_enabled`로 IaC 토글.
  기본 OFF 유지(Phase 4 수동 데모가 문서화된 walkthrough라서). 증거 `docs/evidence/onprem-addons-rollouts-analysis-e2e.log`.
  - [ ] **2단계(잔여)**: `web` provider가 **platform-agent decision 엔드포인트**를 호출해 LLM confidence를 canary
    게이트로(D19 층 유지: 러너 무변경, Rollouts가 에이전트를 판정자로 소비).
- [x] ~~**② OTel → Tempo**~~ — **라이브 실증 완료(2026-07-26, `b07523b`)**: Tempo query API·Grafana 프록시 양쪽에서
  트레이스 조회, Grafana 4 데이터소스(Alertmanager/Loki/Prometheus/**Tempo**). **결과: 인시던트 5026ms 중
  analyze 4136ms = MTTR의 82%가 로컬 LLM 추론** — 이전엔 답할 수 없던 질문이 측정값이 됨.
  증거 `docs/evidence/onprem-tracing-tempo-e2e.log`. 함정: `-target=tempo`만 apply하면 데이터소스가 안 생김(kps도 필요).
  - [ ] **잔여(선택)**: 인시던트 상세 페이지에서 `trace_id`로 Tempo 딥링크 · executor span(현재 parking 경로만 실증).
- [~] **③ 런북 사후검증** — **계약+판정 seam 완료(2026-07-25, `5fba0af`, gate 892)**: `RunbookStep.verify`
  (`StepVerification`) + `resolution_verdict()` 2축 판정(resolved/dispatched/**verified**, 검증 없으면
  verified=None="모름"이고 판정은 기존 규칙과 동일=역호환) + executor `resolved` 배선 + 카탈로그 4스텝. **잔여**:
  provider측 verify 실행부(`assert_workload_ready` 등을 실제 read로 해결) — Phase 1a의 `_run_external_action`
  시그니처 변경과 같은 경로라 **Phase 1a와 함께** 하는 것이 안전(단독 착수 시 충돌).
- [x] ~~**④ 권한 통제 3단 분리**~~ — **완료(2026-07-25, 비커밋 개인 스코프)**: `settings.local.json`의
  `gcloud:*`/`aws:*`/`az:*` 포괄 allow 제거 → 조회 동사 allow(104건) + billable 생성/삭제·terraform apply/destroy·
  helm install/upgrade를 `ask`(30건). D16의 "billable=사용자 게이트"를 로컬 설정이 우회하던 상태 차단.
  짝: `scripts/provision_gke_live.py` 3중 TTL 워치독 커밋(워치독=생성 이후, 권한게이트=생성 자체).
- [~] **⑥ NetworkPolicy** — **집행·시맨틱 라이브 실증 완료(2026-07-26, `b07523b`)**: kind(k8s v1.34.0, 기본
  kindnet) = **ENFORCED**, 차트 렌더 정책으로 같은 테넌트 REACHABLE / 크로스테넌트 BLOCKED 실증(적용 전엔 둘 다
  REACHABLE). 검증기 자체 버그 2건도 라이브가 적발(agnhost `connect`는 http/URL 불가 · 파드 Ready≠포트 바인딩).
  증거 `docs/evidence/onprem-netpol-tenancy-e2e.log`. **차트는 기본 OFF 유지 — 이유 변경**: 집행 불명이 아니라
  대상 namespace·tenant 라벨이 **Phase 2 Capsule 산출물**이라서. Phase 2에서 함께 켠다.
  - [ ] **잔여**: PSS `restricted` 프로파일 · 이미지 서명(Cosign) — 별도 승인 필요. k3s(flannel)는 집행이
    전이되지 않으므로 그 기판에서 검증기 재실행 필요.

## 신규 백로그 — 라이브 실행이 표면화한 별도 결함 (2026-07-26)

- [ ] **capability 런북이 decision 단계에서 사용 불가** — 라이브 인시던트에서 `decision.candidate.invalid` 4건
  관측 후 `generic-recovery`(알림만)로 폴백. 원인 2겹: (a) DynamoDB `incident-runbooks` 시드 행이 `alarm_name`
  없이 저장돼 `require_alarm_name=True` 검증 탈락, (b) **`CAPABILITY_RUNBOOKS` 9개 전부** base `validate_runbook`
  미통과(`steps`만 있고 `actions`/`capabilities` 키 없음 — `capabilities`는 dataclass 파생 property).
  즉 capability 런북은 현재 **장식**이고 `capability_schema.py`는 테스트만 소비. OOMKilled가 restart+rollback
  런북이 아니라 알림으로 처리되는 실질 영향. 시드 계약과 스키마 접점을 함께 고쳐야 함(단독 수정 시 회귀 위험).
- [ ] **⑦ TTL 스위퍼 CronJob** (승인 필요) — 로컬 워치독이 못 지키는 케이스(머신 자체 사망) 보완. 라벨/생성시각
  기준 TTL 초과 클라우드 리소스 **신고**(삭제는 승인 게이트).

## 리팩토링 후속 — 완료(2026-07-20, `8792c9c`, gate 854 유지)

- [x] ~~`operations` 그룹핑 축 통일~~ — `operations/aws/` + `operations/runners/` 신설, gcp/azure와 동형.
- [x] ~~`approval_bridge/handler.py` 분리~~ — handler/request_store/slack_interactive/payloads 4모듈, 패치 타깃 재작성 완료.
- 참고(유지): `_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이). detector/analyzer/decision은 SDK 90%+ 상이라 DRY 안 함(의도적).

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 재평가 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴 메모(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지(계약/방법론만); 정적 무조건 fan-out은 self-consistency 라우팅 회귀라 금지; 자유텍스트 spawn_subagent 핵 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
