# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-14

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-14 — 대시보드 On-Prem 승인 연동: Incidents 페이지 hybrid(AWS+On-Prem) + approve/reject 라우팅

- Status: 직전 On-Prem 승인 게이트를 **대시보드 화면에 연동**. Incidents 페이지의 "Pending Remediation Approvals"가 이제 AWS(DynamoDB/SFN) + On-Prem(webhook `/pending`)을 **hybrid 병합** 표시하고, Approve/Reject 클릭이 source에 따라 SFN 또는 webhook으로 라우팅됨. deployments 대시보드의 AWS+On-Prem hybrid 패턴을 승인에도 적용.
- Changed: `dashboard/src/lib/approval-data.ts` — `ApprovalRequest.source`(aws|onprem) 추가, `ONPREM_WEBHOOK_URL`(기본 `:8078`) HTTP 읽기(`fetchOnPremPending`/`mapOnPremApproval`), `listPendingApprovals`=AWS+onprem 병합, `getApprovalRequest`=onprem 우선 조회, `approve/rejectApprovalRequest`=onprem이면 webhook `/approve`·`/reject`로 분기(SFN 대신). `dashboard/src/components/pending-approvals.tsx` — source 배지(On-Prem 파랑/AWS 주황) 추가. 내 신규 `any` 제거(타입 지정) + 기존 `let mockApprovals`→`const`.
- Verified: `tsc --noEmit` 0, `next build` **Compiled successfully**(11 routes). **라이브 헤드리스 실증**: webhook(:8078)에 P2 pending(APR-34398628) 생성 → `next start`(ONPREM_WEBHOOK_URL=:8078) → `GET /incidents` HTML에 On-Prem 승인 카드 렌더 확인(approval_id·**On-Prem 배지**·payments-api·generic-recovery·ONPREM-CreateChangeRequest). read 라우트는 public이라 무인증 렌더; approve 액션은 미들웨어 인증·RBAC·감사로그 공통. webhook approve/reject 자체는 앞선 세션에서 라이브 실증.
- Blockers: 없음. (브라우저 확장 미연결로 스크린샷은 생략, HTML 렌더 검증으로 대체.)
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드(실 executor·MCP Gateway 단일 카탈로그·클라우드 Provision 어댑터).

## 2026-07-14 — On-Prem Approval Flow(P2 승인 게이트) 구현: pending 스토어 + approve/reject

- Status: ARCHITECTURE의 On-Prem Approval Flow(🔲 계획) 코어 게이트를 **구현+라이브 E2E**로 완성. 직전 webhook이 P2에 `mode=APPROVE`를 반환하지만 승인/실행 수단이 없던 루프를 닫음. Guardian severity→mode 게이팅을 webhook에 배선: **P1=즉시 실행 · P2=parking · P3=알림만**.
- Changed: `onprem_incident_pipeline.py`에 실행 분리(`run_incident_pipeline(..., execute=False)` + `execute_incident(decision)` 재생 헬퍼). 신규 `src/agents/ai/onprem_approvals.py`(오프라인 JSONL pending 스토어, deploy_recorder식 single-row 승계: create/list/get/resolve, `PLATFORM_APPROVALS_FILE`). `onprem_webhook_api.py`에 `GET /pending`·`POST /approve/{id}`(decision 재생 실행)·`POST /reject/{id}` 추가 + `PipelineResult.status`(executed/pending_approval/notified/approved/rejected). `test_onprem_webhook.py` 6→11(P1 AUTO·P2 park→approve/reject·P3 notified·404/409). Makefile approval env. ARCHITECTURE On-Prem Approval Flow 🔲→부분 ✅.
- Verified: `pytest tests/test_onprem_webhook.py` 11 passed. **실 HTTP 승인 루프 스모크**: `POST /webhook/alertmanager`(P2 heuristic)→`pending_approval`(APR-B8C3DDF2, incident_id null)→`GET /pending` count 1(전체 decision 보존)→`POST /approve/{id}`→`approved`+incident_id INC-8D539D65+executed→`/pending` count 0. `make check` → **614 passed, 1 skipped**.
- Blockers: 없음. 잔여(로드맵): Slack 버튼 프런트엔드·Temporal/Redis/PostgreSQL substrate·실 executor(MCP Gateway).
- Next: (외부/deferred) Slack App·아티클. 로드맵 잔여 빌드.

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
