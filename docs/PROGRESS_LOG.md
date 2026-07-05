# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-05

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.

---

## 2026-07-06 — Multi-Cloud AI Deployment: Task 1~3 완료

- Status: 진행 중 (Task 1~3 완료, Task 4 대기)
- Changed:
  - Task 1: `infra/local/` (kind-config.yaml, setup.sh, teardown.sh) + Makefile local-cluster 타겟
  - Task 2: `src/agents/adapters/deployment/` (base.py, local.py, aws.py, gcp.py, azure.py, registry.py) + models.py re-export
  - Task 3: `src/agents/provisioning/manifest_generator.py` + `examples/orders-api.yaml` + `__main__.py`
  - pyproject.toml: pyyaml 의존성 추가
  - docs/NEXT_PLAN.md: Task 1~9 [auto] 등록
- Verified:
  - `make local-cluster` → kind 3노드 (v1.34.0) Ready + registry push/pull → Pod Running
  - `make check` → **198 passed** (0.95s)
  - `python -m src.agents.provisioning examples/orders-api.yaml` → 유효한 K8s YAML 출력
  - git log: b17adeb (Task 1) → ef9f450 (Task 2) → 85d252d (Task 3)
- Blockers: 없음
- Next: Task 4 (Strands Deployer Agent) — strands-agents 설치 + @tool 기반 배포 에이전트

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
