# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-13

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-14 — On-Prem PATH B webhook 구현: Alertmanager→in-process Day-2 파이프라인

- Status: ARCHITECTURE 로드맵의 On-Prem PATH B(이벤트 수신=Webhook FastAPI, 오케스트레이션=직접 호출) 🔲을 **구현+라이브 검증**으로 종료. 발견: Day-2 4핸들러(detector/analyzer/decision/executor)는 이미 on-prem을 지원(detector가 Alertmanager `alerts`/`groupLabels` 자동감지→onprem SignalAdapter, executor onprem 경로=로그-only 스텁)했고, **빠진 건 오직 이벤트 수신기+in-process 체이닝**이었음.
- Changed: 신규 `src/agents/ai/onprem_incident_pipeline.py`(`run_incident_pipeline`: 4핸들러를 출력→입력으로 in-process 체인, 클라우드 Step Functions/Workflows/Durable Functions 대응) + `src/agents/ai/onprem_webhook_api.py`(FastAPI: `POST /webhook/alertmanager`·`/webhook/incident`·`GET /health`, 컴팩트 요약 반환). `tests/test_onprem_webhook.py`(6 테스트: 실 detector/decision/executor 체인 + TestClient 엔드포인트, analyzer Bedrock은 stub·activity는 tmp 격리). Makefile `onprem-webhook` 타깃. `docs/ARCHITECTURE.md` L107(PATH B)·Day-2 On-Prem 컬럼 🔲→✅ + 구현 노트.
- Verified: `pytest tests/test_onprem_webhook.py` 6 passed. **실 HTTP 스모크**(`uvicorn onprem_webhook_api:app :8078` → curl): `/health` ok, `POST /webhook/alertmanager`(crash-loop 페이로드)→ onprem 감지·service=payments-api·resource=kubernetes-workload·heuristic severity·generic-recovery 런북(APPROVE)·onprem 로그-only 실행·incident_id 반환. `make check` → **609 passed, 1 skipped**.
- Blockers: 없음. 잔여(로드맵): Alertmanager 실연동·State Store(PostgreSQL/Redis)·실 executor(MCP Gateway)·Approval Flow.
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드 항목.

## 2026-07-14 — ARCHITECTURE.md 정합화: Orchestrator+A2A를 로드맵→구현(라이브 검증)으로 갱신

- Status: 이번 세션의 A2A Phase 1+2 실증으로 ARCHITECTURE.md가 stale해진 지점을 정합화. 문서가 supervisor+A2A를 여전히 🔲 "타깃/로드맵"으로 표기하고 있었음 → **구현·라이브 검증 완료**로 정정하되, 아직 미완인 부분(MCP Gateway 단일 카탈로그, supervisor의 local_deploy_api 배선)은 로드맵으로 명확히 분리.
- Changed: `docs/ARCHITECTURE.md` — (1) L22 구현 상태: "Orchestrator+A2A 통합 🔲" → "supervisor 라우팅+A2A discovery/위임 ✅(실 kagent 라이브)". (2) "Orchestrator + A2A" 섹션 헤더/인트로에 구현상태 블록 추가, 3개 불릿을 ✅/🔲로 정정(supervisor.py 배선·JSON-RPC 0.3·messageId·capability 격리 명시). (3) 현재/타깃 표의 "에이전트 연결 현재=각자 독립 실행" → "A2A 상호운용 ✅". (4) Gateway A2A Server 프로토콜에 JSON-RPC 0.3(kagent 카드 호환) 명시. 코드 변경 없음(문서만).
- Verified: 편집 후 문서 내 상호 참조/앵커 정합 확인(취약 앵커 링크는 텍스트 참조로 대체). 코드 무변경이라 gate 영향 없음(직전 baseline 603 passed 유효).
- Blockers: 없음.
- Next: (외부/deferred) Slack App · 아티클. 로드맵 빌드 항목(온프렘 PATH B/Day-2, 클라우드 Provision 어댑터, MCP Gateway 단일 카탈로그, Agent Runtime 매니지드 호스팅)은 스코프 큰 선택지 — 착수 시 사용자 지정.

## 2026-07-14 — A2A capability-isolation: PROVISION role 오버매칭 격리 강화

- Status: Phase 2 검증 중 관찰한 **PROVISION role 오버매칭**을 수정. discovery-only 체크에서 `matching_skills(진단카드, PROVISION)`가 `[cluster-diagnostics, observability]`를 반환 — 진단 카드가 provision 전문가로 잘못 매칭될 여지. Phase 1의 KAGENT/DEPLOY 격리와 동일 원칙 적용.
- Changed: `supervisor.py` `ROLE_SKILL_TERMS[PROVISION]`에서 generic `"cluster"` 제거 → provision-특화어 `"infrastructure"`로 교체(`provision`/`terraform`/`ansible`/`infrastructure`). KAGENT와 동일한 경고 주석 추가. `test_supervisor.py`에 회귀 테스트(`test_rejects_diagnostic_only_card_for_provision_role`): 진단-only 카드는 PROVISION에서 `[]`, KAGENT에서만 매칭, 진짜 provisioner 카드는 PROVISION 매칭 유지.
- Verified: `pytest tests/test_supervisor.py` 13 passed; `make check` → **603 passed, 1 skipped**.
- Blockers: 없음.
- Next: (외부/deferred) Slack App 실생성 · 테크 아티클 배포. 코드 백로그 소진.

## 2026-07-14 — A2A Phase 2 완료: 실 kagent 에이전트 대상 라이브 E2E + 스펙 갭 수정

- Status: open-risk #5의 **Phase 2(실제 kagent endpoint)를 라이브로 완결**. defer 권고였으나 착수 → kind+kagent 0.9.11+로컬 MLX Qwen 30B 재프로비저닝 후, supervisor가 **실 kagent 에이전트**를 discovery→match→위임하고 실 도구 진단까지 받는 end-to-end 성공.
- Changed: **버그 수정** `supervisor.py` — JSON-RPC `message/send`의 `params.message`에 A2A 스펙 필수 필드 **`messageId`(UUID) 누락**을 추가. 스펙 준수 `a2a` SDK(kagent 서버)가 `-32602`로 거부하던 것 — **Phase 1의 관대한 자체 게이트웨이는 못 잡던 실 갭**. `test_supervisor.py`에 회귀 테스트(`test_jsonrpc_message_includes_required_message_id`). 신규: `infra/onprem/kagent/local-diagnostic-agent.yaml`(read-only 진단 에이전트, local-qwen ModelConfig+k8s read tools+A2A skills), `docs/evidence/a2a-phase2-live-e2e.log`(성공 트랜스크립트).
- Verified: **라이브 E2E**(in-cluster driver 파드, supervisor.py stdlib-only 복사 실행 → 설계 의도인 카드 내부 DNS url 그대로 도달): classify=kagent → **HTTP `/.well-known/agent-card.json` discovery** → skill 매칭 `[cluster-diagnostics, observability]`(DEPLOY role은 `[]`로 격리 확인) → **JSON-RPC message/send 위임** → kagent 에이전트가 **실 `k8s_get_resources` MCP 도구 호출** → 30B가 `helm/istio/promql-agent` non-Running(0/1) **정확 진단** 반환. 과거 블로커(kind pod→host MLX)는 프록시 **0.0.0.0 바인딩**으로 해소(파드에서 `host.docker.internal:18091` 도달 확인). `make check` → **602 passed, 1 skipped**.
- Blockers: 없음. 인프라(kind `platform-agent` 3노드 + kagent 18파드 + MLX 30B)는 **실행 중 유지** — 데모/추가 검증 원하면 그대로, 정리는 `make local-cluster-down` + `pkill mlx_lm.server`/proxy.
- Next: (외부/deferred) Slack App 실생성 · 테크 아티클 배포. 코드 백로그 재소진.

## 2026-07-13 — NEXT_PUBLIC 프로덕션 인라인 이슈 실측 → 해소(stale)

- Status: risk #7(선택) 진단·실측 종결. Next 16.2.10 `next build`가 `.env.local`의 NEXT_PUBLIC를 정상 인라인함을 확인 → 과거 "미인라인" 노트는 현재 재현 안 됨(stale), 코드 수정 불필요.
- Verified: `dashboard-header.tsx`(`"use client"`)의 `process.env.NEXT_PUBLIC_DASHBOARD_DEV_AUTH`가 빌드 청크에서 `signIn("dev-credentials")`로 **상수 폴딩**(=`"1"` 인라인), `.next/static` 전체에 원문 env 참조 0건. Next 공식 문서로 메커니즘 교차확인(빌드시점 인라인·정적 참조만·/src 사용시 .env는 루트 로드). `.env.local`은 gitignore라 Vercel 빌드엔 부재→prod는 GitHub OAuth 폴백(의도대로).
- Changed: 코드 변경 없음(진단만). STATUS/NEXT_PLAN #7 해소 표기.
- Blockers: 없음.
- Next: 잔여는 A2A Phase 2(kagent, 인프라 무게로 defer 권고) + deferred 외부항목(Slack/아티클).

## 2026-07-13 — A2A Agent Card discovery 실연결(Phase 1) + 매칭 규율 강화

- Status: risk #5(A2A discovery)의 실체를 **라이브로 실연결**. supervisor의 discovery 코드는 이미 완비돼 있었고(카드 fetch+skill 매칭+HTTP/JSONRPC 위임+trace), 갭은 "살아있는 엔드포인트 대상 실증 부재"였음 → 게이트웨이 A2A 서버를 실기동해 mock 없이 E2E 실증.
- Changed: `supervisor.py` `ROLE_SKILL_TERMS[KAGENT]`에서 generic `kubernetes/cluster` 제거 → 진단 특화어(`diagnostic/troubleshoot/observability/investigat/debug/logs`)로 교체. `test_supervisor.py`에 회귀 테스트(`test_rejects_deploy_only_card_for_kagent_role`) 추가. 코드 외 실증 스크립트는 scratchpad.
- Verified: uvicorn 게이트웨이(`/.well-known/agent-card.json` = Platform Deployer Agent, 6 skills) 실기동 → supervisor `from_environment`가 **HTTP로 카드 discovery → DEPLOY skill 매칭 → 위임(delegated=True, trace matched→sent)**. 강화 후 **KAGENT role은 deploy-only 카드를 `capability_mismatch`로 거부**(delegated=False) 라이브 확인. `pytest tests/test_supervisor.py tests/test_gateway.py` 41 passed.
- Blockers: **Phase 2(실제 kagent endpoint)** 미완 — kind+kagent+MLX 재프로비저닝 필요(원커맨드 스크립트 부재, MLX 미구동). JSON-RPC 진단 task 자체는 과거 실증.
- Next: (선택/무거움) Phase 2 kagent 재프로비저닝 후 실 카드 대상 KAGENT discovery.

## 2026-07-13 — 잔여 백로그 정리: kagent(MOOT) + feat 브랜치 로컬 삭제

- Status: 남은 우선순위 소진. **kagent 정리는 MOOT**로 검증 종결, 중복 **feat 브랜치 로컬 삭제**.
- Verified: 활성 kube context 없음(`current-context` 미설정, `kind get clusters` 0개); Multipass `k8s-lab` k3s VM은 Ready(v1.31.4, 44h)이나 kagent namespace·helm·비시스템 파드 전무 → kagent 정리 대상 부재. `git branch -d feat/onprem-offline-recording-hybrid-rollback`(was 930fe98, main에 완전 머지) 로컬 삭제 완료.
- Blockers: origin `feat` 브랜치 삭제는 권한 분류기가 차단(제네릭 지시로 원격 삭제 불가) → **명시 승인 대기**. 미커밋 doc 정리분은 이 커밋으로 반영.
- Next: (승인 시) origin feat 삭제 / (deferred) Slack App·아티클.

## 2026-07-13 — AWS CDK live diff 재검증 (인프라 drift 0)

- Status: NEXT_PLAN의 "synth 미완" 블로커를 근본원인까지 진단·해소하고 live diff를 실측. **인프라/IAM drift 0** 확인.
- Root cause: `src/stacks/cdk.out`이 **1.8GB 재귀 중첩**(asset.X/src/stacks/cdk.out/asset.Y…) — `Code.fromAsset(projectRoot)`의 exclude에 `cdk.out`이 추가되기 전(수정 Jul 11 11:00)에 쌓인 stale 산출물이 synth를 사실상 무한 복사로 몰던 것. exclude는 이미 코드에 있음.
- Changed: 코드 변경 없음. stale `cdk.out` 삭제(1.8GB 회수). 문서: NEXT_PLAN/STATUS/AGENT_BRIEF에 재검증 완료 + diff context 주의 기록.
- Verified: `cdk synth IncidentAgentStack` **~17s exit 0**(새 cdk.out 37M, 99 resources); `cdk diff --no-change-set` **exit 0**. **진짜 diff = Lambda 13개 코드 asset-hash churn만**(재번들링 노이즈), 리소스/IAM add·delete 0. ⚠️ diff는 `-c vercelTeamSlug=men16922 -c vercelProjectName=platform-agent -c vercelOidcProviderArn=arn:aws:iam::908601828278:oidc-provider/oidc.vercel.com/men16922` 필수 — 없으면 조건부 `VercelDashboardReadRole`이 빠져 가짜 삭제 diff.
- Blockers: 없음. 배포는 하지 않음(재검증만).
- Next: kagent 정리 / (선택) feat 브랜치 삭제 / 미커밋 doc 정리분 커밋.

## 2026-07-13 — 추적 IA 자연어 4스텝 라이브 실증 완료

- Status: LinkedIn 데모 녹화 세션에서 자연어 4스텝을 **브라우저 end-to-end로 실증 완료**. ① `Provision ... then deploy orders-api ...`(Provisioning+Deployments 2행) → ② `Roll back orders-api ...`(단일-row 승계, 중복행 없음) → ③ History 행 클릭→중첩 상세(provisioning⊃deploy) → ④ `Tear down the on-prem cluster`(provision rolled-back + orders-api 자동 cascade rolled-back·Rollback 비활성). 이로써 open-risk #6(라이브 실증 미완) 해소.
- Changed: 코드 변경 없음(실증만). 문서 정합화: STATUS open-risk #6 해소, NEXT_PLAN 실증/커밋 항목 close, AGENT_BRIEF 스냅샷 갱신. `.claude/skills/`에 `grill-me`/`grilling` 스킬 2종 도입, `docs/reference/enterprise-ai-governance-dashboard.md` 레퍼런스 노트 추가(DECISIONS Future Reference 포인터).
- Verified: 4스텝 브라우저 실증(사용자 확인); 증거 영상 `docs/post/local-onprem-edited.mp4`(18.2s hero cut: step 1+3). IA 정리분은 커밋 `930fe98`에 이미 포함.
- Blockers: 없음. 남은 것은 `feat/onprem-offline-recording-hybrid-rollback` **push/머지 결정**(별도 승인 대기).
- Next: push/머지 결정 → (선택) AWS CDK live diff 재검증 / kagent 정리.

## 2026-07-12 — 데모 영상 편집 및 자막 버닝 완료

- Status: `docs/post/local-onprem.mov` 원본 영상을 10~20초 범위 내인 18.2초로 편집하고, 각 7개 구간의 설명 자막을 병합(burn-in)하여 `local-onprem-edited.mp4`로 저장 완료.
- Changed: `edit_video_pil.py` 스크립트를 작성하여 FFmpeg 프레임 추출 ➔ Pillow 자막 드로잉 ➔ FFmpeg 비디오 인코딩 파이프라인 구현. 자막 문구를 실제 구동 모드인 "Terraform"으로 정확하게 매핑.
- Verified: `docs/post/local-onprem-edited.mp4` 생성 (18.2초, 1.0MB, silent). 자막 문구 검증 완료.
- Blockers: 없음.
- Next: 자연어 4스텝 라이브 UI 실증 완료 후 전체 커밋 및 push/머지 결정.

## 2026-07-12 — 배포 추적 IA 정리: Provisioning/Deployments/History 분리 + 중첩 상세 + 롤백 단일-row/cascade

- Status: 추적(activity) 데이터 모델·UX를 대폭 정리. **provision/deploy `type` 분류** + **provider×environment** 일관 taxonomy, 롤백을 **단일-row 승계**(새 행 X), **cluster teardown이 그 클러스터 deploy들을 자동 rolled-back으로 cascade**, 자연어 명령(rollback/teardown)도 UI와 동일하게 승계/cascade로 라우팅.
- Changed:
  - Python `deploy_recorder`: `type`(provision/deploy)·`cluster`(연결키)·`environment`(더 이상 provider로 안 덮음) 저장, `_infer_service_version` deploy 우선(=version=kind 버그 수정), 복합 run을 provision+deploy **2행 분리**+단계별 성공판정, `record_rollback`(deployment_id supersede), `record_cluster_teardown`(provision 승계+deploy cascade), `read_deploys`(백엔드별 최신, 동일 timestamp는 나중 기록 우선), `record_deploy`가 teardown-only/rollback-only 자연어 run 라우팅. `local_deploy_api` rollback 배선(deployment_id/service/version/environment, scope=cluster→cascade).
  - Dashboard: **Provisioning**·**History**(Provisioning/Deployment Logs 2섹션·페이징) 페이지 신규, nav 워크플로순(Overview→Agents→Provisioning→Deployments→History→Incidents), **통합 중첩 상세**(상단 provisioning·하단 deploy `<details>` 아코디언, focus만 펼침), 롤백 **인앱 팝업**(Deployments=앱 전용/Provisioning=cluster teardown), 단일-row 갱신, cluster 없음/torn-down 시 Rollback 비활성화, **행 클릭→trace**(Trace 버튼 제거), `model-logo` 서버컴포넌트 onError 오류→client `model-logo-img` 분리, `getLifecycleDetail`.
  - Makefile: `dev-up`/`dev-down`/`dev-status` 한 방 스택 기동(MLX 재사용, router에 `PLATFORM_ACTIVITY_FILE`), `router-api`/`local-llm-up`에 오프라인 기록 env.
  - Docs: `linkedin-onprem-agent-20s-demo.md` 시나리오를 **자연어 명령 중심**(provision+deploy 한 문장→앱 롤백→History 중첩 상세→teardown cascade)으로 재작성.
- Verified: `make check`(anaconda) → **600 passed, 1 skipped**(recorder cascade 테스트 2개 신규); dashboard `tsc` 0 + `next build` 성공; dev 서버 `/provisioning`·`/history`·`/deployments` 200.
- Blockers: 신규 UI/자연어 cascade의 **라이브 end-to-end 실증 미완**(사용자 브라우저 테스트 예정); 미커밋(브랜치 `feat/onprem-offline-recording-hybrid-rollback`); 레거시 activity 행은 `cluster` 없어 롤백 비활성(클린슬레이트는 activity.jsonl 비우기).
- Next: 자연어 4스텝(provision+deploy→app rollback→History 상세→teardown cascade) 라이브 실증 → 전체 커밋 → 브랜치 push/머지 결정.

## 2026-07-12 — On-Prem 오프라인 기록 + Hybrid 대시보드 + 실 롤백 + Local Qwen 7B 전환

- Status: On-Prem 경로를 **기록→병합→롤백까지 오프라인으로 완결**. Local Qwen을 30B→**7B**로 전환하고 tool-call/컨텍스트 이슈를 해결해 자연어 provision→deploy→validate **~39s 자율 수행** 실증.
- Changed:
  - Python: `deploy_recorder` 로컬 JSONL 백엔드(`PLATFORM_ACTIVITY_FILE`); `local_deploy_api` `/api/local-rollback`(app rollout undo + cluster teardown); `mlx_qwen_tool_proxy` JSON/Hermes tool-call 파서(7B는 ```json 블록으로 tool call 방출); `local_deployer` `deploy_service` 복합툴 + 하드닝; provision/ops 출력 ANSI 절단(작은 모델 루프 유지).
  - Dashboard: `activity-data` **local + hybrid**(AWS DynamoDB + On-Prem JSONL 병합) read; rollback route onprem 분기(→라우터); deployments-control 버튼 provider/scope; `data-source-badge` local/hybrid; 모델 로고 4종 로컬 SVG·SELECTED 배지·timestamp `suppressHydrationWarning`.
  - 로컬 dev 로그인: `.env.local`에 `DASHBOARD_DEV_AUTH`/`NEXT_PUBLIC_DASHBOARD_DEV_AUTH`/`AUTH_SECRET`/`AUTH_TRUST_HOST`; `next dev` 구동(NEXT_PUBLIC 프로덕션 인라인 이슈 회피).
  - Makefile: pytest 가능한 인터프리터 자동 탐지(.venv-mlx 그림자 방지).
- Verified:
  - `make check`(anaconda) → **598 passed, 1 skipped**; dashboard `next build` 성공.
  - Live(7B): `provision_cluster`(~21s)→`deploy_service`→validate DONE **~39s**, orders-api 1/1 Running; **app 롤백** v2→v1(`rollout undo`); **cluster 롤백** teardown; `/api/dashboard/deployments`가 `source=hybrid`로 로컬+AWS 병합 반환(내 On-Prem 기록 포함).
  - 커밋 `0b9148c`(브랜치 `feat/onprem-offline-recording-hybrid-rollback`, 24 files/+558); tfstate gitignore.
- Blockers: 대시보드 rollback **버튼→라우트(auth 게이트)** 체인은 로그인 세션 필요해 curl 미검증(라우터 엔드포인트는 검증됨); `NEXT_PUBLIC`은 프로덕션(next start) 인라인 안 돼 `next dev` 사용; 브라우저 확장 미연결로 클릭 자동화 불가.
- Next: 로그인 후 UI Rollback 클릭 실증 → 브랜치 push/머지 결정 → (선택) NEXT_PUBLIC 프로덕션 인라인 해결.

## 2026-07-11 — On-Prem 실 k3s Provision + Agents 선택 UX + LinkedIn 데모 초안

- Status: 기존 Multipass `k8s-lab` VM에 Ansible k3s Provision을 실제 적용하고, Agents 화면을 Agent→Model→Runtime→trace 단일 선택 흐름으로 재구성.
- Changed: k3s config 디렉터리 생성/idempotency 수정, local inventory·kubeconfig ignore; On-Prem runtime panel/router 상태, Agent/Model selection, 실제 model brand asset; `docs/post/linkedin-onprem-agent-20s-demo.md` 추가.
- Verified: k3s v1.31.4 control-plane Ready; Ansible 재실행 `changed=0`; Dashboard `npm run build` 성공.
- Blockers: AWS CDK live diff는 Lambda dependency bundling이 완료되지 않아 재검증 필요; kagent 기본 agent 정리 여부 미결정.
- Next: CDK diff 재검증 → kagent 기본 agent 유지/정리 결정 → 명시 요청 시 push.

## 2026-07-11 — Supervisor 요청 라우팅 + A2A 위임 경계

- Status: Orchestrator(supervisor)의 최소 수직 슬라이스 구현 — 자연어 요청을 provision/deploy/kagent 역할로 분류하고, 등록된 specialist endpoint로만 A2A `message:send` 위임.
- Changed: `supervisor.py`(결정·trace·표준 HTTP A2A client), Gateway A2A Server의 route trace artifact, `PLATFORM_{PROVISION,DEPLOY,KAGENT}_A2A_URL` 환경변수 registry, 라우팅/위임/안전한 미등록 상태 테스트 추가.
- Verified: `pytest tests/test_supervisor.py tests/test_gateway.py -v` → 37 passed. 전체 `pytest tests/ -q`는 외부 pytest 런타임에서 종료 출력이 확보되지 않아 baseline 갱신 없이 유지.
- Blockers: 실제 kagent A2A endpoint 및 Agent Card discovery/skill 기반 라우팅 미연결; 현재 Agent Card는 Gateway `/.well-known/agent-card.json` 노출·검증만 사용.
- Next: kagent endpoint 등록 → Agent Card discovery/능력 매칭 → 로컬 Qwen ModelConfig 연결.

