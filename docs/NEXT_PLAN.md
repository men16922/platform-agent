# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-29

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M10=GitAIOps 7/7+멀티테넌트 Phase 0·1a·1b+공급망,
> M9=eval·하드닝, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 (2026-07-29, gate 1544)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **차단 없는 잔여 소진**. 남은 잔여는 작업이 아니라 **결정** 3건.
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.

## 사용자 게이트 (열린 것만)

- [ ] **⚠️ 결정 1: "배포는 어느 테넌트 소유인가"** — deployments/activities 파티션과 **모델 호출
  rate limit을 동시에** 막고 있다(아래 두 항목). 발명 금지라 결정 없이는 둘 다 진행 불가.
- [ ] **⚠️ 결정 2: 무스코프 MCP 읽기를 닫을 것인가** — 닫으면 검증된 익명 kagent 왕복이 깨진다.
- [ ] **⚠️ 결정 3: Capsule `limitRanges` 이관 경로** — 클러스터 스코프(D30 위반) vs 새 SA+RBAC.
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
**Phase 0·1a·1b·2·3 = 완결**(M10~M12) + **잔여 12건 소진**(M13) — 상세 → `COMPLETED_SUMMARY.md`.

- [ ] **deployments/activities 파티션 — 데이터 모델 결정 필요(버그 아님)** — 인시던트는 tenant가
  *있는데 버려진* 것이었지만, 배포 기록은 `provider/service/version/environment`뿐이고
  `environment`는 레지스트리의 tenant/env 쌍이 아니라 자유 문자열("production")이다.
  **배포는 어느 테넌트 소유인가**를 먼저 정해야 한다 — 발명하지 않고 남긴다.
- [ ] **Phase 4**(managed 어댑터, billable)·**5**(레지스트리 PR 쓰기) = 다음 후보.
  Phase 5가 열리면 3②를 GitOps-native로 닫을 수 있다(D32 재검토 조건). Phase 4로 넘긴 것:
  GCP/Azure 자격증명의 테넌트 바인딩(상세 → `STATUS` Open Risk 8).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 부재).
  실패 비용이 가용성이 아니라 데이터라 rollouts-demo와 달리 미뤘다.
- **2차 잔여**: agent→hub push 인증 · 서명키 custody·rotation · push heartbeat(staleness).
  (S 93.5 근거는 설계 문서 참조)

## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분은 `COMPLETED_SUMMARY.md` **M12**(Phase 3 인가) · **M13**("선언됐지만 아무도 읽지
> 않는 것들" 12건 — 리포트 창 포함) · `PROGRESS_LOG.md` · `docs/evidence/`.

- [ ] **TS 스윕 잔여 후보 — 사문화이지 손실이 아니다(2026-07-29 확인, 고치지 않음)**.
  대시보드 인터페이스 261필드 중 후보 47(구조분해 오탐 포함). 읽어본 결과 **데이터 손실은
  `activity-model.ts` 한 건뿐**이었고 나머지는 죽은 선언이다: ①`ApprovalRequest`의
  `request_kind`/`request_subject`/`request_summary` = 이미 렌더되는 `alarm_name`/`root_cause`의
  **복사본**(온프렘 매퍼만 채움) ②`staleAfterSec` = 임계값을 클라이언트로 보내는데 표시도
  비교도 안 함(집행은 Python `collector.py`에 있고 정상) ③`PlatformTenant → environments →
  substrate/delivery` + `Quota`가 **서로만 참조하는 닫힌 섬** — 라이브는 전부 push된
  `NormalizedAddonStatus`로 돈다(`namespaceFor`의 `Pick<PlatformTenant,"namingPrefix">`만 예외).
  ③은 레지스트리 스키마의 **두 번째 선언**이라 `activity-model`과 같은 부류지만, **거짓
  운영 주장이 없어** 위험도가 다르다. 지우려면 실 레지스트리(Python·git)와 대조가 선행 —
  **실증 없이 손대지 않는다.**
- [ ] **`record_route_activity`·`record_agent_activity`의 `cost_metrics` — 의도적으로 남김**
  (2026-07-29). 둘 다 `deployment_id`를 쓰지 않아 그 필드를 렌더하는 유일한 뷰(배포 상세)에
  닿지 않는다. 지금 넣으면 **소비자 없는 필드**가 되고, 그게 M13이 찾아낸 바로 그 부류다.
  route 활동을 그 뷰에 태울 방법이 생기면 함께.

- [ ] **인시던트 필드 실 DynamoDB 왕복 미검증(쓰기·읽기 양쪽)** — 모킹 테이블 + 직렬화기
  직접 확인 + 투영 표현식 파싱까지다. 새 속성(`triggered_at`·`confidence`·`reconciliation`·
  `trace_id`·`resolved_at`)이 실 테이블을 왕복해 대시보드에 읽힌 적은 아직 없다.
  **이제 유일하게 남은 차단 없는 잔여** — 실 AWS 자원이 필요해 승인 사항.
- [ ] **GCP/Azure는 90일 보관을 집행하지 않는다(2026-07-29 확인, 승인 필요)** — 두 기록기 다
  `ttl`을 쓰지만 **어느 쪽도 스토어가 켜져 있지 않다**: Cosmos 항목 `ttl`은 컨테이너에
  DefaultTimeToLive가 있어야 적용되는데 `durable_functions.py`가 `--ttl` 없이 만들고,
  Firestore는 TTL 정책이 IaC 어디에도 없으며 필드도 **Timestamp가 아니라 정수**라 정책을
  붙여도 안 걸린다. 즉 두 스토어의 인시던트 문서는 **무기한 남는다**. 주석은 사실에 맞춰
  고쳤고(집행 안 하는 걸 광고하지 않는다) **동작은 안 바꿨다** — 보관을 켜는 것은 실 스토어의
  데이터 삭제라 승인 사항이고, 지금 이 스토어들엔 읽는 쪽도 없다.
- [ ] **GCP Firestore·Azure Cosmos 기록기는 `resolved_at`·`triggered_at` 둘 다 안 쓴다** —
  대시보드도 주간 리포트도 그 스토어를 읽지 않아 지금 고치면 **소비자 없는 필드**가 된다.
  Phase 4(managed 어댑터)에서 읽는 쪽이 생길 때 함께 — 의도적으로 남김.
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
