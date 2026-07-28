# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-29

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M10=GitAIOps 7/7+멀티테넌트 Phase 0·1a·1b+공급망,
> M9=eval·하드닝, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 (2026-07-29, gate 1470)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **차단 없는 잔여 소진**. 남은 잔여는 작업이 아니라 **결정** 3건.
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.

## 사용자 게이트 (열린 것만)

- [ ] **⚠️ 결정 1: "배포는 어느 테넌트 소유인가"** — deployments/activities 파티션과 **모델 호출
  rate limit을 동시에** 막고 있다(아래 두 항목). 발명 금지라 결정 없이는 둘 다 진행 불가.
- [ ] **⚠️ 결정 2: 무스코프 MCP 읽기를 닫을 것인가** — 닫으면 검증된 익명 kagent 왕복이 깨진다.
- [ ] **⚠️ 결정 3: Capsule `limitRanges` 이관 경로** — 클러스터 스코프(D30 위반) vs 새 SA+RBAC.
- [ ] **⚠️ 결정 4: 인시던트 타임라인이 무엇을 표시할 것인가** — `triggered_at` 미소비(아래).
- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=책의 GitAIOps는 AI 자리에 사람이 프롬프트를 넣지만
  우리는 **오프라인 Qwen 에이전트로 루프를 무인으로 닫는다**. 차별 소재는 **자동화하면 새로 깨지는 것들**:
  ①롤백↔selfHeal 충돌 ②자격증명=blast radius ③"실행됨≠나아졌음" ④권한 게이트 부재의 과금 누출.
  **새 소재**: "선언은 됐는데 아무도 소비하지 않는 코드"가 반복해서 나왔고 전부 테스트는 초록이었다 —
  라이브 실행만이 소비 부재를 드러냈다(07-28에 세 건: grant·런북 티어·Capsule 필드 / 07-29에 두 건 더:
  executor span·`resource_types`). **07-29 추가 소재**: 내 테스트가 실제 입력이 아니라 키워드 목록에
  맞춰져 있어서, 유닛은 초록인데 라이브는 계속 틀렸다.
  **집필·발행은 이 계획에만 남기고 착수하지 않는다**(사용자 지시 2026-07-25).
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0라 유지 중.

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5 = S 93.5) ·
**의사결정·MAD 히스토리**: `docs/plans/2026-07-21-multi-tenant-env-addons-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책(soft/vcluster/dedicated),
Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: 에이전트 실행 blast radius=1 tenant/env(자격증명이 경계) — Phase 1a에서 강제 완료.
**Phase 0·1a·1b·2·3 = 완결**(M10~M12) — 상세 → `COMPLETED_SUMMARY.md`.

- [ ] **deployments/activities 파티션 — 데이터 모델 결정 필요(버그 아님)** — 인시던트는 tenant가
  *있는데 버려진* 것이었지만, 배포 기록은 `provider/service/version/environment`뿐이고
  `environment`는 레지스트리의 tenant/env 쌍이 아니라 자유 문자열("production")이다.
  **배포는 어느 테넌트 소유인가**를 먼저 정해야 한다 — 발명하지 않고 남긴다.
- [ ] **Phase 4**(managed 어댑터, billable)·**5**(레지스트리 PR 쓰기) = 다음 후보.
  Phase 5가 열리면 3②를 GitOps-native로 닫을 수 있다(D32 재검토 조건). Phase 4로 넘긴 것:
  GCP/Azure 자격증명의 테넌트 바인딩(상세 → `STATUS` Open Risk 7).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 부재).
  실패 비용이 가용성이 아니라 데이터라 rollouts-demo와 달리 미뤘다.
- **2차 잔여**: agent→hub push 인증 · 서명키 custody·rotation · push heartbeat(staleness).
  (S 93.5 근거는 설계 문서 참조)

## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분(Phase 2·3, grant 대조, 런북 선택성·티어, MCP 옆문, call budget, Capsule metadata,
> executor span, 온프렘 매칭)은 `COMPLETED_SUMMARY.md` M12 · `PROGRESS_LOG.md` · `docs/evidence/`.

- [ ] **`triggered_at`이 여전히 미소비**(2026-07-29 스윕 발견) — 네 어댑터가 알람의 실제 발생
  시각(`startsAt`/`firedDateTime`/`started_at`)을 담는데 아무도 안 읽어 **탐지까지 걸린 시간을
  구할 수 없다**(인시던트 기록은 자기 쓰기 시각을 쓴다). 타임라인에 무엇을 표시할지 결정 필요.
- [ ] **analyzer LLM 실패 폴백이 여전히 일괄 P2** — `severity_hint`를 안 본다. 거기서 쓰려면
  severity 매핑을 확정해야 하고, 그건 위와 같은 **정책 결정**이라 발명하지 않았다.
- [ ] **⑥ k3s 검증기 재실행**(선택) — flannel은 NetworkPolicy 집행이 전이되지 않으므로 기판별 재확인 필요.
- [ ] **rate limit을 모델 호출까지 확장 — 위 데이터 모델 결정에 묶여 있다(2026-07-28 조사)**.
  로컬 모델 호출자는 `local_deployer`/`strands_deployer` **둘뿐이고 둘 다 배포 경로**다.
  배포 요청(`DeployRequest`)엔 테넌트가 없고, `setup_tenancy(tenant, env)`는 **모델이 부르는
  도구** — 즉 테넌트는 추론의 **입력이 아니라 출력**이다. 추론에서 알아낸 테넌트로 그 추론을
  과금할 수는 없으므로, 호출자가 미리 선언해야 하고 그게 곧 "배포는 어느 테넌트 소유인가"다.
  인시던트 경로는 테넌트가 있지만 로컬 모델을 쓰지 않는다.
- [ ] **무스코프 MCP 읽기는 여전히 ambient** — 검증된 익명 kagent 왕복을 살리려는 의도적 예외다.
  닫으려면 kagent 경로에 먼저 스코프를 줘야 한다. 읽기가 무해해서가 아니다(남의 로그 = 유출).
- [ ] **A2A 인증 실집행 결정** — 카드가 광고하던 bearer/JWT를 서버가 검사하지 않던 것은 해소했다
  (`A2A_BEARER_TOKEN` 미설정 시 광고도 안 한다). 남은 결정은 **기본값을 on으로 돌릴지** —
  지금은 라이브 kagent 왕복이 익명이라 opt-in이다.
- [ ] **Capsule `limitRanges` 이관 — 경로 결정 필요(기계적 포팅 아님)**.
  `GlobalTenantResource`는 **클러스터 스코프**라 에이전트 변경 범위를 테넌트 밖으로 밀어
  **D30 위반**이고, `TenantResource`는 테넌트 안에 머물지만 **SA+RBAC 새 권한 표면**이 필요하다.
  지금은 동작하고 경고만 뜬다(2건→1건).
- [ ] **Cosign 어드미션 집행**(승인 필요) — 현재는 CI/사람용 검증 게이트까지다. API 서버가 미서명
  이미지를 거부하려면 policy controller(sigstore/Kyverno)라는 새 클러스터 의존성이 필요 → Phase 2와 함께.

## 유지 규약 (완료된 리팩토링에서 나온 "하지 말 것")

`_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이). detector/analyzer/decision은 SDK가 90%+
상이해 **의도적으로 DRY 안 함**. `approval_bridge` 추가 분해도 하지 않는다. 근거 → `DECISIONS.md` D15.
포괄 `gcloud:*`류 권한 allow를 되살리지 않는다(D16 우회 재발) → D22.

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 재평가 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴 메모(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지(계약/방법론만); 정적 무조건 fan-out은 self-consistency 라우팅 회귀라 금지; 자유텍스트 spawn_subagent 핵 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
