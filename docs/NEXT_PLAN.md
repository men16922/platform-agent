# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-26

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M10=GitAIOps 7/7+멀티테넌트 Phase 0·1a·1b+공급망,
> M9=eval·하드닝, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 (2026-07-26, gate 1281)

**GitAIOps 대조 7/7 · 멀티테넌트 Phase 0·1a·1b 완료**(rollouts-demo 소유권 TF→ArgoCD 이관까지 실행).
런북은 이제 선언한 순서·조건·검증대로 실행된다. **Phase 2 주요 4건 완료**(tenancy+Capsule ·
⑥ 데이터플레인 격리 · push 2축 수집기 · 대시보드 스위처). 잔여는 아래 3건.

## 사용자 게이트 (열린 것만)

- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=책의 GitAIOps는 AI 자리에 사람이 프롬프트를 넣지만
  우리는 **오프라인 Qwen 에이전트로 루프를 무인으로 닫는다**. 차별 소재는 자랑이 아니라 **자동화하면 새로
  깨지는 것들**: ①롤백↔selfHeal 충돌 ②자격증명=blast radius ③"실행됨≠나아졌음"(`resolution_verdict`)
  ④권한 게이트 부재의 과금 누출. **새 소재(M10)**: "선언은 됐는데 아무도 소비하지 않는 코드"가 반복해서
  나왔고 전부 테스트는 초록이었다 — 라이브 실행만이 소비 부재를 드러냈다.
  **집필·발행은 이 계획에만 남기고 착수하지 않는다**(사용자 지시 2026-07-25).
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0라 유지 중.

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5 = S 93.5) ·
**의사결정·MAD 히스토리**: `docs/plans/2026-07-21-multi-tenant-env-addons-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책(soft/vcluster/dedicated),
Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: 에이전트 실행 blast radius=1 tenant/env(자격증명이 경계) — Phase 1a에서 강제 완료.

- [~] **Phase 2**: Capsule(soft)+RBAC + 대시보드 tenant/env 스위처 + 라이브 상태 폴러(2축 drift).
  - [x] ~~첫 슬라이스: soft-tier tenancy~~ — **완료(`440f3a0`, gate 1216)**: `platform/tenancy.py`가
    레지스트리에서 Namespace(tenant/env/capability+PSS 라벨)·Capsule Tenant·네임스페이스 스코프 RBAC를
    렌더. Capsule 애드온(기본 OFF·cert-manager 비의존). 라이브 acme-dev 4 네임스페이스 + 쿼터 합산 실증.
    증거 `docs/evidence/phase2-tenancy-capsule.log`.
  - [x] ~~⑥ 실제 활성화~~ — **완료(`3dbc572`, gate 1219)**: 차트 폐기(설치하는 helm_release가
    없었고 16개 데카르트 곱이 구독 6개와 불일치) → 레지스트리 기반 렌더링. 집행이 증명된
    기판에만 렌더(k3s는 0개 + exit 1로 신고). 라이브 4종 통과.
  - [x] ~~대시보드 tenant/env 스위처~~ · ~~push 기반 2축 drift 수집기~~ — **완료(`b2b52fc`,
    gate 1251)**: 스포크 push 전용(허브 read 자격증명 0), 신원=서명을 검증한 키, staleness는
    수신시각 기준 UNKNOWN 강등. UI는 허브 불가/미푸시/침묵을 서로 다르게 표시.
  - [x] ~~클러스터 싱글턴 capability의 scope 축~~ — **완료(`bb7a819`, gate 1267)**: 카탈로그
    `scope: cluster|namespace` + delivery **계약**의 거부 가드 + 수집기의 공유 설치물 처리
    (`applicable=false`, 안 보이면 UNKNOWN). 미선언은 cluster로 fail-safe.
  - [x] ~~Application 삭제 시 워크로드 고아~~ — **완료(`e1ea15f`, gate 1271)**: 계약에
    "Deletion must cascade" 명시 + argocd resources-finalizer. 라이브 A/B로 실증.
    남는 것: cascade는 엔진 관리 대상까지라 **StatefulSet PVC는 존치**된다.
  - [x] ~~어댑터 helm values seam~~ — **완료(`01d3c6d`, gate 1281)**: 카탈로그가 values
    파일을 가리키고(복사 금지) argocd `valuesObject`·flux `spec.values`가 같은 dict를 싣는다.
    라이브에서 PSS 거부·PVC 자동삭제 2건을 더 잡아 근본수정.
  - [ ] faked managed 디스크립터로 `applicable=false` 검증 · DR 재구축 라이브 확인.
- [ ] Phase 3(인가 강화)·4(managed 어댑터, billable)·5(레지스트리 PR 쓰기) = 후속.
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 수단 선행**(kind엔 CSI 스냅샷터 기본 부재).
  rollouts-demo는 데이터 위험 0이라 먼저 했고, 나머지 셋은 실패 비용이 가용성이 아니라 데이터다.
- **S 달성(93.5) 근거**: ①실행위치=in-cluster 러너 ②token broker=incident provenance 바인딩
  ③read=push(허브 read 자격증명 0). **2차 잔여**: agent→hub push 인증 · 서명키 custody·rotation ·
  push heartbeat(staleness).

## 잔여 — 완료 항목에서 의도적으로 남긴 것

- [ ] **② executor span**(선택) — 현재 parking 경로만 실증. 승인 후 실행 경로는 미측정.
- [ ] **⑥ k3s 검증기 재실행**(선택) — flannel은 NetworkPolicy 집행이 전이되지 않으므로 기판별 재확인 필요.
- [ ] **선택 불가 런북 4개** — `CAPABILITY_RUNBOOKS`의 certificate-expiry·disk-full·
  health-check-failure·network-latency-high는 `BUILTIN_RUNBOOKS`에 없어 아무것도 이들을 고를 수 없다.
  step 배선(`c4816fd`) 중 발견했고, 범위를 조용히 넓히지 않으려 분리해 남김.
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
