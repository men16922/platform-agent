# 결정 3 조사 — Capsule `limitRanges` 이관 경로

조사일: 2026-08-02 · gate 1607 기준 · **코드 변경 없음(조사만)**

> 결론 요약: **선택지가 둘이 아니라 셋이다.** 기록은 `GlobalTenantResource`(클러스터 스코프,
> D30 위반)와 `TenantResource`(SA+RBAC 새 권한 표면) 둘만 놓고 "둘 다 비싸서 결정이 필요하다"고
> 적어 두었다. 그런데 **이 레포는 형제 필드에 대해 이미 세 번째 길을 택했다** — Capsule의
> `networkPolicies`를 쓰지 않고 **NetworkPolicy 객체를 직접 렌더**한다. `limitRanges`에도 같은
> 수가 그대로 있고, **두 비용을 다 피한다**.

---

## 1. 기록된 선택지

`docs/evidence/capsule-deprecation-metadata.log:66-75`, `STATUS` Risk 9, `NEXT_PLAN` 결정 3이
같은 두 갈래를 반복한다:

| 경로 | 비용 |
|------|------|
| `GlobalTenantResource` | **클러스터 스코프** → 에이전트 mutating 범위가 테넌트 밖으로 → **D30 위반** |
| `TenantResource` | 테넌트 안에 머물지만 **SA + RBAC 새 권한 표면**이 필요 |

## 2. 빠진 세 번째 — 같은 증거 로그가 스스로 적어 두었다

같은 파일 26–27행:

> `networkPolicies` does not apply to us — **this repo renders NetworkPolicy objects
> directly rather than through the Tenant spec.**

CRD가 deprecate한 세 필드(`additionalMetadata` · `limitRanges` · `networkPolicies`) 중
**`networkPolicies`는 이미 "Capsule 필드를 안 쓰고 객체를 직접 렌더"로 해결돼 있다.**
`limitRanges`도 똑같이 할 수 있다:

**옵션 C — `spec.limitRanges`를 빼고, 테넌트 네임스페이스마다 평범한 `LimitRange` 객체를 렌더한다.**

- `LimitRange`는 **네임스페이스 스코프**다 → 클러스터 스코프 객체 없음 → **D30 무관**.
- **새 SA·RBAC 불필요**. 지금 `render_tenancy`를 적용하는 신원은 이미 같은 네임스페이스에
  `ServiceAccount`·`Role`·`RoleBinding`·`NetworkPolicy`를 만든다. `LimitRange` 생성은 그보다
  **엄격히 약한** 권한이다. (`TenantResource` 경로가 SA를 필요로 하는 이유는 **Capsule이 대신
  복제해 주기 때문**이다 — 우리가 직접 만들면 대리인이 없으니 대리인의 권한도 없다.)
- 렌더러 한 곳(`render_capsule_tenant` → `render_tenancy`)에서 끝난다.

### 무엇을 잃는가 (정직하게)

Capsule의 `limitRanges`는 **재조정**된다 — 누가 지우면 되살리고, 테넌트에 나중에 붙는
네임스페이스에도 자동 적용된다. 직접 렌더한 객체는 **자가 치유하지 않는다**.
단 이 대가는 **이미 NetworkPolicy에서 받아들인 것과 같은 대가**이고, 네임스페이스 집합은
레지스트리가 SSOT라 `render_tenancy`가 아는 집합과 항상 같다.

## 3. 이건 그냥 두면 조용히 깨진다 — 그리고 그 조용함은 이미 Risk 8로 적혀 있다

`limitRanges`가 사문화된 필드였다면 결정할 것도 없다. 아니다:

- `render_capsule_tenant`는 쿼터에 **`limits.cpu`·`limits.memory`**를 넣는다
  (`tenancy.py:346-348`). 쿼터가 `limits.*`를 선언하면 **그 네임스페이스의 모든 파드는
  limits를 명시해야 하고**, 없으면 admission에서 거부된다.
- 그 limits를 채워 주는 게 이 `LimitRange`의 `default`/`defaultRequest`다(`tenancy.py:366-375`).
- **애드온 values 파일 4종(kube-prometheus-stack·loki·tempo·argo-rollouts) 중 limits를
  설정하는 건 하나도 없다**(`infra/onprem/addons/values/`에서 `limits:`는 capsule 자기 것뿐).
  즉 테넌트 워크로드는 **전부 이 default에 의존한다.**
- `verify_tenant_isolation.py`의 프로브 파드도 `requests`만 설정한다(`:108`, `:154`) —
  **격리 검증기 자신이 소비자**다.

제거 릴리스에서 Capsule은 이 필드를 **에러 없이 안 읽는다**(additionalMetadata와 같은 족보).
그러면 LimitRange가 사라지고 → 파드가 admission에서 거부되고 → **`STATUS` Risk 8이 적어 둔
바로 그 모양**이 된다: *"파드가 admission에서 거부되는데 Argo는 Synced로 보인다(파드 0개인 채)."*

## 4. 부수 발견 — 스테일 픽스처 1건 (결정과 무관, 고칠지는 별건)

`tests/test_tenancy_tools.py:183-186`의 `CAPSULE_WARNINGS`는 여전히 **두 경고**
(`limitRanges` + `additionalMetadata`)를 담고 `len(warnings) == 2`를 단언한다. 그런데
`additionalMetadata`는 2026-07-28에 이관됐고 증거 로그도 **"이제 경고는 하나"**라고 적었다.
테스트의 논지(경고는 실패가 아니다)는 여전히 옳지만, **픽스처가 클러스터가 더는 만들지 않는
stderr 모양**을 쓰고 있다 — M13에서 이미 기록한 *"픽스처는 실제 입력에서"*의 재발.

## 5. 아직 측정하지 못한 것 (결정적)

옵션 C를 **추천하되**, 두 가지는 라이브에서 확인해야 한다. **kind 클러스터도 Docker도 지금
내려가 있어** 이번 조사에서는 못 돌렸다:

1. **`spec.limitRanges`를 Tenant에서 빼면 Capsule이 자기가 만든 LimitRange를 회수하는가**
   (그래야 우리 것과 중복되지 않는다).
2. **Capsule이 직접 렌더한 LimitRange를 건드리지 않는가** — 소유하지 않은 객체는 두는 게
   정상이지만, 이 레포의 규칙은 **추론하지 말고 물어보는 것**이다.
3. 확인 방법: 테넌트 ns에 limits 없는 파드를 넣어 **BEFORE(거부되지 않음) → 필드 제거 후
   LimitRange 없음(거부됨) → 옵션 C 적용(다시 통과)** 3단.

## 6. 추천

**옵션 C.** 두 비용(클러스터 스코프 / 새 권한 표면)을 다 피하고, **이 레포가 형제 필드에
이미 내린 결정과 같은 모양**이며, 렌더러 한 곳에서 끝난다. 잃는 자가 치유는
NetworkPolicy에서 이미 같은 값으로 지불한 것이다.

**단, 적용 전에 §5의 라이브 3단을 돌린다** — Capsule 회수 동작은 문서로 추론할 게 아니라
API 서버에 물어볼 것이고, 지금까지 네 번 다 그렇게 해서 전제가 깨졌다.
