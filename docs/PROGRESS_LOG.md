# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-19

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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
