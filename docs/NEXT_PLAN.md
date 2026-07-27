# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-27

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M10=GitAIOps 7/7+멀티테넌트 Phase 0·1a·1b+공급망,
> M9=eval·하드닝, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 (2026-07-27, gate 1355)

**GitAIOps 대조 7/7 · 멀티테넌트 Phase 0·1a·1b 완료**(rollouts-demo 소유권 TF→ArgoCD 이관까지 실행).
런북은 이제 선언한 순서·조건·검증대로 실행된다. **Phase 2 완결**(M11) — 다음은 **Phase 3(인가 강화)**.
**시연 가능**: `make dev-up` → `make demo-baseline` 두 줄로 영상 시나리오 A가 재현된다.
**자연어 한 문장이 테넌트를 세운다**: `setup_tenancy → install_tenant_addons` 체인(17.6s, 라이브 실증).

## 사용자 게이트 (열린 것만)

- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=책의 GitAIOps는 AI 자리에 사람이 프롬프트를 넣지만
  우리는 **오프라인 Qwen 에이전트로 루프를 무인으로 닫는다**. 차별 소재는 자랑이 아니라 **자동화하면 새로
  깨지는 것들**: ①롤백↔selfHeal 충돌 ②자격증명=blast radius ③"실행됨≠나아졌음"(`resolution_verdict`)
  ④권한 게이트 부재의 과금 누출. **새 소재(M10)**: "선언은 됐는데 아무도 소비하지 않는 코드"가 반복해서
  나왔고 전부 테스트는 초록이었다 — 라이브 실행만이 소비 부재를 드러냈다.
  **집필·발행은 이 계획에만 남기고 착수하지 않는다**(사용자 지시 2026-07-25).
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0라 유지 중.
- [ ] **LinkedIn 발행** — Notion 전문은 발행 완료(`3a94c2420ac4801cbe99e36c16ed90fd`,
  YouTube Shorts `2J9WfZV0TPE`). `docs/post/linkedin-intro-ko.md`를 최종 확인해 영상/링크와 게시한다.
  본문의 "어려웠던 것" 단락은 영상의 논지(반증 가능한 화면)와 유지한다.
  **게시 전 정정 1건(미반영)**: 본문의 "**7B가 30B를 이겼습니다**(20/20 vs 19/20)"는 과대주장이다 —
  1건 차이·시행 1회(`trials:1`)이고 temperature 1.0에서는 **역전된다**(7B 18 < 30B 19).
  데이터가 지탱하는 건 ①크기 4배로도 개선 없음 ②temp↑면 악화 ③정확도를 움직인 건 프롬프트
  (전 설정 80%→95~100%). 근거 → `docs/evidence/model-sweep-live.log`. 아티클 본문은 이미 헤지돼 있다.
- [x] **영상 재촬영·편집**(2026-07-26) — 시나리오가 격리 반증 단독 → **풀스택 체인**으로 바뀌어
  다시 찍었다. `docs/post/media/multitenancy-fullstack-30s.mp4`(30.03초 · 오버레이 없음 ·
  원본 153.8초를 10컷). 파이프라인 4단계 → `scripts/demo/README.md`.
  구판 `isolation-falsified-30s.mp4`는 마지막 비트로 흡수됨.

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5 = S 93.5) ·
**의사결정·MAD 히스토리**: `docs/plans/2026-07-21-multi-tenant-env-addons-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책(soft/vcluster/dedicated),
Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리.
**최우선 불변식**: 에이전트 실행 blast radius=1 tenant/env(자격증명이 경계) — Phase 1a에서 강제 완료.

- [x] **Phase 2 완결(M11, gate 1290)** — tenancy+Capsule · ⑥ 데이터플레인 격리 · push 2축
  수집기 + 대시보드 스위처 · capability scope 축 · 삭제 cascade · values seam · managed 경로 ·
  DR 재구축. 상세 → `COMPLETED_SUMMARY.md` M11, 증거 `docs/evidence/phase2-*.log`.
- [x] **Phase 3① 자격증명 격리 full(gate 1355, 2026-07-27)** — 가드 1곳(`guard_scoped_action`)을
  세 러너가 공유, 두 디스패치 경로 모두 스코프 전달, 라이브에서 API 서버가 경계를 판정.
  부수로 `render_rbac`의 **바인딩 대상 SA 부재** 근본수정(Phase 1a의 RBAC 팔이 미행사 상태였음).
  증거 `docs/evidence/phase3-scoped-credentials-all-runners.log`.
- [ ] **Phase 3② 롤백↔selfHeal 우선순위** — registry write-back으로 정책 구현. 지금은 문서로만
  명명돼 있고 `ONPREM_EXECUTOR_LIVE=false`로 묶여 있다(설계 문서 289–290행).
- [ ] **Phase 3③ viewer 가시성 제한** — 2급 항목. 대시보드 쪽, 범위 가장 작고 독립적.
- [ ] Phase 4(managed 어댑터, billable)·5(레지스트리 PR 쓰기) = 후속.
  **Phase 4로 넘긴 것(명시)**: GCP/Azure 자격증명의 테넌트 바인딩. 현재 GCP는 프로젝트 전역 신원,
  Azure는 ARM에서 **cluster-admin kubeconfig**를 받아온다 — 스코프는 네임스페이스만 좁힌다.
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
- [ ] **Capsule deprecation 이관** — `render_tenancy.py` 적용 시 `limitRanges`(→TenantReplications)와
  `additionalMetadata`(→`additionalMetadataList`) 경고가 뜬다. 지금은 동작하지만 상위 버전에서
  **에러 없이 안 읽히는** 쪽으로 실패할 부류라 Capsule 업그레이드 전에 처리.
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
