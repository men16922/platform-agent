# DOCS_POLICY — platform-agent

최종 갱신: 2026-07-05

> 문서 운영 규칙(context budget). overnight-harness 기반.

---

## 1. Read Path (bulk-read 금지)

세션 시작·재개 시 아래 순서만 읽는다:

```
docs/AGENT_BRIEF.md
  → docs/STATUS.md
  → docs/NEXT_PLAN.md
  → (필요 시) docs/PROGRESS_LOG.md 상단
```

**`docs/` 전체를 한꺼번에 읽지 않는다.**

## 2. 라인 예산 (Context Budget)

| 문서 | 예산 | 내용 |
| --- | --- | --- |
| `AGENT_BRIEF.md` | ≤ 60줄 | 1분 압축 문맥, snapshot, 현재 초점, guardrails |
| `STATUS.md` | ≤ 120줄 | 현재 구현 상태, 검증 baseline, active focus, open risks |
| `NEXT_PLAN.md` | ≤ 120줄 | **열린 작업만** (완료 이력 아님) |
| `PROGRESS_LOG.md` | ≤ 120줄 | 최신 3–5개 증분. 넘치면 `COMPLETED_SUMMARY.md`로 압축 |
| `COMPLETED_SUMMARY.md` | 압축 | 완료 milestone 압축 |
| `DECISIONS.md` | 누적 | 되돌리기 어려운 결정만 (Decision/Reason/Impact) |

## 3. 권위 순서

- 다음 작업: `NEXT_PLAN.md` (유일한 source of truth).
- 모순 발견 시 그 사실을 `/sync` 요약에 명시한다.

## 4. 기록 규칙

- 완료 체크리스트는 `COMPLETED_SUMMARY.md`로 압축.
- 되돌리기 어려운 선택은 `DECISIONS.md`에 Decision/Reason/Impact.
- 한국어로 쓰되 **식별자/명령/경로는 원문 그대로.**

## 5. Skill 경계 (overnight-harness)

| skill | 역할 | 금지 |
| --- | --- | --- |
| `/sync` | 읽기만 — Read Path 따라 5–10줄 요약 | 기록·정리 |
| `/checkpoint` | 기록만 — PROGRESS_LOG append + 조건부 STATUS/BRIEF/NEXT 갱신 | 무관한 정리 |
| `/tidy-docs` | 정리만 — 중복 통합·압축 | 새 작업 기록 |

**추측 금지.** 문서에 없으면 "문서에 없음". 코드를 다시 읽어 docs를 재생성하지 않는다.

## 6. PROGRESS_LOG 항목 형식

```text
## YYYY-MM-DD — <한 줄 제목>
- Status:
- Changed:
- Verified:   # 실제로 돌린 검증만. 안 돌렸으면 "미검증"이라고 명시.
- Blockers:
- Next:
```
