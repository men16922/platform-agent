# GUIDE.md — platform-agent 동작 가이드

> 시스템이 어떻게 동작하는지 흐름 중심으로 설명.

---

## 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Entry Points                                 │
├───────────┬───────────┬──────────────┬──────────────────────────────┤
│   Slack   │   Jira    │   GitHub     │   CloudWatch Alarm           │
└─────┬─────┴─────┬─────┴──────┬───────┴──────────────┬───────────────┘
      │           │            │                      │
      ▼           ▼            ▼                      ▼
┌─────────────────────────┐            ┌──────────────────────────────┐
│  Ingress Lambda         │            │  EventBridge Rule            │
│  (HTTP → EventBridge)   │            │  (Alarm ALARM state)         │
└────────────┬────────────┘            └──────────────┬───────────────┘
             │                                        │
             ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     EventBridge (default bus)                         │
└──────────┬──────────────────────┬───────────────────────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────┐    ┌─────────────────────────────────────────────┐
│   Router Lambda  │    │  Operations Step Functions Pipeline          │
│   (Day 1/1.5)   │    │  (Day 2 — Incident Response)                │
└────┬────────┬────┘    └─────────────────────────────────────────────┘
     │        │
     ▼        ▼
Provisioning  Deployment
Pipeline      Pipeline
```

---

## Day 1 — Provisioning (서비스 생성)

```
요청 → Ingress → EventBridge → Router → Provisioning Step Functions
```

1. **Ingress**: HTTP 요청을 받아 EventBridge 이벤트로 변환
2. **Router**: `detail-type: "Provisioning Request"` → Provisioning 파이프라인으로 라우팅
3. **Provisioning Lambda**:
   - CDK 코드 생성 (TypeScript)
   - IAM 최소 권한 설계
   - 비용 추정 (월간 예상 USD)
   - 예상 비용 > $200 → APPROVE 승인 대기
4. **Artifact Writer**: 생성된 CDK 코드를 S3에 저장

```bash
# 로컬 테스트
python -m src.agents.provisioning examples/orders-api.yaml
```

---

## Day 1.5 — Deployment Validation (배포 검증)

```
요청 → Ingress → EventBridge → Router → Deployment Step Functions
```

1. **Deployment Lambda**: smoke test + canary 분석
2. 이상 감지 시 → **Rollback Executor** (SSM Automation)
3. Slack 리포트 전송

---

## Day 2 — Incident Response (인시던트 대응)

```
CloudWatch Alarm → EventBridge → Operations Step Functions
```

**4단계 파이프라인:**

### Step 1: Detector
- CloudWatch Logs Insights 쿼리
- X-Ray trace 수집
- 관련 메트릭 수집
- `NormalizedIncident` 생성 (cloud-neutral envelope)

### Step 2: Analyzer
- Bedrock LLM에 로그/메트릭/트레이스 전달
- Root cause 추론 + Severity 판정 (P1/P2/P3)
- Confidence score

### Step 3: Decision
- Runbook 매칭 (DynamoDB lookup → catalog heuristic → builtin fallback)
- Capability → Action 해석 (provider별 ExecutionAdapter)
- Remediation mode 결정:

| Severity | Mode | 동작 |
|----------|------|------|
| P1 | AUTO | 즉시 실행 |
| P2 | APPROVE | Slack 버튼 승인 대기 (1h timeout) |
| P3 | MANUAL | 기록만, 실행 안 함 |

### Step 4: Executor
- SSM Automation 실행 (또는 kubectl, gcloud 등)
- DynamoDB에 인시던트 이력 기록
- Slack 완료 리포트

### Approval Bridge (P2)
```
Decision(P2) → SQS → Approval Bridge Lambda
  → Slack 메시지 + Approve/Reject 버튼 전송
  → Step Functions WaitForTaskToken (일시정지)

사용자 버튼 클릭 → Lambda Function URL → DynamoDB claim
  → SendTaskSuccess/Failure → Step Functions 재개 → Executor
```

---

## Multi-Cloud AI Agent 배포

```bash
python -m src.agents.ai.orchestrator \
  --service orders-api --version v1.4.2 \
  --env staging --provider local
```

**E2E Pipeline DAG (7 steps):**

```
Spec → Plan → Guard → Build → Push → Deploy → Validate → Report
```

| Step | 설명 |
|------|------|
| Plan | ServiceSpec → 배포 계획 수립 |
| Guard | Guardian Agent 정책 평가 (APPROVE/AUTO/REJECT) |
| Build | 컨테이너 이미지 빌드 |
| Push | 레지스트리에 push |
| Deploy | 클러스터에 배포 (kubectl apply) |
| Validate | 헬스체크 + rollout status 확인 |
| Report | 결과 요약 |

**Provider별 AI Agent:**

| Provider | Agent | LLM | Tool 호출 |
|----------|-------|-----|-----------|
| AWS/Local | Strands | Bedrock Claude | build→push→deploy→validate 자율 호출 |
| GCP | ADK | Vertex AI Gemini 3.5 Flash | gcp_build→gcp_push→gcp_deploy→validate |
| Azure | MS Agent Framework | Azure OpenAI GPT-5.4 | azure_build→azure_push→azure_deploy→validate |

**Guardian Agent (Policy-as-Code):**
```yaml
# src/agents/ai/policies/deploy-policy.yaml
rules:
  - env: prod → APPROVE (사람 승인 필수)
  - env: staging → AUTO (자동 배포)
  - action contains "delete" → REJECT
```

---

## Capability-based Runbook (Cloud-Neutral)

런북은 **capabilities (의도)**를 선언하고, 실행 시점에 provider adapter가 구체 action으로 변환:

```python
# 런북 선언 (cloud-neutral)
{
    "runbook_id": "eks-pod-oom",
    "steps": [
        {"name": "restart_pod", "capability": "restart_workload", "on_failure": "continue"},
        {"name": "scale_nodes", "capability": "scale_out", "condition": {"previous_step_failed": True}}
    ]
}

# 실행 시 (AWS)
restart_workload → AWS-RestartEKSPod (SSM Automation)
scale_out        → AWS-ScaleOutEKSNodeGroup

# 실행 시 (GCP)
restart_workload → kubectl rollout restart
scale_out        → gcloud container clusters resize
```

---

## 로컬 실행

```bash
# 1. On-prem 클러스터
make local-cluster          # kind 3노드 + registry + ingress
make local-cluster-status   # 상태 확인
make local-cluster-down     # 정리

# 2. E2E 파이프라인 (로컬)
python -m src.agents.ai.orchestrator \
  --service orders-api --version v1.4.2 --env dev --provider local

# 3. 테스트
make check                  # 352 tests

# 4. CDK 배포 (AWS)
cd src/stacks && npx cdk deploy

# 5. 인시던트 시뮬레이션
aws cloudwatch set-alarm-state \
  --alarm-name "your-alarm" --state-value ALARM --state-reason "Test"
```

---

## 환경 설정

```bash
cp .env.example .env
# 필수:
#   AWS_REGION, AWS_ACCOUNT_ID
#   GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global
#   GOOGLE_GENAI_USE_VERTEXAI=TRUE
# 선택:
#   SLACK_WEBHOOK_URL, SLACK_SIGNING_SECRET (Slack 버튼용)
#   AZURE_AI_PROJECT_ENDPOINT (Azure AI Agent용)
```

자세한 설정: [`docs/AI_AGENT_LIVE_CALL_GUIDE.md`](docs/AI_AGENT_LIVE_CALL_GUIDE.md) | [`docs/SLACK_APP_SETUP.md`](docs/SLACK_APP_SETUP.md)

---

## 보안

- 각 Agent별 독립 IAM Role (공유 실행 역할 없음)
- `Delete`/`Drop`/`Terminate` 포함 액션 → severity 무관 강제 APPROVE
- Slack signature HMAC-SHA256 검증 (5분 이상 된 요청 자동 거부)
- Lambda Function URL AuthType=NONE이지만 Slack signing secret로 보호
- DynamoDB 승인 요청 TTL 24시간 후 자동 만료
