# Reference — GitAIOps 실습서(Notiflex) 대조 분석

> 외부 학습 레포 분석 노트. **platform-agent 차용 후보 패턴**만 추린다. 이식 전 검토용. 되돌리기 어려운 결정은 `DECISIONS.md`.

- **출처:** `/Users/men1692/Desktop/Study/AI 시대에 개발자가 알아야 할 인프라 구성 배포 with 클로드 코드`
  (책 저장소 `github.com/sysnet4admin/_Book_GitAIOps` 기반 실습 결과물 + 사용자 자체 정리본 `정리/Ch3~9`·`Appendix`)
- **검토일:** 2026-07-25 · 대상 커버리지: ch2~9 정리본 전문 + `Appendix A/B` + 실 산출물(`k8s/`·`argocd/`·`helm-values/`·`command-guardrails/`·`claude-context/`·`docs/`·`.claude/commands/`)
- **레포 성격:** 단일 GKE 클러스터(`notiflex-cluster`, 서울, Spot e2-medium×5, 4 노드풀)에 Go API(`notiflex`, 95줄)를
  GitOps로 올려가며 **ch2→ch9까지 문제 하나씩 해결**하는 학습 플랫폼. ch9가 그 과정을 **GitAIOps**(Git=SSOT · AI=의사결정보조+기록자 · Ops=실행자동화)로 명명·정리.

---

## 메타 결론 — 두 프로젝트는 경쟁이 아니라 **층이 다르다**

| | Notiflex(책) | platform-agent |
|---|---|---|
| 정체 | **운영 대상**(플랫폼 그 자체) | 그 플랫폼을 **운영하는 에이전트** |
| GitAIOps에서의 위치 | Git + Ops 축이 두껍고, AI는 **대화형 조수**(사람이 프롬프트) | AI 축이 두껍고 **무인 파이프라인**(detect→analyze→decide→execute) |
| 격리 | Namespace + RBAC (soft, 학습용) | 설계 S(93.5) — soft/vcluster/dedicated 3티어 + 자격증명 경계 |
| 클라우드 | GKE 단일 종속(Gateway API·WI·CSI) | 4-provider cloud-neutral (capability 레지스트리) |

→ 그래서 **아키텍처를 베낄 대상은 아니다.** 전이되는 건 (a) platform-agent에 **구멍으로 남아 있는 운영 계층**과
(b) 이미 옳게 가고 있다는 **독립 확증**이다. ch9는 우리 하네스(`AGENT_BRIEF`/`STATUS`/`DECISIONS`/`docs/plans`)가
"살아있는 문서 + 사람용 계획 ↔ AI용 증류" 라는 동일 결론에 **독립적으로 도달**했음을 보여준다 — D8이 옳았다는 외부 검증.

## 자산 대조 (책 보유 ↔ 우리 보유)

| 책의 자산 | 도입 장 | platform-agent 현황 | 판정 |
|---|---|---|---|
| ArgoCD GitOps + selfHeal | ch3 | ✅ `infra/onprem/addons/gitops.tf` (annotation 추적, D18) | 동등 |
| Prometheus/Grafana + Loki/Fluent Bit | ch4 | ✅ `monitoring.tf`·`logging.tf` (gate 870 라이브) | 동등 |
| PrometheusRule → Alertmanager | ch4 | ✅ Alertmanager→in-cluster webhook 배선 라이브 | **우리가 앞섬**(4-step 파이프라인까지) |
| Argo Rollouts Canary | ch5/6 | ✅ `rollouts.tf` — 단 **무기한 수동 pause 게이트** | 부분 |
| **AnalysisTemplate 메트릭 자동판정** | ch9.5 제언 | ❌ 없음 | **갭 ①** |
| Gateway API 외부 진입 | ch5 | 🔲 2026-07-21 보류(소비처 없음, `NEXT_PLAN`) | 의도적 미채택 |
| **OpenTelemetry → Tempo 분산 트레이싱** | ch8.2 | ❌ `trace_id` 필드만 존재(`models.py`), OTel export 없음 | **갭 ②** |
| **CronJob 주기 헬스체크** | ch8.3 | ❌ 없음 | **갭 ③** |
| **`command-guardrails/` 위험작업 절차서** | ch8.4 | ❌ 런북에 사전확인/사후검증 단계 없음 | **갭 ④** |
| **`settings.local.json` deny/ask 권한통제** | ch7.5 | ⚠️ `allow`만 있고 `gcloud:*`/`aws:*`/`az:*` **광범위 허용** | **갭 ⑤ (최우선)** |
| App of Apps + **Sync Wave 순서보장** | ch7.3 | 🔲 Phase 1b 계획에 ApplicationSet은 있으나 **Sync Wave 없음** | 갭 ⑥ |
| NetworkPolicy / ResourceQuota / PSS restricted | ch9.5 제언 | ResourceQuota만 Phase 2 계획, **NetworkPolicy·PSS 없음** | 갭 ⑦ |
| 살아있는 문서 3층 + ADR + `/update-docs` | ch5~9 | ✅ 하네스가 동형·더 강함(gate 연동) | 동등+ |
| Kafka/Strimzi · Valkey · 멀티 노드풀 | ch6~8 | ❌ 없음 | **의도적 미채택**(아래 안티패턴) |

---

## Tier 1 — 즉시 실효, 자율 가능

### ① Argo Rollouts **AnalysisTemplate** → 에이전트를 canary 판정자로 (가장 큰 서사 이득)
책 ch9.5.1의 프로덕션 제언 5번("AnalysisTemplate으로 메트릭 기반 Canary 자동 판정")은 우리 `rollouts.tf`의
**정확한 미완 지점**이다. 현재 데모 Rollout은 50%에서 `pause: {}`로 무기한 정지 → 사람이 promote/abort.
이미 있는 재료: kps Prometheus(라이브) + analyzer/decision 에이전트 + Alertmanager→webhook 경로.

- **1단계(순정)**: `AnalysisTemplate` + `prometheus` provider — 에러율/latency 임계로 canary 자동 abort.
  가드 테스트는 기존 `rollouts.tf` 가드(+2) 패턴 그대로.
- **2단계(우리만 할 수 있는 것)**: AnalysisTemplate의 `web`(또는 `job`) provider가 **platform-agent decision
  엔드포인트**를 호출 → LLM root-cause + confidence + P1/P2/P3 판정을 canary 게이트에 연결.
  D19("Rollouts는 인프라 레벨, 러너는 애플리케이션 레벨 — 병존")를 깨지 않는다: 러너 코드 무변경,
  Rollouts가 **에이전트를 판정자로 소비**하는 방향이라 층이 유지된다. 반대 방향(러너를 Rollout으로 대체)은 D19 위반.
- 라이브 검증 $0(kind), 증거는 `docs/evidence/` 관례대로.

### ② 파이프라인 자체의 OTel 트레이스 (ch8.2)
책의 통찰: "메트릭=무엇이 이상한가 → 로그=어떤 오류 → 트레이스=**어느 구간에서 막혔는가**".
우리는 metrics·logs를 갖췄고 **트레이스만 없다**. 그리고 트레이싱이 가장 필요한 대상은 앱이 아니라
**우리 4-step 파이프라인 자체**다 — "Live 7B provision→deploy→validate ~39s"의 39초가 어디서 쓰였는지,
인시던트 MTTR 중 LLM 추론이 몇 %인지 지금은 답할 수 없다.

- Span 경계는 책 기준 그대로("시스템/책임 경계만, 내부 로직은 넣지 않는다"):
  `detect` → `analyze`(LLM 호출 = 별 span, 백엔드 속성 Qwen/Bedrock) → `decide` → `execute`(kubectl 액션별) → `notify`.
- 백엔드는 OTLP 환경변수 1개(`OTEL_EXPORTER_OTLP_ENDPOINT`)로 교체 가능 — 책이 강조한 벤더 중립성이
  우리 cloud-neutral DNA와 정합(온프렘=Tempo, AWS=X-Ray/ADOT, GCP=Cloud Trace).
- 기존 `trace_id`(`models.py`·`activity_writer`)를 OTel TraceID와 **동일 값으로 정렬**하면 대시보드 인시던트
  상세 → Grafana Tempo 딥링크가 공짜로 생긴다. `logging.tf` Loki 로그에도 같은 ID가 이미 실려 있다.
- 애드온 측 증분: `infra/onprem/addons/tracing.tf`(grafana/tempo 단일 바이너리, 저사양 values) +
  kps grafana `additionalDataSources`에 Tempo 추가 — `logging.tf`가 Loki로 한 것과 **완전히 동형**이라 리스크 낮음.

### ③ `command-guardrails` 3단 구조를 **런북 스키마로** 승격 (ch8.4 + Appendix B.1.4)
책의 핵심 구분: `settings.local.json`="하지 마"(기술 통제) vs `command-guardrails/`="해야 한다면 **이 순서로**"(운영 통제).
모든 절차서가 **사전확인 → 실행 → 사후검증** 3단이다.

우리 `RunbookStep`(`runbooks/capability_schema.py:42`)에는 `condition`/`on_failure`/`timeout_sec`은 있지만
**사전확인·사후검증 단계가 없다**. 즉 executor는 "실행했다"까지만 알고 "정말 나아졌나"를 모른다
(D17의 `resolved` 시맨틱 = "모든 액션이 실행됨" — 결과 검증 아님, 이게 그 구조적 귀결).

- 제안: `RunbookStep`에 `precheck`/`verify` capability 슬롯 추가 → executor가 실행 후 verify capability를
  돌려 `resolved`를 **증거 기반**으로 만든다. 예: `restart_workload` 뒤 `wait_ready`, `scale_out` 뒤 `assert_replicas`.
- 사람용 절차서(`docs/runbooks/*.md` 3단)도 함께 두되, **1급 소스는 코드 스키마**여야 한다(책은 md만 있어
  AI가 지킬 보장이 없다 — 우리는 스키마로 강제할 수 있는 게 우위).
- 우선 대상 3종은 책이 고른 것과 우리 위험 지점이 겹친다: teardown_cluster(=Tenant NS 삭제 대응),
  scale-to-0 가드, drain_node(polite drain, D12).

## Tier 2 — 설계·승인 필요

### ④ ⚠️ 권한 통제: `gcloud:*` 광범위 allow가 GKE 방치 과금의 구조적 원인 (ch7.5)
책 ch7.5는 자연어 규칙(`CLAUDE.md` "kubectl delete 하지 마")이 **기술적으로 아무것도 막지 못한다**는 걸
실증하고 `allow`(조회) / `ask`(비용·변경) / `deny`(위험 직접변경) 3단으로 넘어간다.

우리 현황(사실): `.claude/settings.json`은 `defaultMode: "auto"`, `.claude/settings.local.json`은
**`Bash(gcloud:*)`·`Bash(aws:*)`·`Bash(az:*)`를 통째로 allow**. 즉 `gcloud container clusters create`가
**승인 없이 실행 가능**하고, 이것이 06-07·06-24·07-06·07-14 GKE 라이브 클러스터 생성(06-24 ~9시간 방치)의
경로였다. 미커밋 `scripts/provision_gke_live.py`의 3중 TTL 워치독은 **생성된 뒤**를 지키지만,
**생성 자체의 게이트**는 여전히 없다 — 두 통제는 보완재다.

- 제안: 클라우드 CLI를 **동사 단위로 쪼개** allow/ask 분리.
  `allow` = 조회(`gcloud * list|describe`, `aws sts *`, `kubectl get|describe|logs`),
  `ask` = billable 생성/삭제(`gcloud container clusters *`, `aws eks *`, `az aks *`, `terraform apply|destroy`, `helm install|upgrade`).
- 이는 우리 자체 설계와 정합: D16이 "overnight 무인 루프에서 클라우드 변경이 자동 허용되면 billable=사용자 게이트
  설계가 깨진다"고 이미 못박았는데, `gcloud:*` allow가 그 결론을 **로컬 설정에서 우회**하고 있다.
- 주의 2건: (a) 오버나이트 루프의 read-only 작업이 ask로 막히면 루프가 죽는다 → 조회 동사를 먼저 넉넉히 allow.
  (b) 책은 체험 후 `settings.local.json`을 삭제하지만, 우리는 **비커밋 개인 스코프로 유지**가 맞다(D16 (3)).

### ⑤ Sync Wave — TF→GitOps 핸드오프의 **숨은 전제** (ch7.3)
현재 애드온 순서는 Terraform `depends_on`(fluent-bit→loki, rollouts-demo→controller, gitops→argocd)이 보장한다.
그런데 Phase 1b가 계획대로 `terraform state rm`으로 소유권을 GitOps로 넘기면 **`depends_on`이 사라진다**.
멀티테넌트 설계 v5는 ApplicationSet/Flux 팬아웃은 명시했지만 **순서 보장 메커니즘을 명시하지 않았다** —
책의 `argocd.argoproj.io/sync-wave`(0 인프라/CRD → 1 플랫폼 → 2 애플리케이션)가 그 빈칸의 표준 답이다.
- 액션: `docs/plans/2026-07-21-multi-tenant-env-addons.md` Phase 1b DoD에 **"CRD/네임스페이스 wave 0,
  add-on wave 1, 워크로드 wave 2로 순서가 보장됨"** 을 추가. Flux 대응물은 `dependsOn`(Kustomization).
- 이 갭은 설계 문서 리뷰가 놓친 실제 구멍이라 기록 가치가 높다.

### ⑥ NetworkPolicy + PSS restricted — soft 티어 non-guarantee 좁히기 (ch9.5.1 #1)
우리 설계는 soft 티어의 미보호 항목을 정직히 나열한다("공유 control-plane, 커널/노드, **data-plane 격리 없음**").
책의 `deny-cross-tenant` NetworkPolicy는 그중 **data-plane 축을 실제로 좁히는** 최소 수단이고,
Pod Security Standards `restricted` + 이미지 서명(Cosign)은 우리가 아직 손대지 않은 축이다.
- 액션: Phase 2 Capsule(soft) DoD에 NetworkPolicy(테넌트 간 ingress deny) 추가 — ResourceQuota/LimitRange와
  같은 층에서 함께 강제. **선행 확인**: 기판 CNI가 NetworkPolicy를 실제로 집행하는지 — kindnet은 전통적으로
  미집행이었고 최근 지원이 추가됐으므로 **현재 kind 버전으로 실측**해야 한다(미집행이면 Calico 교체 또는
  k3s 기판에서 검증). 집행 안 되는 CNI에 정책만 올리면 "격리했다"는 거짓 신호가 된다.
- Cosign/PSS는 별도 백로그(범위 확장, 승인 필요).

### ⑦ CronJob — push agent heartbeat의 $0 구현체 (ch8.3)
설계 v5의 "2차 잔여: **push heartbeat(staleness)** — 죽은 agent가 상태를 조용히 freeze(fail-open)하지 않게"의
구체적 메커니즘이 책 ch8.3에 그대로 있다: `CronJob` + `concurrencyPolicy: Forbid` + Job history 제한, GitOps로 관리.
- 추가 용도(우리 고유): **고아 클라우드 리소스 TTL 스위퍼** — 로컬 워치독이 프로세스 SIGKILL엔 살아남지만
  머신 자체가 죽으면 무력하다. 클러스터 측 CronJob이 라벨/생성시각 기준으로 TTL 초과 리소스를 신고(삭제는 승인 게이트).

---

## 안티패턴 / 의도적 미채택 (베끼지 말 것)

- **`claude --dangerously-skip-permissions`** (ch2 설치 절차) — 책은 실습 전용 클러스터라 쓴다.
  우리 제품 정체성이 **승인 게이트**(D5·D12)라 정면 충돌. 절대 채택 금지.
- **Kafka + Strimzi**(ch8.1) — 512Mi+ 브로커. D12가 On-Prem 오케스트레이션을 **in-process 4-step**으로
  의도 선택했고 그 이유(완전 오프라인·매니지드 없음)는 유효. 이벤트 durability가 실제로 필요해지는 유일한
  지점은 Phase 2 **agent→hub 상태 push**인데, 그건 재시도+heartbeat로 충분하다(Kafka는 과잉).
- **멀티 노드풀 세분화**(ch7.2) — `nodeSelector`로 API/worker/ops 분리는 **GKE 노드풀 과금 패턴**이다.
  우리는 kind/k3s 로컬 $0 기판이라 노드풀 4개를 흉내내면 비용만 생긴다. 노드 리소스 경합 완화는 이미
  저사양 values(requests 5m)로 처리 중.
- **GKE 종속 시크릿**(ch6.2 Secret Manager CSI + Workload Identity) — 무키 구조는 훌륭하지만 GKE 전용.
  cloud-neutral DNA 유지하려면 **External Secrets Operator**가 우리 대응물(설계 v5 비교표에 이미 있음).
- **Secret 수동 복제**(ch7.4 `valkey-enterprise`) — 책 자신이 "실제 환경에선 ESO/CSI/테넌트별 인스턴스"라 경고.
- **Valkey 단일 인스턴스 SPOF**(ch6.1, ADR-008이 트레이드오프 인정) — 우리 상태 저장은 이미 JSONL/DynamoDB/
  Aurora(④ state store) 3단으로 정리됨. 캐시 레이어 추가 이유 없음.

## 확증된 것 (바꾸지 말라는 신호)

- **살아있는 문서 = 코드와 같은 저장소 + 갱신을 커맨드로 자동화**(ch9.3.1, `/update-docs`) → 우리 `/checkpoint`와 동형. D8 유지.
- **사람용 계획(한국어) ↔ AI용 증류(영어, 실행값)** 2층 분리(Appendix B.1.3) → 우리 `docs/plans/*`(사람) ↔
  `AGENT_BRIEF`(증류)와 동형. 단 **실행값 한 곳** 축은 약하다: 핀 버전·namespace·context·엔드포인트가
  `addons/values/*`·`variables.tf`·`Makefile`·`.env`에 흩어져 있다. 책의 `claude-context/01-environment-values.md`
  등가물(1페이지 실행값 표)을 만들 여지 있음 — 단 `ARCHITECTURE.md`(728줄)를 증류본으로 착각하지 말 것.
- **`--set` 금지, 모든 값은 values 파일 + `--version` 고정**(Appendix B.1.4) → 우리 애드온 5핀 계약과 동일 규율.
- **"한 번에 하나씩 + 매번 실제 상태로 검증"**(ch9.5.2) → 우리 gate(`make check`) + 라이브 증거 관례와 동일.

## 액션

- **자율 가능 코드**: ① AnalysisTemplate(prometheus provider 1단계) · ② OTel span + `tracing.tf` · ③ 런북 precheck/verify 스키마.
- **사용자 승인 필요**: ④ 권한 통제 재설계(오버나이트 루프 영향) · ⑤ Sync Wave(설계 문서 수정) · ⑥ NetworkPolicy/PSS(CNI 교체 가능성) · ⑦ TTL 스위퍼.
- **다음 세션 진입 시**: 이 노트는 `NEXT_PLAN.md` 백로그로 승격되기 전 상태다. Phase 0(멀티테넌트) 착수와
  경쟁시키지 말고, ①②③은 Phase 0과 독립이므로 **가벼운 증분으로 끼워 넣을 수 있다**.
