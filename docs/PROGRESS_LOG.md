# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-26

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-26 — capability step을 executor가 실제로 소비 (gate 1168→1191)

- Status: `capability_schema`가 표현할 수 있던 순서·조건·on_failure·per-step verify를 **아무도 읽지 않던**
  갭을 해소. 고친 것 4개인데 **뒤의 둘은 앞을 고쳐야 보이는 종류**였다.
- Changed(`c4816fd`): `DecisionOutput.steps`(기본 []=기존 동작) + `_resolve_runbook_steps` +
  executor `_run_capability_steps`(조건 평가·on_failure·선언된 verify 우선) + `resolution_verdict`에
  `not_applicable` 축. `CAPABILITY_RUNBOOKS`를 해석 경계에서 연결(row가 이기고 없으면 카탈로그가 채움).
- Verified: `make check` **1191**(+23). **라이브 인-프로세스 before/after**(같은 알럿):
  before `executed=[restart, scale] skipped=[]` — 필요 없는 노드 스케일아웃 /
  after `executed=[restart] skipped=[scale] resolved=True`.
  증거 `docs/evidence/capability-steps-executor-wiring.log`.
- Blockers: 없음. 미완(의도적): CAPABILITY_RUNBOOKS의 4개(certificate-expiry·disk-full·
  health-check-failure·network-latency-high)는 BUILTIN_RUNBOOKS에 없어 여전히 선택 불가 — 별도 갭.
- 품질 메모: **유닛 테스트가 구조적으로 못 잡는 결함**을 만났다. `_deserialise_decision`이 `steps`를
  버려서 executor가 조용히 flat 경로로 되돌아갔는데, 유닛 테스트는 전부 DecisionOutput을 **메모리에서**
  만들어 그 경계를 안 넘는다. 실제 파이프라인을 한 번 돌리자 즉시 드러났다(성공한 restart 뒤에
  `previous_step_failed: True` 조건의 scale이 실행됨). **선언하는 것과 경계를 건너 실어 나르는 것은
  다른 문제이고, 프로덕션에서 도는 건 후자다.** 그 다음 층도 같은 부류였다 — 조건이 적용되자 이번엔
  런북의 *성공* 경로가 `resolved=False`가 됐다(log-only에서 배운 뒤집힘의 재발). 조건 스킵은
  "안 하기로 올바르게 판단함"이지 "하려다 못 함"이 아니다.
- Next: Phase 2(Capsule+RBAC+대시보드 tenant/env 스위처+2축 drift 폴러). `/tidy-docs` 필요(LOG 예산 초과).

## 2026-07-26 — Phase 1b 핸드오프 실행 + 프리플라이트 5번째 검사 (gate 1159→1168)

- Status: 사용자가 `terraform state rm`을 실행해 마지막 블로커가 풀렸고, rollouts-demo 소유권을
  **Terraform → ArgoCD로 이관 완료**. 그 과정에서 프리플라이트의 실제 갭이 드러나 검사 1개를 추가.
- Changed(`7033db3`): `check_live_matches_rendered` + `diff_live_against_rendered`(단방향 비교 —
  라이브의 추가 필드는 서버 기본값이고, 엔진 자신의 `tracking-id`는 제외. 매번 발화하는 체커는 무시당한다) +
  스크립트가 `helm get manifest`와 라이브 객체를 대조해 drift를 수집.
- Verified: `make check` **1168**(+9). 라이브 — plan `1 to add, 0 to change, **0 to destroy**`(helm uninstall
  없음) · ArgoCD **Synced/Healthy** · TF 소유는 `rollouts_demo_app[0]`(소유 기록)뿐 · **helm rev 8 불변**
  (baseline 검사가 요구한 그것) · **Rollout/Service UID·clusterIP 불변**(재생성 아님) · **selfHeal 4→2→4 ~40s**.
- Blockers: loki/tempo/pa는 데이터 보유 → **스냅샷 수단 선행**(kind엔 CSI 스냅샷터 부재). 미이관.
- 품질 메모: **4검사가 다 통과했는데 채택이 no-op이 아니었다** — canary가 돌고 새 RS가 생겼다. 파보니
  핸드오프 잘못이 아니라 라이브 Rollout이 `ports`·`resources.requests`를 잃은 상태였고 ArgoCD가 그걸
  **복구**한 것. 범인은 이 세션의 내 `kubectl patch --type=merge` — JSON merge patch라 **배열을 통째
  교체**해서 name+image만 남기고 나머지를 날린다(strategic merge였다면 name 키로 병합). 티도 안 났다:
  readinessProbe가 없어 파드는 Ready였고 Service의 `targetPort: http`는 해석 대상이 없었다.
  새 검사를 **non-blocking**으로 둔 이유 — 채택은 어차피 매니페스트를 다시 주장하므로 드리프트 자체는
  위험하지 않다. 위험한 건 예상 못 한 churn이 "핸드오프가 망가뜨렸다"로 읽혀 롤백을 부르는 것.
  라이브 시연을 시도했더니 몇 초 만에 드리프트가 사라졌는데, 그건 검사 실패가 아니라 **selfHeal이 먼저
  고친 것**(= 채택 성공의 증거). 검사가 의미 있는 시점은 프리플라이트를 실제로 도는 상태(TF 소유,
  연속 조정 없음)라 유닛 가드로 고정했다. 증거 `docs/evidence/gitops-handoff-preflight.log`.
- Next: Phase 2(Capsule+RBAC+대시보드 tenant/env 스위처+2축 drift 폴러) 또는 capability step 런북을
  executor가 실제 소비. `/tidy-docs` 시점(LOG 예산 초과).

## 2026-07-26 — ① 게이트 완결(3종 판별) + ⑥ PSS/Cosign + ⑦ 스위퍼 CronJob (gate 1114→1159)

- Status: 승인받은 잔여 4건을 한 세션에 소진. **origin push 완료**(4커밋, `5015810`). ①은 "막는다"만
  증명된 상태였는데, pass 경로를 여는 과정에서 **연쇄 결함 3건**이 드러나 전부 근본수정 → 이제 게이트가
  실제로 **가려낸다**. 각 결함은 앞 결함을 고쳐야 보이는 종류라 순서대로 기록(증거 로그가 그 순서를 보존).
- Changed(`8e549bf`): stage 2를 addons 모듈 변수로 노출(`rollouts_demo_agent_analysis_enabled`/`_url`).
  차트 값만 있고 TF 배선이 없어 `helm --set`이 유일한 경로였고 그건 state 밖 드리프트였다.
  (`d96b888`): **analyzer 모델 배선** — `llm.endpoint`를 router(기본 OFF)만 소비하고 webhook은 못 받아
  조용히 휴리스틱 폴백(confidence 0.0=모든 판정 unknown)이던 것. **⑦ 스위퍼 정직성** — `_run_json`이
  실패를 None으로 삼켜 CLI 부재가 "clean(exit 0)"이 되던 것 → `ProviderUnavailable`+**exit 2**.
  **⑥ PSS** — Dockerfile `USER 10001`+`scripts/` COPY(없어서 CronJob이 깨질 뻔) + 3 워크로드 공통
  securityContext. **⑥ Cosign** — `verify_image_signature.py`(0/1/2) + 차트 `image.digest`.
  (`69f149d`): **게이트가 판정할 신호를 스스로 만들던 문제** — 템플릿이 `CanaryUnderJudgement` firing
  알럿을 **합성**해 보내 analyzer가 당연히 문제를 찾음(정상 canary가 conf 0.80으로 `fail`).
  호출자는 **신원만**(namespace+podPrefix), 게이트가 Alertmanager를 직접 조회. `None`(못 봄)과
  `[]`(봤는데 조용함)을 엄격히 분리. (`5015810`): **알럿 시간 스케일** — kps 파드 룰이 `for: 15m`이라
  2~3분짜리 canary엔 영영 발화 안 함 → 크래시 canary도 pass. 차트가 `CanaryPodRestarting`(for 30s,
  interval 15s, ns 한정, warning) 동봉. Chart.yaml 0.2.0(helm provider는 파일이 아니라 메타데이터를 diff).
- Verified: `make check` **1114 → 1118 → 1146 → 1159**(+45). `terraform validate` Success · `helm template` ·
  `helm lint`. **라이브(kind, $0)** — ① 3종 판별: 정상 canary `pass`x3 → abort 안 됨(수동 게이트 대기) /
  크래시 canary `pass→fail→fail` → **165s auto-abort**, stable 4/4·Available=True 내내 / 관측 불가 →
  `unknown` 차단. 판정자 독립 스위치(stage1 OFF일 때 템플릿 1개만 설치)도 확인.
  **⑥ 양방향**: 비준수 설치 → API 서버가 4개 위반 적시하며 `forbidden`(Replicas 0/1) / 준수 설치 →
  Running `uid=10001(app)`; PVC 조합 별도 확인(WRITE OK). **⑥ Cosign**: 서명→VERIFIED / 다른 이미지를
  같은 repo:tag → `no signatures found`. **⑦**: 컨테이너 안에서 `COVERAGE INCOMPLETE … exit 2`.
  증거 `docs/evidence/onprem-{canary-agent-gate,pss-restricted-and-sweeper}-e2e.log`.
- Blockers: **Phase 1b 핸드오프 미완** — 프리플라이트는 push 후 **4검사 전부 통과(SAFE TO PROCEED)**,
  배선(범용 `argocd-app` 래퍼 차트 + `rollouts_demo_gitops_owned` count 토글)도 완료. 남은 단계
  `terraform state rm helm_release.rollouts_demo`가 **권한 정책에 차단**돼 사용자가 직접 실행해야 함
  (우회 시도 안 함). 그 뒤 `terraform apply -var rollouts_demo_gitops_owned=true`.
- 품질 메모: 세 결함이 전부 **"체커가 확인 못 한 것을 통과로 보고"** 같은 형태였다 — 모델 없이 `unknown`,
  CLI 없이 `clean`, cosign 없이 pass. 반대로 ①의 두 번째 결함은 **확인 못 한 걸 실패로 보고**하는 형태라
  더 위험했다: 정상 릴리스를 그럴듯한 이유로 전부 막는 게이트는 사람이 곧 무시하고, 그게 게이트가 없는
  것보다 나쁘다. Cosign에선 도구가 내 대조군을 정정했다 — 서명은 태그가 아니라 **다이제스트**에 붙는다.
- Next: (사용자) `terraform state rm` → 핸드오프 라이브. 그 외 Phase 2(Capsule+대시보드 스위처) ·
  capability step 런북을 executor가 실제 소비 · ② executor span.

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
