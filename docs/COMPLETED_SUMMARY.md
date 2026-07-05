# COMPLETED_SUMMARY — platform-agent

최종 갱신: 2026-06-11

> 완료된 milestone 압축. current docs 에는 링크만, 상세 체크리스트는 여기로 압축.
> 도메인 원문 상세는 `bin/docs/archive/`.

---

## M0 — Operations 파이프라인 기준선 (완료)

Detector / Analyzer / Decision / Executor 4단계 + Approval Bridge. CloudWatch Alarm → Logs Insights / X-Ray / Bedrock RCA → 런북 선택 → SSM Automation → Slack 리포트 → DynamoDB 기록(90일 TTL). canonical 경로 `src/agents/operations/`, flat import 은 compatibility shim 으로 보존. Step Functions pipeline 과 handler 경로 일치.
상세: `bin/docs/archive/agents.md`, `bin/docs/archive/architecture.md`.

## M1 — Human-in-the-loop 승인 (완료)

P2 severity 흐름에 Slack interactive approval. `WaitForTaskToken` + SQS + approval bridge + Step Functions callback(`SendTaskSuccess`/`SendTaskFailure`). Approve/Reject 버튼으로 파이프라인 재개. 인터랙티브 미설정 환경은 `APPROVAL_DEFAULT_DECISION` 폴백.

## M2 — Harness / handoff 레이어 (완료)

`TaskQueue`(.harness/tasks.json), `ContextStore`(.harness/context.json), `TaskRouter`, `AgentHarness`, client 추상화. `python -m harness.handoff` 로 `.harness/handoff.md` 자동 생성(빈 상태면 워크스페이스 스캔 seed). Claude Code ↔ Codex 툴 전환 컨텍스트 보존.

## M3 — Portability runtime seam (완료)

`NormalizedIncident` cloud-neutral envelope. detector 가 alarm context 와 함께 생성 → analyzer RCA prompt 반영 → decision 이 capability 기반 runbook metadata 를 AWS action 으로 해석 → executor 가 normalized incident 기준 SSM 파라미터 우선 구성.

## M4 — 멀티클라우드/온프렘 scaffold (완료, 런타임 미연결)

provider registry + signal adapters(aws/gcp/azure/onprem) + execution adapters(aws/gcp/azure/onprem). 비-AWS 는 normalized incident / capability mapping 검증용 scaffold + 단위 테스트. 실제 provider API 호출은 NEXT_PLAN P1.

## M5 — Runbook registry bootstrap + override 계약 (완료)

`src/agents/runbooks/catalog.py` built-in capability 기반 catalog(eks-pod-oom / lambda-throttle / rds-cpu-high / kafka-lag-spike / generic-recovery). CDK custom resource 가 `incident-runbooks` 에 seed. decision 은 exact `alarm_name` lookup 실패 시 catalog scan heuristic 으로 재매칭. 코드 fallback ≡ DynamoDB 초기값.
override 계약: `src/agents/runbooks/schema.py`(`validate_runbook`). seed 시 malformed skip+로깅, decision 시 malformed 무시+경고 후 heuristic 폴백.
상세: `bin/docs/archive/agents.md` (런북 스키마 표).

## M6 — CDK deprecation 정리 (완료)

DynamoDB `pointInTimeRecovery` → `pointInTimeRecoverySpecification`. Lambda `logRetention` → 함수별 전용 `logs.LogGroup` 을 `logGroup` 으로 주입. legacy `Custom::LogRetention` 커스텀 리소스 + 부수 IAM Role 제거. `npm run synth` deprecation 13건 → 0건.

## M7 — 문서·컨텍스트 하네스 이식 (완료, 2026-06-11)

harness.md 기반으로 `harness/CORE_MANDATES.md` + `CONTEXT_BRIDGE.md`, `docs/` current-doc 체계, `.claude/skills/{sync,checkpoint,tidy-docs}` 구축. 기존 도메인 문서는 `bin/docs/archive/` 로 이관.
