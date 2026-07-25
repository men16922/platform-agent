# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-26

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M9=eval·하드닝 스프린트+라이브 E2E, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 (2026-07-26, gate 1017)

**멀티테넌트 플랫폼 Phase 0·1a 완료** — 최우선 불변식(자격증명이 경계)이 코드 seam + 라이브 RBAC로 강제됨.
GitAIOps 대조 갭 6건 소진 + 라이브 실증 3건 + 런북 전량 무력화 Decimal 결함 근본수정.
**다음 = Phase 1b**(delivery 어댑터 2개 · 순서 보장 이관 · no-churn 핸드오프).
이전 마일스톤(M8 레퍼런스 8/8, M9 eval·하드닝) → `COMPLETED_SUMMARY.md`.

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

## 완료 — On-Prem 애드온 스택 IaC (Phase 1~5, 2026-07-20~21)

ArgoCD GitOps·kube-prometheus-stack·Argo Rollouts·Loki/Fluent Bit + k3s 기판 패리티까지 전 Phase 완료(gate 870).
상세·라이브 증거: `docs/plans/2026-07-20-onprem-platform-addons.md` · `docs/evidence/onprem-addons-*.log` ·
`docs/archive/progress-2026-07.md`. Gateway API는 소비처 부재로 **의도적 보류**(실 외부 노출 요구 생기면 재개).

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on (설계 v5 = S 93.5, Phase 0·1a 완료)

사용자 방향: on-prem이라도 여러 env에 동시 배포, env마다 add-on·격리·GitOps엔진 상이(어느 클라우드든 동일).
**설계 문서**: `docs/plans/2026-07-21-multi-tenant-env-addons.md` (v5) · **의사결정·MAD 히스토리**: `docs/plans/2026-07-21-multi-tenant-env-addons-mad-history.md`. **등급 확정 파이프라인**: 원칙-아키텍트
rubric(8기준) → **MAD(Advocate/Critic, Judge)** 수렴 A+(92) → **평가 에이전트 ground-truth 재리뷰**(코드 주장 2건
오류 적발) → v4 정정 → Fable 5 A+(91) → **S-델타 3건(실행위치·broker 인가·read push) 소진 v5** → **Fable 5 재평가 = S (93.5/100)**. 목표 A+~S **초과 달성(S)**.
확정 아키텍처: **capability, implementation-pluggable**(cloud-neutral DNA 확장) — Tenant=격리 티어 정책
(soft/vcluster/dedicated), Env=cluster(멀티클라우드), Delivery=ArgoCD|Fl|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: 에이전트 실행 blast radius=1 tenant/env(자격증명이 경계, 실행 경로 코드 seam으로 강제).

- [x] ~~**Phase 0**~~ — **완료(2026-07-25, `303f4a2`, gate 958)**: `platform/` 레지스트리(파티션·isolation·quota·prefix) + 로더(py/ts) + `DeliveryAdapter` 계약(tenant/env 관통) + `NormalizedAddonStatus`(2축+applicable). 동작 무변경.
- [x] ~~**Phase 1a**: 실행 자격증명 격리~~ — **완료(2026-07-26, `0bb993f`, gate 1007)**: `IncidentScope` +
  provenance 바인딩 `TokenBroker`(호출자 tenant 문자열 불신, attested 레코드의 tenant로만 발급, nonce 1회용) +
  `NormalizedIncident.tenant/env` 1급 필드 + 실행 경로 scope 관통 + **ambient kubeconfig 경로 삭제**.
  **라이브 DoD 통과**(`docs/evidence/phase1a-credential-isolation.log`): acme→acme 실행 성공 / acme→globex
  거부 / **advisory 가드를 끄면 API 서버가 `Forbidden`**(자격증명이 경계임을 RBAC로 증명) / 위조 tenant 발급
  거부 / scope 없는 live 거부. 잔여(2차): agent→hub push 인증 · 서명키 custody·rotation · push heartbeat.
- [~] **Phase 1b** — **어댑터 2개 + 순서 보장 + 핸드오프 프리플라이트 완료(`738c812`·`e48c5f6`, gate 1079)**: `argocd`/`flux`가
  계약의 세 압박점(순서 원시형·상태 어휘·객체 형태)을 각자 방식으로 만족. wave→`sync-wave`(문자열) /
  `dependsOn`(객체 참조)로 **TF `depends_on` 대체물** 확보. render 결정론·tenant 접두사·라벨 질의성·
  Flux `releaseName` 안정을 가드로 고정. **프리플라이트**(`scripts/preflight_gitops_handoff.py`)가
  `state rm` 전에 4검사(ownership·stateful·source-reachable·baseline)로 안전성을 증명하고 롤백 명령을 선출력.
  **라이브 read-only 결과**: ownership은 전 릴리스 통과(최대 미지수 해소). **잔여 = 블로커 2종 해소 후 실행**:
  (a) loki/tempo/pa가 데이터 보유 → **스냅샷 수단 선행**(kind엔 CSI 스냅샷터 기본 부재),
  (b) 로컬이 origin ahead → 지금 채택하면 **옛 차트 내용**이 적용됨(push는 사용자 게이트).
  `rollouts-demo`가 데이터 위험 0이라 push 후 첫 대상. 증거 `docs/evidence/gitops-handoff-preflight.log`.
- [ ] **Phase 2**: Capsule(soft)+RBAC + 대시보드 tenant/env 스위처 + 라이브 상태 폴러(2축 drift).
- [ ] Phase 3(인가 강화)·4(managed 어댑터, billable)·5(레지스트리 PR 쓰기) = 후속.
- **S 달성(93.5)** = ①실행위치=in-cluster 러너 ②token broker=incident provenance 바인딩 ③read=push(허브 read 자격증명 0). Phase 1a 진입 시 명시할 2차 잔여: agent→hub push 인증·승인레코드 one-time nonce·push heartbeat(staleness).

## GitAIOps 실습서 대조 후속 — 6/7 완료, 잔여만 (근거: `docs/reference/gitaiops-notiflex-book.md`)

**완료**: ①Rollouts AnalysisTemplate(라이브 양방향, `b07523b`) · ②OTel→Tempo(MTTR의 82%가 로컬 LLM 추론) ·
③런북 사후검증(provider 실행부까지, `d68fe6b`) · ④권한 통제 3단(비커밋 개인 스코프) · ⑤Sync Wave(Phase 1b로
흡수, `738c812`) · ⑥NetworkPolicy 집행·시맨틱 실증 · ⑦고아 클러스터 스위퍼. 증거 `docs/evidence/*`.

- [~] **① 2단계** — **코드·차트·테스트 완료(2026-07-26, `b9eafb0`, gate 1114)**: `canary_judge` +
  `POST /canary/judge` + `web` provider 템플릿. 판정 3규칙 전부 안전한 방향 기본값(저신뢰→unknown이 P1보다
  우선, unknown은 승격 안 됨), 게이트는 **분석만**(execute=False). 인클러스터 엔드포인트 200 실증.
  **잔여**: canary 전체 E2E(AnalysisRun→abort). 주의 — 인클러스터 analyzer에 모델이 없어 현재 모든 판정이
  `unknown`이라 **pass 경로 라이브 확인엔 클러스터 도달 가능한 LLM 엔드포인트가 필요**.
- [x] ~~**② 잔여 — Tempo 딥링크**~~ — **완료(2026-07-26, `90a92ba`, gate 1095)**: `trace_id`를 파이프라인→
  레코드→대시보드까지 관통, 상세 페이지에서 Grafana Explore로 딥링크. prod-safe(`stack-links` 규칙:
  미설정이면 **링크 없음** — 죽은 링크는 "트레이싱 꺼짐"을 "트레이스 없음"으로 오독시킴).
  라이브: record trace_id로 Tempo 200 + span 4개.
  - [ ] 잔여(선택): executor span(현재 parking 경로만 실증 — 승인 후 실행 경로는 미측정).
- [ ] **⑥ 잔여(승인 필요)**: PSS `restricted` · 이미지 서명(Cosign). 차트 자체는 Phase 2(Capsule이 대상
  namespace·tenant 라벨을 만듦)에서 켠다. k3s(flannel)는 집행이 전이되지 않으므로 검증기 재실행 필요.

## 신규 백로그 — 라이브 실행이 표면화한 별도 결함 (2026-07-26)

- [x] ~~**런북이 decision 단계에서 전량 탈락**~~ — **근본수정 완료(2026-07-26, `b078094`, gate 1017)**.
  최초 가설(시드 `alarm_name` 누락 / CAPABILITY_RUNBOOKS 스키마)은 **둘 다 오진**이었고, 라이브 테이블을 직접
  스캔해 진짜 원인을 특정: **DynamoDB가 숫자를 `Decimal`로 반환** → `isinstance(Decimal(180), int)`가 False →
  `rto_sec`을 선언한 **모든** 런북이 후보에서 탈락, `generic-recovery`(rto=null)만 생존 → 매 인시던트가
  알림-only. `_is_integer_like` + `normalise_runbook`(읽기 경계 coerce)로 수정. 라이브 before/after
  `docs/evidence/runbook-decimal-rto-fix.log`(1/5 → **5/5** 유효, generic-recovery → **eks-pod-oom**).
- [ ] **(잔여) capability step 런북을 executor가 실제로 사용** — `capability_schema.py`(steps·`verify`)는 아직
  테스트만 소비하고 executor는 flat `actions`를 돈다. ③의 provider측 verify 실행부와 같은 작업.
- [ ] **⑦ TTL 스위퍼 CronJob** (승인 필요) — 로컬 워치독이 못 지키는 케이스(머신 자체 사망) 보완. 라벨/생성시각
  기준 TTL 초과 클라우드 리소스 **신고**(삭제는 승인 게이트).

## 유지 규약 (완료된 리팩토링에서 나온 "하지 말 것")

`_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이). detector/analyzer/decision은 SDK가 90%+
상이해 **의도적으로 DRY 안 함**. `approval_bridge` 추가 분해도 하지 않는다. 근거 → `DECISIONS.md` D15.

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 재평가 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴 메모(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지(계약/방법론만); 정적 무조건 fan-out은 self-consistency 라우팅 회귀라 금지; 자유텍스트 spawn_subagent 핵 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
