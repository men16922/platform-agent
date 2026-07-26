# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-26

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-26 — capability scope 축: 클러스터 싱글턴 렌더 거부 (gate 1251→1267)

- Status: 직전 라이브가 낸 사고(컨트롤러 2개가 같은 Rollout을 조정)를 닫았다. STATUS에
  "렌더 결과를 그대로 적용하지 말 것"으로 남겨뒀던 리스크가 해소됐다.
- Changed(`bb7a819`): 카탈로그에 capability별 `scope: cluster|namespace` ·
  `reject_cluster_singletons`를 **delivery 계약**에 배치(엔진마다 복제하면 세 번째 엔진이
  빠뜨린다) · 수집기가 공유 설치물을 테넌트 drift로 세지 않음(`applicable=False`, 안 보이면
  MISSING 아니라 UNKNOWN) · 대시보드 sync 칸에 "shared" 표기 · 미선언은 cluster로 fail-safe.
- Verified: `make check` **1267**(+16) · `tsc --noEmit` 클린. **라이브**: 사고를 낸 그
  매니페스트를 argocd·flux 둘 다 거부하고 namespace scope 2개(logging/tracing)는 정상 렌더 ·
  재푸시 결과가 4행 전부 missing에서 (2 진짜 missing / 2 shared-unknown)으로 정직해짐.
  증거 `docs/evidence/phase2-capability-scope.log`.
- Blockers: 없음.
- 품질 메모: **내 첫 구현이 게이트를 27 errors로 깨뜨렸다.** scope 누락을
  `validate_registry`의 problem으로 올렸는데, 로더가 fail-closed라 이 필드가 생기기 전에
  쓰인 최소 카탈로그가 전부 로드 자체를 거부했다 — 문서 공백을 "플랫폼 뷰가 아예 안 뜸"으로
  바꾼 셈이고, 막으려던 실패보다 나쁘다. 게다가 **가드는 이미 다른 곳에 있었다**(fail-safe
  기본값 cluster → 어댑터가 거부). 부재는 리포팅으로 내리고 **오값만** 거부한다 —
  부재는 공백이지만 오값은 주장이고, 주장은 믿긴다.
- Next: ArgoCD Application 삭제 시 워크로드 고아(파이널라이저) · faked managed 디스크립터
  (`applicable=false`) · DR 재구축 확인.

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
