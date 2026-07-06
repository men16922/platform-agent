# CDK Deploy to AWS — 결과 보고서

**실행일시:** 2026-07-06 21:28~21:40 KST  
**실행자:** Kiro CLI (kiro_default agent)  
**Region:** us-east-1  
**Account:** 908601828278  

---

## 배포 결과

**✅ 성공 — 97 리소스 CREATE_COMPLETE**

```
IncidentAgentStack | 97/97 | 9:40:29 PM | CREATE_COMPLETE | AWS::CloudFormation::Stack
✅  IncidentAgentStack
```

---

## 생성된 리소스 요약

### Lambda Functions (9)

| Function | 역할 |
|----------|------|
| incident-agent-detector | CloudWatch Logs + X-Ray 분석 |
| incident-agent-analyzer | Bedrock LLM root-cause 분석 |
| incident-agent-decision | 런북 조회 + 판단 |
| incident-agent-executor | SSM Automation 실행 |
| incident-agent-approval-bridge | Slack 승인 → SQS → Step Functions callback |
| incident-agent-runbook-seed | Custom Resource: 런북 초기 데이터 시드 |
| incident-agent-provisioning | CDK 생성 + IAM 설계 |
| incident-agent-deployment | Smoke/canary/rollback |
| incident-agent-reporting | SLO/oncall/capacity 리포트 |
| platform-agent-router | EventBridge → pipeline 라우팅 |

### Step Functions (3)

| State Machine | 용도 |
|--------------|------|
| incident-agent-pipeline | Detect→Analyze→Decide→Execute |
| platform-agent-provisioning | Provisioning 파이프라인 |
| platform-agent-deployment | Deployment validation 파이프라인 |

### EventBridge Rules (5)

| Rule | 트리거 |
|------|--------|
| AlarmStateChangeRule | CloudWatch Alarm → 인시던트 파이프라인 |
| PlatformRequestRouterRule | 프로비저닝/디플로이 요청 라우팅 |
| DailySloSchedule | 매일 SLO 리포트 |
| WeeklyOncallSchedule | 주간 온콜 리포트 |
| MonthlyCapacitySchedule | 월간 용량 추천 |

### DynamoDB Tables (4)

| Table | 용도 |
|-------|------|
| incident-history | 인시던트 이력 |
| incident-runbooks | 런북 레지스트리 |
| incident-approval-requests | 승인 요청 |
| provisioning-plans | 프로비저닝 계획 |

### 기타

| 리소스 | 값 |
|--------|-----|
| SNS Topic | incident-agent-alerts |
| SQS Queue | incident-approval (+ DLQ) |
| Function URL (Approval) | https://5xajd7paallga2st5v3ixfybee0enfxn.lambda-url.us-east-1.on.aws/ |
| Function URL (Ingress) | https://qks3hzt2yffg4bua73dmtmvt240tvfrj.lambda-url.us-east-1.on.aws/ |
| S3 Bucket (Artifacts) | incidentagentstack-provisioningartifacts485e3dd9-x5rruokqhrpj |

---

## 해결한 이슈

### 1. CDK Bootstrap 누락

```
No bucket named 'cdk-hnb659fds-assets-908601828278-us-east-1'
```

**원인:** Stack이 us-east-1로 resolve되지만 bootstrap이 ap-northeast-2에만 있었음.  
**해결:** us-east-1 CDKToolkit 삭제 후 재생성.

### 2. Lambda structlog 모듈 누락

```
Unable to import module 'src.agents.operations.runbook_seed.handler': No module named 'structlog'
```

**원인:** `lambda.Code.fromAsset`이 프로젝트 코드만 패키징하고 pip 의존성 미포함.  
**해결:** CDK `bundling.local.tryBundle()` 추가 — `pip install -r requirements-lambda.txt -t ${outputDir}`.

### 3. DynamoDB Orphan 테이블

```
Resource of type 'AWS::DynamoDB::Table' with identifier 'incident-history' already exists.
```

**원인:** 이전 롤백 시 `RemovalPolicy.RETAIN`으로 테이블이 남아있음.  
**해결:** 4개 테이블 수동 삭제 후 재배포.

---

## CloudFormation Outputs

| OutputKey | Value |
|-----------|-------|
| ApprovalBridgeFunctionUrl | https://5xajd7paallga2st5v3ixfybee0enfxn.lambda-url.us-east-1.on.aws/ |
| IngressFunctionUrl | https://qks3hzt2yffg4bua73dmtmvt240tvfrj.lambda-url.us-east-1.on.aws/ |
| StateMachineArn | arn:aws:states:us-east-1:908601828278:stateMachine:incident-agent-pipeline |
| ProvisioningStateMachineArn | arn:aws:states:us-east-1:908601828278:stateMachine:platform-agent-provisioning |
| DeploymentStateMachineArn | arn:aws:states:us-east-1:908601828278:stateMachine:platform-agent-deployment |
| AlertTopicArn | arn:aws:sns:us-east-1:908601828278:incident-agent-alerts |
| ApprovalQueueUrl | https://sqs.us-east-1.amazonaws.com/908601828278/incident-approval |
| IncidentTableName | incident-history |
| ProvisioningArtifactBucketName | incidentagentstack-provisioningartifacts485e3dd9-x5rruokqhrpj |

---

## 비용 예상 (월간)

| 서비스 | 예상 비용 |
|--------|----------|
| Lambda (9 functions, low traffic) | ~$0 (free tier) |
| Step Functions (< 4000 state transitions) | ~$0 (free tier) |
| DynamoDB (on-demand, low traffic) | ~$1 |
| EventBridge | ~$0 |
| SQS/SNS | ~$0 |
| **합계** | **< $2/월** (idle 상태) |

---

## 다음 단계

1. Slack webhook URL 설정 → 실제 알림 테스트
2. `aws cloudwatch set-alarm-state` → 인시던트 파이프라인 E2E 검증
3. Ingress Function URL로 프로비저닝 요청 전송 테스트
