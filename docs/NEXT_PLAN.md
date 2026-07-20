# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-20

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M9=eval·하드닝 스프린트+라이브 E2E, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 — 자율 백로그 전면 소진 (2026-07-19, gate 847)

승인된 실행 큐 8건·Google/cwc 대조 후속 ①~⑦·레퍼런스 8항목·라이브 E2E 2종(OAuth 배포 클릭·Slack 인터랙티브 승인)·표면화 버그 7건 근본수정까지 전부 완료 → `COMPLETED_SUMMARY.md` M8/M9. **아래는 전부 사용자 결정/외부 의존.**

## 사용자 게이트

- [ ] **push 여부** — 로컬 main이 origin 대비 ahead(Slack E2E~tidy 커밋들). 승인 시 `git push`.
- [ ] **테크 아티클 배포(LinkedIn/Medium)** — **작성 전부 완료(잔여=배포)**: EN `docs/post/platform-agent-architecture.md` + KO `-ko.md` + LinkedIn 컷(EN/KO) `platform-agent-linkedin-cut.md` + 데모 영상 `local-onprem-edited.mp4`.
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
- [ ] **Phase 1b**: Delivery 어댑터 2개 실제(argocd+flux) + TF↔GitOps no-churn 핸드오프.
- [ ] **Phase 2**: Capsule(soft)+RBAC + 대시보드 tenant/env 스위처 + 라이브 상태 폴러(2축 drift).
- [ ] Phase 3(인가 강화)·4(managed 어댑터, billable)·5(레지스트리 PR 쓰기) = 후속.
- **S 달성(93.5)** = ①실행위치=in-cluster 러너 ②token broker=incident provenance 바인딩 ③read=push(허브 read 자격증명 0). Phase 1a 진입 시 명시할 2차 잔여: agent→hub push 인증·승인레코드 one-time nonce·push heartbeat(staleness).

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
