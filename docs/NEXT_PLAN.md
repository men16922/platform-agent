# NEXT_PLAN — platform-agent

최종 갱신: 2026-08-10

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(**M15=공급망 0→집행 + Phase 5 경계 +
> `main` 보호**, M14=결정 6건, M13=미소비 14건) / `PROGRESS_LOG.md`(+`docs/archive/`). **≤120줄**.

## 현재 상태 (2026-08-10, gate 1743 — 로컬 macOS·py3.13 ↔ CI 일치)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **잔여 소진**(M13) + **결정 7건 닫힘**(D36·D38~D43).
**공급망은 닫을 수 있는 만큼 닫혔다**: 서명 생산자 → 배포 직전 소비자 → CI + 키리스(custody 해소).
**어드미션만 남았고 그건 업스트림 대기**다(cosign v3 서명을 policy-controller가 못 읽는다).
**`main`은 보호된다** — PR + CI 통과로만 병합(D43), 그 CI는 이제 **terraform 검증까지 실제로
돌린다**(그 전엔 조용히 skip → Risk 12②). **Phase 5는 경계까지** 섰고 커밋도 **경로 한정**이다.
**남은 건 Phase 4(billable, 별 승인)뿐** — 단 "무과금 작업 소진"은 **이제 세 번 틀렸다**
(08-09 두 번, **08-10 한 번** — 이번엔 목록을 뒤진 게 아니라 **프로브를 그냥 한 번 돌리자**
리포터 자신의 결함이 나왔다). **소진은 목록의 상태지 사실이 아니다 — 그리고 목록 밖에도 있다.**
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.

## 사용자 게이트 — 전부 닫힘 (재개 조건만)

> 결정 1~6 = **D36·D38~D42**, 브랜치 보호 = **D43**. 근거·증거는 `DECISIONS.md`와 각
> `docs/plans/*`. 완료 요약은 `COMPLETED_SUMMARY` **M14·M15**. **재개 조건만 아래 남긴다.**

- 라우터에 인증이 서면 **결정 5 C**(요청이 테넌트를 선언)와 **결정 1의 파티션**이 열린다.
- k3s-lab에 실제 워크로드가 서면 **결정 4**가 열린다(경로=조사 문서 옵션 A).
- 두 번째 리뷰어가 생기면 **CODEOWNERS 리뷰 필수**를 켠다(D43).

- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=책은 AI 자리에 사람이 프롬프트를 넣지만
  우리는 **오프라인 Qwen 에이전트로 루프를 무인으로 닫는다**. 소재=**자동화하면 새로 깨지는 것**:
  ①롤백↔selfHeal 충돌 ②자격증명=blast radius ③"실행됨≠나아졌음" ④권한 게이트 부재의 과금 누출 ·
  **새 소재**: 소비자 없는 선언 14건(M13, 테스트는 내내 초록) · **수호 테스트 자신이 같은
  안티패턴**(4회) · **생산자가 테스트뿐인 메커니즘**(결정 5).
  **집필·발행은 이 계획에만 남기고 착수하지 않는다**(지시 2026-07-25).
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0는 **참**(08-09 실측: 8월 MTD ₩0 · 7월 ₩17,950은 실사용). 단 구독 전체는 ≈$0이 **아니다** — ACR Basic이 월 ~₩6,600 고정으로 돌고, 그건 **다른 프로젝트 것**이다.

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5) · **MAD**: 같은 폴더 `-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책(soft/vcluster/dedicated),
Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: blast radius=1 tenant/env(자격증명이 경계) — **집행 가능하지만 옵트인**
(2026-07-31, D38: 생산자·축소 신원 둘 다 섰고 켜는 건 `make scope-credentials`·`make
deploy-identity`. 미설정이면 예전처럼 인시던트는 거부, 배포는 ambient).

- [ ] **Phase 5 = 경계까지 섰다(2026-08-08)** — UI가 아니라 **"PR은 그 테넌트 파일 하나만
  건드린다"**를 세웠다(→ M15). `registry_write`(+`commit_attachment`, 경로 한정 커밋) +
  `scripts/attach_addon.py`(`--write`/`--commit`) + `.github/CODEOWNERS`.
  **남은 것 = attach UI인데 기록된 이유가 틀렸다(2026-08-08 실측)**: "Next+FastAPI 두 층"이
  아니라 **FastAPI 층이 아예 없다**(Next→OIDC→DynamoDB 직결). 진짜 구속 조건은 **쓰기 대상이
  git 파일**인데(`platform/tenants/*.yaml`, 로컬 `_REPO_ROOT`) **UI는 Vercel이라 파일시스템·
  git·python이 없다**는 것 → "실제 PR 생성"은 별개 잔여가 **아니라 이 항목의 구속 조건**이다.
  우회 없음: OAuth scope는 `read:org user:email`이고 `repo`로 넓히면 **닿는 모든 레포에 쓰기**
  = blast radius=1과 충돌 · 플래너 TS 이식은 **431aeab가 지운 두 번째 진실 공급원**의 재도입.
  ⇒ 여는 조건 = **파이썬 플래너를 어디서 돌릴지**(새 배포 대상 = 비용·승인 사안).
- [ ] **Phase 4 — 산정 끝, 승인 대기.** 근거는 **`docs/plans/2026-08-08-phase4-scope-and-cost.md`가
  권위**(복제 금지). **비용 40배로 쪼개진다**: **4a** 관리형 어댑터(원격 클러스터 **불요**)
  **≈$5/월** · **4b** 원격 클러스터+DR **≈$185/월**. ⚠️**$0 선행: ₩20 예산은 닫혔고 BQ 결제
  내보내기만 남았다** — 없으면 울려도 금액을 모른다. 절차·확인법은
  **`docs/GCP_BILLING_EXPORT_SETUP.md`**(콘솔 수동, 사용자 몫 · 확인은 `make spend-check`).
  ⚠️4a는 자격증명 파티션 **미증명**(Risk 10=4b) · **30분 TTL 가드**가 상시와 안 맞는다 · Phase 5가 열리면 3②를 GitOps-native로(D32 재검토).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 부재).
- **2차 잔여 = 하나 남았다**: **스포크의 읽기 신원** — `_kubectl`이 맨 kubectl이고 공유 `argocd`
  ns를 읽어 테넌트 구분이 **코드 필터**다(쓰기는 허브가 401로 막지만 읽기는 아무것도 안 막는다).
  지금은 **시끄럽게만** 해 뒀고(`warn_if_ambient_read`), seam은 **인클러스터 배포·민팅 경로가
  선행**이라 인프라 결정이다. 증거 `push-identity-ambient.log`. (나머지 2차 잔여는 닫힘 → M15.)

## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분은 `COMPLETED_SUMMARY.md` **M12**(Phase 3 인가) · **M13**("선언됐지만 아무도 읽지
> 않는 것들" 14건 — 배포 tier 발명·네임스페이스 출처 포함) · `PROGRESS_LOG.md` · `docs/evidence/`.

- [ ] **측정 자체의 값을 안 적었다(2026-08-10 실측)** — Cost Explorer는 **요청당 $0.01**
  (MTD $0.27), `spend-watch` 하루 한 번 = 월 ~$0.30. **"read-only"는 "공짜"가 아니다** →
  프로브 docstring에 명시할지. ⚠️**CE는 당일치를 늦게 보고한다** — 오늘 줄의 0은 잰 0이 아니다.
- [ ] **`capsys` 계열 가드의 맹점은 한 건만 봤다(Risk 12④)** — 비용 프로브에서 실제로
  터졌고 고쳤지만 나머지 `readouterr` 사용처는 **안 봤다**. 판정 기준 = "이 가드는 독자가
  읽는 그 물건에 대고 묻는가".
- [ ] **`record_route_activity`·`record_agent_activity`의 `cost_metrics` — 의도적으로 남김**.
  둘 다 `deployment_id`가 없어 그 필드를 렌더하는 유일한 뷰에 닿지 않아 **소비자 없는 필드**가
  된다(`activity-model.ts`가 `deployment_id`로 접는다 — 2026-08-08 재확인).
- [ ] **GCP/Azure 90일 보관 = 승인 항목이 아니었다(2026-08-08 측정)** — 상세·증거는
  **`STATUS` Risk 2가 권위**. 요약: 스토어가 아예 없어 **지울 데이터 0**이고, 보관하려면
  **먼저 프로비저닝**(billable) → Phase 4. 코드 갭은 유효.
- [ ] **GCP/Azure 기록기는 `resolved_at`·`triggered_at`을 안 쓴다** — 읽는 쪽이 없다 → Phase 4.
- [ ] **analyzer LLM 실패 폴백이 여전히 일괄 P2** — `severity_hint`를 안 본다. severity 매핑 확정이 선행이고 그건 **정책 결정**이라 발명하지 않았다.
- [ ] **k3s 승격은 닫혔다(D40) — 다시 열리는 조건은 "k3s-lab에 워크로드가 서는 것"** — 집행은
  증명(07-29), 시맨틱은 미증명이고 **못 증명하는 이유가 기록과 달랐다**(4건 → `STATUS` Risk 5).
  열 때의 경로는 조사 문서 **옵션 A**(프로브 후보-기판 플래그 + 네임스페이스·netpol만 적용,
  Helm·Capsule 불필요, 되돌리기=`kubectl delete ns`, 클라우드 비용 0). ⚠️ 옵션 A는 레지스트리에
  **실체 없는 선언 2건**을 추가하는 대가가 있다 — 그때 재평가할 것.
- [ ] **스코프·배포 신원은 옵트인이다(2026-07-31, D38 이후 남은 것)** — 켜는 건 `make
  scope-credentials`·`make deploy-identity` 두 줄인데 **기본값은 미설정**이라 그 전까지 인시던트
  경로는 전부 거부하고 배포는 ambient로 돈다. 어느 상태인지는
  `scripts/probe_scope_reachability.py`·`make deploy-identity-check`가 답한다. **남은 결정**:
  기본을 on으로 돌릴지(= 데모/로컬 흐름을 깨는 대가) · **서명키 custody·rotation**(2차 잔여) ·
  배포 신원의 테넌트 구분(= 결정 5 C/D, 라우터 인증 선행).
- [ ] **MCP 게이트웨이는 여전히 포트에 붙어 있지 않다** — 결론은 유지, **근거는 틀렸다
  (2026-08-08 재측정)**: "`src/`에 `MCPServer` 생성자 0"이 아니라 `bridge.py:35`에 기본값
  폴백으로 하나 있고, 그 `McpA2aBridge`를 만드는 건 **테스트뿐**이다. ⚠️**세는 함정 둘** —
  `src/stacks/cdk.out`은 untracked인데 파일 grep엔 잡힌다(→ **`git grep`**) · **docstring
  사용 예시**가 호출로 보인다(`mcp_server.py:10`·`bridge.py:10`, D39가 이미 밟았다).
  MCP-over-HTTP를 붙일 땐 **요청 경로가 스코프를 공급하는지** 확인할 것 — D39가 닫은 건
  무스코프 읽기일 뿐 **"스코프가 강제된다"는 아니다**(가드가 그 트랩을 든다).
- [ ] **A2A 인증 실집행 결정** — bearer/JWT 미검사는 해소됐고 남은 건 **기본값 on 여부**
  (라이브 kagent 왕복이 익명이라 opt-in — 그 "익명"은 **나가는 쪽**이다, D39).
- [ ] **Cosign 어드미션 = 업스트림 대기(2026-08-08 실측)** — 원인·증거·과대해석 금지 항목은
  **`STATUS` Risk 6이 권위**다(여기 복제하지 말 것). 요약: 켤 수 없다 — cosign v3의 서명 저장
  위치를 policy-controller가 못 읽고, v2로 되돌려야 하는데 **CI 키리스가 v3 경로**다.
  **재개 조건**: 둘 중 하나가 업스트림에서 맞춰지는 것.

## 유지 규약 (완료된 리팩토링에서 나온 "하지 말 것")

`_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이). detector/analyzer/decision은 SDK가 90%+
상이해 **의도적으로 DRY 안 함**. `approval_bridge` 추가 분해도 하지 않는다(→ D15). 포괄 `gcloud:*`류 권한
allow를 되살리지 않는다(D16 우회 재발) → D22.

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 재평가 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴 메모(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지(계약/방법론만); 정적 무조건 fan-out은 self-consistency 라우팅 회귀라 금지; 자유텍스트 spawn_subagent 핵 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
