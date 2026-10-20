# platform-agent 실사용 검증과 AI 운영 에이전트 발전 계획

작성·공개 자료 조회: 2026-10-03 · 재개: 2026-10-20. 조사/계획 및 T 실행 반복·전달물 완료, 객체 일관성 수정·모델 대조 진행. 진단/R3/R4 전체·R5 미완료.

## 1. 목표와 우선순위

**단일 로컬/온프렘 환경의 배포·검증·복구 흐름을 본인이 반복 사용할 수준으로 완성한다.** 이후 실제 장애 사례에서 얻은 근거와 평가 결과로 진단 품질을 높이고, 검증된 경로만 AWS로 확장한다. 새로운 클라우드나 프레임워크를 추가하는 일은 현재 목표에 포함하지 않는다.

제안하는 제품 방향은 **사용자가 변경 근거·실행 신원·결과를 확인하고, 실패해도 같은 작업의 상태를 추적할 수 있는 플랫폼 운영 에이전트**다. 오프라인 모델과 기존 온프렘 경로는 출발점이다. 이것이 시장에서 유일하다는 주장은 하지 않는다. AWS DevOps Agent도 멀티클라우드·온프렘 조사를 제공하므로, 지원 환경 수만으로 차별성을 설명하기는 어렵다는 판단이다. [AWS GA 발표, 2026-03-31](https://aws.amazon.com/blogs/mt/announcing-general-availability-of-aws-devops-agent/)

우선순위는 **R0 준비 상태 확인 → R1 사용자 흐름 재현 → R2 관측된 병목 수정 → R3 동일 조건 재검증**이다. 기존 Phase 5 운영 연결은 별도 원격 우선순위로 유지한다. 그 승인이 대기 중이어도 로컬 준비 상태 확인과 평가 설계는 진행할 수 있다. Phase 4b는 기존 비용·기간·종료 조건을 유지한다.

## 2. 사용자 피드백을 현재 저장소와 대조한 결과

기준은 이번 세션에서 읽은 09-15 진입 문서와 아래 코드다. 문서의 과거 실증과 현재 코드 존재를 구분했으며, 조사 단계에서는 클러스터·모델·브라우저 사용자 흐름을 재실행하지 않았다. 후속 실측은 §8의 증거에 따로 기록했다.

| 피드백 또는 현황 | 현재 근거 | 계획에 반영할 내용 |
| --- | --- | --- |
| 기초 MVP를 새로 만들 단계가 아니다 | `docs/AGENT_BRIEF.md` Snapshot에 Operations·온프렘 배포·검증·롤백·대시보드 실증 기록 | 사용자 경로를 먼저 재현하고 발견한 문제만 수정 |
| attach UI 전에 Python 실행 위치 결정이 필요하다 | **09-03 기준의 오래된 조건**. `2026-09-05-phase5-planner-runtime.md` §1·§8·§12에 독립 Lambda와 UI/저장/준비/상태 연결이 있고, M91은 배포 후보 검증까지 기록 | 실행 위치·UI를 다시 설계하지 않는다. 미완료는 운영 연결·실제 Invoke·발행 경계 |
| 스코프와 배포 신원은 옵트인이다 | `src/agents/platform/scope.py`는 scope 없이 live 조치를 거부. `deploy_identity.py`는 설정이 없으면 경고 후 ambient kubeconfig 사용 | 둘을 같은 안전 상태로 요약하지 않는다. 실사용 측정 전에 실제 적용 신원을 확인 |
| 제한된 배포 신원이 곧 테넌트 격리는 아니다 | `deploy_identity.py`는 공통 deployer이며 테넌트를 나누지 않는다고 명시. 라우터 인증·결정 5 C/D가 남아 있음 | 단일 사용자 실험 범위를 명시. 클라우드 전체/모든 테넌트 격리로 확대 주장하지 않음 |
| 승인·평가·사후 검증을 추가해야 한다 | `reconciliation.py`, `eval_harness.py`, `onprem_verify.py`, `state_store.py`, `scripts/demo/README.md`가 이미 존재 | 현재 실행 경로에서 사용되는지 확인한 뒤 재사용. 별도 평가 플랫폼·승인 엔진을 먼저 만들지 않음 |
| 구현과 사용 사이에 간극이 있다 | Phase 5는 `published=false`, 실제 PR 연결은 미완료. 온프렘 최신 사용성 지표는 이번 세션에서 미측정 | 완료 시간·수동 개입·상태 불일치·복구 결과를 새 기준선으로 측정 |

`reconciliation.py`의 어휘 중첩과 신호 검사는 환각 징후를 거르는 장치다. **근본 원인의 인과관계를 증명하는 기능으로 해석하지 않는다.** 새 진단 기능이 필요하다는 결론도 장애 재현 결과를 보고 내린다.

## 3. 관련 AI 에이전트 조사와 채택 판단

공식 제품 문서·프로젝트 문서를 우선했다. 제품 소개의 성능 수치는 독립 재현 결과가 아니므로 비교 점수나 이 프로젝트의 목표치로 쓰지 않았다. 날짜 없는 문서는 조회일 기준 자료이며, 설치된 버전의 기능 보장을 뜻하지 않는다.

| 대상과 역할 | 공식 자료에서 확인한 내용 | platform-agent에 대한 판단 |
| --- | --- | --- |
| **AWS DevOps Agent** — 관리형 운영 동료 | 03-31 GA. 조사에 텔레메트리·코드·배포 정보를 결합. 08-25 directed actions, 09-04 조사 피드백 reflections가 변경 이력에 기록. 변경 조치는 도구·작업·자원에 묶인 승인과 추적을 사용. [GA](https://aws.amazon.com/blogs/mt/announcing-general-availability-of-aws-devops-agent/) · [변경 이력](https://docs.aws.amazon.com/devopsagent/latest/userguide/whats-new.html) · [실행 경계](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-working-with-directed-actions.html) | **즉시 반영할 방식:** 변경 이력과 관측 근거를 같은 사용자 흐름에서 제시. **조건부:** AWS 단계에서 같은 장애를 수동 조사/우리 에이전트와 비교. 서비스 도입·과금 호출은 이번 계획의 실행 아님 |
| **Azure SRE Agent** — Azure 운영·조사 | Review/Autonomous를 구분. Review 승인 UI는 Azure 인프라 조치에 적용되며 이메일·Teams 등에는 별도 Hooks/Tool Access Policies가 필요. 전역 기본값과 response plan/task 기본값도 구분. [개요, 갱신 08-27](https://learn.microsoft.com/en-us/azure/sre-agent/overview) · [실행 모드](https://learn.microsoft.com/en-us/azure/sre-agent/run-modes) | **즉시 반영할 방식:** '승인 모드'라는 이름 대신 실제 도구·진입 경로별 집행 여부를 측정. Azure 어댑터 추가·교체는 보류 |
| **HolmesGPT** — 도구 기반 장애 조사 | 장애에 맞는 runbook을 가져와 단계별 조사·완료/생략 결과를 보고. 공개 평가 문서는 회귀·난도별 시나리오와 모델 비교를 제공. [runbooks, 0.23.0 문서](https://holmesgpt.dev/0.23.0/reference/runbooks/) · [평가](https://holmesgpt.dev/latest/development/evaluations/) | **우선 참고:** 기존 runbook과 `eval_harness.py`에 실제 실패 사례를 연결. 외부 비교는 진단 품질이 병목으로 확인될 때 HolmesGPT 하나부터, 동일 입력·권한·모델 조건으로 수행 |
| **kagent** — Kubernetes 에이전트 실행·위임 | 현재 1.x 문서는 **alpha**. MCP binding의 `requireApproval`과 이를 협상하는 클라이언트가 모두 있어야 HITL이 완결. 문서는 CLI의 승인 응답 미지원도 설명. [HITL](https://kagent.dev/docs/kagent/1.x/agents/human-in-the-loop/) | 기존 kagent/A2A 경로를 그대로 기준선으로 고정. 도구 승인 선언만 보고 종단 간 동작을 주장하지 않음. 1.x 전환은 현재 버전에서 재현된 병목과 호환성 근거가 있을 때 검토 |
| **K8sGPT** — Kubernetes 상태 진단 | CLI가 namespace/filter로 분석 대상을 제한하고 `--explain`으로 설명을 제공. [CLI](https://docs.k8sgpt.ai/reference/cli/) | 좁은 K8s 장애의 읽기 전용 비교 후보. 필터는 자격증명 격리의 대체물이 아니며 문서만으로 배포·복구 전체 흐름과 동등하다고 평가하지 않음 |
| **incident.io Investigations** — 사고 대응 흐름에 결합된 조사 | 제품 문서는 텔레메트리·변경·과거 사고를 연결하며, 시스템 변경은 사람이 검토·병합하는 PR로 제한한다고 설명. 이는 공급자 설명이며 직접 검증하지 않음. [제품 동작 범위](https://incident.io/solution/ai-sre) | 진단 근거→검토 가능한 변경안 연결을 참고. 새 Slack 봇·외부 SaaS 도입은 보류하고 기존 대시보드의 흐름부터 검증 |

위 자료에서 읽히는 방향은 다음과 같다. 아래 '적용'은 자료에 대한 설계 판단이다.

1. **운영 맥락을 연결한다.** 조사 결과에 배포 revision·최근 변경·관측 시각·근거를 붙인다. 먼저 기존 activity/incident 기록으로 충분한지 확인한다. 별도 토폴로지 DB나 지식 그래프는 필요성을 측정한 뒤 검토한다.
2. **통제를 실제 도구 호출에서 집행한다.** AgentCore Policy는 Gateway를 통과하는 호출에 결정론적 정책을 적용한다. 적용 범위 밖 도구까지 보호한다고 확대 해석하지 않는다. 우리 프로젝트는 기존 Guardian·scope·배포 신원 경로의 누락부터 찾는다. [AgentCore Policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)
3. **작업 결과로 평가한다.** AgentCore 평가 문서는 trace/tool/session 평가와 코드 기반 평가를 구분한다. 우리 프로젝트는 실제 상태·권한 거부·중복 실행 여부를 결정론적으로 확인하고, 설명 품질만 보조 모델 평가 대상으로 둔다. 관리형 평가 서비스 도입은 선행 조건이 아니다. [평가 구성](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-evaluator.html)
4. **메모리는 검증된 사례에서 시작한다.** AWS의 reflections 흐름은 참고하되, 우리 사례에는 원인 근거·적용 조건·revision·검증 시각·반례를 함께 보관한다. 자동 학습으로 권한이나 실행 정책을 바꾸지 않는다. 초기에는 검토된 runbook/사례 파일로 충분하다는 제안이다. [09-04 변경](https://docs.aws.amazon.com/devopsagent/latest/userguide/whats-new.html)
5. **프로토콜 변화는 호환성 과제다.** MCP 2026-07-28에서 Tasks가 확장으로 이동했다. A2A는 작업별 인가 경계를 구현체가 집행하도록 요구한다. 우리 저장된 request_id/상태 조회 계약을 유지하고 실제 호출 상대의 버전·기능을 먼저 확인한다. 최신 SDK 일괄 교체는 하지 않는다. [MCP 발표](https://blog.modelcontextprotocol.io/posts/2026-07-28/) · [A2A 인가](https://a2a-protocol.org/latest/specification/)

## 4. 실행 계획과 완료 조건

아래 소요일은 **집중 작업 기준 추정**이며 환경 준비·사용자 응답 시간은 제외한다. 당초 계획 작성 단계에서는 클러스터 변경·배포·장애 주입을 실행하지 않았다. 후속 실행 진행 상태는 §8에 기록하며 새로운 `[auto]` 씨앗은 등록하지 않는다.

| 순서 | 범위와 첫 행동 | 산출물·완료 조건 | 재사용 위치 | 추정 |
| --- | --- | --- | --- | --- |
| **R0 — 비변경 사전 점검** | 기존 로컬 kind/온프렘 후보 중 하나, tenant/env 하나, 기존 서비스 하나를 선정. 프로세스·모델·context·신원·복구 대상·현재 설정을 읽기만 해서 확인 | 실행 가능/설정 필요/범위 결정 필요 목록, WIP 포함 후보 manifest, 실행 대상과 중단 조건이 있는 짧은 재현 절차 초안 | `Makefile`의 `dev-status`, `platform/tenants/acme.yaml`, `deploy_identity.py`, scope 관련 probe | 0.5~1일 |
| **R1 — 수정 전 사용자 흐름** | 같은 후보로 기존 대시보드에서 요청→변경 확인→배포→상태 확인→장애 인지→복구를 수행. 정상·거부·실패·응답 유실을 아래 시나리오로 관측 | 원본 관측 기록, 수동 개입/시간/불일치 목록. 실패한 단계도 결과로 남기고 우회하지 않음 | 기존 deployment/operations 어댑터, `onprem_verify.py`, `scripts/demo/README.md` | 1~2일 |
| **R2 — 관측된 병목만 수정** | R1에서 반복 사용을 막은 문제 중 영향이 가장 큰 하나부터 reproduce→measure→fix→re-measure. 문제 없으면 수정 없이 R3로 이동 | 해당 문제의 재현·전후 증거, 필요한 회귀 검사, 전체 게이트 통과. 화면 문제면 실제 저장·새로고침까지 확인 | 기존 코드 경계 안에서 수정. 기본값/권한 정책 변경은 별도 결정 | 문제당 0.5~2일 |
| **R3 — 반복 사용 판정** | 같은 시나리오·동일 후보 조건으로 전후 비교. 정상 흐름은 상태 복원 후 3회, 거부·복구·유실은 각 2회씩을 초기 목표로 수행 | 아래 필수 기준을 모두 만족한 시나리오 묶음, 재현 절차, 짧은 데모, 전후 비교표. 반복 수는 작은 로컬 표본이며 신뢰도 추정치가 아님 | 기존 evidence 형식·데모 파이프라인 | 1~2일 |
| **R4 — 사례 기반 진단 개선** | R1~R3에서 모은 실제 실패와 비슷하지만 원인이 다른 사례를 평가 입력으로 정리. 별도 엔진 대신 기존 평가 하네스 확장 필요성을 먼저 판단 | 출처/관측 시각/정답 근거가 있는 사례, 보류해야 하는 입력, 기존 수동 절차 대비 설명·도구 선택 평가 | `eval_harness.py`, `runbooks/`, `reconciliation.py` | 첫 묶음 2~3일 |
| **R5 — 검증된 범위 확장** | R3 통과 후 추가 확장 방향 하나를 선택: Phase 5 결과를 사용자 흐름에 연결하거나 진단용 외부 에이전트 비교 | Phase 5는 기존 §13의 실증 결과, 외부 비교는 동일 조건 보고서. 둘을 동시에 벌이지 않음 | Phase 5 동결 후보 또는 기존 kagent/A2A seam | 범위 확정 후 산정 |

### R0에서 확정할 경계

- 재현용 툴체인의 실행부터 확인한다. 이번 문서 검증에서 기본 Homebrew Node 26은 `libsimdutf.34.dylib` 누락으로 시작하지 못했다. Node PATH만 지정해도 `npx`가 전역 bin 경로를 앞세워 같은 오류가 남았다. 기존 Node 22.23.3·npm/npx·프로젝트 TypeScript 5.9.3을 임시 prefix에 묶어 npm offline 실행을 확인했고, 관련 검사 131개와 후속 59개가 통과했다. 전역 설정을 바꾸지 않았으며 R0에서도 실제 실행 버전과 경로를 기록한다.
- 우선 후보는 레지스트리에 기록된 `kind-platform-agent`다. 지금 존재·정상 동작한다고 가정하지 않는다. `k3s-lab`은 기존 재개 조건을 충족할 때만 선택하고 새 클러스터 생성으로 자동 전환하지 않는다.
- '깨끗한 환경'은 기존 WIP를 지우는 뜻이 아니다. HEAD와 필요한 WIP의 경로·해시를 기록해 격리된 후보로 재현한다. 코드·의존성·모델·설정 이름을 고정하고 비밀 값·키·기존 실행 데이터는 복제 대상에서 제외한다. HEAD만 내보내고 미커밋 플래너가 검증됐다고 주장하지 않는다.
- `make dev-status` 같은 조회와 `make dev-up`/`demo-baseline`/촬영 준비 스크립트의 변경 효과를 구분한다. 기존 데모 스크립트를 읽지 않고 실행하지 않는다. 공유 프로세스 종료·자원 초기화가 필요하면 실행안에 구체적으로 적는다.
- scope 및 deploy identity 검사 결과를 따로 기록한다. 배포 신원 누락·예상 밖 대상·복구 revision 부재이면 변경 테스트를 시작하지 않는다. 이 실험의 시작 조건을 엄격히 하는 것과 D38/D39 전역 기본값 변경은 별개다.
- 정상 동작 비교에 사용할 기존 서비스와 readiness/health 관측을 고른다. 애플리케이션 데이터·DB migration이 없는 변경만 초기 범위로 삼는다. 단순 rollback이 데이터 복구까지 보장한다는 가정을 피한다.
- 신원 확인에는 credential 자체가 아닌 식별자·허용/거부 결과를 남긴다. 기존 probe 출력도 승인 서명·환경 비밀이 섞이는지 먼저 검토하고 정제한다.

### R1과 R3의 시나리오

| 시나리오 | 실제 사용자 경로에서 확인할 것 | 판정 |
| --- | --- | --- |
| 정상 배포 | revision·대상·실행 신원·배포 결과·실제 readiness와 서비스 health. 대시보드 새로고침 후 동일 실행 추적 | 완료 표시는 실제 상태와 일치하며 다른 대상 변경 없음 |
| 허용되지 않은 요청 | 다른 tenant/namespace의 비민감 대상에 대한 제한 신원의 읽기·쓰기 거부와 자원 불변. scope 없는 조치·승인 거부 경로도 확인 | 거부가 UI/API/실제 자격증명 경계에서 구분되어 기록됨. 공유 deployer의 한계는 미증명으로 남김 |
| 배포 실패와 복구 | 명시한 실험 workload에 실패하는 revision 적용 후 기존 복구 경로 수행. 복구가 자동인지 수동인지 기록 | 알려진 이전 revision·health 복구와 실패 이력이 함께 남음 |
| 응답 유실·새로고침 | 실행 후 응답만 끊고 같은 작업을 조회. 해당 경로에 조회/중복 방지 기능이 있는지 먼저 확인 | 성공 여부 불명은 미확인으로 표시, 무조건 재실행하지 않음. 기능 부재면 R2 병목으로 기록 |
| 근거 부족·잘못된 진단 | 오래된 로그, 다른 서비스의 로그, 유사 증상의 다른 원인, 로그 안의 실행 지시문을 제공 | 불충분함을 밝히고 권한·실행 범위를 넓히지 않음. LLM 자기 확신을 정답 근거로 쓰지 않음 |

위 시나리오의 실패 주입·실제 변경은 R0에서 정한 실험 대상과 범위 안에서 수행한다. 타 테넌트 거부 검증은 실제 비밀 데이터를 읽는 방식 대신 비민감한 확인 대상과 거부 응답을 사용한다. AWS 서비스 통합 검증이 필요해지면 저장소 규칙대로 LocalStack 또는 지정 AWS 테스트 계정을 사용한다.

### 측정 정의와 완료 기준

| 지표 | 측정 방법 | 초기 완료 기준 |
| --- | --- | --- |
| 사용자 개입 | 필요한 명시적 승인과 계획 밖 shell/설정 수정/재입력을 따로 집계 | 계획 밖 개입 0인 정상 반복 경로 확보. 승인을 줄이려고 통제를 없애지 않음 |
| 완료·복구 시간 | 사용자 요청~실제 health 확인, 실패 감지~이전 revision health 회복. 승인 대기와 실행 시간을 분리 | 개선 전후 모든 실행값·중앙값·범위 공개. 측정 전 임의의 단축률 목표 없음 |
| 상태 일치 | UI/API 결과와 실제 revision·health 및 조회 결과를 대조 | 검증 묶음에서 거짓 성공 0. 미확인 상태는 실패와 구분 |
| 권한과 중복 | 거부 요청의 자원 전후 상태, 응답 유실 뒤 외부 실행 횟수 | 검증 묶음에서 범위 밖 변경 0·중복 변경 0. 로컬 결과를 클라우드 격리 증거로 전용하지 않음 |
| 증거 연결 | 실행 ID로 요청·판정·신원·실행·검증·복구 관측을 따라갈 수 있는지 | 모든 시나리오에 누락 없이 연결. 기존 ID/기록 우선 사용 |
| 모델 기여와 비용 | 같은 작업을 기존 CLI/runbook 수동 절차와 비교. 모델/설정·호출 수·토큰·오류·지연 기록 | 모델 추가가 실제 작업을 돕는지 판단 가능. 로컬 모델도 실행 시간·자원 비용이 0이라고 표현하지 않음 |

작은 표본으로 운영 SLO나 일반적인 MTTR 개선률을 주장하지 않는다. 기본 전달물은 **60~90초 데모 한 편, 재현 절차 한 개, 원본 근거에 연결된 전후 비교표 한 개**다. 영상은 관측을 설명하는 자료이며 검증 자체를 대신하지 않는다.

## 5. 기존 우선순위와의 연결

| 기존 작업 | 유지할 범위 | 이 계획과의 관계 |
| --- | --- | --- |
| Phase 5 저장형 플래너 운영 연결 | `docs/plans/2026-09-05-phase5-planner-runtime.md` §13의 자원·인가·Vercel 전환·복구·보관 비용 | 원격 작업 중 우선순위 유지. 승인 후 기존 §13대로 독립 진행하며 신원·후보·복구 대상을 재확인. R3 통과를 기존 배포 승인의 추가 조건으로 만들지 않음 |
| PR writer | §5·§12의 권한 경계, 실험 부분 판정, `published=false`와 CLAIMED 의미 | 자동 PR/merge를 새 목표로 묶지 않는다. 실제 발행을 실증할 때 별도 완료 기준 적용 |
| 스코프·배포 신원 | D38/D39와 결정 5 C/D, 라우터 인증 선행 | 로컬 세션의 적용 상태부터 측정. 전역 fail-closed 전환·멀티테넌트 인가는 변경 효과를 검토한 별도 결정 |
| Phase 4b | 비용·기간·종료 장치와 자격증명 파티션 | 이번 계획 때문에 재개하지 않음. 단일 환경 사용성이 입증되고 필요성이 생길 때 다시 평가 |
| 기존 lab/App·키·branch·draft PR·checkout | 사용자 보존 지시 유지 | 데모 환경 정리나 후보 재생성의 명목으로 삭제하지 않음 |

## 6. 중기 방향과 도입 조건

첫 1~2주에는 R0~R3를 목표로 삼되, 실제 환경 문제가 있으면 기간보다 판정 조건을 우선한다. 이후 2~4주에는 실패 사례를 R4 평가에 연결한다. 4~6주 이후 확장은 아래 조건 중 하나를 충족할 때만 시작한다. 모두 작업량 추정이며 완료 약속이 아니다.

- **진단 품질이 병목:** HolmesGPT를 읽기 전용 비교 대상으로 하나만 선정. 같은 장애 snapshot·권한·도구 예산을 사용한다. 모델을 맞추지 못하면 모델과 에이전트 효과를 분리할 수 없다고 적는다. 비교가 끝나기 전 production adapter를 추가하지 않는다.
- **상태 추적이 병목:** 기존 JSONL/SQL state store와 request_id 계약을 연결하는 최소 변경부터 검토. 일반 목적 durable workflow 엔진이나 벡터 DB를 도입하기 전에 기존 저장소의 누락을 재현한다.
- **반복 지식이 병목:** 검증된 사건의 적용 조건·증거·유효기간·반례를 runbook에 추가. 메모리의 권고와 현재 환경 조회를 구분한다. 자기 생성 메모리만으로 자동 조치를 승격하지 않는다.
- **위임이 병목:** 기존 kagent/A2A의 timeout·인증·작업 조회·승인 응답 호환성을 먼저 측정한다. MCP 인증에서 token passthrough를 금지하는 공식 지침을 참고하고, 클라이언트/서버/다운스트림 신원을 구분한다. [MCP 보안 지침](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)
- **AWS 운영 사용이 다음 가치:** 기존 Phase 5 실행안부터 완료. AgentCore Policy/Evaluations나 AWS DevOps Agent 연계는 그 뒤 도구 경계 또는 진단 비교에 구체적 이점이 있을 때 검토한다. Step Functions·CDK·Python 기반을 교체하지 않는다.

SAP 관점에서도 기존 서비스 선택을 유지할 이유가 있다. Step Functions는 실행 단계와 실패 처리를 명시하고, IAM·자격증명 경계는 변경 범위를 제한하며, 실제 검증·복구는 Reliability 근거가 된다. 이 계획은 이를 한 사용자 흐름에서 관측해 Operational Excellence를 확인하고, 제한된 실험 범위로 비용을 통제하려는 제안이다.

## 7. 지금 하지 않을 일과 재개 신호

| 보류 항목 | 재개할 근거 |
| --- | --- |
| 새 클라우드·프레임워크·에이전트 수 확대 | 단일 환경 흐름이 통과했고 기존 도구가 해결하지 못하는 사용자 작업이 있음 |
| kagent alpha/MCP 최신판 일괄 전환 | 현재 고정 버전의 재현된 문제, 필요한 기능, 호환성·복구 검증 |
| 전면 재설계·새 control plane·범용 지식 그래프 | 기존 구조의 반복된 병목과 작은 수정으로 해결되지 않는 증거 |
| 광범위 자동 복구·자동 PR merge | 작업별 권한·idempotency·실제 복구·운영 범위가 입증되고 명시적 운영 결정이 있음 |
| 테스트 개수 늘리기·벤더 성능 수치 복제 | 테스트는 발견된 결함을 검출할 때만 추가. 성능은 동일 조건으로 직접 측정 |
| GitAIOps 후속편 집필·발행, Phase 4b 상시 운영 | 각각 기존 사용자 지시와 별도 재개 조건 충족 |

## 8. 다음 세션의 정확한 시작점

**현재 목표는 사용자 요청으로 일시중지다(2026-10-03 checkpoint).** 다음 재개 지시 전 구현·실험을 수행하지 않는다. 로컬 dogfood 승인은 이미 있었으며 중지 이유를 승인 대기로 바꾸지 않는다. 아래는 기존 기록의 압축이며 새 실측이 아니다.

| 항목 | 현재 판정과 권위 |
| --- | --- |
| 조사·계획 | 완료. §1~§7의 방향·범위·기존 우선순위 유지 |
| 배포·거부·복구·유실 | T 실행 O/v15에서 정상3·거부2·수동 복구2·실행 중 새로고침2 완료. 각 요청 claim1/deploy1 |
| 거부 상세 연결 | 합성 승인 거부2의 개행/빈 사유·APR↔INC·실행0 확인. alert/분석 E2E는 아님 |
| 전달물 | T 보고서의 재현 절차·전후표와 72초 정지화면 데모 완료. evidence README의 T 항목 |
| 진단/R3/R4 전체 | 미완료. 형식·source 인용 통과와 의미 정확성은 별개. O/S의 원인·현재 상태·삽입 지시 오류 유지 |
| R5 | R3 이후 동일 저장 snapshot의 읽기 전용 HolmesGPT 비교. 미설치/미호출, 운영 연결 없음 |
| 코드/실행 | 실행 O/v15, 작업 트리 R/v16 각각287소스. R은 미활성화, S 응답 계약은 미채택 |
| 마지막 workload 관측 | 10-03 13:12 UTC. 시작 UID/전체 spec/r0/replicas2 복원, revision37. U에서는 재조회하지 않음 |
| 최근 전체 게이트 | T 작업 트리R: 3364 passed·2 skipped·20 warnings,133.83초. 로컬 macOS·Python3.13.5·Node22.23.3/임시prefix. O 자체의 앞선3356/2와 구분 |

### 재개 후 첫 작업

1. `docs/evidence/dogfood-20261003/repeats/u-diagnosis-checkpoint.json`과 Q/S의 raw 관측을 읽는다. U는 코드/공식 문서 검토까지만 수행했으며 새 재현·수정·모델 호출은 없다.
2. 집계 수치와 RS/Pod 불일치를 일관된 양성 복구 대조군과 함께 재현한다. `rollout_complete`가 집계만 검사하는 코드 경로는 발견했지만, 원인 확정에 필요한 새 구분 측정은 미실행이다.
3. 확인된 관측 모순 판정과 현재 revision/실패 단계의 조회 적용 조건만 고친다. Q의 시작 전 Pod 로그 제안, S의 복구 후 이미지 실패 제안·모순 누락을 같은 원본으로 대조한다.
4. 원문·양성 복구 후보·삽입문/유사 증상/근거 부족 기준을 유지한다. 잘못된 문장을 숨기거나 전건 보류·프롬프트 반복으로 성공을 만들지 않는다. 이미 완료한 T 묶음/데모는 반복하지 않고 다음 변경에 필요한 검증만 수행한다.

### 증거를 읽는 위치와 한계

기준 폴더는 `docs/evidence/dogfood-20261003/`다. 상세 보고서의 인용과 원본 hash를 따라가며, 새 관측으로 과거 snapshot의 누락을 보충하지 않는다.

| 자료 | 입증하는 것과 남은 한계 |
| --- | --- |
| `repeats/t-integrated/verification.json` 및 report | 같은 실행 후보의 반복·복구·상태 연결, 재현/비교. 정상 클릭→Pod health 중앙값13.892초(3건); 서버 구간4.004초. 일반 성능/MTTR 아님 |
| `demo/t-integrated-v2/` | 실제 화면4장·72초 편집본·QA. 연속 녹화나 작업시간 측정 아님 |
| `repeats/snapshot-contract-verification.json` | O 실제 snapshot의 대상/시각 적용7/7·모델 인용3/3. 의미 충족1·부분1·실패1; 제외4건은 모델 정확도 분모가 아님 |
| `repeats/revision-window-verification.json` | Q 실제 실패/복구 revision별 자료와 읽기 전용 조사. 누락 waiting 원문과 불필요한 로그 제안의 근거 |
| `repeats/pod-diagnostics-verification.json` | R의 원문/source/Pod 연결 코드 검증. 실제 재생의 삽입문 오류로 실행 반영 보류 |
| `repeats/proposal-contract-review.json` | S 세 계약/실제 응답18개. 마지막 형식5/6, 의미 충족1·부분1·실패3·형식실패1. 미채택 |
| `repeats/u-diagnosis-checkpoint.json` | 코드 검토 가설·미실행 범위·일시중지·재개 지점 |

T의 health는 current Pod liveness200 로그다. 외부 Service/의존성 검사가 아니며 이전 Pod가 생존해 outage를 주장하지 않는다. r0/r1은 같은 캐시 digest다. 제한 tenant SA의 globex 거부와 공통 deployer의 격리는 다르다. `reported_by`는 호출자 기록이며 webhook 인증 증거가 아니다. 모델 해석 검토자는 코딩 에이전트이고 독립 전문가/심사 모델이 아니다.

### 승인·보존 경계와 과거 기록

기존 로컬 승인과 별개로 Phase5/4b 원격 실행·비용 범위를 유지한다. 같은 로컬 승인을 다시 묻거나 curl 재로드를 모든 작업의 선행 조건으로 두지 않는다. 과거 특정 curl/health 탐색 차단을 다른 수단으로 우회하지 않는다. 같은 SA 토큰 갱신은 기존 권한 범위이며 RBAC 확대가 아니다.

기존 lab1367338348·checkout 및 R2 lab/App4924748·설치161238144·키·branch·draft PR을 보존한다. 기존 demo prep의 namespace/Applications 삭제는 이 실험에 사용하지 않는다. 커밋/푸시·클라우드/RBAC 변경·기존 자원 삭제를 자동 재개하지 않는다.

후보 A~U의 단계별 수정·실패·재시도·과거 다음 행동은 [정리 전 §8 원문](../archive/progress-2026-10.md#tidy-20261003-usage-plan)에 그대로 보존했다. [실측 증거 색인](../evidence/dogfood-20261003/README.md)과 `docs/COMPLETED_SUMMARY.md`의 10-03 완료 범위를 함께 사용한다. 과거의 active/계속 진행 문구는 당시 이력이며 현재 일시중지 지시를 대신하지 않는다.

## 9. 2026-10-20 재개 — 객체 일관성 수정과 남은 모델 오류

사용자의 “잔여 작업 완료시까지 수행” 지시로 로컬 작업을 재개했다. §8의 일시중지는 과거 checkpoint이며 현재 지시가 아니다. T 반복·전달물은 재실행하지 않았다. Phase5/4b·기존 자원 보존·커밋/푸시 경계는 유지한다.

- **원인 재현:** `docs/evidence/diagnosis-20261020/before.json`은 실제 Q 실패/복구 raw, S의 일관된 두 revision 실패·원래 모순 raw, 양성 복구/완료와 집계만 완료인 실패 Pod 대조군을 재생했다. S 두 raw의 source hash가 과거 S 입력과 각각 일치한다. 마지막 대조군은 수정 전 거짓 `rollout_complete=true`였다.
- **수정:** Deployment 집계·소유 RS availability·소유/현재 Pod 수와 readiness의 불일치 값을 보존한다. 불일치/미확인에서는 완료·복구 후보를 확정하지 않는다. 정상 완료·revision1 양성 복구는 유지한다. 현재 컨테이너 상태·이전 종료 시도와 조회 적용 근거를 원문과 분리해 전달하며, 원문이 건강성/권한 판정을 바꾸지 않는다. `after.json`, `source-manifest.json` 참조.
- **UI/영속 결과:** inspection summary와 실제 대시보드 projection/component에서 불일치를 표시한다. SSE/SQLite 기존 계약·관련 검사, TypeScript 검사, 실제 Chrome 컴포넌트 검토와 새로고침을 수행했다. `browser-review.json`은 과거 raw의 컴포넌트 검토이며 인증된 앱/라이브 클러스터 E2E가 아니다.
- **모델 전후:** 각7사례, 동일 raw·모델 revision·1024토큰·temperature0·HTTP2/frozen describe1·retry0. 코드 경계 각각7/7, 응답 완료6/7→4/7, 코딩 에이전트 의미 검토0/7→1/7. 삽입문·시작 전 로그·이미지 이름 추론·스케일다운 오독·반복 잘림이 남아 **진단 개선 채택/R3/R4 전체 통과가 아니다.** `paired-review.json`의 개별 원문·해시·실패 이유가 권위다.
- **구분 측정:** 이미지 이름만 바꾼 새 합성3건에서 상태·계수·복구 판정·조회 적용 조건은 동일했다. 완료 사례의 invalid-image 추정이 사라졌지만 다른 오류는 남았다. `lexical-review.json`. 원래 실패를 이 대조군으로 교체하지 않는다. MLX가 `generation_config.json`의 반복 억제 기본값을 쓰지 않는 관측은 별도의 한 변수 실험으로 측정하며, 의미 품질과 혼동하지 않는다.
- **환경:** 기존 Coder 캐시가 비어 있어 과거 revision `6e302ea604ad9ab206367e2c501d1571023e7b6d`를 task-local 폴더에 복원, 모든 LFS SHA를 검증했다. MLX/proxy만 이번 세션 소유로 기동했다. 제품 router/dashboard 후보 미활성화, 클러스터 조회·변경 없음. Node22 Homebrew dylib 오류와 npx 전역 경로 문제는 공식 Node22.23.3 SHA 검증/임시 npm prefix로 분리했다. 전역 설정/권한/유료 API 변경 없음.

**다음:** 현재 한 변수 실험을 먼저 검토하고, 반복 종료와 의미 적합성을 별개로 판정한다. 동일 원본·양성 후보·삽입문·유사 원인·부족 근거 기준을 유지하며 프롬프트 반복이나 오류 은폐로 통과시키지 않는다. 단일 frozen tool 대조를 전체 Investigate 도구 선택/원문 snapshot/인증된 UI 실증으로 확대하지 않는다. 진단/R3/R4 전체·조건부 R5는 열린 작업이다. 기존 수동/코드 기반 흐름은 모델 정확도로 세지 않는다.

## 10. W — 읽기 전용 제안의 적용 조건을 실제 소비 경계에서 집행

V의 상태 일관성 수정만으로 자유 서술 오류는 해결되지 않았다. 원인·조회 제안의 source ID가 존재해도 현재 단계에 맞지 않는 선택이 통과하는 것을 `proposal-applicability-before.json`으로 재현했다. W는 기존 제안 계약을 재사용하며 상태·복구·권한은 코드가 유지하고, 모델은 관측에 맞는 가능성/다음 증거를 선택한다. 원래 텍스트/실패를 trace와 model_completion에 보존하며 수정·재시도로 통과시키지 않는다.

- **계약:** `src/agents/ai/investigation_proposals.py`. 불일치/미확인은 재수집, 완료는 service health, pull 실패는 image/registry/events, 종료 이력이 있는 현재 컨테이너는 이전 시도 로그로 제한한다. CrashLoopBackOff의 image-name 지름길을 이미지 존재 실패로 승격하지 않는다. 원문 지시문이 선택지나 복구 판정을 넓히지 않는다.
- **배선:** readonly factory가 동일 describe 함수 결과에 계약 metadata만 덧붙인다. 도구5개·Kubernetes 신원·권한·조회 횟수는 추가하지 않는다. router가 마지막으로 바인딩된 관측에 최종 제안을 검증하고 inspection에 정상/거부/재수집 상태를 보존한다. 일반 모드와 supplied-text snapshot은 별도다.
- **실측:** 과거 S 잘못된4출력은 새 검증에서 거부, synthetic valid recovery1·유효 단계 출력6은 유지했다. 첫 prototype의 과도한 current-revision-only 출처 요구는 이미 현재 Pod에 묶인 source ID도 거부했다. 이 잘못된 가드와 schema를 실제 binding에 맞게 정렬했다. 현재 prototype은7건 중6유효, 모순 사례의 금지 원인 제안1은 거부한다. 이는 인과 정확도나 전체 도구 선택 점수가 아니다.
- **W 모델:** 실제 production factory/router·frozen describe로 초기7건을 실행했다. 제안5·재수집1·형식거부1. 형식 거부는 old prose sections 지시와 JSON 계약을 함께 주어 prose+JSON으로 답한 사례다. formatting 지시 하나를 제거한 같은 관측의 대조는 유효 JSON이 됐다. 같은 최종 후보7건은 `production-contract-final/`에서 응답7완료·제안6검증·코드 재수집1로 확인했다. 모순 사례의 source-ID 오타도 raw로 남으며 코드 재수집 판정을 모델 성공으로 세지 않는다.
- **소비 경계:** 정상/잘린 출력/단계 위반/재수집, 일반·streaming, SQLite 동일 request 재조회와 actor 격리, 실제 UI projection/render 검사를 수행했다. UI는 검증된 가능성/조회만 별도로 표시하며 거부된 원래 응답도 남긴다. 최종 전체 gate/브라우저 자료와 소스 manifest를 함께 기록한다.

**미완료:** 전체 Investigate 카탈로그에서 실제 도구를 선택하는 경로, 인증된 실제 UI/라이브 읽기 실증, 기존 supplied-text snapshot의 의미 실패, 진단/R3/R4 전체와 조건부 R5. 현재 근거로 완료를 선언하지 않는다. W 전체 gate는3380/3·20warnings·119.20초로 통과했다. 다음은 아래 실제 읽기 실패의 scope 가설 분리다. 기존 T 정상/거부/복구/새로고침 반복과 데모는 완료 범위로 유지한다.

### W 실제 현재 workload 읽기 — 정상 완료가 아닌 failed 기록

기존 제한 토큰은 만료돼 Unauthorized였다. 원래 `platform-agent-deployer` SA UID와 현재 UID가 같음을 확인하고, 기존 로컬 승인 범위에서 같은 신원의1h 토큰을 task-private 0600 파일에만 갱신했다. RBAC/권한 변경은 없다. 기존 credential은 보존했다.

격리 API18778/모델18191에서 실제 Investigate5와 동일 신원으로 요청했다. 모델은 describe_deployment·rollout_status·list_pods·list_namespaces를 병렬 요청했다. 앞의3개는 지정 namespace/workload에 dispatch, cluster-wide list_namespaces는 task scope guard에서 dispatch 전에 거부됐다. 최종 run은 **failed**이며 이를 정상 통과로 세지 않는다. 관측과 제안은 저장됐고 같은 request 재조회는 추가 도구 실행 없이 재생됐으며 다른 actor 조회404도 확인했다. `live-api/review.json`, `verification.json`, `persisted-run.json`이 권위다.

현재 Deployment UID·전체 spec·rev37/replicas2는 T 최종값과 같았다. current rollout 완료, app/external health와 recovery 후보는 미확인이다. 새 workload 변경/권한 확대는 없다. 이 1회 실제 읽기를 반복 성능·테넌트 격리·인증 UI 증거로 확대하지 않는다.

**정확한 다음 행동:** `resume-checkpoint.json`의 살아 있는 프로세스/토큰 만료부터 확인한다. scope guard와 실제 광고한 tool schema/설명 사이의 누락 가설과, 명시적 namespace 지시를 모델이 무시한 가설을 구분한다. 현재 실패를 보존한 채 한 변수로 재측정한다. tool set을 줄이거나 거부를 감춰 동일 조건 통과로 만들지 않는다. 기존 앱/기본 포트는 전환하지 않았고 인증 UI/원문 snapshot/R3/R4 전체/R5는 여전히 남는다.


## 11. 범위 설명 정렬 후 실제 읽기·로컬 로그인 UI와 snapshot 재검증

§10의 첫 failed run은 그대로 유지한다. `scope-selection/`의 첫 응답 대조는 동일5도구/parameter schema·사용자 요청·모델 설정에서 task wrapper의 inventory hint/함수 설명에 실제 scope 제약만 덧붙였다. 원래 설명은 list_namespaces를 다시 요청했고 정렬한 설명은 대상 reads만 요청했다. 둘 다 dispatch0이다. 이 한 쌍은 누락된 범위 정보가 이번 선택에 기여했다는 근거이며 일반 지시 준수율이 아니다. hard guard/RBAC/도구 수는 바꾸지 않았다.

정렬한 설명의 격리 API18779는 동일 원래 SA·1024/temperature0·request5/tool4/retry0에서 succeeded다(a3ee1c17…). W dashboard 소스를 격리 복사해13001에 기동하고 기존 local-dev Credentials 로그인으로 실제 요청8548bb49…도 succeeded다. 각 describe/rollout/list_pods/get_logs4회, API 동일UUID 재생과 UI 새로고침/원문 JSON 복원은 추가읽기0이다. 다른actor404, workload UID/전체spec/rev37/replicas2 불변. 첫127.0.0.1 로그인은 localhost redirect로 MissingCSRF였고 같은 localhost origin에서 성공했다. GitHub OAuth·다중 tenant·외부 health·운영 적용 증명이 아니다. `live-api-scoped/review.json`, screenshots와 helpers를 보존한다.

Supplied-text의 원래7입력은 현재 모델/제품 경로에서 다시 실행했다. 제외4는 모델0이며 정확도 분모가 아니다. 적용3은 응답/인용3통과지만 의미1충족·1부분·1실패다. counterexample은 양쪽 revision의 timeout에도 log directive를 복구 결정·건강한 이전 revision으로 읽는다. 지시문 한 문장만 뺀 ablation은 recovery not_established로 달라졌다. 원본은 변경하지 않았다.

`experiments/dogfood-diagnosis/consistency-resume/snapshot_support.py`는 output schema/validator만 바꾼 역할별 인용 계약 실험이다. 같은7입력·모델/예산을 유지했지만 의미 결과는1충족·1부분·1실패다. 오류 출력의 형식 거부를 모델 성공으로 세지 않는다. `unsupported-role-control.json`은 같은 directive에 세 role을 붙여 schema/정확인용을 모두 통과하면서 의미적으로 틀린 반증이다. **미채택·제품 변경0**이며 citation/형식 guard만으로 의미를 해결했다고 주장하지 않는다. `snapshot-resume-review.json` 참조.

**다음:** 기존 Qwen 고정을 유지하며, 다른 evidence-to-claim 검증 방식을 구체화한 뒤 제한 측정한다. 같은 schema/prompt 반복은 중지한다. 원래 실패/양성 복구를 보존하고 모든 모델·권한·도구 예산 차이는 명시한다. 진단/R3/R4 전체/R5는 미완료, 기존 T 묶음과 이번 실제 읽기/UI는 반복하지 않는다.


고정 Qwen의 별도 evidence-to-claim witness도 `snapshot-witness/`에3건 저장했다. 이는 recovery draft/질문을 주지 않는 추가 모델 호출 프로토콜이며 기존 한 호출 진단과 같은 조건의 정확도 비교가 아니다. 응답3완료지만 key 내부 공백으로 binding0/3, 그와 별개로 counterexample은 두 revision timeout을 previous healthy의 supported 근거로 인용했다. 자동 key 보정/소스 정제 없이 원문 보존·미채택이다. 다음은 모델 고정 상태에서 독립 검사가 가능한 구조화 관측과 명시적 사람 검토 경계의 설계이며, 기존 declared-text 의미 기준을 통과했다고 세지 않는다. `snapshot-witness/review.json` 참조.


## 12. 고정 Qwen 온도 대조와 일시중지 체크포인트

사용자가 기존 Qwen 고정을 확정한 조건을 유지했다. 원래3 snapshot과 동일 prompt/schema·1024토큰·request1/tool0/retry0에서 미리 정한 seed42/31415/27182마다 온도0/0.7을 대조했다. 실제 HTTP pair는 temperature만 다르다. MLX 코드는 명시seed가 있으면 nonbatch 경로를 쓰므로 두 arm을 그 경로로 맞췄으며, 앞선 unseeded 실행과 완전히 같은 경로라고 쓰지 않는다. 모델 카드 권장값 전체를 적용한 실험도 아니다.

18응답은 모두 보존했다. 온도0은9완료/인용9통과지만 기존 의미 오류가 남는다. 온도0.7은6완료/3잘림, 유효 진단0이라 설정을 채택하지 않았다. 각 case/온도에서 다른seed3개의 raw hash가 동일했다. 실제 요청에 각각의seed가 들어간 것은 확인했으나 sampler/RNG/cache 또는 proxy가 원인인지는 아직 측정하지 않았다. 동일 hash만으로 버그/원인을 확정하거나 세 응답을 독립 확률 표본으로 세지 않는다. `snapshot-temperature/review.json`, 원문18건과 `experiments/dogfood-diagnosis/consistency-resume/snapshot_temperature.py`가 권위다.

**현재 paused:** 사용자의 중지·checkpoint 요청을 반영해 새 구현/모델 호출/클러스터 작업을 멈췄다. 제품 소스11개는 W 전체gate3380/3과 hash 일치하며 새 전체gate로 세지 않는다. 서버는 종료/재시작하지 않고 소유 PID/포트만 체크포인트에 기록했다. 재개 시 토큰 만료와 실제 프로세스를 다시 확인하며 기존 파일·DB/evidence 경로에 덮어쓰지 않는다.

**재개 첫 행동:** `pause-checkpoint.json`과 review를 읽고, 실제 로드된 MLX sampler·seed/RNG·prompt-cache 경로를 upstream/proxy 경계에서 구분 측정한다. 모델/원문/prompt/schema를 바꾸는 추가 탐색 전에 이 해석 한계를 해소한다. 기존 진단 기준·양성 복구·실패 원문을 유지하며 R3/R4 전체/R5는 미완료다.


## 13. 2026-10-20 재개 — sampler 경계 규명과 삽입 지시 복구 가드

사용자의 "잔여 작업 완료시까지 수행" 지시로 §12 일시중지에서 재개했다. 체크포인트의 서버6개는 이미 종료돼 있었고, 모델4 shard SHA256을 provenance와 재확인한 뒤 이번 세션 소유로 다시 기동·종료했다. 기존 Qwen 고정, 원래 실패/양성 복구 보존.

- **seed 동일 원문의 원인(확정):** `mx.random.state`는 스레드마다 다른 객체인데 `categorical_sampling`은 import 스레드의 상태를 붙잡아 컴파일되고, 서버는 별도 생성 스레드에서 seed를 설정·샘플링한다. 모델 없는 장수 worker 스레드 재현에서 seed3개·12draw가 모두 같은 토큰이었다. stock 서버는 온도0.7/1.0·upstream/proxy·seed 생략까지 모든 그룹이1종 출력이었고, `categorical_sampling` 하나만 비컴파일로 바꾼 개입 서버는 seed마다 달라지고 같은 seed는 재현됐다. proxy는 같은 seed에서 upstream과 동일해 배제했다. 따라서 §12의 0.7 arm은 표본9개가 아니라 case당 고정 키 출력1개였다. `sampler-boundary/review.json`.
- **온도0 출력의 이력 의존(새 측정 한계):** 같은 요청 바이트라도 prompt cache에 어떤 접두사가 있었는지(cold/부분 캐시)와 seed 유무(batch/nonbatch)에 따라 argmax가 근소한 동점 지점에서 갈렸다. 같은 이력 안에서는 재현된다. 과거 "동일 raw·temperature0" 단일 응답 대조(V 전후, §11 ablation, W 형식 대조)는 이 변수를 통제하지 않았다. 기록은 유지하되 단일 응답 차이를 바꾼 한 변수의 효과로 읽지 않는다. 새 대조는 `cached_tokens`를 기록하고 arm마다 재기동(cold)+다른 이력으로 반복한다.
- **0.7 재측정:** 개입 서버에서 원래 스크립트의 파생본(`snapshot_temperature_sampler.py`, base_url/출력만 다름)으로 18응답. 0.7 진짜 표본은 완료9/인용7유효, counterexample3/3이 여전히 log note를 근거로 review_candidate. 0.7 미채택은 유지하되 근거를 이 측정으로 교체한다. 제품은 temperature/seed를 보내지 않아(서버 기본 0, argmax) seed 결함의 영향이 없다.
- **ablation 재검증:** `injection-cache-control/`. 두 cache 이력에서 원본→review_candidate(지시문 인용), 지시문 제거→not_established가 각각 동일 raw로 재현, 진짜 표본에서도 같은 방향. 지시문이 이 오류의 원인임을 이력/샘플링 변동 밖에서 확인했다.
- **제품 후보(채택, 미커밋):** `snapshot_diagnosis.py`가 표식 기반 삽입 지시 구간을 탐지해 모델 입력·보고서에 `embedded_instructions`로 주석하고(원문 불변), `review_candidate`에는 `recovery_evidence` 인용을 요구하며 그 인용이 지시 구간과 겹치면 코드가 거부한다. baseline(§12 바이트 동일 소스) 대비 cold/warm 각5 case: counterexample 2/2·표식 제거 변형 2/2가 not_established로 정정(후자는 탐지0, 건강한 이전 revision 인용 요구의 효과), 양성 복구2/2 유지, 지시문을 덧붙인 양성 변형은 1/2 거부(fail-closed), lookalike는 2/2 길이 초과 형식 무효로 회귀(원인 단정 부분 오류는 양쪽 모두 남음). 단위12·변이4 red. `injection-guard/review.json`.

**남은 일:** lookalike의 유사 증상 원인 단정(이제 형식 무효), 표식 없는 지시문의 코드 탐지 부재와 비지시문 인용 우회 가능성, 진짜 표본에서의 후보 측정, R3/R4 전체·조건부 R5. 길이 한도 완화·프롬프트 반복으로 lookalike를 통과시키지 않는다.

### 13-1. lookalike 관계 필드 실험(미채택)과 R3/R4 판정

- **실험:** 현재 후보에 `cause_relation`(same/different/not_established)과 비교 소스 양쪽의 `relation_evidence` 코드 검사를 더한 실험 모듈만 사용(제품 소스 불변). 원인이 명시된 합성 양성 대조 2종은 cold/warm 모두 정답(same 2/2, different 2/2)이었다. 그러나 lookalike는 증상 문장 두 개를 인용해 different 2/2로 형식 통과(예측한 형식 우회)했고, counterexample은 소스1개로 same을 내 2/2 형식 무효로 회귀했다. **미채택.** 역할 인용 계약·witness·관계 필드 세 가지 계약 변형이 이 오류를 고치지 못했다. 산문에서 증상과 근본 원인의 차이는 코드가 검증할 수 없다. `relation-probe/review.json`.
- **R3 진단 시나리오 판정(§4 기준: 불충분함을 밝히고 권한·실행 범위를 넓히지 않음, D53 반영):** 범위·실행은 전 사례에서 넓어지지 않았다(도구0·execution_authorized false). 오래된 로그·다른 서비스·시각 미상 4건은 코드가 모델 전에 제외, 로그 지시문은 가드 후보로 정정, 양성 복구 유지. 유사 증상(lookalike)은 모델이 불충분함을 밝히지 못한다. 사용자 결정 D53으로 이 항목은 사람 검토 경계(실행 확대0·unverified 표시)로 충족 처리하며, 모델 의미 통과로 세지 않는다. **이로써 R3 시나리오 묶음은 T 완료분과 함께 충족.** 정상·거부·복구·새로고침 시나리오는 T에서 완료.
- **R4 첫 묶음(제한 포함 정리):** 7사례·코드 보류4·합성 변형4와 하네스, 수동 기준(describe→rollout status→pods→logs·이전 컨테이너 logs) 대비 도구 선택을 기록 증거로 평가했다. 모델은 기준 5개 중 4개를 대상 범위 안에서 선택했고, 이전 컨테이너 로그는 `get_logs`에 옵션이 없다. 제안 계약은 이를 사람에게 보이는 다음 증거(가용성 미검증 명시)로만 내므로 결함이 아니라 고정 도구 확장 여부의 결정이다. 수동 소요 시간은 측정하지 않았다. `r4-first-bundle/review.json`.
- **(D53 이전 기록) 막힌 지점:** 고정 Qwen(사용자 결정)에서 계약 변형으로 lookalike를 고칠 근거가 없다. 남은 선택지는 모두 사용자 결정이다: (a) 유사 증상 질문에 대한 명시적 사람 검토 경계를 R3 기준으로 수용, (b) 모델 고정 해제 후 비교, (c) R5 외부 에이전트 비교(설치·호출 승인 필요). 길이 한도 완화·프롬프트 반복은 하지 않는다.
