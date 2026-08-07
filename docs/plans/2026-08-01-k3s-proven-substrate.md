# 결정 4 조사 — k3s를 `PROVEN_ENFORCING_SUBSTRATES`에 넣을 것인가

조사일: 2026-08-01 · gate 1605 기준 · **코드 변경 없음(조사만)**

> 결론 요약: **질문이 틀렸다.** 브리프는 "막는 건 하나(피어 테넌트 부재)이고
> globex/prod를 만들지 말지가 질문의 전부"라고 적어 두었다. 측정해 보니 **막는 것은 넷**이고,
> 브리프가 지목한 것은 **가장 먼저 걸리는 것도 아니고 결정적인 것도 아니다**.
> 그리고 그 아래에 **순환 게이트**가 있다 — 이 프로브는 구조적으로 **새 기판을 승격시킬 수 없다**.

---

## 1. 기록된 근거 vs 측정된 사실

`src/agents/platform/tenancy.py:83`, `docs/evidence/k3s-netpol-enforcement.log:75`,
`STATUS` Risk 5, `NEXT_PLAN` 결정 4가 모두 같은 한 문장을 반복한다:

> "`verify_tenant_isolation.py`는 k3s-lab에 **피어 테넌트가 없어** 못 돈다."

참이지만 **구속력 있는 이유가 아니다**. 실제로 돌려 본 결과:

```
$ python scripts/verify_tenant_isolation.py --tenant acme --env prod \
      --peer-tenant globex --peer-env prod
ERROR: acme/prod has 1 namespace(s); the same-tenant leg needs two
```

피어를 언급하기도 전에 멈춘다.

## 2. 블로커는 넷이고, 순서가 있다

| # | 블로커 | 어디서 | 문서에 기록됨? |
|---|--------|--------|----------------|
| 1 | **acme/prod는 네임스페이스가 1개** (애드온이 `observability` 하나) — same-tenant leg는 2개를 요구 | `verify_tenant_isolation.py:239` | ❌ 어디에도 없음 |
| 2 | globex에 `prod` env 없음 (dev/kind 하나뿐) | 같은 파일 `:246` | ✅ 이것만 기록됨 |
| 3 | **순환**: `network_policies_apply_to(acme,'prod') = False` — k3s가 proven이 아니라서 프로브가 "검증할 게 없다"며 exit 2. 동시에 `render_tenancy`도 정책을 emit하지 않아 클러스터에 붙일 정책 자체가 없다 | 같은 파일 `:250` + `tenancy.py:418` | ❌ |
| 4 | **k3s-lab에는 테넌시 실체가 0** — Capsule CRD 없음, Flux 없음, NetworkPolicy 0개, kube-system 밖 파드 0개, `acme-prod-*` 네임스페이스 **존재하지 않음** | 라이브 확인 | ❌ |

**1·2를 제거해도 3에서 멈춘다** (임시 레지스트리로 측정):

```
blocker1 targets(acme/prod) = ['acme-prod-logging', 'acme-prod-observability'] -> len>=2 ? True
blocker2 peers(globex/prod) = ['globex-prod-observability']                    -> non-empty ? True
blocker3 network_policies_apply_to(acme,'prod') = False
=> 'no NetworkPolicy is rendered for acme/prod (unproven substrate)' 로 exit 2
```

### 3번이 핵심이다 — 승격 도구가 승격을 못 한다

프로브는 **proven 집합에 이미 들어 있는 기판에서만** 돈다. 그런데 이 프로브의 존재 이유는
**기판을 proven 집합에 넣을지 판단하는 것**이다. 즉 **새 기판을 승격시키려면 먼저 승격시켜야
한다.** kind가 통과할 수 있었던 건 kind가 이미 안에 있었기 때문이고, 프로브가 실제로 한 일은
**승격이 아니라 이미 승격된 것의 회귀 테스트**였다.

이건 최근 세 층과 같은 결함의 **네 번째** 얼굴이다:

- M13 = **소비자 없는 필드**
- D38 = **생산자 없는 메커니즘**
- D39 = **사용처 없는 예외**
- **결정 4 = 도달 불가능한 검증기** — 잘 쓰였고, 4개 주장을 단언하고, 반증 가능하게 설계됐고,
  **자기가 판정해야 할 대상에는 절대 못 닿는다.** 그리고 테스트는 내내 초록이다.

## 3. 비용도 기록과 다르다

브리프: "globex/prod를 만들면 **실 네임스페이스·쿼터·애드온이 프로비저닝**되므로 인프라 결정".

측정: **k3s-lab에는 아무것도 reconcile하지 않는다.** Flux가 없고(`delivery: flux`는 선언뿐),
Capsule도 없다. 레지스트리는 git 파일이고, 이 클러스터를 보는 컨트롤러가 없다.
**레지스트리 편집만으로는 아무것도 프로비저닝되지 않는다.**

역으로 **acme/prod 자체가 이미 실체 없는 선언**이다 — 20일 된 클러스터에 그 네임스페이스는
한 번도 존재한 적이 없다. (거짓 주장을 만들고 있지는 않다: `phase2-managed-and-dr.log:70`이
"acme/prod: not checked — lives on k3s-lab"이라고 정직하게 적어 두었고, 대시보드 2축 상태는
**push 전용**(D28)이라 푸시가 없으면 없는 것으로 보인다.)

VM 실측: `k8s-lab` 2 vCPU / 3.8GiB RAM / 디스크 9.6GiB 중 **5.8GiB 사용(여유 3.8GiB)**,
k3s v1.31.4, 노드 1개, 20일 가동. kube-prometheus-stack 두 벌은 여기 안 맞는다.

## 4. 그래서 지금 이 결정의 실질 가치는?

k3s를 proven에 넣으면 `render_tenancy`가 acme/prod에 NetworkPolicy를 emit한다.
**그 네임스페이스에는 워크로드가 0이고 네임스페이스 자체가 없다.** 즉 오늘 얻는 보호는 0이고,
가치는 전부 **미래 가치**(언젠가 k3s에 뭔가 실제로 돌 때)다.

## 5. 선택지

### A. 프로브에 후보-기판 경로를 연다 (순환을 깬다) + 최소 적용
`--candidate-substrate` 류의 명시적 플래그로 proven 검사만 우회해 **실제 shipped 정책 shape**을
렌더·적용하고 4개 주장을 돌린 뒤 정리. 추가로 레지스트리에 acme/prod 두 번째 애드온 + globex/prod
필요, 그리고 k3s-lab에 **네임스페이스+NetworkPolicy만** 적용(Helm 차트·Capsule 불필요 —
프로브는 자체 agnhost 파드만 쓴다). 되돌리기 = `kubectl delete ns`. 클라우드 비용 0.
- 대가: 레지스트리에 **또 실체 없는 선언 2건**이 늘어난다(loki·globex/prod, 아무도 설치 안 함).
  Capsule 부재라 적용 상태가 shipped 상태와 다르다(쿼터 미집행) — netpol 시맨틱엔 무관하지만
  "실제 것을 테스트했다"는 주장은 좁아진다.

### B. k3s-lab을 진짜로 세운다 (Capsule + Flux + 애드온) 후 승격
가장 높은 충실도. 2 vCPU/3.8GiB/여유 3.8GiB에 kube-prometheus-stack을 얹는 게 현실적인지가
관건이고, 사실상 Phase 1b를 이 클러스터로 확장하는 별도 작업이다.

### C. 결정 4를 "지금은 아니다"로 **닫고**, 기록을 사실로 고치고, 순환을 가드로 고정 ← 추천
k3s는 proven에 넣지 않는다. 단, **닫는 이유를 바꾼다**: "피어 테넌트가 없어서"(부정확)가 아니라
①**승격 도구가 구조적으로 승격을 못 한다**(순환) ②**이 결정이 보호할 워크로드가 0이다**.
- 고칠 곳: `tenancy.py:71-88` 주석 · `STATUS` Risk 5 · `NEXT_PLAN` 결정 4 · 증거 로그에 후속 노트.
- 새 가드: `PROVEN_ENFORCING_SUBSTRATES`의 승격 경로가 **도달 가능한지** 단언하는 테스트
  (D39의 `test_carveout_consumers_exist.py`, D38의 `test_scope_producer_reachability`와 같은 계열).
  "이 집합에 뭔가를 넣으려면 어떤 명령이 그것을 반증할 수 있어야 한다"를 코드로 고정한다.
- 되돌릴 조건: **k3s-lab에 실제 워크로드가 서면** 즉시 재개(그때는 A가 싸다).

## 6. 추천

**C.** 근거: 오늘 A/B가 사는 것은 **미래 가치뿐**인데, A는 레지스트리의 진실성을 깎고 B는
별도 인프라 작업이다. 반대로 **지금 잘못된 것은 기록 자체**다 — 네 곳이 구속력 없는 이유를
반복하고 있고, 그 아래 순환은 아무 데도 안 적혀 있다. 이 레포의 규칙("있는 보증을 과대 해석하지
말 것", "아무도 돌릴 수 없는 경계가 실패 모드다")이 정확히 가리키는 처치다.

**A는 언제 여는가**: k3s-lab에 뭔가 실제로 배포되는 순간. 그때는 블로커 4가 자연히 풀리고,
남는 건 순환(3)뿐인데 C에서 만든 가드가 이미 그걸 가리키고 있다.
