# NEXT_PLAN — platform-agent

최종 갱신: 2026-08-13

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(**M15=공급망 0→집행 + Phase 5 경계 +
> `main` 보호**, M14=결정 6건, M13=미소비 14건) / `PROGRESS_LOG.md`(+`docs/archive/`). **≤120줄**.

## 현재 상태 (2026-08-13, gate 1856 — 로컬 macOS·py3.13)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **잔여 소진**(M13) + **결정 7건 닫힘**(D36·D38~D43).
**공급망은 닫을 수 있는 만큼 닫혔다**(어드미션만 업스트림 대기) · **`main`은 보호된다**
(PR + CI 통과로만 병합, D43) · **Phase 5는 경계까지** 섰고 커밋도 **경로 한정**이다.
**남은 건 Phase 4(billable, 별 승인)뿐** — 단 "무과금 작업 소진"은 **이제 다섯 번 틀렸다**
(08-09 두 번 · 08-10 · 08-11 · 08-12 · **08-13**). 넷이 같은 말을 한다: 목록을 뒤진 게 아니라
**프로브를 한 번 돌리자** 리포터 자신의 결함이 나왔고, **목록의 방향을 뒤집자** 테스트에
이름조차 없던 결함 둘이 나왔고, **직전 세션이 남긴 Next를 그대로 따라가자** 두 provider에
복사된 죽은 티어가 나왔다. **소진은 목록의 상태지 사실이 아니다 — 목록 밖에도 있고, 목록이
무엇의 그림자인지도 물어야 하고, 가장 값싼 다음 수는 대개 직전 세션이 이미 적어 뒀다.**

## 사용자 게이트 — 전부 닫힘 (재개 조건만)

> 결정 1~6 = **D36·D38~D42**, 브랜치 보호 = **D43**. 근거는 `DECISIONS.md`·`docs/plans/*`, 완료
> 요약은 `COMPLETED_SUMMARY` **M14·M15**. **재개 조건만 아래 남긴다.**

- 라우터에 인증이 서면 **결정 5 C**와 **결정 1의 파티션**이 열린다 · k3s-lab에 워크로드가 서면
  **결정 4**(경로=옵션 A) · 두 번째 리뷰어가 생기면 **CODEOWNERS 리뷰 필수**를 켠다(D43).
- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=우리는 **오프라인 Qwen 에이전트로 루프를
  무인으로 닫는다**. 소재=**자동화하면 새로 깨지는 것**: ①롤백↔selfHeal ②자격증명=blast radius
  ③"실행됨≠나아졌음" ④과금 누출 · 소비자 없는 선언 14건(M13) · **수호 테스트 자신이 같은
  안티패턴**(5회+) · **리포트가 독자에게 갈린 채 도착**(M17) · **두 provider에 복사된 죽은
  티어**(08-13). **집필·발행은 착수하지 않는다**(지시 2026-07-25).
- [ ] (선택) **Azure Foundry 정리** — 유휴 ≈$0는 **참**. 단 구독 전체는 아니다: ACR Basic이 월 ~₩6,600 고정이고 **다른 프로젝트 것**(08-12 재확인).

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5) · **MAD**: 같은 폴더 `-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책(soft/vcluster/dedicated),
Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: blast radius=1 tenant/env(자격증명이 경계) — **집행 가능하지만 옵트인**(D38).

- [ ] **Phase 5 = 경계까지 섰다(2026-08-08, → M15)** — UI가 아니라 **"PR은 그 테넌트 파일
  하나만 건드린다"**를 세웠다. **남은 것 = attach UI인데 기록된 이유가 틀렸다(실측)**:
  "Next+FastAPI 두 층"이 아니라 **FastAPI 층이 아예 없다**. 진짜 구속 조건은 **쓰기 대상이
  git 파일**인데 **UI는 Vercel이라 파일시스템·git·python이 없다**는 것 → "실제 PR 생성"은
  별개 잔여가 **아니라 이 항목의 구속 조건**이다. 우회 없음(OAuth `repo`는 blast radius=1과
  충돌 · TS 이식은 **두 번째 진실 공급원**). ⇒ 여는 조건 = **파이썬 플래너를 어디서 돌릴지**.
- [ ] **Phase 4 — 산정 끝, 승인 대기.** 근거는 **`docs/plans/2026-08-08-phase4-scope-and-cost.md`가
  권위**(복제 금지). **비용 40배로 쪼개진다**: **4a** 관리형 어댑터(원격 클러스터 **불요**)
  **≈$5/월** · **4b** 원격 클러스터+DR **≈$185/월**. ⚠️**$0 선행: ₩20 예산은 닫혔고 BQ 결제
  내보내기만 남았다** — 없으면 울려도 금액을 모른다. 절차·확인법은
  **`docs/GCP_BILLING_EXPORT_SETUP.md`**(콘솔 수동, 사용자 몫 · 확인은 `make spend-check`).
  ⚠️4a는 자격증명 파티션 **미증명**(Risk 10=4b) · **30분 TTL 가드**가 상시와 안 맞는다 ·
  Phase 5가 열리면 3②를 GitOps-native로(D32 재검토) · **런북 스토어도 여기서 처음 생긴다**
  (08-13에 티어 1의 계약 필드를 맞춰 뒀다 — 지금은 문서 0개).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 부재).
- **2차 잔여 = 하나**: **스포크의 읽기 신원** — 맨 kubectl로 공유 `argocd` ns를 읽어 테넌트
  구분이 **코드 필터**다(쓰기는 401로 막지만 읽기는 안 막는다). **시끄럽게만** 해 뒀고
  (`warn_if_ambient_read`, M17), seam은 **인클러스터 배포·민팅이 선행**이라 인프라 결정.
  증거 `push-identity-ambient.log`.

## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분은 `COMPLETED_SUMMARY.md` **M12**(Phase 3 인가) · **M13**("선언됐지만 아무도 읽지 않는
> 것들" 14건) · `PROGRESS_LOG.md` · `docs/evidence/`.

- [ ] **`slack_live_approval.py` 이중 노후화 — 고치면 조용히 no-op이라 안 고쳤다(08-11)**
  ①임포트가 **untracked `cdk.out`에만** 있는 경로 ②고쳐도 덮어쓰는 여섯 이름 중 **넷이 부재**
  → **돌아가면서 아무것도 안 한다**. 올바른 이름은 **데모를 Slack에 태워야 확정**된다.
- [ ] **리포트 스트림 남은 경계(M17 · 증거 로그 13절이 권위)** — 파이프 뒤 **13 invocation /
  11 CLI**. 나머지 일곱은 **강제할 실패 경로가 없거나 이미 옳다**. 로깅 문은 **REPORT 4개만**.
- [ ] **런북 walk가 남긴 ②(08-12)** — ①은 **08-13에 닫혔다**(→ `PROGRESS_LOG` 상단). 조건 축은
  `previous_step_failed`만 넓혔고 **`severity`는 `"P2"` 고정**이라 `severity_in` 스텝이 생기면
  같은 함정이 재발한다 — 지금 카탈로그엔 없어 **가드를 안 만들었다**(없는 문제의 가드는
  하중을 못 받는다).
- [ ] **capability 스캔이 남긴 셋(2026-08-13, 증거 7절) — 전부 정책/발명 사안이라 안 고쳤다**
  ⓐ**`kafka-lag-spike`만 두 dict가 어긋난다**: 스텝엔 `rebalance_consumer`가 있는데
  `capabilities`엔 없다(9개 중 이것 하나, **어긋난 쪽이 또 에스컬레이션 스텝**) — 더하면
  매치 면이 넓어지고 빼면 스텝이 준다, **둘 다 동작 변경** · ⓑ**`renew_certificate`가
  GCP/Azure 어댑터에 매핑 없음** → `certificate-expiry`가 선택은 되는데 `actions=[]`
  (**회귀 아님**, 라벨이 정직해져서 **이제 보인다**) · ⓒ**티어 2는 첫 매치가 이긴다**
  (AWS는 점수제) — 테스트가 고정했으니 **우연이 아니라 결정**이다.
- [ ] **`record_route_activity`·`record_agent_activity`의 `cost_metrics` — 의도적으로 남김**.
  둘 다 `deployment_id`가 없어 그 필드를 렌더하는 유일한 뷰에 닿지 않아 **소비자 없는 필드**가
  된다(`activity-model.ts`가 `deployment_id`로 접는다 — 2026-08-08 재확인).
- [ ] **GCP/Azure 90일 보관** — **`STATUS` Risk 2가 권위**. 스토어가 없어 **지울 데이터 0** →
  Phase 4. 코드 갭은 유효.
- [ ] **GCP/Azure 기록기의 `resolved_at`·`triggered_at`은 읽는 쪽이 없다** → Phase 4. **analyzer
  LLM 폴백도 일괄 P2** — severity 매핑은 **정책 결정**이라 발명 안 함.
- [ ] **k3s 승격은 닫혔다(D40) — 여는 조건은 "k3s-lab에 워크로드"** — 집행은 증명(07-29),
  시맨틱은 미증명이고 **못 증명하는 이유가 기록과 달랐다**(→ `STATUS` Risk 5). 경로는 **옵션 A**
  (네임스페이스·netpol만, 비용 0) — ⚠️**실체 없는 선언 2건**을 더하므로 그때 재평가.
- [ ] **스코프·배포 신원은 옵트인이다(D38 이후)** — 상태는 `probe_scope_reachability.py`·
  `make deploy-identity-check`가 답한다. **남은 결정**: 기본 on 여부(데모/로컬을 깨는 대가) ·
  **서명키 custody·rotation** · 배포 신원의 테넌트 구분(결정 5 C/D).
- [ ] **MCP 게이트웨이는 여전히 포트에 붙어 있지 않다** — 결론 유지, **근거는 틀렸다(재측정)**:
  `bridge.py:35`에 폴백이 있고 그 `McpA2aBridge`를 만드는 건 **테스트뿐**. ⚠️**세는 함정 둘** —
  `cdk.out`은 untracked인데 파일 grep엔 잡힌다(→ **`git grep`**) · **docstring 예시**가 호출로 보인다.
- [ ] **A2A 인증 실집행 결정** — 남은 건 **기본값 on 여부**(라이브 kagent 왕복이 익명이라
  opt-in — 그 "익명"은 **나가는 쪽**이다, D39).
- [ ] **Cosign 어드미션 = 업스트림 대기** — **`STATUS` Risk 6이 권위**. **재개 조건**: cosign v3
  ↔ policy-controller 저장 위치가 업스트림에서 맞춰지는 것.

## 유지 규약 (완료된 리팩토링에서 나온 "하지 말 것")

`_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이) · detector/analyzer/decision은
SDK가 90%+ 상이해 **의도적으로 DRY 안 함** · `approval_bridge` 추가 분해 금지(D15) · 포괄
`gcloud:*`류 allow를 되살리지 않는다(D16 우회 재발 → D22).
⚠️**"DRY 안 함"이 덮지 않는 것(08-13)**: 공유되는 게 **SDK가 아니라 계약**인 블록이 있다 —
GCP/Azure 결정 티어 2는 **같은 12줄**이었고 **양쪽 다 죽어 있었다**. 그런 블록은 **provider
간 일치를 묻는 가드**로 묶을 것(`test_capability_catalog_scan.py`).

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지 · 정적 무조건 fan-out · 자유텍스트 spawn_subagent 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고 · 묶음 완료 시 `/checkpoint`.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
