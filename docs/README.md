# docs/ — platform-agent 문서 인덱스

최종 갱신: 2026-07-17

이 디렉토리는 **context budget으로 운영되는 상태/계획/이력 문서** 체계다.
운영 규칙·라인 예산·skill 경계는 [`DOCS_POLICY.md`](./DOCS_POLICY.md) 단일 소스로 관리한다.

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
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — 전체 아키텍처

## Skills

overnight-harness skill 목록·역할·경계는 [`DOCS_POLICY.md` §5](./DOCS_POLICY.md)를 본다.
