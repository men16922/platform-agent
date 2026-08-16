# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-15

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-16 — 08-11부터 묶여 있던 항목: 기록된 차단 이유가 틀렸다 (gate 2102)

- Status: `slack_live_approval.py`는 *"고치면 조용히 no-op"*이라 08-11부터 안 고치고 있었고,
  기록은 *"올바른 이름은 **Slack 데모를 태워야 확정**된다"*였다. **이 레포는 오늘 이미 그런
  기록 하나가 틀린 걸 봤으니**(M19 ⓑ) 믿지 말고 시험했다.
- Verified(**①은 참, ②는 근사했다**): 임포트 경로
  `src.agents.operations.approval_bridge`는 **추적 트리에 없다** — 패키지가 `aws/` 아래로
  이사했고 옛 경로는 **untracked `cdk.out/`에만** 남아 있다(그래서 `cdk synth`를 돌린 머신에서만
  임포트가 됐다). ⚠️기록은 *"여섯 중 넷 부재"*였는데 실제로는 **5/6이 부재**(`_SFN`만 존재)이고
  **호출하는 셋은 전부 존재**한다.
- Verified(**"데모 선행"은 틀렸다**): 사라진 다섯은 서브모듈 분해로 옮겨졌고 **각각 정확히
  한 곳**에 있다(`slack_interactive` 셋 · `request_store` 둘) — 추측 여지가 없다. 그리고
  `_post_slack_request`가 **호출 시점에 모듈 전역을 읽으므로** setattr이 실제로 먹는다.
- Changed: 임포트를 `aws/` 경로로 고치고 다섯 대입을 **값이 실제로 사는 서브모듈**로 돌렸다.
  `handler._SFN`은 **그대로** — 거기서 읽는다(`handler.py:207,220`). 왜 서브모듈이어야 하는지를
  임포트 옆 주석에 적었다.
- Verified(**오프라인 실증**): 스크립트 자신의 `simulate`가 문서상 완전 오프라인이라 그걸로
  끝까지 돌렸다 — SQS 요청→PENDING 저장→**실제 HMAC 서명** 버튼 콜백→HTTP 200→SFN
  resume→**APPROVED**. **Slack 없이 확정됐다.**
- Changed(가드 +8, `test_harness_patch_targets_exist.py` 신규): 스크립트가 대입하는 이름을
  **AST로 뽑아** 대상 모듈에 실재하는지 묻는다(웹훅·자격증명 없이 성립). 호출 진입점 셋 ·
  옛 임포트 경로 부재도 함께. 변이: 대입 하나를 `handler`로 되돌리면 red.
  `make check` **2102**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: ⚠️**"기록된 이유"가 오늘만 세 번 틀렸다**(M19 ⓑ · `Resource:"*"` 전면 금지 · 이번 것).
  전부 **시험하면 값이 났다**. 남은 것: DUAL 모드 조건부 리다이렉트는 **여전히 안 만든다**
  (둘 다 경고에 못 닿아 하중을 못 받는 가드가 된다 — 이건 시험해서 확인한 게 아니라 기록 유지).

## 2026-08-16 — `Resource:"*"` 7건의 근거를 찾아 닫았다 — 도구를 두 번 잘못 골랐다 (gate 2094)

- Status: 08-15에 *"AWS 권한 레퍼런스가 JS 렌더라 못 읽는다"*로 열어 둔 항목. **출처 없이
  코드 주석으로 단정하지 않겠다**고 했으니 출처를 찾는 게 남은 일이었다.
- Verified(⚠️**도구를 두 번 잘못 골랐다**): ①**IAM 정책 시뮬레이터** — 리소스 한정 정책이
  `implicitDeny`+`MatchedStatements: []`라 답이 나온 줄 알았는데, **대조군(`Resource:"*"`)도
  `implicitDeny`**였다. CloudWatch 메트릭은 애초에 ARN으로 주소 지정되는 자원이 아니라
  시뮬레이터가 답할 수 있는 질문이 아니다. ②첫 시도의 `--resource-arns`는 IAM root ARN이라
  **어느 액션과도 안 맞았다** — 대조군이 실패한 걸 뒤늦게 봤다.
- Verified(**되는 도구**): AWS 문서엔 **GitHub 마크다운 미러**가 있고(`awsdocs/*`), 권한
  레퍼런스는 **JSON 미러**가 있다(`iann0036/iam-dataset`, 455개 서비스). 7건 전수 대조 —
  6건은 `resource_types` **없음**, ⚠️**`cloudwatch:ListMetrics`만 `dataset`이 있다**
  (Metrics Insights용이라 메트릭 나열엔 안 맞는다). **"전부 없음"으로 뭉뚱그렸으면 틀렸다.**
- Changed: 7건 전부에 **인접 주석**으로 근거를 적었다(`ListMetrics`의 예외까지). ⚠️`if` 블록
  위에 있던 `ListStateMachines`의 이유는 **문장 옆으로 내렸다** — 참인데 읽는 사람 눈에 없었다.
- Changed(가드 +9, `test_iam_wildcard_justified.py` 신규): 추적되는 `src/stacks/*.ts`의
  모든 `resources: ['*']`가 **인접 주석**을 갖는가(`git ls-files`로 `cdk.out` 배제). 규칙이
  **prose 품질이 아니라 인접성**인 이유도 테스트로 고정했다. 변이: 주석 하나 제거 → 2 failed.
  ⚠️**그 인접성 테스트를 처음엔 손으로 다시 스캔해 짰다가 줄 인덱스를 틀렸다** — 같은 스윕을
  재사용하도록 고쳤다. **검사기와 어긋나는 검사기**가 오늘 여러 번 나온 그 모양이다.
  `make check` **2094**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: 가드레일 문구도 참으로 갱신했다(`AGENT_BRIEF`). ⚠️**같은 라운드에 내가 또 밟았다** —
  진입점 문서의 게이트 숫자를 `str.replace`로 **assert 없이** 갱신해 앵커가 안 맞자 **조용히
  no-op**이 됐고, 줄 수는 그대로라 예산 가드도 못 잡았다. **2081·2085 두 번을 2073인 채로
  커밋했다.** ⇒ **문서 치환은 앵커를 assert할 것**(오늘 코드 쪽에선 계속 그렇게 했으면서
  문서 쪽에선 안 했다). 남은 항목은 전부 외부 입력 대기 — Phase 4 승인 셋 · `.[azure]`
  업스트림 · **CI 검증(push 필요, D43)**.

## 2026-08-16 — CI가 미선언 의존성을 인라인으로 떠받치고 있었다 (gate 2085)

- Status: 내가 `azure` extra에 패키지를 더했는데 **그 extra는 해석이 안 된다**. CI가 그걸
  설치하면 내가 CI를 깬 것이라 확인했다 — **안 깼다**(CI는 `.[dev,state,observability]`만).
  ⚠️**대신 M25가 확증됐다**: 그 줄이 `fastapi "uvicorn[standard]"`를 **명령줄에 직접** 적고
  있었다. **선언이 없어서** 누군가 CI에 손으로 적은 것 — 게이트는 초록인데
  `pip install .`은 그걸 안 준다.
- Changed: CI가 `serving` extra를 **이름으로 요구**하도록 정리(`.[dev,state,observability,serving]`).
  ⚠️**설치 집합은 바꾸지 않았다** — `serving`을 `uvicorn[standard]`로 맞췄다.
- Verified(⚠️**내 근거가 도구에 안 맞았다**): 처음엔 *"코드가 `uvloop`를 임포트 안 하니
  `[standard]`는 불필요"*로 평범한 `uvicorn`을 선언했다. **틀린 추론이다** — 그건 **uvicorn이
  내부에서 쓰는 것**이지 우리 코드가 임포트하는 게 아니라, `src/` grep으로는 답할 수 없다.
  게다가 **CI를 여기서 돌려 볼 수단이 없다**. ⇒ **한 번에 하나만 바꾼다**: 우회는 제거하되
  러너에 떨어지는 패키지는 그대로.
- Verified(가드 +4, `test_optional_dependencies_declared.py` 확장): CI가 `serving`을 요구하는가 ·
  **선언된 패키지를 인라인으로 적지 않는가**(`.[...]` 안의 이름은 오탐 제외) ·
  **문서화된 예외**(`pydantic-ai-slim`은 `onprem`이 Apple 전용 mlx-lm을 끌어 고의 인라인)의
  **이유가 파일에 남아 있는가**. 변이: CI를 옛 방식으로 되돌리면 **3 failed**, 복구하면 23 passed.
  `.[serving]`·CI 조합 둘 다 dry-run 해석 OK. `make check` **2085**, 로컬 macOS·py3.13.
- Blockers: 없음.
- Next: ⚠️**CI 변경을 검증하지 못했다** — 여기서 워크플로를 돌릴 수 없고 `main`은 D43으로
  push가 막혀 있다. 근거는 "설치 집합 무변경"뿐이고, 틀렸다면 되돌리기는 한 줄이다.
  **이건 측정이 아니라 논증이다.**

