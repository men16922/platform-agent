# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-09

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.

---

## 2026-07-09 — LLM 실호출 검증 (3-cloud) + Capability Runbook Schema

- Status: 완료
- Changed:
  - ADK Deployer: Vertex AI Gemini 3.5 Flash 실호출 성공 (location=global 해결)
  - MSFT Deployer: Azure OpenAI GPT-5.4 실호출 성공 (version=2026-03-05 명시, eastus2)
  - Capability-based runbook schema: RunbookStep + CapabilityRunbook + condition evaluator
  - CAPABILITY_RUNBOOKS 카탈로그: 5 런북 (steps 기반 cloud-neutral)
  - system prompt fix: `{region}` → `REGION` (ADK 변수 해석 충돌 해소)
  - README 로드맵 현행화: CDK deploy ✅, LLM 실호출 ✅
  - .env / .env.example: GCP(global)/Azure(eastus2)/AWS 정보 기입
  - Slack App 설정 가이드 (docs/SLACK_APP_SETUP.md)
  - AI Agent 실호출 가이드 (docs/AI_AGENT_LIVE_CALL_GUIDE.md)
  - test_decision.py mock 누락 수정 (환경의존 DynamoDB 호출 제거)
- Verified:
  - `make check` → **352 passed** (329→352, +23 capability runbook 테스트)
  - ADK: Gemini 3.5 Flash tool calling (gcp_build_image) ✅
  - MSFT: GPT-5.4 tool calling (azure_build_image) ✅
  - 리소스 전부 정리 완료 (AWS/GCP/Azure 비용 $0)
- Blockers: 없음
- Next: Slack interactive buttons / GCP·Azure live provider (GKE/AKS)

---

## 2026-07-06 — Task 5~9 완료 + 3-cloud 실배포 E2E 검증

- Status: 완료 (전체 로드맵 주요 항목 소진)
- Changed:
  - Task 5: ADK Deployer (GCP) + MSFT Deployer (Azure) + A2A Card + GCP/Azure tools (6 files)
  - Task 6: Guardian Agent + policy_engine.py + deploy-policy.yaml (7 rules)
  - Task 7: MCP Server (9 tools) + A2A Server (FastAPI) + Bridge
  - Task 8: E2E Pipeline DAG (7 nodes) + orchestrator CLI
  - Task 9: Overnight harness gate 통과 (329 passed)
  - CDK deploy: Lambda bundling fix + requirements-lambda.txt
  - README.md 현행화 (Multi-Cloud AI Platform 구조 추가)
  - 4 test result docs (docs/test/)
- Verified:
  - `make check` → **329 passed** (1.24s)
  - Local kind E2E: dev ✅, staging ✅, prod ⏸(블로킹 정상)
  - Strands + Bedrock Claude Haiku: 자율 4-tool 호출 → 실배포
  - CDK deploy: 97 resources CREATE_COMPLETE (us-east-1)
  - GCP: Artifact Registry push + GKE Autopilot 배포 (asia-northeast3)
  - Azure: ACR push + AKS 배포 (koreacentral)
  - 모든 클라우드 리소스 정리 완료 (비용 $0 복귀)
- Blockers: 없음
- Next: Slack interactive buttons / ADK·MSFT LLM 실호출 / 아키텍처 다이어그램

---

## 2026-07-05 — overnight-harness 전환 + Kiro CLI 특화 + agent-toolkit-for-aws

- Status: 완료
- Changed:
  - 구 harness 제거: `harness/`, `.harness/`, `tests/test_harness.py`, `CLAUDE.md`, `.claude/PLAN.md`, `.claude/skills/`, `PLAN.md`, `docs/plans/`, `bin/docs/archive/`
  - 캐시/아티팩트 제거: `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `src/stacks/cdk.out/`, `*.egg-info`
  - overnight-harness scaffolding: `scripts/overnight/`, `.kiro/steering/`, `.kiro/agents/overnight-harness.json`, `.codex/rules/`, `docs/engineering/`
  - Kiro CLI 특화: `.kiro/agents/aws-ops.json`, `.kiro/agents/cdk-dev.json`, `.kiro/hooks/pre-tool-use-safety.sh`
  - AWS MCP Server: `.kiro/settings/mcp.json` (agent-toolkit-for-aws, profile: q-user, ap-northeast-2)
  - Makefile 신규 (project targets + overnight snippet)
  - 문서 이동/재작성: `KIRO.md`→`docs/`, `PRESENTATION.md`→`docs/`, `.gitignore`, `docs/README.md`, `docs/DOCS_POLICY.md`, `README.md`, `AGENTS.md`
  - `.claude/harness-config.json` 커스터마이즈 (project_name, gate: make check, engine_choices +kiro)
- Verified: `make check` → **159 passed** (1.08s). AWS API 접근 확인 (q-user, STS/Lambda/Bedrock).
- Blockers: 없음
- Next: STATUS.md 현행화 → CDK deploy → E2E smoke test

---

## 2026-06-11 — harness.md 기반 문서·컨텍스트 하네스 이식

- Status: 완료
- Changed:
  - `harness/CORE_MANDATES.md`, `harness/CONTEXT_BRIDGE.md` 신규 작성
  - `docs/` current-doc 체계 신규: `AGENT_BRIEF.md` · `STATUS.md` · `NEXT_PLAN.md` · `PROGRESS_LOG.md` · `COMPLETED_SUMMARY.md` · `DECISIONS.md` · `DOCS_POLICY.md` · `README.md`
  - `.claude/skills/{sync,checkpoint,tidy-docs}/SKILL.md` 신규
  - 기존 도메인 문서(agents/architecture/conventions/models/portability/restructure-plan/status) → `bin/docs/archive/` 로 전면 이관
  - `docs/plans/`, `bin/docs/archive/` 디렉토리 생성
- Verified: `python -m pytest tests/ -q` → **201 passed** (코드 무변경, baseline 재확인). 문서만 변경.
- Blockers: 없음
- Next: 새 세션에서 `/sync` → `/checkpoint` 동작 확인 (NEXT_PLAN P1 비-AWS 런타임 연결로 진행)
