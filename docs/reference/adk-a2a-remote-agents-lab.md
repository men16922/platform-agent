# Reference — GENAI120: Connect to Remote Agents with ADK and the A2A SDK

> 외부 학습 랩 분석 노트. **platform-agent 차용 후보 패턴**만 추린다. 이식 전 검토용.
> 되돌리기 어려운 결정은 `DECISIONS.md`.

- **출처:** Google Cloud Skills Boost 랩 `GENAI120` — "Connect to Remote Agents with ADK
  and the Agent2Agent (A2A) SDK" (`explore.qwiklabs.com/classrooms/20667/labs/112891`)
- **검토일:** 2026-07-28 · 랩 최종 갱신 2026-04-21 · 소요 1h30m · 비용 무료(랩 크레딧)
- **랩 성격:** ADK 에이전트 하나(이미지 생성)를 Cloud Run에 **A2A 서버로 배포**하고,
  두 번째 ADK 에이전트가 그 **Agent Card를 읽어 서브에이전트로 사용**하게 만드는 4-task 실습.

---

## 메타 결론 — 이 랩은 **우리가 이미 지나온 지점**이다

우리는 2026-07-14에 A2A 라이브 E2E를 완주했다: Phase 1(자체 게이트웨이) + **Phase 2 실 kagent
에이전트**(local Qwen 30B) discovery → JSON-RPC 위임 → 실 `k8s_get_resources` 진단.
랩이 가르치는 것은 그 경로의 **관리형 버전**이다.

| | 랩(GENAI120) | platform-agent |
|---|---|---|
| A2A 서버 | `adk deploy cloud_run --a2a` (GCP 종속) | `a2a_server.py` FastAPI, 기판 무관 |
| 카드 배포 | `agent.json` 파일을 손으로 복사 | `/.well-known/agent-card.json` 표준 엔드포인트 |
| 원격 소비 | `RemoteA2aAgent(agent_card=...)` 선언 | `fetch_agent_card` + `matching_skills` 라우팅 |
| 카드 신뢰 | **검증 없음**(카드를 그대로 믿음) | name/skills 부재 시 `ValueError`, 역할별 용어 매칭 |
| 위임 판단 | LLM `transfer_to_agent` | 결정론적 분류 + self-consistency 투표(옵트인) |
| 모델 | Gemini(관리형) | 로컬 Qwen 30B 포함 |

→ **아키텍처를 베낄 대상은 아니다.** 랩은 단일 클라우드 관리형 경로이고 우리 코어는 클라우드-중립이다
(`NEXT_PLAN` 캘린더의 "ADK 재평가" 메모와 같은 결론). 전이되는 건 (a) **용어/계약의 독립 확증**과
(b) 우리 쪽에 실제로 남아 있던 **결함 하나**다.

## 자산 대조

| 랩의 자산 | platform-agent 현황 | 판정 |
|---|---|---|
| Agent Card = 발견 + 능력 명세 | ✅ `a2a_card.json` 6 skills + securitySchemes | 동등 |
| `capabilities`(streaming/push) ≠ `skills` 구분 | ✅ 이미 분리돼 있음 | **동등(독립 확증)** |
| JSON-RPC 2.0 over HTTP(S) | ✅ `supervisor.py`가 `jsonrpc: "2.0"` 분기 | 동등 |
| `RemoteA2aAgent` 선언형 서브에이전트 | ❌ 없음(손으로 위임) | **차용 안 함**(아래) |
| `A2aAgentExecutor` = 프로토콜↔런타임 번역 seam | ✅ `gateway/bridge.py`가 같은 역할(mcp↔a2a) | 동등(이름만 다름) |
| Cloud Run 원커맨드 호스팅 | ✅ Agent Runtime 3/3 클라우드 실 배포 | 동등 이상 |
| SA 임퍼소네이션으로 signed URL | — 해당 워크로드 없음 | 무관 |

## 차용 후보 — 딱 하나, 그리고 그건 코드가 아니다

**Agent Card의 `url`은 "원격 에이전트가 너를 부르는 주소"이지 장식이 아니다.**

랩은 `agent.json`의 `url`을 **배포될 Cloud Run 서비스 URL이 되도록 구성**한다. 이 강조가 우리 쪽
결함을 드러냈다 — `src/agents/ai/a2a_card.json`이 이렇게 돼 있었다:

```json
"supportedInterfaces": [{ "url": "https://platform-agent.example.com/a2a/v1", ... }],
"provider": { "url": "https://github.com/your-org/platform-agent" }
```

둘 다 **가상 주소**다. 실 레포는 `github.com/men16922/platform-agent`이고, `example.com` 호스트는
존재하지 않는다. 우리 코드 어디도 이 값을 소비하지 않기 때문에(엔드포인트는 항상 호출자가 명시적으로
넘긴다) 라이브 E2E를 완주하고도 **한 번도 밟히지 않았다**. 이 필드는 오직 *남이 우리를 소비할 때*
쓰이고, 아직 아무도 우리를 소비한 적이 없다.

그리고 테스트가 이걸 붙잡아주지 못한 이유가 익숙하다:

```python
assert "supportedInterfaces" in card          # 필드가 있는지만 본다
assert "protocolBinding" in iface             # 값이 어디를 가리키는지는 안 본다
```

**선언을 단언하는 가드**다 — 같은 세션에 대시보드에서 고친 `ROUTE_PROTECTION`과 정확히 같은 족보이고,
이 레포가 반복해서 당한 "에러 없이 안 읽히는" 실패의 한 갈래다. 카드가 거짓말을 해도 우리 게이트는
초록이고, 대가는 우리가 아니라 **우리를 부르려는 쪽**이 치른다.

→ 조치: 파일에서 절대 URL을 빼고 서빙 시점에 실제 주소로 채운다(값이 한 곳에서만 나오게).
플레이스홀더 금지 가드 추가. → `PROGRESS_LOG` 2026-07-28.

## 차용하지 않는 것 (이유 포함)

- **`RemoteA2aAgent` 선언형 서브에이전트** — 편하지만 **카드를 검증 없이 믿는다**. 우리
  `matching_skills`는 역할별 용어를 좁게 잡아 *"진단 전용 카드가 프로비저너로 채택되지 않게"*
  막고 있고, 그 주석은 실제 오채택을 겪고 쓴 것이다. 선언형으로 바꾸면 그 방어가 사라진다.
  ADK가 카드 검증 훅을 제공하면 재평가.
- **`adk deploy cloud_run --a2a`** — GCP 종속. 우리 Agent Runtime은 이미 3/3 클라우드 실 배포를
  마쳤고, 코어를 한 클라우드의 배포 CLI에 묶는 것은 D-계열 결정에 반한다.
- **LLM `transfer_to_agent` 위임** — 랩은 위임 판단을 전적으로 모델에 맡긴다. 우리는 결정론적
  분류가 기본이고 self-consistency 투표는 옵트인이다. 인프라 라우팅에서 창의성은 필요 없다는 건
  자체 스윕으로 측정해둔 사실이다(`docs/evidence/model-sweep-live.log`).
- 기존 안티패턴 메모 유지: A2A "Dynamic Autonomy" · 자유텍스트 `spawn_subagent` 금지.

## 후속 자료 — 크로스-언어 멀티에이전트 (Google Developers Blog)

- **출처:** `developers.googleblog.com/build-cross-language-multi-agent-team-with-google-agent-development-kit-and-a2a/` · 검토일 2026-07-28
- **내용:** 계약서 컴플라이언스 파이프라인 — **Python(ADK+Gemini) 추출 에이전트**가
  **Go 검증 에이전트**를 A2A로 호출. Python 쪽은 `RemoteA2aAgent`로 Go 서비스를 로컬
  서브에이전트처럼 감싸고, 공유 state dict가 `INGESTED → EXTRACTED → COMPLIANCE_COMPLETE`
  체크포인트를 추적한다.

**이 글의 진짜 값어치는 마지막 한 문단이다:**

> Go 검증기가 도달 불가가 되면 *"파이프라인은 그냥 실패하지 않는다. `MANUAL_REVIEW`로
> 전이하고 사람 법무 검토자에게 라우팅한다."*

이건 우리가 D24에서 **독립적으로 도달한 결론**이다 — `None`(못 봄) ≠ `[]`(봤는데 조용함),
관측 안 된 canary는 조용한 canary가 아니다. 원격 에이전트 부재를 실패가 아니라 **판단 불가**로
다루고 사람에게 올리는 것이 같은 규율이다. 방금 끝낸 Phase 3②(reconciler 충돌 시 거부 →
사람에게)도 정확히 같은 모양이다. 외부 확증으로 기록한다.

**갈라지는 지점 1건 — 카드 경로 스펙 드리프트**: 이 글은 Agent Card를
`/.well-known/agent.json`에 둔다. 우리와 랩(GENAI120)은 `/.well-known/agent-card.json`이다.
같은 조직의 자료 둘이 다른 경로를 쓴다 — 우리를 소비하려는 쪽이 구 경로를 시도할 수 있으므로,
언젠가 외부 소비자가 생기면 **두 경로를 모두 서빙**하는 것이 싸다. 지금은 소비자가 없어
착수하지 않고 기록만 남긴다.

**모놀리식 에이전트가 깨지는 이유 3가지**(컨텍스트 열화 · blast radius · 테스트 불가)는
우리 supervisor+specialist 분리와 `IncidentScope`(blast radius=1 tenant)의 근거와 동일하다.

## 확증된 것 (바꿀 것 없음)

랩이 A2A의 정본 개념으로 제시하는 5가지 — 표준 통신(JSON-RPC 2.0/HTTPS) · Agent Card 발견 ·
리치 데이터 교환 · 유연한 상호작용(동기/SSE/비동기 푸시) · 엔터프라이즈 대비(보안·인증·관측) —
는 우리 카드와 서버가 **이미 전부 표현**하고 있다. `capabilities`(streaming·pushNotifications)를
`skills`와 분리해 둔 것도 랩의 명시적 구분과 일치한다. 독립 확증으로 기록한다.
