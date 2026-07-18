# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-19

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-19 — 알림성 액션 in-process 1급 처리: generic-recovery 구조적 미해결 근본수정 (gate 844→847)

- Status: 직전 규명한 유령 SSM 문서 결함을 권고안(a)로 수정·라이브 검증 완료. Slack E2E발 후속 3건 전부 소진.
- Changed(`55de55e`): executor에 `_NOTIFICATION_ACTIONS`(={AWS-SendSlackAlert}) — SSM 호출 없이 executor 자신의 Slack 인시던트 리포트로 수행·executed 집계(웹훅 미설정=skip 유지). `tests/test_executor_notification_action.py` +3(in-process·no-webhook skip·혼합 액션 SSM 디스패치 보존).
- Verified: `make check` → **847 passed, 1 skipped**(232.55s, 844→847). **라이브**: 알람 트리거 → 실 LLM **P1/AUTO** 판정 → `executor.notify.in_process` → **`resolved=True`**(INC-E15BA62E, DynamoDB `resolved:true` 확증) — generic-recovery 최초 Resolved. 동일 세션에서 P3/MANUAL 강등 경로도 관측(온화한 알람 reason→LLM P3 판정, Guardian 정책상 정상 skip). 실 LLM 심각도 판정이 reason 텍스트에 반응함을 실증(P3/P2/P1 3단 모두 관측).
- Blockers: 없음.
- Next: 잔여=사용자 게이트(아티클 배포·terraform apply·push 여부) + 선택(On-Prem 승인 게이트 Slack 버튼 연동).

## 2026-07-19 — Analyzer Bedrock 무효 모델 ID 근본수정 + 라이브 검증 · SendSlackAlert skip 규명 (gate 844 유지)

- Status: Slack E2E가 표면화한 후속 2건 처리. (1) Bedrock 정정=완료·라이브 검증, (2) executor skip=근본 원인 규명(수정 방향은 사용자 결정 대기).
- Changed(`9a56949`): 스택이 `.env` 무시하고 무효 ID `anthropic.claude-sonnet-4-5` 하드코딩(InvokeModel은 인퍼런스 프로파일 필요 → **ValidationException, 매 인시던트 휴리스틱 폴백 강등**되던 latent 결함) → `process.env.BEDROCK_MODEL_ID ?? 'us.anthropic.claude-sonnet-4-6'` + IAM을 프로파일 ARN+라우팅 3리전 하위 모델 정확-ARN으로 재구성(bare `"*"` 없음). analyzer 기본값 정합. `.env`도 `us.` 프로파일로 갱신.
- Verified: `make check` → **844 passed, 1 skipped**(232.68s). **라이브**: 알람 재트리거 → `analyzer.llm_done`(confidence 0.52, **실 Claude 분석 root cause가 Slack 승인 카드에 문장형 표시**) → Approve 클릭 → SFN SUCCEEDED(APR-A1EA0CD8565E).
- Blockers: 없음.
- Next: **executor `AWS-SendSlackAlert` skip 규명 결과 = 수정 방향 결정 필요**: 카탈로그(generic-recovery·`open_change_request` 캐퍼빌리티 전체)가 **실존하지 않는 SSM 문서**를 참조 + Executor role IAM allowlist에도 없음(라이브 에러=AccessDenied, IAM 열어도 NotFound) → generic-recovery는 구조적으로 `resolved=False`. 선택지: (a) 알림성 액션을 in-process Slack 송출로 1급 처리(권고) (b) 실 SSM 문서 작성 (c) 의도된 skip으로 문서화만.

## 2026-07-19 — Slack App 실 생성 + 인터랙티브 승인 버튼 라이브 E2E 완주 (gate 843→844)

- Status: 사용자 게이트 "Slack App 실 생성/토큰" **해소**. 사용자=App 생성(Incoming Webhook `#platform-test`·Interactivity Request URL=ApprovalBridgeFunctionUrl·Signing Secret→`.env`), 에이전트=cdk deploy env 주입→알람 트리거→**브라우저로 Slack Approve 버튼 클릭**→SFN 완주. 라이브가 프로덕션 버그 2건 표면화→근본수정→가드(발견→수정→가드 루프 재실증).
- Changed(`0f99420`): (1) **detector** — `_normalise_incident`가 미존재 `_SIGNAL_ADAPTER` 전역 참조(NameError로 **AWS 경로 전면 불능**; 기존 테스트는 non-AWS 경로만 커버라 은닉) → `get_signal_adapter("aws")` 정합 + AWS 경로 실 normalisation 회귀 테스트. (2) **approval_bridge** — pending 저장 시 confidence를 float로 `put_item`(boto3 resource=Decimal만 허용, **TypeError로 승인 요청 전량 소실**; e2e 페이크 테이블이 타입 무검증이라 은닉) → `Decimal` 변환 + 페이크에 실 시리얼라이저와 동일한 float 거부 계약 이식. (3) `.claude/settings.local.json` allow 2건(`source .env && npx cdk deploy/diff`).
- Verified: `make check` → **844 passed, 1 skipped**(234.56s, 843→844). **라이브 E2E**: `set-alarm-state` ALARM→EventBridge→SFN→WaitForApproval→Slack 버튼 메시지(APR-8BC7E7E95B9A)→**Approve 클릭**(서명 HMAC 검증→DynamoDB claim=APPROVED→`SendTaskSuccess`)→SFN **SUCCEEDED**→최종 리포트 INC-2AC4B6C9 게시. 증거 `docs/evidence/slack-interactive-approval-live.log`.
- Blockers: 없음. (참고: 실패 승인 메시지 1건은 maxReceiveCount=1로 DLQ행 — 정리 선택.)
- Next: 후속 후보 — Analyzer `BEDROCK_MODEL_ID` invalid(ValidationException, 휴리스틱 폴백 중) 정정 · executor `AWS-SendSlackAlert` skip 의도 확인. 잔여 사용자 게이트 = 아티클 배포·(billable) terraform apply.

## 2026-07-18 — OAuth 대시보드 배포 트리거 라이브 E2E + 프로덕션 장애 2건 근본수정 (gate 842→843)

- Status: 사용자 게이트 항목 "OAuth UI 배포 클릭 데모" 수행 중 프로덕션 장애 2건을 발견·근본수정하고 E2E 완주. 과금 감사 병행(platform-agent 유휴 $0, slackops EBS 월~$5만 잔존).
- Changed: (1) **`.vercelignore` 앵커링**(`d5e4487`) — 무앵커 `src/`가 `dashboard/src/`까지 제외해 **git 트리거 Vercel 배포가 전부 404 빌드**였음(동일 커밋 CLI=200/git=404로 실증). 수정 후 canonical 200 + git 파이프라인 정상화. (2) **CDK**(`bb65c32`) — CloudTrail로 **07-11 Vercel OIDC provider 삭제**(context 미지정 배포 함정 실화) 규명 → provider 재생성(실 team slug `men16922s-projects`, Vercel API 확증) + role trust 정합 + **정확-ARN `states:StartExecution`**(deployment/provisioning 2개)+`ListStateMachines`. (3) **`smoke_tester.py`**(`025ca69`) — 라이브 클릭이 표면화한 계약 버그(`KeyError 'base_url'`): base_url 옵셔널화(빈 체크=공허 통과, no_canary_data와 동일 시맨틱)+회귀 테스트. (4) 아티클 3종 수치 최신화(736/738→842, eval 로드맵 문장→구현 완료 사실).
- Verified: `make check` → **843 passed, 1 skipped**(236.08s, 842→843). **라이브 E2E**: GitHub OAuth(operator) UI → Start Release → `DEP-612170AC`(FAILED=버그 표면화) → 수정 배포 → `DEP-1F054864` **SFN SUCCEEDED**(`needs_approval:false`) → 대시보드 라이브 피드 반영. 대시보드 배지 **DEMO FALLBACK → LIVE · AWS**(OIDC 복구로 실 DynamoDB 51건). 증거 `docs/evidence/oauth-deploy-trigger-live.log`.
- Blockers: 없음. cdk deploy는 `.claude/settings.local.json` allow 규칙(사용자 승인)으로 해금.
- Next: 잔여 사용자 게이트 = 아티클 배포(원고 842로 최신화 완료)·Slack App·(billable) terraform apply.

## 2026-07-17 — 차트 k3s substrate 스모크: env×substrate 양축 실증 완결 (코드 무변경, gate 842 유지)

- Status: 마지막 선택 소품 수행. **기존** Multipass `k8s-lab`(k3s v1.31.4, Ansible 프로비전 자산) 재사용 — 클러스터 생성 없음, 릴리스 설치→검증→제거·반입 이미지 정리로 VM 원상 복원.
- Changed: `docs/evidence/helm-k3s-substrate-smoke.log`만.
- Verified (라이브): 이미지 tar 전송→`k3s ctr import`(199MB; exec-stdin 스트림은 EOF라 tar 경로가 정석) → `helm install -f values-k3s.yaml` → pod 1/1 Ready ~29s → **PVC가 `local-path`로 Bound**(k3s 오버레이의 핵심 검증; kind는 `standard`) → `/health/ready` 200 → Alertmanager 페이로드→P2 parking(APR-0515026F)→approve→INC-3219D4A8 resolved → uninstall·이미지 제거. **동일 차트가 kind/k3s 양 substrate에서 오버레이만 바꿔 동일 동작 — 레퍼런스 #7 env×substrate 레이아웃 양축 실증 완결.**
- Blockers: 없음.
- Next: **자율 백로그 전면 소진.** 잔여=전부 사용자 게이트(아티클 배포·OAuth 데모·Slack App·terraform apply).

## 2026-07-17 — 차트 State Store 배선(④↔#7 연결 마무리): stateStore values + DSN 멀티-레플리카 모드 (gate 839→842)

- Status: ④(SQL State Store)와 #7(Helm/Terraform)을 잇는 마지막 소품. 차트가 DSN 모드를 1급 values로 지원 — JSONL 기본값 무변경.
- Changed: (1) `values.yaml` `stateStore.{dsn,existingSecret,secretKey}` — **existingSecret(secretKeyRef)=프로덕션 경로**(values에 평문 DSN 금지), plain `dsn`=dev/kind 편의, secret이 plain보다 우선. (2) `_helpers.tpl` `stateStoreEnv`+`strategy`(persistence off→**RollingUpdate**, JSONL RWO일 때만 Recreate) — webhook/router 양쪽 주입. (3) **`infra/onprem/Dockerfile` `.[state]` 설치**(psycopg2 — 없으면 DSN 모드 이미지가 실동작 불가, 재빌드+import 검증). (4) README 2종: 차트=DSN 모드 사용법(라이브 증거 링크), Terraform=`kubectl create secret`+`stateStore.existingSecret` 스니펫(extraEnv 핵 대체). (5) 차트 가드 +3: 기본=DSN env 부재·dsn/secret 모드(secret 우선·평문 무노출)·**DSN 모드=PVC 없음+replicas 2+RollingUpdate**.
- Verified: helm lint 통과, `make check` → **842 passed, 1 skipped**(234.42s, 839→842). 이미지 재빌드 후 `import psycopg2` OK.
- Blockers: 없음.
- Next: 자율 백로그 소진. 잔여=사용자(아티클 배포·OAuth·Slack·terraform apply)·선택(k3s 스모크).

## 2026-07-17 — 레퍼런스 #7-b Terraform 모듈(EKS/Aurora/IRSA) → #7 전체 완결 (gate 834→839, apply 없음·spend 0)

- Status: 레퍼런스 #7 잔여 Terraform 파트 구현·오프라인 검증(사용자 승인 "다음 수행"). apply는 하지 않음(billable=사용자 게이트). 이로써 **레퍼런스 #7 = Helm(#7-a)+Terraform(#7-b) 전체 완결** — AWSome AI Gateway 레퍼런스 8항목 전부 소화(Tier 1 4종+Tier 2 3종+#7).
- Changed: 신규 `infra/terraform/aws-production/`(7파일) — VPC(2AZ·public/private·NAT 1) + EKS 1.31(managed node group, AWS-managed 정책만 ARN attach) + **Aurora PostgreSQL Serverless v2**(min 0.5 ACU·`database_name=platform_state`=④ `PLATFORM_STATE_DSN` seam 정합·`manage_master_user_password`=Secrets Manager, 평문 무노출) + **IRSA**(OIDC provider+차트 SA 전용 trust[sub+aud]·**유일 grant=DynamoDB activity 테이블 정확 ARN**+index, deploy_recorder가 실 소비자) + outputs(DSN 템플릿·IRSA arn·helm 배선 스니펫 README). Redis/Cognito는 **미소비라 의도적 제외** 명시. `tests/test_terraform_module.py` +5(구성 완비·**bare `"*"` 금지**[주석 제외]·state seam 정합·IRSA trust 스코프·validate[init 시]).
- Verified: `terraform init`+`fmt -check`+**`validate` Success**(크레덴셜/spend 0). `make check` → **839 passed, 1 skipped**(238.51s, 834→839). ARCHITECTURE 표 #7 ✅.
- Blockers: `terraform apply`=billable(EKS ~$0.10/h+노드+NAT+Aurora) — 사용자 게이트.
- Next: 자율 코드/인프라 백로그 재소진 — 잔여는 사용자 몫(아티클 배포·OAuth·Slack·apply류) + 선택 소품(k3s 스모크·차트 DSN values).

## 2026-07-17 — 로드맵 ④: SQL State Store(옵트인) + 실 Alertmanager 라이브 E2E — 멀티-레플리카 실증 (gate 829→834)

- Status: ARCHITECTURE 잔여 ④(On-Prem State Store·Alertmanager 실연동)를 로컬 docker($0)로 완결. JSONL 단일-writer 제약(Helm 차트 replicas:1의 근거)을 푸는 productionization seam.
- Changed: (1) 신규 `src/agents/ai/state_store.py` — `SQLStateStore`(DB-API connect 주입·placeholder/autoincrement 파라미터·append-only+latest-wins=JSONL 시맨틱 동일)·`from_dsn`(postgresql→psycopg2, sqlite://→stdlib)·`configured_store`(`PLATFORM_STATE_DSN` 옵트인, 미설정=None=JSONL 무변경). (2) `onprem_approvals`/`onprem_incidents` 읽기·쓰기 양쪽에 seam 배선. (3) pyproject `state = ["psycopg2-binary>=2.9"]` extra. (4) `tests/test_state_store.py` +5(sqlite 오프라인: 시맨틱·라우팅·JSONL 비오염 양방향).
- Verified: `make check` → **834 passed, 1 skipped**(242.90s, 829→834). **라이브 E2E**(docker postgres:16 + prom/alertmanager:v0.28.1): ① **실 Alertmanager가 자체 grouping 후 native 페이로드 배달**(손 페이로드 아님)→4-step→P2 parking→**PostgreSQL row**. ② **레플리카 2개**(동일 DSN, 별개 프로세스): replica-2가 pending 조회·**승인 실행**→replica-1 즉시 pending 0+incident 반영(JSONL 불가능한 것). ③ 양 프로세스 kill→재기동→상태 생존. ④ psql ground truth 3 rows(pending→approved append-only→incident). 전량 teardown. 증거 `docs/evidence/state-store-alertmanager-live.log`.
- Blockers: 없음. Helm 차트에서 DSN 설정 시 replicas>1 해금(차트 values 배선은 후속 소품).
- Next: #7-b Terraform 모듈(클라우드=승인) or 사용자 항목(아티클/OAuth/Slack).

## 2026-07-17 — 레퍼런스 #7-a Helm 차트 kind 라이브 실증 (코드 무변경, gate 829 유지)

- Status: 방금 만든 차트를 전용 kind 클러스터(`pa-helm`)에 실 `helm install`로 end-to-end 실증(사용자 승인). 외부 GKE 컨텍스트 불가침(전 kubectl `--context` 핀), 실증 후 전량 teardown + 원 컨텍스트 복원.
- Changed: `docs/evidence/helm-kind-live-install.log`만(코드 무변경).
- Verified (전부 라이브): (1) `kind load`+`helm install` → deployed·NOTES 정상. (2) webhook pod **1/1 Ready ~12s**(strict `/health/ready` readiness in-cluster 그린)·PVC Bound 1Gi. (3) **RBAC 최소권한 auth can-i 실증**: SA로 patch deployments/get replicasets/patch scale=**yes** · patch nodes/delete pods/create pods\/eviction/delete deployments=**no**(drain off 기본). (4) **Day-2 E2E**: 실 Alertmanager 페이로드 POST → in-pod 4-step(휴리스틱 폴백, Bedrock creds 무=설계) → **P2 APPROVE parking**(APR-284A4249) → `/pending`→`/approve` → executed+resolved(INC-5D000FBD) → `/incidents` 기록. (5) **PVC 영속성**: pod 삭제→새 pod가 동일 인시던트 서빙.
- Blockers: 없음. 잔여=#7 k3s substrate 스모크(선택)·#7-b Terraform 모듈(클라우드=승인).
- Next: ④ State Store/Alertmanager 실연동(로컬 docker) or #7-b or 사용자 항목(아티클/OAuth/Slack).
