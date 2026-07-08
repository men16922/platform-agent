# AI Agent LLM 실호출 검증 가이드

> ADK (Vertex AI Gemini) / MS Agent Framework (Azure OpenAI GPT-4o) / Strands (Bedrock Claude) 실호출 검증 절차.

---

## 사전 조건

| Agent | LLM | 인증 방식 |
|-------|-----|-----------|
| Strands Deployer | Bedrock Claude Haiku | AWS 자격증명 (`aws configure`) |
| ADK Deployer | Vertex AI Gemini 2.0 Flash | GCP 자격증명 (`gcloud auth application-default login`) |
| MSFT Deployer | Azure OpenAI GPT-4o | Azure 자격증명 (`az login`) 또는 API Key |

---

## 1. Strands Agent (AWS/Local) — 이미 검증 완료 ✅

```bash
# Bedrock Claude Haiku 실호출 (이미 검증됨)
python -m src.agents.ai.orchestrator \
  --service orders-api --version v1.4.2 \
  --env dev --provider local
```

결과: 자율 4-tool 호출 → 실배포 성공 (docs/test/ 결과 참조)

---

## 2. ADK Agent (GCP — Vertex AI Gemini)

### 2-1. GCP 인증 설정

```bash
# Application Default Credentials 설정
gcloud auth application-default login

# 프로젝트 + 리전 설정
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=asia-northeast3
```

> ADK는 `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION` 환경변수가 있으면
> 자동으로 Vertex AI 백엔드를 사용합니다. API Key 발급 불필요.

### 2-2. Vertex AI API 활성화

```bash
gcloud services enable aiplatform.googleapis.com --project=$GOOGLE_CLOUD_PROJECT
```

### 2-3. 의존성 확인

```bash
pip install google-adk>=1.0
```

> pyproject.toml에 `google-adk` 이미 포함됨.

### 2-4. 실호출 검증 (Python REPL)

```python
import os
os.environ["GOOGLE_CLOUD_PROJECT"] = "your-project-id"
os.environ["GOOGLE_CLOUD_LOCATION"] = "asia-northeast3"

from src.agents.ai.adk_deployer import create_adk_deployer_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

agent = create_adk_deployer_agent(model="gemini-2.0-flash")

session_service = InMemorySessionService()
session = session_service.create_session(app_name="test", user_id="u1")

runner = Runner(agent=agent, app_name="test", session_service=session_service)

content = types.Content(
    role="user",
    parts=[types.Part.from_text("Deploy orders-api v1.4.2 to GKE with 2 replicas")]
)

events = list(runner.run(user_id="u1", session_id=session.id, new_message=content))
for event in events:
    print(event)
```

### 2-5. ADK CLI (권장)

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=asia-northeast3
cd src/agents/ai
adk run adk_deployer
# 또는 웹 UI:
adk web
```

### 2-6. 기대 결과

- Gemini가 `gcp_build_image` → `gcp_push_image` → `gcp_deploy_to_cluster` → `gcp_validate_deployment` 순서로 tool 호출
- GCP 인프라(GKE 클러스터 등) 없으면 tool 실행 시 오류 발생하지만, **LLM이 tool을 선택하고 올바른 인자를 생성**하는 것이 검증 대상

---

## 3. MS Agent Framework (Azure — GPT-4o)

### 3-1. Azure OpenAI 리소스 생성 (az cli)

```bash
# 리소스 그룹
az group create --name platform-agent-rg --location koreacentral

# Azure OpenAI 리소스 생성
az cognitiveservices account create \
  --name platform-agent-aoai \
  --resource-group platform-agent-rg \
  --kind OpenAI \
  --sku S0 \
  --location koreacentral

# 모델 배포 (gpt-4o)
az cognitiveservices account deployment create \
  --name platform-agent-aoai \
  --resource-group platform-agent-rg \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-08-06" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

### 3-2. 엔드포인트 + 키 조회

```bash
# 엔드포인트
az cognitiveservices account show \
  --name platform-agent-aoai \
  --resource-group platform-agent-rg \
  --query properties.endpoint -o tsv

# API Key
az cognitiveservices account keys list \
  --name platform-agent-aoai \
  --resource-group platform-agent-rg \
  --query key1 -o tsv
```

### 3-3. 인증 방식 선택

**방법 A: AzureCliCredential (권장 — 키 불필요)**

```bash
az login
export AZURE_AI_PROJECT_ENDPOINT=https://platform-agent-aoai.openai.azure.com/
export AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-4o
```

코드에서 `AzureCliCredential()`이 `az login` 토큰을 자동으로 사용합니다.

**방법 B: API Key 방식**

```bash
export AZURE_OPENAI_ENDPOINT=https://platform-agent-aoai.openai.azure.com/
export AZURE_OPENAI_API_KEY=$(az cognitiveservices account keys list \
  --name platform-agent-aoai \
  --resource-group platform-agent-rg \
  --query key1 -o tsv)
export AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-4o
```

### 3-4. 의존성 확인

```bash
pip install "platform-agent[azure]"
# 또는 직접:
pip install agent-framework azure-identity
```

### 3-5. 실호출 검증 (Python REPL)

```python
import os
os.environ["AZURE_AI_PROJECT_ENDPOINT"] = "https://platform-agent-aoai.openai.azure.com/"
os.environ["AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"] = "gpt-4o"

from src.agents.ai.msft_deployer import create_msft_deployer_agent
import asyncio

agent = create_msft_deployer_agent()
result = asyncio.run(agent.run("Deploy orders-api v1.4.2 to AKS with 2 replicas"))
print(result)
```

### 3-6. 기대 결과

- GPT-4o가 `azure_build_image` → `azure_push_image` → `azure_deploy_to_cluster` → `azure_validate_deployment` 순서로 tool 호출
- AKS 클러스터 없으면 tool 실행 시 오류 발생하지만, **LLM이 tool을 올바르게 선택**하는 것이 검증 대상

### 3-7. 리소스 정리

```bash
az group delete --name platform-agent-rg --yes --no-wait
```

---

## 환경변수 요약 (.env)

```bash
# AWS (Strands — already working)
AWS_REGION=ap-northeast-2
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5

# GCP (ADK — Vertex AI, API Key 불필요)
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=asia-northeast3
GCP_PROJECT=your-gcp-project
GCP_REGION=asia-northeast3

# Azure (MS Agent Framework — AzureCliCredential 또는 API Key)
AZURE_AI_PROJECT_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-4o
# API Key 방식 시:
# AZURE_OPENAI_API_KEY=
# AZURE_OPENAI_ENDPOINT=
AZURE_REGION=koreacentral
AZURE_RESOURCE_GROUP=platform-agent-rg
```

---

## 비용 참고

| Agent | 모델 | 예상 비용 (1회 호출) |
|-------|------|---------------------|
| Strands | Claude Haiku | ~$0.001 |
| ADK | Gemini 2.0 Flash (Vertex) | ~$0.0003 |
| MSFT | GPT-4o | ~$0.003 |
| MSFT | GPT-4o-mini | ~$0.0003 |

> 한 번의 E2E 파이프라인 실행에 4~6 tool call이 발생합니다. 전체 비용 < $0.02.

---

## 검증 체크리스트

- [ ] `gcloud auth application-default login` + `GOOGLE_CLOUD_PROJECT` 설정
- [ ] ADK Agent 실행 → Gemini가 tool 호출 순서를 올바르게 계획하는지 확인
- [ ] Azure OpenAI 리소스 생성 (`az cognitiveservices account create`)
- [ ] `az login` + `AZURE_AI_PROJECT_ENDPOINT` 설정
- [ ] MSFT Agent 실행 → GPT-4o가 tool 호출 순서를 올바르게 계획하는지 확인
- [ ] (Optional) GCP/Azure 인프라 구성 → 실 배포까지 E2E 확인
