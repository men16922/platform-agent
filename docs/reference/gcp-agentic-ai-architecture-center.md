# Reference — GCP Architecture Center: Agentic AI 시리즈

> 외부 아키텍처 가이드 분석 노트. **platform-agent 차용 후보 패턴**만 추린다. 이식 전 검토용.
> 되돌리기 어려운 결정은 `DECISIONS.md`.

- **출처:** `docs.cloud.google.com/architecture/agentic-ai-overview` (허브, 최종 검토 2025-11-25)
  + 직접 읽은 하위 문서 3종:
  `multi-tenant-agentic-ai-system` · `multiagent-ai-system` · `choose-design-pattern-agentic-ai-system`
- **검토일:** 2026-07-28
- **시리즈 구성:** 기초 3(개요·컴포넌트 선택·패턴 선택) + 아키텍처 4(멀티에이전트·멀티테넌트·
  프라이빗 네트워킹·단일에이전트 ADK/Cloud Run) + 유스케이스 10. 우리와 층이 겹치는 건 앞의 7이고,
  유스케이스 10은 도메인 예제(학습관리·데이터과학·GraphRAG 등)라 **범위 밖**.

---

## 메타 결론 — **벤더 청사진**이지 아키텍처 처방이 아니다

문서 전반이 "이 문제는 이 GCP 제품으로 푼다"는 형태다. 우리에게 전이되는 건 제품이 아니라
**그들이 문제를 어떻게 쪼갰는가**와, 그 분해가 우리 빈칸을 비추는 지점이다.

| 축 | GCP 가이드 | platform-agent |
|---|---|---|
| 테넌트 격리 | **프로젝트-per-테넌트 단일 모델**(= 우리 `dedicated` 하나) | soft/vcluster/dedicated **3티어 스펙트럼** |
| 격리 집행 | Principal Access Boundary + VPC-SC + IAM | 네임스페이스 RBAC + 스코프 kubeconfig + NetworkPolicy |
| 실행 자격증명 | 에이전트별 IAM, 최소권한 | 인시던트별 `IncidentScope`(attested 승인으로만 발급) |
| 관측 | Cloud Trace/Logging | OTel→Tempo(**MTTR 82%가 로컬 LLM 추론**까지 실측) |
| 모델 | Gemini 관리형 | 로컬 Qwen 포함, 클라우드-중립 |

→ **격리 설계는 우리가 더 세분화돼 있다.** 그들은 "가장 강한 격리 하나"를 처방하고 우리는
비용↔강도 스펙트럼을 갖는다(그리고 각 티어의 **비보증**을 명시한다 — D28의 `notCovered`).
반대로 **그들이 갖고 우리가 안 가진 축이 두 개** 있고, 그게 이 문서의 값어치다.

## 이 문서가 드러낸 우리 갭 2건 (둘 다 실측 확인)

### ① 공유 MCP 서버에 테넌트 신원이 전파되지 않는다

가이드는 MCP 배포를 **local(테넌트별) vs shared(공유)** 로 나누고, shared를 쓰려면
*"에이전트에서 공유 MCP 서버로 최종 사용자 신원을 안전하게 전파"* 해야 세밀한 접근제어가
선다고 못 박는다.

우리 `gateway/mcp_server.py`는 **공유**다. 카탈로그 + per-tool/global kill-switch는 있는데
(`grep tenant` 결과 0건) **테넌트 개념이 없다.** Phase 3①이 *실행* 경로에 세운 경계가
*도구* 경로에는 없다는 뜻이다. kill-switch는 "이 도구를 전부 끈다"이지 "이 테넌트에게만 끈다"가
아니다. → `NEXT_PLAN` 신규 항목.

### ② 테넌트별 rate limit / 노이지 네이버 방어가 없다

가이드는 공유 엔드포인트 앞단에서 **테넌트 단위 쿼터 집행**(Memorystore 카운터 · API Gateway
키 · Provisioned Throughput)을 요구하고, 429에 지수 백오프를 붙이라고 한다.

우리 쿼터는 **Capsule ResourceQuota**(cpu/memory/pods)까지다 — 클러스터 자원은 막지만
**모델 호출·에이전트 실행량은 아무도 안 센다.** 한 테넌트의 폭주가 공유 LLM 엔드포인트를
독점하는 경로가 열려 있다. 로컬 Qwen 단일 인스턴스라 더 직접적이다. → `NEXT_PLAN` 신규 항목.

## 확증된 것 (바꿀 것 없음)

- **local vs shared MCP 트레이드오프 표**가 우리 D27(capability `scope: cluster|namespace`)과
  같은 축이다. 공유 설치물을 테넌트 drift로 세지 않는 우리 `applicable=false` 처리도 같은 결론.
- **"Agent Card로 인증 요구사항을 광고한다"** — 이 문장이 우리 결함을 드러냈다(아래 조치 참조).
- 멀티에이전트 보안 3원칙(human oversight · 최소권한 · 관측)은 우리 승인 게이트 3단(P1/P2/P3),
  `IncidentScope`, OTel 트레이싱에 이미 대응된다.
- 신뢰성: "에이전트 단위 실패를 견디게 설계" = 우리 `resolution_verdict`(실행됨 ≠ 나아졌음)과
  reconciler 충돌 거부(D32)가 같은 계열.

## 패턴 어휘 — 우리가 하는 일에 이름이 붙는다

`choose-design-pattern` 문서의 12패턴 중 우리가 이미 쓰는 것:

| 패턴 | platform-agent에서의 자리 |
|---|---|
| Sequential | detect→analyze→decide→execute 4단 파이프라인 |
| Coordinator | `supervisor.py` 역할 라우팅 |
| Human-in-the-Loop | P2 승인 게이트(Slack 왕복), 카나리 수동 게이트 |
| Custom Logic | capability step의 순서·조건·on_failure |
| Review & Critique | self-consistency 투표(옵트인) |
| Single-Agent | 온프렘 12도구 진단 에이전트 |

**의도적으로 안 쓰는 것**: Swarm(전원 대화) · Hierarchical Decomposition. 가이드 자신이
"most complex, costly, convergence risks"로 분류하고, 우리 안티패턴 메모(자유텍스트
`spawn_subagent` 금지 · 정적 무조건 fan-out 금지)와 같은 이유다 — 독립 확증.

## 차용하지 않는 것

- **프로젝트-per-테넌트 강제** — 우리 soft 티어의 존재 이유가 비용이다. 3티어를 하나로 접으면
  kind 한 대에서 도는 시연부터 불가능해진다.
- **Model Armor / Cloud Armor / IAP 캐스케이딩 인그레스** — GCP 종속. 개념(다층 필터)은 이미
  Guardian Agent + 승인 게이트로 갖고 있다.
- **PAB(Principal Access Boundary)** — GCP 조직 정책 전용. 우리 등가물은 스코프 kubeconfig이고,
  Phase 3①에서 **API 서버가 판정**하는 것으로 라이브 증명했다.
- **공유 허브 비용 배분(균등/비례/티어)** — 흥미롭지만 우리 공유 스택 9개는 TF 소유(D30)이고
  chargeback 요구가 아직 없다. 요구가 생기면 이 표를 참고.
