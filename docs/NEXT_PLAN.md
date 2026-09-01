# NEXT_PLAN — platform-agent

최종 갱신: 2026-09-01

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(**M15=공급망 0→집행 + Phase 5 경계 +
> `main` 보호**, M14=결정 6건, M13=미소비 14건) / `PROGRESS_LOG.md`(+`docs/archive/`). **≤120줄**.

## 현재 상태 (2026-09-01, gate 2368 — 로컬 macOS·py3.13 · CI도 같은 게이트, ubuntu·py3.13)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **잔여 소진**(M13) + **결정 7건 닫힘**(D36·D38~D43).
**공급망은 닫을 수 있는 만큼 닫혔다**(어드미션만 업스트림 대기) · **`main`은 보호된다**
(PR + CI 통과로만 병합, D43) · **Phase 5는 경계까지** 섰고 커밋도 **경로 한정**이다.
**남은 건 Phase 4(billable)뿐** — 단 "무과금 소진"은 **여섯 번 틀렸다**. **소진은 목록의 상태지
사실이 아니다** — 목록 밖에도 있고 **가장 값싼 다음 수는 대개 직전 세션이 적어 뒀다**.
⚠️**목록에 적힌 항목 자체가 틀릴 수도 있고**(M19 ⓑ) **그래도 시험하면 값이 난다**(`git log -L`로
**"언제부터"**까지) · **직전 고침이 남긴 기준이 다음 결함을 찾는다**(M19→M26, 여섯 층 연속).

## 사용자 게이트 — 전부 닫힘 (재개 조건만)

> 결정 1~6 = **D36·D38~D42**, 브랜치 보호 = **D43**. 근거는 `DECISIONS.md`·`docs/plans/*`, 완료
> 요약은 `COMPLETED_SUMMARY` **M14·M15**. **재개 조건만 아래 남긴다.**

- 라우터에 인증이 서면 **결정 5 C**와 **결정 1의 파티션**이 열린다 · k3s-lab에 워크로드가 서면
  **결정 4**(경로=옵션 A) · 두 번째 리뷰어가 생기면 **CODEOWNERS 리뷰 필수**를 켠다(D43).
- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=오프라인 Qwen로 루프를 무인으로 닫는다. 소재=**자동화하면 새로 깨지는 것**(①롤백↔selfHeal ②자격증명=blast radius ③**"실행됨≠나아졌음"** ④과금 누출) · 미소비 선언 14건(M13) · **수호 테스트 자신이 같은 안티패턴**(M17~M20·M27이 사례집).
  ⚠️③의 **산 사례가 완결됐다**: Azure는 실행조차 안 하고 해결됨을 보고**했고**(08-16 발견) 08-30에 배선했다 — **발견·승인·고침·그로 인해 게이트 숫자가 내려간 것까지** 한 벌(M39). **집필·발행은 착수하지 않는다**(지시 2026-07-25).
- [ ] (선택) **Azure Foundry 정리** — 유휴 ≈$0는 **참**. 단 ACR Basic이 월 ~₩6,600 고정이고 **다른 프로젝트 것**(08-12).

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5) · **MAD**: 같은 폴더 `-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책, Env=cluster(멀티클라우드),
Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리. **최우선 불변식**:
blast radius=1 tenant/env(자격증명이 경계) — **집행 가능하지만 옵트인**(D38).

- [ ] **Phase 5 = 경계까지 섰다(2026-08-08, → M15)** — UI가 아니라 **"PR은 그 테넌트 파일 하나만 건드린다"**를
  세웠다. **남은 것 = attach UI인데 기록된 이유가 틀렸다(실측)**: 진짜 구속 조건은 **쓰기 대상이 git 파일**인데
  **UI는 Vercel이라 파일시스템·git·python이 없다**(FastAPI 층은 **아예 없다**) → "실제 PR 생성"은 별개 잔여가
  아니라 **이 항목의 구속 조건**. 우회 없음(OAuth `repo`는 blast radius=1과 충돌 · TS 이식은 **두 번째 진실
  공급원**). ⇒ 여는 조건 = **파이썬 플래너를 어디서 돌릴지**.
- ⛔**Phase 4 / 4a는 닫혔고(08-30, M38) 접혔다(2026-09-01, 사용자 결정 — M40 · 계획서 §11 · D50 Folded).** 실제 청구 **$0.00**(프리티어 `Always Free` 40M). 워크스페이스 `ws-929b8da9…`·IAM 사용자·키 **셋 다 삭제**, 8리전 스윕 0으로 확인. ⚠️**$0.00이 접은 이유가 아니다** — 대가는 **장기 키**였고 D50이 미리 그렇게 적어 뒀다. ⚠️**D48은 안 죽었다**(허용목록 없이 remote_write 금지): 필터 없음 **128배 초과**는 그대로라 `test_amp_cost_handles`를 **지우지 않고** 계약을 함수로 빼 **합성 표**에 물렸다(+7, 변이 7 red). ⚠️**`AccessDenied`를 부재의 증거로 읽지 말 것** — 증거는 **소유 사용자의 부재**다. **다시 열지 말 것.** ⚠️**남은 손질**: kind를 다음에 띄우면 고아가 될 `monitoring/amp-remote-write` Secret 삭제.
- [ ] **Phase 4 남은 것 = 4b**(자격증명 파티션 미증명=Risk 10 · 30분 TTL 가드가 상시와 안 맞는다, billable·별 승인) ·
  ⚠️**$0 선행: BQ 결제 내보내기**(`GCP_BILLING_EXPORT_SETUP.md`, 콘솔 수동 · `make spend-check`).
- ⛔**대시보드 취약점은 닫혔다(08-30) — `npm audit` 0건**(Tier A + `next 16.3.3`; 라우트 17개 동일·eslint 새 소견 0).
  **`STATUS` Risk 11이 권위** — ⚠️거기 적힌 "기록이 세 군데 다 틀렸다"를 지우지 말 것. **다시 열지 말 것.**
⛔**`onprem` extra의 `mlx-lm`은 닫혔다(2026-09-01) — `COMPLETED_SUMMARY` M41이 권위.** 뺐고, `gate.yml`이 이제 `.[onprem]`을 깐다 ⇒ **인라인 패키지 0개**. ⚠️**기록된 근거는 적을 당시 참**이었다(하한 `0.19.0`은 마커가 없어 리눅스 resolve가 진짜 실패) — **stale이 아니라 더 나빠졌다**: 리졸버가 고르는 0.31.3은 마커가 붙어 **설치되고 엔진만 조용히 빠진다**. ⚠️**"안 쓰이니 지운다"가 아니다** — `.venv-mlx` 분리는 **설계**(활성화되면 pytest를 가린다)라 extra가 mlx를 프로젝트 env로 들이는 건 그 분리를 뒤집는다. **다시 열지 말 것.**
- [ ] **정적검사를 게이트에 넣을지 — 사용자/레포 결정.** ✅**선행 둘 다 이제 재기 좋다(09-01, M42)**: `make lint` **20건**(F841 8·E731 5·E701 5·F402 1·E712 1 · src 7·tests 13, 전수 분류 **결함 0**) · mypy **253 errors in 88 files (166 checked)**. ⚠️**그 253은 09-01 전엔 그냥 안 나왔다** — `[tool.mypy]`에 vendored 제외가 없어 `mypy src/`가 **수집 단계에 죽었다**(셋째 형제, 고쳤다). `gate.yml`이 *"a CI job is a bad place to introduce a standard nobody agreed to"*라 적어 뒀다 — **묻기 좋게 만들어 뒀지 대신 정하지 않았다.** 증거 `the-third-sibling-was-mypy.log`. ⚠️**결정에 줄 표본이 하나 생겼다(09-01, M44)**: mypy 253의 **200은 주석 부채**(`type-arg`·`import-untyped`·`no-any-return`·`no-untyped-def`·`no-untyped-call`)이고 **53이 실제 주장**인데, 그중 하나가 **테스트가 한 번도 언급 안 한 계약 갭**을 짚었다. ⛔**이건 "켜라"가 아니라 "이 도구가 여기서 무엇을 찾는가"의 표본이다.** ✅**표본이 커졌다(M45)**: 실제 주장 53 중 **21건을 열어 고칠 값이 있던 건 2건**(M44 계약 갭 + M45 선언 불일치), 나머지 19는 노이즈이거나 *"코드는 옳고 타입이 못 따라간다"*(오탐 4 · 도달 불가 2 · 재-export 3 · 이종 dict 2 · 이름 재선언 1 · 미설치 2). **이제 숫자를 갖고 물을 수 있다.**
- ⛔**Azure executor는 배선됐다(08-30, 승인 후) — `COMPLETED_SUMMARY` M39가 권위. 다시 열지 말 것.**
  ⚠️**"이제 Azure는 안전하다"로 요약 금지**: 열린 건 **경로**고, 오늘 blast radius가 0인 건 러너가
  만지는 **AKS·FunctionApp이 구독에 0개**여서다(**오늘의 사실이지 불변식이 아니다**). 자격증명
  테넌트 바인딩은 그대로 **Phase 4**(Risk 10). ⚠️게이트 숫자가 **2337→2332로 내려갔고 그게 옳다**(같은 항목).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 선행**(kind엔 CSI 스냅샷터 부재).
- **2차 잔여 = 하나**: **스포크의 읽기 신원** — 공유 `argocd` ns를 맨 kubectl로 읽어 테넌트 구분이 **코드 필터**다(쓰기는 401, 읽기는 안 막는다).
  **시끄럽게만** 해 뒀고(`warn_if_ambient_read`, M17), seam은 **인클러스터 배포·민팅 선행**이라 인프라 결정.

## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분은 `COMPLETED_SUMMARY.md` **M12**·**M13** · `PROGRESS_LOG.md` · `docs/evidence/`.

- [ ] **DUAL 모드 조건부 리다이렉트** — `slack_live_approval`은 닫혔고(08-16) 이것만 남았다. **하중을 못 받는 가드**가 되므로 안 만들었다.
- ⛔**capability 스캔은 셋 다 닫혔다(08-17)** — ⓐ**현행 유지**(M35: 티어 2는 액션을 `recommended_capabilities`에서 만들고 `capabilities`는 매치 게이트일 뿐 — 더해도 관측 변화 0, **빼면 네 provider가 다 resolve하는 스텝을 잃는다**) · ⓒ**측정하고 고쳤다**(M36+M37: 기존 가드가 **생산에서 도달 불가한 capability 집합**으로 물어 첫-매치와 점수제의 답이 같은 경우만 태웠다 → 점수 함수를 계약 모듈에 한 벌 두고 셋이 읽는다) · `rollback_release`**는 추천 목록 현행 유지**(진짜 문제는 목록이 아니라 **티어 2가 조건 평가 없이 추천에서 액션을 만든 것**이었고 그걸 고쳤다; `JUSTIFIED_GAPS`가 들고 어긋나면 red). **다시 열지 말 것.**
- [ ] ⚠️**Phase 3② — GCP(08-18)·Azure(08-30) 배선. 남은 건 AWS뿐이고 그건 "러너가 없다"이다.** `guard_rollback`을 부르는 러너가 **onprem 하나**였는데 `ROLLBACK_ACTIONS`는 **네 provider 7종을 다 알았다** — M31이 고친 건 **목록**이고 **호출 지점을 세는 가드가 없었다**(M18이 한 층 위에서 재발: 세는 대상이 액션이 아니라 **러너**). ✅**GCP 배선**: 롤백 walk가 이미 GET하던 매니페스트를 그대로 `guard_rollback`에 넘긴다 — **추가 API 호출 0**, patch 앞에서 거부. ✅**Azure 배선(08-30)**: 면제가 *"고치면 이 항목은 지워야 한다"*고 자기 만료 조건을 적어 뒀고 **가드가 실제로 그걸 집행했다** — `JUSTIFIED_GAPS`는 **비었다**(⚠️그래서 두 면제 규칙이 **하중을 잃어** 합성 표에 대고 다시 물었다). AKS 롤백도 GCP처럼 **patch 직전 GET이 이미 있어 추가 호출 0** · **AWS는 러너가 없다**(SSM Automation 경로, 가드가 그 사실을 박아 뒀다). ⚠️**가드 자신이 한 번 틀렸다**: 문자열 검사라 **호출을 지워도 import 줄이 남아 통과**했다 → **AST로 실제 호출**을 센다. 증거 `docs/evidence/phase-dod-verification-2026-08-18.log`.
- ⛔**`cost_metrics`는 측정으로 닫혔다(08-18)** — 기록된 이유가 **맞다**: cost를 렌더하는 뷰는 **한 곳뿐**이고(`deployments/[id]`) 그걸 먹이는 `mergeActivity`가 `deployment_id === id`로 거른다. route/provider-activity 행은 그 키가 없어 **원리상 못 닿는다**(더하면 안 읽히는 필드가 하나 더 는다). ⚠️**면제는 목록이 아니라 경계다** — 가드가 의무를 **읽는 쪽 선택 규칙에서 유도**하고 `src/agents` **전 모듈**을 rglob으로 훑는다(ACTIVITY writer 넷 중 **하나는 `activity_writer.py`**). 변이 3종 red(롤백 필드 제거 · route에 `deployment_id` 부여 · 스윕 무력화). 증거 `docs/evidence/cost-metrics-exemption-is-derived-and-load-bearing.log`. **다시 열지 말 것.**
- [ ] **⚠️`msft_deployer`가 진짜 라이브러리에서 깨진다(08-30 재측정)** — ✅설치 조건은 열렸다(`.[azure]`가 **31.5초에 성공**, 08-15엔 150초 타임아웃 · agent-framework **1.16.0**). ⛔그런데 `AzureOpenAIResponsesClient`은 **버전 지연이 아니다**: `agent_framework*`에 `AzureOpenAI*Client`가 **0개**고 그 이름은 **업스트림 docstring 한 줄**에만 있다. **여전히 안 고친다 — 대체 심볼이 없어 추측은 발명.** ⚠️테스트가 `sys.modules`를 스텁해 초록이다. 증거 `the-azure-extra-cannot-be-installed.log`.
- [ ] **GCP/Azure 90일 보관** — **`STATUS` Risk 2가 권위**(스토어가 없어 지울 데이터 0 → Phase 4).
  ⚠️"`resolved_at`은 읽는 쪽이 없다"는 **틀렸다**(08-16 재측정): `oncall_reporter._minutes_between`이
  `started_at`과 짝지어 읽고 `aws/reporting.py:239`가 넘긴다 · **analyzer 폴백 severity는 정책**.
- [ ] **k3s 승격은 닫혔다(D40) — 여는 조건 "k3s-lab에 워크로드"** — **`STATUS` Risk 5**가 권위.
  경로는 **옵션 A**(네임스페이스·netpol만, 비용 0) — ⚠️**실체 없는 선언 2건**을 더하므로 재평가.
- [ ] **스코프·배포 신원은 옵트인(D38 이후)** — 상태는 `probe_scope_reachability.py`·`make
  deploy-identity-check`가 답한다. **남은 결정**: 기본 on 여부 · 서명키 custody·rotation ·
  배포 신원의 테넌트 구분(결정 5 C/D).
- [ ] **MCP 게이트웨이는 포트에 안 붙어 있다** — 결론 유지, **근거는 틀렸다(재측정)**: `bridge.py:35`에 폴백이 있고 그 `McpA2aBridge`를 만드는 건 **테스트뿐**. ⚠️**세는 함정 셋**: `cdk.out`(→**`git grep`**) · **docstring 예시**가 호출로 보인다 · ⚠️**`git grep -E`의 `\s`는 조용히 0건**(POSIX ERE엔 없다 → `[[:space:]]`/`-P`) — 08-30에 그걸로 "신뢰도 임계값이 없다"는 **거짓 소견을 낼 뻔했다**. ⚠️**넷째·다섯째**: **리전 한정 조회의 `[]`를 "없다"로 읽지 말 것**(08-30: `us-east-1`이 `[]`인데 워크스페이스는 `ap-northeast-2`에 살아 있었다) · **`AccessDenied`도 부재의 증거가 아니다**(09-01).
- [ ] **A2A 인증 실집행 결정** — 남은 건 **기본값 on 여부**(라이브 kagent 왕복이 익명이라
  opt-in — 그 "익명"은 **나가는 쪽**이다, D39).
- [ ] **Cosign 어드미션 = 업스트림 대기** — **`STATUS` Risk 6이 권위**. ⛔**08-30 확인: 아직**(`policy-controller#1406` open · v3.1.2 `sign`/`attest`에 `--new-bundle-format` 없음) — **이 날짜부터 볼 것.**

## 유지 규약 (완료된 리팩토링에서 나온 "하지 말 것")

`_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이) · detector/analyzer/decision은
SDK가 90%+ 상이해 **의도적으로 DRY 안 함**(⚠️**08-30 실측 — 결정 유지, 근거는 정확히**: SDK 접촉은 **3~5%**뿐이고
`detector`는 동일 블록 **0줄**로 규약대로지만 `analyzer` **51%**·`decision` **56%**가 **글자 그대로 두 벌** = **계약**.
추출은 승인 사안이라 안 했고 바이트 동일 **7쌍을 `test_cross_provider_contract_parity.py`가 표로 박았다**.
증거 `the-dry-exemption-was-right-about-detector-and-quiet-about-two.log`) · `approval_bridge` 추가 분해 금지(D15) · 포괄 `gcloud:*`류 allow 금지(D16→D22).
⚠️**"DRY 안 함"이 덮지 않는 것(M18·M19)**: 공유되는 게 **SDK가 아니라 계약**인 블록은 **계약
모듈에 한 벌만** 두고(`runbooks/schema.py::fits_resource`를 세 provider가 읽는다) **provider 간
일치를 묻는 가드**로 묶는다(`test_capability_catalog_scan.py`) — 복사본 둘은 다음 고침이 한쪽에만
닿는 방식이다. 같은 이유로 **의무가 분류마다 뒤집히는 규칙은 양쪽을 다 물을 것**
(`test_report_streams.py`의 REPORT↔DOCUMENT).
⚠️**"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다(M19)** — `provider`는 **AWS 포함 아무도 안
읽는데** 빌트인 9개가 **전부 `"aws"`**라, 읽으면 GCP/Azure는 **전부 폴백으로 떨어진다**(=#30
이전). **기준은 읽는 쪽의 provider 간 비대칭**이다 — 그 기준으로 `NormalizedIncident`를 훑어
M20이 나왔다. ⚠️**가드의 임포트를 그 파일이 주장하는 범위와 맞댈 것** · **형제는 provider가 아닐 수도**(M21: 같은 provider의 **진입점** 둘) · **다수가 옳고 하나가 뒤처질 수도**(M23: `Destroy`가 AWS에만 없었다).
⛔`triggered_at`·`metric_name`은 **닫혔다**(M21 §8) — 다시 열지 말 것.

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지 · 정적 무조건 fan-out · 자유텍스트 spawn_subagent 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고 · 묶음 완료 시 `/checkpoint`.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
