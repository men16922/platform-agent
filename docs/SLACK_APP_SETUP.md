# Slack App Setup Guide — Interactive Approval Buttons

> platform-agent의 APPROVE / REJECT 버튼을 Slack에서 실제로 동작시키기 위한 설정 가이드.

---

## 아키텍처 개요

```
Step Functions (waitForTaskToken)
    → SQS (incident-approval)
    → Approval Bridge Lambda
        → Slack Webhook: 메시지 + Approve/Reject 버튼 전송
        
사용자가 버튼 클릭 →
    Slack → Lambda Function URL (Interactivity Request URL)
    → Approval Bridge Lambda
        → DynamoDB claim
        → Step Functions SendTaskSuccess / SendTaskFailure
```

---

## Prerequisites

- AWS CDK 배포 완료 (`npx cdk deploy`)
- CloudFormation Output에서 `ApprovalBridgeFunctionUrl` 확인

---

## 1. Slack App 생성

1. [api.slack.com/apps](https://api.slack.com/apps) 접속
2. **Create New App** → **From scratch**
3. App Name: `platform-agent` (또는 원하는 이름)
4. Workspace: 연결할 Slack workspace 선택

## 2. Incoming Webhook 설정

1. 좌측 메뉴 → **Incoming Webhooks** → **Activate** ON
2. **Add New Webhook to Workspace** 클릭
3. 메시지를 받을 채널 선택 (예: `#platform-alerts`)
4. 생성된 Webhook URL 복사 → `.env`의 `SLACK_WEBHOOK_URL`에 설정

```bash
# .env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/TXXXXX/BXXXXX/your-webhook-token
```

## 3. Interactivity 설정 (버튼 콜백)

1. 좌측 메뉴 → **Interactivity & Shortcuts** → **ON**
2. **Request URL** 필드에 CDK Output의 `ApprovalBridgeFunctionUrl` 입력

```
https://<random-id>.lambda-url.<region>.on.aws/
```

> ⚠️ Lambda Function URL은 `authType: NONE`으로 배포됨.  
> Slack signature 검증으로 보안을 확보합니다.

3. **Save Changes** 클릭

## 4. Signing Secret 설정

1. 좌측 메뉴 → **Basic Information**
2. **App Credentials** 섹션에서 **Signing Secret** 복사
3. `.env`에 설정:

```bash
# .env
SLACK_SIGNING_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

4. CDK 재배포 시 환경변수 전달:

```bash
export SLACK_SIGNING_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
npx cdk deploy
```

## 5. OAuth Scopes (필요 시)

Incoming Webhook만 사용하는 경우 추가 scope 불필요.  
Bot으로 채널에 직접 메시지를 보내려면:

- **OAuth & Permissions** → Bot Token Scopes:
  - `incoming-webhook`
  - `chat:write` (optional: bot이 직접 post하는 경우)

---

## 환경변수 요약

| 변수 | 설명 | 필수 |
|------|------|------|
| `SLACK_WEBHOOK_URL` | Incoming Webhook URL | ✅ |
| `SLACK_SIGNING_SECRET` | Slack App Signing Secret | ✅ (버튼 사용 시) |
| `APPROVAL_REQUEST_TABLE` | DynamoDB 테이블명 (CDK가 자동 설정) | ✅ (CDK) |
| `APPROVAL_DEFAULT_DECISION` | 비-interactive 모드 기본값 (`approve`/`reject`) | ❌ (default: `reject`) |
| `APPROVAL_REQUEST_TTL_SEC` | 승인 요청 만료 시간 (초) | ❌ (default: `86400`) |

---

## 동작 확인

### 방법 1: 수동 SQS 메시지 전송

```bash
QUEUE_URL=$(aws cloudformation describe-stacks \
  --stack-name IncidentAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApprovalQueueUrl`].OutputValue' \
  --output text)

aws sqs send-message --queue-url "$QUEUE_URL" --message-body '{
  "taskToken": "test-token-manual-001",
  "runbook_id": "eks-pod-oom",
  "actions": ["AWS-RestartEKSPod"],
  "severity": "P2",
  "alarm_name": "test-alarm",
  "root_cause": "Manual test: OOMKilled in api pod"
}'
```

> ⚠️ 실제 `taskToken`이 아닌 더미 값이므로 버튼 클릭 시 Step Functions callback은 실패합니다.
> 메시지 수신 + 버튼 렌더링 확인 용도입니다.

### 방법 2: CloudWatch Alarm 트리거 (E2E)

```bash
aws cloudwatch set-alarm-state \
  --alarm-name "your-alarm-name" \
  --state-value ALARM \
  --state-reason "Manual test for Slack interactive approval"
```

이 경우 전체 파이프라인(Detector→Analyzer→Decision→Approval Bridge)이 동작하며,
P2 severity 결정 시 실제 `taskToken`이 포함된 승인 요청이 Slack에 전달됩니다.

---

## Troubleshooting

| 증상 | 원인 | 해결 |
|------|------|------|
| 메시지가 Slack에 안 옴 | `SLACK_WEBHOOK_URL` 미설정 | `.env` 확인 후 재배포 |
| 버튼이 없는 메시지만 옴 | `SLACK_SIGNING_SECRET` 또는 `APPROVAL_REQUEST_TABLE` 미설정 | 3개 환경변수 모두 설정 확인 |
| 버튼 클릭 시 "expired" | Request URL 미설정 | Slack App → Interactivity → Request URL 설정 |
| 401 Invalid signature | Signing Secret 불일치 | Slack App → Basic Info에서 재확인 |
| "dispatch_failed" | Lambda Function URL 응답 timeout | Lambda timeout 확인 (현재 1분) |

---

## Security Notes

- Lambda Function URL은 `AuthType: NONE`이지만, 모든 요청에 대해 **Slack Signing Secret** 기반 HMAC-SHA256 검증을 수행합니다.
- 5분 이상 된 요청(replay attack)은 자동 거부됩니다.
- DynamoDB에 저장된 pending request는 TTL(기본 24시간) 후 자동 만료됩니다.
- `Delete`/`Drop`/`Terminate` 포함 액션은 severity와 무관하게 강제 APPROVE 모드입니다.
