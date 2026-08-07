# PROGRESS_LOG Archive — August 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 8월 이력입니다. 최신이 위.

---

## 2026-08-02 — 결정 3: 선택지가 둘이 아니라 셋이었다 (gate 1607→1608)

- Status: 마지막 사용자 게이트(결정 3 = Capsule `limitRanges` 이관 경로)를 조사 → 승인 →
  라이브 검증 → 실행. **다섯 번째로 전제가 깨졌다** — 이번엔 **선택지 개수**였다.
- Verified(조사): 네 문서가 두 갈래(`GlobalTenantResource`=D30 위반 / `TenantResource`=새
  SA+RBAC)만 놓고 "둘 다 비싸다"고 적었는데, **같은 증거 로그 26행이 세 번째 답을 이미 적어
  두었다**: *"`networkPolicies`는 우리에게 해당 없음 — 이 레포는 Tenant spec 대신 객체를 직접
  렌더한다."* 같은 릴리스에 폐기된 형제 필드다. `LimitRange`는 **네임스페이스 스코프**라 D30
  무관, **새 권한 표면도 없다** — `TenantResource`가 SA를 요구하는 건 **Capsule이 대신 쓰기
  때문**이고 직접 쓰면 대리인이 없다.
- Verified(라이브 kind, 3단): ①`spec.limitRanges` 제거 → **Capsule이 자기 LimitRange 4개를
  회수**(globex 것은 유지 = 중복 없음) ②없는 상태에서 limits 없는 파드 → `must specify
  limits.cpu for: c` **Forbidden** — 애드온 values 4종 중 limits를 두는 게 **하나도 없어**
  전 워크로드가 여기 의존하고, 그 거부는 **Argo가 Synced로 보이는**(Risk 8) 자리에서 난다
  ③직접 렌더 후 다시 통과하고, Capsule이 `managed-by` 라벨을 찍었음에도 **컨트롤러 재시작
  전체 리싱크를 견딘다**(8회 샘플 120초, 5/5 생존). 부수: apply stderr **0바이트** — 폐기
  경고 2→0.
- Changed: `spec.limitRanges` 제거 + `render_limit_ranges()` 추가(`render_tenancy`가 Capsule
  Tenant를 낼 때만 방출 — `limits.*` 쿼터가 있을 때가 정확히 그때다) · 가드 2종(하나는
  **파생**: 쿼터가 `limits.`를 선언하면 그 렌더의 **모든** 네임스페이스가 기본값을 가져야 한다,
  나중에 추가될 ns까지 잡힌다) · **스테일 픽스처 라벨링**(`CAPSULE_WARNINGS`는 이제 클러스터가
  만들지 않는 stderr다 — 조용히 갱신하지 않고 HISTORICAL로 명시).
- Verified: `make check` **1608**(+1). 반증 2건 개별 red. ruff 변경 파일 clean. 증거
  `docs/evidence/capsule-limitranges-direct.log`, 조사
  `docs/plans/2026-08-02-capsule-limitranges-path.md`, 결정 **D41**.
- Blockers: 없음. 라이브 변경은 로컬 kind에 국한(테넌트 2개 재적용 + 프로브 파드 정리 완료).
- 품질 메모: **질문이 주는 선택지를 세지 말 것.** D40은 "막는 게 하나"라던 게 넷이었고,
  이번엔 "선택지가 둘"이라던 게 셋이었다. 둘 다 **답이 이미 레포 안에** 있었다 — 이번 것은
  같은 파일 40행 위에. 그리고 **폐기됐다고 사문화된 건 아니다**: 이 필드는 쿼터를 admission
  요구로 바꾸는 축이었고, 없으면 조용히가 아니라 **Forbidden**으로 깨지는데 그 소리가 들리는
  곳이 하필 Argo가 Synced를 보여 주는 자리였다.
- Next: **사용자 게이트 전부 닫힘.** 남은 건 승인 3건 + Phase 4/5.

## 2026-08-01 — 결정 4: 승격 도구가 승격을 못 한다 (gate 1605→1607)

- Status: 브리프의 ⓪순위(결정 4 = k3s를 proven 기판에)를 조사 → 사용자 승인(옵션 C) → 실행.
  **네 번째로 전제가 깨졌다** — 이번엔 **막는 것이 하나가 아니었고**, 기록된 하나는 가장 먼저
  걸리지도 않았다.
- Verified(조사): 네 문서가 반복하던 "k3s-lab에 피어 테넌트가 없다"는 **참이지만 구속력이
  없었다**. 실제 프로브 실행 → `acme/prod has 1 namespace(s); the same-tenant leg needs two`
  로 **피어를 보기 전에** 멈춘다(애드온 1개 = 네임스페이스 1개). 임시 레지스트리로 ①②를
  제거해도 ③에서 멈춘다: `network_policies_apply_to(acme,'prod')=False` — 프로브가 proven
  집합을 전제하고 그 집합을 정하는 게 프로브다. **승격하려면 먼저 승격해야 한다**(kind가
  통과한 건 이미 안에 있어서고, 실제로 한 건 승격이 아니라 회귀 테스트). ④ 라이브 k8s-lab
  (20d): 네임스페이스 4개(전부 기본), netpol 0, Capsule·Flux CRD 없음, kube-system 밖 파드 0,
  `acme-prod-*` **한 번도 존재한 적 없음**. 비용도 반대로 적혀 있었다 — **이 클러스터를 보는
  컨트롤러가 없어 레지스트리 편집은 아무것도 프로비저닝하지 않는다**. 즉 오늘 넣으면 **보호
  대상이 0**이다.
- Changed(승인된 옵션 C): 집합은 `{"kind"}` 유지 · **닫는 이유를 사실로 교체**(tenancy.py
  주석 · STATUS Risk 5 · NEXT_PLAN 결정 4/잔여 · 증거 로그 FOLLOW-UP) · **D40** ·
  새 가드 `tests/test_substrate_promotion_reachable.py`(**멤버십 주장은 현재 레지스트리로
  반증 가능해야 한다** + 순환을 코드에 고정) · 조사 문서
  `docs/plans/2026-08-01-k3s-proven-substrate.md`.
- Verified: `make check` **1607**(+2). 반증 2건 개별 red — k3s를 넣으면 `'k3s' is claimed
  PROVEN, but no tenant/env on it can be run ... acme/prod: 1 namespace(s)`, globex를 다른
  클러스터로 옮기면 kind가 red. 반증 1은 **두 번째 가드까지** red(미증명 기판이 사라지면
  가드를 약화하지 말고 폐기하라는 신호). ruff: 변경 파일 clean.
- Blockers: 없음. **클러스터 변경 0건**(읽기만).
- 품질 메모: M13(**소비자 없는 필드**) → D38(**생산자 없는 메커니즘**) → D39(**사용처 없는
  예외**) → D40(**도달 불가능한 검증기**). 네 번째가 가장 은밀했다 — 프로브는 잘 쓰였고 4개
  주장이 전부 반증 가능한데 **자기가 판정해야 할 대상에는 절대 못 닿는다**. 넷 다 테스트는
  초록이었다. 그리고 **부정확한 근거가 네 파일에 복사돼 3일을 살았다** — D39가 "예외의 근거를
  코드로 확인하라"였다면 이건 **"게이트의 근거는 측정으로 확인하라"**다. 한 번만 돌려 봤으면
  첫 줄에서 드러났다.
- Next: 잔여는 **결정 1건(3: Capsule `limitRanges`)** + 승인 3건. 그 뒤 Phase 4/5.
