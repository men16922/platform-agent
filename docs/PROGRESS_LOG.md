# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-26

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-26 — ① 2단계: 에이전트를 릴리스 게이트로 (gate 1095→1114)

- Status: 다음 우선순위였던 Phase 1b 핸드오프가 **사용자 게이트(push)+스냅샷 부재로 차단**이라, 막힌 데 없는
  ①-2단계를 선택해 진행. 코드·차트·테스트 완료, **canary 전체 E2E는 미실행**(사용자 중단).
- Changed(`b9eafb0`): `ai/canary_judge.py` + `POST /canary/judge`(webhook) + 차트 `agentAnalysis` 값 ·
  `web` provider AnalysisTemplate · Rollout이 두 판정자를 독립 나열(둘 중 하나만 실패해도 abort).
- Verified: `make check` → **1114 passed, 1 skipped**(+19) · `helm template` 3조합(off/agent-only/both).
  **라이브 부분**: 이미지 재빌드→`kind load`→`pa-platform-agent-webhook` 롤아웃→**인클러스터 파드에서
  `POST /canary/judge` 200**, `verdict=unknown confidence=0.00`("refusing to promote on an untrustworthy
  judgment") — 인클러스터엔 모델이 없어 휴리스틱 폴백이고 **"판단 불가 ≠ 승인"이 실제로 동작**함을 보여줌.
- Blockers: canary 전체 E2E 미실행(중단). 재개 시 `helm upgrade --set agentAnalysis.enabled=true` 후 canary를
  돌리면 AnalysisRun이 unknown→실패→abort하는 경로를 볼 수 있음. 단 **인클러스터 analyzer에 모델이 없어
  현재는 모든 판정이 unknown** — pass 경로를 라이브로 보려면 클러스터에서 도달 가능한 LLM 엔드포인트 필요.
- 설계 메모: 판정 3규칙이 전부 안전한 방향 기본값 — 신호없음→pass, **저신뢰→unknown(P1보다 우선)**, P1/P2→fail.
  `successCondition: result == "pass"`라 unknown은 승격시키지 않는다. 게이트는 **분석만**(execute=False):
  remediation 가능한 릴리스 게이트는 곧 리뷰 없는 remediation.
- Next: push 승인 시 Phase 1b 핸드오프(rollouts-demo) · 그 전엔 canary E2E 재개 또는 Phase 2.

## 2026-07-26 — 핸드오프 프리플라이트 + 인시던트→트레이스 딥링크 (gate 1058→1095)

- Status: Phase 1b 잔여(no-churn 핸드오프)를 **안전하게** 진행하기 위한 프리플라이트를 먼저 만들고,
  ②의 잔여였던 딥링크를 소진. 핸드오프 자체는 블로커 2종이 남아 의도적으로 실행하지 않음.
- Changed: **프리플라이트**(`e48c5f6`) `platform/handoff.py` + `scripts/preflight_gitops_handoff.py`(읽기 전용,
  4검사 + 롤백 명령 선출력). **딥링크**(`90a92ba`) `trace_id`를 파이프라인→`record_incident`→대시보드
  `Incident`→상세 페이지까지 관통 + `trace-links.ts`(prod-safe).
- Verified: `make check` **1079**(+21) → **1095**(+16) · `tsc` 클린.
  **프리플라이트 라이브 read-only**(9 릴리스 중 4): **ownership은 전부 통과**(loki 12·pa 6·tempo 4·demo 2
  리소스) — 최대 미지수였던 "채택이 될까"가 해소. **딥링크 라이브**: pipeline trace_id == record trace_id →
  Tempo `/api/traces/<id>` **HTTP 200**, span 4개(analyze가 wall clock의 85%).
- Blockers: **핸드오프 미실행, 이유 2가지**: (1) loki/tempo/pa가 데이터 보유 → 스냅샷 수단 선행
  (kind엔 CSI 스냅샷터 기본 부재), (2) 로컬이 origin ahead → 엔진은 **리모트**를 동기화하므로 지금 채택하면
  옛 차트 내용이 적용되고 그 churn이 채택 실패로 오독됨(push는 사용자 게이트).
- 품질 메모: 프리플라이트 첫 버전이 Pod/ReplicaSet까지 판정해 loki에 오탐 BLOCKED를 냈다 →
  `ownerReferences`로 파생 객체 제외. 수집기도 라벨 셀렉터→`helm get manifest` 열거로 교체
  (차트가 instance 라벨을 안 붙이면 "리소스 없음"이 블로커로 오독 — rollouts-demo가 그 케이스).
  **늑대 소년이 된 체커는 무시당하고, 그게 체커가 없는 것보다 나쁘다.**
- Next: push 후 `rollouts-demo`(데이터 위험 0)로 no-churn 채택 라이브 → 스냅샷 수단 확보 후 stateful 3건.

## 2026-07-26 — 사후검증 provider 실행부 + Phase 1b delivery 어댑터 2개 (gate 1017→1058)

- Status: ③(사후검증)과 Phase 1b(어댑터)를 연달아 소진. 둘 다 "하나만으로는 검증이 안 되는" 구조를 의도적으로
  깨는 작업 — ③은 dispatched≠verified, 1b는 엔진 1개면 추상이 자기 자신에 들어맞는 문제.
- Changed: **③**(`d68fe6b`) `operations/runners/onprem_verify.py` 신설(rollout status / readyReplicas /
  node unschedulable, **액션과 동일한 스코프 자격증명으로 읽기 전용**) + executor가 실행된 액션마다 검증해
  `resolution_verdict(executed, skipped, verifications)`로 집계. **Phase 1b**(`738c812`)
  `platform/adapters/{argocd,flux}.py` + 레지스트리(`get_delivery_adapter`).
- Verified: `make check` **1035**(③, +18) → **1058**(1b, +23).
  **③ 라이브 양방향**(`docs/evidence/onprem-verification-e2e.log`): healthy 워크로드 → dispatched=True
  verified=True resolved=True / broken 워크로드(잘못된 이미지+progressDeadline 30s) → **dispatched=True인데
  verified=False resolved=False** — 이전엔 True로 보고됐을 케이스.
- Blockers: 없음. **의미 오류 1건을 테스트가 잡음**: log-only 모드에서 검증을 돌리면 "실행 안 함"이
  "실행했는데 실패"로 뒤집혀 기본 설정의 모든 인시던트가 resolved=False가 된다 → log-only는 검증 스킵.
- 설계 메모(1b): 두 엔진이 **순서 원시형**(sync-wave 문자열 ↔ dependsOn 객체 참조)·**상태 어휘**(Argo 2필드 ↔
  Flux `Ready` 1조건이라 매핑이 lossy; not-ready를 drifted로 만들면 정보 발명)·**객체 형태**(Application 1개 ↔
  HelmRelease 조합이라 render가 리스트 반환)에서 불일치 — 계약이 argocd-shaped가 아님을 이걸로 압박.
- Next: Phase 1b 잔여(레지스트리→어댑터 팬아웃 실 apply + **TF↔GitOps no-churn 핸드오프 라이브**, PVC 스냅샷 선행).

## 2026-07-26 — Phase 1a 자격증명 격리 + 런북 전량 무력화 결함 근본수정 (gate 983→1017)

- Status: 계획의 **최우선 불변식**(자격증명이 경계) 구현·라이브 증명 완료. 그 과정에서 라이브가 표면화한
  프로덕션 결함 1건도 근본수정 — 두 건 모두 "코드는 건강해 보이는데 실제로는 동작 안 함" 부류.
- Changed: **Phase 1a**(`0bb993f`) `platform/scope.py` 신설(`IncidentScope`·provenance 바인딩 `TokenBroker`)
  + `NormalizedIncident.tenant/env` 1급 필드 + onprem 어댑터 라벨 승격 + `_run_external_action→run_onprem_action`
  scope 관통 + **`_run_kubectl`의 ambient 경로 삭제**(scope 없는 live는 거부). **Decimal 결함**(`b078094`)
  `_is_integer_like`+`normalise_runbook`을 DynamoDB 읽기 경계에 적용.
- Verified: `make check` **1007**(Phase 1a, +24) → **1017**(Decimal 수정, +10).
  **Phase 1a 라이브 DoD**(kind $0, per-tenant SA+RBAC+1h 토큰): acme→acme 실행 성공 / acme→globex 거부 /
  **advisory 가드를 끄면 API 서버 `Forbidden`**(라벨이 아니라 RBAC가 막는다는 결정적 증거) / 위조 tenant 발급
  거부 / scope 없는 live 거부. 증거 `docs/evidence/phase1a-credential-isolation.log`.
  **Decimal 결함 before/after**(동일 알럿): `generic-recovery`(알림만) → **`eks-pod-oom`**(restart+scale, rto=180),
  후보 1/5 → **5/5** 유효. 증거 `docs/evidence/runbook-decimal-rto-fix.log`.
- Blockers: 없음. 기존 러너 테스트 10건이 깨진 건 **의도한 새 동작**(ambient 경로 제거)이라 불변식을 약화시키지
  않고 테스트에 scope를 주입해 갱신.
- 진단 메모: Decimal 결함의 **첫 가설(내 verify 슬롯 회귀)은 오진**이었다 — 거부된 4개에 손대지 않은 런북이
  포함돼 기각하고, 라이브 테이블을 직접 스캔해 `rto_sec must be an integer or null` 한 줄로 좁혔다.
  `isinstance(Decimal(180), int)`가 False라 rto_sec을 선언한 모든 런북이 탈락, rto=null인 generic-recovery만 생존.
  2026-07-19 approval_bridge Decimal 결함(쓰기 방향)과 같은 부류의 읽기 방향 재발.
- Next: Phase 1b(delivery 어댑터 2개 + no-churn 핸드오프 + sync-wave 순서 보장) · ③ provider측 verify(차단 해소됨).

## 2026-07-26 — 라이브 실증 3건 완주 (canary 자동판정 · Tempo 트레이스 · NetworkPolicy 집행)

- Status: Docker/kind 기동해 기본 OFF로 남겨둔 3건을 전부 실증. 클러스터·애드온은 정지 상태였을 뿐 온전해
  재구축 불요(노드 3/3, 애드온 37파드). 게이트 수는 무변경(**983**) — 라이브 실증이라 코드 계약 불변.
- Changed(`b07523b`): `var.rollouts_demo_analysis_enabled`/`_prometheus_address` + set 블록(켜기가 차트 수정이
  아니라 terraform 변수) · 검증기 버그 2건 수정 · 두 values에 검증 결과·잔여 이유 명기 · 증거 3종 추가.
- Verified (라이브 $0, kind k8s v1.34.0): **①양방향** — 나쁜 canary(컨테이너 `exit 1` 패치)는 측정값 2→3→3으로
  `failed(3)>failureLimit(2)` → **사람 개입 0, ~105s auto-abort**(Degraded/RolloutAborted), **stable RS 4/4 유지**;
  좋은 canary(yellow→red)는 측정값 0으로 3연속 Successful → **abort 안 되고** 수동 게이트 정지 → promote로 stable.
  음성만 봤으면 "전부 abort하는 기계"를 못 걸렀음. **②** tempo-0 1/1·resources 25m·Service 3200(=`helm template`이
  잡은 수정 2건이 옳았음 확증), Tempo query API 200 + Grafana 프록시 200, span 분해 **detect 0.3 / analyze 4135.6 /
  decide 890.1 / root 5026.2ms → MTTR의 82%가 로컬 LLM**. **⑥** kindnet **ENFORCED**, 차트 정책으로 same-tenant
  REACHABLE·cross-tenant BLOCKED(적용 전엔 둘 다 REACHABLE).
- Blockers: 없음. 함정 2건 기록 — (a) `-target=helm_release.tempo`만 apply하면 Grafana 데이터소스가 안 생김
  (데이터소스는 kps values 소유) → kps도 apply. (b) `kubectl set image rollout/...`은 Rollout CRD를 모름 → patch 사용.
- Next: Phase 1a(자격증명 격리). **신규 백로그**: capability 런북이 decision에서 사용 불가(시드 `alarm_name` 누락 +
  `CAPABILITY_RUNBOOKS` 9개 전부 base 스키마 미통과 → OOMKilled가 알림으로 폴백). 내 변경과 무관한 기존 결함.
