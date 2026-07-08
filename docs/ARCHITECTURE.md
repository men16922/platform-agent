# ARCHITECTURE.md — platform-agent 아키텍처 상세

---

## 1. High-Level Architecture (전체 구조)

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
  │                  │ │               │ │               │ │ LLM: TBD     │
  │ LLM: Bedrock    │ │ LLM: Gemini   │ │ LLM: GPT-5.4 │ │ (Bedrock or  │
  │      Claude     │ │   3.5 Flash   │ │ Azure OpenAI  │ │  self-hosted) │
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
| **On-Prem Agent** | On-Premise K8s | TBD (Bedrock or self-hosted) | MCP Gateway (kubectl/docker) |

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

**On-Prem Agent의 LLM 선택은 미확정 (TBD):**
- Bedrock Claude (AWS 네트워크 접근 가능 시)
- Self-hosted LLM (완전 폐쇄망)
- 또는 다른 상용 LLM

현재 코드에서는 Strands Agent가 `provider=local`로 On-Prem을 겸하고 있으나,
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

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TRIGGER                                                                      │
│                                                                              │
│  CloudWatch Alarm (state → ALARM)                                           │
│       │                                                                      │
│       ▼                                                                      │
│  EventBridge Rule (source: aws.cloudwatch)                                  │
│       │                                                                      │
│       ▼                                                                      │
│  AWS Step Functions (Incident Response Workflow)                             │
└───────┼─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PIPELINE (Step Functions State Machine)                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 1. DETECTOR                                                          │    │
│  │    • CloudWatch Logs Insights 쿼리 (최근 5분)                        │    │
│  │    • X-Ray trace 수집                                                │    │
│  │    • 관련 메트릭 수집 (CPU, Memory, Error Rate)                      │    │
│  │    • Multi-provider 감지 (aws/gcp/azure/onprem 자동 판별)           │    │
│  │    Output: DetectorOutput (alarm + logs + traces + NormalizedIncident)│    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                  ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 2. ANALYZER                                                          │    │
│  │    • Bedrock Claude에 컨텍스트 전달 (로그 + 메트릭 + 트레이스)       │    │
│  │    • LLM이 root cause 추론                                           │    │
│  │    • Severity 판정: P1 / P2 / P3                                     │    │
│  │    • Confidence score (0.0 ~ 1.0)                                    │    │
│  │    • DynamoDB에서 유사 과거 인시던트 조회                             │    │
│  │    Output: AnalyzerOutput (root_cause + severity + confidence)        │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                  ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 3. DECISION                                                          │    │
│  │    • Runbook 매칭 (3-tier fallback):                                 │    │
│  │      ① DynamoDB lookup (커스텀 런북)                                  │    │
│  │      ② Catalog heuristic (alarm 이름 기반 매칭)                      │    │
│  │      ③ Builtin fallback (generic-recovery)                           │    │
│  │    • Capability → Action 해석 (ExecutionAdapter)                     │    │
│  │    • Remediation mode 결정 (severity 기반)                           │    │
│  │    • 안전장치: Delete/Drop/Terminate → 강제 APPROVE                  │    │
│  │    Output: DecisionOutput (runbook + mode + actions)                  │    │
│  └──────────────┬─────────────────────────────┬────────────────────────┘    │
│                  │                             │                              │
│            ┌─────┴─────┐              ┌───────┴───────┐                      │
│            │ AUTO / APPROVE           │ MANUAL        │                      │
│            │ (실행)     │              │ (기록만)      │                      │
│            └─────┬─────┘              └───────┬───────┘                      │
│                  ▼                             ▼                              │
│  ┌─────────────────────────────────┐   Slack 알림만                         │
│  │ 4. EXECUTOR                     │                                        │
│  │    • SSM Automation 실행        │                                        │
│  │    • 실행 완료 대기 (폴링)      │                                        │
│  │    • DynamoDB 이력 기록         │                                        │
│  │    • Slack 인시던트 리포트 전송 │                                        │
│  │    Output: ExecutorOutput       │                                        │
│  └─────────────────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Approval Flow (P2 상세)

```
Decision (P2 판정)
    │
    ▼
Step Functions: WaitForTaskToken (일시정지, token 발급)
    │
    ▼
SQS Queue (token + incident context 전달)
    │
    ▼
Approval Bridge Lambda (SQS trigger)
    │
    ├─→ DynamoDB에 pending approval 저장 (TTL 24h)
    │
    └─→ Slack 메시지 전송 (Approve / Reject 버튼)
              │
              ▼
        사용자가 버튼 클릭
              │
              ▼
        Slack → Lambda Function URL (HTTP POST)
              │
              ▼
        Approval Bridge Lambda (HTTP trigger)
              │
              ├─→ Slack signing secret HMAC 검증
              ├─→ DynamoDB conditional update (idempotent claim)
              │
              └─→ Approve: SendTaskSuccess → Step Functions 재개 → Executor
                  Reject:  SendTaskFailure → Step Functions 종료
```

### Severity → Mode 매핑

| Severity | Mode | 동작 | RTO 목표 |
|----------|------|------|----------|
| **P1** | AUTO | SSM 즉시 실행, 완료까지 폴링 | < 5분 |
| **P2** | APPROVE | Slack 승인 대기 (1시간 timeout) | < 15분 |
| **P3** | MANUAL | Slack 알림만, 실행 없음 | 해당 없음 |

**Safety Override:** action에 `Delete`, `Drop`, `Terminate` 포함 시 severity 무관 강제 APPROVE.

### Built-in Runbooks

| Alarm 패턴 | Runbook ID | Auto Actions |
|------------|-----------|--------------|
| EKS pod OOM / restart loop | `eks-pod-oom` | Pod 재시작 → 노드 스케일아웃 |
| Lambda throttling | `lambda-throttle` | Reserved concurrency 증가 |
| RDS CPU high | `rds-cpu-high` | 인스턴스 스케일업 → Read replica 추가 |
| Kafka consumer lag | `kafka-lag-spike` | Consumer group 스케일아웃 |
| 기타 | `generic-recovery` | Slack 알림만 |

### Capability Runbook (Cloud-Neutral)

```python
# 선언 (cloud-neutral)
RunbookStep(name="restart_pod", capability="restart_workload", on_failure="continue")
RunbookStep(name="scale_nodes", capability="scale_out", condition={"previous_step_failed": True})

# 실행 시 provider별 해석:
#   AWS:     restart_workload → AWS-RestartEKSPod (SSM)
#   GCP:     restart_workload → kubectl rollout restart (via MCP)
#   Azure:   restart_workload → az aks command invoke
#   On-Prem: restart_workload → kubectl delete pod (via MCP)
```

---

## 공유 컴포넌트 (Cross-cutting)

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

### Guardian Agent

모든 배포 요청에 대해 정책 평가:

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

### IAM (Agent별 최소 권한)

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
