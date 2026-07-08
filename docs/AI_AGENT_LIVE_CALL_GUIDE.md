# AI Agent LLM 실호출 검증 가이드

> ADK (Gemini) / MS Agent Framework (GPT-4o) / Strands (Bedrock Claude) 실호출 검증 절차.

---

## 사전 조건

| Agent | LLM | API Key / 인증 |
|-------|-----|----------------|
| Strands Deployer | Bedrock Claude Haiku | AWS 자격증명 (`aws configure`) |
| ADK Deployer | Gemini 2.0 Flash | `GOOGLE_API_KEY` |
| MSFT Deployer | GPT-4o | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |

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

## 2. ADK Agent (GCP — Gemini)

### 2-1. API Key 발급

1. [Google AI Studio](https://aistudio.google.com/apikey) 접속
2. **Create API Key** 클릭 → 키 복사
3. `.env`에 설정:

```bash
GOOGLE_API_KEY=AIzaSy...your-key-here
```

### 2-2. 의존성 확인

```bash
pip install google-adk>=1.0
```

> pyproject.toml에 `google-adk` 이미 포함됨.

### 2-3. 실호출 검증 (Python REPL)

```python
import os
os.environ["GOOGLE_API_KEY"] = "AIzaSy..."

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

# 실행 (도구 호출은 subprocess/gcloud 필요 — API key만으로 LLM 추론 확인)
events = list(runner.run(user_id="u1", session_id=session.id, new_message=content))
for event in events:
    print(event)
```

### 2-4. ADK CLI (권장)

```bash
export GOOGLE_API_KEY=AIzaSy...
cd src/agents/ai
adk run adk_deployer
# 또는 웹 UI:
adk web
```

### 2-5. 기대 결과

- Gemini가 `gcp_build_image` → `gcp_push_image` → `gcp_deploy_to_cluster` → `gcp_validate_deployment` 순서로 tool 호출
- GCP 자격증명 없으면 tool 실행 시 오류 발생하지만, **LLM이 tool을 선택하고 올바른 인자를 생성**하는 것이 검증 대상

---

## 3. MS Agent Framework (Azure — GPT-4o)

### 3-1. Azure OpenAI 리소스 생성

1. [Azure Portal](https://portal.azure.com) → Azure OpenAI 리소스 생성
2. 모델 배포: `gpt-4o` (또는 `gpt-4o-mini`)
3. Endpoint + API Key 복사:

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=abc123...
AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-4o
```

### 3-2. 또는 Azure AI Foundry (Project Endpoint)

```bash
AZURE_AI_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/
AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-4o
# 인증: AzureCliCredential (az login)
```

### 3-3. 의존성 확인

```bash
pip install agent-framework azure-identity
```

### 3-4. 실호출 검증 (Python REPL)

```python
import os
os.environ["AZURE_AI_PROJECT_ENDPOINT"] = "https://your-project.services.ai.azure.com/api/"
os.environ["AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"] = "gpt-4o"

from src.agents.ai.msft_deployer import create_msft_deployer_agent
import asyncio

agent = create_msft_deployer_agent()
result = asyncio.run(agent.run("Deploy orders-api v1.4.2 to AKS with 2 replicas"))
print(result)
```

### 3-5. 기대 결과

- GPT-4o가 `azure_build_image` → `azure_push_image` → `azure_deploy_to_cluster` → `azure_validate_deployment` 순서로 tool 호출
- Azure 자격증명 없으면 tool 실행 시 오류 발생하지만, **LLM이 tool을 올바르게 선택**하는 것이 검증 대상

---

## 환경변수 요약 (.env)

```bash
# AWS (Strands — already working)
AWS_REGION=ap-northeast-2
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5

# GCP (ADK — Gemini)
GOOGLE_API_KEY=
GCP_PROJECT=your-gcp-project
GCP_REGION=asia-northeast3

# Azure (MS Agent Framework — GPT-4o)
AZURE_AI_PROJECT_ENDPOINT=
AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-4o
# 또는 API Key 방식:
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_REGION=koreacentral
AZURE_RESOURCE_GROUP=your-rg
```

---

## 비용 참고

| Agent | 모델 | 예상 비용 (1회 호출) |
|-------|------|---------------------|
| Strands | Claude Haiku | ~$0.001 |
| ADK | Gemini 2.0 Flash | ~$0.0003 |
| MSFT | GPT-4o | ~$0.003 |
| MSFT | GPT-4o-mini | ~$0.0003 |

> 한 번의 E2E 파이프라인 실행에 4~6 tool call이 발생합니다. 전체 비용 < $0.02.

---

## 검증 체크리스트

- [ ] `GOOGLE_API_KEY` 발급 및 환경변수 설정
- [ ] ADK Agent 실행 → Gemini가 tool 호출 순서를 올바르게 계획하는지 확인
- [ ] `AZURE_AI_PROJECT_ENDPOINT` or `AZURE_OPENAI_ENDPOINT` 설정
- [ ] MSFT Agent 실행 → GPT-4o가 tool 호출 순서를 올바르게 계획하는지 확인
- [ ] (Optional) GCP/Azure 자격증명 설정 → 실 배포까지 E2E 확인
