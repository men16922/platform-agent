# STATUS — platform-agent

최종 갱신: 2026-07-26

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 현재 요약

- 제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`.
- Operations 4단계(detect→analyze→decide→execute) 파이프라인 런타임 동작.
- 3-cloud AI Agent 실호출 완료: Bedrock Claude + Vertex AI Gemini 3.5 Flash + Azure OpenAI GPT-5.4.
- Capability-based runbook schema 구현 (cloud-neutral execution steps).
- overnight-harness 기반 자동 개발 루프 구성 완료 (5 engine 지원).
- 4 provider 코드 완비: AWS / GCP / Azure / On-Prem.

## 검증 Baseline (실제로 돌린 것만)

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
- `make check` (pytest) → **1159 passed, 1 skipped** (2026-07-26, 1114→1159, +45) — **① 게이트 완결(3종 판별) + ⑥ PSS/Cosign + ⑦ 스위퍼 CronJob**(`8e549bf`·`d96b888`·`69f149d`·`5015810`, **origin push 완료**). ①은 pass 경로를 여는 과정에서 **연쇄 결함 3건**이 드러나 전부 근본수정: (a) `llm.endpoint`를 router만 소비하고 webhook은 못 받아 **모든 판정이 unknown**이던 것(모델 부재가 아니라 배선 부재), (b) 템플릿이 firing 알럿을 **합성**해 보내 정상 canary가 conf 0.80으로 `fail`이던 것 → 호출자는 **신원만** 보내고 게이트가 Alertmanager를 직접 조회(`None`=못 봄 ≠ `[]`=조용함), (c) kps 파드 룰이 `for: 15m`이라 2~3분짜리 canary엔 발화 자체가 없어 크래시 canary도 pass이던 것 → canary 시간 스케일 룰 동봉. **라이브 3종 판별**: 정상→`pass`x3 abort 없음 / 크래시→`pass→fail→fail` **165s auto-abort**(stable 4/4, Available=True 내내) / 관측 불가→`unknown` 차단. ⑥ 양방향(비준수 설치는 API 서버가 4개 위반 적시하며 forbidden / 준수 설치는 `uid=10001` Running) + Cosign(서명은 **태그가 아니라 다이제스트**에 붙음을 라이브가 정정 → 차트 `image.digest`). ⑦은 CLI 부재가 `clean(exit 0)`이던 것을 **exit 2(coverage incomplete)** 로. 증거 `docs/evidence/onprem-{canary-agent-gate,pss-restricted-and-sweeper}-e2e.log`.
- `make check` (pytest) → **1114 passed, 1 skipped** (2026-07-26, 1095→1114, +19) — **① 2단계: 에이전트를 릴리스 게이트로**(`b9eafb0`). `canary_judge` + `POST /canary/judge` + `web` provider AnalysisTemplate. 판정 3규칙이 전부 안전한 방향 기본값(**저신뢰→unknown이 P1보다 우선**, `successCondition: result == "pass"`라 unknown은 승격 안 됨), 게이트는 **분석만**(execute=False). 라이브 부분: 이미지 재빌드→kind load→**인클러스터 `POST /canary/judge` 200**에 `verdict=unknown`(모델 부재 폴백) — "판단 불가 ≠ 승인" 실증. canary 전체 E2E는 미실행.
- `make check` (pytest) → **1095 passed, 1 skipped** (2026-07-26, 1058→1095, +37) — **TF→GitOps 핸드오프 프리플라이트**(`e48c5f6`) + **인시던트→Tempo 딥링크**(`90a92ba`). 프리플라이트는 `state rm` 전에 ownership·stateful·source-reachable·baseline 4검사로 안전성을 증명하고 롤백 명령을 선출력 — 라이브 read-only에서 **ownership 전 릴리스 통과**(최대 미지수 해소), 잔여 블로커는 스냅샷 부재와 미푸시 소스. 딥링크는 prod-safe(미설정이면 링크 없음) + 라이브 Tempo 200. 증거 `docs/evidence/gitops-handoff-preflight.log`.
- `make check` (pytest) → **1058 passed, 1 skipped** (2026-07-26, 1017→1058, +41) — **③ 사후검증 provider 실행부**(`d68fe6b`) + **Phase 1b delivery 어댑터 2개**(`738c812`). ③: `onprem_verify`가 액션과 **같은 스코프 자격증명으로** rollout status/readyReplicas/cordon을 읽어 `resolved`를 증거 기반으로. 라이브 양방향 — healthy→resolved=True / broken→**dispatched=True인데 resolved=False**(`docs/evidence/onprem-verification-e2e.log`). 1b: argocd/flux가 순서 원시형·상태 어휘·객체 형태 세 압박점을 각자 만족(wave→`sync-wave`/`dependsOn` = **TF `depends_on` 대체물**).
- `make check` (pytest) → **1017 passed, 1 skipped** (2026-07-26, 983→1017, +34) — **Phase 1a 자격증명 격리**(`0bb993f`, +24)와 **런북 전량 무력화 결함 근본수정**(`b078094`, +10). Phase 1a: `IncidentScope`+provenance 바인딩 `TokenBroker`(호출자 tenant 불신, attested 레코드로만 발급, nonce 1회용) + `NormalizedIncident.tenant/env` 1급 필드 + 실행 경로 scope 관통 + **ambient kubeconfig 삭제**. 라이브 DoD: **advisory 가드를 꺼도 API 서버가 `Forbidden`**(자격증명이 경계임을 RBAC로 증명). Decimal 결함: DynamoDB가 숫자를 `Decimal`로 반환해 `rto_sec`을 선언한 **모든 런북이 후보에서 탈락**→매 인시던트 알림-only 폴백이던 것을 읽기 경계 coerce로 수정(라이브 1/5→**5/5**, generic-recovery→**eks-pod-oom**). 증거 `docs/evidence/{phase1a-credential-isolation,runbook-decimal-rto-fix}.log`.
- **라이브 실증(2026-07-26, `b07523b`, 수 무변경)** — 기본 OFF로 남겨둔 3건 완주: ①canary 자동판정 **양방향**(나쁜 canary=`failed(3)>limit(2)`→사람 개입 0으로 ~105s auto-abort·stable 4/4 유지 / 좋은 canary=3연속 Successful→abort 안 됨) · ②Tempo 트레이스(query API·Grafana 프록시 양쪽 200, **5026ms 중 analyze 4136ms=MTTR의 82%가 로컬 LLM 추론**) · ⑥kindnet=**ENFORCED**+차트 정책 테넌트 시맨틱(same 통과/cross 차단). 증거 `docs/evidence/onprem-{addons-rollouts-analysis,tracing-tempo,netpol-tenancy}-e2e.log`. 라이브가 검증기 자체 버그 2건도 적발(agnhost `connect` http/URL 불가 · 파드 Ready≠포트 바인딩).
- (이전 이력 2026-07-10~17, gate 829 이하 → `docs/archive/status-baseline-2026-07.md`)

## 동작하는 영역 (요약)

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge.
2. **3-Cloud Day2 Operations** — AWS(Step Functions) + GCP(Cloud Workflows) + Azure(Durable Functions). 각각 4-step 파이프라인 구현.
3. **Human-in-the-loop 승인** — Slack 승인 → `WaitForTaskToken` + SQS + SFN callback.
4. **Day1/1.5** — provisioning(cdk_generator/iam_designer/cost_estimator), deployment(smoke/canary/rollback), reporting(slo/oncall/capacity).
5. **Portability** — `NormalizedIncident` cloud-neutral envelope. provider registry + adapters.
6. **Runbook registry** — built-in catalog + capability-based schema + CDK seed + scan heuristic.
7. **AI Agents** — Strands(Bedrock) + ADK(Gemini 3.5 Flash) + MSFT(GPT-5.4). 3종 tool calling 검증 완료.
8. **Guardian Agent** — Policy-as-Code (APPROVE/AUTO/REJECT).
9. **MCP + A2A Gateway** — kubectl/docker MCP (9 tools) + FastAPI A2A + Bridge.
10. **On-prem K8s** — `make local-cluster` (kind 테스트용) → 3노드 + registry + NGINX ingress.
11. **Deployment Adapters** — 4 provider (onprem/aws/gcp/azure): Build→Push→Deploy→Validate→Rollback.
12. **Execution Adapters** — 4 provider: capability → provider-specific action resolution.
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지. AWS DynamoDB 연동 완료. 모든 데모 목업 데이터를 제거하고 실시간 Live 모드만 활성화. 🔐 Auth.js 기반 GitHub OAuth, Admin/Operator/Viewer 역할 부여 및 사용자 권한 관리 제어판(잠금 방지 보호 포함), 장애 복구 승인(Pending approvals), 신규 배포 트리거/롤백 액션 패널, 보안 감사 로그(Audit Logs) 뷰어 화면 프로덕션 배포 완료.

## Active Focus

- **Phase 1b 핸드오프 = rollouts-demo 이관 완료(2026-07-26)** — TF는 Application 1개(소유 기록)만 보유, 워크로드는
  ArgoCD 소유. helm rev 8 불변 · Rollout/Service UID 불변 · selfHeal 4→2→4 ~40s. 채택이 no-op이 아니었는데
  원인은 핸드오프가 아니라 라이브 드리프트(`--type=merge`가 컨테이너 배열을 통째 교체해 ports/resources 소실)였고,
  ArgoCD가 그걸 **복구**한 것 → 프리플라이트에 5번째 검사 `live-matches-rendered`(non-blocking) 추가.
  **잔여**: loki/tempo/pa는 데이터 보유 → 스냅샷 수단 선행(kind엔 CSI 스냅샷터 부재).
- **멀티테넌트/멀티클라우드 플랫폼 — Phase 0·1a·1b(어댑터+프리플라이트) 완료** — `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5, S 93.5). Phase 1a로 **최우선 불변식(자격증명이 경계)이 코드 seam+라이브 RBAC로 강제됨**. Phase 1b = delivery 어댑터 2개(argocd+flux) + TF↔GitOps no-churn 핸드오프 + **순서 보장 이관**(sync-wave/dependsOn). ③ provider측 verify는 Phase 1a가 `incident_scope`를 이미 관통시켜 **차단 해소**.
- **라이브 실증 완료(2026-07-26)**: ①canary auto-abort 양방향(~105s, stable 유지 / 정상 canary는 통과) · ②Tempo 트레이스(**5026ms 중 analyze 4136ms = MTTR의 82%가 로컬 LLM**) · ⑥kindnet ENFORCED + 테넌트 시맨틱(same=통과, cross=차단). 증거 `docs/evidence/onprem-{addons-rollouts-analysis,tracing-tempo,netpol-tenancy}-e2e.log`. ①⑥은 검증 후에도 기본 OFF(①=문서화된 수동 데모 보존, ⑥=대상 ns/라벨이 Phase 2 Capsule 산출물).
- **완료(참고)**: On-Prem 애드온 스택 Phase 1~5(gate 870) · 대시보드 Qwen/상세뷰(gate 876) · GitAIOps 대조 갭 6건(gate 983).
- 아티클: **발행 완료**(2026-07-25). GitAIOps 후속편은 `NEXT_PLAN`에 논지만 남기고 착수 보류(사용자 지시).

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**(provider `oidc.vercel.com/men16922s-projects` 재생성, 실 team slug=Vercel API 확증). 앞으로 diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
3. **Cosign 어드미션 집행 없음(의도적)** — 서명 검증은 CI/사람용 게이트(`scripts/verify_image_signature.py`)
   까지다. 미서명 이미지를 API 서버가 거부하려면 policy controller(sigstore/Kyverno)라는 새 클러스터
   의존성이 필요해 Phase 2 네임스페이스 작업과 함께 다룬다. **지금 있는 보증을 과대 해석하지 말 것.**
4. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
