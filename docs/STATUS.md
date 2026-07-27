# STATUS — platform-agent

최종 갱신: 2026-07-28

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- `make check` (pytest) → **1355 passed, 1 skipped** (2026-07-27, 1341→1355, +14) — **Phase 3①
  자격증명 격리 full**(`bb091e1`): 가드가 `scope.py` 한 곳(`guard_scoped_action`)이고 세 러너가
  같은 구현을 부른다 · `resolve_incident_scope` 이관으로 **GCP Cloud Workflows 경로의 스코프 부재**
  해소(디스패치 경로가 둘인데 로직이 `aws/executor.py`에만 있었다) · seam이 전 분기에 전달하고
  네 번째 클라우드를 스코프 없이 추가하면 구조 가드가 실패한다. **라이브가 Phase 1a 증명의 구멍을
  적발**: `render_rbac`가 바인딩 대상 SA를 렌더하지 않아 **RoleBinding이 없는 SA를 가리키고
  있었다**(fail-closed라 안 드러남 → RBAC 팔이 한 번도 행사된 적 없음). **라이브(kind, $0)**:
  실 토큰으로 자기 ns `yes` / 이웃 테넌트·클러스터 스코프 `Forbidden`(**API 서버**가 판정) ·
  실 러너 in-scope 재시작 성공 · gcp/azure 4케이스 인증·네트워크 이전 거부.
  증거 `docs/evidence/phase3-scoped-credentials-all-runners.log`.
- `make check` (pytest) → **1341 passed, 1 skipped** (2026-07-26, 1322→1341, +19) — **자연어가 테넌트를
  세운다 + 풀스택 30초 영상**: 에이전트 도구 2개 신설(`tenancy_tools.py` = `setup_tenancy` ·
  `install_tenant_addons`)로 "레지스트리에 다 적혀 있는데 사람만 적용할 수 있던" 마지막 두 걸음 해소.
  `cluster_io.py`가 렌더된 객체가 클러스터를 만지는 유일한 자리이고, `render_*` 스크립트와 **같은
  구현**을 쓴다(복사본 0, `render_tenancy.py` 출력이 HEAD와 완전 동일함을 대조로 증명). 자연어 도구는
  되물을 수 없으므로 **kubectl 컨텍스트 ≠ 레지스트리 클러스터면 아무것도 쓰지 않고 거부**.
  **라이브(실제 브라우저)**: 빈칸 → 문장 1줄 → 체인 2단(17.6s) → `4 / 4`·4축 ✓ → `1500m / 16` →
  실제 ArgoCD Synced/Healthy → netpol 1개 삭제 시 network만 ✕(globex 무영향) → 복구 ✓.
  영상 `docs/post/media/multitenancy-fullstack-30s.mp4`(30.03s, 오버레이 없음, 원본 153.8s→10컷).
  라이브가 결함 4건 적발(경고→실패 오기록 · 도구 완료 오판정 · 녹화 세션 부재 · 자격증명 파일).
- `make check` (pytest) → **1322 passed, 1 skipped** (2026-07-26, 1302→1322, +20) — **시연 가능 레벨**: 영상 시나리오를 격리 반증으로 재작성하고 그 대본이 찍히는 상태까지 구축. 준비가 구조적 갭을 드러냄 — repo URL이 TF에만 있어 **레지스트리만으로는 애드온을 설치할 수 없었다**(매 라이브 설치가 손으로 조립됨) → 카탈로그 `self_hosted_repo`(유일한 복사, TF 대조 가드로 안전화) + `scripts/render_addons.py` + `make demo-baseline`. **라이브**: 테넌트 스코프 loki+tempo Synced/Healthy(쿼터가 소비를 셈 cpu 2/16), netpol 1/4 삭제 시 network 축만 ✕·이웃 테넌트 무영향·복구 시 ✓, 실측 지연 18s/61s/59s. 증거 `docs/evidence/demo-isolation-falsification.log`.
- `make check` (pytest) → **1302 passed, 1 skipped** (2026-07-26, 1290→1302, +12) — **대시보드 멀티테넌시 관제 + 검증 훅**(`654c7e5`·`eebc19e`·`bad2642`): 격리 4축·티어·쿼터·네임스페이스를 **기존 push 경로**에 실어 대시보드로(직접 조회는 D26 위반) · 플릿 표 + 티어별 분리/공유/미보장 명시 · Add-ons 누락 4건(Loki·Fluent Bit·Tempo·Capsule) 추가 · Stop 훅 `make check` + PostToolUse 훅 `tsc`. **라이브 반증**: NetworkPolicy 삭제 시 network 축이 False로 뒤집히고 복구 시 True. `tsc` 클린 · `next build` 성공.
- `make check` (pytest) → **1290 passed, 1 skipped** (2026-07-26, 1281→1290, +9) — **Phase 2 완결(M11)**(`c6d930d`): managed 백엔드는 카탈로그에서 파생해 `applicable=false`(조회 안 한 백엔드에 health를 단언하지 않는다, faked 디스크립터로 과금 0 증명) · **DR 드릴** globex/dev 실제 파괴 후 레지스트리만으로 재구축(라벨 완전 동일, 10초 뒤 쿼터 선언값 일치) · 채택 검증기 신설. 증거 `docs/evidence/phase2-managed-and-dr.log`.
- `make check` (pytest) → **1281 passed, 1 skipped** (2026-07-26, 1271→1281, +10) — **어댑터 helm values seam**(`01d3c6d`): 카탈로그가 values 파일을 가리키고(복사 금지) 두 엔진이 같은 dict를 싣는다. 라이브가 결함 2건을 더 드러냈다 — **PSS restricted 테넌트 네임스페이스가 우리 애드온을 거부**(Argo는 Synced/Progressing인데 파드 0개; `monitoring`엔 PSS 라벨이 없어 지금까지 안 보였다) · **구독 해지가 테넌트 데이터를 파괴**(차트가 `whenDeleted: Delete`로 k8s 기본값 Retain을 뒤집음). 둘 다 근본수정. **라이브**: acme-dev-logging이 PSS+쿼터+NetworkPolicy 아래 Synced/Healthy — Phase 2 첫 진짜 테넌트 스코프 설치. 증거 `docs/evidence/phase2-values-seam.log`.
- `make check` (pytest) → **1271 passed, 1 skipped** (2026-07-26, 1267→1271, +4) — **삭제 cascade**(`e1ea15f`): 계약이 삭제 의미를 말하게 하고(Flux=uninstall vs ArgoCD=고아라 같은 의도가 엔진마다 반대 결과) argocd 렌더러가 resources-finalizer를 붙인다. **라이브 A/B**: 파이널라이저만 다른 Application 2개를 삭제 → 있는 쪽 소멸, 없는 쪽은 소유자 없이 Running. 덮지 않는 것: StatefulSet PVC는 남는다. 증거 `docs/evidence/phase2-deletion-cascade.log`.
- `make check` (pytest) → **1267 passed, 1 skipped** (2026-07-26, 1251→1267, +16) — **capability scope 축**(`bb7a819`): 카탈로그에 `scope: cluster|namespace`를 두고 delivery **계약**이 클러스터 싱글턴의 테넌트별 렌더를 거부한다(엔진마다 복제하면 세 번째 엔진이 빠뜨린다). 수집기는 공유 설치물을 테넌트 drift로 세지 않고(`applicable=False`), 안 보이면 MISSING이 아니라 UNKNOWN. 미선언은 cluster로 fail-safe. **라이브**: 직전 세션에 컨트롤러 충돌을 냈던 그 매니페스트를 argocd·flux 둘 다 거부, namespace scope 2개는 정상 렌더. 증거 `docs/evidence/phase2-capability-scope.log`.
- `make check` (pytest) → **1251 passed, 1 skipped** (2026-07-26, 1216→1251, +35) — **Phase 2 잔여 3건: ⑥ NetworkPolicy 실제 활성화 + push 기반 2축 drift 수집기 + 대시보드 tenant/env 스위처**(`3dbc572`·`b2b52fc`). ⑥이 막혀 있던 진짜 이유는 네임스페이스 부재가 아니라 **차트가 켤 수 있는 물건이 아니었던 것**(16개 데카르트 곱 vs 레지스트리 구독 6개, 설치하는 helm_release 없음) → 레지스트리 기반 렌더링으로 대체하고 집행이 증명된 기판에만 렌더. 수집기는 push 전용이라 허브에 스포크 read 자격증명이 0이고, 신원은 서명을 검증한 키다. **라이브(kind, $0)**: 정책 5개 + 격리 4종 통과 · 스포크→허브→대시보드 왕복 실증. `tsc` 클린 · `next build` 성공. 증거 `docs/evidence/phase2-{netpol-activation,push-collector-and-switcher}.log`.
- `make check` (pytest) → **1216 passed, 1 skipped** (2026-07-26, 1191→1216, +25) — **Phase 2 첫 슬라이스: soft-tier tenancy + Capsule**(`440f3a0`). ⑥이 기다리던 tenant 라벨 네임스페이스를 레지스트리에서 렌더·적용. 라이브가 3건을 잡았고 셋 다 거짓 보증 자리 — 특히 **Capsule은 admin이 만든 네임스페이스를 채택하지 않아** Tenant가 Active인데 NAMESPACE COUNT=0(쿼터가 아무것도 안 묶는데 정상으로 보임), 그리고 **쿼터 합산은 정적 조회로는 4배 버그처럼 보이지만** 소비하면 `limited: 6`(=16−10)으로 잔여가 재기록된다(설계는 옳았고 내 첫 결론이 틀렸다).
- `make check` (pytest) → **1191 passed, 1 skipped** (2026-07-26, 1168→1191, +23) — **capability step을 executor가 실제 소비**(`c4816fd`). 스키마가 표현하던 순서·조건·on_failure·per-step verify를 아무도 읽지 않던 갭 해소 + `CAPABILITY_RUNBOOKS`(9런북, 죽은 데이터였음) 연결. **유닛 테스트가 구조적으로 못 잡는 결함 1건 포함**: `_deserialise_decision`이 `steps`를 버려 executor가 조용히 flat 경로로 회귀 — 유닛 테스트는 객체를 메모리에서 만들어 직렬화 경계를 안 넘는다. 라이브 before/after: 필요 없는 노드 스케일아웃 → `executed=[restart] skipped=[scale] resolved=True`.
- `make check` (pytest) → **1168 passed, 1 skipped** (2026-07-26, 1159→1168, +9) — **Phase 1b 핸드오프 실행**(`7033db3`): rollouts-demo 소유권 TF→ArgoCD. 채택이 no-op이 아니었는데 원인은 라이브 드리프트(`--type=merge`가 컨테이너 배열 통째 교체)였고 ArgoCD가 **복구**한 것 → 프리플라이트 5번째 검사 `live-matches-rendered` 추가.
- `make check` (pytest) → **1159 passed, 1 skipped** (2026-07-26, 1114→1159, +45) — **① 게이트 완결(3종 판별) + ⑥ PSS/Cosign + ⑦ 스위퍼 CronJob**(`8e549bf`·`d96b888`·`69f149d`·`5015810`, **origin push 완료**). ①은 pass 경로를 여는 과정에서 **연쇄 결함 3건**이 드러나 전부 근본수정: (a) `llm.endpoint`를 router만 소비하고 webhook은 못 받아 **모든 판정이 unknown**이던 것(모델 부재가 아니라 배선 부재), (b) 템플릿이 firing 알럿을 **합성**해 보내 정상 canary가 conf 0.80으로 `fail`이던 것 → 호출자는 **신원만** 보내고 게이트가 Alertmanager를 직접 조회(`None`=못 봄 ≠ `[]`=조용함), (c) kps 파드 룰이 `for: 15m`이라 2~3분짜리 canary엔 발화 자체가 없어 크래시 canary도 pass이던 것 → canary 시간 스케일 룰 동봉. **라이브 3종 판별**: 정상→`pass`x3 abort 없음 / 크래시→`pass→fail→fail` **165s auto-abort**(stable 4/4, Available=True 내내) / 관측 불가→`unknown` 차단. ⑥ 양방향(비준수 설치는 API 서버가 4개 위반 적시하며 forbidden / 준수 설치는 `uid=10001` Running) + Cosign(서명은 **태그가 아니라 다이제스트**에 붙음을 라이브가 정정 → 차트 `image.digest`). ⑦은 CLI 부재가 `clean(exit 0)`이던 것을 **exit 2(coverage incomplete)** 로. 증거 `docs/evidence/onprem-{canary-agent-gate,pss-restricted-and-sweeper}-e2e.log`.
- **라이브 실증(2026-07-26, `b07523b`, 수 무변경)** — 기본 OFF로 남겨둔 3건 완주: ①canary 자동판정 **양방향**(나쁜 canary=`failed(3)>limit(2)`→사람 개입 0으로 ~105s auto-abort·stable 4/4 유지 / 좋은 canary=3연속 Successful→abort 안 됨) · ②Tempo 트레이스(query API·Grafana 프록시 양쪽 200, **5026ms 중 analyze 4136ms=MTTR의 82%가 로컬 LLM 추론**) · ⑥kindnet=**ENFORCED**+차트 정책 테넌트 시맨틱(same 통과/cross 차단). 증거 `docs/evidence/onprem-{addons-rollouts-analysis,tracing-tempo,netpol-tenancy}-e2e.log`. 라이브가 검증기 자체 버그 2건도 적발(agnhost `connect` http/URL 불가 · 파드 Ready≠포트 바인딩).
- (이전 이력: gate 1114 이하 · 2026-07-10~25 → `docs/archive/status-baseline-2026-07.md`)

## 동작하는 영역 (요약)

제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`. 4 provider(AWS/GCP/Azure/On-Prem) 코드 완비. 하네스 = overnight-harness 5 engine.

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge.
2. **3-Cloud Day2 Operations** — AWS(Step Functions) + GCP(Cloud Workflows) + Azure(Durable Functions). 각각 4-step 파이프라인 구현.
3. **Human-in-the-loop 승인** — Slack 승인 → `WaitForTaskToken` + SQS + SFN callback.
4. **Day1/1.5** — provisioning(cdk_generator/iam_designer/cost_estimator), deployment(smoke/canary/rollback), reporting(slo/oncall/capacity).
5. **Portability** — `NormalizedIncident` cloud-neutral envelope. provider registry + adapters.
6. **Runbook registry** — built-in catalog + capability-based schema + CDK seed + scan heuristic.
7. **AI Agents** — Strands(Bedrock) + ADK(Gemini 3.5 Flash) + MSFT(GPT-5.4). 3종 tool calling 검증 완료.
8. **Guardian Agent** — Policy-as-Code (APPROVE/AUTO/REJECT).
9. **MCP + A2A Gateway** — kubectl/docker MCP (9 tools) + FastAPI A2A + Bridge.
10. **On-prem K8s** — `make local-cluster` (kind 테스트용) → 3노드 + registry + NGINX ingress.
11. **Deployment Adapters** — 4 provider (onprem/aws/gcp/azure): Build→Push→Deploy→Validate→Rollback.
12. **Execution Adapters** — 4 provider: capability → provider-specific action resolution.
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지. AWS DynamoDB 연동 완료. 모든 데모 목업 데이터를 제거하고 실시간 Live 모드만 활성화. 🔐 Auth.js 기반 GitHub OAuth, Admin/Operator/Viewer 역할 부여 및 사용자 권한 관리 제어판(잠금 방지 보호 포함), 장애 복구 승인(Pending approvals), 신규 배포 트리거/롤백 액션 패널, 보안 감사 로그(Audit Logs) 뷰어 화면 프로덕션 배포 완료.

## Active Focus

**지금 하는 것**

- **Phase 3(인가 강화)** — ①자격증명 격리 full = 완료(2026-07-27). 남은 것은
  ②롤백↔selfHeal 우선순위(registry write-back, 지금은 문서로만 명명되고
  `ONPREM_EXECUTOR_LIVE=false`로 묶여 있다) · ③viewer 가시성 제한.
  **과대 해석 금지**: 자격증명 자체가 테넌트-바운드인 것은 **온프렘뿐**(→ Open Risks 7).
- **레포 원고 동기화** — 발행 3종(Notion 전문 `3a94c2420ac4801cbe99e36c16ed90fd` ·
  YouTube Shorts `2J9WfZV0TPE` · LinkedIn)은 2026-07-28 전부 완료. 정정본이 레포에도
  반영됐다(`6979787`). 남은 건 GitAIOps 후속편이며 착수 보류(사용자 지시).

**직전에 선 것들(2026-07-26~27, 상세는 `PROGRESS_LOG`/`COMPLETED_SUMMARY`)**

- **자연어 한 문장이 테넌트를 세운다** — `setup_tenancy → install_tenant_addons` 체인(17.6s).
  에이전트 mutating 범위는 **테넌트 스코프까지**, 공유 스택 9개는 TF 소유(D30).
  컨텍스트가 레지스트리와 다르면 아무것도 쓰지 않고 거부한다.
- **시연 가능** — `make dev-up` → `make demo-baseline`으로 4축 ✓ → netpol 1개 삭제 시
  network 축만 ✕ → 복구까지 재현. 영상·대본 → `docs/post/`.
- **레지스트리가 설치까지 표현한다** — repo+chart+values 세 입력이 전부 레지스트리에서
  나오고(`render_addons.py`), 클러스터 싱글턴은 이름을 대며 거부된다.
- **대시보드가 멀티테넌시를 관제한다** — 플릿 표(전 테넌트 × 격리 4축 + 티어 + 쿼터).
  데이터는 스포크 push로만 들어온다(D28). "N ok"는 실제로 평가한 행만 센다.
- **검증이 훅으로 강제된다** — Stop→`make check`(소스 변경 시만), PostToolUse→`tsc`(D29).
- **Phase 2 = 완결(M11)** · **Phase 0·1a·1b = 완결(M10)** — 상세 → `COMPLETED_SUMMARY`.
  **Phase 1b 잔여**: loki/tempo/pa 이관은 볼륨 스냅샷 수단 선행(kind엔 CSI 스냅샷터 부재).

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**(provider `oidc.vercel.com/men16922s-projects` 재생성, 실 team slug=Vercel API 확증). 앞으로 diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 가동 시 클러스터 리소스 가동 및 WIF OIDC 인증 연동 세부 과금 체크 필요.
3. **Cosign 어드미션 집행 없음(의도적)** — 서명 검증은 CI/사람용 게이트(`scripts/verify_image_signature.py`)
   까지다. 미서명 이미지를 API 서버가 거부하려면 policy controller(sigstore/Kyverno)라는 새 클러스터
   의존성이 필요해 Phase 2 네임스페이스 작업과 함께 다룬다. **지금 있는 보증을 과대 해석하지 말 것.**
4. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로
   죽었는데 `tsc`는 내내 초록이었다(값이 구버전 에이전트 페이로드에서 왔다). 롤링 업그레이드 중엔
   허브가 두 버전 리포트를 동시에 서빙하므로, **푸시로 들어오는 신규 필드는 항상 optional + 폴백**으로
   다룬다. 훅의 `tsc`도 이 부류는 못 잡는다.
5. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 테넌트 네임스페이스에
   `enforce: restricted`가 붙으면 차트 기본값으로는 파드가 admission에서 거부되고, **Argo는
   Synced로 보인다**(파드 0개인 채). loki·tempo는 seccompProfile을 values에 넣어 해소했지만,
   **새 애드온을 추가할 때마다 같은 확인이 필요**하다 — 렌더된 파드 스펙을 테넌트 네임스페이스에
   `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 것이 가장 싸다.
   values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(차트마다 키 철자가 다르다).
6. **Capsule deprecation 2건(미조치)** — `render_tenancy.py`가 내는 `limitRanges`·
   `additionalMetadata`는 상위 버전에서 제거 예정이다. 지금은 동작하지만 **values 파일이
   실패하는 방식과 같은 부류**(에러 없이 안 읽힘)라 Capsule 업그레이드 전에 이관 필요.
7. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다(Phase 3① 이후 남은 것)** — 스코프는 액션이
   **어느 네임스페이스를 건드릴지**를 정할 뿐 토큰 자체를 테넌트에 묶지 않는다. GCP는 프로젝트
   전역 신원 하나이고, **Azure는 ARM에서 클러스터 admin kubeconfig를 받아온다**(인시던트가
   어느 테넌트를 지목하든 실제 작업 신원은 cluster-admin). 자격증명 자체가 경계인 것은 **온프렘뿐**.
   → Phase 4(billable). 덧붙여 advisory `allowed_namespaces`가 실제 RBAC보다 넓고, GKE failover의
   `<cluster>-backup` 점프는 네임스페이스 게이트가 제약하지 않는다.
8. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 릴리스 없음(최신=현재)·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음. 필요 시 `overrides`로 postcss 강제(빌드 파손 리스크) 검토 가능.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
