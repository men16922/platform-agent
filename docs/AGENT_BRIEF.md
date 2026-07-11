# AGENT_BRIEF — platform-agent

최종 갱신: 2026-07-11

> ▶ NEXT SESSION: `docs/NEXT_PLAN.md` — (1) **origin push**(ahead 20), (2) supervisor의 실제 specialist A2A endpoint 연결 + **Agent Card discovery**(현재 card는 노출만) 후 kagent↔로컬 Qwen 연결.
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
- **동작하는 것:** Operations 4단계 + 3-cloud AI Agent + AI Model Router + **범용 On-Prem Ops 에이전트**(provision+deploy+investigate 12도구, reasoning+tool 트레이스) + On-Prem **Provision**(Terraform kind/Ansible k3s) + 대시보드 Agents 채팅(SSE 스트리밍·배포 상세페이지·Tools 팝업). kagent kind 설치됨.
- **하네스:** overnight-harness 플러그인 기반 (5 engine). `make overnight-kiro-once` 로 smoke.
- **Kiro 특화:** aws-ops / cdk-dev / overnight-harness 3개 에이전트 + safety hook + AWS MCP Server.
- **검증:** `make check` → 584 passed, 1 skipped (2026-07-11); supervisor/A2A focused tests 37 passed; Dashboard build + Vercel production + 사용자 권한 관리 UI + 멀티클라우드 우회 복구(Failover) 및 로컬 MLX Qwen2.5/3 프록시 기반 kind E2E 자율 배포 검증 성공.
- **현재 초점:** supervisor의 실제 specialist endpoint·Agent Card discovery 연결, 이후 kagent↔로컬 Qwen.

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
