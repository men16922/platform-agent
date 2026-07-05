# STATUS — platform-agent

최종 갱신: 2026-07-05

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 현재 요약

- 제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`.
- Operations 4단계(detect→analyze→decide→execute) 파이프라인 런타임 동작.
- Slack interactive approval이 Step Functions callback까지 연결됨.
- overnight-harness 기반 자동 개발 루프 구성 완료 (5 engine 지원).
- Kiro CLI 특화: 3개 에이전트(overnight-harness, aws-ops, cdk-dev) + safety hook + AWS MCP Server.
- AWS portability runtime seam 연결됨. 비-AWS(GCP/Azure/on-prem)는 scaffold+테스트 단계.

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **159 passed** (2026-07-05, 1.08s)
- AWS API 접근 확인: STS/Lambda/Bedrock via q-user profile (ap-northeast-2)
- CDK deploy: 미검증 (synth만 이전에 통과)

## 동작하는 영역 (요약)

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge.
2. **Human-in-the-loop 승인** — Slack 승인 → `WaitForTaskToken` + SQS + SFN callback.
3. **Day1/1.5** — provisioning(cdk_generator/iam_designer/cost_estimator), deployment(smoke/canary/rollback), reporting(slo/oncall/capacity).
4. **Portability** — `NormalizedIncident` cloud-neutral envelope. provider registry + adapters.
5. **Runbook registry** — built-in catalog + CDK seed + scan heuristic + schema validation.
6. **Overnight harness** — overnight-harness 플러그인 기반. `make overnight` / `make overnight-kiro-once`.
7. **Kiro CLI 에이전트** — aws-ops(운영 디버깅), cdk-dev(CDK 전용), overnight-harness(자동 루프).
8. **AWS MCP Server** — agent-toolkit-for-aws, mcp-proxy-for-aws@1.6.3, profile: q-user.

## Active Focus

- STATUS/docs 현행화 (이 작업) → CDK deploy → E2E smoke test.
- overnight-harness 첫 루프 smoke test.

## Open Risks / Gaps

1. **CDK 미배포** — synth만 통과. 실 배포(alarm→pipeline→SSM→Slack) E2E 미검증.
2. **비-AWS production runtime 미연결** — adapter 파일 존재, 런타임 경로는 AWS만.
3. **runbook override 등록 자동화 부재** — 수동 AWS CLI/SDK 전제.
4. **git repo 미초기화** — 현재 디렉토리에 `.git` 없음. overnight 루프 사용 전 `git init` + 초기 커밋 필요.
