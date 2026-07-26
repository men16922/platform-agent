# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-26

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-26 — Phase 2: ⑥ 활성화 + push 수집기 + 대시보드 스위처 (gate 1216→1251)

- Status: Phase 2 잔여 3건 소진. ⑥은 "네임스페이스가 없어서" 막혀 있던 게 아니었다 —
  차트가 애초에 **켤 수 있는 물건이 아니었다**.
- Changed(`3dbc572`): tenancy-netpol 차트 폐기 → NetworkPolicy를 네임스페이스와 같은
  호출(`namespaces_for`)에서 렌더(정책 집합=네임스페이스 집합이 구성상 동일) ·
  `PROVEN_ENFORCING_SUBSTRATES`(실험으로 증명된 기판에만 렌더, k3s는 0개+exit 1로 신고) ·
  apply 순서 근본수정(Tenant→Namespace→RBAC→NetworkPolicy) · `verify_tenant_isolation.py` 신규.
- Changed(`b2b52fc`): `platform/collector.py`(레지스트리 선언 기준 행 생성, MISSING≠UNKNOWN,
  HMAC 신원=검증한 키, 서명자 스코프 밖 row 거부, 수신시각 기준 staleness→UNKNOWN 강등) ·
  허브 엔드포인트 2개(`local_deploy_api`) · `push_addon_status.py`(스포크) ·
  대시보드 `/api/dashboard/platform/status` + `PlatformTenantSwitcher`.
- Verified: `make check` **1251**(+35). `tsc --noEmit` 클린 · `next build` 성공.
  **라이브(kind, $0)**: 정책 5개 적용 후 4종 전부 통과(same-tenant 통과/cross 차단/kubelet
  프로브 생존/DNS 무영향) · 스포크→허브→대시보드 왕복, 어댑터가 렌더한 실 Application이
  missing→progressing→healthy로 이동, 잘못된 키 401, 허브 종료 시 connected=false.
  증거 `docs/evidence/phase2-{netpol-activation,push-collector-and-switcher}.log`.
- Blockers: 없음. 라이브가 새로 연 갭 2건은 NEXT_PLAN으로 분리(클러스터 싱글턴 백엔드 ·
  Application 삭제 시 워크로드 고아).
- 품질 메모: 세 번 다 **"테스트가 초록인 채로 아무 효과가 없는 코드"** 였고, 매번 다른
  층이었다. (1) 차트: tenants×envs×capabilities 16개를 렌더하는데 레지스트리 구독은 6개고,
  설치하는 helm_release가 아예 없었다 — 정합 테스트는 `chart ⊆ registry` 부분집합이라 통과.
  (2) apply 순서: 유닛 26개가 객체의 **집합**만 단언하고 순서를 안 봐서, 새 테넌트를 한 번에
  apply하자 Capsule webhook이 거부했다. (3) DNS 근거: 차트는 `kube-system` 허용을 "DNS 때문"
  이라 적었는데 ingress-only 정책은 egress를 건드리지 않는다 — 빼고 실측하니 해석 정상.
  반증 시도도 실패했고 그게 더 유익했다: 피어 네임스페이스에 라벨을 붙였더니 **Capsule이
  되돌렸다**(선택자가 되는 라벨은 테넌트 안에서 조작 불가). 검증기 자신의 가짜 초록도 1건
  고쳤다 — `agnhost dns-suffix`는 질의를 보내지 않아 DNS가 죽어도 exit 0이다.
- Next: 클러스터 싱글턴 capability의 scope 축 · faked managed 디스크립터(applicable=false) ·
  DR 재구축 확인 · Phase 1b 잔여(스냅샷 선행). `/tidy-docs` 시점(LOG 예산 초과).

## 2026-07-26 — Phase 2 첫 슬라이스: soft-tier tenancy + Capsule (gate 1191→1216)

- Status: ⑥(NetworkPolicy·PSS)이 기다리던 산출물 — tenant 라벨이 붙은 `<prefix>-<env>-<capability>`
  네임스페이스 — 를 레지스트리에서 렌더·적용. 문서 정리(`/tidy-docs`) 선행 완료.
- Changed(`440f3a0`): `platform/tenancy.py`(Namespace+Capsule Tenant+네임스페이스 스코프 RBAC,
  soft 티어만) · `scripts/render_tenancy.py`(CRD 부재를 exit 1로 신고) · 애드온 모듈에 Capsule
  추가(기본 OFF·0.13.10 핀·cert-manager 비의존). 앞서 `/tidy-docs`로 LOG 188→91, PLAN 138→65.
- Verified: `make check` **1216**(+25). **라이브(kind, $0)**: Tenant NAMESPACE COUNT=4 ·
  네임스페이스에 `platform-agent.io/tenant`+PSS restricted 라벨 · 쿼터 합산 실증.
  증거 `docs/evidence/phase2-tenancy-capsule.log`.
- Blockers: 없음. Phase 2 잔여 = ⑥ 실제 활성화 · 대시보드 tenant/env 스위처 · push 기반 2축 drift
  수집기 · faked managed 디스크립터(applicable=false) · DR 재구축 확인.
- 품질 메모: 라이브가 3건을 잡았고 셋 다 "그럴듯한 구현이 조용히 거짓 보증을 만드는" 자리였다.
  (1) 소유자 표기 — 유닛 테스트는 **내가 지어낸 형태**만 단언해 초록이었다. (2) **Capsule은 admin이
  만든 네임스페이스를 채택하지 않는다** → Tenant는 Active/reconciled인데 NAMESPACE COUNT=0, 즉
  테넌트는 살아 있고 쿼터는 아무것도 안 묶는데 상태 화면은 정상으로 보인다. (3) **쿼터 합산은 정적
  조회로는 "고장"으로 보인다** — 네 네임스페이스 각각 16이라 4배로 읽히고 나도 그렇게 결론냈다.
  소비 실험을 하니 `limited: 6`(=16−10)으로 잔여가 재기록되고 두 번째 요청이 거부됐다.
  **설계는 옳았고 내 첫 결론이 틀렸다 — 정지 상태 조회가 아니라 소비가 사실을 말한다.**
- Next: Phase 2 잔여(⑥ 활성화 → 대시보드 스위처 → push 수집기).

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
