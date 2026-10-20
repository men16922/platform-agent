# Lessons

Last Updated: 2026-10-20

> 에이전트의 메모리(overnight-harness 1.4.0). **≤40줄** 유지 — 넘치면 `/tidy-docs`가 압축.

Repo-specific facts an agent learned the hard way, one per line, newest first. Read before
starting work; append when a blocker, gate failure, or repair taught you something the docs did
not say. Keep it under 40 lines — `/tidy-docs` compresses older entries into `docs/DECISIONS.md`
or `docs/COMPLETED_SUMMARY.md` when they stop being surprises.
Format (one line each, no prose paragraphs):

```text
- YYYY-MM-DD <area>: <what is true and how you found out>. Applies to: <path/command>.
```

Not for: task status (that is `docs/PROGRESS_LOG.md`), open work (`docs/NEXT_PLAN.md`), or
decisions with rationale (`docs/DECISIONS.md`).

## Entries
- 2026-10-20 CI 전용 실패: 저장소 루트의 `npx tsc`는 TypeScript가 아니라 npm의 `tsc@2.0.4`로 해석된다(setup-node 도입 후 PR #76 34건). `dashboard/node_modules/.bin/tsc`+`require_ts_toolchain`을 쓴다. 또 pytest는 node id를 `PYTEST_CURRENT_TEST`로 내보내므로 131KB 매개변수 id는 Linux에서 subprocess E2BIG가 된다(macOS 통과). 긴 값에는 짧은 ids를 준다. Applies to: `tests/test_dashboard_*.py`, `tests/test_writer_capture.py`.
- 2026-10-20 MLX 측정: mlx_lm 0.31.3 서버는 온도>0에서 요청 seed를 무시한다(컴파일 sampler가 import 스레드 RNG 상태에 묶임). 온도0도 prompt-cache 이력·seed 유무로 출력이 갈린다. 단일 응답 대조는 cached_tokens 기록과 cold 재기동 반복으로만 해석한다. Applies to: `docs/evidence/diagnosis-20261020/sampler-boundary/`.
- 2026-10-20 진단 대조: 같은 Ready/CrashLoopBackOff raw에서 이미지 이름만 바꾸자 이미지 장애 추정이 사라졌다. 식별자의 단어는 원인 증거가 아니며 원래 실패를 중립 이름 대조군으로 교체하지 않는다. Applies to: `docs/evidence/diagnosis-20261020/lexical-review.json`.
- 2026-10-03 MLX: 수정 전 proxy는 upstream 404를 빈 200으로 덮었다. usage-only SSE가 종료 사유를 지우지 않게 하고 잘린 도구 호출은 실행하지 않는다. client timeout도 upstream 종료가 아니다. Applies to: `src/agents/ai/mlx_qwen_tool_proxy.py`.
- 2026-10-03 진단: Qwen의 exact quote/source ID 통과는 의미·대상·시각 적합성을 보장하지 않았다. 양성 대조 질문에 대응하는 출력 필드도 있어야 한다. Applies to: `docs/evidence/dogfood-20261003/repeats/r4-structured-verification.json`.
- 2026-09-06 Lambda bundling: A && B && optional || true는 A/B 실패도 성공으로 덮는다. 선택 단계만 괄호로 묶고 실제 pip·필수 파일 누락의 종료 코드를 검사한다. Applies to: `tests/test_incident_lambda_bundling.py`.
- 2026-09-06 CDK 앱: 스택 직접 compile/synth는 cdk.json의 npx ts-node 누락을 못 본다. 빈 npm 캐시·offline·전역 실행 파일을 뺀 PATH에서 실제 app을 실행해야 한다. ts-node는 source-map-support 요청을 자체 호환 모듈로 연결한다. Applies to: `tests/test_cdk_app_entrypoint.py`.
- 2026-09-06 CDK 갱신: lib 갱신이 assembly schema를 올려 기존 CLI synth를 깨뜨렸다(53→54). CLI 호환성을 함께 검사하고 템플릿 비교는 실제 cdk.json context와 동일 bundling 조건을 사용한다. Applies to: `src/stacks/package-lock.json`.
- 2026-09-06 P5-E 입력: Python의 True==1·1.0==1과 JSON 중복 키의 마지막 값 승계가 성공 증거를 만든다. 수집 값의 JSON 타입과 중복 키를 파서/비교 경계에서 검사한다. Applies to: `writer_evidence.py`, `judge_registry_writer.py`.
- 2026-09-06 P5-E 판정: parent 변이는 후속 snapshot도 같은 오답으로 맞춰야 한다. 한 관측만 바꾸면 단계 간 불일치가 parent 가드 삭제를 가려 초록이 된다. Applies to: `tests/test_writer_evidence.py`.
- 2026-09-06 preview: 크기 초과 뒤 await reader.cancel()은 취소 실패로 413을 덮거나 미완료 취소에 매달린다. 거부 판정과 정리를 분리하고 실제 ReadableStream의 실패/미완료 cancel로 검증한다. Applies to: `registry-preview-contract.ts`, `test_registry_preview_ui.py`.
- 2026-09-06 CI 가드: 호출 문자열은 주석만 남겨도 초록이다(M62 변이). 실제 fixture를 의존성 누락 상태로 호출하고 CI/GITHUB_ACTIONS를 각각 격리한다. skip도 잡아 예상 예외와 대조해야 CI 회귀가 skip으로 숨지 않는다. Applies to: `tests/test_ci_ts_dependency_guard.py`.
- 2026-09-05 Phase 5: `root`만 격리하면 `values_for()`는 호스트를 읽는다(M53 실증의 누락). P5-A는 대상 Helm values도 같은 SHA로 읽고 `values_repo_root`를 명시한다. git·다른 tenant 파일은 불필요하다. `single_file` 권한의 존재와 PR 전체 흐름의 권한 범위는 별도로 검증한다. Applies to: `registry_write.py`, Phase 5 계획서.
- 2026-09-05 날짜 가드: 미래 일정은 `예정: YYYY-MM-DD`로 적는다. 이 날짜 토큰만 검증 이력 대조에서 제외하며 같은 줄의 완료 날짜는 계속 검사한다. Applies to: `tests/test_doc_freshness_claims.py`.
- 2026-09-05 문서 가드: `Status: 날짜`·남은 글자 수를 문자 상한으로 오인하지 않도록 선언 문맥과 수치 경계를 함께 확인한다. Applies to: `tests/test_char_budget_single_source.py`.
