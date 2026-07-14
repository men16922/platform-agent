# DECISIONS — platform-agent

최종 갱신: 2026-07-14

> 되돌리기 어려운 결정만. 형식: **Decision / Reason / Impact**. 최신이 위.

> **Future Reference (차용 후보, 결정 아님):**
> - **enterprise-ai-governance-dashboard** (외부 레포) — 2-Pass Fact NL→SQL 챗봇 + SQL self-heal 루프 + LLM SKU 그룹핑 + 최소권한 Cloud Run SA. 대시보드 챗봇/FinOps 확장 시 검토. 상세 → `docs/reference/enterprise-ai-governance-dashboard.md`. (검토 2026-07-13)

---

## D13 — 단일 도구 카탈로그는 레이어별로 둘 유지(게이트웨이 raw ↔ 인터랙티브 에이전트) — 병합 안 함

- **Decision:** "도구를 한 곳에만 선언하고 discovery+dispatch를 파생"하는 단일-카탈로그 규율을 **두 레이어에 각각 별도**로 적용한다. (1) 게이트웨이 `TOOL_CATALOG`(`ai/gateway/mcp_server.py`) = raw kubectl/docker MCP 핸들러(`ToolResult` 반환, A2A/외부 에이전트용). (2) 인터랙티브 에이전트 `AGENT_TOOL_CATALOG`(`ai/local_deployer.py`) = 상위 어댑터-백드 LLM-튜닝 도구(provision/deploy/investigate, dict 반환, Pydantic AI 스키마용 docstring). 후자에서 `ALL_OPS_TOOLS`(dispatch)와 시스템프롬프트 `## Tools` 인벤토리(discovery)를 둘 다 카탈로그에서 파생, drift-0 불변식 테스트로 강제. **두 카탈로그를 하나로 병합하지 않는다**(D10의 "인터랙티브↔MCP Gateway 통합은 로드맵"을 "레이어가 달라 통합 부적절"로 종결).
- **Reason:** 두 도구군은 추상화 레이어가 다르다 — 게이트웨이는 raw kubectl/docker 1:1 래퍼, 에이전트 도구는 provider-neutral 배포 어댑터를 오케스트레이션(`deploy_service`=build→push→deploy→validate)하고 LLM 컨텍스트용 출력 캡·docstring 스키마로 튜닝됨. 강제 병합하면 레이어를 뒤섞고 에이전트의 튜닝된 행위를 깨뜨림(회귀 리스크 큼). 얻으려던 실익(선언 1곳·discovery↔dispatch drift 제거)은 레이어별 카탈로그로 이미 100% 달성.
- **Impact:** 도구 추가 = 해당 레이어 카탈로그 1곳. 게이트웨이 `test_gateway`·에이전트 `test_local_deployer` 각각 drift-0 불변식 보유. 배포 경로를 게이트웨이 raw 카탈로그로 수렴하는 후속 리팩터는 **의도적 비채택**(레이어 혼합). 되돌리려면 두 카탈로그 파생 구조를 함께 손봐야 함.

## D12 — On-Prem Day-2 = PATH B webhook + in-process 4-step + 오프라인 승인 게이트 + 실 executor는 기본 OFF

- **Decision:** On-Prem의 이벤트 진입(PATH B)은 **FastAPI webhook**(`onprem_webhook_api`), 오케스트레이션은 **in-process 4-step 직접 호출**(`onprem_incident_pipeline`이 detector→analyzer→decision→executor 핸들러를 출력→입력 체인 — 클라우드의 Step Functions/Workflows/Durable Functions 대응). 승인은 **오프라인 JSONL pending 스토어**(`onprem_approvals`, deploy_recorder식 single-row 승계) + `/approve`(decision 재생 실행)·`/reject`. 인시던트는 **오프라인 JSONL 스토어**(`onprem_incidents`)에 기록하고 webhook `/incidents`로 노출 → 대시보드가 AWS+On-Prem을 **hybrid HTTP 병합**(승인 카드·타임라인, source 배지). **실 remediation(`onprem_runner`, kubectl)은 `ONPREM_EXECUTOR_LIVE`로 기본 OFF**(TESTING 시 강제 OFF), 켜도 **되돌리기-가능 4조치만** 자동 실행 — 각 조치는 "안전하지 않으면 스스로 물러난다"는 기준을 코드 가드로 강제: `rollout restart`/`undo` + `scale --replicas=N`(**양수 타깃일 때만**; 누락/0/비정수→log-only, scale-to-0=셧다운 가드) + polite `drain <node>`(**`--force`·`--delete-emptydir-data` 미사용** → kubectl이 PDB 존중·미관리/로컬데이터 파드 거부=실패→skip, NodeName 없으면 log-only). 공격적 force-drain은 의도적으로 사람 몫.
- **Reason:** On-Prem은 매니지드 오케스트레이터/DynamoDB/SFN이 없어 완전 오프라인이어야 함 → in-process 체인 + 파일 스토어. 대시보드는 Vercel-호환 위해 파일 경로 대신 webhook HTTP로 읽음(onprem-status 패턴 재사용). 자동 remediation이 임의로 클러스터를 변경하면 위험 → 기본 OFF + **되돌리기-가능하고 desired-state가 알림에 실려오며 위험 시 스스로 실패하는 액션만**이 안전 기본값(프로덕션 사고 방지). scale/drain은 각각 타깃 파라미터·polite 플래그 정책으로 이 기준을 충족시켜 편입.
- **Impact:** 신규 `onprem_webhook_api`/`onprem_incident_pipeline`/`onprem_approvals`/`onprem_incidents`/`operations/executor/onprem_runner`; executor `_run_external_action` onprem 분기가 stub→runner. `execution/onprem.py`가 ScaleWorkload에 `DesiredReplicas`(라벨)·DrainNode에 `NodeName`(라벨) 스레딩. 대시보드 `approval-data.ts`/`incident-data.ts` hybrid 병합 + `Incident.provider`에 onprem. `make dev-up`에 webhook 통합. 환경변수 `PLATFORM_{APPROVALS,INCIDENT}_FILE`·`ONPREM_WEBHOOK_URL`·`ONPREM_EXECUTOR_LIVE`. 되돌리려면 webhook·스토어·대시보드 hybrid·executor 분기를 함께 되돌려야 함. kind 라이브로 4조치 실증(rollout restart 파드 교체·scale 2→5·drain 노드 cordon+재배치 아웃티지0, 2026-07-14).

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
