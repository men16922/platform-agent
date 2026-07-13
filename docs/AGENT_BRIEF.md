# AGENT_BRIEF — platform-agent

최종 갱신: 2026-07-13

> ▶ NEXT SESSION: `docs/NEXT_PLAN.md` — **actionable 백로그 소진**(origin/main=`686c2f0`). 남은 것은 전부 defer/외부: **A2A Phase 2**(실 kagent endpoint — kind+kagent+MLX 재프로비저닝 필요, 추천=defer), Slack App 실생성, 테크 아티클 배포. ※ 2026-07-13 완료: 추적 IA 라이브 실증·CDK diff 재검증(drift 0)·kagent 정리(MOOT)·feat 브랜치 삭제(local+origin)·**A2A discovery Phase 1 실연결+매칭 강화**·PostCSS 재검증·**NEXT_PUBLIC #7 해소**.
>
> 1분 압축 문맥. 에이전트 진입점. 이 파일은 **≤60줄**로 유지한다.

## Read Path (순서대로, bulk-read 금지)

1. `docs/AGENT_BRIEF.md` — 이 파일
2. `docs/STATUS.md` — 현재 상태 / 검증 baseline / risks
3. `docs/NEXT_PLAN.md` — 열린 작업만
4. (필요 시) `docs/PROGRESS_LOG.md` 상단 — 최신 증분
5. (필요 시) `docs/engineering/` — harness/loop/context 엔지니어링

권위 순서: `NEXT_PLAN.md` (유일한 source of truth).

## Snapshot

- **무엇:** AWS-native 플랫폼 에이전트. provision → deploy 검증 → detect → analyze → decide → execute → Slack 리포트.
- **동작하는 것:** Operations 4단계 + 3-cloud AI Agent + **On-Prem Ops**(12도구, trace) + Terraform kind/실 Multipass VM Ansible k3s Provision + kagent↔Local Qwen A2A + Agents UI. **On-Prem 오프라인 완결**: Local Qwen **7B**로 NL provision→deploy→validate ~39s, 로컬 JSONL 기록 + 대시보드 **hybrid**(AWS+On-Prem 병합) + 실 **롤백**(app/cluster). **추적 IA**: activity에 `type`(provision/deploy)·`cluster` 연결키, 대시보드 **Provisioning/Deployments/History** 분리 + **중첩 상세**(provisioning⊃deploys), 롤백 **단일-row 승계**·**teardown→deploy cascade**, 자연어 rollback/teardown도 동일 라우팅.
- **하네스:** overnight-harness 플러그인 기반 (5 engine). `make overnight-kiro-once` 로 smoke. `make dev-up`으로 로컬 스택(MLX+proxy+router+dashboard) 한 방 기동.
- **Kiro 특화:** aws-ops / cdk-dev / overnight-harness 3개 에이전트 + safety hook + AWS MCP Server.
- **검증:** `make check` → **601 passed, 1 skipped** (2026-07-13); Dashboard `next build` 성공(NEXT_PUBLIC 인라인 실측 확인); Live 7B provision→deploy→validate ~39s·app/cluster 롤백·hybrid 병합·추적 IA 자연어 4스텝 라이브 실증(2026-07-13); **A2A discovery 라이브 E2E**(supervisor→게이트웨이 카드 HTTP discovery→skill 매칭→위임). origin/main=`686c2f0`.
- **현재 초점:** actionable 백로그 소진. 잔여=A2A Phase 2(실 kagent, 추천 defer)+외부(Slack/아티클).

## Guardrails

- 에이전트=Python 3.11 / IaC=CDK TS / 모델은 `src/agents/models.py` 한 곳.
- IAM 최소 권한(`Resource:"*"` 금지), `Delete/Drop/Terminate` 액션은 강제 APPROVE.
- 요청 이상 기능 추가 금지. 테스트 통과 전 완료 선언 금지.
- Gate 명령: `make check`.

## Skills (overnight-harness)

- `/sync` — Read Path 따라 상태 복원(읽기 전용).
- `/checkpoint` — PROGRESS_LOG append + current docs 갱신.
- `/tidy-docs` — 문서 정리/압축.
- `/overnight-report` — 루프 결과 리포트.
- `/overnight-seed` — backlog 시드.
- `/diagnose` — 루프 실패 진단.
