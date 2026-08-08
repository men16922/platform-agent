# NEXT_PLAN — platform-agent

최종 갱신: 2026-08-08

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(**M15=공급망 0→집행 + Phase 5 경계 +
> `main` 보호**, M14=결정 6건, M13=미소비 14건) / `PROGRESS_LOG.md`(+`docs/archive/`). **≤120줄**.

## 현재 상태 (2026-08-08, gate 1668)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **잔여 소진**(M13) + **결정 7건 닫힘**(D36·D38~D43).
**공급망은 닫을 수 있는 만큼 닫혔다**: 서명 생산자 → 배포 직전 소비자 → CI + 키리스(custody 해소).
**어드미션만 남았고 그건 업스트림 대기**다(cosign v3 서명을 policy-controller가 못 읽는다).
**`main`은 보호된다** — PR + CI 통과로만 병합(D43). **Phase 5는 경계까지** 섰다.
**남은 건 Phase 4(billable, 별 승인)뿐**이고, 무과금·무승인으로 열린 작업은 소진됐다.
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.

## 사용자 게이트 — 전부 닫힘 (재개 조건만)

> 결정 1~6 = **D36·D38~D42**, 브랜치 보호 = **D43**. 근거·증거는 `DECISIONS.md`와 각
> `docs/plans/*`. 완료 요약은 `COMPLETED_SUMMARY` **M14·M15**. **재개 조건만 아래 남긴다.**

- 라우터에 인증이 서면 **결정 5 C**(요청이 테넌트를 선언)와 **결정 1의 파티션**이 열린다.
- k3s-lab에 실제 워크로드가 서면 **결정 4**가 열린다(경로=조사 문서 옵션 A).
- 두 번째 리뷰어가 생기면 **CODEOWNERS 리뷰 필수**를 켠다(D43).

- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=책은 AI 자리에 사람이 프롬프트를 넣지만
  우리는 **오프라인 Qwen 에이전트로 루프를 무인으로 닫는다**. 소재는 **자동화하면 새로 깨지는 것**:
  ①롤백↔selfHeal 충돌 ②자격증명=blast radius ③"실행됨≠나아졌음" ④권한 게이트 부재의 과금 누출.
  **새 소재**: "선언은 됐는데 아무도 소비하지 않는 코드" 14건(M13) — 전부 테스트는 초록이었고
  라이브만 드러냈다. **수호 테스트 자신이 같은 안티패턴**이던 것(4회) + **생산자가 테스트뿐인
  메커니즘**(결정 5)까지. **집필·발행은 이 계획에만 남기고 착수하지 않는다**(지시 2026-07-25).
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0라 유지 중.

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5) · **MAD**: 같은 폴더 `-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책(soft/vcluster/dedicated),
Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: blast radius=1 tenant/env(자격증명이 경계) — **집행 가능하지만 옵트인**
(2026-07-31, D38: 생산자·축소 신원 둘 다 섰고 켜는 건 `make scope-credentials`·`make
deploy-identity`. 미설정이면 예전처럼 인시던트는 거부, 배포는 ambient). **Phase 0·1a·1b·2·3
= 완결**(M10~M12) + **잔여 14건 소진**(M13).

- [ ] **Phase 5 = 경계까지 섰다(2026-08-08)** — UI가 아니라 **"PR은 그 테넌트 파일 하나만
  건드린다"**를 세웠다(→ M15). `registry_write` + `scripts/attach_addon.py`(dry-run) +
  `.github/CODEOWNERS`. **남은 것**: 대시보드 attach UI(Next+FastAPI 두 층이라 별도 세션) ·
  실제 PR 생성(외부 동작이라 조작자에게 남김).
- [ ] **Phase 4**(managed 어댑터, billable) = 다음 후보.
  Phase 5가 열리면 3②를 GitOps-native로 닫을 수 있다(D32 재검토 조건). Phase 4로 넘긴 것:
  GCP/Azure 자격증명의 테넌트 바인딩(상세 → `STATUS` Open Risk 10).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 부재)
  — 실패 비용이 가용성이 아니라 데이터라 미뤘다.
- **2차 잔여 = 하나 남았다**: **스포크의 읽기 신원** — `_kubectl`이 맨 kubectl이고 공유 `argocd`
  ns를 읽어 테넌트 구분이 **코드 필터**다(쓰기는 허브가 401로 막지만 읽기는 아무것도 안 막는다).
  지금은 **시끄럽게만** 해 뒀고(`warn_if_ambient_read`), seam을 만들려면 **인클러스터 배포·민팅
  경로가 선행**이라 인프라 결정이다. 증거 `docs/evidence/push-identity-ambient.log`.
  (~~push 인증~~·~~heartbeat~~·~~서명키 rotation~~ = 전부 닫힘 → M15)

## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분은 `COMPLETED_SUMMARY.md` **M12**(Phase 3 인가) · **M13**("선언됐지만 아무도 읽지
> 않는 것들" 14건 — 배포 tier 발명·네임스페이스 출처 포함) · `PROGRESS_LOG.md` · `docs/evidence/`.

- [ ] **`record_route_activity`·`record_agent_activity`의 `cost_metrics` — 의도적으로 남김**.
  둘 다 `deployment_id`가 없어 그 필드를 렌더하는 유일한 뷰에 닿지 않아 **소비자 없는 필드**가 된다.

- [ ] **GCP/Azure 90일 보관 = 승인 항목이 아니었다(2026-08-08 측정)** — GCP는 Firestore API가
  **켜진 적조차 없고** Azure엔 `platform-agent` DB가 없다 → **지울 데이터 0**. 없는 컨테이너에
  TTL을 못 건다 = **구속 조건이 기록과 반대**이고, 보관하려면 **먼저 프로비저닝**(billable)
  → Phase 4. 코드 갭은 유효(스토어가 생기면 `ttl`은 써지는데 아무도 만료 안 시킨다).
  증거 `docs/evidence/gcp-azure-retention-nothing-to-delete.log` · Risk 2.
- [ ] **GCP/Azure 기록기는 `resolved_at`·`triggered_at`을 안 쓴다** — 읽는 쪽이 없어 지금
  고치면 **소비자 없는 필드**가 된다 → Phase 4.
- [ ] **analyzer LLM 실패 폴백이 여전히 일괄 P2** — `severity_hint`를 안 본다. 쓰려면 severity
  매핑 확정이 선행이고 그건 **정책 결정**이라 발명하지 않았다.
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
- [ ] **MCP 게이트웨이는 여전히 포트에 붙어 있지 않다(2026-07-31 확인)** — `src/`에
  `MCPServer` 생성자가 0이다. D39로 무스코프 읽기는 닫혔지만 **"닫았다"가 "스코프가 강제된다"는
  뜻은 아니다**: 호출자가 스코프를 넘겨야 하고 넘기는 프로덕션 경로가 없다. MCP-over-HTTP를
  붙일 때 **요청 경로가 스코프를 공급하는지** 확인할 것(가드가 그 트랩을 들고 있다).
- [ ] **A2A 인증 실집행 결정** — 카드가 광고하던 bearer/JWT를 서버가 안 검사하던 건 해소됐다.
  남은 결정은 **기본값을 on으로 돌릴지**(라이브 kagent 왕복이 익명이라 opt-in — D39가 밝혔듯
  그 "익명"은 **우리가 나가는 쪽**이지 누가 들어오는 쪽이 아니다).
- [ ] **Cosign 어드미션 = 업스트림 대기(2026-08-08 실측)**. 서명 생산자·소비자·CI 키리스는
  전부 섰다(→ M15). 남은 건 어드미션인데 **켤 수 없다**: policy-controller는 설치·동작하고
  실제로 거부하지만 **우리가 서명한 이미지도 거부한다**. 원인 확정 — **cosign v3.1.2는 Sigstore
  bundle을 `sha256-<digest>`에 쓰고 policy-controller는 `…\.sig`를 찾는다**. upstream 최신
  **v0.15.1**로 올려도 동일하고, **cosign v2로 서명하면 통과함을 양방향 실증**했다.
  ⚠️**우리 게이트는 같은 이미지에 VERIFIED를 준다**(같은 cosign을 부르니까) — **"검증됨"이
  도구마다 다르고 우리는 그 불일치를 원리상 못 본다.** 켜려면 서명을 v2로 되돌려야 하는데
  **CI 키리스가 v3 경로**다 → Risk 11과 같은 모양(upstream 대기).
  증거 `docs/evidence/cosign-admission-kind-attempt.log`.
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
