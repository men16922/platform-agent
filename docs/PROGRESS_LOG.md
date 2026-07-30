# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-31

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

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
