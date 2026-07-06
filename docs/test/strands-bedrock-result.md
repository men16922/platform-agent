# Strands Agent + Bedrock LLM 실제 호출 테스트 결과

**실행일시:** 2026-07-06 21:20 KST  
**실행자:** Kiro CLI (kiro_default agent)  
**비용:** ~$0.001 (Claude 3 Haiku single invocation)

---

## 테스트 개요

Strands Deployer Agent가 실제 AWS Bedrock Claude LLM을 호출하여,
자연어 명령으로부터 **자율적으로** 4개 tool을 순차 호출하여 kind 클러스터에 배포하는 E2E 검증.

---

## 환경

| 항목 | 값 |
|------|-----|
| AWS Profile | q-user |
| AWS Account | 908601828278 |
| Bedrock Region | ap-northeast-2 |
| Model | `apac.anthropic.claude-3-haiku-20240307-v1:0` (APAC inference profile) |
| Framework | strands-agents (Strands SDK) |
| Target Cluster | kind-platform-agent (localhost) |
| Registry | localhost:5001 |

---

## 실행 결과

### 입력 (자연어 프롬프트)

```
Deploy the service named strands-test version v1.0.0 to the local kind cluster 
with 1 replica. The docker build context is /tmp/e2e-test-app.
```

### Agent 자율 Tool 호출 순서

```
Tool #1: build_image
  → docker build -t localhost:5001/strands-test:v1.0.0 /tmp/e2e-test-app
  → ✓ success

Tool #2: push_image
  → docker push localhost:5001/strands-test:v1.0.0
  → ✓ success

Tool #3: deploy_to_cluster
  → kubectl apply -f - (Deployment + Service manifest)
  → ✓ success

Tool #4: validate_deployment
  → kubectl rollout status deployment/strands-test
  → ✓ healthy (1/1 checks passed)
```

### Agent 최종 응답

```json
{
  "role": "assistant",
  "content": [
    {
      "text": "The deployment of the service 'strands-test' version 'v1.0.0' to the local kind cluster was successful. The service is healthy and accessible."
    }
  ]
}
```

---

## 실제 클러스터 상태 (검증)

```
$ kubectl get deployment strands-test -o wide
NAME           READY   UP-TO-DATE   AVAILABLE   CONTAINERS     IMAGES
strands-test   1/1     1            1           strands-test   localhost:5001/strands-test:v1.0.0

$ kubectl get pods -l app=strands-test
NAME                            READY   STATUS    RESTARTS   AGE
strands-test-6c899b7d4c-nvg8l   1/1     Running   0          9s
```

---

## 모델 접근 이슈 (해결됨)

| 시도 | Model ID | 결과 | 원인 |
|------|----------|------|------|
| 1 | `anthropic.claude-sonnet-4-20250514-v1:0` | ❌ ValidationException | on-demand 미지원, inference profile 필요 |
| 2 | `apac.anthropic.claude-sonnet-4-20250514-v1:0` | ❌ ResourceNotFound | 30일 미사용으로 Legacy 표시 |
| 3 | `apac.anthropic.claude-sonnet-4-5-20250929-v1:0` | ❌ ValidationException | 잘못된 model identifier |
| 4 | `us.anthropic.claude-3-5-sonnet-20241022-v2:0` | ❌ ResourceNotFound | End of Life |
| **5** | **`apac.anthropic.claude-3-haiku-20240307-v1:0`** | **✅ 성공** | APAC inference profile, 활성 상태 |

**해결 방법:** `apac.` prefix를 사용한 inference profile + 활성 모델 선택.

---

## 핵심 검증 사항

1. **Strands Agent 자율 실행:** LLM이 system prompt를 기반으로 4개 tool을 올바른 순서로 호출 (Build→Push→Deploy→Validate)
2. **Tool → Adapter → 인프라 경로:** @tool decorator → LocalBuildAdapter/LocalRegistryAdapter/LocalClusterAdapter → subprocess (docker/kubectl) → kind cluster
3. **실제 컨테이너 배포:** Pod가 kind에서 Running 확인
4. **Bedrock IAM 인증:** q-user profile → IAM user → bedrock:InvokeModel 정상 동작

---

## 아키텍처 검증

```
자연어 ("Deploy strands-test v1.0.0...")
  → Strands Agent (system prompt + tool definitions)
  → Bedrock Claude Haiku (APAC inference profile)
  → LLM reasons: "I should build, push, deploy, then validate"
  → Tool call: build_image → LocalBuildAdapter → docker build
  → Tool call: push_image → LocalRegistryAdapter → docker push
  → Tool call: deploy_to_cluster → LocalClusterAdapter → kubectl apply
  → Tool call: validate_deployment → kubectl rollout status
  → LLM: "Deployment successful!"
  → Pod Running on kind cluster ✓
```
