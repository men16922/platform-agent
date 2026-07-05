# platform-agent

### 당신의 상시 대기 플랫폼 엔지니어 (always-on platform engineer)

> AWS-native 플랫폼 에이전트 — 단순 알림을 넘어
> **provision → deploy 검증 → detect → analyze → decide → execute → report** 전 구간을 자동화한다.
> 코어는 클라우드에 중립적으로 설계되어 GCP/Azure/on-prem 확장을 염두에 둔다.

---

## 1. 문제 (Why)

전통적인 운영 자동화는 **알림에서 멈춘다.**

```
Alarm 발생 →  Slack 알림 →  사람이 로그 확인 →  사람이 원인 추정 →  사람이 조치 →  사람이 리포트
                    └──────────────── 여기 전부가 수동, 새벽 3시에도 ────────────────┘
```

- 알림은 "무슨 일이 났다"까지만 말한다. **왜, 무엇을 해야 하는지**는 사람이 채운다.
- 대응 품질이 담당자·시간대에 따라 달라진다 (on-call 편차).
- 반복되는 incident에도 매번 처음부터 조사한다 (runbook이 사람 머릿속에만 있음).
- 멀티클라우드 환경에서는 이 편차가 클라우드 수만큼 곱해진다.

**platform-agent는 알림 다음의 모든 단계를 에이전트가 잇는다.**

---

## 2. 무엇을 하는가 (What)

```
 Slack / Jira / GitHub / CloudWatch Alarm
                  │
          Router / Harness
                  │
   ┌──────────────┼──────────────┐
   ▼              ▼              ▼
Provisioning  Deployment    Operations
(Day 1)       (Day 1.5)     (Day 2)  ◀── 핵심 런타임
```

### 핵심: Operations 4단계 파이프라인

| 단계 | 에이전트 | 하는 일 | AWS 서비스 |
|------|----------|---------|-----------|
| **Detect** | Detector | Alarm 수신 → 정규화된 incident 생성 | EventBridge, CloudWatch |
| **Analyze** | Analyzer | 로그·트레이스 수집 → 근본 원인(RCA) 추론 | Logs Insights, X-Ray, Bedrock |
| **Decide** | Decision | runbook 매칭 → 조치안 + 위험도 결정 | DynamoDB (runbook registry) |
| **Execute** | Executor | 승인 후 실제 조치 실행 → 리포트 | SSM Automation, Slack |

**Human-in-the-loop:** 위험한 조치(`Delete`/`Drop`/`Terminate` 등)는 Slack 승인을 강제한다.
`Step Functions WaitForTaskToken` + SQS + approval bridge 로 사람의 Approve/Reject 를 받아 재개한다.

---

## 3. 어떻게 만들었나 (How) — Harness Engineering

이 프로젝트의 차별점은 **두 AI를 역할 분담시키는 harness**다.

```
        AgentHarness (task.type 라우팅)
        ┌──────────────┴──────────────┐
        ▼                             ▼
   Claude Code                     Codex
 (추론 / 설계 / 분석)          (코드 / 보일러플레이트)
 아키텍처 트레이드오프          CDK 스택, Lambda,
 에러 분석, 의사결정           Step Functions JSON, IAM
```

- `ContextStore` 가 **관련 컨텍스트만 주입**해 토큰 한계를 넘긴다.
- Codex 미가용 시 Cursor/Copilot CLI 로 교체 가능 (client layer 추상화).
- `Claude Code → Codex` 핸드오프 문서를 `python -m harness.handoff` 로 생성.

> 이것이 Medium 글 주제: *"Harness Engineering: Claude Code + Codex 를 엮어 컨텍스트 한계를 넘다."*

---

## 4. 설계 철학 (SAP 정렬)

모든 서비스 선택에는 **"무엇"이 아니라 "왜"** 가 있다.

| 결정 | 근거 |
|------|------|
| Step Functions (not SWF) | 서버리스 오케스트레이션, 시각적 상태 관리 |
| EventBridge (not SNS) | 이벤트 라우팅 패턴, 다중 소스 fan-in |
| Executor IAM 최소 권한 | Least Privilege — `Resource:"*"` 금지 |
| 파괴적 액션 강제 승인 | 안전한 자동화, blast radius 통제 |
| CDK (TypeScript) IaC | 타입 안전, 재사용 가능한 인프라 구성 |

---

## 5. IaC 관점 — 클라우드 중립 설계

코어 파이프라인(Analyzer/Decision)은 provider 무관하게 유지하고,
**입출력 경계만 adapter/emitter 로 교체**하는 구조로 설계했다.

### 5.1 레이어별 확장 방향

| Layer | AWS (현재 구현) | GCP | Azure | On-prem |
|-------|----------------|-----|-------|---------|
| Trigger / Ingest | EventBridge + CloudWatch Alarm | Eventarc + Cloud Monitoring | Event Grid + Azure Monitor | Alertmanager / Grafana OnCall webhook |
| Logs / Metrics / Traces | Logs Insights + CloudWatch + X-Ray | Cloud Logging + Monitoring + Trace | Log Analytics + Monitor + App Insights | Loki/ES + Prometheus + Jaeger |
| Execution | SSM Automation / AWS API | Cloud Run/GKE job + Deployment Manager | Azure Automation / Container Apps / AKS | Ansible AWX / Argo / K8s Job / Rundeck |
| State / Memory | DynamoDB + S3 + Bedrock KB | Firestore/BigQuery + GCS + Vertex AI | Cosmos DB + Blob + Azure AI Search | Postgres + MinIO + self-hosted vector |
| **IaC output** | **CDK TypeScript** | CDKTF / Pulumi / Terraform emitter | Bicep / Pulumi emitter | Helm + Crossplane + Terraform emitter |

### 5.2 emitter 교체형 Provisioning

Day 1 provisioning 을 "무조건 CDK 생성"이 아니라 **blueprint ↔ emitter 분리** 로 설계한다.

```
서비스 요구사항
   → Spec parser       (ServiceBlueprint 로 정규화)
   → Policy designer   (IAM/RBAC/Network policy 계산)
   → IaC emitter       [ cdk_ts | pulumi | bicep | helm | terraform ]
   → Deployment validator (smoke/canary 는 공통, metrics backend 만 교체)
```

> AWS 기준선은 CDK TypeScript 로 유지하되, blueprint 와 emitter 를 분리해 두면
> GCP/Azure 추가 비용이 크게 줄어든다.

> ⚠️ **경계:** 위 IaC 매핑과 emitter 목록은 **클라우드 중립 설계 방향**이다.
> 현재 provisioning 코드(`cdk_generator` + `cdk_emitter`)는 **AWS CDK TypeScript 만 실제 생성**한다.
> `pulumi`/`bicep`/`terraform`/`helm` emitter 는 아직 구현 전(설계만).

---

## 6. 지금 동작하는 것 (Verified Status)

**검증 baseline:** `pytest -q` → **201 passed** · `npm run synth` deprecation 0건

| 영역 | 상태 |
|------|------|
| Operations 4단계 파이프라인 (detect→analyze→decide→execute) | ✅ 런타임 동작 |
| Slack HITL 승인 (SFN callback 연결) | ✅ 동작 |
| Runbook registry (deploy-time seed + runtime scan fallback) | ✅ 동작 |
| AWS provisioning (CDK TS 생성 + IAM + cost 추정) | ✅ 동작 |
| Portability seam (cloud-neutral incident envelope) | ✅ 연결 |
| 비-AWS signal 정규화 + capability→action 해석 | ⚙️ 부분 연결 (adapter 실동작) |
| 비-AWS 실제 실행 API 호출 | 🚧 scaffold |
| 멀티클라우드 IaC emitter (pulumi/bicep/terraform) | 🚧 설계만 |
| 실 클라우드 E2E 검증 | 🚧 예정 |

> **정직한 경계:** production path 는 **AWS-native 한정**이다.
> GCP/Azure/on-prem 은 incident 정규화와 action 해석까지는 실동작하지만,
> 실제 provider API 실행과 IaC emitter 는 아직 설계·scaffold 단계다.

---

## 7. 로드맵 (Next)

1. **비-AWS 실행 연결** — executor 의 GCP/Azure/on-prem 실제 API 호출 wiring.
2. **IaC emitter 확장** — `cdk_ts` 외 `pulumi`/`bicep`/`terraform` emitter 구현.
3. **실 클라우드 E2E** — LocalStack / 실 AWS 테스트 계정 기준 end-to-end 시나리오.
4. **Runbook 등록 자동화** — override 등록 CLI/콘솔 도구화.

---

## 8. 한 줄 요약

> **"Alarm 이 울리면, 사람이 아니라 에이전트가 조사하고, 판단하고, (승인 하에) 고치고, 보고한다.
> 그리고 그 코어는 특정 클라우드에 묶이지 않도록 설계됐다."**

*platform-agent — detect → analyze → decide → execute, 상시 가동.*
