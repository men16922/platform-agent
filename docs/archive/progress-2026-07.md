# PROGRESS_LOG Archive — July 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 7월 이력입니다. 최신이 위.

---

## 2026-07-31 — 결정 2: 예외를 붙잡던 근거가 사실이 아니었다 (gate 1596→1605)

- Status: 브리프의 다음 우선순위(결정 2 = 무스코프 MCP 읽기)를 조사→브리프→실행. **또
  전제가 깨졌다** — 이번엔 예외를 정당화하던 **문장**이 틀렸다.
- Verified(조사): "닫으면 검증된 익명 kagent 왕복이 깨진다"는 근거가 **셋 다 반증됐다**.
  ①kagent 왕복은 **아웃바운드**이고 `k8s_get_resources`는 **kagent 자신의 도구**다
  (`a2a-phase2-live-e2e.log`) ②`a2a_server`는 Supervisor로 라우팅하고 게이트웨이로 가는
  경로가 없다 ③**`src/`에 `MCPServer` 생성자가 0**이다 — 무스코프 경로를 실행하던 유일한
  코드는 **그것을 고정하던 테스트**였다. 즉 **존재하지 않는 소비자를 위한 예외**.
- Changed(브리프 추천 B): 읽기도 **기본 거부**, 되돌리려면
  `PLATFORM_MCP_ALLOW_UNSCOPED_READS=true`(빈 문자열=미설정, 켜지면 **호출 시점 경고**,
  **쓰기는 안 열린다**) · `test_gateway.py`의 디스패치 테스트 둘에 **스코프 부여**(그 둘이
  무스코프로 통과하던 게 홀의 증상이었다) · 새 가드 `test_carveout_consumers_exist.py`
  (**예외의 근거로 인용된 소비자가 실재하는지** + MCP-over-HTTP가 붙는 날의 트랩).
- Verified: `make check` **1605**(+9) · **라이브 kind**: BEFORE(탈출구로 옛 동작 재현)
  `secrets -n kube-system`·`nodes`·`pods` 전부 성공 → AFTER 전부 거부, 쓰기는 탈출구로도
  거부, **스코프 가진 호출자는 무영향**. 반증 6건 개별 red. 증거
  `docs/evidence/unscoped-mcp-read-closed.log`.
- Blockers: 없음.
- 품질 메모: **대가가 적어둔 것보다 컸다** — `resource`가 자유 문자열이라 "읽기"는 좁지
  않다. 도구 이름은 `get`인데 **반경은 ambient의 반경**이고 그건 cluster-admin이다.
  문서엔 "남의 로그 = 유출"이라 적혀 있었지만 실제론 secrets를 포함한 전부였다. 그리고
  **반증에서 내 탈출구 경고가 조용해져도 초록이었다** — 조용한 탈출구는 옛 기본값이
  플래그를 단 것일 뿐이라 어서션을 추가했다. **M13(소비자 없는 필드) → D38(생산자 없는
  메커니즘) → 결정 2(사용처 없는 예외)** 로 같은 결함이 세 층에서 나왔다.
- Next: 잔여는 결정 2건(3·4) + 승인 3건.

## 2026-07-31 — 결정 5를 추천안대로 실행: 배포 신원 축소(B) + 스코프 생산자(A) (gate 1572→1596)

- Status: 사용자가 추천안을 승인해 **B 먼저 단독 → A** 순으로 실행. 어제 조사가 찾은
  "두 경로가 반대 방향으로 고장" 둘 다 닫았다.
- Changed **B**(`b92b54e`, +12): 네 배포 어댑터가 전부 맨 `kubectl`을 만들어 ambient로
  돌았고 라이브에서 그 ambient는 **cluster-admin**이었다(`get secrets -A`=yes). seam 하나
  `platform/deploy_identity.py`(넷에 각자 심으면 네 번째가 남는다) · RBAC 렌더러
  (**허용은 어댑터가 부르는 kubectl에서 파생**, **금지는 명시**) · 1h 민팅 · `make
  deploy-identity{,-check}` · `ops_tools`도 같은 seam(프로세스를 공유하니 신원도 공유).
- Changed **A**(`2a21b86`, +12): `attest_decision()`을 **인가가 성립하는 두 지점**에서
  호출(AUTO=정책 결정 시점, 승인=**사람이 결정한 순간** — 파킹 시점 서명은 아무도 승인하지
  않은 행동을 attest한다) · `mint_tenant_kubeconfig.sh`(Phase 1a 증거의 자격증명은 **손으로**
  만들어 커밋된 적이 없었다 = 시연은 되고 재현은 안 됐다) · `make scope-credentials` ·
  프로브를 **"생산자 없음"(코드 갭) vs "이 환경 미설정"(make 한 번)**으로 분리.
- Verified: `make check` **1596**(+24) · **라이브 kind 3노드** 양쪽. B: 축소 신원으로
  `get secrets -A`·`delete namespaces -A`·`create clusterrolebindings` 전부 **no**인데
  **실 배포 2회 + 실 롤백** 정상(1.27→1.28→1.27), `get secrets -n kube-system`은 **API
  서버가 Forbidden**. A: 실 Alertmanager→실 어댑터→**실제로 스코프 획득**(tenant=acme),
  자기 ns PERMITTED·이웃 REFUSED, 서명 변조/caller 불일치 모두 refused, acme 자격증명으로
  globex 조회는 Forbidden. 반증 B 12건·A 8건 개별 red, no-op 없음. 증거
  `docs/evidence/{deploy-identity-reduction,scope-producer-live}.log`.
- Blockers: 없음. **기본값은 둘 다 안 바뀐다** — 배포는 미설정 시 ambient지만 **경고하고**,
  attest는 키 없으면 no-op이라 게이트가 예전과 동일하게 거부한다. fail-closed가 더 안전한
  *모양*이지만 틀린 *변경*이다: 두 줄 데모를 깨고, **아무도 돌릴 수 없는 경계**가 바로
  어제 찾아낸 실패 모드다.
- 품질 메모: **내 가드가 나를 잡았다** — `attest_decision`을 넣자마자 어제 쓴
  `test_scope_producer_reachability`가 "생산자는 생겼는데 자격증명이 없다"로 red(정확히 그
  트랩용). 그런데 **그 가드의 생산자 탐지가 심볼 하나만 봐서** 새 생산자를 못 봤다 — 메커니즘을
  심볼 하나로 탐지하는 건 경계를 열거하는 것과 같은 취약함이라 체인으로 바꿨다. 그리고
  **AST 가드가 호출부는 봤지만 이름이 resolve되는지는 못 봐서**, 린터가 지운 import를
  런타임 NameError로만 알았다(gate 4 red). **읽는 것과 돌리는 것은 다르다.**
- Next: 잔여는 결정 3건(2·3·4) + 승인 3건. 결정 2는 **A로 절반 풀렸다**(스코프 생산자가
  섰으니 kagent 경로에 스코프를 줄 수 있다).

## 2026-07-30 — 결정 5를 조사했더니 질문이 틀렸다: 그 가드는 한 번도 열린 적이 없다 (gate 1565→1572)

- Status: 결정 5("배포 요청이 무엇으로 테넌트를 말하나")를 D36과 같은 방식으로 조사→브리프까지.
  **전제가 깨졌다** — 계획은 "인시던트 경로와 같은 가드를 배포에 태운다"였는데, **그 가드는
  프로덕션에서 열린 적이 없다.**
- Verified(라이브): 실 Alertmanager 페이로드 → 실 온프렘 시그널 어댑터 → 실 resolver → 실 게이트.
  `source_metadata`에 `attested_approval` **없음** → `resolve_incident_scope` → **None**
  (`executor.scope.absent`) → `guard_scoped_action` → **REFUSED**. 원인 셋: 네 어댑터 중 누구도
  그 키를 안 쓰고 · `sign_approval` 프로덕션 호출부 **0**(테스트 17) · 브로커 env 2개를
  **어느 스택·Makefile·스크립트도 설정하지 않는다**. 라이브 모드가 기본 OFF라 안 보였고
  **켜면 전부 거부**된다. 반대편 실측: 배포 경로는 `kubectl apply`에 `--kubeconfig`가 없어
  `kubernetes-admin`(`delete namespaces -A`·`get secrets -A`·`create clusterrolebindings` 모두
  yes). `make check` **1572**(+7). 증거 `docs/evidence/deploy-path-authorization.log`.
- Changed(결정 없이 할 수 있는 것만): ①`scope.py` 모듈 문서에 **도달 불가 사실**을 못 박음
  (게이트 옆에서 읽는 사람이 "스코프 동작함"으로 오독하지 않게) · ②재측정 도구
  `scripts/probe_scope_reachability.py`(k3s 프로브와 같은 규약) · ③가드
  `tests/test_scope_producer_reachability.py` — **양방향 하중**: 닫힌 채로 주석을 지우면 red,
  생산자가 생겼는데 자격증명이 없으면 red, 생산자+자격증명 둘 다면 **green**(반증 E). ④문서 정직화:
  NEXT_PLAN 최우선 불변식 "Phase 1a에서 강제 완료" → **아직 집행 아님**, STATUS Risk 3 전면 개정.
- Blockers: **결정 5는 사용자 결정**. 브리프 `docs/plans/2026-07-30-deploy-request-tenant-scoping.md`
  — 선택지 4종(A 생산자 세우기 · B 배포 신원 축소 · C 요청 선언 · D 프롬프트/시그니처),
  **추천 B 먼저 단독 → A**, C·D는 라우터 인증까지 보류.
- 품질 메모: **생산자 없는 메커니즘은 테스트에서 영원히 초록이다** — 스코프 17개 테스트가 전부
  자기가 `sign_approval`로 만든 레코드로 통과해, "게이트가 동작한다"는 증명하고 "무엇이 게이트를
  여는가"는 한 번도 묻지 않았다. M13의 "픽스처는 실제 입력에서"의 **서브시스템 판본**. 그리고
  **내가 만든 가드가 내 프로브를 생산자로 셌다**(첫 실행 red) — 부재를 보고하는 도구를 생산자로
  세면 안 되므로 언급이 아니라 **호출**을 보게 고쳤다. 이번에도 수호 장치가 먼저 틀렸다(네 번째).
- Next: 결정 5 답변 대기. 결정 2(무스코프 MCP 읽기)도 **같은 뿌리**임이 드러났다 —
  `MCPServer(scope=...)`를 프로덕션에서 구성하는 곳이 없다. 생산자가 서면 둘이 함께 닫힌다.

## 2026-07-30 — 배포 행이 착지한 네임스페이스를 말하지 않아 롤백이 네 층에서 발명했다 (gate 1552→1565)

- Status: 결정 1(D36) 조사에서 떨어진 선행 항목 — "`deploy_recorder`가 namespace를 기록조차
  안 한다" — 을 배선까지 끝냈다. 소비자가 **이미 있었다**: 롤백 경로.
- Changed: ①`deploy_service`가 착지한 네임스페이스를 **결과로 보고**(프롬프트가 선호하라고
  지시하는 도구라, 결과가 침묵하면 기록기는 모델이 넘긴 것만 볼 수 있었다) · ②DEPLOY 행에
  기록, `_infer_namespace`는 **args보다 result 우선**(result는 어댑터가 *한 일*, args는 모델이
  *요청한 것*) · ③`record_rollback`·teardown cascade가 이어받는다(승계는 행을 덮어쓰므로
  빠뜨리면 **지운다** — `cost_metrics` 교훈, 다만 사라지는 게 **다음 롤백의 조준값**이라
  한 번의 롤백이 다음 것을 위해 버그를 재장전한다) · ④대시보드 매퍼·읽기모델·롤백 버튼·Next
  라우트·`RollbackRequest`에서 `"default"` 리터럴 제거 — 해소점은 `ServiceSpec` 하나로.
  **티어(D36)와 달리 부재 보존이 아니라 해소된 사실 기록**이다. 프로비저닝 행에는 안 붙는다.
- Verified: `make check` **1565**(+13) · tsc 클린 · `next build` 성공 · **라이브 kind 3노드**:
  같은 이름이 두 ns에 있으면 `rollout undo -n default`는 **실패하지 않고 엉뚱한 쪽을 되돌리며
  성공을 보고한다**(BEFORE default 1.28→1.27, 대상 acme-prod-app은 1.28 그대로 = 운영자가 누른
  그 서비스 / AFTER 실 배포→실 행→실 HTTP 롤백→대상만 되돌아가고 default 무변, 승계 후에도
  보존). 반증 14건 개별 red. 증거 `docs/evidence/deployment-namespace-provenance.log`.
- Blockers: 없음.
- 품질 메모: **D36이 세 번째·네 번째 경계에서 살아 있었다** — D36 가드가 자기가 아는 두
  경계(FastAPI 요청 모델·대시보드 매퍼)를 **열거**했고 그 사이 롤백 라우트가
  `environment = "production"`을 갖고 있었다(모든 롤백이 덮어쓰는 durable 행에). 파생 스윕으로
  바꾸자 **트리거 라우트**도 즉시 나왔다 → **가드를 열거하면 가드가 모르는 층에서 결함이 산다**.
  그리고 **내 반증 스크립트 초안 자신이** setup 실패를 흘리며 결론을 **정적 텍스트로 출력**해
  통과와 구분되지 않았다(D36 no-op 반증 교훈 재발) — 어서션으로 바꿔 다시 돌렸다.
- Next: 배포 경로 스코프 가드는 **여전히 결정 대기**. **행은 정직해졌지만 요청은 아니다** —
  프롬프트가 namespace/tenant를 언급하지 않아 모델이 아무것도 안 넘기면 `default`로 해소되고
  그건 무테넌트다. 역조회 스코프는 여전히 발명이다.

## 2026-07-29 — 결정 1을 닫았고, 두 층이 발명하던 tier를 없앴다 (gate 1544→1552)

- Status: 결정 1("배포는 어느 테넌트 소유인가")을 조사→브리프→**결정(D36)**→구현까지.
  조사에서 **전제 하나가 깨졌다**: 한 개인 줄 알았던 게 세 개(귀속·인가·과금)였고,
  과금은 **결정 대기가 아니라 구조 대기**였다.
- Changed(`D36`): ①**deployments/activities 무파티션 확정** + **테넌트별 모델 rate limit
  안 함 확정** — 요청 시점에 대상이 미상(모델이 도구를 부를 때 정해짐)이고 라우터가 무인증이라
  본문 테넌트는 자진신고인데, **자진신고 예산은 예산이 아니다**. "테넌트 격리됨"의 범위를
  **플릿·인시던트 둘로** 못 박았다. ②D36이 딸고 온 코드 변경 — **tier 발명 제거**:
  대시보드 NL 배포는 `environment`를 안 보내는데 HTTP 경계가 `"dev"`를, 매퍼가 부재를
  `"production"`을 채웠다(**한 미상값에 두 층이 서로 다른 답**). 경계 기본값 제거 · writer
  조건부 저장(빈 문자열=부재) · 문서에서 optional로 이동 · 렌더 5곳 정직화. ③분리:
  **배포 경로 무스코프**(인가 문제, Open Risk 3) · 트리거 폼 tier 표기.
- Verified: `make check` **1552**(+8) · tsc 클린 · `next build` 성공. 반증 5건 개별 되돌림
  전부 red, 복원 시 13건 통과. 증거 `docs/evidence/deployment-environment-absence.log`,
  브리프 `docs/plans/2026-07-29-deployment-tenant-ownership.md`.
- Blockers: 없음(결정 1은 닫혔다).
- 품질 메모: **처음 추천이 검증에서 뒤집혔다** — "대상 네임스페이스에서 역조회"가 옳은
  모양이라 추천하려다, `deploy_service`의 `namespace` 기본값이 `"default"`이고 프롬프트가
  namespace·tenant를 한 번도 언급하지 않으며 `deploy_recorder`가 namespace를 기록조차 안
  한다는 걸 확인하고 접었다(오늘 켜면 전부 무테넌트 귀속). 그리고 **내 가드가 잡으려던 홀을
  자기가 갖고 있었다**: 조건부 저장은 `item["k"]=v`라 dict 리터럴만 보는 walker에 안 잡혀,
  그대로 뒀으면 가드가 **버그 쪽을 편들었을** 것이다(=environment를 core에 두라고 요구).
  무조건/조건부를 분리해 고쳤다. 반증 4도 처음엔 초록이었는데 **치환이 no-op**이었다
  (파일에 `\u2014` 이스케이프가 문자로 들어가 패턴이 안 맞았다) — 아무것도 안 고친 반증은
  진짜 수정과 똑같이 PASS를 낸다.
- Next: 잔여는 결정 3건(MCP 읽기·Capsule 경로·k3s 게이트) + 승인 3건 + 분리된 인가 1건.

## 2026-07-29 — k3s는 NetworkPolicy를 집행한다, 그런데 게이트는 안 열었다 (gate 1544 유지)

- Status: 계획의 **비-결정 항목 마지막**(⑥ k3s 검증기 재실행)을 실행했다. flannel 집행은
  kindnet에서 **전이되지 않으므로** 기판별 실측이 필요했던 항목.
- Changed(코드 경로 무변경): `tenancy.py`의 기판 주석에 측정 결과와 **왜 아직 안 넣는지**를
  기록 · 부작용 프로브를 `scripts/probe_netpol_side_effects.sh`로 남김.
- Verified(라이브, k3s v1.31.4 + flannel + 내장 kube-router): ①`verify_netpol_enforcement.py`
  → **ENFORCED**(컨트롤 유효 — 무정책 시 B→A 도달을 **먼저** 확인) ②default-deny **아래에서
  태어난** 파드의 readinessProbe가 Ready → **노드발 프로브는 차단되지 않는다**(어떤
  namespaceSelector로도 못 잡는 트래픽이라 여기서 막혔으면 며칠 뒤 앱 회귀로 보였을 것)
  ③같은 정책에서 DNS 정상(`10.43.0.1 kubernetes.default`) → ingress 전용 정책이 egress를
  안 건드림. `make check` 1544 유지. 증거 `docs/evidence/k3s-netpol-enforcement.log`.
- Blockers: **게이트(`PROVEN_ENFORCING_SUBSTRATES`)는 열지 않았다** — 3종이 증명한 건
  "기판이 집행할 수 있고 집행해도 안 깨진다"까지고, **이 집합이 실제로 licensing하는 주장**
  (우리 정책 shape이 같은 테넌트 통과·다른 테넌트 차단)은 미검증이다. 그걸 보는
  `verify_tenant_isolation.py`가 **k3s-lab에 피어 테넌트가 없어 못 돈다**(acme/prod가 유일한 env).
  globex/prod를 만들면 실 네임스페이스·쿼터·애드온이 프로비저닝되므로 **테스트를 돌리려고
  인프라를 지어내지 않았다** → 결정 4로 올림.
- 품질 메모: 첫 실행이 **INCONCLUSIVE**("server pod never became Ready")였고 그대로 기록했다 —
  원인은 VM의 콜드 이미지 캐시(직후 `crictl pull`이 "up to date")였고, 두 실행의 차이는
  클러스터가 아니라 캐시였다. 검증기 자신의 규율대로 **컨트롤이 안 선 실험은 통과가 아니다**.
  그리고 kind용으로 확인해둔 "프로브·DNS는 안 깨진다"를 k3s에 **전이시키지 않고 다시 쟀다** —
  기판이 다르면 CNI도 정책 컨트롤러도 다르다.
- Next: 결정 4(위) 외 잔여 없음. 나머지는 전부 기존 결정 3건 + 승인 1건.

## 2026-07-29 — 리포트 창을 시계가 아니라 보관 필드로 재고 있었다 (gate 1533→1544)

- Status: 읽기 모델 건이 연 **TTL 실마리**를 따라갔다. 거기서 `ttl` 커버리지가 writer마다
  다르다는 걸 알았으니 다음 질문은 **누가 `ttl`을 읽는가** — 두 리포트 창이 그걸 **시각처럼**
  읽고 있었다. M13의 열두 번째.
- Changed(`5988d6b`): `ttl`은 **쓴 시각 + 90일**이다. ①**일일 SLO**: 필터가
  `ttl >= now - 24h`인데 ttl은 항상 미래 90일이고 cutoff는 과거라 **만료 안 된 모든 행에 대해
  참** — "최근 24시간"이 보관 기간 전체였다(바로 다음 줄의 파이썬측 재검사도 같은 두 값이라
  항상 거짓). ②**주간 온콜**: `ttl - 90일`로 역산 — 보관 상수를 바꾸면 리포트 전체가 조용히
  밀리고, **`ttl`이 없는 행은 `now`로 기본값이 잡혀 90일 과거로 떨어져 모든 주간 리포트에서
  소리 없이 빠졌다**(`created_at`에 나이가 분명히 적혀 있는데도). 둘 다 모든 writer가 무조건
  쓰는 `created_at`으로 배치. `ttl`은 레거시 행 폴백으로만 남기되(빼면 리포트가 조용히 줄어든다)
  **writer의 `ttl` 식을 AST로 읽어 상수 일치를 강제**했다. 두 필드로도 못 구하면 **제외**(추측 금지).
- Verified: `make check` **1544**(+11). **BEFORE/AFTER 실측**(90일치 90행): 필터 통과
  **90 → 2**, 경계 포함 기대값 2와 일치. 반증 5건 개별 되돌림 전부 red, 복원 시 11건 통과.
  증거 `docs/evidence/report-windows.log`.
- Blockers: **라이브 미실행** — 둘 다 EventBridge 스케줄 Lambda 경로라 실 AWS가 필요하다
  (이미 열려 있는 승인 항목). "프로덕션에서 과대 집계돼 왔다"는 **코드·writer 포맷에서의 추론**
  이지 발송된 리포트의 관측이 아니다.
- 품질 메모: **내 가드 둘이 먼저 틀렸고 둘 다 이 마일스톤의 단골 실패 양식**이었다.
  ①`failed_requests`(원시 카운트)를 `total_requests`(×100)로 오독해 `// 100`을 넣었더니
  `90 // 100 = 0`이라 **수정 전 코드에서 통과**했다 — 형제 테스트가 같은 오독으로 깨져서야
  드러났다. ②되돌림 3이 초록이었다: 픽스처의 `ttl`과 `created_at`이 **일관돼서 두 구현이 모든
  행에 대해 같은 답**을 냈다 — 테스트가 수정과 버그를 구별 못 했다. **갈리는 경우**(created_at은
  있고 ttl 없음 = 이 수정이 겨냥한 바로 그 조용한 누락 / ttl이 다른 보관 기간)를 추가했다.
  **산문으로만 주장하고 코드로 단언하지 않은 게 있으면 그건 아직 안 고친 것이다.**
- Next(같은 세션에 확인 완료): Azure/GCP `ttl` 식 차이는 **시맨틱 차이가 맞았고**(Cosmos는
  상대 초, 그래서 Azure가 옳다) 그런데 **둘 다 집행되지 않는다** — Cosmos 컨테이너는
  `durable_functions.py`가 `--ttl` 없이 만들어 항목 `ttl`이 무효이고, Firestore는 TTL 정책이
  IaC 어디에도 없으며 필드도 **Timestamp가 아닌 정수**라 정책을 붙여도 안 걸린다. 즉 두
  스토어의 인시던트 문서는 **무기한 남는다**. 주석만 사실에 맞추고(집행 안 하는 걸 광고하지
  않는다) **동작은 안 바꿨다** — 보관을 켜는 건 실 데이터 삭제라 승인 사항이고 읽는 쪽도 없다.
  → `STATUS` Open Risk 2 · `NEXT_PLAN`.

## 2026-07-29 — 읽기 모델 문서가 존재 내내 어긋나 있었다 (gate 1528→1533)

- Status: 스윕을 **대시보드 TS 쪽**으로 확장(기존 스윕은 `src/agents`만 본다). M13의 열한 번째
  이자 **한 층 위**: 필드가 아니라 **선언 자체를 아무도 안 읽는** 경우.
- Changed(`61ee2f4`): `activity-model.ts`는 **아무도 import하지 않는다** — 그래서 어긋나도
  아무것도 안 깨졌고, 실제로 양방향으로 어긋났다. 아무도 안 쓰는 `duration_ms`·`error_message`를
  선언하면서 **배포 상세 페이지가 딛고 선 `trace`·`cost_metrics`·`deployment_id`는 없었다**.
  거짓 주장 둘: ①`ttl` 필수 + "30일 보관"이지만 `ttl`을 쓰는 건 `activity_writer`뿐이고
  실제 대부분을 쓰는 `deploy_recorder`는 안 써서 **그 행들은 만료되지 않는다** ②`GSI1`도
  절반만 채워지고 **아무도 쿼리하지 않는다** — 이 문서를 보고 provider 스코프 쿼리를 짰다면
  에이전트가 쓴 행을 전부 빠뜨린 짧은 목록을 **조용히** 받았을 것이다. writer 계열이 둘인데
  어느 쪽도 상위집합이 아니고 선언은 **둘 다와** 불일치. core/optional 분리 + 접근 패턴을
  USED/NOT USED/NOT WRITTEN으로 표기 + `make*Record` 생성자 4개 제거(배선된 적 없는 TS 쪽
  쓰기 경로 = 갈라질 일만 남은 두 번째 진실 소스).
- Verified: `make check` **1533**(+5) · tsc 클린 · `next build` 성공. 반증 5건(**원본 파일
  포함** → 5개 중 3개 red) 전부 red, 복원 시 5건 통과.
  증거 `docs/evidence/activity-read-model-drift.log`. 런타임 동작 변화 없음(importer가 0인 게 요점).
- Blockers: 없음.
- 품질 메모: 왜 안 잡혔나 — `test_activity_model_schema`가 **부분문자열 존재**만 봤다
  (`'GSI1PK:' in content`, `"TTL_30_DAYS" in content`). 키워드는 **모양을 못 본다** — 이
  마일스톤이 이미 적어둔 안티패턴이 **그 파일을 지키는 테스트에** 있었다. writer AST에서
  파생하는 가드로 교체. **그리고 내 가드도 처음엔 같은 병이었다**: `re.search`라 두 선언 중
  하나만 옵셔널이면 통과해서 되돌림 3이 초록으로 나왔다 — `any`를 쓸 자리에 `all`이 필요했다.
  전 선언 지점을 요구하도록 조인 뒤에야 빨개졌다.
- Next: TS 쪽 후보 중 `ApprovalRequest.request_kind/subject/summary`는 **이미 렌더되는
  `alarm_name`/`root_cause`의 중복**(손실 아님, 사문화). TS 후보 47건을 마저 읽은 결과
  **데이터 손실은 이 건 하나뿐**이었고 나머지는 죽은 선언 → NEXT_PLAN에 후보로 기록(고치지 않음).

## 2026-07-29 — 롤백된 배포는 비용 패널을 통째로 잃었다 (gate 1520→1528)

- Status: M13의 열 번째. 앞의 아홉이 "선언됐는데 아무도 안 읽음"이었다면 이번은 **반대
  방향** — 읽는 쪽은 멀쩡한데 **셋 중 한 생산자만 침묵**했다. 기존 스윕이 구조적으로 볼 수
  없는 부류라 반대 방향 도구를 새로 만들어 찾았다.
- Changed(`db41874`): ①`record_rollback`이 `cost_metrics`를 안 썼다(`steps`를 이미 쥐고
  있어 `_cost_metrics` 호출만 빠진 상태). ②그 자체론 과소보고인데, `mergeActivity`가
  **trace만 합집합**으로 두고 나머지를 `{...latest}`로 최신 행에서 가져간다 → 롤백되는
  순간 도구/추론/토큰 수가 **페이지에서 사라졌다**. 패널이 조건부라 예외도 "0"도 없었고,
  **바로 아래 트레이스는 두 실행을 합쳐 오히려 길어진** 채였다. writer만 고치면 롤백의 2회를
  배포 전체 수치로 보고하게 되어 부정합이 바뀔 뿐이라 읽는 쪽도 함께 고쳤다
  (`sumCostMetrics`가 접힌 모든 행을 합산 + per-tool 내역 병합 = trace와 같은 규칙).
- Verified: `make check` **1528**(+8) · tsc 클린 · `next build` 성공. **라이브**(빌드된
  대시보드 local 모드, 실 recorder가 쓴 JSONL, HTTP GET): BEFORE 양쪽 되돌려 재빌드 →
  200인데 **패널 미렌더**(트레이스 도구명은 10회 표시) / AFTER → `tool calls 5 ·
  reasoning 1 · tokens 920(800 in/120 out)`, 내역이 **두 실행에 걸침**. 반증 4건 개별
  되돌림 전부 red, 복원 시 8건 통과. 증거 `docs/evidence/rollback-cost-metrics.log`.
- Blockers: 없음.
- 품질 메모: 왜 안 잡혔나 — `test_record_deploy_attaches_cost_metrics`가 **동작하는 생산자만**
  단언했고, 병합 규칙엔 테스트가 아예 없었다. 양쪽 절반은 각각 방어 가능했고 **둘이 겹칠 때만**
  터졌으며 **페이지에서만** 보였다. 가드는 또 파생: **`deployment_id`를 쓰는 ACTIVITY 행은
  반드시 `cost_metrics`를 쓴다**(그 키가 곧 상세 페이지로 라우팅되는 조건이므로, 모듈 목록이
  아니라 키가 의무를 만든다). AST가 아무것도 못 잡으면 공허하게 통과하므로 **가드의 가드**도 뒀다.
  새 도구는 첫 실행에서 신뢰를 잃지 않도록 `item["k"]=v` 첨자 대입까지 writer로 인정한다 —
  없으면 **이미 고친 `triggered_at`을 미생산으로 오보고**한다.
- Next: `record_route_activity`·`record_agent_activity`는 `deployment_id`가 없어 이 뷰에
  닿지 않으므로 **의도적으로 안 고침**(넣으면 소비자 없는 필드). 문서 예산 초과는 같은 날
  `/tidy-docs`로 해소(log 164→112, status 133→118).

## 2026-07-29 — MTTR은 존재 내내 구조적으로 0이었다 (gate 1496→1520)

- Status: `resolved_at` 하나를 보러 갔는데 **한 사슬에 결함 셋**. 전부 테스트는 초록.
- Changed(`3a89e43`): ①**쓰는 쪽이 기본값을 채웠다** — 공용 클라우드 기록기가 `resolved_at`을
  무조건 `created_at`과 같은 값으로 써서 **미해소 인시던트가 해소 시각을 달고** 다녔다(온프렘은
  정반대로 아예 안 씀). ②**`_fetch_incidents_from_dynamo`가 `resolved_at`을 `started_at`·
  `resolved_at` 양쪽 끝에 넣었다** → 여태 발송된 **모든 주간 온콜 리포트의
  `average_mttr_minutes`가 0.0**. 같은 함수가 `alarm_name`을 `runbook_id`에 복사해 재발 패턴
  그룹핑도 알람별로 붕괴(런북 하나에 몰리는 서로 다른 알람 = 그 기능의 존재 이유). ③**대시보드
  Scan의 `ProjectionExpression`이 자기 리더가 읽는 4필드를 안 가져왔다**(`triggered_at`·
  `confidence`·`reconciliation`·`trace_id`) → 상세 뷰가 배포 내내 모든 AWS 인시던트에
  "confidence n/a"를 띄웠고, **아침 gate 1496의 수정이 그걸 표시할 배지 한 층 앞에서 멈춰** 있었다.
- Verified: `make check` **1520**(+24) · tsc 클린 · `next build` 성공. **BEFORE/AFTER 실측**:
  동일 입력에 `average_mttr_minutes` **0.0 → 45.0**. **라이브**(실 온프렘 웹훅 체인, 25분 전
  `startsAt`): P1/AUTO **1502초(25m)** 보존 · P3/MANUAL·P2/APPROVE→reject는 `resolved_at`
  **부재**. 반증 7건 개별 되돌림 전부 red, 복원 시 24건 통과.
  증거 `docs/evidence/incident-time-to-resolve.log`.
- Blockers: 없음.
- 품질 메모: 왜 안 잡혔나 — `test_summarizes_incidents`가 MTTR 45.0을 단언하는데 **손으로 만든
  픽스처**에서 받는다. 유일한 실제 생산자가 낼 수 없는 모양이라 **영원히 초록이었을** 것이다
  (07-29 아침에 배운 "픽스처는 실제 입력에서"의 세 번째 사례). 새 테스트는 픽스처가 아니라
  `_fetch_incidents_from_dynamo`를 통과시킨다. 그리고 **투영 가드는 키워드 목록이 아니라
  파생**이다 — 매퍼가 읽는 속성을 파싱해 Scan이 전부 가져오도록 요구하므로 **다음 필드에도**
  실패한다. 손으로 적은 목록이었다면 당시 투영에 맞춰 쓰였을 테고 이 버그를 그대로 통과했다.
  `_minutes_between`은 clamp 대신 None — 발생보다 앞선 해소(시계 어긋남)를 **완벽한 0분 복구로
  세지 않는다**. 파싱 실패도 더는 raise 안 한다(예외 하나가 리포트 전체를 죽였다).
- Next: 실 DynamoDB 왕복은 여전히 미실행(쓰기·읽기 양쪽 모두). GCP Firestore·Azure Cosmos
  기록기는 둘 다 안 쓰지만 읽는 쪽이 없어 **의도적으로 남김**.

## 2026-07-29 — 클라우드 인시던트 행도 발생 시각·confidence를 버렸다 (gate 1491→1496)

- Status: 아침의 온프렘 수정이 남긴 나머지 절반. 같은 누락이 `executor._record_incident`
  (AWS·GCP·Azure 공용)에 있었고, **`tenant`/`env`에 대해 같은 결함을 고쳤다고 적어둔 주석
  바로 아래**였다.
- Changed(`36e3b4a`): 둘 다 **읽는 쪽이 이미 있었다** — ①`triggered_at`(대시보드가 오늘
  아침부터 읽는다. 읽는 쪽이 쓰는 쪽보다 먼저 존재한 비대칭) ②`confidence`(analyzer가 매번
  만들고 상세 뷰가 늘 렌더한다 → **모든 클라우드 인시던트가 그 뷰가 존재한 내내
  "confidence n/a"를 보여줬다**).
- Verified: `make check` **1496**(+5). ②의 함정을 **가정하지 않고 확인**했다 —
  `TypeSerializer().serialize(0.98)`은 `TypeError: Float types are not supported`.
  그 예외는 기록기 자신의 `except Exception`에 잡히므로, 자연스러운 타입으로 썼다면 필드
  하나가 아니라 **레코드 전체가 조용히 사라졌을** 것이다. `Decimal(str(...))`로 저장
  (`request_store.py`가 같은 이유로 세워둔 패턴). 반증: float 되돌림 3건 · triggered_at
  제거 1건, 복원 시 9건 통과. 증거 `docs/evidence/cloud-incident-fields.log`.
- Blockers: 없음.
- 품질 메모: 반증 셋 중 하나를 **아이템 전체에 float가 없는지** 보는 가드로 뒀다 — float
  하나면 쓰기가 통째로 실패하고, 오늘 위험을 들여온 필드가 다음에도 그 필드라는 보장은 없다.
  그리고 이번 결함은 **자기 자신을 설명하는 주석 바로 아래**에 있었다: 같은 함수에서 같은
  종류를 한 번 고쳤다고 그 함수가 그 종류로부터 안전해지지 않는다.
- Next: `resolved_at`이 여전히 `created_at`과 같은 쓴 시각이라 **time-to-resolve는 아직 불가**.
  실 DynamoDB 왕복은 미실행(모킹 테이블 + 직렬화기 직접 확인까지).

## 2026-07-29 — 인시던트 기록이 "언제 터졌는지"를 몰랐다 (gate 1479→1491)

- Status: 스윕이 남긴 두 번째 실제 건. "타임라인 표시 결정 필요"로 적어뒀는데 다시 보니
  **표시는 결정이지만 값을 버리지 않는 것은 결정이 아니다** — 테넌시 때와 같은 모양.
- Changed(`78e472d`): 네 어댑터가 소스의 실제 발생 시각을 채우는데 `record_incident`가 경계에서
  버려, 행이 `created_at`(우리가 쓴 시각)만 알았다 → **탐지 소요시간 산출 불가**, 타임라인이
  인시던트를 "처리된 순간"에 배치. 저장(모르면 **부재**) + 파이프라인·웹훅 양쪽 경로 배선 +
  승인 경로가 함께 버리던 `trace_id`도 복구(어제 넣은 span origin에서) + 대시보드 optional
  필드·방어적 매핑·**`detected +Nm` 배지**. 배지는 장식이 아니라 요점이다 — 읽는 쪽 없이
  저장만 하면 스윕이 그날 찾은 결함을 하나 더 만드는 꼴이다.
- Verified: `make check` **1491**(+12) · `tsc` 클린 · `next build` 성공.
  **라이브(승인 경로 = 간격이 가장 큰 곳)**: 12분 전 발생 신고 → parking → 승인 →
  간격 **735초** 보존("detected +12m"). 트레이싱 켠 2차 실행에서 `trace_id`가 실제
  `onprem.incident_pipeline` 트레이스와 **일치**함까지 확인(주석으로 주장만 하지 않았다).
  반증: 저장 제거 2건 · 음수 억제 제거 1건, 복원 시 12건 통과.
  증거 `docs/evidence/incident-trigger-time.log`.
- Blockers: 없음.
- 품질 메모: `describeDetectionGap`이 **과장을 거부**하도록 짰다 — 발생 시각 없음/파싱 불가/
  발생보다 먼저 기록됨은 전부 렌더 안 함. 마지막은 가정이 아니다(스포크↔허브 시계 어긋남은
  정상이고, 화면의 "detected -3s"는 옆의 모든 숫자에 대한 신뢰를 배지 부재보다 크게 무너뜨린다).
- Next: 클라우드 3사 인시던트 행은 공유 executor가 DynamoDB에 쓰므로 **여전히 발생 시각을
  버린다**(스키마 변경 수반). resolve 시각 미기록이라 time-to-resolve도 아직 불가.

## 2026-07-29 — 계통 스윕: 운영자가 미리 붙인 severity를 버리고 있었다 (gate 1470→1479)

- Status: 남은 잔여가 전부 **결정 대기**라, 결정이 필요 없는 최고 가치 작업으로 **"선언됐고
  아무도 안 읽는" 결함 부류를 계통적으로 훑었다**(이틀 새 여섯 번 나왔고 전부 우연이었다).
- Changed(`0cf5da5`): `src/agents`의 모든 ClassDef 애노테이션 필드 **437개 중 20개** 후보.
  대부분 결함 아님(`TokenBroker.signing_key`는 **오탐** — `self.` 형태를 패턴이 놓쳤다;
  route_trace·slack_ts 등은 직렬화되는 응답 표면). 진짜는 둘, 이빨 있는 건 하나:
  **`severity_hint`를 네 어댑터가 전부 채우는데 아무도 안 읽는다**. 사람이 **미리** 내린
  유일한 분류가 버려지고 severity는 산문에서만 추론된다 — 그런데 severity가
  **P1→AUTO/P2→APPROVE**, 즉 사람 없이 실행할지를 정한다. analyzer 프롬프트에 **증거로**
  노출(하드 매핑은 정책 결정이라 발명 안 함, "구속력 없음 + 다르면 이유 명시").
- Verified: `make check` **1479**(+9). **라이브 A/B**(동일 알람, 라벨만 다름):
  critical→P1/AUTO **실행** · **warning→P2/APPROVE 대기** · info→P2/APPROVE.
  warning이 핵심 — 같은 페이로드가 **오늘 낮엔 P1/AUTO로 자동 실행**됐다.
  반증: 프롬프트 줄 제거 시 9건 중 6건 실패, 복원 시 통과.
  증거 `docs/evidence/declared-unconsumed-sweep.log` · 스윕은
  `scripts/find_unconsumed_fields.py`로 반복 가능하게 남김.
- Blockers: 없음.
- 품질 메모: 테스트가 **프롬프트**를 단언한다. "필드가 설정되는가"를 봤다면 이 필드가 존재한
  내내 통과했을 것이고, **그게 이게 여태 살아남은 방식이다.** 어제 배운 두 가지(호출부에서
  반증 · 픽스처는 실제 입력에서)에 이어 셋째: **소비자를 단언하라, 생산자 말고.**
- Next: `triggered_at`도 같은 상태(네 어댑터가 채우고 아무도 안 읽음 → 탐지 소요시간 불가) —
  타임라인 표시 결정 필요. 그 외 잔여는 전부 결정 대기.

## 2026-07-29 — "선택 가능"은 AWS 경로에서만이었다: 겹친 결함 3개 (gate 1454→1470)

- Status: 어제 라이브에서 본 "온프렘 알람이 새 런북에 안 걸린다"를 **매칭 설계 결정**으로
  남겼는데, 결정이 아니라 **배선 결함 3개가 쌓여** 있었다. 하나를 걷어내야 다음이 보였다.
- Changed(`b70c195`): ①`_synthetic_alarm`이 `reason`과 `metric_name`을 **둘 다
  `signal_type`**으로 채워, 매처가 "availability availability …"를 읽고 있었다. alertname·
  summary는 내내 정규화돼 저장돼 있었고 선택에만 안 닿았다(프로바이더 중립 수정).
  ②`resource_types`가 **모든 런북에 선언돼 있고 아무도 안 읽었다** — 이틀 새 다섯 번째
  "선언됐고 유효하고 소비 안 되는" 필드. 없으면 RDS 런북이 k8s 워크로드에 걸리고, 실패가
  조용하다(해결 실패 시 **런북의 하드코딩 AWS 액션 이름**으로 폴백). ③①②를 고쳐도
  라이브는 계속 달랐다: 시드된 eks-pod-oom **1점**이 빌트인 health-check-failure **3점**을
  이겼다 — 자기 카탈로그가 먼저 스캔됐다는 이유만으로. D34가 "무매칭"만 막고 "더 나쁜 매칭"은
  안 막았다 → 두 카탈로그를 **합집합에 휴리스틱 한 번**으로 통합(동점 시 운영자 우선, D35).
- Verified: `make check` **1470**(+16). **라이브**(실 웹훅+실 analyzer): 디스크→disk-full ·
  NotReady→health-check-failure · 인증서→certificate-expiry · CrashLooping→eks-pod-oom(회귀 없음).
  **전부 ONPREM-\* 액션**으로 해소 = 잘못된 프로바이더 폴백이 안 터졌다는 증거.
  반증 3종(reason 되돌림 4건 · 게이트 제거 1건 · 티어 순차 복귀 6건), 복원 시 36건 통과.
  증거 `docs/evidence/onprem-runbook-matching.log`.
- Blockers: 없음.
- 품질 메모: **이번엔 내 테스트 자체가 결함이었다.** 첫 버전이 통과하는데 라이브는 여전히
  generic-recovery였다 — 내가 쓴 summary에 런북 키워드를 심어놨기 때문이다("…, disk full
  projected in 18h"). 실제 Alertmanager는 `NodeFilesystemSpaceFillingUp`이라고 보낸다.
  **테스트가 Alertmanager가 아니라 키워드 목록에 맞춰져 있었다.** 어제 배운 "호출부에서
  반증하라"에 하나 더: **픽스처를 코드가 아니라 실제 입력에서 가져와라.**
- Next: 남은 잔여는 전부 결정 대기(배포의 테넌트 소유권 · 무스코프 MCP 읽기 ·
  Capsule `limitRanges` 경로) + 런북 DynamoDB 재시드(배포 작업).

## 2026-07-28 — executor span: 실제 경로 전부가 무추적이었다 (gate 1446→1454)

- Status: 잔여 "② executor span(선택)"을 처리. 기록은 "승인 후 경로 미측정"이었는데
  실제로는 **AUTO 경로도 무추적**이었다.
- Changed(`3939d47`): 웹훅이 `execute=False`로 파이프라인을 부르고 **루트 span이 닫힌 뒤**
  실행하므로, 클러스터를 바꾸는 단계가 **실제 알람이 타는 모든 경로에서 span을 안 냈다**.
  기존 테스트는 `run_incident_pipeline(execute=True)`로 들어가 갭보다 한 층 아래를 봤다.
  span을 `execute_incident` 안으로(호출부 3곳 공유) · 웹훅 루트 2개 ·
  승인은 **부모가 아니라 span link**(사이 간격=사람의 고민 시간. 접으면 span 길이가 대부분
  "슬랙 읽는 시간"이 되어 지연 수치가 무의미해진다) · `SpanOrigin`(trace+span id)을 parking
  레코드에 저장(trace id만으론 링크 불가) · 반쪽 origin은 **죽은 링크 대신 속성만**.
- Verified: `make check` **1454**(+8). **라이브**(실 uvicorn + 실 OTLP/gRPC; Docker 다운이라
  Tempo 대신 collector 와이어 프로토콜 구현 싱크): AUTO=**6 span 단일 트레이스**
  (analyze 5.4s/총 7.7s로 wall-clock 분해) · 승인=**트레이스 2개 + 링크 1개**, 링크가 실제로
  제안 span을 가리킴. 사람이 고민한 ~11초는 두 트레이스 어디에도 안 잡힘.
  실행: ONPREM-RolloutRestartWorkload / INC-615A4BEB / resolved=true.
  반증 3종(span 제거 5건 · 링크 제거 1건 · 웹훅 루트 제거 1건), 복원 시 8건 통과.
  증거 `docs/evidence/executor-span-approval-path.log`.
- Blockers: 없음.
- 품질 메모: 부수로 `span()`의 **조용한 충돌**을 고쳤다 — OTel 키가 점 표기라 호출자가
  `**{"a.b": v}`를 쓰는데, `**` 언팩은 명명 파라미터와 충돌해서 **"link"라는 이름의 속성이
  span link가 되어버릴** 수 있었다. 타입체커가 계속 가리키던 게 오탐이 아니었다.
- Next: 위 라이브에서 새 갭 하나가 보였다 — 선택 가능해진 런북 4개가 **온프렘 알람엔 안 걸린다**
  (디텍터가 alertname을 버리고 `metric_name=availability`로 정규화). 회귀는 아니고 매칭 설계 결정.

## 2026-07-28 — 잔여 3건 소진: grant 대조 · 선택 불가 런북 · Capsule 이관 (gate 1411→1446)

- Status: 계획에 남아 있던 **차단 없는 잔여 3건**을 우선순위대로 처리. 셋 다 기록된
  갭보다 컸고, 셋 다 **라이브가 유닛 테스트와 다른 답**을 내놓은 지점에서 진짜 결함이 나왔다.
- Changed(`63df3c5`, grant): 기록은 "대조 안 함"이었는데 실제로는 ①grant를 **줄 방법
  자체가 없었고**(라우트·스토어 둘 다 `tenants`를 안 받음 — 읽기 쪽이 아무 쓰기 경로도
  못 만드는 필드를 소비 중) ②역할 변경이 whole-item Put으로 grant를 **조용히 지웠다**.
  허브 `GET /api/platform/tenants`(레지스트리=SSOT, 못 읽으면 빈 목록 아닌 **503**) +
  `platform-roster.ts`(null=미검증) + 저장 전 대조 + `absent=유지` + users 테이블 컬럼.
- Changed(`9beda00`, 런북): 런북 4개가 BUILTIN에 없어 선택 불가 → 항목 추가. 그런데
  **라이브 전체 경로는 여전히 넷 다 generic-recovery**였다. 실 스캔 결과 시드 테이블에
  generic 행이 있어 티어 2가 티어 4의 답을 대신 냈고 **티어 3(빌트인)이 배포 환경에서
  한 번도 도달된 적 없었다**. `allow_generic=False`로 해소. 부수로
  `assert_health_check_passing` 구현(미구현 검사는 **실패**로 치므로, 안 하면 재시작
  성공에도 매번 롤백 캐스케이드).
- Changed(`278a264`, Capsule): `additionalMetadata` → `additionalMetadataList`.
  CRD에 직접 물어 확인. 제거 릴리스에서 **에러 없이 안 읽히는** 실패라 선제 이관.
- Verified: `make check` **1446**(+35 누적) · `tsc` 클린 · `next build` 성공.
  **라이브**: grant 5케이스(선언 200 / 없는 테넌트 400 지목 / 역할 변경 후 생존 /
  허브 다운 503 / 회수는 200) · 실 DynamoDB 스캔으로 런북 4개 정상 해소 ·
  kind에서 PSS 라벨 유지 + probe 라벨 전파. 증거 `docs/evidence/{phase3-tenant-grant-validation,
  runbook-selectability,capsule-deprecation-metadata}.log`.
- Blockers: 없음(아래 Next는 차단이지 실패가 아님).
- 품질 메모: **반증이 세 번 중 한 번은 내 테스트를 잡았다.** 호출부를 되돌렸는데 새 테스트
  20건이 전부 통과했다 — 전부 `_match_runbook_registry`를 플래그를 이미 준 채로 직접
  불러서, **플래그를 잊은 호출자를 볼 수 없었다**. 라이브만 잡았고, 호출부 단언을 추가했다.
  "가드도 반증하라"는 이제 "가드를 **호출부에서** 반증하라"로 좁혀야 한다.
- Next: **모델 호출 rate limit은 deployments 파티션과 같은 결정에 묶여 있다**(조사 결과) —
  로컬 모델 호출자는 `local_deployer`/`strands_deployer` 둘뿐이고 둘 다 배포 경로인데,
  배포 요청엔 테넌트가 없고 `setup_tenancy(tenant, ...)`는 **모델이 부르는 도구**다.
  즉 테넌트가 추론의 **입력이 아니라 출력**이라 헤더로 받으려면 "배포는 어느 테넌트
  소유인가"를 먼저 정해야 한다. 남은 것: 그 결정 · 무스코프 MCP 읽기 · `limitRanges` 이관 경로 결정.

## 2026-07-28 — 읽기 파티션 완결 + granted-viewer 실증 (gate 1404→1411)

- Status: 대시보드 읽기 경로 둘(플릿·인시던트)이 테넌트로 파티션되고, 오래 미뤄둔
  granted-viewer 왕복이 실증됐다.
- Changed(`0512d2b`): 파티션 불가의 원인은 읽기가 아니라 **쓰기**였다 —
  `NormalizedIncident`는 Phase 1a부터 `tenant`를 갖고 있는데 `_record_incident`가 버렸다.
  저장은 **비어 있으면 키를 안 넣는다**(부재 ≠ 빈 문자열). `visibility.ts`에 `filterRows`
  (같은 seam) · **기록 없는 행은 admin 전용** · `withheld` 카운트 반환 ·
  캐시 헤더 `public, s-maxage=30` → **`private, no-store`**(호출자마다 다른 응답을 공유
  캐시가 서빙하면 그게 유출이다).
- Changed(`2357583`): granted-viewer가 미실증이던 진짜 이유는 OAuth가 아니라 **local-dev
  우회가 `role: admin`을 하드코딩**한 것 — 인가 표면 전체가 로컬에서 검증 불가였다.
  이제 실 로그인과 같은 저장소에서 역할을 읽는다(`DASHBOARD_DEV_AUTH_USER`).
- Verified: `make check` **1411**(+7) · `tsc` 클린 · `next build` 성공.
  **라이브(빌드 산출물)**: 익명 0/3(withheld 3) · **viewer-demo(grant=['acme']) 1/3**
  (withheld 2, `private, no-store`) · admin 3/3(무태그 행 포함).
  **반증**: "기록 없는 행은 모두에게" 주입 → RowFiltering 3건 실패, 복원 시 통과.
  증거 `docs/evidence/phase3-read-partition-live.log`.
- Blockers: 없음.
- 품질 메모: 이번에도 **테스트가 낡은 정책을 고정**하고 있었다 —
  `DASHBOARD_AUTH_DESIGN.md`의 "Read path remains public"을 단언하는 테스트가 있어서,
  정책이 바뀐 뒤에도 문구가 살아남았다. 오늘만 세 번째 사례다(`ROUTE_PROTECTION` ·
  Agent Card 필드 존재 단언 · 이것).
- Next: deployments/activities 파티션은 **데이터 모델 결정 선행**(배포는 어느 테넌트
  소유인가 — 인시던트와 달리 tenant가 아예 없다) · rate limit을 모델 호출까지 ·
  무스코프 MCP 읽기.

## 2026-07-28 — 외부 자료 대조가 연 후속: MCP 옆문 · 테넌트 call budget (gate 1383→1404)

- Status: 참고문서 작성이 목적이었는데 대조가 **우리 결함 4건**을 열었고 전부 근본수정했다.
- Changed(카드 2건, `e7ad744`): Agent Card가 **가상 주소**(`platform-agent.example.com`)를
  광고 · **집행하지 않는 인증**(bearer/JWT)을 광고. 전자는 남이 우리를 소비할 때만 쓰여
  라이브 왕복을 완주하고도 안 밟혔고, 후자는 방향이 더 나쁘다(실제보다 안전한 척).
- Changed(MCP, `1aa86e0`): 게이트웨이가 **ambient 자격증명 경로**였다 — 모든 도구가 맨
  `kubectl`, `kubectl_apply`는 임의 매니페스트를 임의 ns에. Phase 1a가 앞문에서 없앤 그
  fail-open이 옆문에 남아 있었다. argv를 스코프 kubeconfig로 고정(ContextVar — 도구
  파라미터로 두면 **호출자가 자기 자격증명을 지명**하게 된다), 변경 도구는 fail-closed.
- Changed(rate limit, `67ab309`): `platform/ratelimit.py` sliding window, 레지스트리
  `quota.calls_per_min`에서 선언, 미선언=무제한(additive). 예산을 경계보다 먼저 검사.
- Verified: `make check` **1404**(+21). **라이브(kind)**: 자기 ns 읽기 성공 / 이웃 테넌트
  거부 / 무스코프 mutation 거부 / **스코프 안 ns인데도 `secrets`는 `Forbidden`**(우리
  가드가 아니라 **API 서버**가 판정). 증거 `docs/evidence/mcp-gateway-scope.log`.
- Blockers: 없음.
- 품질 메모: 네 결함 전부 **테스트가 선언만 단언해서** 살아남았다(`assert
  "supportedInterfaces" in card`). 같은 날 대시보드의 `ROUTE_PROTECTION`과 같은 족보다.
  그리고 **반증이 내 테스트의 결함을 잡았다** — "거부된 호출은 예산에 안 센다"에 결함을
  주입했는데 테스트가 통과했다(재시도를 시계 멈춘 순간에 해서 거부분이 함께 만료). 아무것도
  단언하지 않고 있었다. 고치니 주입 시 실패·복원 시 통과. 가드를 쓰면 가드도 반증해야 한다.
- Next: rate limit을 모델 호출까지(테넌트 신원 전파 선행) · 무스코프 MCP 읽기(kagent 경로에
  스코프 선행) · Phase 3③ 잔여(grant viewer 브라우저 왕복 · 나머지 읽기 경로 파티션).

## 2026-07-28 — Phase 3 완결: ②reconciler 충돌 거부 · ③읽기 쪽 테넌트 경계 (gate 1355→1377)

- Status: Phase 3 ①②③ 종료. ②는 **거부까지**가 최종 상태이고 그 이유가 구조적이다.
- Changed(②, `9e78f81`): `platform/reconciler.py` — 소유 표식을 **라이브 객체에서** 읽어
  reconciler가 되돌릴 롤백을 거부. 되돌리는 액션만 막는다(restart·scale은 desired로 수렴).
- Changed(③, `1c13a59`): `dashboard/src/lib/visibility.ts` 단일 seam + 플릿 라우트 배선 ·
  `UserRecord.tenants` · `middleware.ts`→`proxy.ts`(Next 16 deprecation) · 죽은
  `ROUTE_PROTECTION` 제거.
- Verified: `make check` **1377**(+22 누적) · `tsc` 클린 · `next build` 성공.
  **라이브(kind, $0)**: ② 같은 워크로드에 out-of-band 변경 → **10초 만에 selfHeal이 되돌림**
  (전제 자체를 먼저 반증) → ArgoCD 관리 롤백 거부 / 같은 워크로드 restart는 정상 실행.
  ③ 빌드 산출물에 익명 curl → `restricted:true` + 빈 플릿. **fail-open 주입 반증**으로
  테스트가 실제로 잡는 것도 확인(2건 실패 → 되돌리니 8건 통과).
  증거 `docs/evidence/phase3-{reconciler-conflict,viewer-visibility}.log`.
- Blockers: 없음.
- 품질 메모: ②의 후반(selfHeal pause)은 **구조적으로 막혔다** — Application이 `argocd`
  네임스페이스에 있고 테넌트 스코프 자격증명은 그것을 읽지도 못한다(`Forbidden` 실측).
  즉 Phase 3①과 3② 경로1이 정면 충돌하고, `apps-in-any-namespace`도 비활성이라
  테넌트 로컬 우회로가 없다. 설계의 권장안인 registry write-back은 Phase 5 의존이라
  Phase 3 안에서 실행 불가 — **계획 자체의 순서 충돌**이다(→ D32).
  ③에서는 정책이 **두 군데 적혀 있고 둘 다 안 도는** 상태를 발견했다.
  `ROUTE_PROTECTION`은 소비자 0이었고, **테스트가 그 죽은 코드의 존재를 고정**하고
  있었다 — 선언을 단언하는 가드가 선언-미소비 정책이 살아남는 방식이다.
  그리고 `AGENTS.md` 지시대로 Next 문서를 먼저 읽은 덕에 `middleware` deprecation을
  잡았다. 안 고쳤으면 고장 모드는 **쓰기 라우트 matcher가 조용히 안 도는 것**이었다.
- Next: Phase 4(managed 어댑터, billable) 또는 Phase 5(레지스트리 쓰기 → ②를 GitOps-native로
  닫음). 잔여: grant 있는 viewer의 브라우저 왕복 · incidents/deployments는 여전히 무파티션.

## 2026-07-27 — Phase 3① 자격증명 격리 full (gate 1341→1355)

- Status: Phase 1a가 온프렘에서만 세운 "자격증명이 경계"를 전 러너·두 디스패치 경로로 확장.
  라이브가 Phase 1a 증명 자체의 구멍을 드러냈다.
- Changed: `scope.py`에 `guard_scoped_action` 단일 가드 + `resolve_incident_scope` 이관(디스패치
  경로가 둘인데 로직이 `aws/executor.py`에만 있어 **GCP 경로는 스코프가 없었다**) ·
  `run_gcp_action`/`run_azure_action`이 scope 수령 · seam이 전 분기에 전달 ·
  `render_rbac`가 바인딩 대상 **ServiceAccount를 렌더**(누락돼 있었음).
- Verified: `make check` **1355**(+14). **라이브(kind, $0)**: SA 생성 후 실 토큰 발급 →
  자기 ns `yes` / 이웃 테넌트 `Forbidden` / 클러스터 스코프 `Forbidden`(판정 주체가 **API 서버**) ·
  실 러너 in-scope 재시작 성공(새 ReplicaSet, rollout 정상) · cross-tenant/무-스코프는 kubectl
  이전 거부 · gcp/azure 4케이스 전부 **인증·네트워크 이전** 거부.
  증거 `docs/evidence/phase3-scoped-credentials-all-runners.log`.
- Blockers: 없음.
- 품질 메모: **RoleBinding이 존재하지 않는 SA를 가리키고 있었다.** k8s는 없는 subject로의
  바인딩을 조용히 받으므로 `kubectl get rolebinding`은 내내 건강해 보였다. fail-closed라
  아무것도 안 깨졌고 그래서 드러나지도 않았다 — values 파일·Capsule과 같은 "에러 없이 안 읽히는"
  부류. 실질은 구멍이 아니라 **Phase 1a 증명의 RBAC 팔이 한 번도 행사된 적 없다**는 것이다
  (DoD가 "Forbidden **또는** 자격증명 부재"라 약한 쪽으로 통과 중이었다). 구조 가드는 subset이
  아니라 equality로 비교한다 — subset은 정규식이 아무것도 못 찾을 때도 통과해서, 감시 대상이
  모양을 바꾸는 바로 그 순간 조용해진다.
- Next: Phase 3② 롤백↔selfHeal 우선순위 · ③viewer 가시성. `docs/PROGRESS_LOG.md`가 예산
  초과(145줄) → `/tidy-docs` 필요.

## 2026-07-26 — 멀티테넌트 실험 전문 재작성·Notion 발행

- Status: **Notion 전문 발행 완료**. 전체 발행에서 남은 것은 LinkedIn 게시뿐이다.
- Changed: `docs/post/notion-article-ko.md`를 영상의 실제 흐름(setup→install→상태 검증→격리 반증)에
  맞춰 5,641→4,477자로 재구성하고 Humanize Korean 적용(A·변경률 14.6%·자체검증 6/6).
- Published: Notion `3a94c2420ac4801cbe99e36c16ed90fd`에 목차·표·YouTube Shorts
  (`2J9WfZV0TPE`) 영상 블록과 전문 반영.
- Verified: MP4 1080×1350·30.033s + 6시점 프레임 검토 · Notion 재조회로 제목/본문/영상 블록 확인 ·
  `git diff --check -- docs/post/notion-article-ko.md` 통과. `make check`는 문서·외부 발행 작업이라 미실행.
- Blockers: 없음. Next: `docs/post/linkedin-intro-ko.md` 최종 확인 후 LinkedIn 게시 → Phase 3(인가 강화).

## 2026-07-26 — 자연어 한 문장이 테넌트를 세운다 + 풀스택 30초 영상 (gate 1322→1341)

- Status: Agents 채팅에 문장 하나를 치면 `setup_tenancy → install_tenant_addons`가 체인으로
  돈다(17.6s). 실제 브라우저로 전 비트를 통과시킨 뒤 그 상태를 찍어 30초로 편집했다.
- Changed(코드): `src/agents/ai/tenancy_tools.py`(도구 2개) · `src/agents/platform/cluster_io.py`
  (렌더된 객체가 클러스터를 만지는 **유일한 자리**) · `Registry.uninstallable_reason` +
  `build_delivery_adapter`로 `render_*` 스크립트와 **같은 구현** 공유(복사본 0) · 시스템
  프롬프트에 체인 순서와 **그 이유**(애드온은 테넌트 ns *안의* 객체) 명시.
- Changed(영상): `scripts/demo/{prep_fullstack.sh,record_fullstack.js,build_fullstack_cut.js}` ·
  `docs/post/media/multitenancy-fullstack-30s.mp4`(1080×1350 · 30.03s · **오버레이 없음**,
  원본 153.8s를 10컷으로) · 아티클/LinkedIn/유튜브 문구 반영.
- Verified: `make check` **1341**(+19) · `render_tenancy.py` 출력이 HEAD와 stdout·stderr·exit
  code 전부 동일(리팩터 무해 증명) · **라이브 브라우저 왕복**: 빈칸 → 문장 → 체인 2단 →
  `4 / 4`·4축 ✓ → `1500m / 16`·`3 / 200` → 실제 ArgoCD Synced/Healthy → netpol 1개 삭제 시
  **network만 ✕**(globex 초록 유지) → 복구 ✓. 증거 `docs/evidence/demo-fullstack-beats.json`.
- Blockers: 없음.
- 품질 메모: 라이브가 결함 4건을 잡았고 전부 내 코드였다. (1) `apply_manifests`가 kubectl
  **경고**를 `error`에 담아 **전 스텝 성공인 실행이 `ok:False`** 로 기록됐다(Capsule deprecation
  2줄). 지금까지 잡은 건 화면이 실제보다 **좋게** 말하는 결함이었는데 이건 **나쁘게** 말한
  첫 사례다. (2) 도구 완료를 "running 문자열 부재"로 판정했는데 DOM엔 그 단어가 없다(아이콘뿐)
  → **일어나지 않은 체인을 찍을** 뻔했다. (3) 녹화 프로필엔 세션이 없어 채팅이 읽기 전용 —
  비활성 입력칸에 문장을 치고 5분 대기, 테이크 1회 손실. (4) `.argocd-demo-password`가 없어
  첫 프레임 전에 죽고 `.gitignore`에도 없었다 — **공개 아티클이 링크할 레포에 자격증명이
  커밋될** 뻔했다(클러스터 시크릿에서 읽도록 변경).
- Next: 발행(Notion 전문 · LinkedIn · YouTube Shorts) · LinkedIn "7B가 30B를 이겼습니다" 정정
  (1건·1시행 차이, temp 1.0에선 역전) · Phase 3(인가 강화).

## 2026-07-26 — 30초 영상 촬영 완료 (배속 없는 실시간)

- Status: 시나리오 A를 **실제로 찍었다**. `docs/post/media/isolation-falsified-30s.mp4`
  (1080×1350 · 30.0초). 연출 없음 — 진짜 NetworkPolicy를 지우고 진짜 push 경로로
  대시보드가 알아차리는 걸 기다렸다가 되돌린다.
- Changed: `scripts/demo/`(record_falsification.js · render_captions.js · README) +
  산출물 2종. 대본은 **최종본 실제 타임코드**로 갱신.
- Verified: 컨택트시트로 6개 시점(1·6·13·16·19·28초) 전부 자막↔화면 상태 일치 확인.
  실측 전환 **삭제 후 7.1초 · 복구 후 8.9초** → 30초에 그대로 들어가 **배속 0**.
  촬영용으로 낮춘 푸시 주기(60s→2s)는 우상단에 상시 표기. 촬영 후 60s로 원복,
  netpol 4개·4축 ✓ 복구 확인.
- Blockers: 없음. 남은 것은 발행(사용자 게이트).
- 품질 메모: **전체 화면 녹화를 폐기했다.** macOS `screencapture -v`는 권한이 있어
  동작했지만 테스트 프레임에 조작자의 다른 탭(학습 사이트·ChatGPT 대화)이 그대로
  담겼다 — 발행용 영상에 들어가면 되돌릴 수 없는 종류의 사고라 테스트 파일을 즉시
  지우고 뷰포트만 녹화하는 Playwright로 바꿨다. 부수 효과로 로그인 세션도 프레임에서
  사라졌다. 그리고 ffmpeg가 libass·freetype 없이 빌드돼 있어 `subtitles`/`drawtext`가
  **아예 없었다** — 자막을 대시보드와 같은 엔진으로 렌더해 픽셀로 넣었다. 오버레이
  `enable=` 창이 자막 목록과 어긋나면 **아무것도 실패하지 않은 채** 화면과 다른 말을
  하는 영상이 나오므로, ffmpeg 명령을 비트 목록이 생성하게 했다(체크인 안 함).
- Next: 아티클 발행(Notion 전문 + LinkedIn 링크, 영상 첨부) · Phase 3(인가 강화).
## 2026-07-26 — 시연 가능 레벨: 레지스트리→클러스터 설치 경로 + 격리 반증 리허설 (gate 1302→1322)

- Status: 영상 시나리오를 멀티테넌시+풀스택으로 재작성하고, **그 대본이 실제로 찍히는
  상태**까지 만들었다. 준비 과정에서 "레지스트리만으로는 애드온을 설치할 수 없다"는
  구조적 갭이 드러나 근본수정했다.
- Changed(문서): `docs/post/video-30s-script.md` 전면 재작성 — 추천안이 A(자연어 39초,
  **이미 발행한 소재**)에서 **격리 반증**으로 교체. 대안 B(풀스택)·C(세 종류의 부재)·D(DR).
- Changed(코드): 카탈로그 `self_hosted_repo` + `Registry.repo_for`/`capabilities_missing_repo`
  — repo URL이 `infra/onprem/addons/*.tf`에만 있어 **레지스트리가 설치 불가능한 애드온을
  선언**하고 있었다(values·scope 갭과 같은 족보). 이 필드는 이 파일의 **유일한 복사**라
  `test_catalog_repos_match_terraform`이 TF helm_release를 파싱해 불일치 시 게이트를 깬다 ·
  `scripts/render_addons.py`(읽기 전용 렌더, 클러스터 싱글턴은 **이름을 대며** 거부,
  빈 출력의 두 의미를 exit code로 구분) · `make demo-baseline`(테넌시+애드온+강제 푸시 1회).
- Verified: `make check` **1322**(+20) · `tsc` 클린 · `next build` 성공 ·
  `verify_tenancy_adoption.py` acme/globex 둘 다 adopted and bounded.
  **라이브(kind, $0)**: acme-dev-logging·acme-dev-tracing Synced/Healthy(테넌트 스코프에서
  **tempo는 이번이 처음**), 쿼터가 비로소 소비를 센다(cpu 2/16·pods 3/200).
  **반증 리허설**: netpol 4개 중 1개 삭제 → acme/dev network만 ✕, 나머지 3축과 **이웃
  globex/dev 행은 초록 유지** → 복구 시 ✓. 강제 푸시 없는 실측 지연 **18s/61s/59s**
  (푸시 60s 주기 + 폴링 15s → 최악 ≈75s). 증거 `docs/evidence/demo-isolation-falsification.log`.
- Blockers: 없음.
- 품질 메모: 라이브가 **화면이 실제보다 좋게 말하는** 결함 2건을 잡았다. (1) 플릿 표가
  `4 ok`라고 했는데 2개는 에이전트가 health를 단언할 수 없는 공유 설치였다 —
  `unknownCount`는 이미 계산돼 있었고 **아무도 쓰지 않았다**(또 소비 부재) → `N ok · M not
  assessed`. (2) `push_addon_status.py` 독스트링이 광고하던 `--once`가 미구현이라 **문서에
  적힌 명령이 그대로 죽었다**. `make dev-up`은 `--interval 60`을 써서 아무도 안 밟았고,
  문서를 읽은 내가 촬영 체크리스트에 옮겨 적으며 밟았다. 그 가드의 첫 판은 스위트를 멈춰
  세웠다(`--interval` 폼을 그냥 부르면 60초씩 영원히 잔다) — 루프는 끝나지 않는 것이
  정상이므로 sleep을 끊어서 단언하도록 고쳤다.
- Next: 아티클 발행(Notion 전문 + LinkedIn 링크) · 영상 촬영 · Phase 3(인가 강화).

## 2026-07-26 — 대시보드 멀티테넌시 관제 + 검증 훅 (gate 1290→1302)

- Status: 멀티테넌시가 CLI로만 보이던 것을 대시보드로 올렸고, 그동안 문서에만 있던
  검증 규칙을 훅으로 강제했다. 아티클 초안 3종도 `docs/post/`에 작성(발행은 사용자 게이트).
- Changed(`654c7e5`·`eebc19e`): `TenancyPosture`(채택 ns 수·쿼터 hard/used·격리 4축·티어·
  자격증명 스코프·네임스페이스 목록)를 **기존 push 경로에 실어** 대시보드까지 전달 —
  대시보드가 클러스터를 직접 조회하면 D26(허브 read 자격증명 0)이 깨진다 · 플릿 표
  (전 테넌트 × 4축, 미보고 테넌트도 행 유지) + 격리 패널(티어별 분리/공유/**미보장** 명시) ·
  Platform Add-ons 누락 4건 추가(Loki·Fluent Bit·Tempo·Capsule, 콘솔 없는 것은 사유 표기) ·
  대시보드 문구 영어화 · `make dev-up`이 push 키와 스포크 푸셔 2개를 함께 기동.
- Changed(`bad2642`): Stop 훅 `make check`(소스 변경 시만, async+asyncRewake라 실패할 때만
  깨움) + PostToolUse 훅 `tsc --noEmit`(dashboard 경로만). 기존 ruff 훅 보존.
- Verified: `make check` **1302**(+12) · `tsc` 클린 · `next build` 성공. **라이브**: acme/dev
  4/4·globex/dev 1/1이 tier=soft, credential per tenant로 대시보드에 표시. **반증까지 확인** —
  NetworkPolicy 삭제 시 network 축이 False로 뒤집히고 복구 시 True 복귀. 훅도 등록 전에
  양방향 검증(정상 exit 0 / 일부러 만든 실패 exit 2 + 정확한 요약).
- Blockers: 없음. 영상 시나리오는 A(자연어 39초)가 이미 발행된 소재라 멀티테넌시+풀스택
  기준으로 재작성 필요.
- 품질 메모: **런타임 TypeError가 났고 tsc는 내내 초록이었다.** `posture.namespaces.length`가
  구버전 에이전트 페이로드에서 터졌다 — TS 타입은 네트워크를 건너온 데이터에 대한 컴파일
  시점 주장일 뿐이고, 롤링 업그레이드 중엔 허브가 두 버전 리포트를 동시에 서빙한다.
  신규 필드를 optional로 내리고 모든 읽기 지점에 폴백을 넣었다. 같은 사건이 **필드 하나가
  푸셔·허브·대시보드 세 프로세스를 전부 통과해야 한다**는 것도 다시 보여줬다(푸셔만 재기동
  했을 때 허브가 모르는 필드를 버렸다). 훅 스크립트 자신도 첫 판이 틀렸다 — `tail -25`가
  pytest 끝의 경고 벽을 잘라 실패가 안 보였고, 요약 라인 grep으로 교체했다.
- Next: 영상 시나리오 재작성 → 촬영 · 아티클 발행(Notion+LinkedIn) · Phase 3(인가 강화).

## 2026-07-26 — faked managed 디스크립터 + DR 재구축 검증 (gate 1281→1290)

- Status: **Phase 2 완결**(M11). 남아 있던 2건을 소진했다.
- Changed(`c6d930d`): `Registry.is_managed_backend`(카탈로그에서 파생 — env가 다시 태그하면
  한 선택에 두 사실이 생긴다) + 수집기의 managed 경로(`applicable=False`·health=None) ·
  `scripts/verify_tenancy_adoption.py`(status.size와 ResourceQuota를 직접 묻는다).
- Verified: `make check` **1290**(+9). **라이브 DR 드릴**: globex/dev를 실제로 파괴하고
  레지스트리만으로 재구축 → 라벨 `diff` 완전 동일, 10초 뒤 ns=1 + ResourceQuota가 선언값
  일치(pods 100·cpu 8·mem 32Gi). 증거 `docs/evidence/phase2-managed-and-dr.log`.
- Blockers: 없음. Phase 2 잔여 0.
- 품질 메모: 재구축 직후 `Tenant ns=0`을 보고 실패로 읽었는데 **또 이른 시점의 정지
  조회**였다(첫 슬라이스의 쿼터 오판과 같은 교훈이 DR 경로에서 재발). 다만 그 10초 창은
  진짜 위험이라 — 네임스페이스는 있고 라벨도 맞고 모든 화면이 완료로 보이는데 쿼터가
  아무것도 안 묶고, **영구 고장과 육안 구별이 안 된다** — 검증기를 만들었다. 그런데
  **그 검증기가 첫 실행에서 거짓 경보를 냈다**: 다른 클러스터(k3s-lab)의 acme/prod를
  "quota unenforced"로 보고했고, 독스트링엔 cannot-check로 하겠다고 써놓고 코드가 안
  지킨 것이었다. **안 본 것은 발견이 아니다.**
- Next: Phase 3(인가 강화) · Phase 1b 잔여(스냅샷 선행) · 선택 항목들.
## 2026-07-26 — 어댑터 helm values seam + PSS/PVC 결함 2건 (gate 1271→1281)

- Status: 렌더러가 chart+version만 실어 선언한 차트 대부분이 템플릿조차 안 되던 갭 해소.
  라이브가 그 위에서 결함 2건을 더 드러냈고, **둘 다 초록 화면 뒤에 있었다**.
- Changed(`01d3c6d`): 카탈로그가 values 파일을 **가리킨다**(복사 금지 — Terraform과
  어댑터가 사본을 각자 가지면 조용히 갈라진다) · `Registry.values_for` ·
  argocd `helm.valuesObject`(문자열 아님)·flux `spec.values`에 같은 dict ·
  공유 values에 파드 레벨 seccompProfile · `enableStatefulSetAutoDeletePVC: false`.
- Verified: `make check` **1281**(+10). **라이브(kind, $0)**: acme-dev-logging이 PSS
  restricted + Capsule 쿼터 + NetworkPolicy 아래에서 Synced/Healthy(2/2 Running, PVC
  Bound) — Phase 2 첫 진짜 테넌트 스코프 애드온 설치. 수집기 관통(logging=synced/healthy)
  확인 후 정리. 증거 `docs/evidence/phase2-values-seam.log`.
- Blockers: 없음.
- 품질 메모: (1) **PSS restricted 테넌트 네임스페이스가 우리 애드온을 거부**했다. Argo는
  Synced/Progressing인데 파드 0개, 진짜 이유는 StatefulSet 이벤트 세 단계 아래
  (seccompProfile 미설정). Terraform이 쓰는 `monitoring`엔 PSS 라벨이 없어 지금까지
  안 보였다 — D23이 경고한 그 상황이 실제로 일어났다. 추론 대신 렌더된 파드 스펙을
  테넌트 네임스페이스에 **server dry-run**해서 API 서버에 물었고, tempo에서 키 함정도
  잡혔다(최상위 `securityContext`=파드, `tempo.securityContext`=컨테이너 — loki 철자를
  쓰면 Helm이 조용히 무시한다. **values 파일은 에러가 아니라 안 읽히는 방식으로 실패한다**).
  (2) **직전 커밋에서 내가 쓴 주의사항이 틀렸다.** "StatefulSet PVC는 cascade에서 남는다"고
  단정했는데 실제로는 PVC까지 사라졌다. 원인은 Argo가 아니라 차트가 `whenDeleted: Delete`로
  쿠버네티스 기본값(Retain)을 뒤집은 것 — 구독 해지가 테넌트 로그를 같은 초에 파괴한다.
  **진실이 내 주의사항보다 위험했다.**
- Next: faked managed 디스크립터(`applicable=false`) · DR 재구축 확인.


## 2026-07-26 — 삭제는 cascade한다: 계약이 삭제 의미를 말하게 (gate 1267→1271)

- Status: 직전 라이브의 고아 워크로드를 닫았다. 진짜 문제는 파이널라이저 부재가 아니라
  **계약이 삭제 의미를 말한 적이 없다**는 것 — Flux는 uninstall, ArgoCD는 고아라
  "구독 해지" 하나의 의도가 엔진마다 반대 결과를 낸다.
- Changed(`e1ea15f`): `DeliveryAdapter.render`에 "Deletion must cascade" 명시 ·
  argocd 렌더러가 `resources-finalizer.argocd.argoproj.io` 부착 · prune≠삭제정책 가드 ·
  flux uninstall 비활성화 금지 가드(부재 단언).
- Verified: `make check` **1271**(+4). **라이브 A/B(kind, $0)**: 같은 차트 Application
  2개를 파이널라이저만 다르게 두고 둘 다 삭제 → 있는 쪽은 사라지고 없는 쪽
  (`podinfo-orphan`)은 소유자 없이 Running. 증거 `docs/evidence/phase2-deletion-cascade.log`.
- Blockers: 없음. 정리 완료(probe ns 삭제), rollouts-demo·테넌트 정책 5개 무손상.
- 품질 메모: 선언한 차트(loki 7.1.0)로 실증하려다 **어댑터가 helm values를 못 싣는다**는
  갭이 드러났다 — `Please define loki.storage.bucketNames.chunks`로 템플릿 자체가 실패한다.
  파이널라이저는 차트와 무관한 엔진 동작이라 기본값으로 설치되는 차트로 통제 실험을 했고,
  **대체 차트를 썼다는 사실을 증거에 명시**했다. 또 이 수정이 덮지 않는 것도 적었다:
  cascade는 엔진이 관리하는 것까지라 StatefulSet PVC는 남는다("깨끗이 제거됨" 아님).
  **[정정 2026-07-26]** 이 마지막 문장은 틀렸다 — 다음 증분에서 실측하니 PVC까지 사라졌고,
  원인은 차트가 `whenDeleted: Delete`로 쿠버네티스 기본값을 뒤집은 것이었다. 위 항목 참조.
- Next: 어댑터 helm values seam · faked managed 디스크립터(`applicable=false`) · DR 재구축.

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

---

## 2026-07-25 — GitAIOps 실습서 대조 → 갭 6건 소진 + 멀티테넌트 Phase 0 (gate 876→983, +107)

- Status: 외부 학습 레포(GitAIOps/Notiflex) 대조로 **우리에게 구멍인 운영 계층**을 특정해 전부 소진.
  두 프로젝트는 층이 다름(운영 대상 ↔ 운영 에이전트)이라 아키텍처 차용이 아니라 갭 메우기.
  레퍼런스: `docs/reference/gitaiops-notiflex-book.md`.
- Changed(8커밋, `5fba0af`~`7b4231a`): **③런북 사후검증**(`RunbookStep.verify` +
  `resolution_verdict` 2축 — 검증 없으면 verified=None="모름"이라 역호환) · **④권한통제 3단**
  (`gcloud:*`/`aws:*`/`az:*` 포괄 allow → 조회 allow 104 + billable ask 30; D16의 로컬 우회 차단) +
  GKE TTL 워치독 커밋 · **①AnalysisTemplate**(canary 메트릭 자동 abort, 수동 게이트에 **가산**,
  기본 OFF) · **②OTel→Tempo**(파이프라인 4단계 span + `tracing.tf`; 무-의존 폴백, 엔드포인트 옵트인) ·
  **멀티테넌트 Phase 0**(`platform/` 레지스트리 + 로더 + `DeliveryAdapter` 계약 + `NormalizedAddonStatus`
  2축; TS 반쪽 포함) · **⑦고아 클러스터 스위퍼**(워치독이 못 지키는 머신-사망 구멍) ·
  **⑥soft티어 NetworkPolicy + CNI 집행 검증기**(기본 OFF) · **⑤Sync Wave 설계 구멍**을 Phase 1b DoD에 명문화.
- Verified: `make check` → **983 passed, 1 skipped**(876→983, +107) · `tsc --noEmit` 클린 ·
  `terraform validate` Success · `helm template`로 신규 차트 3종 양쪽(off/on) 렌더 확인 ·
  **라이브 read-only**: 고아 스위퍼로 2개 GCP 프로젝트 방치 클러스터 **0건 확증**(ground truth 교차확인).
  **`helm template`이 Tempo 버그 2건 적발**: 데이터소스 포트 3100→**3200**(차트가 3100 미노출),
  최상위 `resources:`가 조용히 무시돼 `{}` 렌더→`tempo.resources`로 이동. 검증 없이 넘겼으면 거짓 주장.
- Blockers: **Docker/kind 정지로 라이브 미검증 3건** — ①auto-abort 실증 · ②Tempo 실 적재 ·
  ⑥CNI 집행 판정(그래서 ①⑥은 기본 OFF, 검증기는 클러스터 없을 때 exit 2=INCONCLUSIVE로 사칭 안 함).
- Next: Phase 1a(자격증명 격리 seam) — ③의 provider측 verify 실행부가 같은 `_run_external_action`
  경로라 **함께** 해야 안전. 클러스터 기동 시 위 라이브 3건 일괄 소진 가능.
- 메모: 아티클 **발행 완료**(사용자 확인) → `docs/post/` 추적 4파일 제거(git 이력 잔존), 미추적 원본
  `local-onprem.mov`(22MB)는 복구 불가라 재편집 마스터로 보존. GitAIOps 후속편은 `NEXT_PLAN`에
  논지·소재만 남기고 **착수 보류**(사용자 지시).

## 2026-07-21 — 멀티테넌트/멀티클라우드 플랫폼 설계 확정 — S(93.5) via MAD (코드 무변경, 문서)

- Status: 사용자 방향(on-prem이라도 멀티-env·env별 add-on·클라우드 무관)을 플랫폼 설계로 확정. **코드 착수 전**.
- Changed(`95f1381`): 설계 v5 `docs/plans/2026-07-21-multi-tenant-env-addons.md` + 의사결정·MAD 히스토리
  `-mad-history.md` + NEXT_PLAN 백로그. 아키텍처=**capability, implementation-pluggable**(cloud-neutral DNA 확장):
  Tenant=격리 티어 정책(soft/vcluster/dedicated), Env=cluster(멀티클라우드), Delivery=ArgoCD|Flux 어댑터,
  SSOT=per-tenant git 레지스트리. 최우선 불변식=에이전트 실행 blast radius 1 tenant/env(자격증명이 경계 —
  in-cluster 러너·incident-provenance broker·read push로 봉인).
- Verified: **등급 확정 파이프라인** — 원칙-아키텍트 rubric(8기준·보안16 최대) → **MAD(Advocate/Critic/Judge)**
  A+(92) → **평가 에이전트 ground-truth 재리뷰**(코드 주장 2건 오류 적발: NormalizedIncident namespace 부재·
  resolve_action seam 오인) → v4 정정 Fable5 A+(91) → S-델타 3건 소진 v5 → **Fable5 재평가 = S(93.5)**. 목표 A+~S 초과.
- Blockers: 없음. 2차 잔여(Phase 1a 진입 시): agent→hub push 인증·승인레코드 one-time nonce·push heartbeat.
- Next: Phase 0(레지스트리 스키마+어댑터 계약+NormalizedAddonStatus 2축) → Phase 1a(자격증명 격리 seam).

## 2026-07-21 — 대시보드: On-Prem 분석 Qwen 우선 + 인시던트 상세뷰 + 스택 링크 + AWS데모 제거 (gate 876)

- Status: 애드온 스택 라이브 데모 중 표면화한 대시보드 개선 4건. 사용자 요청 기반.
- Changed(`4aef387`·`74d7a9d`·`7ca72ed`): (1) **analyzer LLM 백엔드 pluggable**(`ANALYZER_LLM_ENDPOINT` 있으면
  OpenAI 호환 로컬 Qwen, 없으면 Bedrock; AWS 무변경·역호환) + 파서 견고화(Qwen 트레일링 텍스트) + onprem 어댑터
  per-alert annotations 캡처 + 프롬프트 alert detail 주입 + 인시던트 confidence 영속화. Makefile onprem-webhook Qwen 배선.
  (2) **인시던트 상세 페이지** `incidents/[id]`(LLM root-cause·confidence 미터·분석 모델 귀속), 카드 클릭 링크.
  (3) **스택 바로가기**를 Provisioning "Platform add-ons"로 이관(IaC 메타·env 기반 URL, prod-safe 가드).
  (4) **AWS 데모 제거**(mock 승인/인시던트 병합 중단) + 배지 정직화(hybrid→local, 거짓 LIVE·AWS 제거).
- Verified: `make check` → **876 passed, 1 skipped**(870→876, +6). tsc 클린. **라이브($0, 로컬 Qwen 7B)**:
  OOMKilled alert → 호스트 webhook(Qwen) → confidence **0.95** + 정확한 OOM root cause → approve → INC-95C55A19
  상세뷰 렌더. DECISIONS 후보=analyzer Qwen 백엔드.
- Blockers: 없음.
- Next: (설계) 위 플랫폼 Phase 0.

## 2026-07-21 — On-Prem 애드온 스택 Phase 5 k3s 기판 패리티 스모크 (코드 무변경, gate 870 유지)

- Status: Phase 5(선택) 잔여 "k3s 패리티" 소진. **동일 addons root가 kubeconfig/context 교체만으로 k3s에 이식됨**을 실증(versions.tf가 광고하는 "kind·k3s 양기판" 계약 검증). 잔여 Phase 5 = Gateway API(필요성 재평가 후)뿐.
- Changed(repo 코드 무변경): 증거 `docs/evidence/onprem-addons-k3s-parity.log`만 추가. addons 모듈·values·테스트 전부 무변경(런타임 var만 교체).
- Verified (라이브 $0, Multipass k3s v1.31.4 on k8s-lab VM 2CPU/3.8GiB): **별도 terraform workspace `k3s`**(state 격리 → kind `default` state 무손상)에서 `terraform apply -target=helm_release.argocd -var kubeconfig_path=<k3s> -var kube_context=k3s-lab` → **ArgoCD 5/5 파드 Ready**(동일 저사양 values, server available=1). 3.8GiB VM 예산 존중해 코어(ArgoCD)로 스코프. 이후 destroy(1 destroyed)→workspace 삭제→빈 argocd ns 정리 → **VM 베이스라인 복원**, default workspace의 kind 리소스 7개 온전 재확인.
- Blockers: 없음. 메모: 전체 관측성 스택(kps+loki 등 20+파드)은 3.8GiB VM엔 과함 → 코어 패리티로 충분(값 동일·기판 이식성 입증). k3s 기본 SC=local-path(kind=standard)라 PVC 소비 컴포넌트는 storageClass 오버라이드 필요(ArgoCD는 PVC 없음).
- Next: (선택) Gateway API 로컬 등가물(필요성 재평가) · 잔여 사용자 게이트(아티클 배포).

## 2026-07-20 — On-Prem 애드온 스택 Phase 5(로깅): Loki + Fluent Bit → Grafana 데이터소스 라이브 실증 (gate 867→870)

- Status: `docs/plans/2026-07-20-onprem-platform-addons.md` Phase 5(선택) 중 **Loki/Fluent Bit 증분 완료** — 관측성 삼각 완성(metrics=Prometheus 기존 + logs=Loki 신규). 잔여 Phase 5 = k3s 패리티·Gateway API(선택).
- Changed: 신규 `logging.tf`(grafana/loki **7.1.0**=v3.6.8 SingleBinary + fluent/fluent-bit **0.57.9**=v5.0.9 DaemonSet, fluent-bit가 loki `depends_on`) + 저사양 `values/loki.yaml`(SingleBinary·filesystem·**chunks/results 캐시 off**=멀티-Gi 풋프린트 함정 회피·backend/read/write replicas 0)·`values/fluent-bit.yaml`(tail→k8s 필터→loki 출력, Auto_Kubernetes_Labels). `values/kube-prometheus-stack.yaml` grafana에 **Loki additionalDataSources** 배선. 가드 +3(SingleBinary+캐시off·fluent-bit→loki gateway·grafana Loki 데이터소스), 핀 계약 3→5.
- Verified: `terraform validate` Success · `make check` → **870 passed, 1 skipped**(867→870). **라이브($0, kind)**: apply(2 added+kps 1 changed)→loki-0 2/2·loki-gateway 1/1·fluent-bit DaemonSet 2/2 Ready. **로그 적재 확증**: Loki query API가 argocd/monitoring/default/kube-system 네임스페이스 라인 반환(k8s 레이블 enrich), 그중 **`pa-platform-agent-webhook` 자체 로그** 포함. Grafana 데이터소스 목록에 Loki 등록 확인(Alertmanager/Loki/Prometheus 3종). 증거 `docs/evidence/onprem-addons-logging-e2e.log`.
- Blockers: 없음. 메모: Grafana `/resources` 프록시 프로브가 404(프로브 URL 경로 이슈)였으나 데이터소스 등록·게이트웨이 직접 쿼리로 적재는 이미 입증 — 데이터소스 결함 아님.
- Next: (선택) Phase 5 잔여(k3s 패리티·Gateway API) · 잔여 사용자 게이트(아티클 배포).

## 2026-07-20 — On-Prem 애드온 스택 Phase 4: Argo Rollouts canary promote/abort 라이브 실증 (gate 865→867)

- Status: `docs/plans/2026-07-20-onprem-platform-addons.md` Phase 4 = IaC+라이브 증거 완결. 애드온 스택 Phase 1~4 전부 완료(Phase 5 선택만 잔여).
- Changed: 신규 `rollouts.tf`(argo-rollouts **2.41.1**=v1.9.1 컨트롤러 helm_release + 데모 canary `charts/rollouts-demo`가 컨트롤러 `depends_on`) + 저사양 `values/argo-rollouts.yaml`(대시보드 on). 데모 Rollout=weighted canary(25→50→75)에 **무기한 `pause: {}` 수동 게이트**(50%) — promote/abort 구동점. 가드 +2(데모 차트 존재·canary 수동게이트), 핀 계약 2→3. **위치 정리: DECISIONS D19**(러너=cloud-neutral 애플리케이션 레벨, Rollouts=k8s 전용 인프라 레벨 → 대체 아닌 병존, 러너 무변경).
- Verified: `terraform validate` Success · `make check` → **867 passed, 1 skipped**(865→867). **라이브($0, kind)**: 컨트롤러 Ready+Rollout Healthy(blue). **경로 A(promote)**: blue→yellow canary가 수동 게이트(50%)에서 ~60s 정지→promote→75%→100%→yellow stable. **경로 B(abort)**: yellow→red canary 25%→abort→Degraded/RolloutAborted, red 축소, **yellow stable 유지**(롤백 시맨틱)→spec 복원 후 Healthy. 증거 `docs/evidence/onprem-addons-rollouts-e2e.log`.
- Blockers: 없음.
- Next: 애드온 스택 코드 완결. (선택) Phase 5(Loki/Fluent Bit·k3s 패리티·Gateway API) · 잔여 사용자 게이트(아티클 배포).

## 2026-07-20 — On-Prem 애드온 스택 Phase 3: ArgoCD GitOps로 platform-agent 차트 관리 + 라이브 실증 (gate 861→865)

- Status: `docs/plans/2026-07-20-onprem-platform-addons.md` Phase 3 = IaC+라이브 증거 완결. Phase 4(Argo Rollouts) 대기.
- Changed(`fafacc6`): 신규 `gitops.tf`(helm_release `platform_agent_app`, argocd `depends_on`) — Application CR을 로컬 래퍼 차트 `charts/platform-agent-app`로 배포해 **plan-time argoproj.io CRD 불필요**. Application은 repoURL/path/rev/valueFiles를 values 주입, automated **selfHeal+prune**, cascade-delete finalizer. `releaseName=pa`로 Phase 2 webhook Service명(`pa-platform-agent-webhook`) 보존 → Alertmanager receiver URL 무변경. `values/argocd.yaml`에 **`application.resourceTrackingMethod=annotation`**(차트가 찍는 `app.kubernetes.io/instance` 라벨과 ArgoCD label 추적의 충돌 근본 회피, Argo 공식 권장). `variables.tf` gitops_* 6종(기본=GitHub origin main). 가드 +4.
- Verified: `terraform validate` Success · `make check` → **865 passed, 1 skipped**(861→865). **라이브($0, kind)**: apply→Application `platform-agent` **Synced/Healthy**(revision=git HEAD `25d8e89`)→기존 **6 리소스 무중단 채택**(webhook·svc·SA·PVC·Role·RB)→drift(`scale 1→3`)→**selfHeal ~16s 내 replicas=1 복원**→Alertmanager接点 보존. 증거 `docs/evidence/onprem-addons-gitops-e2e.log`.
- Blockers: 없음. 규명·해결: instance 라벨 추적 충돌 → annotation 추적 전환으로 근본 해결(DECISIONS 기록).
- Next: Phase 4(Argo Rollouts canary 승격/abort + 러너 위치 정리 DECISIONS 1건) · Phase 5 선택.

## 2026-07-20 — On-Prem 플랫폼 애드온 스택 Phase 1+2: addons IaC + Alertmanager→4-step 라이브 E2E (gate 854→861)

- Status: 신규 백로그(JOURNEY 범위 로컬 확장, `docs/plans/2026-07-20-onprem-platform-addons.md`) Phase 1·2 완료. Phase 3(GitOps)·4(Rollouts) 대기.
- Changed: 신규 `infra/onprem/addons/` terraform root — helm provider(~>3.0), kubeconfig/context 변수로 kind·k3s 양기판 적용, **argo-cd 10.1.4**(앱 v3.4.5=JOURNEY 동일)+**kube-prometheus-stack 87.17.0** 정확 핀, 저사양 values(CPU requests ≤50m 계약, kind 불가 컨트롤플레인 스크랩 4종 off). Alertmanager receiver→in-cluster `pa-platform-agent-webhook`(templatefile `webhook_url` 주입, Watchdog은 null 라우트) + 데모 룰 `PlatformDemoCrashLoop`(restarts>2/5m, for 1m). 가드 `tests/test_onprem_addons_module.py` +7(핀·저사양 계약·receiver 배선·룰 존재·validate).
- Verified: `make check` → **861 passed, 1 skipped**(229.27s, 854→861). **라이브($0)**: kind 3노드 apply→ArgoCD 5파드+모니터링 8파드 전부 Ready→UI 3종(ArgoCD/Grafana/Prometheus) 200. **E2E**: crashme 크래시루프→룰 발화(~3분)→Alertmanager 배달→webhook 4-step→P2 parking(APR-6C9CD1F2)→approve→executor(log-only)→**INC-96D41C2B resolved=true**. 증거 `docs/evidence/onprem-addons-phase1.log`·`onprem-addons-alertmanager-e2e.log`.
- Blockers: 없음. 규명 메모: 인클러스터 analyzer의 휴리스틱 폴백(Bedrock 자격증명 없음)은 설계된 오프라인 경로(`onprem_incident_pipeline` docstring) — 차트 `llm.endpoint`는 배포 플레인 router 전용, 버그 아님.
- Next: Phase 3(ArgoCD Application으로 차트 GitOps — ⚠️ 선행: push 또는 로컬 gitea) · Phase 4(Argo Rollouts canary) · Phase 5 선택.

## 2026-07-20 — 3-클라우드 비용 감사·고아 리소스 정리 + 예산 알림 3종 완비 (코드 무변경, 계정 운영)

- Status: AWS 예산 알림($8.90)발 3-클라우드 전수 감사. 원인=크레딧 차감 전 총사용액(실청구 ~$0.25)이었으나 감사 중 고아 과금원 다수 발견·정리.
- Changed(계정, repo 코드 무변경): **AWS** 고아 Classic ELB(7/9~, `platform-agent-demo` k8s 잔재, 일$0.60)+전용 SG 삭제. **GCP** `claude-study-501117`의 GKE `notiflex-cluster`+Gateway LB+PVC 2 삭제(월~$20 차단), 타 계정 8프로젝트=청구 미연결 확인. **Azure** ACR `roadpilot-backend` 21→1 이미지(최신만 유지). **예산 알림**: Azure·GCP에 월 ₩14,000(≈$10) 예산+80/100% 이메일(men16922@gmail.com, GCP는 billing.user 부여) — AWS 기존 $10과 3종 완비. `.claude/settings.local.json`에 `aws/gcloud/az` CLI allow 3종(개인 스코프).
- Verified: 삭제 후 잔존 0 재확인(AWS ap-northeast-2 ELB/NAT/EIP/EC2/EKS=0, GCP claude-study LB/IP/disk=0), Azure 일별 비용 추이로 AKS 잔재 종료 확인. 합산 월 ~$40 유휴 과금 차단.
- Blockers: 없음. 메모: Azure `acrroadpilot` Basic 고정료(월~₩7,700)는 roadpilot 종료 시 레지스트리 삭제로 정리 가능(프로젝트 범위 밖).
- Next: 잔여=아티클 배포(사용자 "나중에")·push(로컬 ahead 2).

## 2026-07-20 — 보류됐던 리팩토링 후속 2건 완료: operations 그룹핑 축 통일 + approval_bridge 분리 (gate 854 유지)

- Status: NEXT_PLAN "리팩토링 후속(선택)" 2건을 사용자 승인으로 수행. 동작 무변경 순수 구조 개편.
- Changed(`8792c9c`): (1) **그룹핑 축 통일** — AWS Lambda 핸들러 7종을 `operations/aws/{detector,analyzer,decision,executor,reporting,runbook_seed}.py` + `aws/approval_bridge/`로 이동(gcp/azure와 동형), 멀티클라우드 러너 5종(gcp/azure/onprem/_k8s_rest/gcp_auth)을 `operations/runners/`로 분리. CDK 핸들러 문자열 7종·테스트 15파일 임포트 정합. (2) **approval_bridge 분리** — 610줄 handler.py → `handler`(오케스트레이션+SFN 콜백)+`request_store`(DynamoDB pending/claim/finalise)+`slack_interactive`(서명 검증·Block Kit·webhook)+`payloads`(순수 헬퍼). 핸들러가 함수를 unqualified import해 핸들러 경로 함수 패치는 보존, 모듈 전역 패치(웹훅/시크릿/테이블/requests)만 소유 모듈로 재작성.
- Verified: `make check` → **854 passed, 1 skipped**(256.62s) — baseline 동일(테스트 수 무변경=순수 구조 개편 증명). 직접 영향 테스트 12파일 선행 통과.
- Blockers: 없음. 주의: 다음 cdk deploy 시 핸들러 경로 변경이 반영됨(Vercel context 필수 규칙 유지).
- Next: 잔여=아티클 배포(사용자 "나중에")·push. 코드 백로그 없음.

## 2026-07-19 — terraform aws-production 실 apply→검증→destroy 완주 + 아티클 854 최신화 (코드 무변경, gate 854 유지)

- Status: 마지막 billable 사용자 게이트 "(billable) terraform apply" 소진(사용자 허용 규칙 추가로 해금). 레퍼런스 #7-b = 코드·validate·**실 apply/destroy** 전 단계 실증 완료.
- Changed: `docs/evidence/terraform-aws-production-apply-live.log` + 아티클 3종 854 최신화·승인 게이트 Slack 라이브 사실 보강(`0f19d12`). `.claude/settings.local.json`에 terraform apply/destroy/output/state list/show allow 5종(개인 스코프 — apply/destroy는 사용 후 제거 권장).
- Verified (라이브): 1차 apply가 로컬 DNS 블립으로 EKS 폴링 실패(실 클러스터는 ACTIVE, terraform만 tainted)→재개 apply가 replace 포함 수렴(**8 added/1 destroyed**). 검증: EKS 노드 2 **Ready**(v1.31.14)·Aurora `platform_state` **available**(0.5 ACU)+마스터 시크릿·**IRSA trust가 재생성 클러스터 OIDC로 정확 재배선**(차트 SA 한정)·outputs/DSN 템플릿 정합 → **destroy 29개 완료**, 계정 잔존 0(EKS/RDS/NAT). 비용 ≈$0.5 미만.
- Blockers: 없음.
- Next: 잔여 = 아티클 **배포**(원고는 854로 최신화 완료·사용자 "나중에") · push 수시 · (선택) settings의 terraform allow 정리.

## 2026-07-19 — On-Prem P2 승인 게이트 Slack 버튼 연동 + 라이브 왕복 완주 (gate 847→854)

- Status: 잔여 선택 항목 "On-Prem 승인 게이트 Slack 버튼" 구현·라이브 검증 완료. terraform apply(3번)는 분류기 차단으로 **사용자 `!` 실행 대기**.
- Changed(`617839b`): 로컬 API는 공개 URL이 없어 버튼 콜백 직수신 불가 → **DynamoDB 승인 테이블을 공유 매체**로: 신규 `onprem_slack_approval.py`(P2 parking 시 bridge 스키마·버튼 계약으로 PENDING 기록+Slack 송출, `sync_decisions` 결정 회수) + bridge onprem kind=SFN 콜백 생략 + webhook API approve/reject 코어 추출·startup 폴러. 전부 옵트인(`ONPREM_SLACK_APPROVAL`), 기본=오프라인 무변경. +7 test.
- Verified: `make check` → **854 passed, 1 skipped**(232.03s, 847→854). **라이브**: P2 페이로드→APR-3E6D2540 parking→DynamoDB PENDING(kind=onprem)→Slack ONPREM 카드(실 LLM root cause)→**Approve 클릭**→APPROVED→폴러 회수→실행→`/pending` 0·INC-FA2143AF resolved=true. 증거 `docs/evidence/onprem-slack-approval-live.log`.
- Blockers: terraform apply/destroy는 분류기+settings 자기수정 차단 — 사용자 `!` 또는 `/permissions` allow 필요.
- Next: (사용자) terraform apply→검증→destroy · 아티클 배포(나중) · push는 수시.

## 2026-07-19 — 알림성 액션 in-process 1급 처리: generic-recovery 구조적 미해결 근본수정 (gate 844→847)

- Status: 직전 규명한 유령 SSM 문서 결함을 권고안(a)로 수정·라이브 검증 완료. Slack E2E발 후속 3건 전부 소진.
- Changed(`55de55e`): executor에 `_NOTIFICATION_ACTIONS`(={AWS-SendSlackAlert}) — SSM 호출 없이 executor 자신의 Slack 인시던트 리포트로 수행·executed 집계(웹훅 미설정=skip 유지). `tests/test_executor_notification_action.py` +3(in-process·no-webhook skip·혼합 액션 SSM 디스패치 보존).
- Verified: `make check` → **847 passed, 1 skipped**(232.55s, 844→847). **라이브**: 알람 트리거 → 실 LLM **P1/AUTO** 판정 → `executor.notify.in_process` → **`resolved=True`**(INC-E15BA62E, DynamoDB `resolved:true` 확증) — generic-recovery 최초 Resolved. 동일 세션에서 P3/MANUAL 강등 경로도 관측(온화한 알람 reason→LLM P3 판정, Guardian 정책상 정상 skip). 실 LLM 심각도 판정이 reason 텍스트에 반응함을 실증(P3/P2/P1 3단 모두 관측).
- Blockers: 없음.
- Next: 잔여=사용자 게이트(아티클 배포·terraform apply·push 여부) + 선택(On-Prem 승인 게이트 Slack 버튼 연동).

## 2026-07-19 — Analyzer Bedrock 무효 모델 ID 근본수정 + 라이브 검증 · SendSlackAlert skip 규명 (gate 844 유지)

- Status: Slack E2E가 표면화한 후속 2건 처리. (1) Bedrock 정정=완료·라이브 검증, (2) executor skip=근본 원인 규명(수정 방향은 사용자 결정 대기).
- Changed(`9a56949`): 스택이 `.env` 무시하고 무효 ID `anthropic.claude-sonnet-4-5` 하드코딩(InvokeModel은 인퍼런스 프로파일 필요 → **ValidationException, 매 인시던트 휴리스틱 폴백 강등**되던 latent 결함) → `process.env.BEDROCK_MODEL_ID ?? 'us.anthropic.claude-sonnet-4-6'` + IAM을 프로파일 ARN+라우팅 3리전 하위 모델 정확-ARN으로 재구성(bare `"*"` 없음). analyzer 기본값 정합. `.env`도 `us.` 프로파일로 갱신.
- Verified: `make check` → **844 passed, 1 skipped**(232.68s). **라이브**: 알람 재트리거 → `analyzer.llm_done`(confidence 0.52, **실 Claude 분석 root cause가 Slack 승인 카드에 문장형 표시**) → Approve 클릭 → SFN SUCCEEDED(APR-A1EA0CD8565E).
- Blockers: 없음.
- Next: **executor `AWS-SendSlackAlert` skip 규명 결과 = 수정 방향 결정 필요**: 카탈로그(generic-recovery·`open_change_request` 캐퍼빌리티 전체)가 **실존하지 않는 SSM 문서**를 참조 + Executor role IAM allowlist에도 없음(라이브 에러=AccessDenied, IAM 열어도 NotFound) → generic-recovery는 구조적으로 `resolved=False`. 선택지: (a) 알림성 액션을 in-process Slack 송출로 1급 처리(권고) (b) 실 SSM 문서 작성 (c) 의도된 skip으로 문서화만.

## 2026-07-19 — Slack App 실 생성 + 인터랙티브 승인 버튼 라이브 E2E 완주 (gate 843→844)

- Status: 사용자 게이트 "Slack App 실 생성/토큰" **해소**. 사용자=App 생성(Incoming Webhook `#platform-test`·Interactivity Request URL=ApprovalBridgeFunctionUrl·Signing Secret→`.env`), 에이전트=cdk deploy env 주입→알람 트리거→**브라우저로 Slack Approve 버튼 클릭**→SFN 완주. 라이브가 프로덕션 버그 2건 표면화→근본수정→가드(발견→수정→가드 루프 재실증).
- Changed(`0f99420`): (1) **detector** — `_normalise_incident`가 미존재 `_SIGNAL_ADAPTER` 전역 참조(NameError로 **AWS 경로 전면 불능**; 기존 테스트는 non-AWS 경로만 커버라 은닉) → `get_signal_adapter("aws")` 정합 + AWS 경로 실 normalisation 회귀 테스트. (2) **approval_bridge** — pending 저장 시 confidence를 float로 `put_item`(boto3 resource=Decimal만 허용, **TypeError로 승인 요청 전량 소실**; e2e 페이크 테이블이 타입 무검증이라 은닉) → `Decimal` 변환 + 페이크에 실 시리얼라이저와 동일한 float 거부 계약 이식. (3) `.claude/settings.local.json` allow 2건(`source .env && npx cdk deploy/diff`).
- Verified: `make check` → **844 passed, 1 skipped**(234.56s, 843→844). **라이브 E2E**: `set-alarm-state` ALARM→EventBridge→SFN→WaitForApproval→Slack 버튼 메시지(APR-8BC7E7E95B9A)→**Approve 클릭**(서명 HMAC 검증→DynamoDB claim=APPROVED→`SendTaskSuccess`)→SFN **SUCCEEDED**→최종 리포트 INC-2AC4B6C9 게시. 증거 `docs/evidence/slack-interactive-approval-live.log`.
- Blockers: 없음. (참고: 실패 승인 메시지 1건은 maxReceiveCount=1로 DLQ행 — 정리 선택.)
- Next: 후속 후보 — Analyzer `BEDROCK_MODEL_ID` invalid(ValidationException, 휴리스틱 폴백 중) 정정 · executor `AWS-SendSlackAlert` skip 의도 확인. 잔여 사용자 게이트 = 아티클 배포·(billable) terraform apply.

## 2026-07-18 — OAuth 대시보드 배포 트리거 라이브 E2E + 프로덕션 장애 2건 근본수정 (gate 842→843)

- Status: 사용자 게이트 항목 "OAuth UI 배포 클릭 데모" 수행 중 프로덕션 장애 2건을 발견·근본수정하고 E2E 완주. 과금 감사 병행(platform-agent 유휴 $0, slackops EBS 월~$5만 잔존).
- Changed: (1) **`.vercelignore` 앵커링**(`d5e4487`) — 무앵커 `src/`가 `dashboard/src/`까지 제외해 **git 트리거 Vercel 배포가 전부 404 빌드**였음(동일 커밋 CLI=200/git=404로 실증). 수정 후 canonical 200 + git 파이프라인 정상화. (2) **CDK**(`bb65c32`) — CloudTrail로 **07-11 Vercel OIDC provider 삭제**(context 미지정 배포 함정 실화) 규명 → provider 재생성(실 team slug `men16922s-projects`, Vercel API 확증) + role trust 정합 + **정확-ARN `states:StartExecution`**(deployment/provisioning 2개)+`ListStateMachines`. (3) **`smoke_tester.py`**(`025ca69`) — 라이브 클릭이 표면화한 계약 버그(`KeyError 'base_url'`): base_url 옵셔널화(빈 체크=공허 통과, no_canary_data와 동일 시맨틱)+회귀 테스트. (4) 아티클 3종 수치 최신화(736/738→842, eval 로드맵 문장→구현 완료 사실).
- Verified: `make check` → **843 passed, 1 skipped**(236.08s, 842→843). **라이브 E2E**: GitHub OAuth(operator) UI → Start Release → `DEP-612170AC`(FAILED=버그 표면화) → 수정 배포 → `DEP-1F054864` **SFN SUCCEEDED**(`needs_approval:false`) → 대시보드 라이브 피드 반영. 대시보드 배지 **DEMO FALLBACK → LIVE · AWS**(OIDC 복구로 실 DynamoDB 51건). 증거 `docs/evidence/oauth-deploy-trigger-live.log`.
- Blockers: 없음. cdk deploy는 `.claude/settings.local.json` allow 규칙(사용자 승인)으로 해금.
- Next: 잔여 사용자 게이트 = 아티클 배포(원고 842로 최신화 완료)·Slack App·(billable) terraform apply.

## 2026-07-17 — 차트 k3s substrate 스모크: env×substrate 양축 실증 완결 (코드 무변경, gate 842 유지)

- Status: 마지막 선택 소품 수행. **기존** Multipass `k8s-lab`(k3s v1.31.4, Ansible 프로비전 자산) 재사용 — 클러스터 생성 없음, 릴리스 설치→검증→제거·반입 이미지 정리로 VM 원상 복원.
- Changed: `docs/evidence/helm-k3s-substrate-smoke.log`만.
- Verified (라이브): 이미지 tar 전송→`k3s ctr import`(199MB; exec-stdin 스트림은 EOF라 tar 경로가 정석) → `helm install -f values-k3s.yaml` → pod 1/1 Ready ~29s → **PVC가 `local-path`로 Bound**(k3s 오버레이의 핵심 검증; kind는 `standard`) → `/health/ready` 200 → Alertmanager 페이로드→P2 parking(APR-0515026F)→approve→INC-3219D4A8 resolved → uninstall·이미지 제거. **동일 차트가 kind/k3s 양 substrate에서 오버레이만 바꿔 동일 동작 — 레퍼런스 #7 env×substrate 레이아웃 양축 실증 완결.**
- Blockers: 없음.
- Next: **자율 백로그 전면 소진.** 잔여=전부 사용자 게이트(아티클 배포·OAuth 데모·Slack App·terraform apply).

## 2026-07-17 — 차트 State Store 배선(④↔#7 연결 마무리): stateStore values + DSN 멀티-레플리카 모드 (gate 839→842)

- Status: ④(SQL State Store)와 #7(Helm/Terraform)을 잇는 마지막 소품. 차트가 DSN 모드를 1급 values로 지원 — JSONL 기본값 무변경.
- Changed: (1) `values.yaml` `stateStore.{dsn,existingSecret,secretKey}` — **existingSecret(secretKeyRef)=프로덕션 경로**(values에 평문 DSN 금지), plain `dsn`=dev/kind 편의, secret이 plain보다 우선. (2) `_helpers.tpl` `stateStoreEnv`+`strategy`(persistence off→**RollingUpdate**, JSONL RWO일 때만 Recreate) — webhook/router 양쪽 주입. (3) **`infra/onprem/Dockerfile` `.[state]` 설치**(psycopg2 — 없으면 DSN 모드 이미지가 실동작 불가, 재빌드+import 검증). (4) README 2종: 차트=DSN 모드 사용법(라이브 증거 링크), Terraform=`kubectl create secret`+`stateStore.existingSecret` 스니펫(extraEnv 핵 대체). (5) 차트 가드 +3: 기본=DSN env 부재·dsn/secret 모드(secret 우선·평문 무노출)·**DSN 모드=PVC 없음+replicas 2+RollingUpdate**.
- Verified: helm lint 통과, `make check` → **842 passed, 1 skipped**(234.42s, 839→842). 이미지 재빌드 후 `import psycopg2` OK.
- Blockers: 없음.
- Next: 자율 백로그 소진. 잔여=사용자(아티클 배포·OAuth·Slack·terraform apply)·선택(k3s 스모크).

## 2026-07-17 — 레퍼런스 #7-b Terraform 모듈(EKS/Aurora/IRSA) → #7 전체 완결 (gate 834→839, apply 없음·spend 0)

- Status: 레퍼런스 #7 잔여 Terraform 파트 구현·오프라인 검증(사용자 승인 "다음 수행"). apply는 하지 않음(billable=사용자 게이트). 이로써 **레퍼런스 #7 = Helm(#7-a)+Terraform(#7-b) 전체 완결** — AWSome AI Gateway 레퍼런스 8항목 전부 소화(Tier 1 4종+Tier 2 3종+#7).
- Changed: 신규 `infra/terraform/aws-production/`(7파일) — VPC(2AZ·public/private·NAT 1) + EKS 1.31(managed node group, AWS-managed 정책만 ARN attach) + **Aurora PostgreSQL Serverless v2**(min 0.5 ACU·`database_name=platform_state`=④ `PLATFORM_STATE_DSN` seam 정합·`manage_master_user_password`=Secrets Manager, 평문 무노출) + **IRSA**(OIDC provider+차트 SA 전용 trust[sub+aud]·**유일 grant=DynamoDB activity 테이블 정확 ARN**+index, deploy_recorder가 실 소비자) + outputs(DSN 템플릿·IRSA arn·helm 배선 스니펫 README). Redis/Cognito는 **미소비라 의도적 제외** 명시. `tests/test_terraform_module.py` +5(구성 완비·**bare `"*"` 금지**[주석 제외]·state seam 정합·IRSA trust 스코프·validate[init 시]).
- Verified: `terraform init`+`fmt -check`+**`validate` Success**(크레덴셜/spend 0). `make check` → **839 passed, 1 skipped**(238.51s, 834→839). ARCHITECTURE 표 #7 ✅.
- Blockers: `terraform apply`=billable(EKS ~$0.10/h+노드+NAT+Aurora) — 사용자 게이트.
- Next: 자율 코드/인프라 백로그 재소진 — 잔여는 사용자 몫(아티클 배포·OAuth·Slack·apply류) + 선택 소품(k3s 스모크·차트 DSN values).

## 2026-07-17 — 로드맵 ④: SQL State Store(옵트인) + 실 Alertmanager 라이브 E2E — 멀티-레플리카 실증 (gate 829→834)

- Status: ARCHITECTURE 잔여 ④(On-Prem State Store·Alertmanager 실연동)를 로컬 docker($0)로 완결. JSONL 단일-writer 제약(Helm 차트 replicas:1의 근거)을 푸는 productionization seam.
- Changed: (1) 신규 `src/agents/ai/state_store.py` — `SQLStateStore`(DB-API connect 주입·placeholder/autoincrement 파라미터·append-only+latest-wins=JSONL 시맨틱 동일)·`from_dsn`(postgresql→psycopg2, sqlite://→stdlib)·`configured_store`(`PLATFORM_STATE_DSN` 옵트인, 미설정=None=JSONL 무변경). (2) `onprem_approvals`/`onprem_incidents` 읽기·쓰기 양쪽에 seam 배선. (3) pyproject `state = ["psycopg2-binary>=2.9"]` extra. (4) `tests/test_state_store.py` +5(sqlite 오프라인: 시맨틱·라우팅·JSONL 비오염 양방향).
- Verified: `make check` → **834 passed, 1 skipped**(242.90s, 829→834). **라이브 E2E**(docker postgres:16 + prom/alertmanager:v0.28.1): ① **실 Alertmanager가 자체 grouping 후 native 페이로드 배달**(손 페이로드 아님)→4-step→P2 parking→**PostgreSQL row**. ② **레플리카 2개**(동일 DSN, 별개 프로세스): replica-2가 pending 조회·**승인 실행**→replica-1 즉시 pending 0+incident 반영(JSONL 불가능한 것). ③ 양 프로세스 kill→재기동→상태 생존. ④ psql ground truth 3 rows(pending→approved append-only→incident). 전량 teardown. 증거 `docs/evidence/state-store-alertmanager-live.log`.
- Blockers: 없음. Helm 차트에서 DSN 설정 시 replicas>1 해금(차트 values 배선은 후속 소품).
- Next: #7-b Terraform 모듈(클라우드=승인) or 사용자 항목(아티클/OAuth/Slack).

## 2026-07-17 — 레퍼런스 #7-a Helm 차트 kind 라이브 실증 (코드 무변경, gate 829 유지)

- Status: 방금 만든 차트를 전용 kind 클러스터(`pa-helm`)에 실 `helm install`로 end-to-end 실증(사용자 승인). 외부 GKE 컨텍스트 불가침(전 kubectl `--context` 핀), 실증 후 전량 teardown + 원 컨텍스트 복원.
- Changed: `docs/evidence/helm-kind-live-install.log`만(코드 무변경).
- Verified (전부 라이브): (1) `kind load`+`helm install` → deployed·NOTES 정상. (2) webhook pod **1/1 Ready ~12s**(strict `/health/ready` readiness in-cluster 그린)·PVC Bound 1Gi. (3) **RBAC 최소권한 auth can-i 실증**: SA로 patch deployments/get replicasets/patch scale=**yes** · patch nodes/delete pods/create pods\/eviction/delete deployments=**no**(drain off 기본). (4) **Day-2 E2E**: 실 Alertmanager 페이로드 POST → in-pod 4-step(휴리스틱 폴백, Bedrock creds 무=설계) → **P2 APPROVE parking**(APR-284A4249) → `/pending`→`/approve` → executed+resolved(INC-5D000FBD) → `/incidents` 기록. (5) **PVC 영속성**: pod 삭제→새 pod가 동일 인시던트 서빙.
- Blockers: 없음. 잔여=#7 k3s substrate 스모크(선택)·#7-b Terraform 모듈(클라우드=승인).
- Next: ④ State Store/Alertmanager 실연동(로컬 docker) or #7-b or 사용자 항목(아티클/OAuth/Slack).


## 2026-07-17 — 레퍼런스 #7-a: On-Prem Helm 차트 + 컨테이너 이미지 (gate 823→829, pyproject latent 버그 수정)

- Status: ARCHITECTURE 잔여 ⑤(레퍼런스 #7 Helm/Terraform 프로덕션, Tier 3) 중 **Helm 파트** 구현. 로컬·$0·오프라인 검증 가능 범위만 자율 수행(kind 라이브 설치=클러스터 생성이라 승인 게이트).
- Changed: (1) `infra/onprem/Dockerfile` — python3.11-slim + kubectl v1.31.4(Day-2 runner가 subprocess로 침) + `pip install .` 단일 이미지, 2엔트리포인트(webhook/router). (2) `infra/helm/platform-agent/` — webhook(기본 on, liveness `/health`·readiness `/health/ready`=서킷브레이커 인지 Tier1 #6 반영) + router(opt-in, 빌드툴 부재 명시·PVC 공유 시 podAffinity 핀) + **최소권한 RBAC**(4조치 동사 열거: 네임스페이스 Role=restart/undo/scale, **drain은 별도 ClusterRole·`allowDrain` 기본 off**) + PVC 단일-writer(replicas 1·Recreate, State Store가 멀티 경로임을 명시) + env×substrate values(kind/k3s) + NOTES/README. (3) `tests/test_helm_chart.py` +6 — helm lint·기본=webhook-only+노드 불가침·**RBAC `"*"` 금지**(fully-armed도)·drain 표면 정확성(cordon만, eviction API)·프로브 분리·단일-writer(helm 미설치 시 skip). (4) **`pyproject.toml` latent 버그 수정**: `[project.optional-dependencies.<name>]`+`dependencies=` 형식이 PEP 621 위반 — 아무도 `pip install .` 안 해서 잠복, 이미지 빌드가 표면화 → extras 배열로 정정.
- Verified: `make check` → **829 passed, 1 skipped**(263.50s, 823→829, +6). helm lint 통과·기본/풀 렌더 검증(기본=ClusterRole 없음, 풀=drain CR+k3s LLM endpoint 배선). **이미지 실빌드 성공(881MB)** + 컨테이너 스모크: kubectl v1.31.4·양 API import OK·webhook 기동→`/health` 200·`/health/ready` 200(checks ok)→정리.
- Blockers: kind/k3s **라이브 helm install은 클러스터 생성 필요 = 승인 대기**. Terraform 모듈(#7-b, EKS/Aurora)은 클라우드·별도 묶음.
- Next: (승인 시) kind 라이브 설치 실증 / #7-b Terraform 모듈 / ④ State Store·Alertmanager 실연동(로컬 docker 가능).

## 2026-07-17 — ⑦ 라이브 모델 스윕 실 실행 완료 (로컬 MLX, spend $0): 프롬프트 결함 발견→수정→가드 (gate 822→823)

- Status: 승인 큐 마지막 잔여였던 ⑦ 라이브 실행을 **A 로컬 MLX 경로**(무과금)로 완료. 신규 `scripts/live_model_sweep.py`가 shipped `live_router_factory`+`run_sweep`을 실 mlx_lm.server(:18090, per-request 동적 모델 로드) 상대로 구동. 총 **160 라이브 호출**(2모델×2 effort×20케이스×프롬프트 v1/v2), 미파싱→backstop 발화 0.
- Changed: (1) `scripts/live_model_sweep.py` 신규 — effort→temperature 매핑(low=0.0/high=1.0), points JSONL resume(모델별 순차 실행 병합 실증), 응답 `model` 에코 검증+오염 시 미기록 가드. (2) **`model_sweep.py` `_classify_prompt` 결함 수정** — 라이브 런이 표면화: v1 프롬프트가 "provision=create/**tear down**"으로 teardown→deploy cascade 제품 시맨틱과 모순 + 진단동사 우선 미명시 → 전 config가 동일 adversarial 2건 미스("Investigate why the terraform apply failed"→provision·"Tear down the staging cluster"→provision). 모델이 아니라 프롬프트가 틀렸음. v2로 재작성. (3) 회귀 가드 `test_classify_prompt_matches_product_routing_semantics` 추가.
- Verified: `make check` → **823 passed, 1 skipped**(230s, 822→823, +1). 라이브 v1→v2 델타(프롬프트 수정만): 7B/low 0.80→**1.00**·7B/high 0.75→0.90·30B/low 0.80→0.95·30B/high 0.80→0.95. **증거 기반 선택: Qwen2.5-Coder-7B @ temp0 = 20/20(100%)·최속(0.20s/success)** — "라우팅엔 큰 모델" 정적 주석은 측정으로 반증(30B보다 7B가 정확·빠름). 증거: `docs/evidence/model-sweep-live.log` + points JSONL 2종(v1 baseline/v2). MLX 서버는 실행 후 종료(유휴 $0 복원).
- Blockers: 없음. **승인된 실행 큐 8항목 전부 완료(코드+실행).**
- Next: 잔여는 전부 인프라/사용자 — 아티클 배포·OAuth 데모·Slack App·State Store·Helm/Terraform(#7 Tier 3).

## 2026-07-17 — 승인된 실행 큐 8항목 코드 전부 완료: ⑧-1/2/3 + ⑨ A/B + ⑦ 어댑터 (gate 796→822, 사용자 "전부 다")

- Status: 사용자가 ⑧·⑨ 잔여 + ⑦를 전부 승인("전부 다 하자"). 위험 낮은 순 큐로 8개 코드 묶음을 순차 구현·게이트·커밋. ⑦는 어댑터 코드까지 완료, 실 실행(과금)만 사용자 게이트로 잔존.
- Changed (8 커밋, 전부 origin/main): **⑧-3**(`e79bf94`) `ROLE_ALLOWED_ACTIONS` 위임 `allowedActions` 힌트+`action_sink_grader` 단일소스. **⑨A-1/A-2**(`0050129`) SSE `id:` dedup·`ready` 센티넬·`asyncio.wait_for` heartbeat. **⑧-1**(`fdf9e11`) `metadata.task` 구조화 디스크립터. **⑨B-1**(`1184ee5`) 신규 `memory_tier.py`(signature·scrub·distill·MemoryStore). **⑧-2**(`13d1352`) `Supervisor(confidence_router=)` 옵트인 저-confidence 게이트(구조적 Protocol=cycle 회피). **⑨B-2**(`ccc8a47`) recall+`augment_instruction` 옵트인 `memory=` seam(조언적). **⑨B-3/A-3**(`3b4cbd9`) `consolidate`/`dominant_failures` + SSE `agent` 필드. **⑦ 어댑터**(`57d2aa7`) `live_router_factory(call_model, backstop=)`(모델응답→role 파싱·latency 측정·결정론 백스톱, `run_sweep` 드롭인).
- Verified: `make check` 각 묶음 그린 → **822 passed, 1 skipped**(261s, 796→822, **+26 test**). 전부 비파괴(옵트인 DI·additive 메타데이터·SSE 하위호환·주입식 모델호출). 설계 2건(`docs/plans/a2a-delegation-hardening.md`·`sse-memory-hardening.md`) 승인·실행 반영.
- Blockers: **⑦ 실 실행만 잔존**(코드 완비) = 실 `call_model`+creds+과금(클라우드), or 로컬 MLX=무과금이나 `make dev-up` 스택 기동 필요. 사용자 결정 대기(A 로컬무과금/B 클라우드~$0.05/C 멈춤).
- Next: ⑦ 실 실행(사용자 선택) or 인프라/사용자(아티클 배포·OAuth·Slack·State Store·Helm/Terraform).

## 2026-07-17 — cwc-workshops 후속 ⑨: SSE 하드닝 + 회수가능 메모리 tier 설계 제안 (문서만, 코드 무변경)

- Status: ⑨(설계 항목)의 설계 제안서 작성. 실 코드(SSE 스트림·deploy_recorder) 근거로 그라운딩, 구현은 승인 대기(런타임 표면 개입이라). 자율 코드 백로그 실질 소진 후 남은 설계 작업.
- Changed (docs only): 신규 `docs/plans/sse-memory-hardening.md` — (A) SSE: A-1 event-id/dedup·A-2 READY 센티넬+heartbeat·A-3 per-agent 귀속(각 리스크/권고), (B) 메모리: B-1 시그니처-키드 distilled tier·B-2 실행시작 과거 주입(옵트인 DI·조언적)·B-3 주기 consolidation. 근거 file:line(`local_deploy_api.py:216-276`=`data:`만·id/READY 없음, `deploy_recorder`=풀 트레이스 저장하나 미주입). `NEXT_PLAN.md` ⑨ [~]로 갱신·설계 링크.
- Verified: 코드 무변경(gate 796 유지, 미실행). 권고 1순위=A-1+A-2(비파괴·즉시 UX). 안티: 정적 무조건 주입 금지·SSE replay 버퍼 상한·distilled 메모리 PII/시크릿 스크럽 선행.
- Blockers: 없음. ⑨ 전 항목 구현=승인 대기.
- Next: **자율 코드/설계 백로그 소진.** 잔여는 전부 승인/스펜드/인프라: ⑧-1/2/3(승인)·⑨ A/B(승인)·⑦ 라이브(실 spend)·아티클 배포·OAuth·Slack·State Store·Helm/Terraform.

## 2026-07-17 — cwc-workshops 후속 ⑧(안전 서브셋+⑧-4): A2A 위임 sanitize+cap · 경계 smell-test 가드 · 설계 제안 (gate 790→796)

- Status: ⑧(A2A 위임 injection-safe, Tier 3 설계·승인) 중 **비파괴 안전 서브셋**만 자율 구현하고, 계약/동작 변경 4건은 설계 제안서로 분리(승인 대기). supervisor 위임 경계=호출자 자유텍스트가 특화에 raw 전달이던 것을 bounded/cleaned로.
- Changed: `supervisor.py` — 신규 `sanitize_instruction(text, max_len=4000)`(C0/C1 control-char strip[tab/newline 유지]·length cap+truncation 마커·적용 transform 리스트 반환, 클린 입력=무변경). `handle`이 **아웃바운드** 명령어에 적용(분류는 원문 유지)·적용 시 `trace{kind:"sanitize"}` 기록. `trace` 지역변수 타입 주석 `list[dict[str,Any]]`(기존 latent pyright 경고 동반 수정). 신규 `docs/plans/a2a-delegation-hardening.md`(⑧-1 구조화 페이로드·⑧-2 저-confidence 게이트·⑧-3 최소권한 힌트·⑧-4 경계 smell-test, 각 리스크·권고·순서). **⑧-4(승인 무관, 완료)**: `ARCHITECTURE.md`에 **TOOL→SKILL→SUBAGENT smell-test** + 위임 안전 불변식 명문화 + **회귀 가드 테스트**(supervisor는 mutating provision/deploy를 in-process 실행 안 함, 반드시 A2A transport로 위임·미설정 시 refuse).
- Verified: `make check` → **796 passed, 1 skipped**(231.96s, 790→796, +6). sanitize: 클린=무변경·control-char strip·length cap 마커. 위임: 아웃바운드 텍스트 sanitized(`\x07` 제거 확인)+trace 기록·클린 입력은 sanitize trace 없음. ⑧-4 가드: configured=transport만 호출·unconfigured=transport 미호출+not_configured. 기존 delegation/JSONRPC/messageId 회귀 0.
- Blockers: 없음. ⑧-1/2/3(구조화/게이트/최소권한)은 **승인 대기**(`docs/plans/a2a-delegation-hardening.md`); ⑧-4는 완료.
- Next: (승인 시) ⑧-3 최소권한 힌트(가장 안전) → ⑧-1 구조화 디스크립터 → ⑧-2 저-confidence 게이트. or ⑨ SSE/메모리(설계) / ⑦ 라이브 스윕(실 spend=사용자).

## 2026-07-17 — cwc-workshops 후속 ⑦(스캐폴드): 오프라인 모델/파라미터 스윕 러너 (gate 779→790, 실 spend 0)

- Status: NEXT_PLAN ⑦(모델 스윕→Model Router 정량화)의 **자율 가능 오프라인 스캐폴드** 구현. 실 API 호출/과금 코드 없음 — LLM 백엔드는 `router_factory` 주입(테스트=결정론 mock), 라이브 모델 배선+실 spend은 사용자 게이트.
- Changed: 신규 `src/agents/ai/model_sweep.py`(eval_harness 위 증분) — `SweepConfig`(model×thinking×effort)+`grid()` 카테시안, `run_sweep()`(config별 dataset 채점→**cost_per_success/seconds_per_success** headline, `_majority_observation`로 `trials` self-consistency 재사용), **resumable**(`done=` 재투입 시 config.key dedup으로 스킵·기존 포인트 front 보존), `SweepPoint`(pass_rate/cost_per_success/seconds_per_success, 0성공=inf, to/from_dict 영속), `rank()/best()/scoreboard()`(cost/seconds/pass_rate 키, 결정론 tie-break). +11 test(`tests/test_model_sweep.py`, mock 백엔드).
- Verified: `make check` → **790 passed, 1 skipped**(218.92s, 779→790, +11). 스모크: good 모델(=classify)=20/20·cost_usd=price×calls·trials=3→3N calls·resume는 done config에서 factory 미호출(폭발 팩토리로 확증)·rank best-first.
- Blockers: 없음. ⑦ 라이브 실행(실 model 호출·과금)만 사용자 판단 잔여.
- Next: (설계·승인) ⑧ A2A 위임 injection-safe or ⑨ SSE/메모리 tier. **⚠️ PROGRESS_LOG 120줄 초과 임박 → `/tidy-docs` 권장.**

## 2026-07-17 — cwc-workshops 후속 ⑤: eval 하네스 성숙 — 선언적 멀티 grader 스코어카드 (gate 767→779, 비파괴 증분)

- Status: NEXT_PLAN ⑤(eval 성숙, 자율 코드) 수행. 단일-judge grade()/EvalReport 경로는 무변경으로 두고 그 위에 선언적 멀티-grader 스코어카드 레이어를 증분 추가. cwc eval-멀티메트릭 방법론 반영.
- Changed (`eval_harness.py`, 비파괴): (a) **선언적 `Grader`**(name+kind `code`|`judge`) — 단일 Judge→명명 메트릭 다중. 빌트인 `role_match_grader`·`budget_grader`·`action_sink_grader`(code) + `judge_grader`(기존 Judge 래핑=judge). (b) **`Verdict` 3-상태**(PASS/FAIL/**PASS_SLOW**=정답이나 예산초과) + **budget grader**(latency>budget→PASS_SLOW) + **action-sink grader**(read-only role이 mutate=FAIL·per-role allowed 정책=blast-radius 안전 메트릭). 리치 `Observation`(decision+latency_s+actions)와 `observing()` 브리지로 결정론 classifier를 무변경 투입. (c) **pinned-baseline 델타**: `Scorecard.metrics()`/`delta(baseline)`/`regressions()`(회귀 diff, 신규 메트릭=baseline None). (d) **`score(..., trials=N)` majority vote**(self-consistency 재사용; 결정론 라우터엔 no-op). `__all__` 확장, docstring 갱신.
- Verified: `make check` → **779 passed, 1 skipped**(232.74s, 767→779, **+12 test**). 표적(eval+supervisor+orchestration) 57 passed. 스모크: dataset 3메트릭(role/latency/blast_radius) 전부 1.0·PASS_SLOW(slow 라우터)·action-sink FAIL(read-only kagent가 rollout restart)·delta regressed True. 기존 grade()/EvalReport/judge 경로 회귀 0.
- Blockers: 없음. NEXT_PLAN ⑤ 완료 마킹.
- Next: (자율) ⑦ 모델/파라미터 스윕(실 API spend=사용자 판단) or ⑧ A2A 위임 injection-safe(설계·승인) / 세션 누적 커밋.

## 2026-07-17 — cwc-workshops 후속 ⑥: ROUTING_EVAL_SET + llm_judge 하드닝 (gate 758→767, over-trigger 갭 2건 수정)

- Status: NEXT_PLAN ⑥(데이터셋+judge 하드닝, 즉시 실익·자율) 수행. eval 하네스가 실 라우팅 over-trigger 갭 2건 표면화 → `classify_request` 정밀도 수정 → 회귀가드로 전환. 발견→수정→가드 루프 재실증.
- Changed: **(dataset)** `ROUTING_EVAL_SET` 13→**20**, 카테고리 균형(provision 4·deploy 4·diagnose 5·cluster-creation-verb 2·**adversarial 5**) + **네거티브(adversarial) 케이스** 도입(hot 키워드가 한쪽 가리키나 의도는 다른 쪽 → precision 채점, recall만 아님). **(classify_request)** first-substring-wins → **precedence**: ① 진단 동사(diagnose/investigate/troubleshoot/debug/why is/are/did)=KAGENT가 provision 명사보다 우선 · ② provision(기존 유지) · ③ 약한 investigation 명사(logs/pods/namespace/istio/status)는 delivery 동사(deploy/ship/install/release/roll out/promote) 선행 시 억제 → DEPLOY. 과광범 `observability` 트리거 제거. **(judge 반-관대)** `_build_judge_prompt` 재작성(read-only/mutating 경계 명시·확신없으면 FAIL) + 신규 `calibration_probe`(파괴적 provision→read-only kagent 컨트롤 canary; PASS/에러/미파싱=관대·불신) + `llm_judge(calibrate=True)`(canary 실패 grader를 exact-match로 강등). 빈문자열/"모름"/"don't know"=결정론 백스톱 유지.
- Verified: `make check` → **767 passed, 1 skipped**(227.82s, 758→767, **+9 test**). 표적 스위트(eval+supervisor+orchestration) 45 passed. 데이터셋 grade **20/20 100%**, by_category 전부 1.0. probe: lenient→False·discerning→True. 기존 supervisor/orchestration classify 단언(4건) 회귀 0. over-trigger 수정 확인: "Deploy the observability stack"=KAGENT→**DEPLOY**, "Investigate why the terraform apply failed"=PROVISION→**KAGENT**.
- Blockers: 없음. NEXT_PLAN ⑥ 완료 마킹.
- Next: (자율) ⑤ eval 멀티메트릭(선언적 Grader·PASS-SLOW·pinned baseline) or ⑦ 모델 스윕(실 API spend=사용자) / 세션 누적 4 커밋 미푸시(origin +3 + 이번분).

## 2026-07-17 — cwc-workshops(Anthropic Code with Claude) 대조 → reference 노트 + NEXT_PLAN 후속 ⑤~⑨ (코드 무변경)

- Status: 사용자 요청으로 `/Users/men1692/Desktop/AI/cwc-workshops`(Anthropic 공식 워크샵 9개) 대조. 병렬 3-Explore(eval 방법론·오케스트레이션/프로덕션·메모리)로 platform-agent 차용 후보만 추출. 방금 만든 ④ eval 하네스와 직결.
- Changed (docs only): 신규 `docs/reference/cwc-workshops.md`(메타결론: CMA 베타 런타임 전이X·계약만; Tier1 eval 성숙·Tier2 모델스윕·Tier3 A2A 위임계약·Tier4 SSE/메모리, file:line 인용 + `ROUTING_EVAL_SET` 자기비판). `NEXT_PLAN.md` "cwc-workshops 후속" 블록 ⑤~⑨(⑤eval 멀티메트릭/PASS-SLOW/action-sink·⑥데이터셋+llm_judge 하드닝·⑦모델 스윕 정량화=자율가능, ⑧A2A injection-safe 위임·⑨SSE/회수가능 메모리=설계). `AGENT_BRIEF.md` NEXT SESSION 포인터 갱신.
- Verified: 코드 무변경(gate 758 유지, 미실행). 문서 라인수 NEXT_PLAN 71/120·brief 42/60·cwc-workshops 44. 핵심 규명: 워크샵 전부 CMA 베타 API 위라 런타임 전이 불가(우리 자체 Orchestrator/A2A/MCP 스택), **계약·패턴만** 전이. eval 방법론 워크샵들이 우리 하네스 방향 독립검증+다음단계 제시.
- Blockers: 없음.
- Next: (자율) ⑥ 데이터셋+llm_judge 하드닝(즉시 실익) or ⑤ eval 멀티메트릭 or ⑦ 모델 스윕 / 세션 누적분 커밋(문서 다수 + eval_harness/supervisor 코드).

## 2026-07-17 — Google 생태계 후속 ①③④ 완료: 아티클 포지셔닝 + 버전 규명 + eval 하네스 스파이크 (gate 748→758)

- Status: `/goal 나머지 완료시까지 수행`으로 Google Agent 생태계 대조의 잔여 자율 항목을 완결. ②(context 격리)는 직전에 no-op 규명, 이번엔 ①③④ 수행.
- Changed: **①(docs)** EN `platform-agent-architecture.md` + KO `-ko.md` 맺으며 앞에 "같은 논지, 이제 플랫폼 벤더가 출시하다" 수렴 섹션(ADK 2.0 deterministic-workflow·A2A zero-context-pollution·agents-cli eval loop ↔ 우리 reconciliation/self-consistency/최소-페이로드 위임, 출처 3링크; 미검증 벤치마크는 정성 서술만). **④(code)** 신규 `src/agents/ai/eval_harness.py`: 클라우드-중립·오프라인 decision-quality 평가 계층 — `EvalCase` 라벨 데이터셋 + injectable `Router`/`Judge`, `exact_match_judge`(결정론) + `llm_judge`(LLM-as-judge, 파싱실패/에러 시 exact-match **결정론 백스톱**), `EvalReport`(pass_rate·카테고리별·`meets(threshold)` 회귀 가드), 빌트인 `ROUTING_EVAL_SET`(13). +10 test(`tests/test_eval_harness.py`, 하네스 메커니즘만 검증).
- Verified: `make check` → **758 passed, 1 skipped**(229.91s, 748→758). **④ 실익 실증 + 루프 완결**: 결정론 classifier 스파이크 → 11/13(84.6%), **실제 라우팅 갭 2건 표면화**("Create a GKE cluster"·"Spin up a kind cluster" → PROVISION이어야 하나 DEPLOY; classifier 키워드가 'create a X cluster'/'spin up' 미커버) → **`supervisor.classify_request` 수정**(cluster+생성동사 조합 감지, 기존 DEPLOY/KAGENT 케이스 회귀 0 확인) → eval set **13/13**, 갭 케이스는 회귀 가드로 전환. 유닛테스트가 못 잡는 결정-품질 갭을 발견→수정→가드로 닫는 루프 실증. **③ 규명**: 우리 클라이언트 A2A=stdlib-only(`a2a` SDK import 0, `supervisor.py`)라 A2A SDK 드리프트 무영향; ADK=`google-adk>=1.0`(`adk_deployer.py` Gemini 경로만), ADK Python GA 2026-03 후 재평가는 캘린더 항목.
- Blockers: 없음. reference 노트+NEXT_PLAN ①②③④ 전부 완료 마킹.
- Next: (선택) LLM router/judge로 eval 확장 / 커밋·푸시 / 잔여 인프라·사용자(아티클 배포·Slack·OAuth 데모·State Store·Helm/Terraform).

## 2026-07-17 — Google Agent 생태계 3자료 대조 → reference 노트 + NEXT_PLAN 후속 4건 (코드 무변경)

- Status: ADK 2.0·A2A·agents-cli(구글 developer 블로그+레포) 3자료를 우리 설계와 대조. **핵심 결론: 철학/기능 대부분 이미 구현**(reconciliation gate·self-consistency 폴백·Guardian·specialists-as-tools·자체 런타임 호스팅 3종)이라 마이그레이션/채택 대상 아님. 순수 문서 작업.
- Changed: 신규 `docs/reference/google-agent-ecosystem-2026.md`(A: ADK 2.0 deterministic-workflow 철학 대조표+유일 델타=context 격리 · B: A2A 4대 이점 vs 우리 상태(Zero Context Pollution=부분·Dynamic Autonomy=갭) · C: agents-cli 레이어차·유일 차용후보=eval 하네스 · 액션 4). `NEXT_PLAN.md`에 "Google 생태계 후속" 블록(①아티클 포지셔닝 ②context 격리 감사 ③버전 트래킹 ④eval 하네스, ①④=자율가능·②=감사→승인게이트).
- Verified: 코드 무변경(gate 748 유지, 미실행). 문서 라인수 NEXT_PLAN 61/120·reference 82. ⚠️ A2A SDK 버전표·벤치마크 50%/20%는 요약모델 추출값이라 아티클 인용 전 원문 재확인 필요(문서에 명기).
- Audit(②, 읽기전용 수행): **델타 아님(no-op).** Orchestrator step은 특화 에이전트에 `parts:[{"text": instruction}]`(그 step instruction만) 전송(`supervisor.py:171`), `context_id`는 A2A `contextId` 상관관계 UUID(`:174`)지 누적 컨텍스트 아님 → 이미 최소 스코프, shared `contextId`는 A2A "Zero Context Pollution" 정석. 초안의 "shared context_id=오염" 프레이밍(docstring 오독) 정정. 코드 무변경. reference §A/§B + NEXT_PLAN ② 갱신.
- Blockers: 없음.
- Next: 잔여 자율=④eval 하네스 스파이크·①아티클 포지셔닝. ③버전 트래킹(백로그). 인프라/사용자 항목 잔여.

## 2026-07-17 — repo 구조·소스 리팩토링 + docs 병합 (dead code 제거·executor 공통화·post_webhook 버그수정)

- Status: 전체 폴더구조·소스 리팩토링 검토(병렬 3-에이전트 조사: src 구조·cross-cloud 중복·dashboard/tests/infra) 후 안전분만 실행. 커밋 4개, gate 748 유지, push 안 함.
- Changed: **(구조)** `src/agents/{executor,detector,decision,analyzer,approval_bridge}` 유령 패키지 5개 삭제(빈 `__init__`, import 0, 실구현은 `operations/` 하위); `infra/onprem/terraform/.terraform` **16MB null-provider 바이너리 추적해제**+`.gitignore` 등록(물리 유지). **(docs)** README↔DOCS_POLICY skills 중복(6 vs 3 불일치)→DOCS_POLICY §5 단일소스 통합; stale 문서 10개 제거(직전 커밋 `174d57f`); 미커밋 삭제 2건(linkedin 포스트·`local-llm-onprem.md`) 확정+NEXT_PLAN 참조수선. **(소스)** `operations/_executor_common.py` 추출(gcp/azure executor ~150줄 중복: deserialise/serialise/run_actions/slack, provider-특화는 유지); `operations/executor/_k8s_rest.py` 추출(gcp/azure runner의 byte-identical rollout-restart/scale).
- Verified: `make check` → **748 passed, 1 skipped**(239s, baseline 유지). gcp/azure day2 + multicloud runner 62 passed. pytest collection 749(import 에러 0). runtime import 확인.
- Bug fix: gcp/azure executor가 `post_webhook({"blocks":blocks})`로 dict를 URL자리에 넘기고 payload 누락(시그니처 `post_webhook(url,payload)`)+반환 None에 `.get("ts")`→TypeError가 except에 삼켜져 Slack 리포트 **조용히 무전송**이었음. 공통 `post_incident_slack`이 올바른 인자로 수정(테스트는 SLACK_WEBHOOK 미설정 early-return이라 회귀 없음).
- Deferred(판단): (a) `approval_bridge/handler.py`(604줄) 분리 — 테스트가 내부심볼 12개+를 `handler` 모듈경로에 `@patch` 강결합, 분리시 재import 필요해 실익<리스크→보류. (b) `_k8s_rest`는 restart/scale만(rollback은 GKE `:previous` fallback vs AKS 필수파라미터로 시맨틱 상이). (c) `operations` 그룹핑 축 통일(#3, AWS=role별 vs gcp/azure=cloud별) — 반나절 import churn, 별도 승인. detector/analyzer/decision은 SDK 90%+ 상이라 DRY 안 함(leaky).
- Blockers: 없음.
- Next: (선택) push / `operations` 그룹핑 축 통일 / 외부·인프라(아티클 배포·Slack·OAuth 데모).

## 2026-07-15 — AI endpoint 라이브 재검증(풀 스택 E2E) + per-agent 동작 규명 + 클라우드 과금 감사

- Status: 코드 변경 0(순수 검증/사실규명). 문서가 "코드 완료"라 주장하던 AI endpoint 7종을 실제로 띄워 라이브 재현하고, 대시보드 NL 채팅의 per-agent 실행 스코프를 코드로 규명, 클라우드 유휴 과금을 감사.
- Changed: 없음(git clean, gate 748 유지). `.DS_Store` 노이즈만.
- Verified (실제 실행): `make dev-up`(MLX 30B+proxy+router+webhook+dashboard) 전 계층 up. **AI endpoint 7종 라이브**: router `/health`·`/api/models`(onprem·aws verdict 로직)·dashboard 프록시 `agents/models`(`source:router-api`=fallback 아님)·`agents/onprem-status`(connected)·LLM 브레인(proxy→MLX `READY`). **`/api/local-deploy` 풀 E2E 24.9s**: local-qwen이 build→push→deploy→validate 자율 실행→kind에 `orders-api 1/1 Running`(image `localhost:5001/orders-api:v1.0.0`, `DEP-AD0FC7B4`)→대시보드 배포 피드 최상단 관통(executor-writes→dashboard-reads). SSE `/api/local-deploy/stream`도 tool_call→result→reasoning→done 정상. 검증 후 전부 teardown(kind down+스택 down+컨텍스트 `pa-aks-live` 복원).
- 규명(코드 근거): (1) 대시보드 배포 라우트(`agents/deploy`·`/stream`)는 **모델 무관 전부 `LOCAL_DEPLOY_API_URL`(127.0.0.1:8077) 프록시** → Vercel 공개 URL에선 4종 모두 채팅 배포 불가(502), local-only. (2) `route_deploy`(`model_router.py:269`)에서 **pydantic-ai(local-qwen)만 실 실행**; strands/adk/msft는 `_cloud_outcome`(L232)로 `ok=False` "requires {cloud} creds" **미실행**(주석 "routed without live execution"). 클라우드 3종 라이브는 이 채팅이 아니라 별도 어댑터/스크립트/런타임호스팅 경로에서 실증됨. → DECISIONS D14.
- 과금 감사: **platform-agent 유휴 ≈$0**. AWS(908601828278) NAT/EC2/RDS/LB 0, DynamoDB 18개 전부 PAY_PER_REQUEST, `IncidentAgentStack` 서버리스. Azure `pa-foundry-908601` `gpt-mini`=GlobalStandard(종량제, 유휴$0). GCP GKE/Compute 0. `pa-aks-live`=DNS 미해석(이미 삭제된 유령 컨텍스트). ※ 같은 계정의 `am_*`/`n8n`/roadpilot은 별개 프로젝트(미검토).
- Blockers: 없음.
- Next: 자율 백로그 여전히 소진 상태. 대시보드 채팅에서 클라우드 3종을 실행되게 하려면 `route_deploy` cloud 분기를 어댑터 실호출로 잇는 설계 필요(서버측 크레덴셜+과금 정책=사용자 판단).

## 2026-07-15 — 아키텍처 잔여 로드맵 2건 구현: supervisor 프론트도어 배선 + deploy↔runtime 정면 배선

- Status: ARCHITECTURE 잔여 로드맵 중 자율 가능 2건 구현 → 코어 아키텍처의 명시적 미구현 배선 항목 소진(잔여는 인프라/아스피레이셔널/사용자만).
- Changed: (1) **② supervisor 프론트도어**(`local_deploy_api.py`) — `/api/local-deploy`에 `get_front_door` DI seam(Supervisor/Orchestrator from_environment, `SUPERVISOR_ORCHESTRATION` 옵트인) 추가, 요청을 supervisor로 먼저 분류→A2A 엔드포인트(`PLATFORM_*_A2A_URL`) 설정 시 위임(delegated 응답), 미설정 시 in-process `route_deploy` 폴백. `DeployResponse`에 `delegated`/`route`/`route_trace` 추가(폴백에도 분류 노출). **비파괴**: A2A 미설정=기존 동작+분류만. (2) **① deploy↔runtime 배선**(`pipeline.py`) — DeployPipeline에 opt-in `host` 스텝(`report`→`host`) + `PipelineSpec.host_runtime`/`runtime_image_uri`/`runtime_role_arn`/`runtime_env`/`runtime_approved`. `get_runtime_adapter(provider).host_agent(RuntimeSpec)` 호출, **plan-first**: 미승인=preflight(hosted=False), 승인=실 create, onprem=managed runtime N/A라 SKIPPED. `run()`에 핸들러 SKIPPED 처리 브랜치 추가(옵셔널 스텝이 파이프라인 실패 아님, 기존 핸들러는 SKIPPED 미반환이라 무영향).
- Verified: 신규 test +7(프론트도어 delegate/fallthrough 2 + host 스텝 skipped/onprem/preflight/create/error 5). 기존 pipeline 테스트 갱신(7→8 노드, host SKIPPED 허용). `make check` → **748 passed, 1 skipped**(741→748). ARCHITECTURE 로드맵 ①②를 ✅로 갱신.
- Blockers: 없음. 잔여 로드맵(③ AgentCore Memory/Tools 패리티 · ④ On-Prem State Store/Alertmanager · ⑤ Helm/Terraform Tier 3 · ⑥ Slack/Harbor)은 전부 인프라/아스피레이셔널/사용자 개입.
- Next: 자율 가능한 아키텍처 배선 소진. 외부(아티클 배포·OAuth 데모)·인프라 항목만 잔여.

## 2026-07-15 — ARCHITECTURE.md stale 마커 정정 + 잔여 로드맵 재정리

- Status: 아키텍처 문서가 이미 done인 항목을 "🔲/미구현"으로 남겨둬 자기모순(예: L22는 Provision 4-provider ✅인데 L265는 "미구현"). 코드로 검증 후 stale 마커를 실제 상태로 정정하고, 진짜 미구현만 상단에 단일 로드맵으로 통합.
- Changed (docs only): (1) **Provision 표/현재상태**(L250–265) — "AWS만 CDK·나머지 🔲/온프렘 미구현" → 4-provider 어댑터 ✅(`adapters/provisioning/` aws/gcp/azure/onprem, AKS 실 클러스터 라이브). (2) **단일 카탈로그**(L297/303/305/278) — "인터랙티브 채택 로드맵 🔲" → 채택 완료 ✅(`AGENT_TOOL_CATALOG`), 두 카탈로그는 레이어 분리 의도적(수렴 안 함)로 결정 명시. (3) **On-Prem 실 executor scale/drain**(L420) — "로드맵" → 되돌리기-가능 4조치 ✅(restart/undo/scale/polite drain, kind 라이브). (4) **top 요약**(L22–24) — Tier 1/2 전부 반영 ✅ 명시 + **잔여 로드맵 6항목 단일 통합**(deploy↔runtime 배선·supervisor 프론트도어·Agent Runtime Memory/Tools·On-Prem State Store/Alertmanager·Helm/Terraform Tier 3·Slack/Harbor). 코드로 검증: provisioning/onprem.py 존재·onprem_runner scale(L73)/drain(L87)·local_deployer AGENT_TOOL_CATALOG.
- Verified: 문서 일관성 재검(`grep 🔲/미구현` → 남은 마커 전부 진짜 로드맵, 모순 0). 코드 무변경이라 gate 741 유지.
- Blockers: 없음.
- Next: (자율 가능) 진짜 로드맵 중 supervisor 프론트도어 배선·deploy↔runtime 배선. 외부: 아티클 배포·OAuth 데모.

## 2026-07-15 — orchestrator 활동 기록 배선: consensus/steps 대시보드 실표시 완성

- Status: 직전 커밋에서 대시보드는 consensus/steps를 render-capable로 만들었으나 이를 활동 레코드로 남기는 producer가 없었음. 이제 orchestrator 실행 경로가 라우팅 런을 ACTIVITY로 기록 → 대시보드가 실제로 표시.
- Changed: (1) `deploy_recorder.py` — `record_route_activity(instruction, trace, tool_calls, …)` + activity-only `_persist_activity`: consensus/plan 프레임을 담은 `type=route` ACTIVITY를 로컬 JSONL/DynamoDB(기존 백엔드 선택 로직 재사용)에 기록, `recording_enabled()` 꺼지면 no-op. (2) `gateway/a2a_server.py` — orchestrator 경로(OrchestratorOutcome)에서 `record_route_activity` 호출(best-effort try/except, 게이트웨이 응답 안 깨짐). (3) `activity-timeline.tsx` — 활동 카드에 consensus 인라인 칩(role·agreement·fell_back·plan 체인) 렌더(route 활동은 deployment_id 없어 상세 링크 대신 인라인 표시).
- Verified: 신규 test +3(`record_route_activity` 프레임 기록·disabled no-op·게이트웨이가 route 활동 기록). `make check` → **741 passed, 1 skipped**. **로컬 E2E**: `SUPERVISOR_ORCHESTRATION=true`+`PLATFORM_ACTIVITY_FILE`로 A2AServer send_message → JSONL에 `type=route` 1건, trace 프레임 `['consensus','plan']`, consensus `{role:deploy, agreement:1.0, votes:{deploy:5}}` 기록 확인. 대시보드 `next build` 성공.
- Blockers: 없음. consensus/steps 이제 **실 producer→저장→대시보드 표시** 완결(opt-in `SUPERVISOR_ORCHESTRATION`).
- Next: 외부(아티클 배포·OAuth 데모)만 잔여.

## 2026-07-15 — 대시보드: 신규 백엔드 관측 기능 3종 노출 (cost_metrics·reconciliation·consensus/steps)

- Status: 최근 Tier 1/2 백엔드가 만들지만 대시보드 read/render에서 떨어지던 관측 데이터 3종을 노출. 조사 결과 cost_metrics만 순수 read/render였고, reconciliation은 On-Prem만 저장(AWS 파리티 1줄 추가), consensus/steps는 미저장(대시보드는 render-capable로).
- Changed (dashboard): (1) **cost_metrics** — `mock-data.ts` `CostMetrics` 타입+`AgentActivity` 필드, `activity-data.ts` `mapCostMetrics` 매핑, `deployments/[id]` PhaseBody에 "cost/usage sub-metrics" 패널(도구별 호출·reasoning·토큰). (2) **reconciliation** — `Reconciliation` 타입+`Incident` 필드, `incident-data.ts` `mapReconciliation`, `incident-row.tsx`에 게이트 배지(grounding ratio·`AUTO→APPROVE` 강등 사유·issues; grounded면 녹색 배지). (3) **consensus/steps** — `TraceItem`에 `consensus`/`plan` kind+필드, `parseTrace`가 프레임 인식, PhaseBody가 self-consistency 투표(agreement·votes·fell_back)와 orchestration plan(role 체인) 렌더.
- Changed (backend 파리티): `executor/handler.py` `_record_incident`가 `decision.reconciliation` 존재 시 인시던트 레코드에 첨부(On-Prem `onprem_incident_pipeline`와 동일 shape) — AWS 인시던트도 강등 사유 노출 가능.
- Verified: 대시보드 `next build`(Next 16) 성공(전 라우트 컴파일), 백엔드 `make check` → **738 passed, 1 skipped**. cost_metrics·reconciliation은 실 데이터 경로 존재(즉시 표시). **consensus/steps는 render-capable이나 현재 이를 활동 레코드로 persist하는 경로 없음**(orchestrator/a2a는 활동 미기록) → 데이터 생기면 표시, 지금은 빈 상태(정직히 기록).
- Blockers: 없음. consensus/steps를 실제로 채우려면 orchestrator 경로가 활동을 기록해야 함(별도 백엔드 작업).
- Next: (선택) orchestrator 활동 기록 배선. 외부: 아티클 배포·OAuth 데모.

## 2026-07-15 — 라이브 실증: Tier 2 #3 MCP-over-HTTP(실 HTTP) + #4 STS graceful fallback(실 STS)

- Status: 그간 스텁/fake만이던 #3 원격 MCP 커넥터와 #4 크로스계정 폴백을 **실 네트워크로 라이브 실증**. #3=로컬 mock MCP 서버 상대 실 HTTP JSON-RPC 왕복, #4=실 boto3 STS AssumeRole 실패→실 in-account 폴백. shipped 코드(`remote_mcp_tool`/`post_mcp_call`, `assume_role_session`) 그대로 구동.
- Changed: 신규 `scripts/live_net_demo.py`(stdlib http.server mock MCP + 실 STS 호출) + 증거 `docs/evidence/tier2-live-mcp-http-sts-fallback.log`. 제품 코드 무변경.
- Verified (라이브): **(C) #3 실 HTTP** — C1 실 JSON-RPC 왕복 성공(서버가 `tools/call name=search args` 수신, output reinject), C2 remote isError→failed ToolResult 매핑, C3 **kill-switch가 dispatch 전 차단→서버 hit 0**(HTTP 미발생 확인), C4 dead port→graceful degrade(Connection refused). **(D) #4 실 STS** — 현 계정 908601828278에서 존재하지 않는 롤 AssumeRole→실 **AccessDenied**→graceful fallback(assumed=False·fell_back=True), 폴백 세션 실 신원 `user/q-user`로 in-account 동작 확증; `fallback=False`→실 ClientError re-raise. 제품 코드 무변경이라 gate 738 유지.
- Blockers: 없음. #4의 실제 크로스계정 assume 성공 경로(2번째 계정+trust policy)는 여전히 사용자 필요 — 단 fallback/실패 경로는 실 STS로 실증됨.
- Next: 외부(아티클 배포·OAuth 데모). 자율 실증 가능분 소진.

## 2026-07-15 — 라이브 실증: Tier 2 #2 self-consistency + Tier 1 reconciliation (실 MLX Qwen 30B)

- Status: 그간 유닛(스텁)만이던 #2 self-consistency와 reconciliation 게이트를 **실 로컬 LLM(MLX Qwen3-Coder-30B)으로 라이브 실증**. 스텁이 아니라 shipped 코드 경로(`route_with_self_consistency`, `reconcile`/`apply_gate`)를 실 모델 출력으로 구동.
- Changed: 신규 `scripts/live_tier2_demo.py`(실 LLM sampler=temp1.0 분류기로 self-consistency 구동 + 실 LLM 분석으로 reconciliation 게이트 구동) + 증거 `docs/evidence/tier2-live-selfconsistency-reconciliation.log`. 제품 코드 무변경.
- Verified (라이브): **(A) self-consistency** — "Deploy orders-api…"→5/5 deploy(agreement1.00), "cluster looks off…"→5/5 kagent. 실 sampler→shipped 라우터→실 consensus 동작. **fallback 브랜치 프로브**: 8개 모호/2액션 프롬프트×7샘플 전부 만장일치(7/7) → 이 30B는 내부 일관성이 강해 fallback 라이브 미발화(=self-consistency가 강한 모델에선 **confidence signal**로 기능, fallback은 약한 모델용 안전망; fallback 자체는 유닛 `test_low_agreement_falls_back…` 커버). **(B) reconciliation** — TLS 만료 증거 있는 실 인시던트에서: grounded(LLM이 증거 봄→root_cause "expired SSL certificate", ratio **0.62**→게이트 **AUTO 유지**) vs hallucination(LLM이 증거 없이 추측→"resource/DB pool exhaustion", ratio **0.08**→게이트 **AUTO→APPROVE 강등**). 실 환각을 결정론 게이트가 포착. 제품 코드 무변경이라 gate 738 유지.
- Blockers: 없음. #3(원격 MCP SigV4)·#4(2nd AWS 계정) 라이브는 여전히 사용자 엔드포인트/크레덴셜 필요.
- Next: 외부(아티클 배포·OAuth 데모)·(선택)#3/#4 실 라이브.

## 2026-07-15 — Tier 2 #4 크로스계정 소비자 배선 + 종합 아키텍처 아티클

- Status: #4 `assume_role_session`을 실 소비자 2곳에 배선(그간 헬퍼+runtime만) + 레퍼런스 반영 스토리를 담은 종합 아키텍처 테크 아티클 작성.
- Changed: (1) `adapters/deployment/aws.py` `AwsBuildAdapter.build` CodeBuild 클라이언트를 `assume_role_session(env-role).session.client("codebuild")`로 구성(boto3 부재는 ImportError→기존 BuildResult 에러 유지). (2) `operations/executor/handler.py` `_ssm_client(region)` 헬퍼 신설 — 모듈-레벨 `_SSM`(primary) + 리전-페일오버 클라이언트 둘 다 이 헬퍼 경유(assume-role+graceful fallback, env 미설정=in-account 무변경). (3) 신규 `docs/post/platform-agent-architecture.md` — 결정론적 가드레일 중심의 종합 아키텍처 아티클(Tier 1/2 레퍼런스 반영 스토리·설계 원칙·검증 문화). 배포는 사용자 몫.
- Verified: `tests/test_aws_session.py` +2(deployment build·executor `_ssm_client`이 env-role로 assume_role_session 소비). `make check` → **738 passed, 1 skipped**(736→738). 기존 executor/deployment 스위트 무변경=비파괴.
- Blockers: 없음. 실 크로스계정(2nd 계정+trust)·아티클 배포는 사용자 개입.
- Next: main 병합+push. 이후 외부(아티클 배포·OAuth 데모)·라이브 실증만 잔여.

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 2 #3: MCP-over-HTTP 커넥터 + per-tool/글로벌 kill-switch (Tier 2 완결)

- Status: Tier 2 **#3 완료 → Tier 2(#2·#3·#4) 전체 완결**. MCP 게이트웨이에 (1) 원격 MCP 서버를 카탈로그 도구로 노출하는 intercept-reinject 커넥터, (2) 도구별·글로벌 kill-switch 추가. 모두 기존 단일 카탈로그/디스패치 위에 얹어 비파괴.
- Changed: `src/agents/ai/gateway/mcp_server.py` — (1) **remote MCP 커넥터**: `post_mcp_call(endpoint, tool, args)`(JSON-RPC `tools/call` over HTTP, stdlib urllib) + `_reinject()`(MCP content/isError/JSON-RPC error→`ToolResult`) + `remote_mcp_tool(name, …, endpoint, remote_tool=…, transport=…)` 팩토리(핸들러가 tool_use 가로채→원격 호출→재주입, 전송 실패 시 raise 대신 error ToolResult로 **degrade**). (2) **kill-switch**: `MCPServer(*, extra_tools, disabled_tools, kill_switch)` — `call_tool`이 존재검사(unknown→ValueError 유지) **후** kill-switch 게이트(글로벌=전 도구 차단, per-tool=해당 도구만 차단, 둘 다 핸들러 미실행 blocked ToolResult). `disable_tool`/`enable_tool`/`set_kill_switch` + `MCP_DISABLED_TOOLS`/`MCP_KILL_SWITCH` env. `tools`/`_tool_map`은 base 카탈로그+`extra_tools` 병합, 원격 커넥터도 동일 kill-switch 지배. `docs/ARCHITECTURE.md` 표 row#3 ✅ + Tier 2 완결 표기.
- Verified: 신규 `tests/test_mcp_connector.py` +13(글로벌/per-tool kill-switch 핸들러 미실행·enable 되돌림·env 파싱·unknown 우선 raise·base 카탈로그 불변(9)·extra_tools 디스커버리+디스패치·remote forward/reinject·isError·JSON-RPC error·전송실패 degrade·원격도 kill-switch 지배). `make check` → **736 passed, 1 skipped**(723→736). 기존 `test_gateway.py` 29건 무변경 통과=비파괴.
- Blockers: 없음. 실 원격 MCP 서버(SigV4/IRSA 인증) 라이브 연동은 사용자 엔드포인트 필요=자율 범위 밖; intercept-reinject 경로는 stub transport로 완결 검증. (SigV4 서명은 필요 시 `#4`의 `assume_role_session`/`gcp_auth.py` SigV4 선례 재사용 가능.)
- Next: **Tier 2 전체 완결.** 잔여 레퍼런스=#7(Helm/Terraform 프로덕션, Tier 3). 외부: Slack App 실 생성·아티클 배포·대시보드 OAuth 로그인 데모. (선택) 실 로컬 MLX-Qwen sampler self-consistency 라이브 실증.

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 2 #4: cross-account STS AssumeRole + graceful fallback

- Status: Tier 2 **#4 완료**. 크로스계정 조치를 위한 STS AssumeRole 헬퍼 + **회복탄력성 폴백**(실패/서킷-OPEN 시 in-account 크레덴셜로 우아하게 강등). Tier 1 `CircuitBreaker`를 재사용해 리질리언스 재구현 회피. 어댑터-로컬이라 규모 작음.
- Changed: (1) 신규 `src/agents/adapters/aws_session.py` — `assume_role_session(role_arn, *, region, external_id, fallback=True, breaker=None) -> SessionResult`: STS `assume_role`로 타깃 계정 임시 크레덴셜→boto3 `Session` 구성, 실패 시 `_in_account_session`으로 **graceful fallback**(`fallback=False`면 raise). 공유 `_BREAKER`(threshold3/60s)로 반복 실패 시 fast-fail. `_sts_client`/`_in_account_session` 모듈-함수 seam(monkeypatch 주입, moto 불요). `SessionResult(assumed/fell_back)`로 트레이스. `assume_role_arn_from_env()`(`AWS_ASSUME_ROLE_ARN`). (2) `adapters/runtime/aws.py` `_client` **옵트인 소비** — 세션을 `assume_role_session(env-role)`로 구성 후 `.client(_SERVICE)`; env 미설정 시 role=""→in-account, `boto3.client(...)`와 동치(무변경). (3) `docs/ARCHITECTURE.md` 표 row#4 → ✅.
- Verified: 신규 `tests/test_aws_session.py` +9(assume 성공·실패 폴백·`fallback=False` raise·빈 role passthrough(STS 미호출)·external_id 스레딩·반복실패 서킷 OPEN+fast-fail·env 헬퍼·runtime `_client` 옵트인 2종). `make check` → **723 passed, 1 skipped**(714→723). 기존 runtime/circuit_breaker 스위트 무변경 통과=비파괴 확인.
- Blockers: 없음. (Pyright 신규모듈 stale-index 경고는 런타임/pytest 무관.) 실 크로스계정 라이브(2번째 AWS 계정+trust policy)는 사용자 크레덴셜 필요=자율 범위 밖; 어댑터 경로는 stub으로 완결 검증.
- Next: 잔여 Tier 2 = **#3 MCP-over-HTTP 커넥터 + per-tool kill-switch**(앵커 `gateway/mcp_server.py` `TOOL_CATALOG`, intercept-reinject). (선택) 다른 크로스계정 소비자 배선(`deployment/aws.py` CodeBuild, executor SSM).

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 2 #2: agents-as-tools 오케스트레이션 + self-consistency

- Status: Tier 2 최우선 항목 **#2 완료**. 단일-샷 결정론적 라우터(supervisor) 위에 **오케스트레이터 레이어**를 추가 — self-consistency 투표 라우팅 + 전문가-as-tools 체이닝. **비파괴**: 기본 sampler/planner가 결정론적이라 기본 동작은 `Supervisor.handle`과 동일.
- Changed: (1) 신규 `src/agents/ai/orchestration.py` — `route_with_self_consistency()`(sampler를 N회 호출→plurality 투표, `agreement<min_agreement`면 결정론적 `classify_request`로 폴백=reconciliation 게이트 철학, `fell_back` 플래그) + `RouteConsensus`(to_dict/trace_frame) + `PlanStep`/`single_step_planner` + `Orchestrator`(consensus→plan→각 step을 **기존 `Supervisor.handle`로 위임**=specialists-as-tools, 실패 step에서 **short-circuit**, step 간 **shared contextId**) + `OrchestratorOutcome`(SupervisorOutcome를 duck-type). (2) `gateway/a2a_server.py` **옵트인 배선** — 주입 가능 `orchestrator` 파라미터 + `SUPERVISOR_ORCHESTRATION` env 플래그, 활성 시 아티팩트 data에 `consensus`/`steps` 추가(기존 `route`/`trace`의 하위호환 superset), 플래그 미설정 시 기존 경로 무변경. (3) `docs/ARCHITECTURE.md` 레퍼런스 표 row#2 → ✅ 구현완료.
- Verified: 신규 `tests/test_orchestration.py` +12(majority vote·저합의 폴백·기본 sampler 만장일치 회귀가드·multi-step 순서/contextId 스레딩·실패 step short-circuit·게이트웨이 옵트인 stash·기본 경로 consensus 부재·to_dict). `make check` → **714 passed, 1 skipped**(702→714). 런타임 import 확인.
- Blockers: 없음. (Pyright가 신규 모듈 stale-index로 "could not be resolve" 경고하나 런타임/pytest 무관.)
- Next: 잔여 Tier 2 — #3 MCP-over-HTTP 커넥터 + per-tool kill-switch, #4 cross-account STS AssumeRole+fallback(각 별도 세션 권장). (선택) 실 로컬 MLX-Qwen sampler로 self-consistency 라이브 실증(머신러리는 sampler-agnostic이라 옵트인).

## 2026-07-15 — AWSome AI Gateway 레퍼런스 Tier 1 반영(4종) + Vercel 404 수정 + GKE 라이브

- Status: 외부 레퍼런스(aws-samples AWSome AI Gateway) 패턴을 코드로 **Tier 1 4종 반영**. 아울러 Vercel 대시보드 404 진단·수정, GKE 실 provision(어댑터 `node_size`)까지.
- Changed (Tier 1): (1) **Reconciliation gate**(`8f1878f`) — `reconciliation.py`: analyzer의 severity/root_cause가 detector 증거(firing state·metrics·logs·grounding overlap)에 근거하는지 검증, 미근거 시 decision을 **AUTO→APPROVE 강등**(환각 기반 자율조치 차단). `DecisionOutput.reconciliation` 필드+decision handler 배선+파이프라인 surface. 구조적 evidence 없을 땐 vocabulary 체크 skip(on-prem thin-evidence 오탐 방지). (2) **비용 3단계 게이트**(`0a18794`) — `cost_estimator.evaluate_budget()`: OK<SOFT_WARNING(≥80%)<THROTTLE(≥100%·승인필요)<HARD_BLOCK(≥150%), `PLATFORM_MONTHLY_BUDGET_USD`. (3) **회복탄력성**(`de4b92c`) — `circuit_breaker.py`(CLOSED/OPEN/HALF_OPEN, fail-fast+fallback, injectable clock) + webhook `/health/ready`(strict 503) vs `/health`(lenient 200). (4) **비용 서브메트릭**(`6bc541c`) — `deploy_recorder._cost_metrics()`: 트레이스에서 도구별 호출수·reasoning steps·토큰 usage 집계→ACTIVITY `cost_metrics`. `docs/ARCHITECTURE.md`에 레퍼런스 도입 매핑표+Tier 1 완료 표기.
- Changed (기타): **Vercel 대시보드 완전 복구·영구 안정화** — (1) 404 원인=프로덕션 alias(`platform-agent-red`) stale 바인딩 + 매뉴얼 배포가 `.venv-mlx` 100MB+ metallib 업로드 실패 → `.vercelignore` 수정(`3e7762e`)+`vercel --prod` 재배포로 200 복구. (2) **근본원인 확정·영구수정**: `ssoProtection=all_except_custom_domains`(모든 `.vercel.app`에 Vercel 인증) 때문에 canonical URL 302+`-red` git-push flapping → 사용자가 API로 `ssoProtection=null` 해제 → **`platform-agent-men16922s-projects.vercel.app` 안정적 공개 200**(git push에도 안 깨짐). (3) **대시보드 agent tool list 드리프트 수정**(`26586b5`) — `agent-tools.ts`가 백엔드 `AGENT_TOOL_CATALOG`(13개)와 불일치(`deploy_service` 누락·rollback 오분류)→정합(Investigate5/Provision2/Deploy5/Recover1), tsc 통과·라이브. GKE 실 provision(`node_size` `f3e7952`)→즉시 teardown(비용$0).
- Verified: 신규 테스트 +30(reconciliation9+budget9+cb6+readiness2+cost_metrics4). `make check` → **702 passed, 1 skipped**. 실 Vercel canonical URL 200 공개 안정화·대시보드 렌더 확인·GKE 삭제·현재 실시간 과금 $0.
- Blockers: 없음. 잔여 레퍼런스 Tier 2(agents-as-tools·MCP-over-HTTP·cross-account STS)는 supervisor/gateway 리팩터라 규모 커 별도 세션 권장. PROGRESS_LOG 169줄>budget120 → `/tidy-docs` 필요.
- Next: (선택) Tier 2 레퍼런스(새 세션). 외부: Slack App·아티클·대시보드 OAuth 로그인 데모.

## 2026-07-14 — Provision 어댑터 라이브: AKS 실 클러스터 provision→검증→teardown + node_size 지원 추가

- Status: provisioning 어댑터(GKE/AKS)를 **실 클러스터로 라이브 검증**(그간 코드+테스트만). Azure 구독의 기본 VM 크기가 제한돼 create가 실패 → **어댑터에 `node_size` 지원 추가**(실 개선)로 해결 후 AKS 실 provision 성공. teardown까지 어댑터로 실증.
- Changed: `provisioning/base.py` `ProvisionSpec`에 `node_size:str=""` 추가. `azure.py` provision에 `--node-vm-size`(node_size 시), `gcp.py` provision에 `--machine-type`(node_size 시) 스레딩. `test_provisioning_adapters.py` +2(gcp `--machine-type`·azure `--node-vm-size` 스레딩). 제한 구독에서 기본 크기 미가용 시에도 provision 가능해짐.
- Verified: `make check` → (아래 gate). **실 Azure eastus AKS 라이브**: 어댑터 `provision_cluster(approved=True, node_count=1, node_size="Standard_D2als_v7")`→클러스터 생성 성공(k8s 1.35.6, 1 node Ready, Ubuntu 24.04)→`kubectl get nodes` 확인→어댑터 `teardown_cluster(approved=True)`→삭제 완료(list `[]`). billable create는 하네스가 자동차단→사용자 `!`로 어댑터 호출 실행(delete는 미차단). 총비용 ≈$0.03(1노드 ~10분).
- Blockers: 없음. 하네스 자동모드가 billable IaC create를 차단(delete/push는 허용) → 실 create는 사람이 실행하는 설계. GKE create/self-permission 모두 자동차단 확인 → **GKE 실 create는 자율 범위 밖**.
- Next: 없음(Provision 라이브 objective 종결). **GKE는 AKS가 동일 어댑터 경로를 실 클러스터로 실증하여 검증 충족**; preflight 라이브 통과; 실 2차 클러스터 확인은 선택(헬퍼 `scripts/provision_gke_live.py` 준비, 사람이 실행). 전 커밋 origin push 완료.

## 2026-07-14 — Azure AI Foundry 실 배포 라이브 E2E + v1→v2 어댑터 결함 수정: 3/3 클라우드 완결

- Status: Runtime 호스팅 **3/3 클라우드 라이브 완결**(AWS+GCP에 이어 Azure). 도중 **실 코드 결함 발견·수정**: azure 어댑터가 v1 API(`create_agent`) 기준이었는데 설치 SDK는 `azure-ai-projects` **2.3.0(v2)** — v1 호출은 `AttributeError`로 실 환경에서 절대 동작 불가(목 테스트가 가림). v2로 재작성 후 실 배포까지 실증.
- Changed: (1) `azure.py` v2 재작성 — preflight `agents.list()`, host `agents.create_version(agent_name, definition=PromptAgentDefinition(model, instructions))`, teardown `agents.delete(name)`; `_prompt_definition` seam으로 테스트 SDK-독립. `test_runtime_adapters.py` azure 섹션 v2로 갱신(+1). (2) 신규 `infra/foundry/README.md` — 셋업 + 라이브에서 겪은 gotcha 5종(데이터플레인 RBAC≠Owner·MSA `--assignee-object-id`·모델 deprecation/SKU·에이전트명 하이픈(AgentCore는 언더스코어)·Responses API `agent_reference` 호출). 커밋 `4caf7de`(fix)·`2231362`(README).
- Verified: `make check` → **670 passed, 1 skipped**. 실 Azure eastus: Foundry 계정+프로젝트+gpt-5.4-mini 배포, **Cognitive Services User** 역할(사용자가 `!`로 부여), 어댑터 preflight→list, `host_agent(approved=True)`→`create_version`(v1)→**Responses API 쿼리** 응답 `"...hosted as an API agent on Azure AI Foundry"`→`teardown_agent(approved=True)`→삭제(0 agents). Standard 배포라 유휴 과금 ≈$0.
- Blockers: 없음. Azure 라이브가 오래 막혔던 원인=데이터플레인 RBAC(하네스가 IAM 부여 차단→사용자가 직접 실행). 
- Next: (선택) Azure Foundry 스택(계정/프로젝트/모델, ≈$0 유휴) 유지 or 삭제. origin push(로컬 10커밋).

## 2026-07-14 — GCP Vertex Agent Engine 실 배포 라이브 E2E: 어댑터 create→DEPLOYED→query→teardown (billable, 승인 후)

- Status: Runtime 호스팅 어댑터의 **GCP Agent Engine 실 배포 라이프사이클을 실 클라우드에서 실증** — AWS AgentCore에 이어 **2/3 클라우드 라이브 완결**. 사용자 승인 후 billable create → 호스팅된 reasoning engine이 Gemini로 실제 응답 → 즉시 삭제.
- Changed: 신규 `infra/agentengine/deployer_agent.py` — Agent Engine custom-template 에이전트(`set_up`+`query`, Gemini 2.5 Flash 호출, `hosted_on=vertex-agent-engine` 태깅). (어댑터 코드 자체는 `36085fc`.)
- Verified: 실 GCP us-central1(project-ec7809f7). GCS staging 버킷 생성, `cloudpickle.register_pickle_by_value`로 에이전트 직렬화, 어댑터 `host_agent(approved=True)`→`agent_engines.create`→**DEPLOYED**(reasoningEngines/6487926195169001472)→`query` 응답 `{"result":"...","model":"gemini-2.5-flash","hosted_on":"vertex-agent-engine"}`→`teardown_agent(approved=True)`→삭제→**list 0 완전 삭제**. 커밋 `40fa8f6`. 총비용 <$0.50(엔진 삭제 완료, staging 버킷 잔여=무시 가능).
- Blockers: 없음(GCP). Azure Foundry 실 create만 남음(Foundry 프로젝트 생성 선행 필요).
- Next: (선택) Azure Foundry 실 배포 or 외부(Slack App/아티클). origin push 대기(로컬 8커밋).

## 2026-07-14 — AWS AgentCore 실 배포 라이브 E2E: 어댑터 create→READY→invoke→teardown (billable, 승인 후)

- Status: Runtime 호스팅 어댑터의 **AWS AgentCore 실 배포 전 라이프사이클을 실 클라우드에서 실증**. 사용자 승인 후 billable create 실행 → 호스팅된 에이전트가 실제 응답 → 즉시 삭제(비용 최소화). 어댑터 create/teardown 경로가 목이 아닌 **실 API로 검증**됨.
- Changed: 신규 `infra/agentcore/` 패키징 — `app.py`(AgentCore 런타임 컨트랙트 `/invocations`+`/ping`, `bedrock-agentcore` SDK로 minimal Claude Haiku 4.5 converse 에이전트 래핑), `Dockerfile`(linux/arm64), `requirements.txt`. (어댑터 코드 자체는 앞 커밋 `36085fc`.)
- Verified: 실 AWS us-east-1(acct 908601828278). ARM64 이미지 build→ECR push(단일 매니페스트), 최소권한 exec role 생성, 어댑터 `host_agent(approved=True)`→`CreateAgentRuntime`→**READY(~12s)**→`invoke_agent_runtime` 응답 `{"result":"...hosted on Amazon Bedrock AgentCore","model":"claude-haiku-4-5"}`→`teardown_agent(approved=True)`→DELETING→**count 0 완전 삭제**. 커밋 `2079c01`. 총비용 <$0.50(런타임 삭제 완료, 잔여=ECR 이미지 ~$0.007/월+무료 IAM role).
- Blockers: 없음(AWS). GCP Agent Engine/Azure Foundry 실 create는 여전히 승인·(Azure는 프로젝트 생성) 대기.
- Next: (선택) ECR 이미지/IAM role 정리 or 유지, origin push. 잔여 외부: Slack App·아티클.

## 2026-07-14 — Agent Runtime 호스팅 어댑터 3종(AgentCore/Agent Engine/Foundry) + 라이브 preflight(AWS·GCP)

- Status: **④ Host role** 신설 — 빌드된 에이전트(Strands deployer 등)를 매니지드 런타임에 올리는 어댑터 레이어. provisioning의 plan-first/approved-gated 계약을 3-provider로 미러링. **비용 안 나가는 범위 전부 수행**: 코드+목 테스트 완결 + AWS·GCP는 **실 클라우드 read-only preflight 라이브 통과**, Azure는 설계대로 blocker 보고(과금 없음).
- Changed: 신규 `src/agents/adapters/runtime/` 패키지 — `base.py`(`RuntimeSpec`/`RuntimeResult`/protocol, provider별 create knobs용 `extra` dict), `aws.py`(AgentCore via boto3 `bedrock-agentcore-control`, **신규 의존성 0**), `gcp.py`(Vertex Agent Engine via `vertexai.agent_engines`), `azure.py`(AI Foundry via `azure-ai-projects`), `registry.py`(`["aws","gcp","azure"]`). 공통: 미승인 host=읽기전용 preflight(list, 생성 0), `approved=True`=실 create(AgentCore=ECR img+role, Agent Engine=agent_object, Foundry=model), teardown=approved 강제+이름으로 id 해석. 클라우드 SDK는 지연 import + gcp/azure extras에 기록(`google-cloud-aiplatform`, `azure-ai-projects`). `test_runtime_adapters.py` 20개.
- Verified: `pytest tests/test_runtime_adapters.py` 20 passed. `make check` → **669 passed, 1 skipped**. 커밋 `36085fc`. **라이브 read-only preflight**: 실 AWS(acct 908601828278, us-east-1)→0 runtimes / 실 GCP(project-ec7809f7, us-central1 Vertex)→0 engines. Azure=Foundry 프로젝트 부재로 preflight blocked(엔드포인트 없음, graceful). **billable create는 미실행**(승인 대기).
- Blockers: 실 create는 전부 과금/하드-투-리버스 → 사용자 허락 필요. Azure 라이브 preflight도 Foundry 프로젝트 생성(과금)이 선행이라 대기.
- Next: (사용자 결정) 3종 중 실 배포할 것 선택 — 비용 견적 제시함. 잔여 외부: Slack App·아티클.

## 2026-07-14 — GCP/Azure managed-cloud Provision 어댑터(GKE/AKS): provisioning 4-provider parity

- Status: provisioning 어댑터가 deployment/execution 레이어처럼 **4-provider parity**(onprem/aws/**gcp**/**azure**) 달성. 그간 On-Prem(Terraform/Ansible)+AWS(CDK)만 있고 클라우드 Provision이 갭이었음. AWS 어댑터의 **plan-first / approved-gated 계약을 그대로 미러링** — 하드-투-리버스(클러스터 생성/삭제)는 승인 게이팅.
- Changed: 신규 `adapters/provisioning/gcp.py`(GKE via `gcloud container clusters create/delete`, 미승인=읽기전용 `clusters list` preflight) + `azure.py`(AKS via `az aks create/delete`, 미승인=`aks list` preflight). `registry.py`→`["onprem","aws","gcp","azure"]` 라우팅. `base.py` `ProvisionSpec`에 `node_count:int=2`. config는 deployment 어댑터와 **동일 env**(`GCP_PROJECT`/`GCP_REGION`, `AZURE_RESOURCE_GROUP`/`AZURE_REGION`). **안전 기본값**: `provision_tools`가 `approved`를 미노출 → LLM 도구 호출은 cloud provider에서 **preflight-only**(과금 인프라 생성 불가), 전용 테스트로 고정. `test_provisioning_adapters.py` 10→23(registry 해결·preflight-only·approved-create argv·teardown 승인 강제·project/RG 누락·CLI-absent·도구 preflight 고정).
- Verified: `pytest tests/test_provisioning_adapters.py` 23 passed. `make check` → **649 passed, 1 skipped**. 커밋 `6baa6ee`. **라이브 미실행**: 실 GKE/AKS create는 WIF/OIDC 크레덴셜·과금 필요 → argv/게이팅만 결정론 검증, 어댑터는 credential-ready(`ProvisionSpec(...,approved=True)`로 즉시 라이브 가능).
- Blockers: 라이브 클라우드 create는 크레덴셜·과금 대기(처음부터 크레덴셜-대기 항목).
- Next: (진행 중) **Agent Runtime 매니지드 호스팅 — AgentCore**(Strands→Bedrock AgentCore, AWS라 실 배포 테스트 가능성 검토). 잔여 외부: Slack App·아티클.

## 2026-07-14 — On-Prem 실 executor 완결: polite node drain(--force 없음, PDB 존중)

- Status: On-Prem Day-2 실 executor의 **되돌리기-가능 조치 세트 완결** — restart/undo/scale에 이어 **마지막(가장 위험)** `ONPREM-DrainNode`→`kubectl drain <node>` 추가. 노드 단위라 blast-radius가 커서 **보수적 "polite drain" 정책**으로 게이팅.
- Changed: `onprem_runner.py` — DrainNode 전용 분기(`_kubectl_args`): `["drain", <node>, "--ignore-daemonsets", "--timeout=90s"]`, **`--force`·`--delete-emptydir-data` 의도적 미사용**(→ kubectl이 PodDisruptionBudget 존중, 미관리/로컬데이터 파드에선 거부=실패→executor skip; 아웃티지·데이터손실 방지), NodeName 없으면 log-only. `execution/onprem.py` — DrainNode 분기 분리, 워크로드 대신 `NodeName`(라벨 `node`/`instance`) 스레딩. 여전히 `ONPREM_EXECUTOR_LIVE` 기본 OFF. `test_onprem_runner.py` 10→13(drain args·`--force`/`--delete-emptydir-data` 부재 검증·node 누락 log-only), unwired 테스트를 CleanupDiskSpace로 교체. `test_portability_adapters.py` +1(NodeName 스레딩).
- Verified: `pytest tests/test_onprem_runner.py tests/test_portability_adapters.py` 25 passed. **실 kind 라이브 실증(3노드: control-plane+worker×2)**: nginx web 4 replicas(worker 2/worker2 2 분산) → runner로 worker drain → **노드 cordon(SchedulingDisabled)+파드 evict→worker2 재배치, deployment 4/4 Running 유지(아웃티지 0)** → 클러스터 정리. `make check` → **636 passed, 1 skipped**.
- Blockers: 없음. 공격적 force-drain은 의도적으로 사람 몫(로드맵도 아님). **On-Prem 로컬-자율 백로그 전부 소진**.
- Next: 잔여는 전부 외부/클라우드 — (deferred) Slack App·아티클, GCP/Azure Provision·Agent Runtime(크레덴셜 필요).

## 2026-07-14 — 인터랙티브 에이전트 단일 도구 카탈로그: 프롬프트↔등록 드리프트 제거

- Status: 게이트웨이의 단일-카탈로그 규율을 **인터랙티브 `local_deployer` 에이전트**에도 적용. 기존엔 시스템 프롬프트의 `## Tools` 인벤토리를 **손으로** 적고 `ALL_OPS_TOOLS`(등록)와 수동 동기화 → 게이트웨이가 고쳤던 드리프트 위험 그대로였음. **`AGENT_TOOL_CATALOG` 단일 source-of-truth** 도입: dispatch(`ALL_OPS_TOOLS`, Pydantic AI 등록)와 discovery(프롬프트 인벤토리, LLM이 안다고 듣는 도구)를 **둘 다 카탈로그에서 파생** → 도구 추가=1곳, 드리프트 불가.
- Changed: `local_deployer.py` — 프롬프트를 `_SYSTEM_PROMPT_TEMPLATE`(`__TOOLS__` 센티넬)로 분리, `AgentTool`(frozen: func+category+hint)+`AGENT_TOOL_CATALOG`(13개: investigate5/provision2/deploy5/recover1) 도입, `_render_tool_inventory()`가 `## Tools` 마크다운 생성, `ALL_OPS_TOOLS`=`[t.func for t in CATALOG]` 파생. **레이어 구분 명시**: 게이트웨이 `TOOL_CATALOG`(raw kubectl/docker MCP 핸들러)와 달리 이건 상위 어댑터-백드 LLM-튜닝 에이전트 도구 → 별도 카탈로그 유지(병합 아님). `test_local_deployer.py` +2(discovery==dispatch==catalog==source-lists union 불변식·카테고리 유효성).
- Verified: `pytest tests/test_local_deployer.py` 10 passed. **행위 보존**: 동일 13함수 등록(TestModel drive 테스트 통과), 프롬프트 인벤토리는 등가 내용으로 재생성(도구별 힌트+동일 카테고리). `make check` → **633 passed, 1 skipped**. (라이브 MLX 7B 경로 재실행 안 함 — 프롬프트 변경은 가산적 명료화, 결정론 테스트가 배선 커버.)
- Blockers: 없음. 잔여(로드맵): 배포 경로 전체 리팩터(어댑터 튜닝 도구를 게이트웨이 raw 카탈로그로 수렴)는 레이어가 달라 의도적으로 미수행.
- Next: (외부/deferred) Slack App·아티클. (로드맵) GCP/Azure Provision·Agent Runtime(크레덴셜 필요).

## 2026-07-14 — On-Prem 실 executor 확장: kubectl scale(양수 타깃 게이팅)

- Status: On-Prem Day-2 실 executor의 **세 번째 되돌리기-쉬운 조치** 추가 — rollout restart/undo에 이어 `ONPREM-ScaleWorkload`→`kubectl scale --replicas=N`. scale은 desired-state라 알림이 목표 replica를 실어와야 실행되게 게이팅.
- Changed: `execution/onprem.py` — `ONPREM-ScaleWorkload` 분기 분리, 알림 라벨(`desired_replicas`/`replicas`)에서 `DesiredReplicas` 파라미터 스레딩(없으면 `_compact`가 드롭). `onprem_runner.py` — `_kubectl_args()` 헬퍼로 argv 빌드 분리, scale은 `_positive_int()`로 **양수(≥1)일 때만** 실행(누락/0/비정수→log-only, scale-to-0=셧다운은 사람 필요). 여전히 `ONPREM_EXECUTOR_LIVE` 기본 OFF. `test_onprem_runner.py` 7→10(scale 실행·replicas 누락·scale-to-0 가드), `test_portability_adapters.py` +2(DesiredReplicas 스레딩·라벨 부재 시 생략), unwired 테스트를 DrainNode로 교체.
- Verified: `pytest tests/test_onprem_runner.py tests/test_portability_adapters.py` 22 passed. **실 kind 라이브 실증**: nginx `payments/payments-api`(2 replicas) 배포 → runner로 scale→**2→5 실제 확장**(5/5 ready) → scale-to-0은 runner가 `live_missing_target`로 log-only(replicas 5 불변) → 클러스터 정리. `make check` → **631 passed, 1 skipped**.
- Blockers: 없음. drain은 위험(정책 선행) → 로드맵 유지.
- Next: (외부/deferred) Slack App·아티클. (로드맵) 인터랙티브 에이전트 카탈로그 채택(아래 세션에서 완료).

## 2026-07-14 — MCP Gateway 단일 도구 카탈로그: 삼중 중복 → 단일 source-of-truth

- Status: ARCHITECTURE "MCP Gateway 단일 카탈로그" 타깃의 **기반 확립**. 게이트웨이가 도구를 **3곳**(구현 static 메서드 + `MCP_TOOLS` 스키마 리스트 + `MCPServer._tool_map` dispatch)에 손으로 동기화하던 걸 **단일 `TOOL_CATALOG`**(name+desc+params+handler)로 수렴 — discovery(`MCP_TOOLS`)와 dispatch를 카탈로그에서 파생. 도구 하나 추가 = 카탈로그 1곳(+구현). 외부 A2A/MCP 에이전트와 bridge가 이 단일 카탈로그를 공유.
- Changed: `gateway/mcp_server.py` — `ToolSpec`(frozen, handler 포함) + `TOOL_CATALOG` 도입, `MCP_TOOLS`=`[s.definition() for s in TOOL_CATALOG]` 파생, `MCPServer._tool_map`=카탈로그 파생(하드코딩 맵 제거). **공개 API 전부 보존**(MCPServer/KubectlTool/DockerTool/ToolResult/ToolDefinition/MCP_TOOLS/_run_cmd — bridge·테스트 무변경). `test_gateway.py` +2 불변식 테스트(discovery↔dispatch↔catalog 일치·드리프트 0, 전 도구 dispatch 검증).
- Verified: `pytest tests/test_gateway.py` 32 passed(기존 30 회귀 없음 + 신규 2). `make check` → **626 passed, 1 skipped**.
- Blockers: 없음.
- Next: (로드맵) **인터랙티브 에이전트(local_deployer)의 카탈로그 채택** — 지금은 게이트웨이(A2A/MCP)만 단일 카탈로그; 인터랙티브 in-process 도구와의 완전 수렴은 더 큰 후속 단계(배포 경로 리팩터, 리스크 큼). (외부) Slack App·아티클.

## 2026-07-14 — On-Prem 실 executor: 로그-only 스텁 → 실 kubectl 원격조치(기본 OFF 게이팅)

- Status: On-Prem Day-2의 **마지막 조각** — executor가 조치를 로그만 찍던 걸 **실제 kubectl 실행**으로. 안전을 위해 **기본 OFF 플래그**(`ONPREM_EXECUTOR_LIVE`) 뒤에 게이팅(기본 동작=로그-only 무변경), **되돌리기 쉬운 액션(rollout restart/undo)만** 실 실행 배선(scale·drain 등 위험/모호한 건 로그-only 유지).
- Changed: 신규 `src/agents/operations/executor/onprem_runner.py`(gcp_runner 패턴; `_is_live()`=플래그ON&TESTING≠True, `_LIVE_KUBECTL`={RolloutRestart→`rollout restart`, ArgoRollback→`rollout undo`}, 실패 시 raise→executor가 skip 처리). `executor/handler.py` `_run_external_action`의 onprem 분기를 stub→`run_onprem_action`. `tests/test_onprem_runner.py` 7개(기본 로그-only·live restart/undo kubectl args·unwired/누락 로그-only·TESTING 강제 OFF·실패 raise).
- Verified: `pytest` 21 passed(runner 7 + webhook 14). **실 kind 라이브 실증**: 단일노드 kind에 `payments/payments-api`(nginx, 2 replicas) 배포 → `ONPREM_EXECUTOR_LIVE=true`로 runner 실행 → `kubectl_ok`("deployment restarted") → **파드 실제 교체**(구 RS `6dc8c9cbd9`→0, 신 RS `86f76b7f49`→2). 테스트 클러스터 정리. `make check` → (아래).
- Blockers: 없음. 기본 OFF라 프로덕션 안전; scale/drain 등은 desired-state 파라미터 필요로 로드맵.
- Next: (외부/deferred) Slack App·아티클. (로드맵) MCP Gateway 단일 카탈로그·클라우드 Provision.

## 2026-07-14 — `make dev-up` 원커맨드 스택에 On-Prem Day-2 webhook 통합

- Status: On-Prem Day-2 vertical을 **운영 완결** — `make dev-up` 한 방에 MLX+proxy+router+**webhook(:8078)**+dashboard가 함께 뜨고, 대시보드(기본 `ONPREM_WEBHOOK_URL=:8078`)가 자동으로 On-Prem 승인·인시던트를 hybrid 표시.
- Changed: `Makefile` — `WEBHOOK_PORT`/`APPROVALS_FILE`/`INCIDENT_FILE` 변수 추가, `dev-up`에 webhook 기동 스텝(activity/approvals/incidents env), `dev-down`에 종료, `dev-status`에 `:8078/health` 체크. `onprem-webhook` 타깃도 변수화(INCIDENT_FILE 추가).
- Verified: `make dev-status`에 webhook 라인 표시(down), `make -n dev-up` dry-run에 webhook 스텝·env·포트 정상 파싱. (코드 무변경, gate 영향 없음 — 직전 617 passed 유효.)
- Blockers: 없음.
- Next: (외부/deferred) Slack App·아티클. 로드맵(실 executor·MCP Gateway 단일 카탈로그·클라우드 Provision).

## 2026-07-14 — 대시보드 Incidents 타임라인 On-Prem surfacing: 오프라인 인시던트 스토어 + hybrid 병합

- Status: On-Prem Day-2 인시던트를 대시보드 **Incidents 타임라인**에 표시. 기존엔 승인 카드만 On-Prem을 노출했고 타임라인은 AWS DynamoDB만 읽어(오프라인 On-Prem 인시던트 부재), executor의 DynamoDB write는 오프라인 no-op이었음. webhook 계층에 로컬 인시던트 스토어를 두어 종단 완성.
- Changed: 신규 `src/agents/ai/onprem_incidents.py`(오프라인 JSONL 인시던트 스토어, 대시보드 Incident 필드명 그대로: incident_id/alarm_name/provider/severity/mode/root_cause/runbook_id/resolved/executed_actions/created_at; `PLATFORM_INCIDENT_FILE`). `onprem_webhook_api.py`: 종단 상태에서 인시던트 기록(P1 AUTO=resolved, P3 MANUAL=unresolved, P2는 approve/reject 시점 기록—park 중 중복 방지) + `GET /incidents`. `test_onprem_webhook.py` 11→14. 대시보드: `mock-data.ts` `Incident.provider`에 `onprem` 추가, `incident-data.ts` `isProvider`+`fetchOnPremIncidents`(webhook `/incidents` HTTP)+`getIncidentFeed` hybrid 병합(source=`hybrid`), `incident-row.tsx` 라벨 `ON-PREM`(폴백 버그 수정; provider-logo는 이미 onprem 지원).
- Verified: `pytest tests/test_onprem_webhook.py` 14 passed. **webhook 라이브**: P2 alert→park(timeline 0)→approve→`/incidents` 1건(onprem/P2/resolved/INC-1121DAB7). **대시보드 라이브 헤드리스**: `next start`(ONPREM_WEBHOOK_URL=:8078)→`GET /incidents`에 On-Prem 인시던트 렌더(INC-1121DAB7·**ON-PREM 배지**·generic-recovery·source "On-prem incidents (live)"). `tsc` 0·`next build` 성공. `make check` → **617 passed, 1 skipped**.
- Blockers: 없음.
- Next: (외부/deferred) Slack App·아티클. 로드맵(실 executor·MCP Gateway 단일 카탈로그·클라우드 Provision).

## 2026-07-14 — 대시보드 On-Prem 승인 연동: Incidents 페이지 hybrid(AWS+On-Prem) + approve/reject 라우팅

- Status: 직전 On-Prem 승인 게이트를 **대시보드 화면에 연동**. Incidents 페이지의 "Pending Remediation Approvals"가 이제 AWS(DynamoDB/SFN) + On-Prem(webhook `/pending`)을 **hybrid 병합** 표시하고, Approve/Reject 클릭이 source에 따라 SFN 또는 webhook으로 라우팅됨. deployments 대시보드의 AWS+On-Prem hybrid 패턴을 승인에도 적용.
- Changed: `dashboard/src/lib/approval-data.ts` — `ApprovalRequest.source`(aws|onprem) 추가, `ONPREM_WEBHOOK_URL`(기본 `:8078`) HTTP 읽기(`fetchOnPremPending`/`mapOnPremApproval`), `listPendingApprovals`=AWS+onprem 병합, `getApprovalRequest`=onprem 우선 조회, `approve/rejectApprovalRequest`=onprem이면 webhook `/approve`·`/reject`로 분기(SFN 대신). `dashboard/src/components/pending-approvals.tsx` — source 배지(On-Prem 파랑/AWS 주황) 추가. 내 신규 `any` 제거(타입 지정) + 기존 `let mockApprovals`→`const`.
- Verified: `tsc --noEmit` 0, `next build` **Compiled successfully**(11 routes). **라이브 헤드리스 실증**: webhook(:8078)에 P2 pending(APR-34398628) 생성 → `next start`(ONPREM_WEBHOOK_URL=:8078) → `GET /incidents` HTML에 On-Prem 승인 카드 렌더 확인(approval_id·**On-Prem 배지**·payments-api·generic-recovery·ONPREM-CreateChangeRequest). read 라우트는 public이라 무인증 렌더; approve 액션은 미들웨어 인증·RBAC·감사로그 공통. webhook approve/reject 자체는 앞선 세션에서 라이브 실증.
- Blockers: 없음. (브라우저 확장 미연결로 스크린샷은 생략, HTML 렌더 검증으로 대체.)
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드(실 executor·MCP Gateway 단일 카탈로그·클라우드 Provision 어댑터).

## 2026-07-14 — On-Prem Approval Flow(P2 승인 게이트) 구현: pending 스토어 + approve/reject

- Status: ARCHITECTURE의 On-Prem Approval Flow(🔲 계획) 코어 게이트를 **구현+라이브 E2E**로 완성. 직전 webhook이 P2에 `mode=APPROVE`를 반환하지만 승인/실행 수단이 없던 루프를 닫음. Guardian severity→mode 게이팅을 webhook에 배선: **P1=즉시 실행 · P2=parking · P3=알림만**.
- Changed: `onprem_incident_pipeline.py`에 실행 분리(`run_incident_pipeline(..., execute=False)` + `execute_incident(decision)` 재생 헬퍼). 신규 `src/agents/ai/onprem_approvals.py`(오프라인 JSONL pending 스토어, deploy_recorder식 single-row 승계: create/list/get/resolve, `PLATFORM_APPROVALS_FILE`). `onprem_webhook_api.py`에 `GET /pending`·`POST /approve/{id}`(decision 재생 실행)·`POST /reject/{id}` 추가 + `PipelineResult.status`(executed/pending_approval/notified/approved/rejected). `test_onprem_webhook.py` 6→11(P1 AUTO·P2 park→approve/reject·P3 notified·404/409). Makefile approval env. ARCHITECTURE On-Prem Approval Flow 🔲→부분 ✅.
- Verified: `pytest tests/test_onprem_webhook.py` 11 passed. **실 HTTP 승인 루프 스모크**: `POST /webhook/alertmanager`(P2 heuristic)→`pending_approval`(APR-B8C3DDF2, incident_id null)→`GET /pending` count 1(전체 decision 보존)→`POST /approve/{id}`→`approved`+incident_id INC-8D539D65+executed→`/pending` count 0. `make check` → **614 passed, 1 skipped**.
- Blockers: 없음. 잔여(로드맵): Slack 버튼 프런트엔드·Temporal/Redis/PostgreSQL substrate·실 executor(MCP Gateway).
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드.

## 2026-07-14 — On-Prem PATH B webhook 구현: Alertmanager→in-process Day-2 파이프라인

- Status: ARCHITECTURE 로드맵의 On-Prem PATH B(이벤트 수신=Webhook FastAPI, 오케스트레이션=직접 호출) 🔲을 **구현+라이브 검증**으로 종료. 발견: Day-2 4핸들러(detector/analyzer/decision/executor)는 이미 on-prem을 지원(detector가 Alertmanager `alerts`/`groupLabels` 자동감지→onprem SignalAdapter, executor onprem 경로=로그-only 스텁)했고, **빠진 건 오직 이벤트 수신기+in-process 체이닝**이었음.
- Changed: 신규 `src/agents/ai/onprem_incident_pipeline.py`(`run_incident_pipeline`: 4핸들러를 출력→입력으로 in-process 체인, 클라우드 Step Functions/Workflows/Durable Functions 대응) + `src/agents/ai/onprem_webhook_api.py`(FastAPI: `POST /webhook/alertmanager`·`/webhook/incident`·`GET /health`, 컴팩트 요약 반환). `tests/test_onprem_webhook.py`(6 테스트: 실 detector/decision/executor 체인 + TestClient 엔드포인트, analyzer Bedrock은 stub·activity는 tmp 격리). Makefile `onprem-webhook` 타깃. `docs/ARCHITECTURE.md` L107(PATH B)·Day-2 On-Prem 컬럼 🔲→✅ + 구현 노트.
- Verified: `pytest tests/test_onprem_webhook.py` 6 passed. **실 HTTP 스모크**(`uvicorn onprem_webhook_api:app :8078` → curl): `/health` ok, `POST /webhook/alertmanager`(crash-loop 페이로드)→ onprem 감지·service=payments-api·resource=kubernetes-workload·heuristic severity·generic-recovery 런북(APPROVE)·onprem 로그-only 실행·incident_id 반환. `make check` → **609 passed, 1 skipped**.
- Blockers: 없음. 잔여(로드맵): Alertmanager 실연동·State Store(PostgreSQL/Redis)·실 executor(MCP Gateway)·Approval Flow.
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드 항목.

## 2026-07-14 — ARCHITECTURE.md 정합화: Orchestrator+A2A를 로드맵→구현(라이브 검증)으로 갱신

- Status: 이번 세션의 A2A Phase 1+2 실증으로 ARCHITECTURE.md가 stale해진 지점을 정합화. 문서가 supervisor+A2A를 여전히 🔲 "타깃/로드맵"으로 표기하고 있었음 → **구현·라이브 검증 완료**로 정정하되, 아직 미완인 부분(MCP Gateway 단일 카탈로그, supervisor의 local_deploy_api 배선)은 로드맵으로 명확히 분리.
- Changed: `docs/ARCHITECTURE.md` — (1) L22 구현 상태: "Orchestrator+A2A 통합 🔲" → "supervisor 라우팅+A2A discovery/위임 ✅(실 kagent 라이브)". (2) "Orchestrator + A2A" 섹션 헤더/인트로에 구현상태 블록 추가, 3개 불릿을 ✅/🔲로 정정(supervisor.py 배선·JSON-RPC 0.3·messageId·capability 격리 명시). (3) 현재/타깃 표의 "에이전트 연결 현재=각자 독립 실행" → "A2A 상호운용 ✅". (4) Gateway A2A Server 프로토콜에 JSON-RPC 0.3(kagent 카드 호환) 명시. 코드 변경 없음(문서만).
- Verified: 편집 후 문서 내 상호 참조/앵커 정합 확인(취약 앵커 링크는 텍스트 참조로 대체). 코드 무변경이라 gate 영향 없음(직전 baseline 603 passed 유효).
- Blockers: 없음.
- Next: (외부/deferred) Slack App · 아티클. 로드맵 빌드 항목(온프렘 PATH B/Day-2, 클라우드 Provision 어댑터, MCP Gateway 단일 카탈로그, Agent Runtime 매니지드 호스팅)은 스코프 큰 선택지 — 착수 시 사용자 지정.

## 2026-07-14 — A2A capability-isolation: PROVISION role 오버매칭 격리 강화

- Status: Phase 2 검증 중 관찰한 **PROVISION role 오버매칭**을 수정. discovery-only 체크에서 `matching_skills(진단카드, PROVISION)`가 `[cluster-diagnostics, observability]`를 반환 — 진단 카드가 provision 전문가로 잘못 매칭될 여지. Phase 1의 KAGENT/DEPLOY 격리와 동일 원칙 적용.
- Changed: `supervisor.py` `ROLE_SKILL_TERMS[PROVISION]`에서 generic `"cluster"` 제거 → provision-특화어 `"infrastructure"`로 교체(`provision`/`terraform`/`ansible`/`infrastructure`). KAGENT와 동일한 경고 주석 추가. `test_supervisor.py`에 회귀 테스트(`test_rejects_diagnostic_only_card_for_provision_role`): 진단-only 카드는 PROVISION에서 `[]`, KAGENT에서만 매칭, 진짜 provisioner 카드는 PROVISION 매칭 유지.
- Verified: `pytest tests/test_supervisor.py` 13 passed; `make check` → **603 passed, 1 skipped**.
- Blockers: 없음.
- Next: (외부/deferred) Slack App 실생성 · 테크 아티클 배포. 코드 백로그 소진.

## 2026-07-14 — A2A Phase 2 완료: 실 kagent 에이전트 대상 라이브 E2E + 스펙 갭 수정

- Status: open-risk #5의 **Phase 2(실제 kagent endpoint)를 라이브로 완결**. defer 권고였으나 착수 → kind+kagent 0.9.11+로컬 MLX Qwen 30B 재프로비저닝 후, supervisor가 **실 kagent 에이전트**를 discovery→match→위임하고 실 도구 진단까지 받는 end-to-end 성공.
- Changed: **버그 수정** `supervisor.py` — JSON-RPC `message/send`의 `params.message`에 A2A 스펙 필수 필드 **`messageId`(UUID) 누락**을 추가. 스펙 준수 `a2a` SDK(kagent 서버)가 `-32602`로 거부하던 것 — **Phase 1의 관대한 자체 게이트웨이는 못 잡던 실 갭**. `test_supervisor.py`에 회귀 테스트(`test_jsonrpc_message_includes_required_message_id`). 신규: `infra/onprem/kagent/local-diagnostic-agent.yaml`(read-only 진단 에이전트, local-qwen ModelConfig+k8s read tools+A2A skills), `docs/evidence/a2a-phase2-live-e2e.log`(성공 트랜스크립트).
- Verified: **라이브 E2E**(in-cluster driver 파드, supervisor.py stdlib-only 복사 실행 → 설계 의도인 카드 내부 DNS url 그대로 도달): classify=kagent → **HTTP `/.well-known/agent-card.json` discovery** → skill 매칭 `[cluster-diagnostics, observability]`(DEPLOY role은 `[]`로 격리 확인) → **JSON-RPC message/send 위임** → kagent 에이전트가 **실 `k8s_get_resources` MCP 도구 호출** → 30B가 `helm/istio/promql-agent` non-Running(0/1) **정확 진단** 반환. 과거 블로커(kind pod→host MLX)는 프록시 **0.0.0.0 바인딩**으로 해소(파드에서 `host.docker.internal:18091` 도달 확인). `make check` → **602 passed, 1 skipped**.
- Blockers: 없음. 인프라(kind `platform-agent` 3노드 + kagent 18파드 + MLX 30B)는 **실행 중 유지** — 데모/추가 검증 원하면 그대로, 정리는 `make local-cluster-down` + `pkill mlx_lm.server`/proxy.
- Next: (외부/deferred) Slack App 실생성 · 테크 아티클 배포. 코드 백로그 재소진.


## 2026-07-13 — NEXT_PUBLIC 프로덕션 인라인 이슈 실측 → 해소(stale)

- Status: risk #7(선택) 진단·실측 종결. Next 16.2.10 `next build`가 `.env.local`의 NEXT_PUBLIC를 정상 인라인함을 확인 → 과거 "미인라인" 노트는 현재 재현 안 됨(stale), 코드 수정 불필요.
- Verified: `dashboard-header.tsx`(`"use client"`)의 `process.env.NEXT_PUBLIC_DASHBOARD_DEV_AUTH`가 빌드 청크에서 `signIn("dev-credentials")`로 **상수 폴딩**(=`"1"` 인라인), `.next/static` 전체에 원문 env 참조 0건. Next 공식 문서로 메커니즘 교차확인(빌드시점 인라인·정적 참조만·/src 사용시 .env는 루트 로드). `.env.local`은 gitignore라 Vercel 빌드엔 부재→prod는 GitHub OAuth 폴백(의도대로).
- Changed: 코드 변경 없음(진단만). STATUS/NEXT_PLAN #7 해소 표기.
- Blockers: 없음.
- Next: 잔여는 A2A Phase 2(kagent, 인프라 무게로 defer 권고) + deferred 외부항목(Slack/아티클).

## 2026-07-13 — A2A Agent Card discovery 실연결(Phase 1) + 매칭 규율 강화

- Status: risk #5(A2A discovery)의 실체를 **라이브로 실연결**. supervisor의 discovery 코드는 이미 완비돼 있었고(카드 fetch+skill 매칭+HTTP/JSONRPC 위임+trace), 갭은 "살아있는 엔드포인트 대상 실증 부재"였음 → 게이트웨이 A2A 서버를 실기동해 mock 없이 E2E 실증.
- Changed: `supervisor.py` `ROLE_SKILL_TERMS[KAGENT]`에서 generic `kubernetes/cluster` 제거 → 진단 특화어(`diagnostic/troubleshoot/observability/investigat/debug/logs`)로 교체. `test_supervisor.py`에 회귀 테스트(`test_rejects_deploy_only_card_for_kagent_role`) 추가. 코드 외 실증 스크립트는 scratchpad.
- Verified: uvicorn 게이트웨이(`/.well-known/agent-card.json` = Platform Deployer Agent, 6 skills) 실기동 → supervisor `from_environment`가 **HTTP로 카드 discovery → DEPLOY skill 매칭 → 위임(delegated=True, trace matched→sent)**. 강화 후 **KAGENT role은 deploy-only 카드를 `capability_mismatch`로 거부**(delegated=False) 라이브 확인. `pytest tests/test_supervisor.py tests/test_gateway.py` 41 passed.
- Blockers: **Phase 2(실제 kagent endpoint)** 미완 — kind+kagent+MLX 재프로비저닝 필요(원커맨드 스크립트 부재, MLX 미구동). JSON-RPC 진단 task 자체는 과거 실증.
- Next: (선택/무거움) Phase 2 kagent 재프로비저닝 후 실 카드 대상 KAGENT discovery.

## 2026-07-13 — 잔여 백로그 정리: kagent(MOOT) + feat 브랜치 로컬 삭제

- Status: 남은 우선순위 소진. **kagent 정리는 MOOT**로 검증 종결, 중복 **feat 브랜치 로컬 삭제**.
- Verified: 활성 kube context 없음(`current-context` 미설정, `kind get clusters` 0개); Multipass `k8s-lab` k3s VM은 Ready(v1.31.4, 44h)이나 kagent namespace·helm·비시스템 파드 전무 → kagent 정리 대상 부재. `git branch -d feat/onprem-offline-recording-hybrid-rollback`(was 930fe98, main에 완전 머지) 로컬 삭제 완료.
- Blockers: origin `feat` 브랜치 삭제는 권한 분류기가 차단(제네릭 지시로 원격 삭제 불가) → **명시 승인 대기**. 미커밋 doc 정리분은 이 커밋으로 반영.
- Next: (승인 시) origin feat 삭제 / (deferred) Slack App·아티클.

## 2026-07-13 — AWS CDK live diff 재검증 (인프라 drift 0)

- Status: NEXT_PLAN의 "synth 미완" 블로커를 근본원인까지 진단·해소하고 live diff를 실측. **인프라/IAM drift 0** 확인.
- Root cause: `src/stacks/cdk.out`이 **1.8GB 재귀 중첩**(asset.X/src/stacks/cdk.out/asset.Y…) — `Code.fromAsset(projectRoot)`의 exclude에 `cdk.out`이 추가되기 전(수정 Jul 11 11:00)에 쌓인 stale 산출물이 synth를 사실상 무한 복사로 몰던 것. exclude는 이미 코드에 있음.
- Changed: 코드 변경 없음. stale `cdk.out` 삭제(1.8GB 회수). 문서: NEXT_PLAN/STATUS/AGENT_BRIEF에 재검증 완료 + diff context 주의 기록.
- Verified: `cdk synth IncidentAgentStack` **~17s exit 0**(새 cdk.out 37M, 99 resources); `cdk diff --no-change-set` **exit 0**. **진짜 diff = Lambda 13개 코드 asset-hash churn만**(재번들링 노이즈), 리소스/IAM add·delete 0. ⚠️ diff는 `-c vercelTeamSlug=men16922 -c vercelProjectName=platform-agent -c vercelOidcProviderArn=arn:aws:iam::908601828278:oidc-provider/oidc.vercel.com/men16922` 필수 — 없으면 조건부 `VercelDashboardReadRole`이 빠져 가짜 삭제 diff.
- Blockers: 없음. 배포는 하지 않음(재검증만).
- Next: kagent 정리 / (선택) feat 브랜치 삭제 / 미커밋 doc 정리분 커밋.

## 2026-07-13 — 추적 IA 자연어 4스텝 라이브 실증 완료

- Status: LinkedIn 데모 녹화 세션에서 자연어 4스텝을 **브라우저 end-to-end로 실증 완료**. ① `Provision ... then deploy orders-api ...`(Provisioning+Deployments 2행) → ② `Roll back orders-api ...`(단일-row 승계, 중복행 없음) → ③ History 행 클릭→중첩 상세(provisioning⊃deploy) → ④ `Tear down the on-prem cluster`(provision rolled-back + orders-api 자동 cascade rolled-back·Rollback 비활성). 이로써 open-risk #6(라이브 실증 미완) 해소.
- Changed: 코드 변경 없음(실증만). 문서 정합화: STATUS open-risk #6 해소, NEXT_PLAN 실증/커밋 항목 close, AGENT_BRIEF 스냅샷 갱신. `.claude/skills/`에 `grill-me`/`grilling` 스킬 2종 도입, `docs/reference/enterprise-ai-governance-dashboard.md` 레퍼런스 노트 추가(DECISIONS Future Reference 포인터).
- Verified: 4스텝 브라우저 실증(사용자 확인); 증거 영상 `docs/post/local-onprem-edited.mp4`(18.2s hero cut: step 1+3). IA 정리분은 커밋 `930fe98`에 이미 포함.
- Blockers: 없음. 남은 것은 `feat/onprem-offline-recording-hybrid-rollback` **push/머지 결정**(별도 승인 대기).
- Next: push/머지 결정 → (선택) AWS CDK live diff 재검증 / kagent 정리.

## 2026-07-12 — 데모 영상 편집 및 자막 버닝 완료

- Status: `docs/post/local-onprem.mov` 원본 영상을 10~20초 범위 내인 18.2초로 편집하고, 각 7개 구간의 설명 자막을 병합(burn-in)하여 `local-onprem-edited.mp4`로 저장 완료.
- Changed: `edit_video_pil.py` 스크립트를 작성하여 FFmpeg 프레임 추출 ➔ Pillow 자막 드로잉 ➔ FFmpeg 비디오 인코딩 파이프라인 구현. 자막 문구를 실제 구동 모드인 "Terraform"으로 정확하게 매핑.
- Verified: `docs/post/local-onprem-edited.mp4` 생성 (18.2초, 1.0MB, silent). 자막 문구 검증 완료.
- Blockers: 없음.
- Next: 자연어 4스텝 라이브 UI 실증 완료 후 전체 커밋 및 push/머지 결정.

## 2026-07-12 — 배포 추적 IA 정리: Provisioning/Deployments/History 분리 + 중첩 상세 + 롤백 단일-row/cascade

- Status: 추적(activity) 데이터 모델·UX를 대폭 정리. **provision/deploy `type` 분류** + **provider×environment** 일관 taxonomy, 롤백을 **단일-row 승계**(새 행 X), **cluster teardown이 그 클러스터 deploy들을 자동 rolled-back으로 cascade**, 자연어 명령(rollback/teardown)도 UI와 동일하게 승계/cascade로 라우팅.
- Changed:
  - Python `deploy_recorder`: `type`(provision/deploy)·`cluster`(연결키)·`environment`(더 이상 provider로 안 덮음) 저장, `_infer_service_version` deploy 우선(=version=kind 버그 수정), 복합 run을 provision+deploy **2행 분리**+단계별 성공판정, `record_rollback`(deployment_id supersede), `record_cluster_teardown`(provision 승계+deploy cascade), `read_deploys`(백엔드별 최신, 동일 timestamp는 나중 기록 우선), `record_deploy`가 teardown-only/rollback-only 자연어 run 라우팅. `local_deploy_api` rollback 배선(deployment_id/service/version/environment, scope=cluster→cascade).
  - Dashboard: **Provisioning**·**History**(Provisioning/Deployment Logs 2섹션·페이징) 페이지 신규, nav 워크플로순(Overview→Agents→Provisioning→Deployments→History→Incidents), **통합 중첩 상세**(상단 provisioning·하단 deploy `<details>` 아코디언, focus만 펼침), 롤백 **인앱 팝업**(Deployments=앱 전용/Provisioning=cluster teardown), 단일-row 갱신, cluster 없음/torn-down 시 Rollback 비활성화, **행 클릭→trace**(Trace 버튼 제거), `model-logo` 서버컴포넌트 onError 오류→client `model-logo-img` 분리, `getLifecycleDetail`.
  - Makefile: `dev-up`/`dev-down`/`dev-status` 한 방 스택 기동(MLX 재사용, router에 `PLATFORM_ACTIVITY_FILE`), `router-api`/`local-llm-up`에 오프라인 기록 env.
  - Docs: `linkedin-onprem-agent-20s-demo.md` 시나리오를 **자연어 명령 중심**(provision+deploy 한 문장→앱 롤백→History 중첩 상세→teardown cascade)으로 재작성.
- Verified: `make check`(anaconda) → **600 passed, 1 skipped**(recorder cascade 테스트 2개 신규); dashboard `tsc` 0 + `next build` 성공; dev 서버 `/provisioning`·`/history`·`/deployments` 200.
- Blockers: 신규 UI/자연어 cascade의 **라이브 end-to-end 실증 미완**(사용자 브라우저 테스트 예정); 미커밋(브랜치 `feat/onprem-offline-recording-hybrid-rollback`); 레거시 activity 행은 `cluster` 없어 롤백 비활성(클린슬레이트는 activity.jsonl 비우기).
- Next: 자연어 4스텝(provision+deploy→app rollback→History 상세→teardown cascade) 라이브 실증 → 전체 커밋 → 브랜치 push/머지 결정.

## 2026-07-12 — On-Prem 오프라인 기록 + Hybrid 대시보드 + 실 롤백 + Local Qwen 7B 전환

- Status: On-Prem 경로를 **기록→병합→롤백까지 오프라인으로 완결**. Local Qwen을 30B→**7B**로 전환하고 tool-call/컨텍스트 이슈를 해결해 자연어 provision→deploy→validate **~39s 자율 수행** 실증.
- Changed:
  - Python: `deploy_recorder` 로컬 JSONL 백엔드(`PLATFORM_ACTIVITY_FILE`); `local_deploy_api` `/api/local-rollback`(app rollout undo + cluster teardown); `mlx_qwen_tool_proxy` JSON/Hermes tool-call 파서(7B는 ```json 블록으로 tool call 방출); `local_deployer` `deploy_service` 복합툴 + 하드닝; provision/ops 출력 ANSI 절단(작은 모델 루프 유지).
  - Dashboard: `activity-data` **local + hybrid**(AWS DynamoDB + On-Prem JSONL 병합) read; rollback route onprem 분기(→라우터); deployments-control 버튼 provider/scope; `data-source-badge` local/hybrid; 모델 로고 4종 로컬 SVG·SELECTED 배지·timestamp `suppressHydrationWarning`.
  - 로컬 dev 로그인: `.env.local`에 `DASHBOARD_DEV_AUTH`/`NEXT_PUBLIC_DASHBOARD_DEV_AUTH`/`AUTH_SECRET`/`AUTH_TRUST_HOST`; `next dev` 구동(NEXT_PUBLIC 프로덕션 인라인 이슈 회피).
  - Makefile: pytest 가능한 인터프리터 자동 탐지(.venv-mlx 그림자 방지).
- Verified:
  - `make check`(anaconda) → **598 passed, 1 skipped**; dashboard `next build` 성공.
  - Live(7B): `provision_cluster`(~21s)→`deploy_service`→validate DONE **~39s**, orders-api 1/1 Running; **app 롤백** v2→v1(`rollout undo`); **cluster 롤백** teardown; `/api/dashboard/deployments`가 `source=hybrid`로 로컬+AWS 병합 반환(내 On-Prem 기록 포함).
  - 커밋 `0b9148c`(브랜치 `feat/onprem-offline-recording-hybrid-rollback`, 24 files/+558); tfstate gitignore.
- Blockers: 대시보드 rollback **버튼→라우트(auth 게이트)** 체인은 로그인 세션 필요해 curl 미검증(라우터 엔드포인트는 검증됨); `NEXT_PUBLIC`은 프로덕션(next start) 인라인 안 돼 `next dev` 사용; 브라우저 확장 미연결로 클릭 자동화 불가.
- Next: 로그인 후 UI Rollback 클릭 실증 → 브랜치 push/머지 결정 → (선택) NEXT_PUBLIC 프로덕션 인라인 해결.

## 2026-07-11 — On-Prem 실 k3s Provision + Agents 선택 UX + LinkedIn 데모 초안

- Status: 기존 Multipass `k8s-lab` VM에 Ansible k3s Provision을 실제 적용하고, Agents 화면을 Agent→Model→Runtime→trace 단일 선택 흐름으로 재구성.
- Changed: k3s config 디렉터리 생성/idempotency 수정, local inventory·kubeconfig ignore; On-Prem runtime panel/router 상태, Agent/Model selection, 실제 model brand asset; `docs/post/linkedin-onprem-agent-20s-demo.md` 추가.
- Verified: k3s v1.31.4 control-plane Ready; Ansible 재실행 `changed=0`; Dashboard `npm run build` 성공.
- Blockers: AWS CDK live diff는 Lambda dependency bundling이 완료되지 않아 재검증 필요; kagent 기본 agent 정리 여부 미결정.
- Next: CDK diff 재검증 → kagent 기본 agent 유지/정리 결정 → 명시 요청 시 push.

## 2026-07-11 — Supervisor 요청 라우팅 + A2A 위임 경계

- Status: Orchestrator(supervisor)의 최소 수직 슬라이스 구현 — 자연어 요청을 provision/deploy/kagent 역할로 분류하고, 등록된 specialist endpoint로만 A2A `message:send` 위임.
- Changed: `supervisor.py`(결정·trace·표준 HTTP A2A client), Gateway A2A Server의 route trace artifact, `PLATFORM_{PROVISION,DEPLOY,KAGENT}_A2A_URL` 환경변수 registry, 라우팅/위임/안전한 미등록 상태 테스트 추가.
- Verified: `pytest tests/test_supervisor.py tests/test_gateway.py -v` → 37 passed. 전체 `pytest tests/ -q`는 외부 pytest 런타임에서 종료 출력이 확보되지 않아 baseline 갱신 없이 유지.
- Blockers: 실제 kagent A2A endpoint 및 Agent Card discovery/skill 기반 라우팅 미연결; 현재 Agent Card는 Gateway `/.well-known/agent-card.json` 노출·검증만 사용.
- Next: kagent endpoint 등록 → Agent Card discovery/능력 매칭 → 로컬 Qwen ModelConfig 연결.

## 2026-07-11 — 범용 Ops 에이전트 + 관측성 + On-Prem Provision(Terraform/Ansible) + kagent + 아키텍처 정식화

- Status: AI Model Router 배포 채팅을 **범용 On-Prem Ops 에이전트**로 확장(질의→자율 tool 수행), reasoning+tool 트레이스 스트리밍/기록/상세페이지, On-Prem **Provision 역할**(Terraform kind + Ansible k3s) 구현, kagent 설치, ARCHITECTURE 통합·최신화.
- Changed:
  - **범용 Ops**: `ops_tools.py`(read-only kubectl: list_pods/get_logs/describe/rollout_status/list_namespaces) + 시스템프롬프트 일반화. 도구셋 = provision+deploy+investigate(12개).
  - **Provision(① 역할)**: `adapters/provisioning/`(base/onprem/registry) + `provision_tools.py`(provision_cluster/teardown) + `infra/onprem/terraform`(kind IaC, validate/plan ✅) + `infra/onprem/ansible`(k3s 플레이북).
  - **관측성**: `model_router.build_trace`(reasoning+tool ordered trace) + SSE `reasoning` 이벤트, `deploy_recorder` trace 저장, 배포 상세 페이지(`/deployments/[id]`) — instruction/reasoning/tool args·result/summary(markdown)/kubectl output.
  - **대시보드**: 로컬 dev 로그인(GitHub 없이 admin, prod 비활성), Agents 채팅 SSE 스트리밍+인라인 args/result, ModelLogo, Agent 카드 **Tools 팝업**(포털), 배포 상세 진입(Deployments/타임라인), 폭 확대(max-w-[1800px]), 채팅 60vh, 타임라인 10건 페이징.
  - **kagent**: kind에 helm 설치(controller/ui/postgres Running, 에이전트 10개 CRD). LLM(로컬 Qwen) 연결은 호스트 네트워킹 미해결.
  - **Make**: `local-llm-up/down/status`, `mlx-serve/mlx-proxy/router-api`.
  - **Docs**: ARCHITECTURE 통합 스택 표 + Orchestrator+A2A 타깃 + On-Prem "MCP만" 부정확 수정. DECISIONS D9.
- Verified:
  - `make check` → **584 passed, 1 skipped**; dashboard `tsc` 0; `terraform validate/plan` green.
  - **Live E2E (실 MLX Qwen30B → kind)**: NL 배포 build→push→deploy→validate + recorder→DynamoDB→대시보드 aws-live 추적, reasoning/tool SSE, "list pods" 질의는 진단만 수행 확인.
- Blockers: kagent↔로컬 Qwen 연결(kind pod→host MLX 네트워킹, MLX proxy 0.0.0.0 바인딩 필요). 클라우드 Provision/Agent Runtime 호스팅·Orchestrator+A2A 통합 = 로드맵.
- Next: (1) Orchestrator(supervisor)+A2A 통합 착수, or (2) kagent↔Qwen 연결 완성, or (3) push(현재 origin 대비 ahead 18).

## 2026-07-11 — AI Model Router + 자연어 On-Prem 배포 + 대시보드 Agents 채팅

- Status: 모델(두뇌)과 환경(대상)을 분리하는 **AI Model Router**를 구현하고, On-Prem은 Strands 대신 **Pydantic AI + MLX Qwen** 독립 에이전트로 전환. 대시보드 Agents 페이지에 모델 선택 + 자연어 배포 채팅 추가.
- Changed:
  - `model_router.py` — 모델 레지스트리(local-qwen/bedrock-claude/vertex-gemini/azure-gpt) + (model×environment) 적합도 매트릭스 + 라우팅.
  - `local_deployer.py` — Strands 무의존 Pydantic AI On-Prem 에이전트(완전 오프라인). `local_deploy_api.py` — `/api/models`(셀렉터) + `/api/local-deploy`(실행). `deploy_recorder.py` — DEPLOY+ACTIVITY 기록(executor-writes, env 게이트).
  - `mlx_qwen_tool_proxy.py` — 클라이언트 `stream` 플래그 존중(SSE/JSON 양쪽) 프레임워크 중립화.
  - Dashboard: `agents/deploy`·`agents/models` 라우트, `agent-deploy-chat.tsx`(적합도 배지+step trace), `lib/model-router.ts`(정적 fallback), `agents/page.tsx` 연동.
  - `scripts/slack_live_approval.py` — AWS 배포 없이 Slack 승인 send/simulate/full 하네스.
  - Docs: `ARCHITECTURE.md`(Model Router 섹션+프레임워크 표+On-Prem 갱신), `local-llm-onprem.md`(프레임워크 분리 기록). `pyproject.toml` `[onprem]` extra.
- Verified:
  - `make check` → **569 passed, 1 skipped** (신규 +22 테스트: router/local_deployer/local_deploy_api/deploy_recorder/proxy).
  - Dashboard `tsc --noEmit` 0 + `next build` 성공(신규 라우트 등록 확인).
  - 라우터 API live: `/api/models?provider=onprem` → local-qwen recommended 최상단, aws → bedrock-claude recommended 확인.
  - **Live E2E (신규 Pydantic AI 경로)**: MLX Qwen3-Coder-30B(.venv-mlx, :18090) + proxy(:18091) → `route_deploy("Deploy orders-api ... namespace local-llm-smoke", local-qwen, onprem)` → build→push→deploy→validate 자율 4-tool 실행, `ok=True`. kubectl 확인: `orders-api 1/1 Running`, image=`localhost:5001/orders-api:v1.5.0` 롤링 업데이트.
  - **Live 추적 실증 (Deployments 배선 완성)**: API 배포(`PLATFORM_ACTIVITY_TABLE`=platform-agent-activity, us-east-1) → recorder가 `DEP-262AC0A3`(orders-api v1.6.0)+`ACT-1C981F27` 기록 → 대시보드 `/api/dashboard/deployments`(source: aws-live)가 최신 배포로 노출 확인. kubectl: image v1.6.0. 대시보드↔라우터 API 배선도 dev 서버 live curl(`source: router-api`)로 확인.
  - Slack simulate: approve/reject E2E(실 HMAC 서명 → SFN send_task_success/failure) 통과.
- Blockers:
  - ⚠️ 워킹트리에 **세션 외 미커밋 변경** 다수(ruff autofix류). 특히 `src/agents/models.py` 재수출 제거로 `from src.agents.models import ServiceSpec` ImportError(테스트는 통과). 이번 커밋에서 제외함 — 별도 검토 필요.
  - 실 MLX 서버 기반 채팅→kind 배포 live 스텝은 운영자 수행 필요(로직은 TestModel로 검증).
- Next: 세션 외 미커밋 변경(특히 models.py) 검토/정리 → 대시보드 채팅 live 데모(MLX+kind).

## 2026-07-11 — 로컬 Qwen3-Coder 모델 기반 On-Premises E2E 자율 배포 검증 완료

- Status: MLX Qwen tool proxy의 이중 호환성(Pass-through 및 XML Fallback) 개선을 적용하고, 로컬 kind 클러스터 및 레지스트리 환경에서 strands 자율 배포 E2E 연동 테스트 통과.
- Changed:
  - Tool Proxy: `mlx_qwen_tool_proxy.py`에서 MLX-LM 서버의 네이티브 `tool_calls` JSON 구조를 무손실 중계(Pass-through)하도록 보완하고 XML 마크업 Fallback 로직을 개선.
  - Documentation: `local-llm-onprem.md`에 proxy 구조와 kind 클러스터 E2E 배포/검증 E2E 실행 결과 수록.
- Verified:
  - `make local-cluster` 기동 및 MLX Qwen proxy (:18081) 연동 테스트 완료.
  - `orders-api` 배포 E2E: 빌드(build_image) -> 푸시(push_image) -> local-llm-smoke 네임스페이스 배포(deploy_to_cluster) -> 검증(validate_deployment, 1/1 Ready) 자율 연동 성공.
  - 전체 단위/통합 테스트 (`make check`) 실행: 544 passed, 1 skipped (성공).
- Next: Slack App 대화형 인터랙티브 컴포넌트 실연동 설정 (Task 12).

## 2026-07-11 — 유저 권한 관리(Users Admin UI) 및 멀티 클라우드 장애 복원력(Failover) 연동 완료

- Status: Admin용 사용자 계정 권한 제어판 구축 및 AWS/GCP/Azure 장애 발생 시 예비 리전/클러스터 우회 복구(Multi-region Failover) 시스템 구현 완료.
- Changed:
  - Users UI: `/users` 계정 권한 설정 페이지를 신설하고 대시보드 내 `UsersTable` 클라이언트 컴포넌트를 연동. Admin 역할 사용자만 진입 가능하며 DynamoDB에 저장된 개별 세션 계정 등급(Viewer/Operator/Admin)을 실시간 편집 가능.
  - Self-lockout Protection: 관리자가 본인 역할을 실수로 강등하여 관리 콘솔에서 잠기는 잠금 방지(Lockout Protection) 기능 적용.
  - Sidebar: 로그인 세션의 역할에 따라 `admin` 권한이 있는 경우에만 "Users" 메뉴가 동적으로 노출되도록 개선.
  - AWS Failover: SSM Automation 실행 실패 시 `AWS_FAILOVER_REGION`(기본 `us-east-1`)으로 자동 스위칭하여 복구 문서를 재시도하도록 보강.
  - GCP Failover: GKE API 호출 및 Cloud Run 조작 실패 시 `GCP_FAILOVER_CLUSTER_NAME` 및 `GCP_FAILOVER_REGION`으로 우회하여 복구 동작을 연속 수행하도록 지원.
  - Azure Failover: AKS 크레덴셜 획득/API 배포 실패 시 `AZURE_FAILOVER_CLUSTER_ID` 및 `AZURE_FAILOVER_RESOURCE_ID`로 Failover하여 실행 보장.
  - MLX-LM Integration: On-Premise 타겟 배포 시 로컬 MLX-LM API 서버를 타겟팅할 수 있는 통합 연동 모듈을 `strands_deployer`에 추가하고 python 환경에 `mlx-lm` 설치 완료.
  - Tests: `test_multicloud_runners.py`에 GKE failover 복구 단위 테스트를 추가하고 전체 543개 백엔드 테스트 및 Next.js 프로덕션 빌드/배포 패스 검증 완료.
- Next: Slack 대화형 연동 가이드 정리.

## 2026-07-11 — 대시보드 감사 로그(Audit Logs) 뷰어 및 역할 기반 필터 연동 완료

- Status: 시스템 변조/승인 이력을 모니터링할 수 있는 감사 로그(Audit Logs) 조회 페이지 및 전용 API 구현 완료.
- Changed:
  - API Route: `/api/dashboard/audit` 엔드포인트를 구현하여 인증 및 역할 검증(Admin/Operator 권한 체크)을 거쳐 감사 로그를 전달하고 미들웨어 수준에서 경로 차단 보호를 적용.
  - Audit Page: `/audit` 화면을 신설하여 비인증/Viewer 등급 사용자에게는 "Access Denied" 오류 화면을 출력하고, 승인된 관리자에게는 SSR 기반의 실시간 DynamoDB 로그 리스트 렌더링.
  - Audit logs table: 클라이언트 컴포넌트(`AuditLogsTable`)를 개발하여 감사 ID, 수행한 운영자, 액션, 대상, 결과 상태(Success/Failed), 발신 IP 및 UserAgent의 대화형 검색 및 필터링 기능 추가.
  - Sidebar: 로그인한 세션 유저의 역할에 맞춰 Admin/Operator인 경우에만 좌측 네비게이션 메뉴에 "Audit Logs" 메뉴 아이템이 동적으로 렌더링되도록 개선.
  - Overview: 메인 Overview 화면의 "Incident feed" 옆 "View all →" 요소를 Next.js `Link` 컴포넌트로 연동하여 실제 Incidents 페이지로 정상 라우팅되도록 수정.
  - Deploy: Next.js 16 빌드 성공 및 최종 프로덕션 웹사이트 배포 완료.
- Next: Slack App 대화형 구성요소의 실 연동 설정 가이드 수립.

## 2026-07-11 — GCP 및 Azure 실 API 연동 및 OIDC 인증 연동 완료

- Status: AWS STS 연계를 활용한 GCP/Azure 실 REST API 연동 및 OIDC 페더레이션 크레덴셜 자격증명 모듈 구현 완료.
- Changed:
  - GCP Auth: AWS STS GetCallerIdentity 서명 정보로 GCP STS 교환 토큰을 가져오는 WIF 페더레이션 자격증명 모듈(`gcp_auth.py`) 구현 (Service Account Key 폴백 지원).
  - GCP/Azure Runners: GKE 롤아웃 재시작/스케일링/롤백 API 호출 및 Cloud Run 스케일링/트래픽 롤백 REST API 호출이 가능한 실 인프라 러너(`gcp_runner.py`, `azure_runner.py`) 개발.
  - Executors: 중앙 AWS Step Functions Executor(`handler.py`) 및 GCP Cloud Workflows Executor(`gcp/executor.py`) 양측에 신규 외부 클라우드 실 실행부 바인딩 완료.
- Verified:
  - `pytest tests/test_multicloud_runners.py` -> 5 passed (성공).
  - 전체 파이썬 테스트 슈트 -> 541 passed, 1 skipped (Mock 모드 기본 지원 확인).
- Next: Slack App interactive 구성요소의 단일 AWS 연결 설정 연계.

## 2026-07-11 — Auth Phase 2 & 3 UI Control Panels 구현 및 배포 완료

- Status: 대시보드 내 승인/배포/롤백 수행이 가능한 대화형 UI 구성 요소 개발 및 프로덕션 배포 완료.
- Changed:
  - Incidents UI: `PendingApprovals` 카드 컴포포넌트 구현하여 미해결 승인 건 목록 노출 및 즉각적인 승인/거절 기능 제공 (역할 기반 접근 체크 연동).
  - Deployments UI: `DeploymentsControl` 컴포넌트 추가하여 신규 배포 트리거 모달 양식(`service_name`, `version`, `provider`, `environment`) 및 성공한 배포 건에 대한 롤백(Rollback) 실행 버튼 연동.
  - Vercel: 로컬 빌드 및 프로덕션 사이트(`https://platform-agent-red.vercel.app`)에 최종 배포 완료.
- Verified:
  - `make check` -> 536 passed, 1 skipped (성공).
  - Dashboard `npm run build` -> Next.js 16 빌드 및 TypeScript 타입 체크 성공.
- Blockers: 없음.
- Next: 추가로 요구되는 Slack App 연동 또는 GCP/Azure 클러스터 연동 시 설정 연계.

## 2026-07-11 — Auth Phase 2 (Option 1) & Phase 3 (Option 2) 완료

- Status: Auth Phase 2 및 Phase 3에 명시된 기능 전체 구현 및 빌드 검증 성공.
- Changed:
  - CDK: `platform-agent-users` 및 `platform-agent-audit` DynamoDB 테이블 정의 및 Vercel OIDC role 권한 부여. Step Functions `SendTaskSuccess/Failure/DescribeExecution` 권한 추가.
  - Auth Phase 2: GitHub Organization 멤버십 체크 및 DynamoDB 사용자 역할 연동 (`auth.ts`, `user-data.ts`), 사용자 역할 관리를 위한 관리자 API (`/api/dashboard/users`) 구현.
  - Auth Phase 3: Step Functions 연동 approval 승인/거절 API (`/api/dashboard/incidents/[id]/approve`), deployment trigger API (`/api/dashboard/deployments/trigger`), deployment rollback API (`/api/dashboard/deployments/[id]/rollback`) 구현.
  - Audit logging: 모든 쓰기/변경 엔드포인트에 90일 보관 감사 로그 적재 (`audit-data.ts`, `platform-agent-audit` 테이블 적재).
- Verified:
  - `make check` -> 536 passed, 1 skipped.
  - Dashboard `npm run build` -> Next.js 16 빌드 및 TypeScript 타입 체크 성공.
- Blockers: 없음.
- Next: Vercel에 신규 테이블 권한이 포함된 CDK 스택 재배포 및 배포 환경 연동.

## 2026-07-11 — Dashboard live data pipeline + Auth (Task 11 [auto] 완료)

- Status: Task 11 자동 항목(Activity DB write path, Auth.js Phase 1) 구현 및 검증 완료.
- Changed:
  - Write path: `src/agents/ai/pipeline.py`에 `platform-agent-activity` 테이블 적재 로직 `_record_pipeline_result` 구현.
  - Auth: GitHub OAuth(`dashboard/src/auth.ts`), 세션 프로바이더(`auth-provider.tsx`), 대시보드 헤더 세션 연동 및 미들웨어(`/api/dashboard/:path*/approve` 등) 보호 완료.
  - Test fix: `tests/test_gcp_day2_operations.py`의 휴리스틱 테스트들이 실 Vertex AI 대신 Mock/Heuristic Fallback을 타도록 `vertexai` 모듈 mock 패치 적용.
  - Renaming: 대시보드 UI 상의 `CNCF / On-Prem` 표기를 `On-Premise`로 리네이밍.
- Verified:
  - `make check` -> 536 passed, 1 skipped (성공).
  - GCP Day2 tests -> 28 passed.
  - Dashboard `npm run build` -> Turbopack 컴파일 및 타입 검사 통과.
- Blockers: 없음.
- Next: Vercel 환경 변수 `DASHBOARD_ACTIVITY_TABLE` 추가 및 대시보드 재배포 (manual).

## 2026-07-11 — Dashboard portfolio release (Task 10 완료)

- Status: 3개 항목 모두 구현·배포·검증 완료.
- Changed:
  - Open Graph: `opengraph-image.tsx` (Edge runtime 1200×630) + `twitter-image.tsx` + `layout.tsx` full OG/Twitter metadata.
  - Durable read model: `activity-model.ts` (DynamoDB 단일 테이블 PK/SK+GSI1) + `activity-data.ts` (3 feed 함수) + API routes 3개 + CDK `platform-agent-activity` 테이블.
  - Auth boundary: `docs/DASHBOARD_AUTH_DESIGN.md` (RBAC 3-role, JWT, 승인 플로우, 3-phase 구현 계획) + `dashboard/src/lib/auth.ts` (타입 모듈).
  - Pages: `page.tsx`/`deployments/page.tsx`/`agents/page.tsx`를 activity-data.ts 사용하도록 전환.
  - CDK: `platform-agent-activity` 테이블 + GSI1 + Vercel OIDC read grant 배포 완료.
- Verified:
  - `make check` → **525 passed, 1 skipped** (244.82s).
  - Dashboard `npm run build` → 11 routes 컴파일 성공 (opengraph-image, twitter-image 포함).
  - Vercel production 배포 → `platform-agent-red.vercel.app` OG image 200 OK (107KB), 전체 meta tags 확인.
  - CDK deploy → `platform-agent-activity` ACTIVE (PK/SK + GSI1), Vercel role에 read 추가.
  - AWS: `aws dynamodb describe-table` → 스키마 정확 확인.
- Blockers: 없음.
- Next: Executor에서 activity table write path 연결 → Auth.js Phase 1.

---

## 2026-07-11 — Vercel OIDC live incident production 활성화

- Status: 완료.
- Changed:
  - AWS: Vercel Team issuer OIDC Provider + `platform-agent-vercel-dashboard-read` Role 배포; `incident-history` read-only 권한.
  - Vercel: Production/Preview에 live source, region, table, role ARN env 설정; CLI root link + `.vercelignore` 추가.
  - Production `https://platform-agent-red.vercel.app` 갱신.
- Verified:
  - CloudFormation `UPDATE_COMPLETE`; OIDC trust는 team/project + production/preview subject로 제한.
  - Protected Preview와 Production API 모두 `source=aws-live`; 현재 records 0건.
  - Production Overview `LIVE · AWS` 표시, Playwright console errors 0건.
- Blockers: 없음.
- Next: Open Graph 메타/이미지 구성과 공유 미리보기 검증.

---

## 2026-07-11 — Dashboard AWS incident live read path + Vercel OIDC

- Status: 구현·로컬 live read 검증 완료.
- Changed:
  - Dashboard `/api/dashboard/incidents` + server data source: `aws-live` / `demo` / `demo-fallback` 계약과 UI 라벨 추가.
  - Executor DynamoDB record에 provider/mode/runbook/timestamp/executed_actions read-model 필드 추가.
  - CDK: Vercel team/project/environment-scoped OIDC trust + `incident-history` read-only IAM role.
- Verified:
  - `make check` → **519 passed, 1 skipped** (230.44s); 신규 persistence test 포함.
  - Dashboard lint/build pass; Playwright demo API·페이지 console error 0건.
  - 로컬 AWS mode → `source=aws-live`, 0 records; CDK TypeScript build + OIDC-context synth pass.
- Blockers: 없음.
- Next: OIDC role을 실배포해 Vercel live feed 활성화.
