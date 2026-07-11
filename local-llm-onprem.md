# Local LLM On-Prem 검증 보고서

검증일: 2026-07-11  
결론: **통과** — Apple Silicon 로컬 MLX-LM 서버에서 `Qwen3-Coder-30B-A3B-Instruct-4bit`가 OpenAI 호환 추론과 On-Prem 배포 도구 호출을 정상 처리했다.

## 검증 환경

| 항목 | 실측값 |
| --- | --- |
| 호스트 | MacBook Pro, Apple M4 Max, unified memory 48GB |
| OS | macOS 26.5, arm64 |
| 런타임 | MLX 0.32.0, MLX-LM 0.31.3 |
| 모델 | `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit` |
| 모델 파일 | 17,180,913,664 bytes (30.5B total parameters, 4-bit) |
| 서버 | `127.0.0.1:18080` (외부 노출 없음) |
| KV/prompt cache | 2GiB 상한 |

모델은 약 17.2GB라서 이 검증 호스트의 48GB 메모리에서 실행 가능하다. 운영 환경에서도 모델 파일 외에 macOS와 KV cache 여유를 남겨야 하므로 32GB는 최소선, 48GB 이상을 권장한다.

## 실행 방법

전역 Python 환경의 `transformers 5.13.0`은 현재 MLX-LM 0.31.3과 호환되지 않아 `AutoTokenizer.register`에서 실패했다. 아래처럼 격리 환경에서 검증했다.

```bash
python -m venv .venv-mlx
.venv-mlx/bin/pip install 'mlx-lm==0.31.3' 'transformers==5.0.0'

HF_HUB_DISABLE_XET=1 .venv-mlx/bin/mlx_lm.server \
  --model mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit \
  --host 127.0.0.1 --port 18080 \
  --max-tokens 512 --prompt-cache-bytes 2147483648
```

플랫폼 에이전트에는 다음 환경 변수만 설정하면 된다. 현재 `src/agents/ai/strands_deployer.py`가 이를 읽어 Strands `OpenAIModel`을 MLX endpoint에 연결한다.

```bash
export ONPREM_LLM_PROVIDER=mlx
export ONPREM_LLM_ENDPOINT=http://127.0.0.1:18080/v1
export ONPREM_LLM_MODEL=mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit
```

## 실측 결과

| 검증 | 결과 | 근거 |
| --- | --- | --- |
| MLX HTTP 모델 목록 | PASS | `GET /v1/models`가 모델 ID를 반환 |
| 기본 chat completion | PASS | 요청 26 tokens(18 prompt + 8 completion)에 정확히 `MLX on-prem inference healthy` 반환 |
| OpenAI tool calling | PASS | `finish_reason=tool_calls`, `validate_deployment` 호출 및 `{"service_name":"platform-agent-smoke","provider":"onprem"}` JSON 인자 반환 |
| Strands On-Prem 모델 구성 | PASS | `ONPREM_LLM_*` 설정으로 agent가 위 MLX 모델 ID를 사용하도록 구성됨 |
| 기존 deployer 도구 단위 테스트 | PASS | `pytest tests/test_strands_deployer.py -q` → 19 passed |

Tool-call 검증은 실제 Kubernetes 명령을 실행하지 않고, MLX 서버가 프로젝트 도구 스키마를 올바르게 해석·직렬화하는지를 확인했다. 이는 build/push/deploy 같은 변경 작업을 로컬 테스트 중 임의 실행하지 않기 위한 안전한 경계다.

## 현재 한계와 다음 실행

- 현재 kubeconfig는 DNS가 해제된 이전 EKS endpoint를 가리키며, `kind get clusters`도 비어 있다. 따라서 실제 `kubectl` 배포/검증 단계는 이번 실행 범위에서 통과로 선언하지 않았다.
- 실제 On-Prem E2E를 하려면 `make local-cluster`로 kind와 `localhost:5001` registry를 만들고, 전용 smoke 이미지/namespace에서 agent가 반환한 도구 호출을 실행한다. 기존 워크로드에는 실행하지 않는다.
- MLX-LM 서버는 localhost 용도다. production에서는 서버를 외부에 직접 노출하지 말고, 인증된 내부 프록시 또는 동일 노드 통신으로 제한한다.
- `transformers`는 검증된 `5.0.0`으로 pinning한다. 최신 전역 패키지를 무심코 올리면 MLX-LM import 실패가 재발할 수 있다.

## 판정

로컬 LLM이 On-Prem Agent의 **모델 호출 및 tool-call 계층**을 대체할 수 있음이 확인됐다. 실제 클러스터 실행은 별도 kind smoke 환경을 준비한 뒤 수행해야 하며, 현재 기본값인 Qwen2.5-Coder 32B 8-bit 대신 이 4-bit Qwen3-Coder 모델을 `ONPREM_LLM_MODEL`으로 설정해 사용하는 것을 권장한다.

---

## kind 대상 실배포 추가 검증 (2026-07-11)

EKS kubeconfig를 사용하지 않았다. `make local-cluster`로 새 `kind-platform-agent` 3-node 클러스터를 만들고, 전용 `local-llm-smoke` namespace에서만 실행했다.

| 단계 | 결과 | 실측 근거 |
| --- | --- | --- |
| kind 준비 | PASS | control-plane + worker 2개 모두 `Ready`, context=`kind-platform-agent` |
| Qwen 배포 의도 생성 | PASS | `qwen-kind-smoke`, `nginx:1.27-alpine`, replica=1, namespace=`local-llm-smoke`, port=80, health path=`/` 생성 |
| adapter 실제 배포 | PASS | `deploy_to_cluster` → `status=success`, deployment ID=`local-llm-smoke/qwen-kind-smoke` |
| kind rollout | PASS | `kubectl rollout status` → successfully rolled out |
| Pod 상태 | PASS | `qwen-kind-smoke` 1/1 `Running`, image=`nginx:1.27-alpine` |
| adapter 실제 검증 | PASS | `validate_deployment` → `healthy=True`, `checks_passed=1/1` |

따라서 **Qwen → kind 실제 배포 및 검증은 성공**했지만, 완전 자율 Strands 루프에 투입하기 전에는 MLX server의 Qwen3-Coder tool parser가 OpenAI tool-call 형식과 provider enum을 안정적으로 출력하도록 호환성 보강이 필요하다. 이 보정 없이는 모델 출력값을 검증하지 않고 실행해서는 안 된다.

---

## 완전 자율 Strands + Qwen + Local Proxy 추가 E2E 검증 (2026-07-11)

MLX-LM 서버의 도구 호출 및 XML 마크업 파싱 문제를 보완하는 `mlx_qwen_tool_proxy`를 추가한 후, 완전 자율적인 `Strands Agent` 루프를 이용해 `orders-api` 패키지의 빌드부터 검증까지 전체 파이프라인 E2E를 성공적으로 수행했다.

### 1. 프록시 개선 및 동작
- **기능:** MLX-LM 0.31.3 서버가 직접 반환하는 정형화된 OpenAI `tool_calls` 객체의 통과(Pass-through)를 보장하고, XML 마크업(`<function=...>` / `<parameter=...>` 형식) 발생 시에만 JSON tool call로 구조화해주는 Fallback 매칭 어댑터 탑재.
- **포트 구성:** MLX-LM 서버(`:18080`) -> 프록시 서버(`:18081`) -> Strands `OpenAIModel` (`ONPREM_LLM_ENDPOINT` 연동).

### 2. 자율 루프 E2E 테스트 결과
테스트 시나리오: `orders-api v1.4.2` 배포 시도 (`local-llm-smoke` 네임스페이스)

| 단계 | 수행 도구 | 상태 | 상세 기록 |
| --- | --- | --- | --- |
| 1. Build | `build_image` | PASS | `localhost:5001/orders-api:v1.4.2` 로컬 빌드 성공 |
| 2. Push | `push_image` | PASS | 로컬 kind registry (`localhost:5001`)로 푸시 완료 |
| 3. Deploy | `deploy_to_cluster` | PASS | deployment/service 리소스 생성 (`local-llm-smoke` 네임스페이스) |
| 4. Validate | `validate_deployment` | PASS | `rollout status` 대기 및 Ready 상태 확인 완료 (1/1 Running) |

```bash
# E2E 검증 실행 결과 확인
$ kubectl get deployments -n local-llm-smoke
NAME         READY   UP-TO-DATE   AVAILABLE   AGE
orders-api   1/1     1            1           5s

$ kubectl get svc -n local-llm-smoke
NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
orders-api   ClusterIP   10.96.242.204   <none>        8080/TCP   7s
```

### 3. 판정
- `mlx_qwen_tool_proxy`를 통한 호환성 어댑터 적용 결과, 모델의 직접적인 `tool_calls` 출력을 소실 없이 중계하여 Strands 에이전트가 단일 프롬프트 지시로부터 **자율적으로 4단계 배포 시퀀스(Build -> Push -> Deploy -> Validate)를 중단 없이 E2E 완수**함을 입증했다.
- 이로써 On-Premise 로컬 LLM을 통한 자율 플랫폼 에이전트 배포 시나리오 검증을 완벽히 통과로 종결한다.

---

## 프레임워크 분리: 온프렘은 Strands 대신 Pydantic AI (2026-07-11)

### 배경
로컬 경로에서 Strands는 본래 가치(Bedrock/AWS-native)를 쓰지 않으면서, Qwen의 tool-call 포맷을 맞추기 위한 프록시 계층까지 요구했다. "AWS SDK 없이 완전 로컬"이라는 온프렘 서사를 정직하게 만들기 위해, 프레임워크를 각 클라우드의 네이티브 어댑터로 대칭 배치했다.

| provider | 프레임워크 | 모델 | 모듈 |
| --- | --- | --- | --- |
| aws | Strands | Bedrock Claude | `strands_deployer.py` |
| gcp | ADK | Vertex Gemini 3.5 Flash | `adk_deployer.py` |
| azure | MSFT SDK | Azure OpenAI GPT-5.4 | `msft_deployer.py` |
| **onprem / local** | **Pydantic AI** | **MLX Qwen2.5/3-Coder** | **`local_deployer.py`** |

### 구현
- `src/agents/ai/local_deployer.py` — **Strands 無의존** Pydantic AI 에이전트. `import strands` 전무 (단위 테스트로 강제). tool 5종(build/push/deploy/validate/rollback)은 plain 함수로, 프레임워크 중립 `get_deployment_adapters`를 직접 호출.
- `create_local_deployer(provider="onprem", model=None)` — `ONPREM_LLM_*` 환경변수로 `OpenAIChatModel`을 로컬 프록시에 연결. `model=TestModel()`로 LLM 없이 구동 가능.
- 의존성: `pip install -e '.[onprem]'` → `pydantic-ai-slim[openai]` + `mlx-lm` (경량, OpenAI 프로바이더만).

### 프록시 프레임워크 중립화
`mlx_qwen_tool_proxy`가 클라이언트 요청의 `stream` 플래그를 존중하도록 확장했다. Strands(`OpenAIModel`, 스트리밍)는 SSE를, Pydantic AI(`run_sync`, `"stream": false`)는 단일 `chat.completion` JSON을 받는다. 업스트림 MLX 호출은 항상 스트리밍으로 강제해 파싱을 단일화하고, 업스트림이 JSON으로 답할 경우의 fallback(`_extract_from_json`)도 추가했다.

```bash
# 온프렘 로컬 배포 에이전트 실행 (MLX :18080 -> proxy :18081 -> Pydantic AI)
export ONPREM_LLM_ENDPOINT=http://127.0.0.1:18081/v1
export ONPREM_LLM_MODEL=mlx-community/Qwen2.5-Coder-32B-Instruct-8bit
python -c "from src.agents.ai.local_deployer import create_local_deployer; \
print(create_local_deployer().run_sync('Deploy orders-api v1.4.2 to the local cluster').output)"
```

### 검증
- `pytest tests/test_local_deployer.py tests/test_mlx_qwen_tool_proxy.py -q` → **12 passed** (TestModel 기반 전체 tool 배선 + 프록시 stream/non-stream/XML-fallback 통합 테스트 포함).
- 전체 게이트 `make check` → **554 passed, 1 skipped** (기존 Strands/ADK 경로 회귀 없음).

