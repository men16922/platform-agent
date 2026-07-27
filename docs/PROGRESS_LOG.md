# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-28

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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
