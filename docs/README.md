# docs/ — platform-agent 문서 인덱스

최종 갱신: 2026-07-05

이 디렉토리는 **context budget으로 운영되는 상태/계획/이력 문서** 체계다.
운영 규칙은 `DOCS_POLICY.md`.

---

## Read Path (이 순서만, bulk-read 금지)

1. [`AGENT_BRIEF.md`](./AGENT_BRIEF.md) — 1분 진입점 (≤60줄)
2. [`STATUS.md`](./STATUS.md) — 현재 상태 / 검증 baseline / risks
3. [`NEXT_PLAN.md`](./NEXT_PLAN.md) — 열린 작업만
4. (필요 시) [`PROGRESS_LOG.md`](./PROGRESS_LOG.md) 상단 — 최신 증분

## Current docs (항상 작게 유지)

| 문서 | 역할 |
| --- | --- |
| [`AGENT_BRIEF.md`](./AGENT_BRIEF.md) | 에이전트 진입점 (≤60줄) |
| [`STATUS.md`](./STATUS.md) | 현재 구현 상태·검증·risks (≤120줄) |
| [`NEXT_PLAN.md`](./NEXT_PLAN.md) | 열린 작업만 (≤120줄) |
| [`PROGRESS_LOG.md`](./PROGRESS_LOG.md) | 최신 증분 로그 (≤120줄, 최신이 위) |
| [`COMPLETED_SUMMARY.md`](./COMPLETED_SUMMARY.md) | 완료 milestone 압축 |
| [`DECISIONS.md`](./DECISIONS.md) | 되돌리기 어려운 결정 |
| [`DOCS_POLICY.md`](./DOCS_POLICY.md) | 문서 운영 규칙 (context budget) |

## Reference

- [`engineering/`](./engineering/) — Harness engineering bibles (loop, verification, context, prompt)
- [`PRESENTATION.md`](./PRESENTATION.md) — 블로그/아티클 소스

## Overnight Harness Skills

- `/sync` — 상태 복원(읽기 전용)
- `/checkpoint` — 기록
- `/tidy-docs` — 정리
- `/overnight-report` — 루프 결과 리포트
- `/overnight-seed` — backlog 시드
- `/diagnose` — 루프 실패 진단
