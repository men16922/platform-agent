# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-06 (Task 5 스코프 수정: Azure → MS Agent Framework)

> **열린 작업만.** 완료 이력은 여기 두지 않는다(→ `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`). **≤120줄** 유지.
> 설계 문서: `docs/plans/2026-07-05-multi-cloud-ai-deployment-platform.md`

---

## Task 1: On-prem 환경 구성 (kind + local registry) ✅

- [x] infra/local/kind-config.yaml (3노드 + registry mirror)
- [x] infra/local/setup.sh (registry + kind + ingress)
- [x] infra/local/teardown.sh
- [x] Makefile 타겟 (local-cluster, local-cluster-down, local-cluster-status)
- [x] 검증: `make local-cluster` → 3노드 Ready + registry push/pull 확인
- [x] git commit: b17adeb

## Task 2: Deployment Adapter 추상화 ✅

- [x] `src/agents/adapters/deployment/base.py` — ABC (BuildAdapter, RegistryAdapter, ClusterAdapter)
- [x] `src/agents/adapters/deployment/local.py` — docker build + localhost:5001 + kubectl
- [x] `src/agents/adapters/deployment/aws.py` — CodeBuild + ECR + EKS
- [x] `src/agents/adapters/deployment/gcp.py` — Cloud Build + AR + GKE
- [x] `src/agents/adapters/deployment/azure.py` — Azure Pipelines + ACR + AKS
- [x] `src/agents/adapters/deployment/registry.py` — factory
- [x] 24 단위 테스트 + git commit: ef9f450

## Task 3: Service Spec 스키마 + Manifest 생성 ✅

- [x] `manifest_generator.py` — spec → K8s YAML (Deployment/Service/Ingress)
- [x] `examples/orders-api.yaml` 예시
- [x] CLI: `python -m src.agents.provisioning spec.yaml`
- [x] 15 단위 테스트 + git commit: 85d252d

## Task 4: Strands Deployer Agent (AWS/Local) ✅

- [x] `src/agents/ai/strands_deployer.py` — Agent 정의 + system prompt
- [x] `src/agents/ai/tools/` — @tool (build, push, deploy, validate, rollback)
- [x] pyproject.toml에 `strands-agents>=1.0` 추가
- [x] 19 단위 테스트 (mock model) + git commit: 547b1a0

## Task 5: 클라우드-네이티브 에이전트 (GCP: ADK / Azure: MS Agent Framework) ✅

- [x] `src/agents/ai/adk_deployer.py` — Google ADK Agent (GCP adapter를 tool로 호출)
- [x] `src/agents/ai/msft_deployer.py` — Microsoft Agent Framework Agent (Azure adapter를 tool로 호출)
- [x] `src/agents/ai/a2a_card.json` — Agent Card (A2A 프로토콜 공통)
- [x] GCP tools: `src/agents/ai/tools/gcp_build.py`, `gcp_push.py`, `gcp_deploy.py`
- [x] Azure tools: `src/agents/ai/tools/azure_build.py`, `azure_push.py`, `azure_deploy.py`
- [x] 테스트: 각 에이전트 mock model 기반 단위 테스트 (34 tests)

## Task 6: Guardian Agent (Policy-as-Code) ✅

- [x] `src/agents/ai/guardian.py` — 정책 평가 Agent
- [x] `src/agents/ai/policies/deploy-policy.yaml`
- [x] `src/agents/ai/policy_engine.py` — YAML 정책 파싱/평가
- [x] 테스트: prod → APPROVE, staging → AUTO, delete → REJECT (32 tests)

## Task 7: MCP + A2A Gateway ✅

- [x] `src/agents/ai/gateway/mcp_server.py` — kubectl/docker MCP (9 tools)
- [x] `src/agents/ai/gateway/a2a_server.py` — FastAPI A2A (v1.0 HTTP+JSON)
- [x] `src/agents/ai/gateway/bridge.py` — MCP↔A2A 번역
- [x] cross-agent 통신 테스트 (30 tests)

## Task 8: E2E Pipeline Orchestration (Graph) ✅

- [x] `src/agents/ai/pipeline.py` — Strands Graph DAG (7 nodes)
- [x] `src/agents/ai/orchestrator.py` — CLI entry
- [x] E2E 테스트: spec → plan → guard → deploy(kind) → validate → report (16 tests)

## Task 9: Overnight Harness 연동 ✅

- [x] `make check` gate 통과 (329 passed, 1.24s)
- [x] Makefile overnight targets 확인 (39줄)
- [x] harness-config.json gate=make check 연결 확인

---

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
