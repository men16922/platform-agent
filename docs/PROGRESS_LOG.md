# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-31

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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
