# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-11

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.

---

## 2026-07-11 — Dashboard 반응형·navigation QA + mobile navigation 보완

- Status: 완료
- Changed:
  - `dashboard/src/components/dashboard-header.tsx` — mobile(<md)에서 Overview/Incidents/Deployments/Agents 4개 route로 이동하는 primary navigation 추가.
- Verified:
  - Playwright MCP: desktop 1440×1000, mobile 390×844에서 4 routes 렌더링, 수평 overflow 없음 확인.
  - mobile primary navigation 4개 링크 노출 및 Incidents/Deployments/Agents 실제 route 이동 확인; console errors 0건.
  - `dashboard: npm run lint` + `npm run build` → pass; 4 routes static prerendered.
- Blockers: 없음.
- Next: Vercel preview 배포와 Open Graph 메타/이미지 구성.

---

## 2026-07-11 — Dashboard 운영 콘솔 디자인 강화

- Status: 완료 (로컬 디자인·렌더링 검수)
- Changed:
  - `dashboard/` — Chrome dark 기반 운영 콘솔 UI: 공통 셸, Overview/Incidents/Deployments/Agents 정보 계층 재구성.
  - `dashboard/public/providers/` — AWS, Google Cloud, Microsoft Azure, CNCF 로컬 SVG 자산 추가; 외부 CDN 의존 제거.
  - Overview — provider health, severity별 incident surface, Guard intervention 배포 실행 보드, provider-logo deployment register 적용.
- Verified:
  - `dashboard: npm run lint` → pass.
  - `dashboard: npm run build` → pass; 4 routes static prerendered.
  - Playwright → `http://localhost:3000` 렌더링/스크린샷 검수, 콘솔 오류 0건 (Next font preload warning 1건).
- Blockers: 없음. Vercel 배포와 실제 API 데이터 연결은 아직 수행하지 않음.
- Next: 4개 route 반응형·상호작용 QA를 마친 뒤 Vercel preview 배포와 Open Graph 메타데이터를 준비.

---

## 2026-07-10 — GCP/Azure Day2 Operations + Dashboard 구현

- Status: 완료
- Changed:
  - `src/agents/operations/gcp/` — 5 모듈 (detector/analyzer/decision/executor/workflows)
  - `src/agents/operations/azure/` — 5 모듈 (detector/analyzer/decision/executor/durable_functions)
  - `tests/test_gcp_day2_operations.py` — 28 tests (Vertex AI Gemini 실호출 포함)
  - `tests/test_azure_day2_operations.py` — 28 tests
  - `dashboard/` — Next.js 16 + Tailwind 4, 4개 페이지 (Overview/Incidents/Deployments/Agents)
  - `docs/ARCHITECTURE.md` — GCP/Azure 모든 상태 🔲→✅ 업데이트 + 구현 상세 섹션 추가
  - `docs/DASHBOARD_DESIGN.md` — 대시보드 디자인 방향 문서 (결정 대기)
- Verified:
  - `pytest tests/ --ignore=tests/test_gcp_day2_operations.py` → **490 passed** (462 기존 + 28 Azure)
  - `pytest tests/test_gcp_day2_operations.py` → **28 passed** (Vertex AI 실호출, severity=P2, confidence=0.95)
  - Dashboard: `npm run build` → 4 routes static prerendered, HTTP 200 전부 확인
  - GCP E2E: Cloud Monitoring alert → Pub/Sub → detect → analyze(Gemini) → decide → execute
  - Azure E2E: Azure Monitor alert → Event Grid → detect → analyze(heuristic) → decide → execute
- Blockers: 없음
- Next: 대시보드 디자인 방향 결정 → 스타일 적용 → Vercel 배포

---

## 2026-07-10 — 4-Cloud 실배포 데모 (EKS/GKE/AKS/On-Prem)

- Status: 완료 + 정리
- Changed:
  - `examples/orders-api/Dockerfile` + `app.py` — 데모용 Flask 앱 (healthz/id 엔드포인트)
  - `docs/SIMPLE_ARCHITECTURE.md` — 블로그용 심플 아키텍처 문서
  - CDK Lambda bundling fix (이전 커밋)
- Verified:
  - **EKS** (ap-northeast-2): Cloud Build 없이 ECR 직접 push → kubectl → 2 pods Running → /id 응답 ✅
  - **GKE** (asia-northeast3): Cloud Build → Artifact Registry → kubectl → 2 pods Running → /id 응답 ✅
  - **AKS** (koreacentral): ACR push → kubectl → 2 pods Running → /id 응답 ✅
  - **On-Prem** (kind 3-node): docker build → kind load → kubectl → 2 pods Running → /id 응답 ✅
  - 4곳 모두 외부 엔드포인트 (LB/port-forward) 접근 확인
  - 데모 후 전체 리소스 삭제 완료 (비용 $0 복귀)
- Blockers: 없음
- Next: 블로그 포스팅 게시 + push

---

## 2026-07-10 — CDK 재배포 (IncidentAgentStack, us-east-1)

- Status: 완료
- Changed:
  - `src/stacks/incident_agent_stack.ts`: Lambda bundling 수정 — `cp -r src/` → `cp -r src/agents + src/step_functions` (src/stacks 제외, 281MB→36MB)
  - DynamoDB 테이블 4개 (이전 RETAIN 잔류) 수동 삭제 후 CDK 새로 생성
  - 97 resources CREATE_COMPLETE (us-east-1)
- Verified:
  - ApprovalBridgeFunctionUrl: `https://kglj7vclmq4sqm7u7ap5ydldyu0yndto.lambda-url.us-east-1.on.aws/`
  - IngressFunctionUrl: `https://wztlktdd5l4ox3l3acufj5mu4q0svepc.lambda-url.us-east-1.on.aws/`
  - Step Functions, EventBridge, SQS, DynamoDB 모두 정상 생성
- Blockers: 없음
- Next: Slack App 생성 후 Interactivity URL에 ApprovalBridgeFunctionUrl 설정

---

## 2026-07-09 — Capability-based Runbook Schema 확장 (9 런북 × 4 provider)

- Status: 완료
- Changed:
  - catalog.py: CAPABILITY_RUNBOOKS 5→9 (disk-full, health-check-failure, certificate-expiry, network-latency-high)
  - kafka-lag-spike에 rebalance_consumer step 추가, lambda-throttle에 serverless-service 추가
  - 4 provider execution adapter 매핑 보완:
    - AWS: rollback_release, rebalance_consumer, cleanup_disk_space, expand_storage, renew_certificate, drain_node
    - GCP: scale_database_primary, rollback_release, rebalance_consumer + 동일 새 capability
    - Azure: scale_database_primary, rollback_release, rebalance_consumer + 동일 새 capability
    - OnPrem: scale_database_primary + 동일 새 capability
  - tests/test_capability_runbook_e2e.py: 84개 E2E 테스트
- Verified: `make check` → **462 passed**, 1 skipped (0.78s)
- Blockers: 없음
- Next: README 로드맵 체크 + commit

---

## 2026-07-09 — Slack Interactive Buttons E2E 테스트 완성

- Status: 완료
- Changed:
  - `tests/test_approval_bridge_e2e.py` — 25개 E2E 테스트 추가
    - TestE2EApprovalFlow: 전체 approve/reject 플로우 (SQS→DDB→Slack callback→SFN)
    - TestSlackSignatureVerification: 실제 HMAC-SHA256 검증 (9 tests)
    - TestEdgeCases: 중복 클릭, 만료, SFN 실패→PENDING 복원, 배치, fallback
    - TestBlockKitStructure: Approve/Reject 버튼, non-interactive, header 포맷
    - TestApprovalIdGeneration: deterministic, collision-resistant, format
  - handler.py 코드는 이미 완전 구현 상태 확인 (추가 변경 없음)
- Verified: `make check` → **378 passed** (352→378, +25 E2E + 1 기존 추가)
- Blockers: 없음
- Next: README 로드맵 Slack interactive buttons ✅ 체크 + commit

---

## 2026-07-09 — Architecture Diagrams (3장) + Image References

- Status: 완료
- Changed:
  - GPT image generation 프롬프트 3개 작성 및 다이어그램 생성 완료
    - High-Level Architecture (PATH A/B, Orchestrator, Day1/2, Cross-cutting)
    - Day 1: AI Deployment Pipeline (7-Step DAG, 4 Agents, 4 Targets)
    - Day 2: Incident Response Pipeline (Signal→Detect→Analyze→Decide→Execute)
  - docs/ARCHITECTURE.md: 각 섹션에 `![](images/...)` 참조 추가
  - docs/images/README.md 생성 (expected files + color scheme 문서화)
  - 모든 다이어그램 영어 전용, 통일된 color scheme (Orange=AWS, Blue=GCP, Dark Blue=Azure, Gray=On-Prem, Purple=AI)
- Verified: ARCHITECTURE.md image refs 삽입 확인
- Blockers: 이미지 파일은 수동으로 docs/images/ 에 배치 필요
- Next: 이미지 파일 배치 후 commit, Slack App 생성 (last priority)

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
