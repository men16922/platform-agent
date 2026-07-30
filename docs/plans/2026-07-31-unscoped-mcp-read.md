# 결정 2 브리프 — "무스코프 MCP 읽기를 닫을 것인가"

작성: 2026-07-31 · gate 1596 · 선행 = D38(스코프 생산자)

> 이 항목은 오래 "의도적 예외"로 열려 있었다. 이유는 **"닫으면 검증된 익명 kagent 왕복이
> 깨진다"**였다. 조사 결과 **그 이유가 사실이 아니다.**

---

## 요약 (30초)

MCP 게이트웨이는 mutating 도구(`kubectl_apply`)는 스코프 없이 거부하지만, **읽기 4종**
(`kubectl_get`·`logs`·`describe`·`rollout_status`)은 **ambient로 통과**시킨다. 그리고 ambient는
라이브 kind에서 **cluster-admin**이다(D38 실측). 라이브 확인:

```
MCPServer()                      # 스코프 없음 — 익명 호출자가 얻는 바로 그 객체
  .call_tool("kubectl_get", {"resource": "secrets", "namespace": "kube-system", ...})
  → success: True
  .call_tool("kubectl_get", {"resource": "nodes", ...})
  → node/platform-agent-control-plane  node/platform-agent-worker  node/platform-agent-worker2
```

`resource`는 자유 문자열이라 **읽기 도구 하나가 클러스터의 모든 자원 종류에 닿는다.**
"남의 로그 = 유출"이라고 적어둔 것보다 넓다 — 로그가 아니라 **secrets를 포함한 전부**다.

**그런데 그걸 여는 대가로 지키던 것이 없다:**

| 주장 | 실제 |
|---|---|
| "익명 kagent 왕복이 이걸 쓴다" | **아니다.** kagent 왕복은 **우리가 kagent를 부르는** 아웃바운드다. `k8s_get_resources`는 **kagent 자신의 도구**이고 kagent의 자격증명으로 돈다(`docs/evidence/a2a-phase2-live-e2e.log`). 우리 MCP 게이트웨이는 그 경로에 **없다**. |
| "무스코프 읽기 경로가 프로덕션에서 쓰인다" | **`MCPServer`를 생성하는 프로덕션 코드가 0이다.** 호출부는 자기 docstring · `bridge.py`(그 자신도 docstring에서만 참조됨) · `scripts/live_net_demo.py`(클러스터 읽기는 안 쓰고 `extra_tools`만) 뿐. |
| "A2A 인바운드가 게이트웨이로 라우팅된다" | **아니다.** `a2a_server`의 `/message:send`는 Supervisor/Orchestrator로 간다. MCP 게이트웨이로 가는 경로가 없다. |

즉 **이 예외는 존재하지 않는 소비자를 위해 열려 있었다.** 그리고 그 예외를 붙잡고 있는
유일한 코드는 그것을 고정하는 테스트다(`test_unscoped_read_still_works`).

**M13의 그 결함이 한 층 더 위에서 반복됐다**: 이번에 없는 건 필드의 소비자도, 메커니즘의
생산자도 아니라 — **예외를 정당화하던 사용처**다.

---

## 확인된 사실 (코드/라이브 기준)

### F1. 무스코프 읽기는 ambient이고 ambient는 cluster-admin이다
`mcp_server.py:449` — `self._scope is None`이면 mutating만 거부하고 읽기는 `fn(**args)`로
그대로 실행한다. `_kubectl()`은 스코프가 없으면 `["kubectl", ...]`(무 `--kubeconfig`).
D38 실측: 그 ambient는 `kubernetes-admin`/`kubeadm:cluster-admins`.

### F2. `resource`가 자유 문자열이라 반경이 도구 이름과 무관하다
`ToolSpec("kubectl_get", ..., {"resource": "string", "namespace": "string", ...})`.
`secrets`도 `nodes`도 같은 도구로 읽힌다. 라이브에서 둘 다 성공.

### F3. kagent 왕복은 이 경로를 쓰지 않는다 — 방향이 반대다
`docs/evidence/a2a-phase2-live-e2e.log`: `kind: discovery` → `kind: delegation`,
`"role": "kagent"`. 우리가 **보내는** 쪽이고 `k8s_get_resources`는 응답에 담겨 온 **kagent의
도구**다. "익명"이란 말이 가리키는 것도 다르다 — **우리 클라이언트가 bearer 없이 kagent를
부르는 것**(= 별개 항목인 A2A 인증 결정)이지, 누군가 우리 게이트웨이를 부르는 게 아니다.

### F4. 프로덕션에 `MCPServer` 생성자가 없다
`grep -rn "MCPServer(" src scripts` → docstring 1 · `bridge.py` 1 · 데모 스크립트 1.
`bridge.McpA2aBridge`를 생성하는 프로덕션 코드도 없다. 즉 **게이트웨이는 포트에 붙어 있지
않다.** D38에서 스코프 생산자에 대해 발견한 것과 **같은 모양**이다.

### F5. 데모조차 이 경로를 안 쓴다
`scripts/live_net_demo.py`는 `extra_tools`(web_search 등)만 호출한다. 클러스터 읽기 4종은
부르지 않는다.

---

## 선택지

### A. 무스코프 클러스터 읽기를 거부한다 (mutating과 같은 규칙)

- **비용**: 실질 0. 깨지는 프로덕션 호출자가 없고(F4) 데모도 안 쓴다(F5). 바뀌는 건
  카브아웃을 고정하던 테스트 하나.
- **얻는 것**: 게이트웨이에 **휴면 상태의 ambient 경로가 남지 않는다.** 이게 실제 가치인
  이유는 레퍼런스 작업이 **MCP-over-HTTP**를 상정하고 있기 때문이다 — 누군가 이걸 포트에
  붙이는 순간, 오늘 무해해 보이는 이 예외가 **인증 없는 cluster-admin 읽기 API**가 된다.
  그때 발견하면 이미 늦다.
- **주의**: "닫았다"가 "스코프가 강제된다"는 뜻은 아니다. **호출자가 스코프를 넘겨야**
  읽기가 되는 것이고, 넘기는 프로덕션 경로는 아직 없다(= D38 Risk 3의 옵트인 문제와 동일).

### B. 명시적 옵트인 뒤로 옮긴다 (`PLATFORM_MCP_ALLOW_UNSCOPED_READS`)

- A와 같되, 정말로 ambient 읽기가 필요한 로컬 작업자를 위한 탈출구를 남긴다.
- **비용**: 플래그 하나. **얻는 것**: 기본이 안전하면서 "이걸 켜면 무슨 일이 벌어지는지"가
  한 곳에 적힌다. 레포의 기존 규약과도 맞는다(`ONPREM_EXECUTOR_LIVE`·`A2A_BEARER_TOKEN`).

### C. 그대로 둔다

- **비용**: 위 F1~F2가 계속 참이고, 문서에는 **사실이 아닌 이유**가 적혀 있다. 최소한
  이유는 고쳐야 한다 — 틀린 근거로 열려 있는 예외는 다음 사람이 재검토할 수 없다.
- **얻는 것**: 없음. 지키던 게 없다는 것이 이 조사의 결론이다.

---

## 추천

**B.** 기본은 거부, `PLATFORM_MCP_ALLOW_UNSCOPED_READS=true`로 되살릴 수 있게.

A가 아니라 B인 이유는 하나뿐이다: 이 조사가 방금 **"소비자가 없다고 믿었는데 있었다"의 반대
사례**를 만들었으니, 내가 못 본 로컬 사용처가 있을 가능성에 **되돌릴 손잡이**를 남기는 편이
정직하다. 다만 그 손잡이는 **명시적이고 시끄러워야** 한다 — 조용한 기본값으로 되돌아가면
아무것도 안 한 것과 같다.

C를 고르더라도 **문서의 이유는 반드시 고쳐야 한다.** "익명 kagent 왕복을 살리려는 예외"는
검증된 근거가 아니라 **검증되지 않은 채 인용돼 온 문장**이었다.

---

## 결정하면 내가 할 일 (B 기준)

- `mcp_server.py`: 무스코프 클러스터 읽기를 mutating과 같은 이유로 거부. 탈출구는
  `deploy_identity`와 같은 규약(빈 문자열=미설정, 켜지면 **호출 시점에 경고**).
- `tests/test_mcp_scope.py`: `test_unscoped_read_still_works`를 **거부 + 탈출구** 단언으로
  교체하고, 파일 상단의 근거 문장(4번)을 사실로 고친다.
- **가드는 파생시킨다**: 카브아웃의 근거로 인용된 소비자가 실재하는지를 검사한다. 이번 건의
  진짜 교훈은 "ambient가 나쁘다"가 아니라 **"예외의 근거가 코드로 확인되지 않은 채 인용됐다"**
  이고, 그건 다음 예외에서도 똑같이 일어난다.
- 라이브 반증: 켜짐/꺼짐 두 상태에서 `kubectl_get secrets`가 각각 어떻게 되는지.
