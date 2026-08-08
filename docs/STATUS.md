# STATUS — platform-agent

최종 갱신: 2026-08-02

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.

---

## 검증 Baseline (실제로 돌린 것만)

- **실 AWS 왕복**(2026-08-08, gate 무관 — 프로브) — 인시던트 속성 6종이 실
  `incident-history`를 왕복해 **타입까지 보존**됨. `confidence`=`Decimal`(DynamoDB N)이라
  대시보드의 `typeof === "number"`가 참이 된다. **모킹으로는 원리상 못 잡는 검증**(목은
  float를 받고, 실제로는 boto3 예외가 `except`에 잡혀 행이 통째로 사라진다).
  `scripts/probe_incident_roundtrip.py` · 증거 `docs/evidence/incident-fields-dynamo-roundtrip.log`.
  **남은 한 칸**: 대시보드 TS 리더 미검증.
- `make check` (pytest) → **1636 passed, 1 skipped** (2026-08-08, +18) — **서명키 회전**:
  결함은 암호가 아니라 **배포 위상**이었다 — 서명자와 검증자가 다른 프로세스인데 키가 하나라
  교체가 원자적일 수 없고, 그 실패가 `failed attestation`(=위조로 읽힘)이라 **회전은 장애
  아니면 오경보**였다. `PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING`(검증 전용, 절대 서명 안 함) +
  **겹침을 유한하게 만드는 건 D42의 TTL**. 반증 4종 red(특히 retiring 레코드에 TTL 미적용).
  **custody는 미해결이고 거짓 주장도 아니다**(→ Risk 3).
- `make check` (pytest) → **1618 passed, 1 skipped** (2026-08-08, +1) — **테스트가 상했다**:
  `test_incident_time_to_resolve.py`는 **수정된 적이 없는데** red가 됐다. 픽스처가
  `created_at`을 하드코딩(`2026-07-29`)하는데 생산자는 **살아 있는 시계**로 7일 창을 건다 →
  **08-05에 이미 깨져 있었다**. `now` 기준 상대 배치로 교체(형제 `test_report_windows.py`의
  모양) + 가드 1건. **게이트 숫자에는 측정 날짜가 붙어야 한다** → Risk 12.
- `make check` (pytest) → **1617 passed, 1 skipped** (2026-08-02, +3) — **푸시 읽기 신원**:
  push 인증은 **이미 완료**였고(계획이 일주일째 스테일), 실제로 열린 건 **스포크의 읽기**다 —
  맨 kubectl + 공유 `argocd` ns라 테넌트 구분이 **코드 필터**다. 쓰기는 허브가 401로 막는다
  (라이브 4종). 시끄럽게만 해 둠. 증거 `docs/evidence/push-identity-ambient.log`.
- `make check` → **1614** (2026-08-02, +6) — **결정 6 = D42**: 승인
  재사용을 **TTL로 묶었다**(서명이 덮는 `issued_at`, 기본 900초, 끄는 스위치 없음). one-time-use는
  **틀린 수정**이었다(실행기가 같은 인시던트로 두 번 해석). 라이브: 만료·미래 스탬프·시각 위조
  전부 거부, TTL 안 재사용은 **가능하고 그렇게 적었다**. 증거
  `docs/evidence/approval-ttl-replay-bound.log`.
- `make check` → **1608** (2026-08-02, +1) — **결정 3 = D41**: Capsule `limitRanges`를 대체 없이
  **객체 직접 렌더**(→ Risk 9). 라이브 3단(Capsule 회수 · 없으면 `must specify limits.cpu`
  Forbidden · 전체 리싱크 생존), 경고 2→**0**. 증거 `docs/evidence/capsule-limitranges-direct.log`.
- `make check` → **1607** (2026-08-01, +2) — **결정 4 = D40**: k3s는 proven 기판에 넣지 않는다
  (→ Risk 5). 가드 `tests/test_substrate_promotion_reachable.py`.
- `make check` → **1605** (2026-07-31, +9) — **무스코프 MCP 읽기 차단**(D39): 근거 **"익명
  kagent 왕복이 이걸 쓴다"가 사실이 아니었다**(`src/`에 `MCPServer` 생성자 0 → 그 경로를 돌리던
  유일한 코드는 **그것을 고정하던 테스트**). `resource`가 자유 문자열이라 반경은 ambient
  =cluster-admin이었다(라이브 `secrets -n kube-system`·`nodes` 성공 → 차단). 증거
  `docs/evidence/unscoped-mcp-read-closed.log`.
- `make check` → **1596·1572** (2026-07-30~31) — **결정 5 A·B**(D38, 배포 신원 축소 + 스코프
  생산자, **둘 다 옵트인**) + 그 조사(**생산자 없는 메커니즘은 테스트에서 영원히 초록**).
  증거 `docs/evidence/{deploy-identity-reduction,scope-producer-live,deploy-path-authorization}.log`.
- `make check` → **1565·1552·1544** (2026-07-29~30) — M13의 마지막 셋: 배포 네임스페이스
  출처(D37, 라이브에서 `rollout undo -n default`가 **엉뚱한 워크로드를 되돌리고 성공을 보고**) ·
  tier 발명 제거(D36) · 리포트 창(`ttl`을 시각으로, 90→2, **라이브 미실행**).
  상세 → `COMPLETED_SUMMARY` M13.
- (이전 이력: gate **1533** 이하 · 2026-07-10~29 → `docs/archive/status-baseline-2026-07.md`
  및 `PROGRESS_LOG`.)

## 동작하는 영역 (요약)

제품 방향: Day1+Day2를 함께 다루는 AWS-native `platform-agent`. 4 provider(AWS/GCP/Azure/On-Prem) 코드 완비. 하네스 = overnight-harness 5 engine.

1. **Operations 파이프라인** — Detector/Analyzer/Decision/Executor + Approval Bridge. **3-Cloud Day2**: AWS(Step Functions) + GCP(Cloud Workflows) + Azure(Durable Functions), 각각 4-step.
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
13. **Dashboard** — Next.js 16 + Tailwind 4, 5페이지, DynamoDB Live 전용. Auth.js GitHub OAuth + Admin/Operator/Viewer 권한 제어판(잠금 방지), 복구 승인, 배포 트리거/롤백, 감사 로그 — 프로덕션 배포 완료.

## Active Focus

**지금 하는 것**

- **Phase 3(인가 강화) = 완결(M12) + 결정 5 A·B로 실제 집행 가능해짐(2026-07-31, → Risk 3)** —
  다음은 **Phase 4**(managed, billable) 또는 **Phase 5**(레지스트리 쓰기 — 열려야 ②를
  GitOps-native로 닫는다). **과대 해석 금지 4건**: 스코프·배포 신원은 **옵트인**(→ Risk 3) ·
  자격증명이 테넌트-바운드인 건 **온프렘뿐**(→ Risk 10) · ②는 조용한 되돌림을 거부로 바꿀
  뿐(→ D32) · 파티션된 읽기 경로는 **둘뿐**.
- **결정 6건 전부 닫힘(2026-08-02)** — D36·D38·D39·D40·D41·**D42**. 열린 결정 없음, 남은 건
  **승인 3건** 뒤 **Phase 4/5**. 여섯 번의 조사에서 **여섯 번 다 전제가 깨졌다**: 소비자 없는
  필드(M13, 14건) → 생산자 없는 메커니즘(D38) → 사용처 없는 예외(D39) → 도달 불가능한
  검증기(D40) → 세지 않은 선택지(D41) → **상태가 살아남지 못하는 가드**(D42 — **수호 테스트가
  홀을 가린** 첫 사례). 전부 테스트는 초록이었다.
  **M13 교훈**(상세 → `COMPLETED_SUMMARY` M13): 부재보다 **그럴듯한 기본값**이 오래 산다 ·
  **투영/스키마 계층도 소비자**다 · 가드는 **파생**시켜라 · **수호 테스트 자신이 안티패턴일 수
  있다** · 생산자가 없으면 소비자를 단언해도 초록이다(→ Risk 3).
- **발행 3종 완료(2026-07-28)** — Notion·YouTube Shorts `2J9WfZV0TPE`·LinkedIn `6979787`. 후속편 보류.

**직전에 선 것들(2026-07-26~27, 상세는 `PROGRESS_LOG`/`COMPLETED_SUMMARY`)**

- **자연어 한 문장이 테넌트를 세운다** — `setup_tenancy → install_tenant_addons`(17.6s). mutating
  범위는 **테넌트 스코프까지**, 공유 스택 9개는 TF 소유·컨텍스트 불일치 시 거부(D30).
- **시연 가능** — `make dev-up` → `make demo-baseline` 4축 ✓ → netpol 1개 삭제 시 network 축만 ✕
  → 복구까지 재현(영상·대본 `docs/post/`) · **레지스트리가 설치까지 표현한다**(`render_addons.py`)
  · **대시보드가 멀티테넌시를 관제한다**(플릿 표, push 전용 D28) · **검증이 훅으로 강제된다**
  (Stop→`make check`, PostToolUse→`tsc`, D29).

## Open Risks / Gaps

1. **CDK 배포 시 Vercel context 필수(함정 실화 이력)** — ⚠️ context 미지정 배포가 **실제로 07-11 OIDC provider를 삭제**해(CloudTrail 확인) 대시보드가 조용히 DEMO FALLBACK으로 강등돼 있었음 → **07-18 복구**. diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`. 로컬 pip 번들링(arm64↔amd64) 주의 유지.
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다 — 단 "실 데이터 삭제"는 틀렸다(2026-08-08
   재측정)** — 코드 갭은 유효: Cosmos DefaultTimeToLive 미설정, Firestore TTL 정책 부재 →
   스토어가 생기면 **어느 쪽도 만료 안 됨**. 하지만 **스토어가 아예 없다**: GCP는 platform-agent
   프로젝트에 **Firestore API가 켜진 적조차 없고**, Azure엔 `platform-agent` DB가 없다 →
   **지울 데이터 0**. 승인 항목이 아니라 **Phase 4(프로비저닝, billable)** 선행 항목이다.
   증거 `docs/evidence/gcp-azure-retention-nothing-to-delete.log`.
3. **⚠️ 스코프 격리는 가능하지만 옵트인이다(2026-07-31, D38·D39)** — 세 경로가 닫혔다: 인시던트
   생산자(`attest_decision`) · 배포 축소 신원 · MCP 무스코프 읽기 거부. **기본값은 미설정**이라
   `PLATFORM_{CREDENTIAL_DIR,APPROVAL_SIGNING_KEY}` 없으면 인시던트는 전부 거부,
   `PLATFORM_DEPLOY_KUBECONFIG` 없으면 배포는 ambient(=cluster-admin). 즉 **"설정하면 집행되고,
   안 하면 조용히 안 된다."** 묻기 `scripts/probe_scope_reachability.py`·`make
   deploy-identity-check`, 켜기 `make scope-credentials`·`make deploy-identity`. **남은 것**: 배포
   신원은 테넌트를 구분 안 함(결정 5 C/D=라우터 인증 선행) · **서명키 rotation은 닫힘**(2026-08-08,
   `..._KEYS_RETIRING` 검증 전용 + D42 TTL이 겹침을 유한하게) **단 custody는 미해결** — 로컬은
   클러스터명 파생이고 `Makefile:256`이 "NOT a secret-management story"라고 **정확히 라벨**해
   뒀다. 닫으려면 시크릿 매니저 선택 = 인프라·정책 결정(+과금) · **승인 재사용은 TTL까지만
   허용**(D42) · 클라우드 3종은 Risk 10.
4. **GCP/Azure 실 클러스터 비용** — 실 배포/Remediation 시 클러스터 가동 + WIF OIDC 과금 체크.
5. **k3s는 집행하지만 proven 집합엔 없다 — 결정 4 = D40으로 닫힘(2026-08-01)** — 집행은 라이브
   증명(07-29), 시맨틱은 미증명. 네 문서가 반복한 "피어 테넌트 부재"는 **참이지만 구속력이
   없었다**: 실제로는 넷 — ①acme/prod는 **네임스페이스 1개**(피어 보기 전에 exit) ③**순환**
   (프로브가 proven 집합을 전제 = **승격하려면 먼저 승격해야 한다**) ④**k3s-lab에 테넌시 실체
   0** → 넣어도 **보호 대상 0**. 열리는 조건: k3s-lab에 워크로드. → D40, `docs/plans/2026-08-01-k3s-proven-substrate.md`.
6. **서명 경로는 섰다(2026-08-08). 어드미션은 여전히 없다** — 아침까지 공급망 보증은 **0**이었다:
   `cosign sign` 레포에 0건 · `.github/workflows/` 없음(= "CI 게이트"는 **돌 수 없는 단계**) ·
   검증기의 유일한 호출자는 **자기 테스트**(D39 모양) · 차트가 레지스트리 없는 맨 태그 +
   `digest: ""`라 **서명이 놓일 주소조차 없었다**. → `make sign-image`로 ①빌드 ②**다이제스트로**
   push ③`cosign sign` ④**레포 자신의 게이트로 검증**(`verify_image_signature.py`의 첫 프로덕션
   호출자)까지 라이브 실증. 미서명 다이제스트는 `NOT SIGNED`(exit 1)로 거부됨.
   그리고 **소비자도 붙였다** — 서명 경로만 만들었을 때 나는 **소비자 없는 생산자**를 새로
   만든 것이었다(이 레포가 온종일 사냥한 그 결함). `image_trust.require_trusted_image`가
   **배포 직전**에 거부한다: 라이브에서 미서명 다이제스트는 `cluster.deploy` **호출 전에** 막혔다
   (`docs/evidence/image-signature-deploy-gate.log`). **"could not evaluate"(exit 2)도 거부**한다 —
   검사 실패는 이미지가 괜찮다는 증거가 아니다.
   **남은 것**: ⓐ키는 **로컬 dev 전용**(빈 암호, `~/.platform-agent/cosign`) — 실 배포는 KMS/키리스
   ⓑ**CI 없음** — 사람이 `make`를 쳐야 돈다 ⓒ차트의 `digest`는 **비워 둔다**(로컬 레지스트리
   다이제스트를 커밋하면 아무도 못 가진 이미지에 대한 주장이 된다) ⓓ**어드미션 집행은 여전히
   미도입** — policy controller = 새 클러스터 의존성이고, 실패 모양이 Risk 8이다
   ⓔ**배포 게이트는 옵트인**(`PLATFORM_REQUIRE_SIGNED_IMAGES`, 미설정=검사 0)이고 **온프렘
   진입점 하나**만 덮는다 — 클라우드 3종과 ArgoCD가 직접 당기는 이미지는 지나가지 않는다.
   가드 `tests/test_signature_gate_claims.py`·`tests/test_image_trust.py`.
   **있는 보증을 과대 해석하지 말 것.**
7. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 라이브에서 페이지가 `posture.namespaces.length`로
   죽었는데 `tsc`는 내내 초록이었다(구버전 에이전트 페이로드). 롤링 업그레이드 중엔 허브가 두
   버전을 동시에 서빙하므로 **푸시 신규 필드는 항상 optional + 폴백**으로 다룬다.
8. **PSS restricted 아래에서 애드온 차트는 기본값으로 동작하지 않는다** — 파드가 admission에서
   거부되는데 **Argo는 Synced로 보인다**(파드 0개인 채). **새 애드온마다 확인이 필요**하다 — 렌더된
   파드 스펙을 테넌트 ns에 `kubectl apply --dry-run=server`로 던져 API 서버에 직접 묻는 게 가장 싸다.
   values 파일은 에러가 아니라 **안 읽히는 방식으로** 실패한다(키 철자가 차트마다 다름).
9. **Capsule deprecation = 해소(2026-08-02, D41)** — 두 필드 다 이관(`additionalMetadata` 07-28 ·
   `limitRanges` 08-02 **객체 직접 렌더**), 경고 **0건**. 잃은 건 Capsule 재조정(NetworkPolicy와 같은 대가).
10. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다** — 스코프는 액션이 **어느 네임스페이스를
   건드릴지**만 정하고 토큰을 테넌트에 묶지 않는다. GCP는 프로젝트 전역 신원 하나, **Azure는 ARM에서
   클러스터 admin kubeconfig를 받아온다**. 자격증명 자체가 경계인 것은 **온프렘뿐** → Phase 4.
11. **Dashboard dependency audit** — Next.js 16.2.10 내부 번들 PostCSS(<8.5.10) moderate 2건(XSS via `</style>` in CSS stringify). **재검증(2026-07-13)**: 16.2.x 패치 없음·`audit fix --force`는 next@9 다운그레이드 → **upstream 대기 확정**. 빌드타임 경로라 런타임 위험 낮음.
12. **게이트는 상한다 — 초록에는 유효기간이 있다(2026-08-08)** — 소스가 한 줄도 안 바뀌었는데
   `make check`가 red가 됐다: 픽스처가 절대 시각을 하드코딩하고 생산자가 **살아 있는 시계**로
   창을 걸면, 통과는 **달력이 움직이기 전까지만** 참이다(07-29 픽스처 + 7일 창 → **08-05 만료**).
   지금 창 필터를 타는 테스트는 **둘뿐**이고 둘 다 `now` 기준이다. **새로 추가할 때 확인할 것**:
   픽스처가 절대 시각이면 그 테스트는 만료일이 있는 주장이다. 그리고 **"1617 passed"는 날짜
   없이는 주장이 아니다** — 기록에는 측정 시점을 함께 남긴다.
- (해소된 리스크 이력 — Slack App 미연결=07-19 해소·A2A discovery=07-14·추적 IA 실증=07-13·NEXT_PUBLIC 인라인=07-13 — 은 `PROGRESS_LOG`/`docs/archive/` 참조.)
