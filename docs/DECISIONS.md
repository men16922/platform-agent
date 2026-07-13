# DECISIONS — platform-agent

최종 갱신: 2026-07-13

> 되돌리기 어려운 결정만. 형식: **Decision / Reason / Impact**. 최신이 위.

> **Future Reference (차용 후보, 결정 아님):**
> - **enterprise-ai-governance-dashboard** (외부 레포) — 2-Pass Fact NL→SQL 챗봇 + SQL self-heal 루프 + LLM SKU 그룹핑 + 최소권한 Cloud Run SA. 대시보드 챗봇/FinOps 확장 시 검토. 상세 → `docs/reference/enterprise-ai-governance-dashboard.md`. (검토 2026-07-13)

---

## D11 — 배포 추적 데이터 모델·IA: type/cluster 분류 + 롤백은 status(단일-row 승계) + teardown cascade

- **Decision:** activity 기록에 **`type`(provision/deploy)** 과 **`cluster`(연결키: deploy.cluster == provision.service)** 를 저장하고, **롤백은 별도 type이 아니라 status(`rolled-back`)** 로 표현한다(원본 행을 같은 `deployment_id`로 supersede = 단일-row). **cluster teardown은 그 클러스터의 deploy들을 자동 `rolled-back`으로 cascade**. 자연어(rollback_deployment/teardown_cluster)와 UI 버튼은 **동일 경로**(supersede/cascade)로 기록. 대시보드는 **Provisioning / Deployments / History** 3분리 + **통합 중첩 상세**(provisioning⊃deployments, 한 페이지). `provider`(aws/gcp/azure/onprem)와 `environment`(production/staging/dev)는 직교(더 이상 environment=provider 아님).
- **Reason:** 한 run이 provision+deploy 복합이라 단일 행으론 provisioning/deploy가 뭉개짐 → type 분리 + cluster 상관. 롤백을 type으로 두면 cluster 롤백이 Provisioning→Deployments로 새서 분리 원칙이 깨짐 → status로. 클러스터를 내리면 그 위 앱은 물리적으로 사라지므로 추적도 truthful하게 cascade. 자연어=UI 동일 결과라야 데모가 일관.
- **Impact:** `deploy_recorder`에 `type/cluster/environment`, `record_rollback`(supersede), `record_cluster_teardown`(cascade), `read_deploys`(최신, 동일 timestamp는 나중 우선) 추가. 읽기측 dedupe는 **latest-per-id**. 레거시 행은 `cluster` 없어 롤백 비활성. 대시보드 상세는 `getLifecycleDetail`(cluster로 엮음). 되돌리려면 기록 스키마·읽기 dedupe·페이지 3개를 함께 되돌려야 함.

## D10 — 2-역할 에이전트(Provision/Deploy) + Orchestrator+A2A + On-Prem Provision=Terraform/Ansible, Runtime=kagent

- **Decision:** ServiceSpec 기반 **① Provision(Day-0/1 IaC) + ② Deploy(Day-1 App)** 2-역할로 분리. 온프렘 Provision = **Terraform(kind, Mac Tier1) + Ansible(k3s, VM Tier2)**. 상위 통합은 **Orchestrator(supervisor) + A2A**(에이전트 상호운용) + **MCP 단일 도구 카탈로그**. On-Prem 에이전트 런타임 대응물 = **kagent(CNCF)**. 인터랙티브 에이전트는 현재 in-process 도구 사용(MCP Gateway는 A2A/외부용, 통합은 로드맵).
- **Reason:** "Platform Agent가 클러스터까지 셋업" 컨셉 충족 → 클러스터 프로비저닝을 에이전트 능력으로. 온프렘 IaC 표준 = Terraform(인프라)+Ansible(구성). AgentCore는 AWS 매니지드라 온프렘 불가 → kagent(K8s CRD, MCP/A2A)가 오픈소스 대응물.
- **Impact:** `adapters/provisioning/`(capability→환경별) + `provision_tools` + `infra/onprem/{terraform,ansible}` 추가. Deploy 어댑터(4-provider CodeBuild/Cloud Build/ACR Tasks/docker)는 유지. ARCHITECTURE 상단 통합 스택 표가 단일 레퍼런스. 미구현: 클라우드 Provision apply, Orchestrator+A2A 통합, kagent↔로컬LLM 연결.

---

## D9 — AI Model Router: 모델↔환경 분리, On-Prem = Pydantic AI + MLX

- **Decision:** LLM(두뇌)과 배포 환경(대상)을 분리하고 `model_router.py`가 (model×environment) 적합도 검증 후 라우팅. On-Prem 에이전트는 Strands 대신 **Pydantic AI + 로컬 MLX Qwen** 독립 구현(`local_deployer.py`). 프레임워크 = 각 클라우드 네이티브(aws=Strands, gcp=ADK, azure=MSFT, onprem=Pydantic AI).
- **Reason:** On-Prem에서 Strands는 Bedrock 이점 없이 MLX tool-call 포맷을 맞추는 proxy까지 요구 → "완전 오프라인" 서사와 상충. 배포 tools는 이미 provider-neutral이라 모델↔환경 분리가 자연스러움.
- **Impact:** 어떤 모델이든 어떤 환경에 배포 가능(적합도 배지로 표기). 대시보드 Agents 채팅이 `/api/models`+`/api/local-deploy`로 자연어 배포. 실행부(로컬 API)가 DEPLOY/ACTIVITY 기록 → 대시보드는 read-only 유지. `mlx_qwen_tool_proxy`는 프레임워크 중립 정규화(stream/non-stream)로 잔존.

## D8 — 문서·컨텍스트 하네스 도입 (harness.md 이식)

- **Decision:** "항상 읽는 작은 current docs" 와 "필요 시 여는 archive" 를 물리적으로 분리하고, `/sync`·`/checkpoint`·`/tidy-docs` skill 로 강제. 기존 도메인 문서는 `bin/docs/archive/` 로 전면 이관.
- **Reason:** 멀티세션·멀티에이전트에서 매번 작은 컨텍스트로 상태 복원. 시작 컨텍스트 = 비용·정확도.
- **Impact:** 세션 진입은 Read Path(CONTEXT_BRIDGE→AGENT_BRIEF→STATUS→NEXT_PLAN)만. 도메인 상세는 archive 링크로만 접근. docs/ 전체 bulk-read 중단.

## D7 — runbook catalog: 코드 fallback = DynamoDB seed 초기값 공유

- **Decision:** 단일 built-in catalog 를 코드 fallback 이자 `incident-runbooks` seed 초기값으로 동시 사용. exact `alarm_name` → catalog scan heuristic → 내장 → generic 순.
- **Reason:** 두 소스 이중 관리 제거, registry 비어도 동작 보장.
- **Impact:** catalog 변경이 fallback 과 seed 양쪽에 일관 반영. malformed override 는 `validate_runbook` 으로 무시+폴백.

## D6 — capability 기반 provider-neutral runbook

- **Decision:** 런북은 capability(`restart_workload` 등) 로 표현, executor adapter 가 provider action 으로 해석.
- **Reason:** 멀티클라우드 확장 시 control-plane 재사용.
- **Impact:** AWS 외 provider 추가가 adapter 교체로 가능.

## D5 — `Delete`/`Drop`/`Terminate` 액션 강제 APPROVE

- **Decision:** severity 와 무관하게 파괴적 액션은 무조건 approval 게이트.
- **Reason:** 자동 실행으로 인한 비가역 손실 방지.
- **Impact:** P1 AUTO 라도 파괴적 액션이면 사람 승인 대기.

## D4 — 실행은 SSM Automation (Lambda 직접 호출 아님)

- **Decision / Reason:** 감사 로그·승인 게이트·기존 운영 문서 재사용.
- **Impact:** Executor 만 `StartAutomationExecution` 권한 보유.

## D3 — LLM 은 Bedrock (외부 API 아님)

- **Decision / Reason:** VPC 내 호출, IAM 인증, 데이터 외부 전송 없음.
- **Impact:** Analyzer 만 Bedrock `InvokeModel` 권한.

## D2 — 알람 트리거는 EventBridge (SNS 아님)

- **Decision / Reason:** 이벤트 패턴 매칭, 다중 타겟, 필터링.
- **Impact:** alarm state change 를 EventBridge rule 로 캡처.

## D1 — 오케스트레이터는 Step Functions (SWF 아님)

- **Decision / Reason:** 시각적 디버깅, 재시도/에러 핸들링 내장, CDK 통합. (SAP: SWF vs Step Functions)
- **Impact:** 파이프라인은 `src/step_functions/pipeline.json`, CDK 와 동기 유지.
