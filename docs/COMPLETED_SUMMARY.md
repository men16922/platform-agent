# COMPLETED_SUMMARY — platform-agent

최종 갱신: 2026-07-17

> 완료된 milestone 압축. current docs 에는 링크만, 상세 체크리스트는 여기로 압축.
> 도메인 원문 상세는 `bin/docs/archive/`.

---

## M0 — Operations 파이프라인 기준선 (완료)

Detector / Analyzer / Decision / Executor 4단계 + Approval Bridge. CloudWatch Alarm → Logs Insights / X-Ray / Bedrock RCA → 런북 선택 → SSM Automation → Slack 리포트 → DynamoDB 기록(90일 TTL). canonical 경로 `src/agents/operations/`, flat import 은 compatibility shim 으로 보존. Step Functions pipeline 과 handler 경로 일치.
상세: `bin/docs/archive/agents.md`, `bin/docs/archive/architecture.md`.

## M1 — Human-in-the-loop 승인 (완료)

P2 severity 흐름에 Slack interactive approval. `WaitForTaskToken` + SQS + approval bridge + Step Functions callback(`SendTaskSuccess`/`SendTaskFailure`). Approve/Reject 버튼으로 파이프라인 재개. 인터랙티브 미설정 환경은 `APPROVAL_DEFAULT_DECISION` 폴백.

## M2 — Harness / handoff 레이어 (완료)

`TaskQueue`(.harness/tasks.json), `ContextStore`(.harness/context.json), `TaskRouter`, `AgentHarness`, client 추상화. `python -m harness.handoff` 로 `.harness/handoff.md` 자동 생성(빈 상태면 워크스페이스 스캔 seed). Claude Code ↔ Codex 툴 전환 컨텍스트 보존.

## M3 — Portability runtime seam (완료)

`NormalizedIncident` cloud-neutral envelope. detector 가 alarm context 와 함께 생성 → analyzer RCA prompt 반영 → decision 이 capability 기반 runbook metadata 를 AWS action 으로 해석 → executor 가 normalized incident 기준 SSM 파라미터 우선 구성.

## M4 — 멀티클라우드/온프렘 scaffold (완료, 런타임 미연결)

provider registry + signal adapters(aws/gcp/azure/onprem) + execution adapters(aws/gcp/azure/onprem). 비-AWS 는 normalized incident / capability mapping 검증용 scaffold + 단위 테스트. 실제 provider API 호출은 NEXT_PLAN P1.

## M5 — Runbook registry bootstrap + override 계약 (완료)

`src/agents/runbooks/catalog.py` built-in capability 기반 catalog(eks-pod-oom / lambda-throttle / rds-cpu-high / kafka-lag-spike / generic-recovery). CDK custom resource 가 `incident-runbooks` 에 seed. decision 은 exact `alarm_name` lookup 실패 시 catalog scan heuristic 으로 재매칭. 코드 fallback ≡ DynamoDB 초기값.
override 계약: `src/agents/runbooks/schema.py`(`validate_runbook`). seed 시 malformed skip+로깅, decision 시 malformed 무시+경고 후 heuristic 폴백.
상세: `bin/docs/archive/agents.md` (런북 스키마 표).

## M6 — CDK deprecation 정리 (완료)

DynamoDB `pointInTimeRecovery` → `pointInTimeRecoverySpecification`. Lambda `logRetention` → 함수별 전용 `logs.LogGroup` 을 `logGroup` 으로 주입. legacy `Custom::LogRetention` 커스텀 리소스 + 부수 IAM Role 제거. `npm run synth` deprecation 13건 → 0건.

## M9 — eval·하드닝 스프린트 + 라이브 E2E 2종: 자율 백로그 전면 소진 (완료, 2026-07-19)

**목적:** Google 생태계·cwc-workshops 대조 후속(①~⑦)과 승인된 실행 큐 8건(⑧⑨ 잔여+⑦ 라이브)을 소진하고, 남은 사용자 게이트 2종(OAuth 배포 클릭·Slack App)을 라이브 E2E로 완주. gate 748→847, spend ~$0.
**산출:** (a) **eval 하네스 시리즈(④⑤⑥)** — `eval_harness.py`(injectable Router/Judge·결정론 백스톱)→멀티-grader 스코어카드(PASS_SLOW·action-sink·Scorecard.delta)→데이터셋 20케이스+adversarial 5·judge 반-관대(calibration_probe); 라우팅 갭 4건 발견→`classify_request` precedence 재설계→회귀 가드. (b) **모델 스윕(⑦)** `model_sweep.py`+라이브 160콜(M8 참조). (c) **A2A/SSE/메모리 하드닝(⑧⑨ 8건)** — sanitize·최소권한 힌트·구조화 디스크립터·저-confidence 게이트·SSE id/ready/heartbeat·`memory_tier.py`(distill/recall/consolidate), 전부 옵트인·비파괴. (d) **OAuth 배포 클릭 E2E**(07-18) + **Slack 인터랙티브 승인 E2E**(07-19) — 이 라이브들이 프로덕션 버그 7건 표면화→전부 근본수정(`.vercelignore` 404·OIDC provider 삭제 복구·smoke_tester base_url·detector NameError·approval_bridge float→Decimal·Bedrock 무효 모델 ID·유령 SSM 문서→D17 in-process 알림).
**검증:** `make check` 847 passed. 라이브 증거 `docs/evidence/{oauth-deploy-trigger-live,slack-interactive-approval-live}.log`, SFN SUCCEEDED 3회·DynamoDB APPROVED/resolved 확증, 실 LLM 심각도 P1/P2/P3 3단 관측. 상세 이력: `docs/archive/progress-2026-07.md`·`status-baseline-2026-07.md`.

## M8 — 프로덕션 패키징 + State Store: AWSome 레퍼런스 8/8 완결 (완료, 2026-07-17)

**목적:** 레퍼런스 잔여 #7(Helm/Terraform)과 로드맵 ④(State Store/Alertmanager)를 닫아 AWSome AI Gateway 레퍼런스 전 항목(Tier 1 4종 + Tier 2 3종 + #7)을 소화. gate 822→842(+20 test), 커밋 9개 전부 origin/main, 클라우드 spend $0.
**산출:** (a) **⑦ 라이브 모델 스윕**(로컬 MLX 160콜) — `_classify_prompt` teardown/진단동사 결함 발견→수정→가드, 증거 기반 선택 **7B@temp0=20/20**(30B 반증). (b) **#7-a Helm 차트** `infra/helm/platform-agent/` + 이미지 `infra/onprem/Dockerfile`(kubectl 내장) — 최소권한 RBAC(4조치 동사 열거·drain 별도 게이트)·strict/lenient 프로브 분리·env×substrate values. (c) **④ SQL State Store** `state_store.py`(`PLATFORM_STATE_DSN` 옵트인, 미설정=JSONL 무변경) + 차트 `stateStore` values(secretKeyRef 우선, DSN 모드=RollingUpdate·replicas>1 해금). (d) **#7-b Terraform** `infra/terraform/aws-production/`(VPC/EKS 1.31/**Aurora Serverless v2 `platform_state`**=DSN seam 정합/IRSA 정확-ARN grant; Redis·Cognito=미소비 제외). (e) 부산물 버그 2건: pyproject optional-deps PEP 621 위반(이미지 빌드가 표면화)·이미지 psycopg2 누락.
**검증:** 라이브 4건 — kind 실 install(RBAC can-i allow/deny·P2 승인 루프·PVC 영속), **실 Alertmanager→멀티-레플리카 상태 공유**(docker PG, replica-2 승인→replica-1 즉시 반영), k3s substrate(기존 k8s-lab VM, `local-path` Bound), terraform init+validate. 증거 `docs/evidence/{model-sweep-live,helm-kind-live-install,state-store-alertmanager-live,helm-k3s-substrate-smoke}.log`. 가드 테스트 +20(helm/terraform/state/sweep). 잔여=사용자 게이트만(terraform apply·아티클·OAuth·Slack).

## M7 — 문서·컨텍스트 하네스 이식 (완료, 2026-06-11)

harness.md 기반으로 `harness/CORE_MANDATES.md` + `CONTEXT_BRIDGE.md`, `docs/` current-doc 체계, `.claude/skills/{sync,checkpoint,tidy-docs}` 구축. 기존 도메인 문서는 `bin/docs/archive/` 로 이관.
