# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-30 — "업스트림 대기" 둘의 재개 조건을 재다: 하나는 열렸고, 하나는 다른 리스크였다 (gate 2302)

- Status: 남은 항목이 승인·콘솔 수동에 몰려 있어, **닫혀 있던 "업스트림 대기" 항목들의 재개 조건**을
  쟀다. 둘 다 기록이 낡아 있었고 **한쪽은 리스크의 성격 자체가 달랐다**. 증거 둘:
  `the-azure-extra-cannot-be-installed.log`(기존, 조건 갱신) ·
  `docs/evidence/the-dashboard-audit-record-described-a-different-risk.log`(신규).
- Verified(**`.[azure]` — 재개 조건 ①은 충족됐다**): 격리 venv(py3.13)에서 `pip install .[azure]`가
  **31.5초에 성공**한다. 08-15엔 `agent-framework>=1.0` 단독으로 **150초 타임아웃**이었다
  (`core[all]` 강제 → 무한 역추적). 지금은 **1.16.0**이고 `Provides-Extra: []` — 업스트림이 풀었다.
- Verified(**②는 미충족이고, 버전 지연이 아니다**): 진짜 라이브러리에 대고 태우니 `msft_deployer.py:19`가
  `ImportError: cannot import name 'AzureOpenAIResponsesClient'`로 죽는다. 설치 트리를 훑으니
  **`AzureOpenAI*Client` 클래스가 0개**고, 그 이름은 **업스트림 자신의 docstring 한 줄**에만 있다
  (`agent_framework_azure_contentunderstanding/_file_search.py:78`). ⇒ **여전히 안 고친다 — 대체 심볼이
  없으므로 추측은 발명.** 형제 스윕: adk/local은 **자기 extra 미설치**일 뿐이고(둘 다 선언돼 있다)
  strands는 임포트된다 — **자기 extra가 깔린 채 죽는 건 msft 하나**다.
- Verified(**⚠️Risk 11 — 기록이 세 군데 다 틀렸다**): *"PostCSS moderate 2건 · 패치 없음 · 빌드타임이라
  런타임 위험 낮음"*인데 실측은 **critical 2 · high 6**이고 **런타임**이다. `next-auth`가 *"auth checks
  **fail open**"*(critical)인데 **런타임 8파일**에 있고 그중 하나가 **승인 UI**(`pending-approvals`) ·
  next는 **미들웨어 우회·SSRF·내부 Server Function 노출** · PostCSS조차 이제 **high**(임의 `.map` 읽기).
  ⚠️**기록의 반증 실험이 `--force` 하나였다** — non-force는 **메이저 강등이 없다**. 하나의 경로에서 얻은
  답을 항목 전체의 성질로 쓴 것이고, 08-18의 *"거부가 러너 하나의 성질이었다"*와 같은 모양이다.
- Changed(**Tier A만 적용**): `npm audit fix` → **critical 2 → 0**(총 8→3). 변경은 **lockfile 32줄**이고
  **package.json은 그대로**다. `npx tsc --noEmit` 통과 · `npm run build` **exit 0**(라우트 전부 생성).
  ⛔**Tier B는 안 했다**: 남은 high 3(next·postcss·sharp)이 **`next@16.3.3`**에 달렸는데 major는 아니어도
  **프레임워크 마이너 업**이고 이 대시보드는 **조용히 강등된 이력**이 있다(Risk 1) → **결정 사안**.
- Changed(**측정이 남긴 것도 치웠다**): `pip install .`이 리포 루트에 **`build/`를 남기는데 gitignore에
  없었다** — 지우고 `.gitignore`에 넣었다(커밋될 수 있던 함정).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. ⚠️**Risk 11을 "upstream 대기"로 다시 닫지 말 것** — 업스트림은 이미 고쳤다.
- Next: **Tier B 결정**(`next@16.3.3`) · Azure executor 배선(승인) · BQ 결제 내보내기(콘솔 수동).

## 2026-08-30 — 승인 대기 항목의 근거를 재다: 결론은 살아남고, 적힌 목록이 틀렸다 (gate 2302)

- Status: 남은 항목이 대부분 승인·업스트림·콘솔 수동이라, **가장 값싼 다음 수 = 승인을 떠받치는
  기록된 근거를 재는 것**이었다. Azure executor 항목의 근거 셋을 물었다. 코드 변경 0.
  증거는 `docs/evidence/azure-executor-reports-resolved-without-executing.log` **§정정 2026-08-30**.
- Verified(**디스패치 비대칭은 유효**): 러너 파일은 gcp 325 · azure 311 · onprem 226줄, aws는 없다
  (SSM 경로). **executor가 자기 러너를 부르는 건 GCP 하나** — 08-16 그대로이고 `test_executor_
  dispatches_to_runner.py`가 AST 호출로 집행한다.
- Verified(**⚠️"순수 잠재"의 근거가 틀렸다 — 결론은 아니다**): 08-16이 적은 *"구독에 Function App·
  AKS·Cosmos 전부 없다"*를 재니 FunctionApp **0** · AKS **0**은 맞고 **Cosmos는 1개 있다**
  (`cosmos-roadpilot`). `az cosmosdb list`의 `systemData.createdAt`이 **2026-07-14** —
  그 측정보다 **한 달 먼저**다. ⇒ **stale이 아니라 쓰일 때부터 틀린 기록**(08-15 ⓑ와 같은 모양:
  *"언제부터 있었는지까지 물어야 stale과 오기를 가른다"*). ⚠️그리고 `rg-roadpilot`은 **남의
  프로젝트**다 — 태그·RG를 안 읽으면 남의 자원을 우리 잔재로 설명하게 된다.
- Verified(**그런데 Cosmos는 애초에 러너의 능력 밖이었다**): `azure_runner`가 분기하는 액션은
  **다섯, 리소스 타입 둘**(AKS 3 · FunctionApp 2)이고 그 밖은 `raise ValueError`. **Cosmos 액션은
  하나도 없다.** ⇒ 08-16의 근거는 **세 타입을 손으로 적었는데 하나는 러너가 만질 수 없는 것**이었다
  (Risk 12④ⓐ — 목록이 무엇의 그림자인지부터). **결론은 더 나은 근거로 다시 선다**: 러너가 실제로
  닿는 두 타입이 **둘 다 0** = 배선 시 blast radius **대상 0개**. ⚠️**오늘의 사실이지 불변식은 아니다.**
- Verified(**곁가지 — 선언 16 vs 구현 5는 결함이 아니다**): aws 16/0(러너 없음) · gcp 16/5 ·
  azure 16/5 · onprem 12/4로 **네 provider가 같은 모양**이라 Azure 고유가 아니다. 그리고 **배선된
  쪽의 읽는 지점이 정직하다** — `gcp/executor.py`가 러너의 `ValueError`를 `except`로 받아
  **`success: False`**를 돌린다. 미구현 액션이 "실행됨"으로 보고되지 않는다. ⇒ Azure 배선의
  안전성 논거가 하나 늘었다.
- Changed: 증거 로그에 **§정정** 추가 · `NEXT_PLAN`의 Azure 항목이 이제 **러너 액션에서 유도한
  근거**를 든다. **src 변경 0 · 가드 변경 0**(기존 가드가 목록을 하드코딩하지 않아 손댈 게 없었다).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: **승인 사안 그대로**. 바뀐 건 결론이 아니라 **근거의 질**이다.
- Next: 승인이 오면 Azure 배선(+ **Phase 3② 면제 삭제** — 가드가 red로 요구한다). 무과금 잔여는
  **BQ 결제 내보내기**(콘솔 수동)와 **`make lint` 20건 처리 여부**(신규 결정).

## 2026-08-30 — 같은 함정을 pytest에만 막아 뒀다: ruff는 실행마다 답이 달랐다 (gate 2302)

- Status: 위 증분이 **"미수정, 범위 밖"으로 기록만** 한 항목을 재서 닫았다. 증거
  `docs/evidence/ruff-and-pytest-did-not-exclude-the-same-vendored-trees.log`.
- Verified(**재현 — 같은 명령, 같은 트리, 다른 답**): `ruff check src/ tests/` 10회가
  **20 · 6527 · 20 · 6527 · 6527 · 6527 · 20 · 6527 · 6527 · 20**. 초과분 6,507건이 **전부
  `src/stacks/cdk.out`**(벤더 CDK 자산 4,703 py파일). 캐시를 지우면 첫 실행만 20이고 다시 흔들린다.
- Verified(**원인 = 선언이 아니라 추론**): 두 경로 다 gitignore인데 **pytest만 소리 내어 말했다**
  (`norecursedirs`). `[tool.ruff]`엔 대응 항목이 **없었다**. ⇒ **Risk 12②가 두 번째 도구에서
  재발**(선언되지 않은 것 위에서 통과)이자 **12⑥ 형제 집합의 설정 판** — 같은 함정을 한쪽에만
  막아 뒀다. ⚠️NEXT_PLAN은 **이미 `cdk.out`을 "세는 함정"으로 적어 뒀다**(MCP 항목): 같은
  디렉터리·같은 함정·다른 도구인데 기록이 도구 하나에만 적용돼 있었다.
- Changed: `[tool.ruff] extend-exclude`에 두 경로를 **선언**했다 → 10회 **전부 20**. ⚠️**게이트는
  아니다**(`check: test`) — 나쁜 건 CI가 아니라 `make lint`를 돌린 사람이 실행마다 다른 답을 받고,
  흔들리는 쪽이 **진짜 소견 20건을 벤더 6,507건 밑에 묻었다**는 것이다. **읽을 수 없는 신호는 읽지 않게 된다.**
- Verified(**묻혀 있던 20건 전수 분류 — 결함 0**): F841 8 · E731 5 · E701 5 · F402 1 · E712 1.
  "단언이 빠진 모양"인 **아홉 건을 개별로** 물었다. `azure_runner:275 url`=죽은 변수(분기마다 자기
  URL) · F402=그 함수가 dataclass `field`를 안 씀 · `test_pipeline original_guard`=지역 인스턴스라
  오염 없음 · `test_activity_writer result`=mock의 `put_item`을 단언한다. ⚠️**가장 그럴듯했던 건
  `pipeline.py:218 dep_id`** — `record_deployment()`가 돌려준 id를 버리고 **바로 다음 줄**에서
  ACTIVITY 행을 쓴다(08-18에 "쓸 수 있는데 안 쓴다"로 읽혔던 그 모양). 물어 보니
  **`record_agent_activity`에 `deployment_id` 매개변수가 아예 없다** ⇒ 08-18이 **읽는 쪽**에서
  내린 경계가 **쓰는 쪽에서 독립으로 재확인**됐다. **결함이 아니라 경계다** — 시험은 범위를 줄 때도 값이 있다.
- Changed(**가드 +3**): `test_vendored_paths_are_excluded_from_both_tools.py` — 형제 일치 · 공허
  방지 · **도구에 직접 묻기**(`ruff check --show-settings`). ⚠️**TOML 키는 오타가 나도 파싱된다**:
  `extend_exclude`(밑줄)로 쓰면 ruff가 파일을 받고 키를 **조용히 무시**한다 — 선언을 읽으면 누가
  타이핑했다가, resolved settings를 읽어야 **도구가 동의했다**가 증명된다.
- Verified(**변이 4종 red**): 제외 통째 삭제 · ruff만 한 경로 누락 · **키 오타**(세 번째 방향이
  사는 지점) · **양쪽 다 빈 목록**(형제 일치는 **통과**하고 공허 방지만 red — 그 칸을 메우는 게 요지).
- Verified: `make check` **2302 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13, 38.0s).
- Blockers: 없음. 20건은 **안 고쳤다**(스타일 · 열 파일 · 범위 밖) — 이제 **읽을 수 있으니**
  고칠지는 결정 사안이고, `make lint`를 게이트에 넣으려면 그게 선행이다.
- Next: **Azure executor 디스패치**(승인 사안) — 그 전에 기록된 근거 *"순수 잠재: 구독에 리소스 없음"*(08-16)을 재는 게 값싸다.
