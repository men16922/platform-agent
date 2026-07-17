# Reference — Google Agent 생태계 2026 (ADK 2.0 + A2A)

> 외부 자료 분석 노트. **우리 설계와의 대조·차용 후보**만 추린다. 이식/채택 전 검토용. 되돌리기 어려운 결정은 `DECISIONS.md`.

- **출처:**
  - ADK 2.0 — https://developers.googleblog.com/why-we-built-adk-20/
  - A2A collaborative agents — https://developers.googleblog.com/how-a2a-is-building-a-world-of-collaborative-agents/
  - agents-cli — https://google.github.io/agents-cli/ · https://github.com/google/agents-cli
- **검토일:** 2026-07-17
- ⚠️ 두 글의 **구체 버전/수치**(ADK Python GA 시점, A2A SDK 버전표, 벤치마크 50%/20%)는 요약 모델이 추출한 값이라 **아티클 인용 전 원문 재확인 필요**. 아래 "우리 접점"은 값과 무관하게 유효.

---

## A. ADK 2.0 — "Agentic Workflows"

### 핵심 주장
순수 LLM-주도 오케스트레이션을 버리고 **deterministic directed-graph 실행 + LLM은 인지(추론)에만**. 라우팅·조건분기·에러핸들링·API 호출은 전통 코드로 실행하고, LLM은 진짜 추론이 필요한 노드에만 예약. 효과: 토큰 ~50%↓·지연 ~20%↓·prompt-injection 완화(실행 제어를 LLM에서 분리)·노드 간 context 격리(attention degradation 방지). Python GA는 2026-03 예정, Go 신규 출시.

### 우리 접점 — **대부분 이미 구현됨 (마이그레이션 대상 아님)**
| ADK 2.0가 파는 것 | platform-agent 대응물 |
|---|---|
| Deterministic 라우팅(LLM 아님) | `orchestration.py` self-consistency majority vote → **저합의 시 결정론 `classify_request` 폴백**(`:206`) |
| LLM 결론 무조건 신뢰 안 함 | `reconciliation.py` — 미근거 시 **AUTO→APPROVE 강등**(실 환각 라이브 포착, grounding 0.08) |
| 실행 제어를 LLM에서 분리 | Guardian policy-as-code + capability runbook + approval 게이트. LLM=분류/분석, **실 kubectl/클라우드 액션은 결정론 경로가 게이트** |
| 특화 에이전트를 워크플로 노드로 | Orchestrator plan→각 step `Supervisor.handle` 위임(specialists-as-tools), 실패 시 short-circuit(`:222`) |

→ 우리는 "vanilla autonomous agent"가 아니라 이미 deterministic-control-plane 쪽. ADK 2.0의 순수-LLM→그래프 마이그레이션 스토리는 우리에게 해당 없음.

### context 격리 — **감사 완료(2026-07-17): 델타 아님(no-op)**
초안은 Orchestrator가 step들에 shared `context_id`를 넘기는 것(`orchestration.py:212`)을 오염 후보로 봤으나, **오독이었음**. 근거: `supervisor.py:171`이 특화 에이전트에 보내는 A2A 페이로드는 `parts:[{"text": instruction}]` = **그 step의 instruction만**(누적 컨텍스트·이전 step 출력·대화이력 threading 없음). `context_id`는 `message["contextId"]`(`:174`) = **A2A 프로토콜 상관관계 UUID**(수신 피어가 task 그룹핑하는 세션 키)이지 우리가 밀어넣는 컨텍스트 페이로드가 아님. → 우리는 이미 step별 최소 스코프 페이로드 전송, shared `contextId`는 A2A "Zero Context Pollution" 정석(수신 피어가 자기 state 독립 관리). **코드 변경 불요.**

---

## B. A2A — 협업 에이전트 프로토콜

### 상태 (2026-06 기준, ⚠️버전 재확인)
- SDK: **Python/Go v1.0 GA**, Java Beta, .NET Preview, JS/TS v0.3 stable(1.0 개발 중). 레포 `github.com/a2aproject`.
- 우리는 `a2a` SDK를 이미 사용 중(kagent 0.9.11-era). **Phase 2 라이브 E2E 완결**: supervisor→실 kagent 에이전트 카드 HTTP discovery→skill 매칭→JSON-RPC 위임→실 `k8s_get_resources` 진단. (증거 `docs/evidence/a2a-phase2-live-e2e.log`)

### 4대 아키텍처 이점 vs 우리 상태
| A2A가 강조 | platform-agent |
|---|---|
| **Secure Boundaries** — 에이전트가 사설 환경/데이터를 공개 LLM 노출 없이 유지 | ✅ On-Prem 오프라인 완결(Local Qwen), 크로스계정 STS 격리와 정합 |
| **Zero Context Pollution** — 피어가 자기 state 독립 관리, 주 에이전트 context 오염 방지 | ✅ (감사 완료 2026-07-17) — step별 페이로드는 instruction만(`supervisor.py:171`), shared `contextId`는 상관관계 UUID지 컨텍스트 블롭 아님. 이미 최소 스코프 |
| **Dynamic Autonomy** — 수신 에이전트가 의도 파악·계획 정제·**되묻기(clarify)·불완전 요청 push-back** | ❌ **갭(아스피레이셔널)** — 현재 위임은 fire-and-return. 특화 에이전트가 되묻거나 거부하는 대화형 왕복 없음 |
| **Workload Distribution** — 팀/벤더별 모듈 개발 | ✅ provision/deploy/kagent 역할 분리, 카탈로그 단일화 |

---

## C. agents-cli — 에이전트 빌드 메타-툴링

### 상태
GCP(Gemini Enterprise Agent Platform)에서 에이전트를 **빌드**하는 CLI + skill 라이브러리. coding agent(Claude Code·Antigravity·Codex)를 `npx skills add google/agents-cli`로 증강. 명령: `scaffold`/`run`/`lint`/`eval generate|grade|optimize`/`deploy`/`publish gemini-enterprise`/`infra cicd`. Python 78%+HCL 12%, Apache-2.0, 5.2k★, **Pre-GA**. 배포: Agent Runtime/Cloud Run/GKE, 관측: Cloud Trace+BigQuery.

### 우리와의 관계 — **레이어가 다름 (채택 대상 아님)**
| | agents-cli | platform-agent |
|---|---|---|
| 정체 | 에이전트를 **빌드**하는 메타-툴 | 이미 빌드된 멀티클라우드 Day1/Day2 ops 에이전트 |
| 클라우드 | **GCP/Gemini Enterprise 종속** | 클라우드-중립(AWS/GCP/Azure/On-Prem) |
| 배포 | 자체 `deploy`/`publish` | 이미 `adapters/runtime/` 3종 라이브(Agent Engine 포함) |

→ GCP lock-in이 우리 멀티클라우드 중립성과 충돌. `deploy→Agent Runtime`도 우리 Agent Engine 어댑터와 겹침(그들 GCP만, 우리 3-cloud). scaffold/관측/CI-CD는 우리 DynamoDB trace+대시보드+`make check`와 **패리티**.

### 유일한 차용 후보 — **eval 하네스**
`eval generate/grade/optimize` = eval 데이터셋 + metrics + **LLM-as-judge** + 프롬프트 최적화 루프. **우리가 실제로 없는 계층**: `make check`(748)는 결정론 유닛/통합 테스트뿐이고, reconciliation gate·self-consistency는 **런타임 가드레일**이지 오프라인 결정-품질 평가가 아님. → LLM 라우팅/분석 품질을 데이터셋으로 채점·회귀 추적하는 계층은 비어 있음. 클라우드-중립하게(mock LLM/실 MLX) 이식 가능한 **자율 코드 항목**.

### 안티패턴
- **GCP/Gemini Enterprise lock-in** — eval "방법론"만 추상화, 툴 자체 의존 금지.
- **Pre-GA** — API 불안정, 프로덕션 의존 금지.

---

## 액션 (우선순위별)

1. ~~**아티클 포지셔닝**~~ — **완료(2026-07-17).** EN `platform-agent-architecture.md` + KO `-ko.md` 맺으며 앞에 "같은 논지, 이제 플랫폼 벤더가 출시하다" 수렴 섹션 추가(ADK 2.0·A2A·agents-cli ↔ 우리 reconciliation/self-consistency/최소-페이로드 위임, 출처 3링크). 미검증 벤치마크(50%/20%)·버전 수치는 **정성 서술만**(인용 안 함). 배포는 사용자.
2. ~~**context 격리 감사**~~ — **완료(2026-07-17): 델타 아님.** 감사 결과 우리는 이미 step별 최소 페이로드(instruction만) 전송, shared `contextId`는 A2A 상관관계 키. 코드 변경 불요(위 A절 참조).
3. ~~**버전 트래킹**~~ — **규명 완료(2026-07-17): 백로그 노트.** 우리 클라이언트 A2A=stdlib-only(`a2a` SDK import 0, `supervisor.py`)라 A2A SDK 드리프트 무영향(SDK는 원격 kagent 서버에만). ADK=`google-adk>=1.0`(`adk_deployer.py` Gemini 경로만). ADK Python GA **2026-03** 후 workflow-graph를 Gemini 서브경로에 적용 가능한지 재평가(코어 Orchestrator는 클라우드-중립이라 비대상). 지금 액션 없음.
4. ~~**eval 하네스 검토**~~ — **완료(2026-07-17): 스파이크로 실익 확인.** `src/agents/ai/eval_harness.py`(클라우드-중립·오프라인, injectable Router/Judge, `llm_judge`는 실패 시 결정론 백스톱, `EvalReport` 회귀 가드) + 빌트인 `ROUTING_EVAL_SET`. gate 748→758(+10 test). 결정론 classifier 스파이크에서 **실제 라우팅 갭 2건 표면화**(cluster-creation 동사 미커버) → `classify_request` 수정 → eval set 13/13(갭=회귀가드). 발견→수정→가드 루프 = 유닛테스트가 못 잡는 결정-품질 계층 실익 확인.

## 안티패턴 / 주의
- 두 글은 **마케팅 톤**(Google 스튜어드십 강조, 거버넌스/Linux Foundation 언급 없음). 프로토콜 스펙 세부(agent card·auth·transport)는 이 글이 아닌 스펙 문서로 확인.
- "Dynamic Autonomy(되묻기)"는 매력적이나 **요청 범위 밖 기능** — 백로그 메모만, 자율 추가 금지.
