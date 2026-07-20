# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-20

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-20 — On-Prem 플랫폼 애드온 스택 Phase 1+2: addons IaC + Alertmanager→4-step 라이브 E2E (gate 854→861)

- Status: 신규 백로그(JOURNEY 범위 로컬 확장, `docs/plans/2026-07-20-onprem-platform-addons.md`) Phase 1·2 완료. Phase 3(GitOps)·4(Rollouts) 대기.
- Changed: 신규 `infra/onprem/addons/` terraform root — helm provider(~>3.0), kubeconfig/context 변수로 kind·k3s 양기판 적용, **argo-cd 10.1.4**(앱 v3.4.5=JOURNEY 동일)+**kube-prometheus-stack 87.17.0** 정확 핀, 저사양 values(CPU requests ≤50m 계약, kind 불가 컨트롤플레인 스크랩 4종 off). Alertmanager receiver→in-cluster `pa-platform-agent-webhook`(templatefile `webhook_url` 주입, Watchdog은 null 라우트) + 데모 룰 `PlatformDemoCrashLoop`(restarts>2/5m, for 1m). 가드 `tests/test_onprem_addons_module.py` +7(핀·저사양 계약·receiver 배선·룰 존재·validate).
- Verified: `make check` → **861 passed, 1 skipped**(229.27s, 854→861). **라이브($0)**: kind 3노드 apply→ArgoCD 5파드+모니터링 8파드 전부 Ready→UI 3종(ArgoCD/Grafana/Prometheus) 200. **E2E**: crashme 크래시루프→룰 발화(~3분)→Alertmanager 배달→webhook 4-step→P2 parking(APR-6C9CD1F2)→approve→executor(log-only)→**INC-96D41C2B resolved=true**. 증거 `docs/evidence/onprem-addons-phase1.log`·`onprem-addons-alertmanager-e2e.log`.
- Blockers: 없음. 규명 메모: 인클러스터 analyzer의 휴리스틱 폴백(Bedrock 자격증명 없음)은 설계된 오프라인 경로(`onprem_incident_pipeline` docstring) — 차트 `llm.endpoint`는 배포 플레인 router 전용, 버그 아님.
- Next: Phase 3(ArgoCD Application으로 차트 GitOps — ⚠️ 선행: push 또는 로컬 gitea) · Phase 4(Argo Rollouts canary) · Phase 5 선택.

## 2026-07-20 — 3-클라우드 비용 감사·고아 리소스 정리 + 예산 알림 3종 완비 (코드 무변경, 계정 운영)

- Status: AWS 예산 알림($8.90)발 3-클라우드 전수 감사. 원인=크레딧 차감 전 총사용액(실청구 ~$0.25)이었으나 감사 중 고아 과금원 다수 발견·정리.
- Changed(계정, repo 코드 무변경): **AWS** 고아 Classic ELB(7/9~, `platform-agent-demo` k8s 잔재, 일$0.60)+전용 SG 삭제. **GCP** `claude-study-501117`의 GKE `notiflex-cluster`+Gateway LB+PVC 2 삭제(월~$20 차단), 타 계정 8프로젝트=청구 미연결 확인. **Azure** ACR `roadpilot-backend` 21→1 이미지(최신만 유지). **예산 알림**: Azure·GCP에 월 ₩14,000(≈$10) 예산+80/100% 이메일(men16922@gmail.com, GCP는 billing.user 부여) — AWS 기존 $10과 3종 완비. `.claude/settings.local.json`에 `aws/gcloud/az` CLI allow 3종(개인 스코프).
- Verified: 삭제 후 잔존 0 재확인(AWS ap-northeast-2 ELB/NAT/EIP/EC2/EKS=0, GCP claude-study LB/IP/disk=0), Azure 일별 비용 추이로 AKS 잔재 종료 확인. 합산 월 ~$40 유휴 과금 차단.
- Blockers: 없음. 메모: Azure `acrroadpilot` Basic 고정료(월~₩7,700)는 roadpilot 종료 시 레지스트리 삭제로 정리 가능(프로젝트 범위 밖).
- Next: 잔여=아티클 배포(사용자 "나중에")·push(로컬 ahead 2).

## 2026-07-20 — 보류됐던 리팩토링 후속 2건 완료: operations 그룹핑 축 통일 + approval_bridge 분리 (gate 854 유지)

- Status: NEXT_PLAN "리팩토링 후속(선택)" 2건을 사용자 승인으로 수행. 동작 무변경 순수 구조 개편.
- Changed(`8792c9c`): (1) **그룹핑 축 통일** — AWS Lambda 핸들러 7종을 `operations/aws/{detector,analyzer,decision,executor,reporting,runbook_seed}.py` + `aws/approval_bridge/`로 이동(gcp/azure와 동형), 멀티클라우드 러너 5종(gcp/azure/onprem/_k8s_rest/gcp_auth)을 `operations/runners/`로 분리. CDK 핸들러 문자열 7종·테스트 15파일 임포트 정합. (2) **approval_bridge 분리** — 610줄 handler.py → `handler`(오케스트레이션+SFN 콜백)+`request_store`(DynamoDB pending/claim/finalise)+`slack_interactive`(서명 검증·Block Kit·webhook)+`payloads`(순수 헬퍼). 핸들러가 함수를 unqualified import해 핸들러 경로 함수 패치는 보존, 모듈 전역 패치(웹훅/시크릿/테이블/requests)만 소유 모듈로 재작성.
- Verified: `make check` → **854 passed, 1 skipped**(256.62s) — baseline 동일(테스트 수 무변경=순수 구조 개편 증명). 직접 영향 테스트 12파일 선행 통과.
- Blockers: 없음. 주의: 다음 cdk deploy 시 핸들러 경로 변경이 반영됨(Vercel context 필수 규칙 유지).
- Next: 잔여=아티클 배포(사용자 "나중에")·push. 코드 백로그 없음.

## 2026-07-19 — terraform aws-production 실 apply→검증→destroy 완주 + 아티클 854 최신화 (코드 무변경, gate 854 유지)

- Status: 마지막 billable 사용자 게이트 "(billable) terraform apply" 소진(사용자 허용 규칙 추가로 해금). 레퍼런스 #7-b = 코드·validate·**실 apply/destroy** 전 단계 실증 완료.
- Changed: `docs/evidence/terraform-aws-production-apply-live.log` + 아티클 3종 854 최신화·승인 게이트 Slack 라이브 사실 보강(`0f19d12`). `.claude/settings.local.json`에 terraform apply/destroy/output/state list/show allow 5종(개인 스코프 — apply/destroy는 사용 후 제거 권장).
- Verified (라이브): 1차 apply가 로컬 DNS 블립으로 EKS 폴링 실패(실 클러스터는 ACTIVE, terraform만 tainted)→재개 apply가 replace 포함 수렴(**8 added/1 destroyed**). 검증: EKS 노드 2 **Ready**(v1.31.14)·Aurora `platform_state` **available**(0.5 ACU)+마스터 시크릿·**IRSA trust가 재생성 클러스터 OIDC로 정확 재배선**(차트 SA 한정)·outputs/DSN 템플릿 정합 → **destroy 29개 완료**, 계정 잔존 0(EKS/RDS/NAT). 비용 ≈$0.5 미만.
- Blockers: 없음.
- Next: 잔여 = 아티클 **배포**(원고는 854로 최신화 완료·사용자 "나중에") · push 수시 · (선택) settings의 terraform allow 정리.

## 2026-07-19 — On-Prem P2 승인 게이트 Slack 버튼 연동 + 라이브 왕복 완주 (gate 847→854)

- Status: 잔여 선택 항목 "On-Prem 승인 게이트 Slack 버튼" 구현·라이브 검증 완료. terraform apply(3번)는 분류기 차단으로 **사용자 `!` 실행 대기**.
- Changed(`617839b`): 로컬 API는 공개 URL이 없어 버튼 콜백 직수신 불가 → **DynamoDB 승인 테이블을 공유 매체**로: 신규 `onprem_slack_approval.py`(P2 parking 시 bridge 스키마·버튼 계약으로 PENDING 기록+Slack 송출, `sync_decisions` 결정 회수) + bridge onprem kind=SFN 콜백 생략 + webhook API approve/reject 코어 추출·startup 폴러. 전부 옵트인(`ONPREM_SLACK_APPROVAL`), 기본=오프라인 무변경. +7 test.
- Verified: `make check` → **854 passed, 1 skipped**(232.03s, 847→854). **라이브**: P2 페이로드→APR-3E6D2540 parking→DynamoDB PENDING(kind=onprem)→Slack ONPREM 카드(실 LLM root cause)→**Approve 클릭**→APPROVED→폴러 회수→실행→`/pending` 0·INC-FA2143AF resolved=true. 증거 `docs/evidence/onprem-slack-approval-live.log`.
- Blockers: terraform apply/destroy는 분류기+settings 자기수정 차단 — 사용자 `!` 또는 `/permissions` allow 필요.
- Next: (사용자) terraform apply→검증→destroy · 아티클 배포(나중) · push는 수시.

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
