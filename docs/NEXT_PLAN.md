# NEXT_PLAN — platform-agent

최종 갱신: 2026-08-02

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(**M14=사용자 게이트 5건**, M13=미소비 14건,
> M10=GitAIOps 7/7+멀티테넌트 Phase 0·1a·1b) / `PROGRESS_LOG.md`(+`docs/archive/`). **≤120줄** 유지.

## 현재 상태 (2026-08-08, gate 1618)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **차단 없는 잔여 소진**(M13, 14건) + **결정 6건 전부 닫힘**(D36·D38·D39·D40·D41·**D42**). 남은 잔여는 **승인 3건**뿐이고 그 다음은 **Phase 4/5**.
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.

## 사용자 게이트 (결정 6건 전부 닫힘 — 재개 조건만)

- [x] **결정 1~5 = 전부 닫힘(2026-07-29~08-02)** — 1=**D36**(배포는 테넌트 소유가 아니다) ·
  2=**D39**(무스코프 읽기 거부) · 3=**D41**(Capsule `limitRanges`를 객체로 직접 렌더) ·
  4=**D40**(k3s는 proven에 넣지 않는다) · 5=**D38**(스코프 생산자 + 배포 신원 축소).
  근거·증거는 `DECISIONS.md`와 각 `docs/plans/*`. **다시 열리는 조건만 여기 남긴다**:
  라우터에 인증이 서면 결정 5 **C**(요청이 테넌트를 선언)와 결정 1의 파티션이 열리고,
  k3s-lab에 실제 워크로드가 서면 결정 4가 열린다(경로=조사 문서 옵션 A).
- [x] **결정 6 = 완료(2026-08-02) → D42**: 승인은 **1회용이 아니라 상하는 것**. 서명이 덮는
  `issued_at` + TTL(기본 900초, `PLATFORM_APPROVAL_TTL_SECONDS`, **끄는 스위치 없음**).
  one-time-use는 **틀린 수정**이었다 — 실행기가 같은 인시던트로 두 번 해석한다. TTL 안의
  재사용은 **가능하고 그렇게 적었다**. 조사 `docs/plans/2026-08-02-nonce-replay-scope.md`,
  증거 `docs/evidence/approval-ttl-replay-bound.log`. **남은 것**: 행동 단위 1회용(옵션 B)은
  실행기 3종 상태 저장이 필요 → Phase 4와 함께.
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

- [ ] **Phase 4**(managed 어댑터, billable)·**5**(레지스트리 PR 쓰기) = 다음 후보.
  Phase 5가 열리면 3②를 GitOps-native로 닫을 수 있다(D32 재검토 조건). Phase 4로 넘긴 것:
  GCP/Azure 자격증명의 테넌트 바인딩(상세 → `STATUS` Open Risk 10).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 부재)
  — 실패 비용이 가용성이 아니라 데이터라 미뤘다.
- **2차 잔여**(2026-08-02 재측정): ~~agent→hub push 인증~~ = **이미 완료**(2026-07-26, 오늘
  라이브 재확인 — 무서명·틀린 키·신원 불일치·크로스테넌트 행 전부 401). ~~push heartbeat~~ =
  `--interval` + 허브 stale 판정으로 **동작 중**. **실제로 남은 것 둘**:
  ① **스포크의 읽기 신원** — `_kubectl`이 맨 kubectl이고 공유 `argocd` ns를 읽어 테넌트 구분이
  **코드 필터**다(쓰기는 허브가 막지만 읽기는 아무것도 안 막는다). 인클러스터 배포 매니페스트도
  없다. 지금은 **시끄럽게만** 해 뒀다(`warn_if_ambient_read`) — seam을 만들려면 **민팅 경로가
  선행**이다(D38이 그래서 `make deploy-identity`와 함께 나왔다). 증거
  `docs/evidence/push-identity-ambient.log`. ② ~~서명키 rotation~~ = **닫힘(2026-08-08)** —
  막고 있던 건 암호가 아니라 **배포 위상**이었다(서명자·검증자가 다른 프로세스 = 교체가
  원자적일 수 없고, 그 실패가 `failed attestation`이라 **위조로 읽힌다**).
  `PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING`은 **검증 전용**이고 겹침을 유한하게 만드는 건
  D42의 TTL이다. 3단 절차는 `Makefile:256` 주석. **남은 것 = custody**: 키가 어디서 오는가는
  시크릿 매니저 선택이라 **인프라·정책 결정**(+과금)이고, 로컬 라벨은 이미 정확하다
  ("NOT a secret-management story") → 승인 필요 항목에 가깝다.
## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분은 `COMPLETED_SUMMARY.md` **M12**(Phase 3 인가) · **M13**("선언됐지만 아무도 읽지
> 않는 것들" 14건 — 배포 tier 발명·네임스페이스 출처 포함) · `PROGRESS_LOG.md` · `docs/evidence/`.

- [ ] **TS 스윕 잔여 후보 — 사문화이지 손실이 아니다(2026-07-29 확인, 고치지 않음)**. 261필드 중
  후보 47을 완독했고 **데이터 손실은 `activity-model.ts` 한 건뿐**. 나머지는 죽은 선언이다:
  `ApprovalRequest.request_*` 3종=렌더 필드의 복사본 · `staleAfterSec`=집행은 Python
  `collector.py` · `PlatformTenant→…substrate/delivery`+`Quota`=**서로만 참조하는 닫힌 섬**.
  마지막 건은 **거짓 운영 주장이 없어** 위험도가 다르고, 지우려면 실 레지스트리 대조가 선행이다.
- [ ] **`record_route_activity`·`record_agent_activity`의 `cost_metrics` — 의도적으로 남김**.
  둘 다 `deployment_id`가 없어 그 필드를 렌더하는 유일한 뷰에 닿지 않아 **소비자 없는 필드**가 된다.

- [x] **인시던트 필드 실 DynamoDB 왕복 = 검증됨(2026-08-08)** — 생산자 `_record_incident`가 실
  `incident-history`에 행을 남기고(18속성), 여섯 속성이 **타입까지 보존**되며(특히
  `confidence`가 `Decimal` = DynamoDB N — 문자열이었다면 대시보드가 영원히 "n/a"),
  생산 리더의 `started_at`이 `triggered_at`에서 온다. 프로브는 자기 행을 지운다:
  `scripts/probe_incident_roundtrip.py`, 증거 `docs/evidence/incident-fields-dynamo-roundtrip.log`.
  **남은 한 칸**: 대시보드 **TS 리더**로는 안 읽었다(속성명·별칭 대조까지). 브라우저 렌더는 미확인.
- [ ] **GCP/Azure 90일 보관 — 승인 항목이 아니었다(2026-08-08 측정)**. "켜는 건 실 데이터
  삭제"가 **한 번도 측정된 적 없는 절반**이었다: GCP는 platform-agent 프로젝트
  (`project-ec7809f7`)에 **Firestore API가 켜진 적조차 없고**(다른 3개 프로젝트도 스윕),
  Azure는 구독 1개·Cosmos 계정 1개에 `platform-agent` DB가 **없다**. 즉 **지울 데이터가 0**이고,
  없는 컨테이너에 `DefaultTimeToLive`를 걸 수도 없다. **구속 조건이 기록과 반대**다 — 보관을
  켜려면 **먼저 프로비저닝**해야 하고 그건 billable → **Phase 4로 이관**. 코드 레벨 갭은
  그대로 유효하다(스토어가 생기는 순간 `ttl`은 써지는데 아무도 만료시키지 않는다).
  증거 `docs/evidence/gcp-azure-retention-nothing-to-delete.log` · `STATUS` Risk 2.
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
- [ ] **Cosign 어드미션 — 승인이 아니라 선행이 막고 있다(2026-08-08 측정)**. 기록된 이유
  ("policy controller = 새 클러스터 의존성")는 **참이지만 구속하지 않는다**. 진짜 구속 조건은
  한 단계 앞이다: **아무것도 서명하지 않는다**(`cosign sign` 0건 · CI 자체가 없음 · 검증기의
  유일한 호출자는 자기 테스트 · 차트는 레지스트리 없는 맨 태그 + `digest: ""`라 서명이 놓일
  주소가 없다). 지금 policy controller를 넣으면 **모든 워크로드가 거부**된다.
  **순서**: ①이미지를 레지스트리에 다이제스트로 올린다 → ②`cosign sign` → ③차트가 다이제스트를
  핀 → ④그때 어드미션이 의미를 갖는다. **①②는 완료(2026-08-08)** — `make sign-image`가
  빌드→다이제스트 push→서명→**레포 자신의 게이트로 검증**까지 하고, 미서명 다이제스트는
  `NOT SIGNED`로 거부된다(라이브). ③은 **커밋하지 않는다**(로컬 다이제스트는 배포별 값) ·
  ④만 남은 승인 사항. **소비자도 붙었다**(2026-08-08) — 서명 경로만 만들면 **소비자 없는
  생산자**가 되므로 `image_trust.require_trusted_image`를 **배포 직전**에 배선했다.
  라이브에서 미서명 다이제스트는 `cluster.deploy` 호출 **전에** 막힌다. 증거
  `docs/evidence/image-signature-deploy-gate.log`. ⚠️**옵트인**이고
  (`PLATFORM_REQUIRE_SIGNED_IMAGES`) **온프렘 진입점 하나**만 덮는다.
  ~~그 전에 붙는 결정 둘(CI · 키 custody)~~ = **둘 다 닫힘(2026-08-08)** — 사실 **한 결정**이었다:
  **키리스가 키를 없애서 custody를 푼다**. `gate.yml`(게이트를 기계가 돌린다) + `sign-image.yml`
  (빌드→GHCR→키리스 서명→레포 자신의 게이트로 검증, 라이브 VERIFIED). 대가는 **Rekor 영구 공개
  기록**(철회 불가). 증거 `docs/evidence/ci-keyless-signing.log`.
  **④어드미션 = kind에서 시도했고 승인 조건이 하나 더 드러났다(2026-08-08)**. policy-controller는
  설치·동작하고 **실제로 거부한다**. 그런데 **우리가 서명한 이미지도 거부한다**(`no signatures
  found`) — 호스트 `cosign verify`는 같은 다이제스트에 VERIFIED이고 서명 아티팩트도 레지스트리에
  실재하는데도. ⚠️**첫 시도는 성공처럼 보였다**: 미서명이 거부됐는데 사유가 `connection refused`
  였고, **서명된 것도 같은 이유로 거부**됐다 — 미서명만 돌려 봤으면 "동작한다"고 잘못 적었을
  것이다. **원인 확정**: 멀티아치 가설은 **반증**됐고(자식 manifest에 서명해도 동일), 진짜 원인은
  **cosign v3와 policy-controller가 서명을 서로 다른 곳에 둔다**는 것이다 — cosign **v3.1.2**는
  **Sigstore bundle**을 `sha256-<digest>` 태그에 쓰고, policy-controller **0.13.1**은 cosign v2의
  `sha256-<digest>`**`.sig`** 태그를 찾는다. 그 태그는 없다. `--registry-referrers-mode=legacy`도
  되돌리지 못한다. ⚠️**핵심**: 우리 게이트는 같은 이미지에 **VERIFIED**를 준다(같은 cosign v3를
  부르니까) — 즉 **"검증됨"이 도구마다 다르고, 우리 게이트는 이 불일치를 원리상 못 본다.**
  클러스터는 우리가 통제하지 않는 자기 검증기를 갖고 있다.
  **닫는 법(택1, 승인 사항 — 코드가 아니라 버전 선택)**: ①cosign **v2**로 서명 ②Sigstore bundle을
  읽는 policy-controller로 업그레이드. 증거 `docs/evidence/cosign-admission-kind-attempt.log`.
  → `STATUS` Risk 6·13, 가드 `tests/test_signature_gate_claims.py`·`test_image_trust.py`.

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
