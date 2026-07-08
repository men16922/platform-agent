# ARCHITECTURE.md — platform-agent 아키텍처 상세

---

## 1. High-Level Architecture (전체 구조)

![High-Level Architecture](images/architecture-high-level.png)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         누가 파이프라인을 시작하는가?                         │
│                                                                             │
│  PATH A: 직접 호출                    PATH B: 이벤트 기반 자동 트리거        │
│  ┌───────────────────────┐           ┌────────────────────────────────┐     │
│  │ • 개발자 (터미널)      │           │ Slack / Jira / GitHub webhook  │     │
│  │ • AI 도구             │           │           ↓                    │     │
│  │   (Claude Code, Codex,│           │ 이벤트 수신 레이어 (환경별):   │     │
│  │    Kiro, AGY)         │           │  AWS: EventBridge → Lambda     │     │
│  │ • CI/CD              │           │  GCP: Pub/Sub → Cloud Func     │     │
│  │   (GitHub Actions,    │           │  Azure: Event Grid → Az Func   │     │
│  │    Jenkins 등)        │           │  On-Prem: Webhook (FastAPI)    │     │
│  └───────────┬───────────┘           └──────────────┬─────────────────┘     │
│              │                                      │                       │
│              └──────────────┬───────────────────────┘                       │
│                             ▼                                               │
│              ┌───────────────────────────────┐                              │
│              │      AI Orchestrator          │                              │
│              │    (배포 파이프라인 엔진)       │                              │
│              │                               │                              │
│              │  "서비스 X를 버전 Y로,        │                              │
│              │   환경 Z에, provider P로 배포" │                              │
│              │                               │                              │
│              │  → 7-step DAG 실행            │                              │
│              │  → provider에 맞는 AI Agent    │                              │
│              │    가 자율적으로 빌드/배포     │                              │
│              └──────────────┬────────────────┘                              │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │ Day 1        │   │ Day 2        │   │ Cross-cutting│
    │ AI 배포      │   │ 인시던트     │   │              │
    │              │   │ 자동 대응    │   │ Guardian     │
    │              │   │              │   │ Gateway      │
    │              │   │              │   │ Runbooks     │
    └──────────────┘   └──────────────┘   └──────────────┘
```

### AI Orchestrator란?

배포 파이프라인을 실행하는 **엔진**. 입력으로 "무엇을 어디에 배포할지"를 받으면, 7단계 DAG를 순서대로 실행한다.

- 특정 클라우드에 종속되지 않음 (순수 Python)
- 어디서 실행하든 동일하게 동작 (개발자 노트북, CI 서버, Lambda, Cloud Function)
- provider 값에 따라 적절한 AI Agent를 선택해서 배포 수행

### 핵심 설계 원칙

| 원칙 | 설명 |
|------|------|
| **파이프라인 엔진 = 클라우드 독립** | 어떤 환경에서든 실행 가능. 클라우드 SDK 의존 없음 |
| **호스팅 레이어 = 교체 가능** | AWS(EventBridge+Lambda)는 하나의 구현. GCP/Azure/On-Prem도 동일 패턴으로 확장 |
| **Agent-per-cloud** | 각 클라우드에 최적화된 LLM Agent가 자율적으로 tool calling |
| **Policy as Code** | Guardian Agent가 모든 배포에 대해 APPROVE/AUTO/REJECT 판정 |

### 진입 경로 비교

| 경로 | 트리거 주체 | 설명 |
|------|-----------|------|
| **PATH A: 직접 호출** | 개발자, AI 도구, CI/CD | 클라우드 무관. Orchestrator를 직접 호출 |
| **PATH B: 이벤트 기반** | Slack/Jira/GitHub webhook | 호스팅 환경에 따라 이벤트 수신 방식이 다름 |

**PATH B 호스팅별 구현 상태:**

| 호스팅 환경 | 이벤트 수신 | 오케스트레이션 | 상태 |
|------------|-----------|--------------|------|
| AWS | EventBridge → Lambda | Step Functions | ✅ 구현 |
| GCP | Pub/Sub → Cloud Functions | Cloud Workflows | 🔲 미구현 |
| Azure | Event Grid → Azure Functions | Durable Functions | 🔲 미구현 |
| On-Prem | Webhook (FastAPI) | 직접 호출 | 🔲 미구현 |

두 경로 모두 동일한 **AI Orchestrator**로 수렴한다.

---

## 2. AI Deployment Pipeline (Day 1 상세)

![Day 1: AI Deployment Pipeline](images/architecture-day1-pipeline.png)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Guardian Agent (Policy-as-Code)                       │
│                    ┌──────────────────────────────────┐                      │
│                    │  deploy-policy.yaml              │                      │
│                    │  • prod → APPROVE (사람 승인)    │                      │
│                    │  • staging → AUTO               │                      │
│                    │  • "delete" 포함 → REJECT       │                      │
│                    └──────────────┬───────────────────┘                      │
│                                   │                                          │
│                                   ▼                                          │
│  ┌──────┐  ┌──────┐  ┌───────┐  ┌───────┐  ┌──────┐  ┌────────┐  ┌──────┐│
│  │ Spec │→│ Plan │→│ Guard │→│ Build │→│ Push │→│ Deploy │→│Validate│→Report│
│  └──────┘  └──────┘  └───────┘  └───────┘  └──────┘  └────────┘  └──────┘│
│                          │                                                   │
│                    REJECT → 중단                                             │
│                    APPROVE → 사람 승인 대기                                  │
│                    AUTO → 자동 진행                                          │
└─────────────────────────────────────────────────────────────────────────────┘

                              │ provider 선택
            ┌─────────────────┼─────────────────┬────────────────┐
            ▼                 ▼                 ▼                ▼
  ┌──────────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────┐
  │ Strands Agent    │ │ ADK Agent     │ │ MS Agent      │ │ On-Prem Agent│
  │ (AWS)            │ │ (GCP)         │ │ (Azure)       │ │              │
  │                  │ │               │ │               │ │ LLM: Any     │
  │ LLM: Bedrock    │ │ LLM: Gemini   │ │ LLM: GPT-5.4 │ │ (Local LLM   │
  │      Claude     │ │   3.5 Flash   │ │ Azure OpenAI  │ │  or API Key) │
  │                  │ │               │ │               │ │              │
  │ Tools:           │ │ Tools:        │ │ Tools:        │ │ Tools:       │
  │  aws_build_image│ │ gcp_build_img │ │ azure_build   │ │ onprem_build │
  │  aws_push_image │ │ gcp_push_img  │ │ azure_push    │ │ onprem_push  │
  │  aws_deploy     │ │ gcp_deploy    │ │ azure_deploy  │ │ onprem_deploy│
  │  validate       │ │ validate      │ │ validate      │ │ validate     │
  │  rollback       │ │ rollback      │ │ rollback      │ │ rollback     │
  └────────┬─────────┘ └──────┬────────┘ └──────┬────────┘ └──────┬───────┘
           │                   │                  │                  │
           ▼                   ▼                  ▼                  ▼
  ┌──────────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────┐
  │ AWS              │ │ GCP           │ │ Azure         │ │ On-Prem      │
  │ EKS + ECR       │ │ GKE +         │ │ AKS + ACR     │ │ Kubernetes   │
  │ CodeBuild       │ │ Artifact Reg  │ │ ACR Tasks     │ │ + Private    │
  │                  │ │ Cloud Build   │ │               │ │   Registry   │
  │ (Cloud SDK)     │ │ (Cloud SDK)   │ │ (Cloud SDK)   │ │ (via MCP     │
  │                  │ │               │ │               │ │  Gateway)    │
  └──────────────────┘ └───────────────┘ └───────────────┘ └──────────────┘
```

### Agent별 역할

| Agent | 담당 | LLM | 인프라 접근 방식 |
|-------|------|-----|----------------|
| **Strands Agent** | AWS 전용 | Bedrock Claude | Cloud SDK (aws cli) |
| **ADK Agent** | GCP 전용 | Vertex AI Gemini 3.5 Flash | Cloud SDK (gcloud) |
| **MS Agent** | Azure 전용 | Azure OpenAI GPT-5.4 | Cloud SDK (az cli) |
| **On-Prem Agent** | On-Premise K8s | Local LLM or API Key (any) | MCP Gateway (kubectl/docker) |

- AWS/GCP/Azure: 각 cloud SDK를 직접 호출하여 빌드/푸시/배포
- On-Prem: **MCP Gateway를 통해서만** 클러스터에 접근 (kubectl + docker subprocess)

### Pipeline DAG 각 Step 설명

| Step | 역할 | 실패 시 |
|------|------|---------|
| **Spec** | ServiceSpec 파싱 (이름, 버전, 환경, provider, replicas) | 즉시 중단 |
| **Plan** | 배포 전략 수립 (rolling/canary/blue-green) | 즉시 중단 |
| **Guard** | Guardian Agent가 정책 평가 | REJECT → 중단, APPROVE → 대기 |
| **Build** | 컨테이너 이미지 빌드 | 중단 + 에러 리포트 |
| **Push** | 레지스트리에 이미지 push | 중단 + 에러 리포트 |
| **Deploy** | 클러스터에 배포 (kubectl apply / cloud SDK) | rollback 시도 |
| **Validate** | 헬스체크 + rollout status 확인 | rollback 시도 |
| **Report** | 결과 요약 → Slack 전송 | best-effort |

### On-Prem 제어 경로

On-Prem은 다른 클라우드와 제어 방식이 근본적으로 다르다:

```
AWS/GCP/Azure:  AI Agent → Cloud SDK 직접 호출 (aws/gcloud/az cli)
On-Prem:        On-Prem Agent → MCP Gateway → kubectl/docker subprocess → K8s 클러스터
```

On-Prem Agent는 **MCP Server가 유일한 실행 인터페이스**. kubeconfig가 가리키는 클러스터가 타겟이 된다.

| 환경 | K8s 클러스터 | Registry |
|------|-------------|----------|
| 로컬 테스트 | kind | localhost:5001 |
| 프로덕션 | 실제 on-prem K8s | private registry (Harbor 등) |

**On-Prem Agent의 LLM:**
- **Local LLM** (Ollama, vLLM 등) — 완전 폐쇄망, 데이터 외부 유출 없음
- **API Key 기반** (OpenAI, Anthropic, Google 등) — 네트워크 접근 가능 시 아무 LLM이나 사용
- 환경변수 `ONPREM_LLM_PROVIDER` + `ONPREM_LLM_MODEL`로 설정
- 핵심: On-Prem Agent는 특정 LLM에 종속되지 않음. tool calling만 지원하면 됨

현재 코드에서는 Strands Agent가 `provider="onprem"`으로 On-Prem을 겸하고 있으나,
아키텍처상으로는 독립 On-Prem Agent로 분리하는 것이 목표.

### CLI 사용법

```bash
# On-Prem 배포
python -m src.agents.ai.orchestrator \
  --service orders-api --version v1.4.2 --env staging --provider onprem

# AWS 배포
python -m src.agents.ai.orchestrator \
  --service orders-api --version v1.4.2 --env prod --provider aws

# GCP 배포
python -m src.agents.ai.orchestrator \
  --service orders-api --version v1.4.2 --env staging --provider gcp

# Azure 배포
python -m src.agents.ai.orchestrator \
  --service orders-api --version v1.4.2 --env staging --provider azure
```

---

## 3. Incident Response Pipeline (Day 2 상세)

![Day 2: Incident Response Pipeline](images/architecture-day2-incident.png)

### 추상 파이프라인 (클라우드 독립)

Day 2 파이프라인의 **논리 구조**는 모든 환경에서 동일:

```
Signal (알람/메트릭 이상) → Event Bus → Orchestrator → 4-step Pipeline → Report
```

```
┌─────────────────────────────────────────────────────────────────┐
│  1. DETECTOR — 신호 수집 + NormalizedIncident 생성              │
│  2. ANALYZER — LLM root cause 추론 + severity 판정             │
│  3. DECISION — Runbook 매칭 + remediation mode 결정             │
│  4. EXECUTOR — 실행 or 승인 대기 or 기록만                     │
└─────────────────────────────────────────────────────────────────┘
```

핵심: **4단계 로직은 순수 Python**. 클라우드별로 다른 것은 "어떤 인프라로 이 로직을 호스팅하느냐".

### Provider별 구현 매핑

| 컴포넌트 | AWS (✅ 구현) | GCP (🔲) | Azure (🔲) | On-Prem (🔲) |
|---------|-------------|---------|-----------|-------------|
| **Signal** | CloudWatch Alarm | Cloud Monitoring Alert | Azure Monitor Alert | Prometheus / Alertmanager |
| **Event Bus** | EventBridge | Pub/Sub | Event Grid | Webhook (FastAPI) |
| **Orchestration** | Step Functions | Cloud Workflows | Durable Functions | Temporal / Prefect |
| **LLM (Analyzer)** | Bedrock Claude | Vertex AI Gemini | Azure OpenAI GPT | Local LLM or API Key |
| **Executor** | SSM Automation | gcloud / kubectl | az cli / kubectl | kubectl (via MCP) |
| **Approval Gate** | SQS + Lambda URL + Slack | Cloud Tasks + Cloud Run + Slack | Service Bus + Az Func + Slack | Redis + FastAPI + Slack |
| **State Store** | DynamoDB | Firestore | Cosmos DB | PostgreSQL / Redis |
| **Notification** | Slack Webhook | Slack Webhook | Slack Webhook | Slack Webhook |

### AWS 구현 상세 (현재 동작)

```
CloudWatch Alarm (ALARM)
    │
    ▼
EventBridge Rule → Step Functions State Machine
    │
    ├─→ 1. Detector Lambda (CW Logs Insights + X-Ray + metrics)
    ├─→ 2. Analyzer Lambda (Bedrock Claude → root cause + severity)
    ├─→ 3. Decision Lambda (DynamoDB runbook lookup → mode 결정)
    │       │
    │       ├─ P1 AUTO → 4. Executor (SSM 즉시 실행)
    │       ├─ P2 APPROVE → Approval Bridge (아래 상세)
    │       └─ P3 MANUAL → Slack 알림만
    │
    └─→ Report: DynamoDB 이력 + Slack 리포트
```

### Approval Flow (P2 — provider별)

**AWS 구현 (✅):**
```
Decision(P2) → Step Functions WaitForTaskToken
  → SQS → Approval Bridge Lambda
    → DynamoDB pending + Slack 버튼 전송
      → 사용자 클릭 → Lambda Function URL
        → HMAC 검증 → DynamoDB claim → SendTaskSuccess/Failure
```

**GCP 구현 (🔲 계획):**
```
Decision(P2) → Cloud Workflows callback
  → Cloud Tasks → Approval Cloud Function
    → Firestore pending + Slack 버튼 전송
      → 사용자 클릭 → Cloud Run endpoint
        → Firestore claim → Workflows resume
```

**Azure 구현 (🔲 계획):**
```
Decision(P2) → Durable Functions external event wait
  → Service Bus → Approval Az Function
    → Cosmos DB pending + Slack 버튼 전송
      → 사용자 클릭 → Az Function HTTP trigger
        → Cosmos DB claim → Durable Functions raise event
```

**On-Prem 구현 (🔲 계획):**
```
Decision(P2) → Temporal workflow signal wait
  → Redis queue → Approval FastAPI endpoint
    → PostgreSQL pending + Slack 버튼 전송
      → 사용자 클릭 → FastAPI webhook
        → PostgreSQL claim → Temporal signal
```

### Severity → Mode 매핑 (모든 provider 공통)

| Severity | Mode | 동작 | RTO 목표 |
|----------|------|------|----------|
| **P1** | AUTO | 즉시 실행, 완료까지 폴링 | < 5분 |
| **P2** | APPROVE | 승인 대기 (1시간 timeout) | < 15분 |
| **P3** | MANUAL | 알림만, 실행 없음 | 해당 없음 |

**Safety Override:** action에 `Delete`, `Drop`, `Terminate` 포함 시 severity 무관 강제 APPROVE.
이 규칙은 Guardian Agent 정책에 포함되어 있으며, 모든 provider에서 동일하게 적용.

### Capability Runbook (Cloud-Neutral)

런북은 **capability(의도)**를 선언하고, 실행 시점에 provider adapter가 구체 action으로 해석:

```python
# 선언 (cloud-neutral)
RunbookStep(name="restart_pod", capability="restart_workload", on_failure="continue")
RunbookStep(name="scale_nodes", capability="scale_out", condition={"previous_step_failed": True})

# 실행 시 provider별 해석:
#   AWS:     restart_workload → AWS-RestartEKSPod (SSM Automation)
#   GCP:     restart_workload → kubectl rollout restart (Cloud Shell / MCP)
#   Azure:   restart_workload → az aks command invoke --command "kubectl rollout restart"
#   On-Prem: restart_workload → kubectl delete pod (via MCP Gateway)
```

### Built-in Runbooks

| Alarm 패턴 | Runbook ID | Capability Actions |
|------------|-----------|-------------------|
| EKS/GKE/AKS pod OOM | `pod-oom` | restart_workload → scale_out |
| Lambda/Cloud Func throttle | `function-throttle` | increase_concurrency |
| RDS/Cloud SQL/Az SQL CPU | `db-cpu-high` | scale_up → add_replica |
| Kafka consumer lag | `kafka-lag-spike` | scale_out_consumer |
| 기타 | `generic-recovery` | notify_only |

---

## 공유 컴포넌트 (Cross-cutting)

### Guardian Agent

**순수 Python — 클라우드 독립.** YAML 정책 파일을 읽어서 평가할 뿐, 특정 인프라에 종속 없음.

```yaml
# src/agents/ai/policies/deploy-policy.yaml
rules:
  - condition: { environment: "prod" }
    decision: APPROVE        # 사람 승인 필수
  - condition: { environment: "staging" }
    decision: AUTO           # 자동 배포
  - condition: { action_contains: "delete" }
    decision: REJECT         # 거부
```

**Provider별 Guardian 호스팅:**

| 환경 | 호스팅 방식 | 호출 | 상태 |
|------|-----------|------|------|
| AWS | Lambda 내 Python | Step Functions에서 직접 호출 | ✅ 구현 |
| GCP | Cloud Function 내 Python | Workflows에서 HTTP 호출 | 🔲 |
| Azure | Az Function 내 Python | Durable Functions activity | 🔲 |
| On-Prem | FastAPI endpoint 또는 직접 import | Orchestrator에서 직접 호출 | 🔲 |

핵심: Guardian 로직은 동일 코드. 차이는 "어디서 실행되느냐"뿐.

### Gateway

| 컴포넌트 | 역할 | 프로토콜 |
|---------|------|---------|
| **MCP Server** | kubectl 5종 + docker 4종 = 9개 tool 노출 | MCP (Model Context Protocol) |
| **A2A Server** | 외부 agent와 통신, task lifecycle 관리 | A2A v1.0 (HTTP+JSON) |
| **Bridge** | MCP ↔ A2A 양방향 변환 | 내부 |

```
외부 Agent → A2A Server (/.well-known/agent-card.json 디스커버리)
           → POST /message:send
           → Bridge → MCP Server → kubectl/docker 실행
           → 결과를 A2A task artifact로 반환
```

Gateway는 **On-Prem Agent의 유일한 실행 인터페이스**이자,
다른 provider에서도 kubectl 기반 작업이 필요할 때 사용 가능.

### IAM / RBAC (Provider별 접근 제어)

| Provider | 메커니즘 | Agent 격리 |
|----------|---------|-----------|
| AWS | IAM Role per Lambda | Detector/Analyzer/Decision/Executor 각각 별도 역할 |
| GCP | Service Account per Function | Workload Identity + 최소 권한 |
| Azure | Managed Identity per Function | RBAC role assignment |
| On-Prem | K8s ServiceAccount + RBAC | kubeconfig context 분리 |

**AWS IAM 상세 (현재 구현):**

| Agent | 허용 권한 |
|-------|----------|
| Detector | `logs:StartQuery`, `xray:GetTraceSummaries`, `cloudwatch:GetMetricStatistics` |
| Analyzer | `bedrock:InvokeModel` (모델 ARN 한정), `dynamodb:GetItem` |
| Decision | `dynamodb:GetItem` (runbook table), `sns:Publish` |
| Executor | `ssm:StartAutomationExecution` (문서 prefix 한정), `dynamodb:PutItem` |

---

## 참고

- 전체 동작 가이드: [`GUIDE.md`](../GUIDE.md)
- Slack App 설정: [`docs/SLACK_APP_SETUP.md`](SLACK_APP_SETUP.md)
- AI Agent 실호출 가이드: [`docs/AI_AGENT_LIVE_CALL_GUIDE.md`](AI_AGENT_LIVE_CALL_GUIDE.md)
- 구현 상태: [`docs/STATUS.md`](STATUS.md)
