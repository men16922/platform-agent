# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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
