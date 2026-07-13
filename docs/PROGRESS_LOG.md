# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-13

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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

