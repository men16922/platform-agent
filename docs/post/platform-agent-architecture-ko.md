# 자율 플랫폼 에이전트에게 손을 쥐여주다 — 그리고 그 손을 안전하게 만드는 가드레일

*멀티클라우드·온프렘을 아우르는 플랫폼 운영 에이전트가 클러스터를 프로비저닝하고, 배포를 내보내고, 장애를 스스로 복구하기까지 — 그리고 LLM이 되돌릴 수 없는 일을 저지르지 않게 막는 결정론적 가드레일에 관하여.*

> 이 글은 영문판 [`platform-agent-architecture.md`](platform-agent-architecture.md)의 한국어판입니다.

---

## 한 줄 요약

`platform-agent`는 AWS 네이티브(그러나 클라우드 중립)로 설계된 에이전트로, **Day 1**(프로비저닝 → 빌드 → 배포 → 검증)과 **Day 2**(감지 → 분석 → 결정 → 실행 → 리포트)를 **AWS·GCP·Azure·온프렘** 전반에서 다룬다. 자연어 한 문장 — *"온프렘 클러스터를 만들고, orders-api를 배포한 뒤 정상인지 확인해줘"* — 이 계획되고, 추적되며, 승인 게이트를 거치는 실제 인프라 작업 시퀀스로 변환된다.

흥미로운 지점은 "LLM이 도구를 호출할 수 있다"가 아니다. 핵심은 **가드레일**이다. 모델이 도구 결과로 뒷받침하지 못하는 사실 위에서 행동하기를 거부하는 **정합성(reconciliation) 게이트**, 라우팅에 대한 **자기일관성(self-consistency) 투표**, 예산 게이트, 서킷 브레이커, 도구별 kill-switch, 그리고 크로스계정 실패 시의 우아한 폴백. 이 글은 아키텍처와 그 뒤의 엔지니어링 원칙을 짚어본다 — **854개 통과 테스트**와 세 개의 실제 클라우드에서의 라이브 E2E로 검증된.

---

## 문제

텍스트를 요약만 하는 에이전트는 리스크가 낮다. `kubectl scale`, `terraform apply`, `create_agent_runtime`을 **프로덕션 계정에** 실행하는 에이전트는 다르다. 에이전트에게 손을 쥐여주는 순간, 두 질문이 모든 설계 결정을 지배한다.

1. **환각 위에서 행동하지 않게 어떻게 막는가?** 지어낸 근본 원인을 근거로 "이건 P1이니 배포를 자동 재시작"이라 결정하는 LLM은, 자동화가 없느니만 못하다.
2. **되돌리기 어려운 작업을 어떻게 안전하게 만드는가?** 클러스터 삭제, 런타임 teardown, 0으로 스케일 — 이런 건 모델의 말만 믿고 절대 일어나선 안 된다.

아래 모든 것은, 어떤 식으로든, 이 두 질문에 대한 답이다.

---

## 아키텍처 한눈에

시스템은 하나의 패턴을 축으로 조직된다: **`ServiceSpec`(선언적 의도) → capability → 환경 네이티브 어댑터**. 에이전트는 의도를 해석하고, 어댑터가 클라우드 중립 capability("클러스터 프로비저닝", "배포 롤백")를 각 provider의 네이티브 메커니즘으로 번역한다.

| 레이어 | AWS | GCP | Azure | 온프렘 |
|---|---|---|---|---|
| **프로비저닝(IaC)** | CDK / Terraform | gcloud / Terraform | az / Terraform | Terraform + Ansible |
| **클러스터** | EKS | GKE | AKS | kind · k3s · kubeadm |
| **빌드 → 푸시** | CodeBuild → ECR | Cloud Build → AR | ACR Tasks → ACR | docker build → registry |
| **배포 → 검증** | kubectl → EKS + health | kubectl → GKE | kubectl → AKS | kubectl → local |
| **배포 에이전트** | Strands + Bedrock Claude | ADK + Gemini 3.5 Flash | MSFT SDK + Azure GPT‑5.4 | Pydantic AI + Local Qwen (MLX) |
| **매니지드 런타임** | Bedrock AgentCore | Vertex AI Agent Engine | Foundry Agent Service | kagent (CNCF) |
| **Day‑2 (이벤트/오케스트레이션)** | EventBridge / Step Functions | Pub/Sub / Cloud Workflows | Event Grid / Durable Functions | Webhook / Temporal |

이 표에서 두 가지 설계 귀결이 나온다.

- **파이프라인 엔진은 클라우드 독립적**이다 — 순수 파이썬, 클라우드 SDK 의존 없음. 그래서 노트북·CI 러너·Lambda·Cloud Function 어디서나 동일하게 돈다.
- **호스팅 레이어는 교체 가능**하다 — AWS(EventBridge + Lambda)는 이벤트 수신 계약의 한 구현일 뿐, GCP·Azure·온프렘도 같은 형태를 따른다.

### 모델 ↔ 환경 분리

"배포 에이전트" 열은 각 클라우드의 *권장 네이티브* 조합을 보여주지만, 두뇌(모델)와 대상(환경)은 **AI Model Router**로 의도적으로 분리돼 있다. 어떤 모델이든 어떤 환경으로 배포를 몰 수 있고, 라우터는 적합도만 표기한다. 이 덕분에 동일한 자연어 흐름이 클라우드의 Bedrock Claude에서도, 오프라인의 로컬 MLX Qwen에서도 돈다.

### 온프렘, 완전 오프라인

온프렘 경로는 데모용 껍데기가 아니라 1급 시민이다. **로컬 Qwen 7B**(MLX 툴콜 프록시로 서빙)가 `프로비저닝 → 배포 → 검증` 전체 사이클을 ~39초에 돌리고, 실행을 로컬 JSONL에 기록하며, 대시보드는 이를 클라우드 DynamoDB 기록과 **하이브리드**로 병합해 한 화면에 보여준다. 롤백(앱 `rollout undo` 및 클러스터 teardown)도 완전 오프라인으로 작동한다. 인터넷도, 클라우드 계정도 없이 전체 라이프사이클이 돈다.

---

## 엔지니어링 스파인: 레퍼런스를 정직하게 채택하기

여기서부터가 관점이 담긴 부분이다. 우리는 공개된 AWS 레퍼런스 — **AWSome AI Gateway**(`aws-samples`, MIT-0), 가상 키·예산·멀티계정 Bedrock 라우팅을 갖춘 내부용 *LLM 프록시 게이트웨이* — 를 놓고 물었다. *제품 목적은 우리와 다른데, 이 중 플랫폼 운영 에이전트에 채택할 가치가 있는 패턴은 무엇인가?*

답은 LLM 프록시 부분이 아니라 **거버넌스·회복탄력성·오케스트레이션** 패턴이었다. 각각을 구체적 컴포넌트에 매핑해 티어 단위로 반영했다. 모든 기능은 **옵트인이며 비파괴적**이다 — 기본 동작은 그대로고, 운영자가 켤 때만 각 기능이 작동한다. 이 제약이 깨끗한 seam을 강제했고, 전부 오프라인 테스트 가능하게 만들었다.

### Tier 1 — 거버넌스 & 회복탄력성

**1. 정합성 게이트(reconciliation, deterministic-tool-first).** 질문 #1에 대한 직접적 답이다. 자율 `결정 → 실행`이 돌기 전에, 순수 파이썬 게이트가 분석기의 `severity`와 `root_cause`가 감지기의 증거 — 발화 중인 알람 상태, 메트릭, 로그, 그리고 주장된 근본 원인과 관측 증거 간의 토큰 중첩 — 에 실제로 *근거하는지* 검사한다. 결론이 근거 없으면 결정은 **AUTO에서 APPROVE로 강등**되어 사람이 검토한다. LLM은 제안할 수 있어도, 도구 결과에서 짚어내지 못하는 사실 위에서 **행동할 수는 없다**. Day-2 executor가 실제 `kubectl`을 치는 지금(`ONPREM_EXECUTOR_LIVE`), 이것이 마지막 방어선이다.

**2. 3단계 예산 게이트.** `evaluate_budget()`가 `PLATFORM_MONTHLY_BUDGET_USD` 대비 지출을 분류한다: `OK` → `SOFT_WARNING`(≥80%) → `THROTTLE`(≥100%, 승인 필요) → `HARD_BLOCK`(≥150%). 비용은 나중에 붙이는 게 아니라 정책 입력이다.

**3. 서킷 브레이커 + readiness 게이트.** `CLOSED / OPEN / HALF_OPEN` 브레이커(fail-fast + 폴백, 주입 가능한 clock으로 상태머신을 결정론적으로 테스트), 그리고 엄격한 `/health/ready`(의존성 다운 시 503)를 관대한 `/health`(200 liveness)에서 분리.

**4. 비용 서브메트릭.** 모든 트레이스를 도구별 호출 수·추론 스텝·토큰 사용량으로 집계해 활동 레코드에 첨부 — "그 자율 실행이 실제로 얼마 들었나"에 답할 수 있게.

### Tier 2 — 오케스트레이션 & 멀티계정

**#2 agents-as-tools + self-consistency.** 라우터는 결정론적 키워드 분류기(한 문장 → 한 전문가: provision/deploy/diagnostics, A2A로 위임)로 출발했다. Tier 2는 그 위에 오케스트레이터 레이어를 얹어 (a) **라우트를 투표**하고 — 분류기를 N회 샘플링해 다수결을 취함 — (b) **전문가를 도구처럼 체이닝**한다 — 복합 요청을 순서 있는 플랜으로 분해해 각 단계를 기존 위임 경로로 넘기고, 첫 실패에서 short-circuit하며, 단계 간 컨텍스트를 공유. 미묘한 부분은 **폴백**이다: 샘플 투표가 신뢰하기엔 너무 갈리면(합의가 임계 미만), 라우터는 추측하지 않고 결정론적 분류기로 되돌아간다. 이는 *정합성 게이트와 같은 철학*이다 — 결정론적 backstop이 근거 없는 모델 호출을 언제나 이긴다. 그리고 기본 샘플러가 *바로 그* 결정론적 분류기이므로, 실제 (LLM) 샘플러를 주입하기 전까지 기본값으로 켜도 아무것도 바뀌지 않는다.

**#3 MCP-over-HTTP 커넥터 + kill-switch.** 게이트웨이는 kubectl/docker를 단일 카탈로그로부터 MCP 도구로 노출한다. Tier 2는 *원격* MCP 서버(웹 검색, 외부 API)를 카탈로그 도구로 등록하는 `remote_mcp_tool()` 팩토리를 더한다: 핸들러가 로컬 tool-use를 가로채 JSON-RPC `tools/call`로 HTTP를 통해 원격에 보내고 결과를 재주입한다 — 원격이 죽어 있으면 예외를 던지지 않고 에러 결과로 degrade한다. 로컬이든 원격이든 모든 도구는 dispatch 시점에 검사되는 **도구별·전역 kill-switch**(`disable_tool`/`set_kill_switch` 또는 `MCP_DISABLED_TOOLS`/`MCP_KILL_SWITCH`)로 통제된다: 차단된 도구는 실행 없이 거부를 반환한다. 환경변수 하나로 특정 기능 — 혹은 게이트웨이 전체 — 를 끊을 수 있다.

**#4 크로스계정 STS AssumeRole + 우아한 폴백.** AWS 계정을 넘나드는 작업을 위해 `assume_role_session()`이 타깃 계정의 롤을 assume하고 임시 크레덴셜로 boto3 세션을 만든다. AssumeRole이 실패하면 — AccessDenied, 스로틀링, 깨진 trust policy — 혹은 반복 실패로 공유 서킷 브레이커가 이미 열려 있으면, 전체 작업을 실패시키는 대신 **in-account 크레덴셜로 우아하게 강등**한다. 회복탄력성을 재발명하지 않고 Tier 1의 서킷 브레이커를 재사용한다. 잘못된 계정에서 조용히 도는 것을 결코 허용하면 안 되는 호출자를 위해 `fallback=False`도 제공한다.

---

## 그 아래의 원칙들

기능 이름을 걷어내면, 같은 몇 개의 원칙이 반복된다.

- **모델 출력보다 결정론적 backstop.** 정합성 게이트와 self-consistency 폴백은 같은 규칙을 담는다: 모델이 근거 없거나 자기모순일 때는 결정론적 경로가 결정한다. LLM은 제안하고, 검증된 로직이 처분한다.
- **되돌리기 어려운 작업엔 승인 게이트.** `Delete / Drop / Terminate / teardown` — 클러스터 프로비저닝, 런타임 호스팅, 0으로 스케일 — 은 명시적 승인을 강제 통과한다. 자율 경로는 의도적으로 *되돌릴 수 있는* 부분집합(재시작, 롤백, 스케일업, PodDisruptionBudget을 존중하는 정중한 drain)이다. 게이트의 사람 쪽도 라이브다: P2 인시던트는 서명 검증되는 **Slack Approve/Reject 카드**로 파킹되고, 클릭 한 번이 멈춰 있던 Step Functions 실행을 재개한다 — 공개 콜백 URL이 없는 온프렘 파이프라인도 DynamoDB 결정 스토어를 공유해 같은 버튼 계약을 쓴다.
- **옵트인, 비파괴.** 모든 Tier 1/2 기능은 기본적으로 꺼진 채 나간다. 새 동작은 env 플래그나 주입된 의존성 뒤에서만 작동하므로, 채택이 기존 경로를 위협하지 않는다 — 회귀 테스트가 기본값 불변을 증명한다.
- **주입 가능한 seam, 오프라인 테스트 가능.** transport·STS 클라이언트·샘플러·clock·card-fetcher가 전부 주입 가능하다. 유닛 스위트에 moto도, 라이브 클라우드 요구도 없다 — 페이크를 모듈 레벨 seam에 monkeypatch로 꽂는다. 854개 테스트가 몇 분 만에 도는 이유다.
- **재발명보다 재사용.** Tier 1 회복탄력성용으로 쓴 서킷 브레이커가 Tier 2 크로스계정 폴백을 돌리는 *바로 그* 객체다. 패턴은 중복되지 않고 복리로 쌓인다.

---

## 검증 문화

위의 어떤 것도 실제로 돌려보기 전엔 "완료"가 아니다.

- **`make check` → 854 passed, 1 skipped.** 모든 기능은 테스트와 함께 도착하고, 게이트는 멀티파일 변경마다 돈다.
- **실제 클라우드에서 라이브.** 매니지드 에이전트 런타임 호스팅은 세 클라우드 모두에서 E2E 실증 — AgentCore·Vertex Agent Engine·Azure AI Foundry 각각 실제 `create → invoke/query → teardown`을 진짜 모델 응답과 함께 수행하고 즉시 삭제(각 $0.50 미만). 프로비저닝 패리티는 실제 AKS 클러스터로 실증(create → Ready → teardown).
- **실제 피어 대상 A2A.** 슈퍼바이저가 실제 kagent 에이전트(로컬 MLX Qwen)를 A2A로 발견·위임 — Agent Card 발견 → 스킬 매칭 → JSON-RPC 위임 → 실제 `k8s_get_resources` 진단이 돌아왔다. 이 라이브 실행은 관대한 사내 게이트웨이가 가리고 있던 스펙 준수 버그(필수 `messageId` 누락)까지 드러냈다.
- **결정론 가드레일 자체도 라이브.** 실제 MLX Qwen으로: 증거를 본 분석은 근거 있음(grounding 0.62)으로 AUTO 유지, 증거 없이 추측한 분석은 환각(0.08)으로 잡혀 APPROVE로 강등. 실제 HTTP로: 원격 MCP JSON-RPC 왕복과 dispatch 이전에 발화하는 kill-switch. 실제 STS로: 존재하지 않는 롤 AssumeRole 실패 → in-account 우아한 폴백.

---

## 같은 논지, 이제 플랫폼 벤더가 출시하다

우리가 이 가드레일들을 만든 건, 그것만이 에이전트에게 `kubectl`을 맡길 유일한 방법이었기 때문이다. 그런데 주요 에이전트 플랫폼들이 같은 결론으로 수렴하고 있다.

- **Google ADK 2.0**는 "Agentic Workflows"를 도입했다 — LLM은 진짜 추론에만 예약하고 라우팅·조건분기·에러핸들링은 결정론적 코드로 실행하는 directed-graph 런타임으로, 명시적으로 신뢰성을 얻고 실행 제어를 모델에서 분리해 prompt injection을 완화하기 위함이다. 이는 우리의 reconciliation 게이트와 self-consistency 폴백을 프레임워크 기본기로 재진술한 것이다: *결정론적 컨트롤 플레인, LLM은 인지에만.*
- **A2A 프로토콜**의 "zero context pollution"(특화 피어가 자기 state를 독립 관리해 주 에이전트의 컨텍스트 창이 오염되지 않음)은, 우리 위임이 각 특화 에이전트에 그 자신의 instruction만 보내고 A2A `contextId`를 (커지는 컨텍스트 블롭이 아니라) 상관관계 키로 다루는 이유와 정확히 같다.
- **Google `agents-cli`**는 빌드와 나란히 eval 루프(데이터셋 + LLM-as-judge + 최적화)를 1급으로 만든다 — 결정론적 *테스트*(우리 `make check`)와 *결정-품질 평가*가 별개 계층임을 상기시킨다. 후자도 이후 구현했다 — 오프라인 eval 하네스(멀티-grader 스코어카드)와 라이브 모델 스윕이 "라우팅엔 큰 모델" 가정을 측정으로 반증했다(7B가 30B보다 정확하고 빨랐다).

요점은 누가 사이드 프로젝트를 베꼈다는 게 아니라, 독립적인 팀들이 LLM에게 진짜 손을 쥐여줄 때 같은 결정론적 가드레일에 손을 뻗는다는 것이다. 수렴은 설계가 옳다는 좋은 신호지 신기함이 아니다.

*참고: Google Developers Blog — [Why we built ADK 2.0](https://developers.googleblog.com/why-we-built-adk-20/), [How A2A is building a world of collaborative agents](https://developers.googleblog.com/how-a2a-is-building-a-world-of-collaborative-agents/); [`google/agents-cli`](https://github.com/google/agents-cli).*

---

## 맺으며

에이전틱 플랫폼 도구의 표제 기능은 자율성이다. *출시 가능한* 기능은 신뢰다. `platform-agent` 엔지니어링의 대부분은 모델이 더 많은 도구를 호출하게 가르치는 데가 아니라, 그 호출들 **주변의 경계**에 들어갔다 — 결론을 증거에 근거시키고, 결정을 투표하고, 비용을 게이팅하고, 서킷을 끊고, 스위치를 내리고, 모델이 확신 없을 때 이기는 결정론적 경로를 언제나 남겨두는 것.

레퍼런스를 잘 채택한다는 건, 대부분을 무시하고 전이되는 소수의 패턴 — 거버넌스·회복탄력성·오케스트레이션 — 을 애초에 그것을 위해 쓰이지 않은 제품에 맞게 적응시키는 것이었다. 그 결과는 실제 인프라를 만지게 맡길 수 있는 에이전트다. 물어보지 않고 무엇을 해도 되는지, 미리 정확히 정해뒀기 때문이다.

---

*컴패니언 데모(약 20초, 전부 자연어): 온프렘 에이전트가 클러스터를 프로비저닝하고 배포하는 모든 도구 호출이 실시간으로 보이는 영상 — `docs/post/local-onprem-edited.mp4`.*
