# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-31

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M10=GitAIOps 7/7+멀티테넌트 Phase 0·1a·1b+공급망,
> M9=eval·하드닝, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 (2026-07-31, gate 1605)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **차단 없는 잔여 소진**(M13, 14건). 남은 잔여는 **결정 2건**(3·4) **+ 승인 3건**. 결정 1=D36, 5=D38, **2=D39**(무스코프 읽기 차단 — 근거가 사실이 아니었다)로 닫힘.
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.

## 사용자 게이트 (열린 것만)

- [x] **결정 1 = 완료(2026-07-29) → D36**: 배포는 테넌트 소유가 아니다. deployments/activities
  **무파티션 확정** + **테넌트별 모델 rate limit 안 함 확정**. 근거·선택지 →
  `docs/plans/2026-07-29-deployment-tenant-ownership.md`, 결정 → `DECISIONS.md` D36.
  되돌릴 조건: 배포 경로가 테넌트-aware해지고 라우터에 인증이 서면 둘 다 열린다.
- [x] **결정 2 = 완료(2026-07-31) → D39**: 무스코프 클러스터 **읽기도 거부**. 근거였던
  "익명 kagent 왕복이 이걸 쓴다"가 **사실이 아니었다**(왕복은 아웃바운드 · `src/`에 `MCPServer`
  생성자 0). 브리프 `docs/plans/2026-07-31-unscoped-mcp-read.md`, 증거
  `docs/evidence/unscoped-mcp-read-closed.log`. 탈출구 `PLATFORM_MCP_ALLOW_UNSCOPED_READS`.
- [ ] **⚠️ 결정 3: Capsule `limitRanges` 이관 경로** — 클러스터 스코프(D30 위반) vs 새 SA+RBAC.
- [ ] **⚠️ 결정 4: k3s를 proven 기판에 넣을 것인가** — 집행은 라이브로 증명됐고 시맨틱은
  미증명(피어 테넌트 부재). 상세는 아래 잔여 섹션.
- [x] **결정 5 = 완료(2026-07-31) → D38**: **B 배포 신원 축소 + A 스코프 생산자** 둘 다 실행.
  브리프 `docs/plans/2026-07-30-deploy-request-tenant-scoping.md`, 증거
  `docs/evidence/{deploy-identity-reduction,scope-producer-live}.log`. **C·D(요청이 테넌트를
  선언)는 라우터 인증까지 보류** — 인증 없는 자진신고로 가드를 세우면 오류 방어를 공격 방어처럼
  광고하게 된다. 되돌릴 조건: 라우터에 인증이 서면 C가 열린다.
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
- **2차 잔여**: agent→hub push 인증 · 서명키 custody·rotation(**결정 5-A의 선행**) · push heartbeat.

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

- [ ] **인시던트 필드 실 DynamoDB 왕복 미검증** — 모킹 테이블 + 직렬화기 확인 + 투영 파싱까지다.
  새 속성 5종이 실 테이블을 왕복해 대시보드에 읽힌 적은 없다 — 실 AWS 승인 사항.
- [ ] **GCP/Azure는 90일 보관을 집행하지 않는다(2026-07-29, 승인 필요)** — 둘 다 `ttl`을 쓰지만
  스토어가 안 켜져 있어 **무기한 남는다**. 켜는 건 실 데이터 삭제 → `STATUS` Risk 2.
- [ ] **GCP/Azure 기록기는 `resolved_at`·`triggered_at`을 안 쓴다** — 읽는 쪽이 없어 지금
  고치면 **소비자 없는 필드**가 된다 → Phase 4.
- [ ] **analyzer LLM 실패 폴백이 여전히 일괄 P2** — `severity_hint`를 안 본다. 쓰려면 severity
  매핑 확정이 선행이고 그건 **정책 결정**이라 발명하지 않았다.
- [ ] **k3s: 집행 증명 완료(2026-07-29), 게이트는 미개방 — 결정 4** — 라이브 3종(검증기
  **ENFORCED** 컨트롤 유효 · default-deny **아래에서 태어난** 파드의 readinessProbe Ready ·
  같은 정책에서 DNS 정상). 증거 `docs/evidence/k3s-netpol-enforcement.log` ·
  `scripts/probe_netpol_side_effects.sh`. `PROVEN_ENFORCING_SUBSTRATES`에 넣으면 `render_tenancy`가
  **acme/prod(k3s-lab)에 NetworkPolicy를 emit**한다. 3종이 증명한 건 "기판이 집행할 수 있고
  집행해도 워크로드가 안 깨진다"까지고, **이 집합이 licensing하는 주장**(우리 정책 shape이 같은
  테넌트는 통과·다른 테넌트는 차단)은 미검증이다 — `verify_tenant_isolation.py`가 **k3s-lab에
  피어 테넌트가 없어 못 돈다**. globex/prod를 만들면 실 자원이 프로비저닝되므로 **인프라 결정**.
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
- [ ] **Capsule `limitRanges` 이관 — 경로 결정 필요(기계적 포팅 아님)**.
  `GlobalTenantResource`는 **클러스터 스코프**라 에이전트 변경 범위를 테넌트 밖으로 밀어
  **D30 위반**이고, `TenantResource`는 테넌트 안에 머물지만 **SA+RBAC 새 권한 표면**이 필요하다.
  지금은 동작하고 경고만 뜬다(2건→1건).
- [ ] **Cosign 어드미션 집행**(승인 필요) — 현재는 CI/사람용 게이트까지. API 서버가 미서명
  이미지를 거부하려면 policy controller라는 새 클러스터 의존성이 필요.

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
