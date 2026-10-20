# COMPLETED_SUMMARY — platform-agent

최종 갱신: 2026-10-03

> 완료된 milestone 압축. current docs 에는 링크만, 상세 체크리스트는 여기로 압축.
> 도메인 원문 상세는 `bin/docs/archive/`.

---

## 2026-10-03 — 단일 환경 실사용 검증의 완료 범위

**목적:** 기존 배포·검증·복구를 실제 사용자 흐름에서 반복하고, 관측된 사용성/기록 결함만 보완했다. 조사·방향성 계획은 `docs/plans/2026-10-03-platform-agent-usage-and-evidence.md` §1~§7에 있다.
**산출:** 거짓 성공·고정0초·응답 유실·모델 입력 재생성 문제를 고치고 준비된 이미지의 입력→검토→확인→rollout→같은 ID 조회를 연결했다. 승인 거부 사유/사건 연결, 읽기 전용 도구 범위, 관측/미검증 해석 구분 및 snapshot 대상/시각 계약도 기존 경로에 연결했다.
**실측:** T 실행O/v15 정상3·제한 신원 거부2·실패 후 사용자 확인 복구2·새로고침2, 각 claim1/deploy1. 합성 승인 거부2·실행0, scope 누락2·dispatch0. 마지막 UID/전체 spec/r0/replicas2 복원(revision37). 재현 절차·전후 비교표·72초 정지화면 데모 완료. 증거 색인 `docs/evidence/dogfood-20261003/README.md`의 T 항목.
**검증:** T 작업트리R/v16 `make check` 3364 passed·2 skipped·20 warnings,133.83초(로컬 macOS·Python3.13.5·Node22.23.3/임시prefix). 실행O 자체의 앞선3356/2와 구분한다. 신규 기능의 운영/원격 CI 검증이 아니다.
**미완료:** 진단 의미 오류로 R3/R4 전체·R5 비교는 열려 있다. R 원문 전달 후보와 S 응답 계약은 미채택, U는 재현 전 코드 검토 가설이다. r0/r1 동일 digest·Pod liveness 관측·공유 deployer·합성 승인 경계를 유지하며 MTTR/테넌트 전체 격리/alert 분석 E2E로 확대하지 않는다. 사용자 요청으로 목표 paused.


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

## M91 — Vercel 인증 해소·운영 조회·배포 후보 재생성 (사전 점검 완료, 2026-09-15)

**산출:** 실제 Vercel project/production/도메인·반환 callback/OIDC 메타데이터와 AWS 기존 자원을 재확인했다. 사라진 tmp 후보를 Git 제외 작업 폴더에 재생성하고 §13의 정확 Origin·복구 대상·Hobby 롤백 조건을 확정했다.
**검증:** 대시보드 소스 106파일 M90 일치·공식 Node 24 Linux ARM64 clean npm ci/build 성공·audit 0. Python 3.9 marker 충돌은 기준 3.13 실행으로 해소. Lambda 3.13 ARM64 읽기 전용/네트워크 차단 import 8모듈·native YAML·422와 실제 CDK no-lookups 8자원 합성 통과. template은 asset 해시 외 M90과 동일. 증거 `docs/evidence/registry-planner-resume-verification-2026-09-15.json`.
**경계:** 원격 설정 조회와 로컬 후보 검증이다. AWS/Vercel 자원 변경·운영 로그인/Invoke/전환·PR 발행/원격 CI는 미실행이다. 실행 범위 확인이 다음이며 기존 WIP·lab/키/checkout 보존.

## M90 — 저장형 플래너 배포 후보·AWS 사전 점검 (부분 완료, 2026-09-13)

AWS 계정/리전·기존 사용자 테이블/OIDC/bootstrap·새 스택 부재와 공개 GitHub 계획을 읽기 전용으로 확인했다. 본인 사용자 Item은 없었다. 대시보드 WIP 12경로만 고정해 깨끗한 Linux Node 24 빌드, 기존 검증 Lambda asset과 실제 대상 CDK 합성을 완료했다. 원격 배포/권한 변경/Invoke/CI는 미실행이다.
검토안은 `docs/plans/2026-09-05-phase5-planner-runtime.md` §13, 증거는 `docs/evidence/registry-planner-candidate-verification-2026-09-13.json`. Vercel 인증·현행 production/복구 URL·callback 확인이 남았다. 기존 자원/키/WIP 보존.

## M89 — 대시보드 AWS 준비·상태 transport (로컬 완료, 2026-09-13)

**산출:** 공통 연결 설정·고정 Invoke operation/subject/request·제한된 응답 해석. 준비/상태 API와 화면은 AWS 저장 기능의 명시적 활성화를 요구한다.
**검증:** TS 118 passed(+37), Next build·실제 SDK 설정/네트워크 차단 실패·TS↔실제 Lambda/로컬 DB 왕복·인증 HTTP/Chrome 응답 유실 복구·변이 5종 red 후 복구. make check 3252 passed·2 skipped(106.21초, 2026-09-13 로컬 macOS·py3.13). 증거 `docs/evidence/registry-aws-transport-verification-2026-09-13.json`.
**경계:** 로컬 구현/검증이며 AWS Invoke·OIDC 원격 교환·IAM 집행/배포·PR 발행은 미검증. 기존 자원/키 보존.

## M88 — 저장형 Lambda·전용 계획 테이블 계약 (로컬 완료, 2026-09-13)

**산출:** 실제 Lambda의 preview 저장/prepare/status·별도 테이블/CDK 최소 IAM·배포 asset 모듈 8개. 기존 preview 요청 모양과 발행 미확인 의미를 유지한다.
**검증:** 관련 113 passed(+20), 실제 패키지/로컬 DB·8개 준비 경쟁·핵심 변이 4종 검출/복구, 공식 Python 3.13 Linux ARM64 import/SDK 설정·실제 CDK 앱 합성. make check 3215 passed·2 skipped(97.44초, 2026-09-13 로컬 macOS·py3.13). 증거 `docs/evidence/registry-lambda-storage-verification-2026-09-13.json`.
**경계:** 정의/로컬 검증이며 원격 테이블·함수 배포가 아니다. 대시보드 AWS 준비/상태 transport와 발행은 후속이다. 기존 키/자원 보존.

## M87 — 인증된 상태 HTTP·화면 복구 (로컬 완료, 2026-09-13)

**산출:** session subject·request_id 전용 status 경로와 opt-in 로컬 준비/조회 UI. 준비 응답 유실 시 자동 재전송 없이 상태를 조회하고 CLAIMED를 발행 성공으로 표시하지 않는다.
**검증:** TS 81 passed(+21), Next build·실제 Auth.js HTTP/DynamoDB Local·Chrome 유실/새로고침 복구, 핵심 변이 3종 red 후 바이트 복구. make check 3195 passed·2 skipped(88.14초, 2026-09-13 로컬 macOS·py3.13). 증거 `docs/evidence/registry-status-http-verification-2026-09-13.json`.
**경계:** production Lambda 저장/상태 배선·원격 배포/발행은 별도다. 기존 자원/키 보존, 이번 임시 로컬 자원만 정리.

## M86 — 본인 준비 요청 상태 조회 서비스 (로컬 완료, 2026-09-13)

상태 서비스와 local --status는 현재 본인의 요청만 조회한다. 서버 저장 payload/상태 불변식·현재 write grant를 검증하고 DB를 다시 읽어 동시 claim을 반영한다. CLAIMED→PREVIEW 재개와 claim ID 변경은 거부한다. 만료된 레코드는 만료 여부를 표시하되 TTL/준비권을 갱신하지 않는다. 응답은 PREVIEW/CLAIMED·expires_at/expired·published=false로 제한하며 내부 payload와 claim_id를 노출하지 않는다.

관련 60 passed(+20), 실제 DynamoDB Local·별도 CLI 프로세스와 4종 변이 검출/복구 확인. 본인/권한 회수/저장 변조/만료/동시 claim/실제 DB 테이블 부재를 검증했다. 임시 로컬 자원만 정리했고 원격 AWS/GitHub 호출은 없다. 증거 `docs/evidence/registry-status-verification-2026-09-13.json`. 인증 HTTP/화면 연결·production 저장/배포·발행은 별도다.

## M85 — 네 권한 진단의 오프라인 증거 조정 (완료, 2026-09-13)

고정 review bytes와 M83/M84 관측을 연결하는 writer_reconciliation·CLI를 추가했다. 시도/응답 ID·시각/토큰 유효 기간·신원/권한·Git/PR/작성 계정/파일·폐기 기록을 비교하며, 부분 일치/불충분/경계 위반을 구별한다. 원래 STOPPED와 네 증거 공백은 보존하고 발행 성공·재시도 권한으로 승격하지 않는다. 평가 시각과 관측 유효 기간은 호출자가 명시한다.

신규 55 passed, 변이 4종 검출/복구. 보존 기록을 M84 관측 시각으로 두 번 평가해 동일한 consistent_partial, 입력 SHA 불변 확인. 원격 조회·쓰기·민팅·키 접근 없음. 근거 `docs/evidence/writer-reconciliation-verification-2026-09-13.json`. PREVIEW/CLAIMED 상태 조회·production 연결/배포/UI는 별도다.

## M84 — nullable 작성 App 처리·별도 봇 계정 검증 (완료, 2026-09-13)

실제 nullable Issue 필드를 본뜬 로컬 HTTP 5건이 TypeError/KeyError를 재현했다. 기존 관측기는 형태/정수 ID를 확인해 pr_author_app_unavailable로 거부하며 기존 성공 가드는 유지한다. 별도 GET 전용 observe_pr_author는 App JWT의 실제 ID/slug·운영자 조회 봇 ID·PR/Issue 작성자를 대조하고, 모순 필드·다른 계정·조회 중 App 변경을 거부한다. 관련 95 passed(+25), 변이 3종 검출/복구.

실제 GET 11회로 App 4924748↔봇 328527925↔PR #1 작성자 대조, PR/files/refs 불변 확인. 원래 Issue null과 M83 STOPPED는 유지하며 과거 POST 자격증명/설치 신원 파일 조회를 증명했다고 하지 않는다. 설치 토큰 민팅·원격 쓰기 0회, 키/자원 보존. 상세는 `docs/evidence/writer-pr-author-verification-2026-09-13.json`. 전체 판정 연결·production writer/배포/UI는 별도다.

## M83 — Contents read 추가 후 draft PR 생성 실측 (부분 검증, 2026-09-13)

사용자 재다운로드 키로 정확한 네 권한·acme 경로·R2 저장소 한 곳을 API 대조하고, 운영자 branch 생성 201·설치 신원 ref 200·acme PUT 200·globex PUT 403·draft PR #1 생성 201을 확인했다. 독립 운영자 조회는 R2 App 봇·정확한 SHA·acme +1/-0·main/형제/기존 branch 불변을 확인했다. 토큰 revoke 204 후 같은 토큰 GET 401, 모든 자원/키/intent 보존.

실제 Issue performed_via_github_app=null이어서 검증기의 TypeError를 재현했다. 엄격한 작성 App ID·설치 신원 PR 파일 조회는 미검증으로 유지하고 원래 STOPPED 결과를 보존했다. 쓰기/민팅 재시도 없이 운영자 GET으로 조정했다. 증거 `docs/evidence/phase5-writer-ref-read-live-2026-09-13.json`. 자동 branch·tenant 읽기 격리·production 연결/배포/UI는 미완료다.

## M82 — 승인된 R2 읽기 권한 적용 (설정 완료·실험 미실행, 2026-09-13)

사용자가 M80 범위를 승인해 기존 App 4924748의 Contents read를 추가하고 설치 161238144에서 수락했다. 선택 repo는 lab 1367740190 한 곳, acme single_file write/PR write/metadata read는 유지됨을 UI에서 확인했다. R2 PEM이 기록된 Downloads 경로에 없어 토큰 민팅 전 중단했다. 실제 네 작업은 0회이고 JWT API 권한 재대조도 미실행이다.

운영자 읽기로 고정 main/기존 진단 head 불변·새 branch 부재·PR 0건을 확인했다. 파일 삭제/새 키 생성 없음. 증거 `docs/evidence/phase5-writer-ref-read-setup-2026-09-13.json`. 현재 키 경로만 인계받으면 재승인 없이 첫 토큰/작업을 시작할 수 있다. 이 항목은 권한 설정 결과이며 PR 발행 또는 production 완료가 아니다.

## M81 — CLI bootstrap 실패 토큰 정리 (로컬 완료, 2026-09-13)

--execute에서도 어댑터 생성/구성 오류가 executing 플래그 설정 전에 나면 전달된 토큰이 정리되지 않음을 실제 로컬 HTTP로 재현했다. private journal을 확인한 뒤 설치 토큰부터 인수하고 명시적 실행 요청의 이후 실패를 revoke/같은 토큰 401로 처리한다. journal 미확보·토큰 미인수는 호출자 책임이다. 오프라인은 계속 API 0회, 기존 권한 guard와 전체 workflow 재전송 차단은 유지한다.

7 failed·7 passed → 신규 16 passed·관련 70 passed. 폐기 누락/오프라인 네트워크/조기 인수 변이 3종 검출 후 소스 바이트 복구. 반복 실행은 이미 무효인 토큰을 조회하고 두 번째 DELETE를 보내지 않았다. 증거 `docs/evidence/writer-bootstrap-cleanup-verification-2026-09-13.json`. 실제 GitHub 호출·민팅·권한 변경은 없으며 M80 승인 질문은 대기 중이다.

## M80 — Contents read 후속 권한 시험 검토 (준비 완료, 2026-09-13)

실제 App 4924748 권한 폼에서 Contents Read-only와 Single file Read and write가 미저장 상태로 공존함을 확인하고 새로고침으로 취소했다. 기존 설치 161238144는 lab 1367740190 한 곳·기존 세 권한이다. `experiments/phase5-writer/retry-20260913/ref-read-execution-review.md`와 ref-read-review.json에 변경할 네 권한·고정 요청·단계별 중단·토큰 폐기·자원 보존을 명시했다. base64/해시 및 synthetic 파일 각각 +1/-0 로컬 대조 완료.

증거 `docs/evidence/phase5-writer-ref-read-review-2026-09-13.json`. 원격 권한 저장·민팅·API 쓰기·삭제는 0회이며 폼 공존만으로 서버 허용이나 PR 성공을 주장하지 않는다. 사용자 확인이 필요한 구체 범위는 기존 R2 App/설치 Contents read 추가·새 운영자 branch 1개·acme 허용/globex 거부 각 1회·조건부 draft PR 최대 1건이다. 기존 키를 사용하며 production writer/배포/UI는 미완료다.

## M79 — R2 PR-only ref 읽기 오류 실측 (진단 완료·PR 미성공, 2026-09-13)

사용자 계속 지시 후 기존 App/설치/branch를 재사용하고 검토된 PR POST 한 번만 실행했다. 422 상세 `not all refs are readable`를 비공개 진단에서 확인했다. PR 0건·snapshot 불변, 새 토큰 revoke 204 후 GET 401. 기존/R2 자원·종료 intent 보존. 증거 `docs/evidence/phase5-writer-r2-pr-diagnostic-2026-09-13.json`.

공식 ref 조회 권한은 Contents read여서 현재 권한 부재와 일치하나, 추가 후 PR 성공 또는 기존 파일 경계 보존은 미실증이다. M70/M77의 버린 상세는 복원하지 않았다. `experiments/phase5-writer/retry-20260913/ref-read-followup.md`에 권한 추가 후보·publisher 분리·tenant repo 이관의 경계와 다음 로컬 검토를 정리했다. production writer/배포/UI는 미완료다.

M79 문서 반영 후 `make check` 3058 passed·2 skipped(2026-09-13 로컬 macOS·py3.13, 증감 0). 옛 PEM은 기록된 Downloads 경로에서 미발견이며 이번 실행에는 삭제가 없었다. R2 PEM·두 checkout은 존재 확인.

## M78 — opt-in 미분류 PR 오류 상세 수집 (로컬 완료, 2026-09-13)

`writer_diagnostics.py`와 실제 GitHub 응답 경로·CLI --error-details-dir을 연결했다. 세 자격증명과 일반 토큰/PEM/URL 형태 제거, 오류당 512·합계 1024 UTF-8 바이트 제한, 사용자 소유 0700 디렉터리/0600 파일, request ID 연결. 기본 M73 기록·실행 권한은 유지하고 상세는 stdout/결과로 반환하지 않는다. 저장 실패는 UNKNOWN으로 중단하며 기존 종료 요청을 다시 열지 않는다.
합성 미분류 문구가 사라지는 현상을 재현한 뒤 보존 전후를 확인했다. 실제 loopback HTTP·파일/새 프로세스 회귀 224 passed, 전체 3058 passed·2 skipped(로컬 macOS·py3.13, +20), 변이 3종 검출/복구. 증거 `docs/evidence/writer-diagnostics-verification-2026-09-13.json`. 임의 텍스트의 모든 비밀을 탐지한다는 보장은 없으며 reviewed synthetic 실험에만 사용한다. 실제 M77 문구는 복원 불가, 후속 PR-only 검토는 준비됐지만 원격 호출은 미실행이다.

## M77 — R2 실제 단일 파일 권한 시험 (실측 완료·PR 미성공, 2026-09-13)

새 private lab 1367740190·App 4924748·설치 161238144를 만들고 사용자 새 PEM으로 신원을 확인했다. ref 403으로 자동 branch 가설은 실패, 승인된 운영자 branch 진단에서 acme PUT 200·globex PUT 403·PR 422를 관측했다. 독립 Git 비교로 acme 한 줄·main/형제 불변·PR 0건 확인. 두 제한 토큰은 각각 revoke 204 후 GET 401 확인했고 기존/새 자원은 모두 보존했다.
PR 오류는 validation_failed / PullRequest / custom까지 수집했으나 상세 문구가 unclassified로 남아 원인은 미확정이다. 키 원문/토큰/JWT는 저장하지 않았다. 증거 `docs/evidence/phase5-writer-r2-live-2026-09-13.json`. 다음은 custom 진단 수집 계약 보완이며 종료 실행 재전송·권한 확대·production 연결을 완료했다고 주장하지 않는다.

## M76 — GitHub 요청·독립 관측 어댑터와 R2 실행 검토 (로컬 완료, 2026-09-13)

`writer_github.py`가 고정 GitHub API·신원별 요청·현재 권한/저장소·commit/tree·PR/Issue 작성 App/파일 목록을 M75에 연결한다. 검증된 최소 관측 저장으로 재시작하며, `scripts/run_registry_writer.py`는 기본 오프라인 설정 검사와 명시적 실행/토큰 폐기를 제공한다. 키 읽기·App 생성·민팅은 별도 준비다.
관련 회귀 249 passed, 전체 `make check` 3038 passed·2 skipped(로컬 macOS·py3.13, +50), 변이 5종 검출 후 복구. 초기 gate는 옛 문서 수집 수만 실패해 갱신했다. 실제 운영자 GET 13회로 보존 lab Git snapshot을 확인했으나 설치 토큰 쓰기·PR 422 원인은 미검증이다. 증거는 `docs/evidence/writer-github-verification-2026-09-13.json`. 새 lab/App·권한·보존·키 인계 범위는 `experiments/phase5-writer/retry-20260913/execution-review.md`; 원격 생성/쓰기는 미실행이다.

## M75 — 단계별 진행·중단과 독립 관측 연결 (로컬 완료, 2026-09-13)

- M73 수집·M74 단일 호출·기존 증거 판정기를 묶었다. 신원/seed/branch의 고정 매핑, policy/review/과거 관측 digest, 실제 HTTP 상태 대조와 현재 snapshot을 검사한다. 검증된 단계만 진행하고 종료 결과를 재사용해 다시 보내지 않는다.
- 실제 로컬 HTTP+합성 Git 관측으로 회귀 153 passed, 핵심 변이 5종 검출·복구, 전체 게이트 2988 passed·2 skipped(+37)를 통과했다. 프로세스 사망/재시작·동시 실행·폐기 후 401 대조도 포함한다.
- CONSISTENT는 관측의 일관성이며 live_verified=false다. GitHub 요청/관측 어댑터·새 키 인계·원격 발행은 남았다. 보존 lab은 GET으로 상태만 재확인했다. 상세는 PROGRESS_LOG M75·Phase 5 계획서 §12.

## M74 — 호출 전 intent·단일 실행권 (로컬 완료, 2026-09-13)

- private 디렉터리의 intent를 배타 생성·fsync한 뒤에만 요청을 전송한다. 기존 intent는 재시작/동시 실행에도 다시 사용하지 않는다. M73 수집기와 receipt를 연결하고 읽기 전용 상태를 제공한다.
- 실제 HTTP 경쟁→1회 전송, 전송 전/후 프로세스 사망, 6개 fsync 실패 지점, 불완전/변조 기록을 검증했다. 집중 회귀 71 passed, 변이 3종 검출/복구, 전체 게이트 2951 passed·2 skipped(+25). 상세는 PROGRESS_LOG M74·Phase 5 계획서 §12.
- OBSERVED는 HTTP 관측이며 PR 성공이 아니다. 전체 단계 제어·GitHub transport·token revoke/읽기 조정은 남았다. 새 디렉터리로 재시도하는 우회를 막을 상위 고정 매핑이 다음 작업이다.

## M73 — 제한된 실패 응답 영속 수집 (로컬 완료, 2026-09-13)

- 고정 message 분류·errors allowlist·형식 검증 request ID만 남기는 수집기를 구현했다. private 원자적 파일 저장, CLI stdin/출력 경계, stdlib HTTPResponse/HTTPError 연결을 실제 파일·프로세스·loopback 서버로 확인했다.
- 회귀 208 passed, 비밀 누출/파일 공개 생략/중복 헤더 변이 4종 검출·복구, 전체 게이트 2926 passed·2 skipped(+46). 상세는 PROGRESS_LOG M73와 Phase 5 계획서 §12.
- 수집 기록은 결과/권한/출처 증명이 아니고 M70 본문을 복원하지 않는다. 원격 API·키·보존 자원은 사용하지 않았다. 다음은 호출 전 intent 보존·불확실 결과 뒤 자동 재전송 방지다.

## M72 — 로컬 preview 저장·제출 준비 연결 (완료, 2026-09-13)

- planner 내부 artifact→DynamoDB 저장→기존 preview 응답을 연결했다. 저장 실패/작업 중 만료는 성공이 아니다. request_id만 받는 로컬 prepare API는 현재 권한·기준 SHA를 확인한 뒤 조건부 소비하고 내부 output/claim_id를 노출하지 않는다.
- 실제 DynamoDB Local·독립 CLI·Auth.js HTTP 검증과 연결 변이 3종 검출 후 복구, dashboard build와 전체 게이트 2880 passed·2 skipped(+35)를 통과했다. 상세는 PROGRESS_LOG M72·Phase 5 계획서 §12.
- CLAIMED/published=false는 준비권만 뜻한다. production 저장/PR 어댑터·제출 UI는 미구현이며 사용자 보존 lab/PEM/checkout은 변경하지 않았다. 다음은 원격 재측정 전 실패 응답 수집 계약이다.

## M71 — 서버 변경안 저장·조건부 소비 (로컬 완료, 2026-09-12)

- subject/request/output/envelope digest/5분 만료를 함께 저장하고 request_id 중복 생성을 거부한다. 현재 권한·base SHA를 확인한 뒤 상태/payload/subject/만료 조건으로 PREVIEW→CLAIMED를 한 번만 허용한다. production preview와 PR writer는 미연결이다.
- 실제 DynamoDB Local의 프로세스 간 보존·동기화된 8개 소비 경쟁·회수/만료/변조/장애 거부, CAS·만료·TTL 변이 3종 검출 후 바이트 복구를 확인했다. 신규 14개 포함 전체 게이트 2845 passed·2 skipped(2026-09-12 로컬 macOS·py3.13). 상세와 증거는 PROGRESS_LOG M71·Phase 5 계획서 §12.
- 사용자 보존 lab·키·checkout을 유지했다. 원격 쓰기·원본 commit/push·배포 없음. 다음은 preview 저장 연결과 제출 준비 경계이며 최종 성공/실패/불확실 상태 전이는 writer와 함께 구현한다.

## M70 — P5-E 네 호출 실측·후속 경계 검토 (실측 완료, 자동 PR 미완료, 2026-09-12)

- 정확한 최소 권한 설치 토큰으로 ref 403, 운영자 진단 branch에서 acme 200·globex 403, PR 422를 관측했다. main/형제 불변·대상 한 줄 diff·PR 0건을 운영자 읽기로 재확인했다. 판정은 diagnostic_only=true·sibling_boundary=supported·전체 inconclusive다.
- PR 오류 본문 미수집으로 원인을 복원할 수 없다. 발행 경로를 임의로 고치지 않고 계획서 §12에 공통 서버 저장 계약과 두 발행 후보의 변경 범위/검증 조건을 구체화했다. 키 인계 대기는 해소됐다.
- 토큰·설치·App은 폐기/삭제됐지만 사용자가 lab 삭제를 중단했다. lab 1367338348·로컬 키/checkout을 보존하며 추가 삭제 금지다. 원본 commit/push·배포 없음. 근거는 PROGRESS_LOG M70·`docs/evidence/phase5-writer-live-2026-09-12.json`.

## M69 — P5-E 생성 시도와 실패 후 정리 (시도·정리 완료, 실증 미완료, 2026-09-06)

- 사용자 재개 지시와 GitHub 본인 재인증 후 private lab ID 1358934947·App ID 4848286을 생성했다. Actions off, single_file write(acme.yaml)·PR write·metadata read만 설정했다. 키 ID 4366703은 생성됐지만 응답이 ERR_BLOCKED_BY_CLIENT로 이어졌으며 다운로드 기록 접근은 Browser Use URL 정책이 거부했다.
- 설치 토큰·App 설치·seed push·네 권한 호출·PR은 0건이다. 권한을 넓히거나 차단 경로를 우회하지 않았다. 따라서 single_file 가설의 성공/실패를 판정할 수 없다. 재시도는 사용자 키 다운로드 인계가 선행이다.
- App 삭제 큐 응답 후 소유자 목록·직접 설정 페이지 404로 부재를 확인했다. lab DELETE API는 403이어서 토큰 권한을 늘리지 않고 소유자 UI에서 동일 ID/full_name의 저장소를 삭제했다. 성공 화면·API 404·전체 소유자 목록 부재를 대조했다. 기존 App/운영 저장소는 보존했다. 증거 `docs/evidence/phase5-writer-attempt-2026-09-06.log`. 로컬 게이트 기준선은 M68의 2831 passed·2 skipped이며 실증 완료를 뜻하지 않는다.

## M68 — Lambda Docker 패키징 실패 전파 (로컬 완료, 2026-09-06)

- CDK Docker bundling 명령 끝의 || true가 requirements 설치·필수 agents/step_functions 복사 실패까지 종료 코드 0으로 덮었다. 선택적인 src/__init__.py 복사만 괄호로 묶어 오류 무시 범위를 좁혔다. 실제 pip·복사 명령 회귀 3 failed·2 passed → 5 passed.
- 공식 Lambda Python 3.11 ARM64 이미지에서 정상 의존성 설치·소스 패키징을 수행했다. 네트워크와 자격증명이 없는 별도 컨테이너에서 핸들러 13개의 import·callable 확인을 완료했다. Python 3.11.16/aarch64이며 전체 Python 테스트나 AWS 서비스 실행을 증명하지 않는다. host local bundler·전체 CDK CLI 배포도 별도다.
- 전체 `make check` **2831 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 59.28초, +5). 첫 게이트의 STATUS 숫자 형식 불일치 1건을 보완한 뒤 통과했다. 증거 `docs/evidence/incident-lambda-bundling-2026-09-06.log`. 기존 WIP 보존, 원본 commit/push·배포 없음. 새 P5-E lab/App 시험 범위는 재개 지시로 확인했으며 등록 화면의 사용자 본인 재인증을 기다린다.

## M67 — CDK 기본 앱의 누락된 실행 의존성 (로컬 완료, 2026-09-06)

- 실제 cdk.json app이 사용하는 ts-node가 manifest·lockfile에 없었다. 전역 도구·캐시·네트워크가 없는 Node 22에서 `npm run synth -- --no-lookups --quiet`가 ENOTCACHED로 실패했다. ts-node ^10.9.2 하나만 추가하자 앱이 Lambda bundling까지 진입했다. source-map-support import는 ts-node 내부 호환 경로로 처리됨을 확인했다.
- 임시 프로젝트·제한 PATH·빈 npm 캐시에서 실제 기본 앱을 실행하는 회귀를 추가했다. 변경 전 1 failed → 변경 후 1 passed. 새 Linux npm ci 후 실제 context와 bundling 비활성 조건에서 98개 리소스를 합성했고 npm audit 0건을 확인했다. 일반 synth의 Lambda 패키징과 원격 배포는 별도다.
- 첫 전체 게이트는 이 M67 요약이 없어 문서 연결 검사 2개가 실패했다(2824 passed, 2 skipped). 문서 반영 후 전체 `make check` **2826 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 56.49초, +1)로 통과했다. 증거 `docs/evidence/cdk-app-entrypoint-2026-09-06.log`. 원본 commit/push·원격 변경 없음, P5-E 재인증·실행 범위 확인 대기.

## M66 — 새 Linux 설치 검증과 보안 lockfile 갱신 (로컬 완료, 2026-09-06)

- M61에서 남은 새 환경 검증을 Linux amd64·Node 22.23.2·npm 10.9.8·Python 3.13.15로 수행했다. 초기 두 npm ci 성공, 네트워크 차단·CI selector 활성 상태에서 TS/CDK 관련 **69 passed, 0 skipped**. GitHub 원격 CI 실행은 아니다.
- npm audit의 high dashboard 1·stacks 3을 확인해 기존 범위 안에서 browserslist 4.28.9·aws-cdk-lib 2.268.0·CLI 2.1140.0으로 갱신했다. 신규 schema 54와 기존 CLI의 불일치를 재현 후 해소했다. 갱신 뒤 새 설치·관련 69개 검사·dashboard production build·CLI assembly synth 통과, 두 audit 모두 알려진 취약점 0건이다. package.json·전역 스크립트 권한은 바꾸지 않았다.
- 실제 cdk.json context로 전후 98개 리소스를 대조했다. runbook seed provider의 Node 22→24·코드 S3Key 두 필드만 다르며 IAM·앱 설정은 일치한다. 앱 bundling 비활성 상태이므로 Lambda 패키징·배포 또는 기본 ts-node synth 명령 검증으로 읽지 않는다.
- 원본 npm ci 후 전체 `make check` **2825 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 55.56초, 증감 0). 증거 `docs/evidence/ci-node22-lockfile-refresh-2026-09-06.log`. 기존 WIP 보존, 원본 commit/push·배포 없음. P5-E 재인증 완료·원격 실행 범위 확인은 남았다.

## M65 — P5-E 실행 검토와 엄격한 JSON 입력 (로컬 완료, 2026-09-06)

- 실제 소유 저장소 목록/App 설정 UI와 지원 API 버전을 대조하고 `experiments/phase5-writer/execution-review.md`에 정확한 생성·권한·시험·최종 정리 범위를 기록했다. App 등록 진입은 GitHub Confirm access 재인증에서 멈췄다. 원격 변경은 없다.
- 판정기의 boolean/float 정수 오인과 모순된 중복 JSON 키의 성공 판정을 재현해 수정했다. 신규 12 failed → 관련 **116 passed**, 변이 5종 검출. 전체 `make check` **2825 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, +12). 증거 `docs/evidence/phase5-writer-execution-review-2026-09-06.log`. 사용자 인증·원격 실행 범위 확인이 남았고 전체 목표는 진행 중이다.

## M64 — P5-E 오프라인 증거 판정기 (완료, 2026-09-06)

- `writer_evidence.py`와 `judge_registry_writer.py`: 최소 신원/권한·정규화한 실제 요청·운영자 ref/parent/tree/main 관측·형제 불변·PR 작성 App/URL/파일 목록을 대조한다. supported/diagnostic_only/unsupported/boundary_failure/inconclusive와 고정 reason을 JSON으로 출력한다. 신뢰할 수 없는 입력 출처나 실제 원격 호출을 인증하지 않으며 live_verified=false다.
- 입력 계약·합성 예제와 **104개 검사**를 추가했다. parent 검사 삭제를 가리던 후속 불일치를 제거한 회귀를 포함해 변이 8종을 검출했다. DOCUMENT stdout·실패 종료 코드·입력 오류 비노출도 실제 subprocess로 확인했다. 전체 `make check` **2813 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, +104). 증거 `docs/evidence/phase5-writer-judge-2026-09-06.log`. 원격 실증/정리 완료·commit/push는 수행하지 않았다.

## M63 — preview 스트림 경계와 reader 정리 (완료, 2026-09-06)

- 실제 Request/ReadableStream으로 4 KiB 누적 한도·정확 경계·헤더 위조·취소 실패/미완료·읽기 실패·reader 해제를 검사했다. 신규 13개 중 변경 전 12 failed·1 passed. 취소가 413을 덮거나 지연하던 경로, 정규화되지 않은 읽기 실패, 남는 reader 잠금을 수정했다.
- 수정 후 preview 계약 전체 **46 passed**, 변이 6종 검출. 전체 `make check` **2709 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, +13). 증거 `docs/evidence/preview-stream-boundaries-2026-09-06.log`. 원격 HTTP/CI·호스팅 업로드 시간 제한 검증은 별도이며 commit/push·원격 변경은 없다.

## M62 — overnight 결과 독립 검수와 후속 반영 (완료, 2026-09-06)

- M61 결과 커밋 `2e81799`를 독립 게이트로 검수: **2686 passed, 2 skipped**(로컬 macOS·py3.13). 2회차/구현 커밋 1개, DONE(drained), 잔여 auto·새 blocked 0개.
- 원본의 기존 WIP와 import 제거 두 건을 보존하고 결과 diff만 반영했다. 가드 검사는 호출 문자열 대신 실제 fixture의 로컬/두 CI selector × compiler/node 누락으로 보완했다(17 passed). bare skip+주석 변이가 기존 7개를 통과하던 결함을 재현했고 보완 후 3종 변이를 검출했다.
- 원본 최종 `make check` **2696 passed, 2 skipped**(로컬 macOS·py3.13, +10). 문서 숫자 불일치 1건을 정정한 뒤 통과했다. 실행·커밋 기록도 정정했다. 증거 `docs/evidence/overnight-review-followup-2026-09-06.log`. 원본 후속 변경은 미커밋이며 push·원격 CI·배포는 수행하지 않았다.

## M61 — CI의 TS/CDK 검증 누락 방지 (완료, 2026-09-06)

- `gate.yml`에 `actions/setup-node@v4`(Node 22, `dashboard/package-lock.json`·`src/stacks/package-lock.json` 캐시)와 두 `npm ci` 스텝을 추가해 tsc 툴체인을 CI에도 준비한다. 이유는 terraform init 스텝과 같다: 준비되지 않으면 두 TS 계약 테스트가 `pytest.skip`으로 숨어 gate가 아무것도 검사하지 않고도 초록이 된다(Risk 12②).
- `tests/_ts_toolchain.py`(신규, `require_ts_toolchain`)를 두 테스트 파일이 호출하게 바꿨다: 로컬(=`CI`·`GITHUB_ACTIONS` 미설정)은 계속 skip하고, 그 두 환경변수가 있으면 skip 대신 `pytest.fail`한다.
- `tests/test_ci_ts_dependency_guard.py`(신규 7)로 회귀 검증: 툴체인 존재 시 무해함, 로컬은 skip, `CI`/`GITHUB_ACTIONS`는 fail, 두 계약 파일의 호출 문자열 검사. 이 검사는 주석만 남겨도 초록인 한계가 있어 M62에서 실제 fixture 실행으로 대체했다.
- 로컬에 이미 설치돼 있던 `dashboard/node_modules`·`src/stacks/node_modules`로 TS 계약·CDK 합성 테스트가 변경 전후 모두 실제로 통과함을 확인했다(스킵 아님). 전체 `make check` **2686 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, +7). 증거 `docs/evidence/ci-ts-cdk-dependency-guard-2026-09-06.log`.
- `npm ci`·`npm install`·원격 CI 실행·push·배포·P5-E 자원 생성은 하지 않았다 — 커밋된 lockfile로 신선한 ubuntu 러너에서 `npm ci`가 실제로 성공하는지는 이 세션이 검증한 범위 밖이다.

## M60 — 하네스 critic 기본값을 엔진별로 분리 (완료, 2026-09-06)

- 저장소 Makefile과 재설치 snippet의 Claude critic 기본값을 `CLAUDE_CRITIC_MODEL`로 옮겼다. 공통 `OVERNIGHT_CRITIC_MODEL`은 비워 설치된 1.5.0이 실제 critic 엔진에 따라 선택하게 한다. 명시적인 공통 override는 유지한다. 플러그인 캐시/권한 경계는 수정하지 않았다.
- 실제 make 하위 프로세스 환경을 검사한다. 기본값·Codex·Kiro·Claude→Codex critic·환경/명령행 override를 두 파일에서 확인: 변경 전 **12 failed** → 변경 후 **12 passed**. 실제 설치된 선택 코드·Codex argv 생성도 전송을 막은 채 검사해 `--model gpt-6-astra`를 확인했다.
- 전체 `make check` **2679 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, +12). 증거 `docs/evidence/harness-critic-routing-2026-09-06.log`. 모델 호출·overnight 실행·commit·push·배포는 하지 않았다. 기존 혼합 WIP 보존. 다음 로컬 작업은 CI의 TS/CDK 검사 누락 방지이며 P5-E 원격 실증은 별도다.

## M59 — P5-E: single_file 발행 경계 실증안과 요청 본문 준비 (준비 완료, 2026-09-05)

- 계획서 §10과 `experiments/phase5-writer/`에 private lab/App 이름·single_file 한 경로/PR write·seed/예상 diff·신원별 API 본문·판정/정리 절차를 확정했다. 운영자 seed/관측과 installation-token 시험을 분리하고 ref 거부 후 별도 진단 branch는 전체 흐름 성공으로 세지 않는다.
- 실제 GitHub 소유자 등록 폼에서 acme 경로·PR write·Contents 미허용·owner-only·webhook off를 확인했다. Create는 누르지 않았다. 현재 gh의 installation 목록 403은 토큰 종류 제한이며 App 부재 증거로 쓰지 않았다. 문서상 ref와 file PUT은 Contents write를 요구하므로 single_file 성공을 미리 단정하지 않는다.
- 로컬 검증: 가상 acme/prod YAML을 실제 P5-A 플래너에 넣어 한 줄 diff·출력 SHA와 대조, 두 PUT 본문의 Git blob SHA/base64 일치, 요청/등록안의 범위 일치. `make check` **2667 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 테스트 증감 0). 증거 `docs/evidence/phase5-writer-preflight-2026-09-05.log`.
- **P5-E 전체 완료가 아니다.** 다음은 계획서 §10의 새 lab/App 생성·권한 부여·시험·정리 범위 검토 후 실제 실증이다. 원격 자원·App/key/token·설치·PR 생성·커밋·push·배포 없음. single_file 후보 경계도 파일 안의 dev/prod나 모든 PR metadata까지 격리하지는 않는다.

## M58 — P5-D: 세션 기반 preview UI와 쓰기 grant 보존 (완료, 2026-09-05)

- Provisioning에서 tenant/env/capability/version을 입력하면 canonical diff·base SHA·만료를 표시한다. 입력 변경 시 이전 preview를 지운다. 서버는 Auth.js username만 전달하며 정확 Origin·custom header·fetch metadata·JSON/크기 제한을 검증한다.
- 전용 OIDC Invoke 역할을 사용하고 SDK FunctionError·업무 실패·미연결을 구분한다. 로컬 Git HEAD/사용자 JSON 어댑터는 명시적 local mode에서만 실행되며 Vercel에서는 거부한다. 역할/읽기 grant 수정은 실제 DynamoDB partial Update로 별도 write grant를 보존하고 저장 장애를 demo 성공으로 감추지 않는다.
- 검증: 신규 **38 passed**, 전체 `make check` **2667 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13). Next.js production build·TypeScript, 실제 Auth.js operator/admin 허용·viewer 거부·같은 세션 grant 회수·읽기 grant만 있을 때 거부, 위조 422·CSRF 403·익명 401·장애/미연결 503. 실제 DynamoDB Local 사용자 route의 최신 grant 보존·감사 기록·테이블 장애, 브라우저 성공/이미 연결됨 오류 화면을 확인했다. 변이 6종 red → 바이트 복구 후 38 passed. 증거 `docs/evidence/phase5-preview-ui-2026-09-05.log`.
- 로컬 서버·임시 컨테이너 정리. 원격 Invoke·Vercel 배포·실사용자 grant 변경·PR 생성 없음. TS 계약 검사는 dashboard npm 의존성이 없으면 skip하며 원격 검증을 대신하지 않는다. 다음은 P5-E 발행 자격증명 실증안 구체화다.

## M57 — P5-C: Lambda·읽기·최소권한 CDK·배포 패키지 (완료, 2026-09-05)

- `registry_lambda.handler`가 검증한 요청을 P5-B에 전달한다. DynamoDB GetItem은 강한 일관성·fallback 없음. 공개 GitHub commit/tree/blob의 경로와 regular-file mode·SHA를 대조하고 redirect·과대 응답·truncation을 거부한다.
- `registry_planner_stack.ts`와 별도 `bin/registry_planner.ts`: 기존 운영 stack/provider 불변, production 전용 Invoke 역할, 정확 사용자 테이블 GetItem·전용 log stream 쓰기, Python 3.13 ARM64. 함수 URL·광역 managed policy·GitHub token·Secrets 권한 없음.
- Linux ARM64 wheel 고정본과 여섯 플래너 모듈만 패키징했다. 신규 테스트 **38 passed**, 전체 `make check` **2629 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 51.37초), TypeScript build·실제 CDK 합성·패키지 격리 import. 실제 DynamoDB Local SDK 허용 200·권한 부족/삭제 403·테이블 장애 503. 임시 자원 정리. 변이 7종 red → 바이트 복구. 증거 `docs/evidence/phase5-lambda-runtime-2026-09-05.log`.
- AWS Lambda 원격 실행·GitHub live 호출·private token·세션/UI·PR은 검증하지 않았다. CDK npm 의존성이 없는 환경은 해당 테스트를 skip한다. 다음은 P5-D UI·서버 route·로컬 세션 매트릭스이며 grant 편집 시 보존도 확인한다.

## M56 — P5-B: 현재 사용자 레코드의 명시적 tenant 쓰기 grant (완료, 2026-09-05)

- `registry_authorization.plan_authorized_snapshot()`: 신뢰하는 세션 주체를 소문자 저장 키로 정규화하고 `CurrentUserReader`에서 매번 조회한다. 레코드 username 일치 + operator/admin + 정확 tenant 쓰기 grant를 통과해야 P5-A를 호출한다. 읽기용 `tenants`와 세션 role을 인가 근거로 받지 않는다.
- 세션 주체 없음 401, 사용자 부재·권한 부족 403, 조회 장애 503. 예외에 자격증명·호스트 경로를 노출하지 않는다. 조회 전에 요청을 검증·복사해 승인 대상과 플래너 입력을 고정한다. P5-A의 요청 검증 함수를 공유한다.
- 검증: 관련 테스트 **187 passed**(+57). `make check` **2591 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 48.40초), 인가 변이 **7종 red** → 바이트 복구. 실제 파일을 사용하는 P5-A 연결과 admin/operator 허용, 거부 시 registry 읽기 0, 권한 회수·역할 변경·삭제·이전 성공 후 장애를 검사했다. 증거 `docs/evidence/phase5-write-grants-2026-09-05.log`.
- 신뢰하는 어댑터의 현재 레코드 반환을 전제로 한다. 실제 AWS/세션 연결·grant 저장 설정·Lambda 배포·UI·PR 발행은 하지 않았다. 다음은 P5-C의 Lambda adapter·CDK 정의와 로컬 검증이다. 제출 시 권한을 다시 확인해야 한다.

## M55 — P5-A: revision에 묶인 읽기 스냅샷과 변경안 (완료, 2026-09-05)

- `src/agents/platform/registry_planner.py`: 사용자 요청은 tenant/env/capability/version만 받는다. 서버 주체·요청 ID·시각을 분리하고, 읽기 어댑터에서 고정 SHA의 catalog·대상 tenant·Helm values를 받는다. 경로·blob·크기·UTF-8·엄격 YAML 검증 뒤 기존 플래너를 재사용한다.
- **M53 정정**: 두 파일 실증은 호스트 values를 읽고 있었다. 호스트 루트를 빈 디렉터리로 바꾸면 실패했고, `values_repo_root`를 주입해 해결했다. 값 파일까지 같은 revision과 digest로 묶으며 기존 CLI 기본 동작·설치 가능성 검사는 유지한다.
- 출력은 canonical 경로·diff·만료 시각·digest다. 주체·요청·세 blob·출력 SHA-256·계약 버전·응답을 바인딩한다. 입력 파일·형제 tenant/env·기존 주석의 변경을 거부한다. digest는 인증 서명이 아니며 인가·서버 측 계획 저장·재제출 처리는 P5-B 이후 범위다.
- 검증: 실제 레포 파일 세 개, 네트워크/프로세스 실행 금지, 호스트 values 경로 차단, 관련 테스트 **130 passed**. `make check` **2534 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 45.96초). 변이 8종 red → 바이트 복구. 첫 변이에서 의미 비교 검사를 우회해도 다른 검사들이 잡아낼 수 있음을 확인하고, 잘못된 환경에 한 줄만 추가하는 독립 회귀 사례를 더했다. 증거 `docs/evidence/phase5-snapshot-planner-2026-09-05.log`.
- 다음은 P5-B: 현재 사용자 레코드의 명시적 write grant. 원격 조회·설정·배포·commit·push·PR 발행 없음.

## M54 — GCP 비용 창 재측정: 달력은 늘었지만 같은 부하는 아니었다 (측정 완료, 2026-09-05)

- 기존 export **3,053행**. 이 프로젝트 누적 사용액 **₩14.801301**, PROMOTION **−₩12.356601**, 기타 크레딧 **−₩2.444753**, 청구는 미세 반올림 차이를 제외하면 **≈₩0**. 결제계정 전체 사용액은 **₩251.18**이며 이 레포 몫과 구분했다.
- 프로젝트의 일별 관측은 08-24~09-05이나 오래된 행의 금액은 거의 0이고 09-05는 04:00 UTC까지만 있다. 09-02·03 Cloud Storage는 각각 ₩0.062387, 09-04 Artifact Registry는 ₩5.376524, 09-05에는 Cloud Run ₩2.521778과 DISCOUNT가 나타난다. **긴 달력 범위를 안정된 부하로 읽지 않고 월 추정을 보류**했다.
- BigQuery SELECT **3건**(전체 report·프로젝트/일·프로젝트/일/서비스), AWS CE **0건**. 추가 일별 질의 둘은 각각 `--maximum_bytes_billed=10485760`으로 제한했다. table numBytes는 실제 과금 스캔 바이트로 주장하지 않는다.
- 증거 `docs/evidence/gcp-spend-window-2026-09-05.log`. 원격 자원·설정 변경 없음. 새 상시 GKE의 비용 추정이나 크레딧 만료 시점은 이 측정으로 답하지 않는다.

## M53 — Phase 5 실행 위치 설계: 플래너에는 git 작업 트리가 필요 없었다 (설계·로컬 실증 완료, 2026-09-05)

- **D52**: 독립 Python Lambda + Vercel 서버의 OIDC/IAM Invoke. `docs/plans/2026-09-05-phase5-planner-runtime.md`에 후보 비교·인가·snapshot/digest·동시 변경·재시도·PR 발행 경계·구현 순서 P5-A~F를 기록했다.
- 초기 실증은 **catalog + 대상 tenant YAML 두 파일**을 임시 경로에 두고 실행했다. **M55 정정: 호스트의 Helm values를 추가로 읽었으므로 두 파일만으로 격리됐다는 결론은 틀렸다.** PATH에 실행 파일이 없고 subprocess/network를 거부하는 audit hook 아래에서도 계획이 생성됐다. 입력과 실제 workspace registry는 바뀌지 않았다. 기존 레지스트리 쓰기 테스트 **25 passed**.
- FastAPI는 이미 존재하고 Vercel Python도 지원되므로 옛 배제 근거를 철회했다. 새 blocker는 **현재 사용자 레코드 기반 write grant**, demo fallback 없는 인가, **PR 발행 자격증명 경계**다. GitHub API에 single_file permission은 있지만 branch 생성에는 문서상 Contents write가 필요하므로 전체 흐름의 범위를 아직 증명하지 못했다.
- 증거 `docs/evidence/phase5-planner-runtime-2026-09-05.log`. 이번 결과는 **설계·로컬 실증**이며 Lambda 배포·UI·실제 PR 생성은 아니다. 문서 반영 후 `make check` **2429 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13). 다음 구현은 P5-A다.

## M52 — 문서 경로·결정 번호·문자 예산 가드와 STATUS 줄 여유 (완료, 2026-09-05)

- 경로: 진입점 여섯(BRIEF·STATUS·NEXT_PLAN·PROGRESS_LOG·COMPLETED_SUMMARY·DECISIONS)의 구체적 Markdown 참조가 Git 추적 파일과 실제 파일에 모두 대응하는지 검사한다. archive는 **참조 대상**에는 포함하고 **검색 원문**에서는 제외한다. 접두 경로·확장자·glob/생략형 경계를 고정했다.
- 결정: BRIEF·STATUS·NEXT_PLAN의 D번호를 `DECISIONS`의 `## D번호` 헤딩과 대조한다. 한국어 조사·개별 인용·범위의 중간 번호까지 검사한다. 본문에 이름만 적는 것은 정의가 아니다.
- 문자 예산: archive를 포함한 Markdown에서 config의 문자 상한을 중복 표기하지 않도록 검사한다. **9개 문서의 21개 숫자 복제**를 설정 참조로 바꿨다. 실측 크기·비율·줄 예산은 유지했다. 처음 넓힌 선언 패턴이 `Status: 09-02`와 남은 글자 수를 오탐해, 선언 문맥을 좁히고 회귀 사례를 넣었다.
- 줄 여유: `STATUS` 119→99줄(체크포인트 전), 공백 정규화 대조로 기존 본문 동일 확인. 현재 줄 수는 체크포인트 증분을 포함하며 아래 완료 기준 이내다.
- 검증: 새 가드 **16 passed**. 실제 문서 변이 **19종 전부 red**, 매번 바이트 사본 복구 확인 후 **16 passed**. 전체 `make check` **2429 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 42.53초). 런타임 코드·클라우드 자원 변경 없음.

- 후속 수정: 날짜 가드가 미래 예정일을 지난 검증일로 읽어 진입점 세 개를 오탐했다. 명시적인 `예정: YYYY-MM-DD`만 제외하고 같은 줄의 완료일은 계속 검사한다. 회귀 검사 +3, 문서 변이 2종 red → 복구 후 날짜 가드 12 passed.
- 증거: `docs/evidence/doc-guards-2026-09-05.log`. `STATUS` 최종 **102줄**, 기존 본문은 신규 체크포인트 블록·갱신일을 제외하면 공백 정규화 동일. 열린 `[auto]` **0건**.

### 완료한 계획의 경계 (당시 문구 보존)

- [x] [auto] 진입점 문서가 지목하는 `docs/**/*.md` 경로의 실존 가드. Done: BRIEF·STATUS·NEXT_PLAN·PROGRESS_LOG·COMPLETED_SUMMARY·DECISIONS의 `docs/….md` 인용이 전부 실존(**오늘 dangling 0 — 초록에서 시작한다**). ⚠️**경계를 넣을 것**: `bin/docs/…`에서 `docs/…`만 잘라내면 없는 경로 3건이 **오탐으로 생긴다**(09-03 실측). ⚠️**2026-07 archive의 8건은 제외** — 그때 있던 파일을 적은 이력이지 지금의 주장이 아니다(M48이 주석을 뺀 것과 같은 이유).
- [x] [auto] 진입점 문서가 인용하는 `D<번호>`의 실존 가드. Done: BRIEF·STATUS·NEXT_PLAN이 인용하는 D번호 **14개**가 `DECISIONS.md`에 실재(**오늘 전부 실재 — 초록에서 시작**). `test_milestone_pointer_claims`(M번호)의 **형제이고, 형제 집합은 세는 순간 전부 셀 것**.
- [x] [auto] 문자 예산 숫자의 **유일 표기** 가드. Done: `harness-config.json` 밖에서 문자 예산(`char_budgets`)을 적는 문서가 0. 현재 archive **4곳**이 복제 중이고 09-02 로그가 *"선행 사례, 이번 범위 밖"*으로 이미 지목했다. ⚠️**줄 예산은 의도적으로 3곳**(config·`DOCS_POLICY`·문서 헤더)이고 기존 가드가 일치를 묻는다 — **문자 예산만 유일 표기다**(M19).
- [x] [auto] `docs/STATUS.md`의 **줄** 예산 여유 회복. Done: ≤108줄(현재 115/120). ⚠️**문자는 58%라 여유롭다 — 이건 줄 문제다** ⇒ 인접 줄을 합쳐 문단을 넓히는 방향(09-02 NEXT_PLAN 압축이 *"두 예산은 반대 방향으로 당긴다"*를 남겼다). ⚠️**⚠️/⛔ 문장은 한 글자도 지우지 말 것.**

## M51 — 재개 조건이 2년 전에 멈춘 이슈를 보고 있었다 (완료, 2026-09-02)

**목적**: 열린 항목 중 **날짜가 박힌 재확인 지시**를 단 유일한 것(Risk 6 / Cosign 어드미션,
*"08-30 확인: 아직 — 이 날짜부터 볼 것"*)을 판정하는 것. **나온 것**: 결론은 살아 있고 **근거가
죽어 있었다.**

**결론 유지**: 어드미션은 아직 못 켠다. 08-08 kind 실측(*"서명된 것도 `no signatures found`"*)이
그대로다.

**⚠️근거 교체**: 재개 조건이던 `policy-controller#1406`은 **2024-09-30 이후 갱신이 없고**, 그
이슈가 요구하던 구현은 **`#1725`로 2025-04-23에 머지**됐다. **"이슈가 열려 있다"는 "지원이
없다"의 증거가 아니었다** — Risk 4의 *"'없다'는 어떻게 봤는지까지"*가 **업스트림 쪽에서 재발한
모양**이고, 그 조건은 **영원히 발화하지 않을 수 있는 신호**였다.

**⚠️그렇다고 '낡은 버전을 시험했다'도 아니다**: 08-08에 쓴 chart **0.10.6**의 appVersion은
**0.13.1**(2025-09-17)로 `#1725` 머지 **이후**다. **지원이 들어간 버전에서 이미 실패했다.**
이 한 단계를 안 물었으면 정반대의 틀린 이야기를 적었을 것이다.

**진짜 신호**: `#1899`(*"cosign v3.0.2 서명을 policy-controller 0.13.1이 검증 못 한다"*, **open**)가
**우리 조합 그대로**이고 고침은 `#1968`(**미머지**)이다. ⇒ **새 조건 = `#1968` 머지, 또는
`#2007`(2026-08-24 머지)을 담은 릴리스** — 최신 v0.15.1은 2026-03-26이고 그 뒤 **51 커밋 미출시**.

**cosign 쪽 기록은 정확했고 더 넓게 참이다**: `--new-bundle-format`은 v3.1.2의 **여섯 하위 명령
어디에도 없다**(v2 옵트인이었고 v3에선 기본이라 사라졌다) ⇒ **간극은 서명하는 쪽이 아니라
검증하는 쪽**이다.

**안 한 것도 측정이다**: **클러스터 변경 0**(재시도는 kind 변경이라 승인 후) · 클라우드 호출 **0건**
(GitHub API와 로컬 `cosign --help`뿐) · `make check` **2407 passed + 2 skipped**(변동 0).
증거: `docs/evidence/the-resume-condition-was-watching-a-dead-issue.log`.

## M50 — `MEASURABLE`이 금액을 대신 묻는다: 그리고 첫 가드가 그 변이를 통과시켰다 (완료, 2026-09-02)

**목적**: `GCP_BILLING_EXPORT_SETUP.md` §4가 *"데이터가 생기면 그때 붙인다"*로 미뤄 둔 분기를
붙이는 것. 미룬 이유는 **태워 볼 데이터가 없어 검증할 수 없었다**였고, **M49**가 730행을 만들며
그 조건이 사라졌다. **대상**: `scripts/probe_cloud_spend.py` — 명령을 인쇄만 하던 자리가 질의를
돌리고, 프로젝트별로 **총사용액 · PROMOTION · 기타크레딧 · 청구** 넷을 갈라 인쇄한다.

**ⓐ 크레딧을 한 컬럼으로 합치면 세 번째 거짓 0이 된다.** 프로모션은 **마르는 잔액**이고
`DISCOUNT`/`FREE_TIER`는 **요율의 성질**인데, 합치면 화면이 똑같아지고 독자는 *"GCP는 싸다"*로
읽는다 — 잔액이 다할 때까지만 참인 문장이다. ⇒ 질의가 `c.type = 'PROMOTION'`과
`IFNULL(c.type,'') != 'PROMOTION'`을 **따로** 센다.

**ⓑ ⚠️첫 가드가 바로 그 변이를 통과시켰다.** `"= 'PROMOTION'" in sql`은 **`!= 'PROMOTION'`에도
참**이다 — promo 컬럼을 전 크레딧으로 넓혀도 **남은 반쪽이 사라진 반쪽 대신 답했다**. 부등호를
가르는 lookbehind(`(?<![!<>])`)로 고쳤다. **M48의 접두 매칭 함정과 같은 계열**이고, 이번에도
**가드가 독자가 읽는 그 물건이 아니라 제 창문에 물고 있었다**(Risk 12④).

**ⓒ ⚠️프로브가 제가 경고하는 오독을 할 뻔했다.** 창을 전 행으로 재면 `2026-08-01 ~ 2026-09-02`
— **한 달**로 인쇄된다. 그 08-01은 `project`가 없는 **Invoice 행 하나**이고 실사용은 08-30부터다
(**M49 ⓑ**가 적은 바로 그 행). ⇒ 창은 **계정 수준 행을 뺀** 사용 행에서만 잰다:
`08-30 ~ 09-02 (729행, 계정 수준 1행 제외)`. **경고를 문서에 적는 것과 도구가 그 함정을 피하는
것은 다른 일이다.**

**ⓓ 안 하는 쪽도 정했다**: 질의 실패는 **0이 아니라** *"직접 물어볼 것"* + 붙여넣을 명령이다 ·
`--project_id`를 넘긴다(없으면 **다른 프로젝트에 과금**된다, 09-01 실측) · **스캔 바이트를
인쇄한다** — 이것이 이 프로브에서 **유일하게 과금되는 호출**이고, CE가 이 계정 청구서의 84%가 된
방식이 *"반복해서 물은 것"*이었다. 한글 폭 정렬(`east_asian_width`)도 여기 들어간다: 숫자가
엉뚱한 머리글 아래로 가는 것은 표에서 **오독이 생기는 자리**다.

**검증**: `make check` **2407 passed + 2 skipped**(2397 → **+10**), 실패 0. **변이 12종 전부 red**
(PROMOTION 뭉개기 3종 · 창을 전 행으로 · 경고 제거 2종 · 실패를 0으로 · `--project_id` 제거 ·
콜론 형태 · 스캔 비용 제거 · 인쇄만 하기 · 합계에서 크레딧 누락). 변이·실행·복구는 **한
스크립트**이고 **복구는 바이트 사본에서**(Risk 12⑦). 라이브 확인은 **`report_gcp()` 직접 호출
1회**(BQ 질의 1건 ~40KB) — **AWS Cost Explorer 0건**.
증거: `docs/evidence/the-guard-let-the-mutation-through-because-of-one-character.log`.

## M49 — 적재는 도착했고, ₩0의 정체는 요율이 아니라 프로모션 크레딧이었다 (완료, 2026-09-02)

**목적**: M46이 만든 넷째 상태(`EXPORTED_EMPTY`)의 **판정**. 09-01엔 테이블만 있고 `numRows`
0이었고, 판정 시점은 09-02 01:11Z 이후였다. **나온 것**: 적재는 왔고, 그 뒤에 함정이 셋 더 있었다.

**적재는 도착했다.** `numRows` **730**(422,688바이트 · `lastModifiedTime` 09-02 06:29:40Z), 프로브의
GCP 분기도 **`MEASURABLE`**. 2026-07 GKE 방치 사건 이래 열려 있던 *"GCP 실지출은 어떤 방법으로도
못 읽는다"*가 **닫혔다** — 07월 자체는 여전히 복구 불가다(소급 적용 없음, 아래).

**ⓐ ⚠️₩0은 요율이 아니다.** 총사용액 **₩67.87** → 청구 **≈₩0**. 그 차이의 **99.4%(₩67.4773)**가
`FreeTrialUpgrade:CreditId-FreeTrial:…` **`type=PROMOTION`**이고, 티어성 `DISCOUNT`는 **₩0.39**
(Cloud Run CPU/Memory Allocation Time)뿐이다. **AMP와 같은 계열의 반대 방향**이다 — 거기선 절벽이
요율→**한도**로 옮겨 앉았고, 여기선 요율도 한도도 아니라 **크레딧 잔액**이다. ⛔*"GCP는 어차피
공짜"*로 요약 금지. **소진 시점은 내보내기가 말해 주지 않는다** — 안 잰 칸이다.

**ⓑ ⚠️월별 집계는 "8월이 백필됐다"로 읽혔고, 그건 틀렸다.** `invoice.month=202608`이 **310행**에
`first_usage 2026-08-01 07:00`이라 한 달치로 보였다. **일별로 가르니** 08-01은 **1행**이고 그것은
`project=null`인 **Invoice 행**이다. 실제 사용 데이터는 **08-30부터**(41 → 124 → 548 → 16행) — 토글
(09-01 01:53Z) 이전 **이틀**뿐이다. ⇒ `GCP_BILLING_EXPORT_SETUP.md` **§0은 성립한다**. **집계 축을
하나만 보면 없는 백필이 보인다**(*"MTD로 '지금'을 답하지 말 것 — 일별로 갈라야 멈춘 것과 도는 것이
갈린다"*가 잡았다).

**ⓒ ⚠️월 런레이트는 아직 못 잰다.** 창이 **3일**이고 마지막 날(09-02)은 **안 찼으며**, 총액의
**81%**가 **하루치 4행**이다(`claude-study-501117`의 Cloud Storage **₩54.90**, 09-01에만). 여기서
30을 곱하면 **가정이 총액을 지배**한다 — 4a 추정표가 100배 틀렸던 그 모양이다. **며칠 뒤 다시 묻는
것이 무료인 다음 측정**이다.

**ⓓ ⚠️총액의 90%는 다른 프로젝트 것이다.** 결제계정 `010556-A2B7AE-292490`에 프로젝트 **5개**,
비용 행이 있는 건 **3개**: `claude-study-501117` **₩59.27** · `project-ec7809f7…`(platform-agent)
**₩6.55** · `warranty-hack` **₩2.05**, `gen-lang-client-*` 둘은 **0행**. ⇒ 브리프가 경고한 *"0행은
'₩0'이 아니다 — 프로젝트가 5개다"*가 답을 얻었다: **5개 중 3개가 돈다.** ACR을 *"다른 프로젝트
것"*으로 갈랐던 Azure와 같은 모양이고, **결제계정 총액을 이 레포의 비용으로 읽으면 10배 틀린다.**

**비용(안 한 것도 측정이다)**: `bq show`는 메타데이터라 **$0**(스캔 0바이트), 질의 5건 합계 스캔
**~250KB** = 무료 티어 1TB/월의 **0.000025%**. **AWS Cost Explorer는 한 번도 호출하지 않았다** —
`make spend-check` 전체는 CE **$0.01**을 물고 그게 이 계정 청구서의 84%가 된 방식이다.
게이트 변동 **0**(측정과 문서만 바뀌었다).
증거: `docs/evidence/the-gcp-zero-is-a-promotion-credit-not-a-rate.log`.

## M48 — 인쇄된 경로도 주장이다: 39개를 전수로 물었고 0개가 dangling이었다 (완료, 2026-09-02)

M46이 남긴 교훈("**인쇄된 지시도 주장이다**")을 가드로 만든 것. 09-01엔 GCP 프로브가
인쇄하던 `bq` 명령에 결함이 셋이었고 **한 번도 실행된 적이 없었다**. 지시 전체의 정합성은
기계화할 수 없지만 그 안의 **경로**는 가장 값싸게 물어지는 주장이고, 가장 먼저 썩는다.

**대상**: `tests/test_script_printed_paths_resolve.py` — `scripts/*.py`의 문자열 리터럴 속
레포-상대 경로 **전수**. 앵커(top-level 디렉터리)는 **git에서 유도**해 새 디렉터리가 생기면
그날 스윕된다. **쓰기 전에 쟀다**: 23 스크립트 · **39개**(distinct, stdout에 닿는 것 **4개**) ·
**dangling 0** ⇒ 초록에서 시작하는 가드지 청소 과제가 아니다.

**⚠️ 존재는 git에게 물었지 이 노트북에게 묻지 않았다.** `pathlib.exists()`였다면 여기선
초록, CI에선 red다 — `src/stacks/node_modules`는 디스크에 있고 `.gitignore:16`에 있다.
불변식은 *"레포가 담고 있다"*이지 *"내 파일시스템에 있다"*가 아니다(Risk 12②).

**⚠️ 첫 판은 false red를 냈고, 면제 목록으로 덮지 않았다.** `probe_scope_reachability.py`의
`.endswith("platform/scope.py")`는 경로가 아니라 **grep 출력에 맞대는 조각**이다(`platform/`이
top-level이라 경로처럼 보였다). **쓰임으로** 갈랐다 — `startswith`/`endswith`의 인자와 `in`의
좌변은 독자에게 보여지지 않는다. *"중의적인 top-level 이름은 앵커에서 뺀다"*는 규칙도
재 봤는데 `src`(↔`dashboard/src`)까지 죽여서 안 썼다. **면제는 목록이 아니라 경계다.**

**⚠️ 접두 매칭 함정은 양쪽에 다 있었다.** 추출 쪽: 확장자를 `json|jsonl` 순서로 나열하면
`.jsonl`이 잘린다(실제 짝이 있다 — `model-sweep-live-points.jsonl` ↔ 존재하지 않는 `.json`)
⇒ 꼬리는 **탐욕적 문자 클래스 하나**. 검사 쪽: `startswith` 멤버십이면 그 없는 `.json`이
**있는 것으로 통과**한다 ⇒ 정확 일치. 양방향 다 테스트로 못 박았다.

**⚠️ 가드 자신이 한 번 틀렸다 — 변이 하나가 살아남았다.** 접두 함정 테스트가
`_repo_paths()`(집합)에 물었는데 dangling 검사는 **별도의 식**을 써서, 멤버십을 `startswith`로
느슨하게 해도 전부 초록이었다. **가드가 독자가 쓰는 그 물건이 아니라 제 창문에 물고
있었다**(Risk 12④). 판정을 `_in_repo()` 한 곳으로 뽑아 둘이 같은 것을 묻게 하니 red.

**경계(기존 가드와 안 겹친다)**: `test_evidence_pointers_resolve`는 `docs/evidence/*.log`
**한 종류**를 `tests`·`docs`·`src`에서 훑고 **`scripts/`는 안 읽는다**. 이 파일이 나머지 절반이다.

**안 한 것**: `#` 주석은 안 훑는다 — 주석에만 사는 경로를 재니 `src/stacks/node_modules`
하나였고 **의도적으로 tracked가 아니다**(훑으면 가드가 vendored 의존성을 커밋하라 요구한다).
docstring은 범위 안이다(리터럴이고 독자가 읽는다). 점으로 시작하는 top-level은 앵커 밖이고
**scripts의 참조 횟수를 0으로 쟀다**. 라이브 호출 0건.

**검증**: `make check` **2397 passed + 2 skipped**(2392 → **+5**). **변이 8종 전부 red**
(없는 이름 · `.jsonl`→`.json` · gitignore된 경로 · 추출기를 확장자 나열로 · 스윕 비우기 ·
`print()` 미인식 · 멤버십 `startswith` · 조각 예외 제거). 변이·실행·복구는 한 스크립트이고
**복구는 바이트 사본에서** 했다(Risk 12⑦ — `git checkout --`가 아니다).
증거 `docs/evidence/the-printed-path-was-a-claim-nobody-checked.log`.

## M47 — 서버는 대기 시간을 말하고 있었고 전송 계층이 그걸 버렸다 (완료, 2026-09-02)

M46ⓒ가 남긴 잔여. 09-01엔 **사람이 헤더를 읽고 40초를 손으로 기다렸다**; 이건 프로브가
스스로 하게 한 것이다. **힌트를 인쇄하는 것과 기다리는 것은 다르다** — 리포트는 다음 날
아침에 읽히고, 그때 그 429는 이미 지나갔다.

**전송 계층을 바꿔야 했다 — 그게 이 항목이 별도였던 이유다.** `az rest`는 응답 헤더를
버린다. ⇒ 토큰은 `az account get-access-token`으로 받고 질의는 **`curl -D -`**로 한다
(`az`는 여전히 유일한 로그인 경로다 — 두 번째 인증 수단을 만든 게 아니다).
⚠️**토큰은 argv에 두지 않는다**: `--config -`(stdin)로 넘긴다 — `ps`는 이 기계의 아무
프로세스나 읽는다. **URL은 argv에 남긴다**(비밀이 아니고, 가드가 무는 게 그것이다).

**핵심 규칙: 헤더가 없으면 재시도하지 않는다.** 없는 간격을 지어내는 것이 애초에 429를
영구 실패로 읽게 만든 방식이다(20초<40초). 파싱 안 되는 값(HTTP는 `Retry-After`에 날짜도
허용한다)도 **0초가 아니라 재시도 없음**이다 — 0으로 읽으면 스로틀 중인 서버에 타이트
루프를 돈다. `clienttype-retry-after`가 `retry-after`보다 우선(09-01에 고갈된 건 그 버킷
하나였다). 대기는 **최대 3회**, 매 대기는 **60초로 클램프**, 그리고 **기다린다고 인쇄한다**
(40초를 조용히 있으면 멈춘 것처럼 보이고, 죽인 사람은 스로틀을 영구 실패로 배운다 —
이 항목이 고치는 바로 그 오독).

**가드도 같이 옮겼다**: `test_only_the_cost_query_endpoint_is_posted_to`가 사라진
`az rest --url`을 보고 있었다 — **아무것도 매치하지 않는 가드는 영원히 통과한다**. curl
계층에 대고 묻고 **POST가 하나도 없으면 red**(vacuous가 여기서의 실패 모양이다).

**검증**: `make check` **2392 passed + 2 skipped**(2381 → **+11**). **변이 7종 전부 red**
(URL 이동 · `-D -` 제거 · 없는 간격을 20초로 추측 · 토큰을 argv로 · 재시도 상한 완화 ·
클램프 제거 · 파싱 실패를 0초로). ⚠️**라이브 재측정은 안 했다** — 429를 다시 부르는 건
그 자체로 스로틀을 쓰는 것이고, 이 변경의 내용은 **간격을 어디서 얻는가**라 오프라인에서
전부 물어진다.

## M46 — 테이블은 생겼는데 아무것도 안 들어 있었다: 묻는 도구 셋이 틀렸다 (완료, 2026-09-01)

**목적**: 전날 남긴 다음 행동("`make spend-check`의 GCP 줄")을 확인하는 것. **나온 것**: 묻는
도구 자신의 결함 셋. **셋 다 읽어선 안 보이고 태워야 보인다.**

**ⓐ 빈 테이블이 측정으로 읽혔다.** 13시간 뒤 내보내기 테이블이 생겼고(01:53Z, 토글 42분 뒤)
프로브는 *"잴 수 있다"*로 바뀌었다. 그런데 **`numRows` 0**이다 — `lastModifiedTime`은 조회
4분 전이라 **작성기는 도는데 실린 게 없다**. `MEASURABLE`이 **테이블 존재**만 보고 **행 수**를
안 봤다. `probe_cloud_spend.py`가 존재하는 이유가 *"빈 절은 0으로 읽힌다"*인데 **빈 테이블이
측정으로 읽히는 형태로 한 층 위에서 재발**했다. ⇒ 상태를 **셋→넷**(`EXPORTED_EMPTY`).
MEASURABLE에 접으면 **없는 답을 약속**하고, NOT_EXPORTED에 접으면 **이미 옳게 켜진 콘솔
토글로 되돌려 보낸다** — 다른 문제, 다른 다음 행동. 행 수는 **`bq show` 메타데이터**로 센다
(스캔 0바이트 = **$0**; `bq query`로 셌으면 **프로브가 돌 때마다 과금**됐을 것이고 그게 바로
CE가 이 계정 청구서의 84%가 된 방식이다).

**ⓑ 인쇄되던 `bq` 명령은 돌지 않았다 — 한 달 내내.** MEASURABLE 분기는 **라이브 내보내기가
있어야 도달**해서 09-01 전엔 **한 번도 실행된 적이 없었다**. 처음 태우니 즉시 에러. 한 줄에
셋: **ⓐ콜론**(`project:dataset.table` — 표준 SQL은 점) · **ⓑ`--project_id` 없음**(실제로
**같은 결제 계정의 다른 프로젝트** `claude-study-501117`에서 돌았다) · **ⓒ`SUM(cost)`만**
= 크레딧 미반영. ⚠️ⓒ는 **`GCP_BILLING_EXPORT_SETUP.md` §4가 명시한 함정**인데 **그 문서를
가리키는 도구가 그 함정을 인쇄하고 있었다** — **같은 명령이 두 벌이었고 한 벌만 맞았다.**
⇒ `_export_query()` 한 곳에서만 만든다. **고친 명령은 쓰기 전에 라이브에 태웠다**(exit 0).
⚠️**인쇄된 지시도 주장이다.**

**ⓒ Azure 429의 기록된 결론이 뒤집혔다.** 13시간 뒤에도 429(5회째)라 헤더를 봤다. 고갈된 건
**`clienttype-requests: DefaultQuota:0` 하나**고(entity 2·tenant 18·QPU 58 여유) 서버가
**`clienttype-retry-after`로 대기 시간을 말하고 있었다**(5→**40**). 40을 기다리니 **200**:
ACR **₩76.67**·Cosmos DB ₩0. ⚠️**재시도는 두 번 다 답이었다** — 09-01의 *"이번엔 아니었다"*는
**간격이 서버 요구값 아래**였던 것(20초<40초)이고, **고정 간격 재시도는 영구 실패와 구분되지
않는다.** ⚠️`_why()`가 docstring에 적은 값어치(*"1분 뒤 재시도인지 깨진 자격증명인지"*)를
**헤더를 버리는 전송 계층(`az rest`)이 못 주고 있었다** — 이유의 **이름**은 줬고 **행동에
필요한 값**은 못 줬다. 힌트는 **429일 때만** 붙는다(모든 실패에 붙는 조언은 읽히지 않는다).

**미리 막은 새 함정 둘**: **`bq show` 실패는 0행이 아니다**(`AccessDenied`·리전 `[]`·429와 같은
부류 → MEASURABLE로 두고 질의가 독자 앞에서 시끄럽게 실패하게 둔다) · **빈 테이블이 스윕을
멈추지 않는다**(멈추면 스윕이 지우려던 **단일 위치 가정**이 되살아난다).

**검증**: `make check` **2381 passed + 2 skipped**(2368 → **+13**). **변이 8종 전부 red.**
**안 한 것도 측정이다** — AWS는 재측정하지 않았다(13시간 전 값이 유효하고 **다시 묻는 것 자체가
청구서**다). 권위 `docs/evidence/the-table-existed-and-held-nothing.log`.

## M45 — 시그니처는 필수라 했고 본문은 선택이라 했다: 그 기본값이 정책이었다 (완료, 2026-09-01)

mypy 253을 **분류하다가** 나왔다. **결정(게이트 편입)은 여전히 안 내렸다.**

**`arg-type` 15 중 10이 한 함수**: `onprem_webhook_api`가 `summary.get(...)`를
`record_incident(severity: str, …)`의 **필수 `str`** 자리로 넘긴다. 그런데 본문은 다섯 다
**`x or "기본값"`** — **본문은 처음부터 `None`을 받도록 쓰여 있었다. 코드가 옳고 선언이
거짓이었다.** `None`은 도달 가능하다: 파이프라인 결과는 키를 항상 갖지만 **값이 `.get()`
결과**이고, 파이프라인이 스스로 `incident = detector_out.get("normalized_incident") or {}`라
적어 뒀다 — **부재를 예상했다는 저자들 자신의 진술**이다. ⚠️`else: # MANUAL` 가지는
**`mode`가 `None`일 때도 걸린다**. 고침: 다섯을 `str | None`로(**문을 닫는 쪽이 아니다** —
거부하면 저하된 인시던트가 *"인시던트 없음"*이 된다). `arg-type` **15→5**, mypy **253→241**.

**⚠️ 진짜 발견은 그다음이다.** 주석을 고치는 건 **도는 것을 하나도 안 바꾼다.** 도는 것은
**기본값 부여**이고, `record_incident`를 쓰는 테스트 7개 중 **다섯 필드에 `None`을 넘기는
파일이 0개**였다 ⇒ **저하된 인시던트가 어떻게 분류되는지가 무단언**이었다. 둘은 그냥 기본값이
아니라 **축의 안전한 끝**이다 — **MANUAL**은 실행하지 **않는** 모드(AUTO로 기본값이 되면
**아무도 고르지 않은 조치가 클러스터에 나간다**; M39가 *"안 했는데 했다고 보고"*라면 이건
*"아무도 안 골랐는데 실행"*이다) · **P3**은 척도의 **바닥**(P1이면 불완전한 analyzer 출력마다
사람을 호출하고, 그렇게 훈련된 사람은 호출을 무시한다). 가드 **+10**은 문자열이 아니라
**어느 끝인지**를 묻고 **저장된 행까지** 읽는다(반환값만 보면 파일에 `null`이 적혀도 통과한다).

**⚠️ 못 잰 축 하나**: 변이 M5(저장 건너뛰기)는 `_append(record)` 같은 **단일 호출 지점이 없어**
붙지 않았다 — *"안 쟀다"*로 남긴다. 나머지 넷은 red.

**곁가지 — mypy 오탐을 격리했다**: `return-value` 4건이 전부 `x or os.getenv(k, DEF)` 모양인데
`os.getenv(k, DEF)` 단독·`x or "literal"`·`x or y`는 다 `str`이고 **그 조합만 `str | None`**이다
(`or`의 오른쪽에서 오버로드가 첫 번째로 재해석 — mypy 1.14.1). **런타임엔 None이 될 수 없다.**

**결정에 줄 누적 숫자**: 실제 주장 53 중 **21건을 열어** **고칠 값이 있던 건 2건**(M44+M45),
나머지 19는 노이즈이거나 *"코드는 옳고 타입이 못 따라간다"*. **게이트 2358 → 2368.**
증거 `docs/evidence/the-signature-said-required-the-body-said-optional.log`.

## M44 — 계약이 모두가 부르는 메서드를 빠뜨리고 있었다: 찾은 건 mypy였다 (완료, 2026-09-01)

*"정적검사를 게이트에 넣을지"*의 **선행 실측을 다시 돌리다가** 나왔다. **결정은 내리지 않았다.**

**기록의 "전수 분류 결함 0"이 재현된다**(ruff 20건): 가장 위험해 보이는 여섯을 실제로 열었고
전부 미관/죽은 변수였다 — `dep_id`(넘길 파라미터가 **아예 없다**) · `azure_runner.url`(각 분기가
자기 URL을 만든다) · F402(문자열 루프 변수와 **이름만** 겹침) · `original_guard`(새 인스턴스라
복원할 게 없다) · `result`(단언은 부작용에 건다) · E701 ×5(열 맞춤).

**없던 반쪽 — mypy 253의 성격**: `type-arg` 71·`import-untyped` 40·`no-any-return` 36·
`no-untyped-def` 32·`no-untyped-call` 21 = **200/253(79%)이 주석 부채**, 나머지 **53이 실제
타입 주장**. **"253"은 절망적으로 읽히고 "200은 부채, 53이 주장"은 결정 가능하게 읽힌다.**

**⚠️ 그 53 중 하나가 진짜였다**: `ExecutionAdapter`가 `parameters_for_action`을 선언하지
않는데 **네 어댑터가 다 구현**하고 `aws/executor.py`가 **베이스 타입을 통해 부르며**
**테스트는 그 이름을 한 번도 언급하지 않는다(0건)**. 오늘 런타임 결함은 없다. 나쁜 건 호출부가
`except Exception: pass`라는 것 — 베이스 만족에 `resolve_action` **하나면 충분**했으므로
다섯째 provider가 그 조건만 채우면 `AttributeError`가 **삼켜지고 AWS 모양 파라미터**를 받는다.
**에러 나지 않는 방식으로 실패한다**(Risk 8).

**⚠️ `from_alarm_context`는 고치지 않았다**: 정의도 호출도 AWS 하나이고 호출이 **리터럴 고정**이라
베이스에 올리면 나머지 셋에 **거짓**이 된다 — 기준은 *읽는 쪽의 provider 간 비대칭*이다(M19 ⓑ).

**고침**: 베이스에 선언 + 신규 가드가 **AST로 유도**한다(provider가 **변수면 베이스 필수,
리터럴이면 면제** — 정규식으론 못 가른다) + 형제 넷의 구현 검사(**선언은 절반**이다).

**⚠️ 내가 두 번 더 틀렸다**: ⓐ면제 테스트를 **`assert … or True`**로 끝냈다(assertion이 아니다 —
세션 내내 *실패할 수 없는 규칙*을 찾아 온 손이 썼다) ⇒ **면제가 실제로 면제하는지** 묻게 고쳤다 ·
ⓑM3(호출부 리터럴화)을 또 한 파일에서 읽을 뻔했는데 **전체 스위트에 물으니 이번엔 진짜였다**
(2356 passed — 아무것도 안 잡는다): **provider를 인자로 받은 함수가 그걸 무시하고 AWS를
하드코딩해도 초록**이다(M23과 같은 모양). **내 면제가 만든 탈출구라 내가 닫았다.**

변이 5종 전부 red. **게이트 2350 → 2358.** 증거
`docs/evidence/the-contract-omitted-the-method-everyone-calls.log`.

## M43 — 게이트가 안 돈 PR을 "CI 초록"으로 읽었다: 없는 것과 통과한 것이 같은 색이다 (완료, 2026-09-01)

⛔**먼저 오해를 막을 것: `main`은 무방비였던 적이 없다.** 브랜치 보호가 `check` 컨텍스트를
**요구**하고(`required_status_checks.contexts == ["check"]`) 게이트는 **main 대상 PR에선 언제나
돌았다**. **D43은 계속 성립했다.**

**문제는 스택 PR이었다.** `gate.yml`이 `pull_request: branches: [main]`이라 **base가 다른
브랜치인 PR엔 이 job이 아예 안 돈다**. PR **#58**(base = M39 브랜치)에서 `gh pr checks`가
*Amazon Q: pass / Vercel: pass / Vercel Preview Comments: pass*를 답했고 **`check` 행이 아예
없었다** — 그걸 "CI 초록"으로 읽었다. ⚠️**없는 것과 통과한 것은 그 목록에서 같아 보이고,
차이는 읽는 사람이 채운다.**

**이건 Risk 12②의 한 층 위다**: 거기 적힌 *"skip은 실패가 아니라서 검사 안 하는 게이트와
통과한 게이트가 같은 색"*은 **건너뛴 테스트**였고, 여기선 **안 돈 워크플로**다.

**고침**: `branches` 필터 제거 ⇒ **모든 PR이 게이트를 받는다**(CI 몇 분 더, **초록이 어디서나
같은 뜻**). 가드 +4: 트리거 존재(공허성) · **base 필터 부재**(진짜 고침) · 이유 주석이
`#58`·`Risk 12`를 계속 가리키는지. ⚠️**YAML 1.1은 맨 `on:`을 불리언 `True`로 읽는다** —
`wf["on"]`만 본 테스트는 KeyError로 *"트리거가 없다"*를 답했을 것이라 **둘 다** 조회한다
(자기가 막는 실패와 같은 모양). 변이 4종 전부 red. **게이트 2346 → 2350.**

⚠️**경계**: **게이트가 병합 조건이라는 것은 가드가 주장하지 않는다** — 그건 GitHub 브랜치
보호에 있지 레포에 없고, `test_signature_gate_claims`가 **배선을 앞질러 간 주장**의 표준
사례다. 레포 안에 있는 절반만 묻는다.

**재개 방지**: `2026-08-08-phase4-scope-and-cost.md`의 4a 절이 아직 **착수 대상**으로 읽혀
*"끝났고 접혔다"* 박스를 얹었다(§10·§11 · M38·M40 · D50 Folded).

## M42 — 셋째 형제는 mypy였다: 형제를 세는 가드 자신이 둘만 세고 있었다 (완료, 2026-09-01)

**선행 실측 둘은 기록대로였다**: `make lint` **20건**(F841 8·E731 5·E701 5·F402 1·E712 1 ·
src 7·tests 13) · mypy **253 errors in 88 files (166 checked)**. ⚠️**그런데 그 253은 그냥은 안
나온다** — `mypy src/`는 `cdk.out`의 중복 모듈에서 **수집 단계에 죽는다**(*"Found 1 error in 1
file (errors prevented further checking)"*). **선언된 설정이 그대로는 실행조차 안 됐다**:
`pyproject`가 그 블록을 *"the settings are the target"*이라 적어 뒀는데 **못 돌리는 target은
돌려서 실패하는 target보다 약하다.**

**⚠️ Risk 12⑥이, 그 규칙을 집행하려고 만든 가드 안에서 재발했다.** 08-30에 pytest↔ruff
비대칭을 고치며 만든 가드의 파일명이 **`..._from_both_tools.py`(both=둘)**인데, 같은
`pyproject.toml`의 **`[tool.mypy]`가 셋째 형제**로 두 경로 중 아무것도 안 적고 있었다.
⚠️**빠진 쪽이 하필 가장 나쁜 형제였다** — ruff의 실패는 시끄럽고 오락가락(20↔6,527)인데
mypy의 실패는 **총체적**(우리 코드를 한 줄도 안 본다)이고 문장이 *"1 error"*라 **작아 보인다**.

**고침**: `[tool.mypy] exclude` 추가 ⇒ `mypy src/`가 그냥 돈다. 가드는 `..._from_every_tool.py`로
개명하고 **셋 다 순회**. ⚠️**게이트 편입은 바뀐 게 없다** — 결정은 그대로 레포의 것이다.

**⚠️ 가드의 가드 — 변이가 시켜서 만들었다**: 첫 판의 `TOOLS`는 **손으로 적은 dict**라
**M5(TOOLS에서 mypy 제거)가 초록으로 살아남았다**. **이 파일의 주제가 이 파일에 그대로
일어났다 — 세는 일 자체를 아무도 안 세고 있었다**(내 docstring은 *"derived, not listed"*라고
**코드가 안 하는 걸 주장**했다). ⇒ `[tool.*]`에서 제외 키를 **유도**해 양방향 대조.

**⚠️ 재는 동안 두 번 더 틀렸다**: ⓐ`mypy`가 **252**를 답한 건 **증분 캐시**였다(청소 후 253) —
*"기록이 틀렸다"*고 쓸 뻔했다. **캐시된 답은 측정이 아니다**(Risk 12⑦ `.pyc` 계열) ·
ⓑ**변이를 적용하지 않고 변이를 쟀다**(정규식 과도 이스케이프 → 한 건도 안 지워졌는데 시간을
쟀다) ⇒ **변이 적용부터 확인하고 결과를 읽을 것.**

**게이트 비용**: `mypy src/` **49.2s**(게이트 36초의 배)를 `mypy src/stacks/` **0.13s**로 바꿨다 —
결함이 사는 자리이고 답이 둘뿐이라 공허하지 않다. 변이 8종 중 7 red, M6은 **설명된 초록**.
**게이트 2342 → 2346.** 증거 `docs/evidence/the-third-sibling-was-mypy.log`.

## M41 — `onprem` extra의 `mlx-lm`: 선언은 있고 그걸 쓰는 곳이 없었다 (완료, 2026-09-01)

**기록된 근거는 적을 당시 참이었다.** `gate.yml`이 *"mlx-lm은 Apple Silicon 전용이라 리눅스
러너에서 resolve가 안 된다"*고 적어 인라인 우회를 했는데, PyPI 재측정 결과 **하한
`0.19.0`은 `mlx>=0.17.0`에 플랫폼 마커가 없어 진짜 실패**한다. ⚠️**그런데 stale해진 게 아니라
더 나빠졌다**: `>=0.19`는 리졸버에게 **0.31.3**을 고르게 하고 거기엔 `platform_system ==
"Darwin"` 마커 + `py3-none-any` 휠이 있어 **설치는 되고 엔진만 조용히 빠진다**.
**우회를 "이제 필요 없다"고 풀었으면 CI가 엔진 없는 mlx-lm을 초록으로 깔았을 것이다.**

**그래서 우회가 아니라 선언을 물었다**: `src/`가 mlx를 임포트하는 곳 **0건**(에이전트는 MLX
**서버**와 HTTP로 말한다 ⇒ 엔진은 임포트가 아니라 **프로세스**) · `.venv-mlx`엔 mlx-lm은
있고 `pydantic-ai-slim`은 없다 ⇒ **`.[onprem]`의 산물이 아니다** · 진짜 메커니즘은
`make mlx-setup`. ⚠️**"안 쓰이니 지운다"가 아니다**: Makefile이 *"활성화된 `.venv-mlx`가
pytest를 가린다"*고 적고 인터프리터를 탐침으로 고른다 — 분리는 **설계**이고, extra가 mlx를
프로젝트 env로 들이면 그걸 뒤집는다. **미사용이 아니라 틀린 메커니즘이었다.**

**고침**: `onprem`에서 `mlx-lm` 제거 · `gate.yml`이 `.[onprem]`을 깐다 ⇒ **인라인 패키지 0개**
(`serving` extra가 없앤 것과 **같은 모양의 우회**가 하나 남아 있었다). 가드 +3. **게이트 2339 → 2342.**

**⚠️ 내가 만든 가드 하나가 주석으로 통과했다**: *"`mlx-setup`이 여전히 메커니즘인가"*를
`"mlx-lm" in Makefile`로 물었는데 **`MLX_BIN` 위 주석**에 그 문자열이 있어 레시피를 깨도
초록이었다 — **주석이 주어인 규칙은 규칙이 아니다.** ⚠️**그걸 "레시피 가드가 없다"로 읽은
것도 틀렸다(Risk 12⑦ 재발)**: 변이를 **이 파일에만** 물어서였고, 전체 스위트엔 red다 —
`test_local_stack_prerequisites.py`가 **레시피를 직접 읽는 옳은 자리의 옳은 질문**이었다.
⇒ 약한 사본은 **지우고** 어디가 그 자리인지 주석으로 남겼다.

변이 M1~M4 red(M4는 **전체 스위트에서**), M5는 **초록이고 설명된다**(현재 위반 0건이라 꺼도
관측 불변 — 그 규칙의 하중을 재는 변이는 M1이고 red). ⚠️**리눅스 resolve는 로컬에서 증명
못 한다** — PR의 CI 체크가 그 답이다.
증거 `docs/evidence/the-onprem-extra-declared-a-mechanism-nobody-used.log`.

## M40 — 4a를 접었다: 지운 이유는 $0.00이 아니라 장기 키였고, 가드는 지우면 안 됐다 (완료, 2026-09-01)

**삭제(D50 집행, 사용자 결정)**: AMP 워크스페이스 `ws-929b8da9…`(ap-northeast-2) · IAM 사용자
`amp-remote-write-4a` · 키 `AKIA…62VN`. 삭제 전 정책은 **기록과 정확히 일치**했다(관리형 0,
인라인 1건 = `aps:RemoteWrite` 하나 × 워크스페이스 하나). ⚠️**좁은 키도 장기 키이고, 실제 청구
$0.00은 지울 이유를 줄이지 않았다** — D50이 미리 그렇게 적어 뒀다.

**확인은 "어떻게 봤는지"까지**: 8리전 스윕 0 · `describe-workspace`를 **id로 직접** 물어
`ResourceNotFoundException` · `get-user` `NoSuchEntity`. ⚠️**`get-access-key-last-used`는
`AccessDenied`고 그건 부재의 증거가 아니다**(권한이 없어 나온 답 — 키가 살아 있어도 같다);
증거는 **소유 사용자의 부재**다.

**⚠️ 가드를 지울 뻔했다.** `test_amp_cost_handles.py`의 9건은 목적지가 사라지면 **전부 공허하게
참**이 된다. 지우는 쪽도 답이 아니었다 — **D48(허용목록 없이 remote_write 금지)은 4a를 접어도
안 죽고**(필터 없음 = 프리티어 **128배**, ≈$180/월 = 4b 값 ⇒ 4a를 고른 이유가 지워진다) 그걸
적어 둔 유일한 물건이다. 계약을 **함수(`remote_write_violations`)로 빼** 두 호출자에 물렸다:
**살아 있는 파일**(목적지가 없어야 한다) + **합성 표 9종**.

**⚠️ 첫 판이 틀렸다 — 규칙이 다른 규칙의 그림자로 세어졌다**: 합성 표를 `violations != []`로만
묻자 **와일드카드 검사를 통째로 지워도 초록**이었다(`kube_.*`가 `allowlist-drift`에도 걸려서).
**M17의 "결함을 그 그림자로 세지 말 것"의 재발.** 위반 코드 7종 + 케이스가 **어느 규칙이 물어야
하는지** 지정 + 함수 본문에서 코드를 긁어 표와 대조(새 규칙이 케이스 없이 늘면 red).
재변이 **7종 전부 red**. **게이트 2332 → 2339**(+7).

**⚠️ 남긴 것의 이유가 바뀌었다**: KSM interval **60s**는 비용 손잡이가 아니라 이제 데모 알람 룰의
`[5m]`=5샘플(120초면 2샘플 → `> 2`가 원리상 도달 불가). **워크스페이스 id는 더는 안 박는다** —
없는 것을 박으면 **영원히 틀릴 수만 있는 규칙**이다.

증거 `docs/evidence/folding-4a-the-price-was-a-long-lived-key.log` · 계획서 **§11** · **D50 Folded**.

## M39 — Azure는 하지 않은 조치를 "해결됨"으로 보고했다: 배선하니 비대칭 7건이 닫히고 게이트가 내려갔다 (완료, 2026-08-30)

**목적**: 08-16에 발견돼 13일간 세 진입점이 `▶ NEXT SESSION` **첫 행동**으로 가리켜 온 승인 사안.
권위 = `docs/evidence/azure-executor-reports-resolved-without-executing.log` **§종결**.

**결함**: `azure/executor.py::_execute_single_action`이 capability를 풀고 로그만 찍은 뒤
`{"success": True}`를 돌려줬다. 그 성공이 `executed`에 쌓여 `resolution_verdict`가 `resolved=True`를
내고 **Slack에 "해결됨"이 올라가고 그렇게 기록됐다.** 311줄 러너가 **import 한 줄 거리**에 있었고
GCP는 Phase 3에 배선됐는데 Azure만 안 됐다 — 그리고 **그 사실이 어디에도 적혀 있지 않았다.**

**산출**: ⓐ**배선** — GCP와 같은 모양으로 `run_azure_action`을 `resolve_incident_scope`와 함께 부른다
(발명 없음). 미구현 11종은 러너의 `ValueError`가 `except`를 타고 **`success: False`**가 된다.
ⓑ**Phase 3② Azure** — AKS 롤백에 `guard_rollback`. GCP에서 성립한 근거가 그대로 성립한다:
**patch 직전 GET이 이미 있어 추가 API 호출 0**. ⓒ**기록 둘이 같은 커밋에서 움직였다** — 디스패치
표의 azure 면제와 `JUSTIFIED_GAPS`. 후자는 *"fix the dispatch first, then this entry must go"*라고
**자기 만료 조건을 적어 뒀고 가드가 그걸 집행했다.**

**⚠️여기서 배운 것 셋** — ①**AST 가드는 "성공이라 보고한 것이 실제로 일어났는가"를 못 묻는다.**
08-16의 가드는 *호출이 소스에 있나*만 봤다. 신규 `test_executor_reports_only_what_the_runner_did.py`가
**gcp·azure 둘 다에** 러너 호출·실패 전파·`resolved` 판정을 묻는다(형제 하나만 순회 금지 —
`WIRED`가 디스패치 표와 어긋나면 red). 변이 M1(호출 삭제)이 **넷을 죽였다** = 같은 결함을 다른
각도로 잡는다는 증거. ②**면제가 비면 "면제엔 이유가 있어야 한다"는 규칙이 하중을 잃는다**(Risk 12③)
→ 두 규칙을 **합성 표**에 대고 다시 물었다. **실패할 수 없는 규칙은 규칙이 아니다.**
③**공허성 검사를 숫자로 두면, 진짜 고침이 그 숫자를 깬다.** `test_contract_symbol_parity`의
`len(ASYMMETRIES) >= 20`이 26→19로 red가 났고 **초록으로 가는 길은 숫자를 내려 적는 것뿐**이었다 —
그건 그 파일이 스스로 이름 붙인 *allowlist nobody prunes*다. **구조적 양성 대조로 교체**
(`paginated_scan=={aws}` · `run_gcp_action=={aws,gcp}`) — 결함이 닫혀도 안 낡고, reader 집합을
틀리게 계산하는 walk까지 잡는다.

**⚠️비대칭 7건이 한 번에 닫혔다**: `guard_rollback`·`IncidentScope`·`resolve_incident_scope`·
`guard_scoped_action`·`IsolationTier`·`Registry`·`load_registry`. M29가 *"one cause, six symptoms"*
라고 적어 둔 인과가 **반대 방향으로 확인됐다** — 원인을 고치니 증상이 동시에 사라졌다.

**검증**: 변이 **6종 red, 생존 0**(기준선 먼저, `__pycache__` 삭제 후 복구 확인 = 기준선과 동일).
gate **2332 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13). ⚠️**2337에서 −5로 내려갔다**:
정당화 7건 해소 **−14**(parity가 JUSTIFIED·ASYMMETRIES 양쪽에 파라미터라이즈) · 새 행동 가드 **+7** ·
공허성 둘 **+2**. **결함이 닫히면 그 결함을 설명하던 줄도 사라진다 ⇒ 게이트 숫자는 단조증가
지표가 아니고, 줄어든 숫자는 분해해 적어야 한다.**

**⚠️과대 해석 금지**: 열린 것은 **경로**지 안전이 아니다. 오늘 blast radius가 0인 이유는 러너가
만지는 **AKS·FunctionApp이 구독에 0개**여서고 이는 **오늘의 사실이지 불변식이 아니다**. 하나라도
생기면 같은 코드가 실 변경을 친다 — 그때의 방어는 `guard_scoped_action`(스코프 없으면 거부)과
`guard_rollback`(reconciler 충돌 거부)이고, **자격증명을 테넌트에 묶는 것은 여전히 Phase 4**
(Risk 10 — AKS admin kubeconfig).

## M38 — Phase 4 / 4a 종료: 청구액은 $0.00이었고, 프리티어를 배제한 근거의 전건이 거짓이었다 (완료, 2026-08-30)

**목적**: 13일간 세 진입점이 가리켜 온 마지막 미측정 항목 — *"08-19 이후 AMP 실제 청구액"*.
권위 = `docs/plans/2026-08-15-4a-remote-write-allowlist.md` **§9·§10** ·
`docs/evidence/amp-actual-bill-is-zero-and-the-free-tier-reason-was-inverted.log`.

**산출**: DoD 넷(③308 시계열 · ④`from_managed` · ①②관리형 렌더=M37) + **청구액 대조**로 4a가
닫혔다. 실제 청구 **$0.00**(계량 798,331 샘플 · 0.0005 GB-Mo · 쿼리 920). ⚠️`Credit` 행이 없다 —
**크레딧 상쇄가 아니라 Usage 행 자체가 $0**이고, AMP 그룹은 13일 전부 CE에 **존재한다**
(계량되고 0인 것과 계량조차 안 된 것은 다른 사실이다).

**사유 — §3이 세운 조건문의 전건이 거짓**: AMP 프리티어는 12개월 한정이 아니라
**`freeTierType: "Always Free"` 40M/월**이다. ⚠️**틀린 기록이 아니다** — §3은 추론임을 명시했고
*"확정은 AMP를 켠 뒤 첫 청구서가 답한다"*고 **무엇이 확정할지 지목했다.** 다만 답은 이미 그 계정
데이터 안에 있었다(당시 12건이 **전부 "Always Free"**). 같은 데이터가 두 결론을 지탱했고 **비싼
쪽을 골랐다** — 보수적이라 안전했다.

**검증**: 교차 확인 **2.4%**(실가동 41.3 수집-시간 × 19,800/h = 817,740 vs 계량 798,331) ·
허용목록 **유출 0**(전체 창에서 메트릭 이름 정확히 4개, 시계열 308이 11일 간격 두 시점 동일).
가드 +6(`test_amp_bill_claims`, 변이 7종 red). gate **2299**.

⚠️**믿으면 안 되는 요약 둘**: ⓐ**"AMP는 어차피 공짜"** — 절벽이 요율에서 **40M 한도**로 옮겨
앉았을 뿐이고 필터 없음은 **128배 초과**다(허용목록 하중 그대로) · ⓑ**"$1.42"** — 720시간
**연속 가동 가정**인데 실측 duty cycle은 **13%**(13일 중 4일·41.3h, 로컬 kind라 08-27T19:55Z
이후 죽어 있다) → 프리티어가 없었어도 **$0.07**이다.

**접을 때**: IAM 사용자 `amp-remote-write-4a` · 액세스 키 · 워크스페이스 셋 다 삭제(D50) —
⚠️**$0이라고 이 이유가 줄지 않는다**(대가는 돈이 아니라 **장기 액세스 키 하나**였다).

## M37 — 티어 2가 조건을 안 보고 추천에서 액션을 만들었다 + 4a DoD ①② (완료, 2026-08-17)

열려 있던 판단 셋을 추천안대로 실행했다. ⚠️**둘째의 전제가 측정에서 무너져 답이 바뀌었다.**

**#1 판별 수단** — 점수 로직을 **계약 모듈에 한 벌**(`schema.score_runbook`·`match_text`) 두고
세 provider가 읽는다. GCP/Azure 티어 2가 첫 매치 대신 점수로 고른다 → **세 provider가 같은
인시던트에 같은 답**(health-check = `health-check-failure`/rto 240). 키워드 어휘는 이미
클라우드-중립이라 **없던 건 데이터가 아니라 읽는 쪽이었다.**

**#2 — 추천 목록이 아니라 티어 2가 문제였다.** 티어 2는 액션을 **조건 평가 없이** 추천에서
만든다. 카탈로그에서 **에스컬레이션에만 존재**하는 capability는 넷이고 그중 **둘이 GCP/Azure에서
first-response로 실행**되고 있었다 — 같은 모듈의 **티어 1은 조건을 평가한다**(M21 모양: 형제가
provider가 아니라 **진입점**). ⇒ 티어 2가 **승자의 steps에서** 액션을 만들게 고쳤다.
⚠️**티어 2 액션을 단언하는 테스트가 0개**였다 — 조건 무시도, 이 고침도 red를 안 냈다.

**#3 4a DoD ①②** — 결정: **관리형은 매니페스트를 내지 않고 read model이 그 부재를 설명한다**
(`applicable=False`·sync `n/a`). **새 매니페스트 종류는 발명하지 않았다.** `ManagedBackendNotRenderable`는
삭제(결정이 났으므로 죽은 코드). 변이 16종 전부 red. gate **2279**.

## M36 — 가드가 생산에서 도달 불가한 입력으로만 통과하고 있었다 (완료, 2026-08-17)

마지막 미측정 항목 ⓒ(*"티어 2는 첫 매치가 이긴다 — 테스트가 고정했으니 결정이다"*).
**앞쪽은 정확하고 뒤쪽이 틀렸다.**

`test_capability_catalog_scan`의 케이스는 **후보를 유일하게 가리는 capability 집합을 손으로
골랐다**(`["rollback_release"]`·`["drain_node"]`). ⚠️**어떤 signal 어댑터도 그런 집합을 안 낸다** —
`kubernetes-workload`는 `restart_workload`+`scale_out`을 내고 그건 후보 셋과 동시에 겹친다.
⇒ **첫-매치 구현과 점수제 구현의 답이 같은 경우만 태웠다**(Risk 12⑤). 게다가
`["rollback_release"]`는 그 세 provider가 **추천하지 않는 값**이다(M35에서 측정) — **생산에서
도달 불가한 입력으로 통과**하고 있었다.

실제 집합으로 물으니 GCP/Azure는 OOM·health-check·latency **셋 다** rto **180**을 보고했다
(인시던트와 무관하게 늘 같은 답). 가드 +12. gate **2269**.

## M35 — ⓐ의 답은 "현행 유지"였고, 그걸 시험하다 만든 스윕이 결함 넷을 냈다 (완료, 2026-08-17)

**ⓐ의 주장은 성립한다**: 어긋남은 한 방향뿐. ⚠️**내 픽스처가 한 번 틀렸다** — resolve는
**(capability, resource_type) 쌍**으로 키를 거는데 `kafka-topic`으로 물어 *"네 provider 전부
미구현"*으로 읽었다. 올바른 `streaming-consumer`로는 전부 resolve된다. **주장 전에 잡았다.**

**두 선택지는 대칭이 아니다**(08-12엔 "둘 다 동작 변경"이었다): 티어 2는 액션을 steps가 아니라
`recommended_capabilities`에서 만들고 `capabilities`는 **매치 게이트일 뿐**이다 — 더해도 관측
변화 0, **빼면 네 provider가 다 resolve하는 에스컬레이션 스텝을 잃는다.** ⇒ **현행 유지로 닫는다.**

**찾던 건 하나였는데 스윕이 결함 넷을 냈다**: `rebalance_consumer`가 **Azure만** 없는데
**같은 커밋에서 태어나 처음부터 빠져 있었다**(stale이 아니라 오기). 가드 +6. gate **2257**.

## M34 — 계약이 세 형식인데 walk는 둘만 물었다 (완료, 2026-08-17)

열린 항목 **"런북 walk ②(`severity` 축)"**를 시험했다. **닫혔다 — 두 겹으로.** ①`severity` 축
자체는 **M33이 08-16에 닫았다**(가드가 셋 다 있고 양방향) · ②e2e walk의 `severity="P2"` 고정은
**결함이 아니라 범위**다: 카탈로그 9런북 16스텝의 조건 키는 **`previous_step_failed` 하나뿐**(6스텝).

**닫으러 갔다가 옆에서 나왔다.** `evaluate_condition`이 문서화한 형식은 **셋**
(`previous_step_failed`·`severity_in`·`provider`)인데 walk 자리에서 물어진 건 **둘**이었다 —
`provider`는 **순수함수 단위 테스트**(직접 만든 컨텍스트)에만 있었다(Risk 12④ⓒ).
⚠️**`test_step_condition_is_read.py`의 도크스트링이 세 형식을 정확히 열거하면서 둘만 물었다** —
M20과 같은 모양(**산문이 참이어도 물은 것이 범위다**).

변이 8종 전부 red(**기준선 먼저**): 대조군으로 `"severity"`를 지우면 red · **`"provider"`를
지우면 세 walk 전부 GREEN 생존**(=가드 없음) → 추가 후 여섯 전부 red. 가드 +6. gate **2224**.

## M33 — 08-12 기록의 전제는 틀렸는데 그것이 가리킨 가드 공백은 진짜였다 (완료, 2026-08-16)

**기록**: *"런북 walk ② — 조건 축은 `previous_step_failed`만 넓혔고 **`severity`는 `"P2"`
고정**이라 `severity_in` 스텝이 생기면 재발한다 — 카탈로그에 없어 가드를 안 만들었다."*

**전제는 틀렸다.** `src` 어디에도 조건 컨텍스트에 P2 고정이 없다. `git log -L
175,175:…/aws/executor.py`가 `"severity": decision.analyzer.severity.value`를 **gate
1191**로 지목한다 — 08-12 기록(gate 1825)보다 한참 전이다. **stale이 아니라 쓰일 때부터
틀린 기록**(M19 ⓑ와 같은 모양). 그리고 `severity_in` 가드도 *이미 둘* 있었다.

**그런데 그 둘이 두 구현을 구별하지 못했다.** AWS 쪽 executor walk 테스트는 조건
`["P1"]`에 실제 severity **P3**로 스킵을 단언한다 — **"P2" 고정이어도 똑같이 스킵된다.**
유일하게 태운 경우가 **옳은 구현과 틀린 구현이 일치하는 경우**였다. Risk 12⑤ 그대로:
*기본값과 같은 값을 고른 픽스처는 가드가 아니다.*

**고친 것**: 양성 방향을 넣었다 — 같은 조건에 **P1 인시던트**면 스텝이 **실행돼야** 한다.
**검증**: 기록이 주장한 상태(`"severity": "P2"`)를 실제로 만들어 보니 **기존 테스트는
그대로 초록**이고 **새 테스트만 red**였다. gate 2207→2208.

⇒ **틀린 기록도 값이 난다**(M19 이후 네 번째). 다만 값이 난 건 기록이 말한 결함이
아니라 **그 자리를 지키던 가드**였다.

## M32 — 근거 없는 분석이 두 클라우드에선 사람 없이 실행됐다 + 스윕을 게이트로 (완료, 2026-08-16)

**결함**: `apply_gate`/`reconcile`을 읽는 provider가 **AWS 하나**였다. `reconcile`이
근거 없음으로 보는 것 — 알람 미발화 · 증거 없음 · **P1인데 confidence 낮음** ·
root_cause 어휘가 증거에 없음(환각 신호) — 을 AWS는 사람에게 올리고 **GCP/Azure는
그대로 자동 실행**했다. M23과 같은 안전 게이트 계열. **공유해도 안전**하다: `reconcile`은
순수 함수(`re`·dataclasses·계약 타입뿐, 네트워크·모델·SDK 없음)이고 `apply_gate`는
**내리기만** 한다.

⚠️**기존 테스트 둘이 red가 났고 그게 요점이었다** — `test_decision_p1_auto_mode`가
`severity`만 P1로 올리고 confidence는 **0.30**을 뒀다. 게이트에 물으니
`['P1 severity with low confidence 0.30']`. **모델이 뒷받침 안 한 P1**을 만들어 놓고
자동 실행을 단언하던 픽스처였다. AWS 대응 테스트는 `_determine_mode`를 **직접 불러
게이트를 우회**한다 — 양쪽이 서로 다른 방식으로 이 질문을 피해 왔다.

**스윕을 영구 게이트로**(`test_contract_symbol_parity.py`): provider별 임포트 **전이
폐포**로 공용 심볼 독자를 세고, **26건 전부에 사유**를 적었다. 새 비대칭은 red →
분류 강제. *비대칭 금지*가 아니라 **설명 없는 비대칭 금지**.
⚠️**첫 스윕은 직접 임포트만 세어 틀렸다** — `post_webhook`이 AWS 전용으로 보였는데
셋 다 `_executor_common`으로 닿는다. **직접 계수는 없는 비대칭을 만들고 있는 것을 감춘다**
(`['aws','gcp']` 8건이 통째로 안 보였다). ⚠️새 가드가 **내 사유 둘이 부실하다고 red**를 냈다.

**검증**: gate 2147→**2203**(+56). 변이: GCP에서 게이트 제거 → 스윕이
`apply_gate:aws+azure`로 정확히 지목.

## M31 — 롤백 가드 목록에서 AWS 둘이 빠졌고, 그걸 잡을 테스트가 AWS를 안 셌다 (완료, 2026-08-16)

어댑터가 내보내는 롤백 액션은 **일곱**인데 `ROLLBACK_ACTIONS`는 **다섯**이었다 —
`AWS-RollbackEKSDeployment`·`AWS-RollbackLambdaAlias`가 없어 `is_rollback()`이 AWS
롤백에 **False**를 답했다. M23의 정확한 재판(그때도 AWS 사본에만 `Destroy`가 없었다).

⚠️**그리고 이걸 잡으려던 테스트가 같은 병을 앓았다**: 도크스트링은 *"adding a provider
without registering its rollback fails here"* 인데 순회 목록이
`("ONPREM-","GCP-","AZURE-")` — **클라우드 목록에서 AWS가 빠져 있다.** 게다가 `any(...)`라
클라우드당 하나만 있으면 통과한다. **손으로 쓴 형제 목록이 여섯 번째로 틀렸다** → 기대
집합을 **실행 어댑터에서 AST로 유도**하고 양방향으로 묻게 바꿨다.

**지금 live는 아니다**: `is_rollback` 소비자는 `onprem_runner` 하나뿐이라 선언이 틀린
것이지 조치가 새지는 않는다 — 다만 AWS 롤백을 그 가드에 태우는 순간 AWS만 다른 답을 받는다.
**검증**: gate 2146→2147. 변이: AWS 둘 제거(=고치기 전) → 새 가드 단독 red, **옛 가드는
그 상태에서 초록**이었다는 것이 요지다.

## M30 — 런북 스텝의 condition을 GCP/Azure는 아예 안 읽었다 (완료, 2026-08-16)

`evaluate_condition`은 계약이고(세 형태를 도크스트링이 명시) AWS executor는 스텝마다
그걸로 거른다. **읽는 provider가 AWS 하나**였다. GCP/Azure는 스토어 런북의 `steps`를
평탄화하며 `capability`만 읽어, 계약대로 쓴 운영자는 **모든 조건부 스텝을 무조건** 받았다
— 카탈로그가 여섯 번 쓰는 `{"previous_step_failed": true}`(=**에스컬레이션**)를 무조건
내보낸다는 건 **아무것도 실패 안 했는데 더 센 조치를 친다**는 뜻이다. M19와 같은 모양.

⚠️**평가 시점이 다르고 그건 덮을 버그가 아니다**: AWS는 **실행 중**에 걸어 갱신하므로
에스컬레이션이 실제로 발화한다. GCP/Azure는 **결정 시점**이라 초기 컨텍스트로 평가 →
에스컬레이션은 **연기가 아니라 제외**다. 나머지 절반은 step-walking executor(=M29)가 필요하다.
⚠️내 픽스처가 `resource_type`을 언더스코어로 써서 **대조 테스트가 잡았다**(어댑터 키는 하이픈).
**검증**: gate 2135→2146(+11). 변이 → 4 failed.

## M29 — Azure는 하지 않은 조치를 "해결됨"으로 보고한다 (측정 완료·미수정, 2026-08-16)

`azure/executor.py::_execute_single_action`은 **아무것도 실행하지 않는다** — 로그를 찍고
`success: True`를 돌려 `executed`에 쌓이고 `resolved=True`가 되어 **Slack에 올라가고
기록된다.** `runners/azure_runner.py`는 **311줄 실구현**(ARM→AKS 자격증명→`_k8s_rest`)이고
`gcp_runner.py` 308줄과 대등한데, **Azure executor만 자기 러너를 안 부른다**(GCP는 Phase 3에
배선). `docs/`·`src/` 어디에도 스텁이라는 줄이 없다(정규식 전수 0건).

**왜 못 잡았나**: `test_scope_all_runners.py`는 **러너 셋**에 스코프를 묻는다 — 러너는
대칭이라 초록이다. **비대칭인 건 executor인데 아무도 안 물었다**(Risk 12④ⓐ).

⛔**안 고쳤다 — 승인 사안.** 배선하면 실제 ARM/AKS 변경이 시작된다(하드-투-리버스는 승인 후).
`success: False`로 낮추는 것도 출력을 바꾸므로 **선택**이다. 가드
(`test_executor_dispatches_to_runner.py`)로 **설명 없는 비대칭 금지**만 걸어 뒀다 —
배선하는 순간 red가 나서 기록을 같이 고치게 된다. 근거
`docs/evidence/azure-executor-reports-resolved-without-executing.log`.

## M28 — 신뢰할 수 없는 쪽만 검증을 안 했다 (완료, 2026-08-16)

**목적**: 렌즈를 문서 추적이 아니라 **기계적으로** 돌렸다 — 공용 계약 모듈의 공개 심볼마다
**세 provider 중 몇이 읽는지** 세었다.

**찾은 것**: `fits_resource`·`validate_runbook`·`is_destructive_action`은 셋 다 읽는데
`normalise_runbook`만 **AWS 하나**. 그 홀수를 따라가 보니 **그 비대칭 자체는 정당했다**
(`Decimal`은 boto3 산물, Firestore/Cosmos는 네이티브 int — M19 ⓑ 모양). 정당한 비대칭
끝에 정당하지 않은 것이 있었다: `_select_runbook` **티어 1**(운영자가 out-of-band로
손등록하는 스토어)은 GCP/Azure에서 **검증을 전혀 안 했고**, 티어 2(레포 내 상수
`BUILTIN_RUNBOOKS`)만 매 반복 검증했다 — **변조될 수 없는 쪽을 검증하고 변조될 수 있는
쪽을 믿었다.** AWS는 반대로 하고 이유까지 주석에 적어 뒀다.

**고친 것**: 두 provider 티어 1에 `validate_runbook` + 폴백. ⚠️`require_alarm_name`은
**기본값 False**로 두었다 — AWS는 `get_item(Key={"alarm_name": …})`이라 속성이 반드시
있지만 GCP/Azure는 **문서 ID로** 키를 건다. True를 넘기면 정상 오버라이드를 전부 거절해
**티어 1이 도달 불가**가 된다(티어 2가 예전에 깨진 그 모양). 테스트로 고정했다.

**검증**: gate 2107→**2123**(+16). 변이 `problems = []` → **8 failed**(malformed 4종 × 2).
⚠️첫 판은 내 수정이 **비-dict에서 터졌고 테스트가 잡았다** — `validate_runbook`은 "never
raises"로 그 경우를 보고하도록 설계돼 있어 판별을 검증 앞으로 옮겼다. 잠재 결함(스토어에
아직 아무것도 안 심음), 아래 티어의 `rto_sec`과 같은 지위.

## M27 — 진입점을 둘만 셌고, 게이트 숫자를 아무도 안 봤다 (완료, 2026-08-16)

**목적**: PR #39로 **190개 테스트가 처음 CI 검증**된 뒤(1912→2102, ubuntu·py3.13) 진입점의
"CI 일치는 1912까지" 경고를 걷어냈다.

**찾은 것 — 형제 집합, 또**: 진입점은 셋인데 **둘만 고쳤다.** `NEXT_PLAN` 8행은 죽은 경고를
그대로 달고 있었고 게이트 숫자도 **2027**로 **75 뒤처져** 있었다 — 한 줄에 오류 둘.
드리프트는 처음이 아니다(08-15: 문서 2073 / 실제 2081·2085). **줄 수 예산 가드는 틀린
숫자를 못 본다 — 긴 파일만 본다.**

**고친 것**: `test_gate_number_claims.py` — ⓐ세 진입점이 서로 다르면 red ⓑ`passed+skipped`를
**pytest 수집 수**와 대조. ⚠️**합계를 고정한 이유**: 여섯 모듈이 `pytestmark = skipif`를
다는데 **런타임 스킵이라 수집은 된다** → helm 없는 기계는 passed↔skipped 사이만 옮겨가고
합계는 보존된다. `passed`를 고정했으면 문서와 무관한 이유로 남의 노트북에서 red가 났다.
⚠️**첫 판은 가드가 틀렸다** — 세 문서 모두 "숫자 하나"를 요구했는데 STATUS의 검증 Baseline은
**newest-first 이력**이라 1862/1825/1789를 정당하게 든다. **틀린 건 문서가 아니라 계기였다.**
덤: STATUS의 `1862→+211`도 **2073 시절 잔재**(1862+211=2073) → `+245`.
그리고 내가 심은 "직전 검증 `aa1c913`=2102"는 **구조적으로 항상 한 커밋 뒤처져** 값을 지우고
**"CI 숫자는 PR 체크가 권위"** 포인터만 남겼다(권위 문서 복제 금지의 재발).

**검증**: gate 2102→**2107**(+5). 변이 `NEXT_PLAN`만 2102 → `test_entry_docs_agree` 단독 red.

## M26 — 렌즈가 여섯째 층에서 말랐다 (완료, 2026-08-15)

`ExecutorOutput`에 같은 기준(읽는 쪽의 provider 간 비대칭)을 댔다. **결함은 없었다** —
GCP/Azure `executor.py`의 `bool(executed) and not skipped`를 공용
`resolution_verdict(...).resolved`로 모았을 뿐 **동작 변경 0**. 다섯 층에서 다섯 결함이
나온 뒤 여섯째는 **범위**였다. **말랐다는 것도 측정이다** — 다음 세션이 같은 층을 다시
훑지 않게 여기 남긴다.

## M25 — optional 임포트 여섯이 미선언이었다 (완료, 2026-08-15)

`pyproject.toml`은 이 교훈을 **패키지 하나**에 대해 이미 적어 뒀는데(08-08 CI가 tracing
17건으로 잡음) **형제를 안 셌다.** `try: import X / except ImportError:`를 전수로 훑으니
여섯이 더 나왔고 **전부 폴백이 경고**라 설치는 성공하고 **팔 하나 없는 에이전트가 나간다**:
`.[gcp]`는 로그·메트릭·스토어가 없고, `.[azure]`는 **LLM조차 없었다**(`openai`).
`make dev-up`의 ASGI 스택은 **아무도 선언하지 않아** CI가 인라인으로 떠받치고 있었다.
**고친 것**: gcp/azure extras 보강 + 새 `serving` extra, CI는 인라인 대신 extra를 부른다.
**검증**: +19(+4 CI 절). ⚠️`.[azure]`는 여전히 설치 불가 — **업스트림 차단**
(`agent-framework`가 `core[all]` 강제, `msft_deployer.py:19`의 심볼이 core 1.14.0에 없음).
**안 고쳤다 — 현재 API를 모르고 추측은 발명이다.**

## M24 — 게이트가 테스트마다 Gemini를 과금 호출하고 있었다 (완료, 2026-08-15)

`make check`가 **라이브 Vertex AI**로 나가고 있었다. **깨진 테스트는 0건**이라 아무도
빨간불을 못 봤고, 비용과 비결정성만 조용히 쌓였다. `tests/conftest.py`에 세션 autouse로
`socket.socket.connect`/`connect_ex`를 감싸 **루프백만 허용**하고 나머지는 목적지를 이름
붙여 거절한다 → **D49**(게이트는 외부 네트워크로 나가지 못한다, D45의 일반화).
**검증**: 288.56s → **36s**. ⚠️**이 단축은 최적화가 아니라 과금 호출을 멈춘 결과다.**
차단으로 깨진 테스트 **0건** — 즉 아무도 그 네트워크를 필요로 하지 않았다.

## M23 — 파괴 액션이 AWS에서만 자동 실행됐다 (완료, 2026-08-15)

`_determine_mode`의 위험 패턴 목록이 세 provider에 **복사**돼 있었고 **AWS 사본에만
`Destroy`가 빠져** 있었다. 결과: `Destroy`가 든 액션은 GCP/Azure에선 APPROVE,
**AWS에선 AUTO**. ⚠️**다수가 옳고 하나가 뒤처지는 모양** — 형제 비교의 새 얼굴이다.
**고친 것**: `runbooks/schema.py::is_destructive_action` 한 벌 + 세 provider가 읽음
(M19의 `fits_resource` 선례). **D48**로 계약화. **검증**: +79.

## M22 — 승인자에게 보여 준 "과거 유사 인시던트"가 랜덤이었다 (완료, 2026-08-15)

`ScanIndexForward=False, Limit=5`가 **정렬 키를 `incident_id`(랜덤)** 로 잡고 있었다 →
"최근 5건"이 **사전순 5건**이고, 테이블이 커져도 **같은 5건에 얼어붙는다.**
**이번엔 AWS만 틀렸다**(GCP/Azure엔 이 기능이 없다) — 비대칭은 provider 간에만 생기지
않는다. **고친 것**: 페이지네이션 읽기 + 클라이언트측 `created_at` 정렬(상한 500).
**검증**: +13.

## M21 — 등급이 P3↔P1로 뒤집혔다 (완료, 2026-08-15)

`reason`이 규칙 이름을 잃어 분석 모델이 근거 없이 등급을 매겼다. ⚠️**형제가 provider가
아니라 같은 provider의 진입점 둘**이었다 — 형제 집합을 "세 클라우드"로만 상상하면 못 센다.
**고친 것**: `adapters/base.py::incident_reason` 한 벌(규칙 이름 4키 + 설명 2키를 이어
붙이고 폴백은 `signal_type`), AWS는 위임 · GCP/Azure는 원시 키 하나 대신 이것을 읽는다.
**검증**: +17. ⛔`triggered_at`·`metric_name`은 **닫혔다**(전수 스윕: 8필드 중 닿는 건
`reason` 하나 — **결함이 아니라 범위**). **다시 열지 말 것.**

## M20 — 운영자가 알람 규칙에 써 둔 severity가 두 모델에는 끝내 안 닿았다 (완료, 2026-08-15)

**목적**: **M19가 남긴 기준을 그대로 다음 계약에 댔다** — *"선언됐는데 안 읽힌다"가 아니라
"읽는 쪽이 provider 간에 비대칭이다"*. `NormalizedIncident`는 provider 경계를 넘는 유일한
봉투라 그 필드들을 **읽는 쪽으로** 훑었다.

**찾은 것 — 형제 집합, 다섯 번째**
- `severity_hint`는 **네 시그널 어댑터가 전부 채운다**(Azure `essentials.severity` · GCP
  `incident.severity` · onprem Alertmanager 라벨 · AWS 알람 상태). **읽는 곳은
  `aws/analyzer.py:200` 하나**였다. `observations`(→ `Alert detail`)도 같다.
- ⚠️**이 레포가 스스로 적어 뒀는데 가드가 안 지켰다**: `test_analyzer_prompt_evidence.py`
  도크스트링(07-29)이 **네 어댑터를 정확히 열거**하고 *"severity가 **AUTO냐 APPROVE냐**를
  정한다 — 라이브 관측: `severity: warning` 규칙이 **P1으로 등급 매겨져 즉시 조치됐다**"*라고
  쓴다. 그런데 그 파일의 임포트는 **`aws.analyzer` 한 줄**이다.
- **재현**: 실제 `_build_prompt` — aws는 둘 다 YES, **gcp/azure는 둘 다 NO**. 두 정규화
  블록은 **AWS의 고치기 전 다섯 줄과 글자 그대로 같다**. **onprem은 이미 덮인다**
  (`onprem_incident_pipeline.py:34`가 AWS analyzer를 임포트 — 07-29 관측이 그 경로).

**고침(발명 없음)**: 프롬프트 두 줄과 **함께 시스템 프롬프트의 안전장치**를 이식했다 —
*"강한 증거로 다루되 벗어나면 root_cause에 이유를 써라. **구속력은 없다** … **말없이
어긋나는 것**이 이 항목이 막으려는 것이다."* ⚠️**안전장치 없이 라벨만 넣으면 구멍보다
나쁘다**: 라벨이 지시로 읽혀 **AUTO/APPROVE를 라벨 혼자 정한다.** severity 어휘 →
P1/P2/P3 **매핑은 안 한다**(정책 결정, AWS도 안 했다).

**가드 +18**: 기존 파일을 **세 analyzer로 parametrize**. 이식 전 **16 red**, **AWS 11건은
내내 초록**. 역방향 둘 — **힌트가 없으면 줄을 안 붙인다**(무조건 붙이는 구현이면 나머지가
전부 통과한다) · **시스템 프롬프트가 "not binding"을 말한다**. onprem을 목록에서 뺀 이유를
**코드에 적었다**(빠진 것과 덮인 것은 구별돼야 한다).

**검증**: `make check` **1894 → 1912**(+18, 2026-08-15, 로컬 macOS·py3.13; **CI도 1912 —
일치**). 변이 **6건 전부 red, 생존 0**(무조건 붙이기 · 안전장치 제거 · 어휘 정규화 포함),
복구 후 0 modified.

**⇒ 이번에 확인된 것**: **직전 고침이 남긴 기준이 다음 결함을 찾는다**(M19 → M20, 하루 만에).
그리고 ⚠️**고침을 설명하는 산문이 그 고침의 범위를 넘겨 말할 수 있다** — 07-29 도크스트링은
네 어댑터를 정확히 열거했는데 **코드는 하나만 고쳤다**. **산문이 참이어도 임포트 줄이 범위다.**

증거 `docs/evidence/operator-severity-never-reached-two-models.log` · PR #37

## M19 — 런북이 "이 자원엔 안 맞는다"고 선언해 뒀는데 두 provider가 그 줄을 안 읽었다 (완료, 2026-08-15)

**목적**: `NEXT_PLAN`의 열린 항목 **ⓑ**("`renew_certificate`가 GCP/Azure 어댑터에 매핑
없음")를 "기록된 이유를 한 번 돌려 보고 시작할 것"에 따라 시험했다. 시작 전에 **직전
세션의 M18/D47 문서 체크포인트가 커밋 안 된 채** 트리에 있어 먼저 닫았다(PR #33).

**결과 — ⓑ는 틀렸고, 그 옆에 진짜 결함이 있었다**
- **ⓑ는 오기였다(stale 아님)**: 읽지 말고 **돌려서** 재니 **네 provider 전부** 풀린다.
  `git log -L`로 매핑은 **2026-07-09**부터 — 그 기록이 쓰인 08-14 커밋보다 **한 달 앞선다**.
- **#34 결함(고침)**: 티어 2가 런북의 **`resource_types`를 안 읽는다**. AWS는
  `_fits_resource`로 **이미 배제 중**이고, 어긋난 쌍 **67 / 81**이 GCP/Azure에선 그대로
  선택된다. ⚠️**AWS보다 조용하다**: AWS는 하드코딩 액션으로 폴백해 **다른 provider의
  액션**을 넘기지만(시끄럽다), GCP/Azure는 풀리지 않는 capability를 **버리고 짧아진 목록**을
  돌려준다 → `certificate-expiry`가 kubernetes-workload에 선택되고 **RTO 600을 단 채
  notify만 한다**. 규칙은 `runbooks/schema.py::fits_resource` **한 곳**으로(세 provider가
  읽고 AWS는 위임) — **공유되는 게 SDK가 아니라 계약**인 블록이라 복사본을 안 늘렸다.
- **가드 +32**: ground truth를 **함수가 아니라 카탈로그가 선언한 데이터**에 댔다(두 구현이
  똑같이 틀리면 통과하는 가드를 피하려고). 전수 스윕(9타입 × 전 런북 × 2 provider) +
  **역방향 셋**(선언한 타입은 뽑힌다 · unknown은 아무것도 배제 안 한다 · **폴백은 게이팅
  안 된다** — AWS엔 있고 여기엔 없던 짝). 역방향이 없으면 **"전부 배제"가 통과한다**.

**검증**: `make check` **1862 → 1892 → 1894**(+32, 2026-08-15, 로컬 macOS·py3.13;
**CI도 1894 — 숫자 일치**). 변이 **6건 전부 red, 생존 0**, 복구 후 0 modified.

**⚠️ 내가 틀린 것 셋**: **형제 함정 네 번째** — 두 파일에 같은 필터를 넣었는데 **Azure만
import가 되돌아가** 죽어 있었다(GCP만 초록인 걸 보고서야 알았다) · **변이 "생존"을 잘못
읽었다** — **틀린 테스트 파일**에 물었고 실제 가드는 `test_runbook_selectability.py`에
있었다(*"생존"은 어디에 물었는지까지 말할 것*) · **대기 조건이 "출력 파일이 비어 있지
않다"**여서 pytest가 도는 중에 트리를 되돌렸다(*변이·실행·복구는 한 스크립트 안에*).
그리고 **기존 테스트 2건이 red가 됐고 그게 옳았다** — 픽스처가 모든 런북을 **k8s인 척** 물었다.

**⚠️ 남긴 것 — 그리고 건드리면 안 되는 것**: ⓐ(`kafka-lag-spike` 두 dict 불일치)·ⓒ(첫-매치-
승리)는 **정책 사안**. 계약 필드 일곱을 훑어 보니 **`provider`는 AWS 포함 아무도 안 읽는데
빌트인 9개가 전부 `"aws"`**라, 읽기 시작하면 GCP/Azure는 **전부 `generic-recovery`로
떨어진다**(=#30 이전). ⇒ **"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다. 기준은 읽는
쪽의 provider 간 비대칭이다.**

증거 `docs/evidence/resource-types-declared-and-unread.log` · PR #33·#34

## M18 — 가드가 형제 집합 중 **하나만** 순회하고 있었다 (완료, 2026-08-13)

**목적**: 직전 세션이 남긴 Next("`BUILTIN_RUNBOOKS`를 덮는 테스트가 있나")를 그대로 따라간
것이 시작이다. 답은 **"있다, 5개 파일"**이었는데 **전부 dict의 모양만** 물었다(길이·키
집합·deepcopy). **읽는 쪽으로 가니 죽은 코드가 있었다.** 그 뒤 같은 모양이 두 번 더 나왔고,
셋을 묶는 것은 하나다 — **가드가 형제 중 하나만 순회하면 나머지는 안 물어진 채다.**

**결과 — PR 3건, 진짜 결함은 하나**
- **#30 결함(고침)**: GCP/Azure `_select_runbook` **티어 2가 원리상 도달 불가**였다. 같은 12줄이
  **두 파일에 복사**된 채 결함 셋이 겹쳐 있었다 — ①`if not validate_runbook(rb)`(그 함수는
  **문제의 목록**을 돌려주니 빈 리스트=유효 → **유효한 런북마다 skip**) ②`rb.get("steps")`
  (`steps`는 `CAPABILITY_RUNBOOKS` 것) ③`estimated_rto_sec`(계약은 `rto_sec` → **D47**).
  ⚠️**터지지 않는 게 핵심**: actions는 티어 3에서 정상 resolve되니 결정은 채워져 보이고,
  **자기가 따른다고 주장하는 런북과 RTO만** 틀렸다 = **모든 GCP/Azure 인시던트가
  `generic-recovery`**. 기존 커버리지는 `"runbook_id" in result`와 `!= ""` 두 줄로,
  **둘 다 `"generic-recovery"`에 영원히 참**이었다.
- **#31 범위(`src/` 무변경)**: "로깅 문은 DOCUMENT/DUAL을 **안 봤다**"를 시험했더니 **변명이
  참**(다섯 다 WARNING+에 안 닿음 = 고칠 것 없음). **대신 감사가 `for name in REPORT:`**라
  **DOCUMENT의 거울 의무**를 안 물었다 — DOCUMENT CLI가 같은 리다이렉트를 부르면
  `yaml.safe_load_all`이 **ScannerError**로 터진다(실증). 가드 3건.
- **#32 범위(`src/` 무변경)**: capability **17종 × provider 4종** 전수 행렬 — 구멍은 **이미
  알려진 정당한 skip 하나**뿐. **검증(`verify`)이 onprem 한정**인 것은 **기록된 경계**이고
  코드가 정직하다(`verified=None`) → 틀린 건 **이 파일의 무조건 주장 한 줄**이라 한정했다.
  가드 4건(선언처가 **둘**이므로 **양쪽을 읽는지 자체가 ground truth**).

**검증**: `make check` **1825 → 1856 → 1859 → 1862**(+37, 2026-08-13, 로컬 macOS·py3.13;
CI도 세 지점 전부 통과). 변이 **8+5+5 = 18건 전부 red, 생존 0**, 복구 후 diff clean.

**⚠️ 내가 틀린 것 넷 — 전부 증거 로그에 있다**: 변이 하네스의 `restore()`가 `git checkout --`라
**커밋 안 된 고침을 날렸다**(*초록으로 안 돌아오는 복구는 복구가 아니다*) · 새 RTO 가드의
픽스처가 **틀린 기본값과 같은 300**이라 결함을 통과시켰다(*기본값과 같은 값을 고른 픽스처는
가드가 아니다*) · `basicConfig(stream=sys.stdout)`이 **호출 시점의 스트림을 붙잡는** 걸 놓쳐
첫 실증이 헛돌았다(*리다이렉션은 흉내 내지 말고 실제로 걸 것*) · `verify`를 **틀린 해소기**에
물었다. 그리고 **선언처가 둘인데 하나만 본 것 — 그걸 찾으려고 만든 스윕 안에서**.

**남긴 것(정책 판단이라 발명 안 함)**: `kafka-lag-spike`의 두 dict 불일치 ·
`renew_certificate`의 GCP/Azure 어댑터 매핑 부재 · 티어 2의 첫-매치-승리 ·
DUAL의 모드 조건부 리다이렉트(**하중을 못 받는 가드**) · `assert_concurrency_applied`(도달 불가).

증거 `docs/evidence/{gcp-azure-capability-scan-was-unreachable,
report-streams-swept-across-all-clis(15절),verify-capabilities-declared-vs-implemented}.log`

## M17 — 리포트가 독자에게 갈린 채 도착하고 있었다 (완료, 2026-08-10~11)

**목적**: 비용 프로브가 본문을 stdout, 판정을 stderr로 내보내 **파이프에서 세 절이 전부 비어**
있었다(TTY에선 멀쩡 = 저자가 본 것). 고치고 나니 **가드가 못 잡은 이유**가 더 컸다 — `capsys`가
`.out`/`.err`를 갈라 주므로 `.err`에 묻는 테스트는 **독자의 사본이 갈라진 걸 원리상 못 본다**
(STATUS Risk 12④). 그 맹점을 `scripts/` CLI **22개 전수**에 대고 물었다.

**결과**
- **분류가 먼저였다** — "stderr 금지"가 아니라 **"독자의 스트림이 독자가 필요한 걸 날라야
  한다"**이고, 독자가 파서면 의무가 거꾸로 선다. `scripts/*.py` 22개 = **REPORT(17) /
  DOCUMENT(3) / DUAL(2)**, 미분류 신규 스크립트는 red. `render_tenancy.py`는 처음부터 옳았다.
- **수정 9건**(exit code 전부 유지) — verify_netpol/tenant_isolation/tenancy_adoption ·
  verify_image_signature(**스트림이 실패 종류마다 달랐다**) · attach_addon(`--commit` 거부가
  diff 뒤 = **없는 줄이 유일한 실패 신호**) · watch_cloud_spend · push_addon_status(한 스트림
  +flush) · preflight(모드 의존) · **`src/`의 manifest_generator**(인자 없이 리다이렉트하면
  usage가 **유효 YAML 매핑**으로 파일에 앉고 exit 0).
- **덤**: CE **요청당 $0.01** · `spend-watch` 월 **~$0.30** · "당일 줄의 0은 잰 0이 아니다"를
  명시(아무 문서에도 없었다).

**검증**: 변이 **24건 전부 red, 생존 0**(거울 방향 3 · 미분류 스크립트 1 · `src/` 3 포함 —
단 **1건은 처음에 살아남았다**, 아래) · 낡은 가드 정확히 3건이 red로 잡혀 `.out`으로 ·
**실제 서브프로세스 파이프**로 교차 확인(고친 것을 되돌리면 `capsys` 가드와 파이프 가드가
**함께** red) · `verify_netpol_enforcement`는 kind에 **라이브로 돌려** ENFORCED 전문이
stdout에 도착함을 확인. `make check` **1743 → … → 1789**, CI가 **다섯 지점 전부 숫자까지 일치**(#24~#28). 증거
`docs/evidence/{spend-probe-report-split-across-streams,report-streams-swept-across-all-clis}.log`.

**세 번째 문(08-11 추가)**: `src/`는 `sys.stderr` **0건**인데 **로깅 핸들러도 0건**이라
`logger.warning`이 `logging.lastResort`로 **stderr에 나간다** — `print`가 없는 경로라 스트림
훑기로는 **원리상 못 찾는다**. 실제로 `push_addon_status`가 읽기 경로에서
`warn_if_ambient_read`("스포크는 아무 자격증명이나 들고 읽는다")를 그리로 흘리고 있었다.
`main`이 로깅을 stdout으로. 가드는 **서브프로세스**로 돌린다 — 인프로세스면 pytest 핸들러가
`lastResort`를 가려 **버그가 원리상 안 보인다**(`capsys` 맹점의 한 층 아래 판박이).

**넷째 문(08-11 추가) — 잡히지 않은 예외**: "나머지는 클러스터가 필요하다"를 **시험했더니**
넷은 아니었고 **넷 다 깨져 있었다**. `PATH`를 벗기면 트레이스백으로 죽어 stdout 0B·**exit 1**
— `probe_cloud_spend`는 헤딩만 찍고 죽어 08-10의 결함이 다른 문으로 돌아왔고,
`watch_cloud_spend`의 exit 1은 "**새로 과금되기 시작했다**"라 **못 쟀는데 경보를 울린다**.
원인이 정확했다: `_run`은 처음부터 막고 "never raises"라 적었는데 **형제 `_aws`가 안 했다**.

**남긴 경계**: 실제 파이프 뒤 **11 invocation / 9 CLI**(4→8 REPORT는 "클러스터 필요"를 시험한
결과) · 나머지는 라이브 자격증명·기동한 스택이 필요하거나 **강제할 실패 경로가 없다** ·
로깅 문은 **REPORT 4개만** · **`slack_live_approval`은 안 고쳤다**(임포트가 untracked
`cdk.out`에만 있는 경로 + 덮어쓰는 이름 6개 중 4개 부재 → 고치면 **돌아가면서 조용히
아무것도 안 한다**. 올바른 이름은 데모를 Slack에 태워야 안다 → 발명하지 않았다).

## M16 — 비용 관측: 세 클라우드가 다 "안심시키는 0"을 주고 있었다 (완료, 2026-08-09)

**목적**: "AWS 8월 $0"을 두 번 보고했고 둘 다 틀린 뒤(실제 $8.81), **측정 자체를 믿을 수 있게** 만든다.

**같은 실패가 세 번, 매번 다른 얼굴로 — 셋 다 호출은 성공하고 결과도 그럴듯하다:**

| provider | 안심시키는 기본값 | 실제 |
|---|---|---|
| AWS | `aws ce`가 **크레딧 상계** → 순액 ≈$0 | **$8.81** (t3.medium 18일째) |
| Azure | `az consumption usage list`가 **28행 전부 `pretaxCost` null** → 합계 0 | **₩1,989** MTD (7월 ₩22,630) |
| GCP | 프로브에 **provider 자체가 없음** → 잰 0과 구별 불가 | **여전히 못 잼**(비용 API 부재) |

**산출**: `make spend-check`(3 provider, 크레딧 필터·전 리전/구독/프로젝트 스윕) ·
`make spend-watch`(**무엇이 새로** 과금되기 시작했는가 — 임계값 없음) + 셸 훅(하루 한 번) ·
`docs/GCP_BILLING_EXPORT_SETUP.md`(콘솔 5클릭 + 함정) · GCP 예산 ₩20 → **₩28,000** ·
결정 **D44~D46** · 증거 5건(`aws-spend-hand-check-was-zero` · `gcp-budget-always-firing-fixed` ·
`gcp-actual-spend-has-no-api` · `azure-consumption-cli-returns-null-cost` ·
`azure-credit-netting-does-not-apply-yet` · `spend-watch-launchd-blocked-by-tcc`).

**검증**: gate **1699 → 1737**(로컬 macOS·py3.13 **↔ CI 일치**) · 변이 **22건 전부 red, 생존 0**.

**과대 해석 금지**: GCP는 **여전히 못 잰다**(콘솔 토글 하나에 막혀 있다) · Azure 크레딧 상계는
**"지금 없다"지 "없는 성질"이 아니다**(예약을 사면 갈린다) · **터미널을 안 열면 검사도 없다**
(launchd는 TCC로 막힌다) · ACR 월 ~₩6,600은 **다른 프로젝트 것이라 두었다**.

**내가 틀린 것 3건(전부 기록)**: 게이트에서 **라이브 gcloud를 부르는 가드**(21.97s → 0.02s) ·
`mtime` 초 단위에 속아 **정상 동작을 실패로 읽은 테스트** · **CI에 없는 `/bin/zsh`**
— Risk 12②를 **인용해 가며 짠 커밋에서** 그대로 밟았고, CI가 잡았다.

## M15 — 공급망을 0에서 집행까지 + Phase 5 경계 + `main` 보호 (완료, 2026-08-08)

**gate 1617 → 1668 (+51), 커밋 23건.** 하루 전체를 관통한 패턴 하나: **문서에 적힌 이유가
진짜 구속 조건이 아니었다** — 게이트 red(달력) · 서명키(배포 위상) · 보관(데이터 0) ·
Cosign(서명 자체가 없음) · 어드미션(cosign 버전).

- **승인 3건을 쟀다** — ①실 DynamoDB 왕복 **통과**(`confidence`가 `Decimal`로 왕복 = 문자열이면
  화면만 영원히 "n/a", float면 boto3 예외가 `except`에 잡혀 **행 전체 소실**. 목으로는 원리상
  못 잡는다) ②GCP/Azure 보관은 **질문이 틀렸다**(스토어가 아예 없어 **지울 데이터 0** → 승인이
  아니라 프로비저닝 선행 = Phase 4) ③Cosign만 진짜 승인이었다.
- **공급망 0 → 집행**: 서명 생산자(`make sign-image`) → 배포 직전 **소비자**(`image_trust`,
  exit 2도 거부) → **CI**(`gate.yml`) → **키리스**(Fulcio 단명 인증서 = **custody의 답**).
  CI가 첫날 세 건을 잡았고 셋 다 진짜 결함(임의로 넓힌 lint · **미선언 OTel exporter** ·
  **미검증 `>=3.11`**). **어드미션은 업스트림 대기** — cosign v3 서명을 policy-controller가
  v0.15.1로도 못 읽고, v2로 서명하면 통과함을 **양방향 실증**했다.
- **서명키 rotation**(D42 TTL이 겹침 창을 유한하게) · **테스트 시효**(소스 무변경 red) ·
  **레포 원고 동기화**(원고의 "다음 단계" 3건이 이미 사실이 아니었다).
- **Phase 5 = 경계까지**: UI가 아니라 **"PR은 그 테넌트 파일 하나만 건드린다"**를 세웠다 —
  Phase 0부터 헤더에 적혀 있었지만 **반증할 수단이 0**이던 문장. 텍스트로 편집·의미로 검증.
- **`main` 보호 = 집행 확인**(D43) · **TS 닫힌 섬 제거**(인가 규칙의 **두 번째 진실 공급원**).
- **교훈 3종**: 게이트 숫자는 **날짜 없이는 주장이 아니다**· 게이트가 **말해지지 않은 환경** 위에서
  통과하고 있었다 · **행복 경로만 태운 가드는 하중을 받지 않는다**(전부 → Risk 12 — 안전망을 통째로 지워도 14개가 초록이었다). 그리고 **내 가드가 네 번 틀렸다**.
- 상세 → `PROGRESS_LOG` / `docs/archive/progress-2026-08.md` / `docs/evidence/*` / D43.

## M14 — 열린 결정 6건 전부 닫힘 (완료, 2026-07-29~08-02)

**gate 1565 → 1617 (+52).** 열려 있던 결정을 전부 닫았고(마지막 하나는 조사 중 새로 열려
같은 세션에 닫혔다), **여섯 번 다 조사가 질문을 바꿨다** — 어느 것도 "선택지 중 하나를
고르는" 일이 아니었다.

- **D36**(결정 1) — 배포는 테넌트 소유가 아니다. 한 개인 줄 알았던 게 **셋**(귀속·인가·과금)이었고
  과금은 결정이 아니라 **구조 대기**였다. 무파티션 + 테넌트별 모델 rate limit 안 함 확정.
- **D38**(결정 5) — **두 경로가 반대 방향으로 고장**이었다: 인시던트는 게이트가 옳은데 **생산자가
  테스트뿐**이라 열 수 없었고, 배포는 **가드 없이 cluster-admin**이었다. A(스코프 생산자)+B(배포
  신원 축소) 둘 다 실행, **둘 다 옵트인**(→ `STATUS` Risk 3).
- **D39**(결정 2) — 예외를 붙잡던 **근거가 사실이 아니었다**. `src/`에 `MCPServer` 생성자가 0이라
  무스코프 경로를 실행하던 유일한 코드는 **그것을 고정하던 테스트**였다. 읽기도 기본 거부.
- **D40**(결정 4) — **막는 게 하나가 아니었다**(넷). 기록된 하나는 가장 먼저 걸리지도 않았고,
  그 아래 **순환 게이트**가 있었다: 승격 도구가 proven 집합을 전제해 **새 기판을 승격시킬 수 없다**.
  k3s는 넣지 않음(재개 조건: k3s-lab에 실제 워크로드).
- **D41**(결정 3) — **선택지가 둘이 아니라 셋**이었고 셋째는 **같은 증거 로그 40행 위**에 있었다
  (형제 필드 `networkPolicies`는 이미 객체 직접 렌더). Capsule 폐기 경고 2→**0**.
- **D42**(결정 6, Phase 5를 재다가 열렸다) — `nonce`가 one-time-use라고 **적혀만 있었다**:
  `_spent`가 인스턴스 상태인데 프로덕션이 브로커를 매번 새로 만들어 **3/3 발급**됐고, **수호
  테스트가 broker 하나를 잡아 유일한 성립 조건을 제공**했다. 진짜 1회용은 **틀린 수정**이었다
  (실행기가 같은 인시던트로 두 번 해석). **TTL로 대체** — 약속이 줄었고 대신 지켜진다.
- **부수(결정 아님)** — `2차 잔여`의 "push 인증"은 **일주일째 스테일**이었고(07-26 완료),
  그 자리의 진짜 구멍은 **스포크의 읽기 신원**이었다: 맨 kubectl + 공유 `argocd` ns라 테넌트
  구분이 **코드 필터**다. 쓰기는 허브가 401로 막는다(라이브 4종).

**교훈**: 예외의 근거는 **코드로**, 게이트의 근거는 **측정으로** 확인하라 · **질문이 주는
선택지·블로커 개수를 세지 말 것**(두 번 다 답이 이미 레포 안에 있었다) · **없는 것은 테스트에서
영원히 초록이다** · 가드는 **파생**시켜라(열거하면 새 경계를 놓친다) · **폐기됐다고 사문화된 건
아니다** · 가드는 **자기 상태가 살아남는 수명에서만** 집행된다 · **계획 문서도 측정 대상이다**
(닫힌 항목이 열린 채면 다음 사람은 이미 된 일을 하거나 그 옆의 진짜 구멍을 못 본다) ·
**픽스처도 측정하라**(필드명 하나 틀린 픽스처가 오탐을 만들었다).

**새 가드 5종** — 전부 반증을 개별로 확인했다: `test_carveout_consumers_exist.py`(D39, 예외의
근거로 인용된 소비자가 실재하는가) · `test_substrate_promotion_reachable.py`(D40, 멤버십 주장이
현재 레지스트리로 반증 가능한가) · 파생 LimitRange 가드(D41, 쿼터가 `limits.`를 선언하면 그
렌더의 **모든** 네임스페이스가 기본값을 가져야 한다) · `test_scope_replay_reachability.py`(D42,
**프로덕션 함수로** 단언 — 재사용이 실제로 거부되기 시작하면 일부러 red) ·
`test_push_read_identity.py`(읽기가 ambient임을 프로세스가 말하는가).
증거 `docs/evidence/{unscoped-mcp-read-closed,deploy-identity-reduction,scope-producer-live,
k3s-netpol-enforcement,capsule-limitranges-direct,approval-ttl-replay-bound,
push-identity-ambient}.log`, 조사 `docs/plans/2026-07-29~2026-08-02-*`.

## M13 — "선언됐지만 아무도 읽지 않는 것들" 14건 (완료, 2026-07-28~30)

**gate 1411 → 1565 (+154).** 증거 `docs/evidence/{phase3-tenant-grant-validation,
runbook-selectability,capsule-deprecation-metadata,executor-span-approval-path,
onprem-runbook-matching,declared-unconsumed-sweep,incident-trigger-time,
cloud-incident-fields,incident-time-to-resolve,rollback-cost-metrics,
activity-read-model-drift,report-windows,deployment-environment-absence,
deployment-namespace-provenance}.log`.
결정 → `DECISIONS` D33·D34·D35.

Phase 3가 인가를 닫은 뒤 남은 잔여를 우선순위대로 소진했는데, **아홉 건이 전부 같은
결함**이었다: 필드나 계획이 **선언되고, 채워지고, 저장되고, 아무도 읽지 않는다.** 테스트는
아홉 번 다 초록이었다 — 전부 *생산자*를 단언했기 때문이다. 아홉 번 다 **라이브 실행만이**
드러냈고, 그중 네 번은 유닛 테스트가 통과하는 동안 라이브가 다른 답을 냈다.

그 뒤 같은 축의 **변형 두 건**이 더 나왔고, 둘 다 스윕을 **새 방향으로 넓혀서** 찾았다:
**⑩반대 방향**("읽는데 아무도 안 씀" — 생산자 셋 중 하나만 침묵) · **⑪한 층 위**(필드가
아니라 **선언 자체를 아무도 안 읽음** — importer 0인 스키마 문서가 양방향으로 드리프트).

- **grant 대조(1425)**: 기록은 "대조 안 함"이었지만 grant를 **줄 방법 자체가 없었고**(읽기 쪽이
  아무 쓰기 경로도 만들 수 없는 필드를 소비 중) 역할 변경이 whole-item Put으로 grant를 지웠다.
  허브 로스터(못 읽으면 **503**, 회수만 예외) + 저장 전 대조 → D33.
- **런북 선택성(1445)·티어(1470)**: 런북 4개가 BUILTIN에 없어 선택 불가 → 넣었더니 라이브는
  여전히 generic-recovery. 시드 테이블의 generic 행이 티어 4의 답을 대신 내서 **빌트인 티어가
  배포 환경에서 한 번도 도달된 적 없었다**(D34). 고쳤더니 이번엔 **더 나쁜 매칭**이 이겼다 —
  1점짜리 시드 행이 3점짜리 빌트인을 눌렀다(D35, 합집합 휴리스틱).
- **온프렘 매칭(1470)**: `reason`이 `metric_name`의 **복사본**이라 매처가
  "availability availability…"를 읽었고, `resource_types`는 모든 런북에 선언돼 있고 **미소비**라
  엉뚱한 런북이 걸려도 하드코딩 AWS 액션으로 조용히 폴백했다.
- **Capsule metadata(1446)**: `additionalMetadata`는 제거 릴리스에서 **에러 없이 안 읽히는**
  쪽으로 실패할 필드라 선제 이관(라이브에서 probe 라벨 전파로 반증).
- **executor span(1454)**: 웹훅이 루트 span을 닫은 뒤 실행해 **AUTO·승인 양쪽 다 무추적**.
  승인은 부모가 아니라 **링크** — 사이 간격이 사람의 고민 시간이라 접으면 지연 수치가 무의미해진다.
- **severity_hint(1479)**: 우연을 그만두려 **계통 스윕**(437 필드 → 20 후보). 네 어댑터가 전부
  채우는데 아무도 안 읽어, 사람이 **미리** 내린 분류가 버려지고 **AUTO/APPROVE를 정하는 축**이
  산문에서만 추론됐다. 라이브 A/B: warning이 자동실행 → 승인대기로.
- **인시던트 발생 시각(1491·1496)**: 행이 "우리가 쓴 시각"만 알아 탐지 소요시간이 산출 불가.
  온프렘·클라우드 양쪽 + `detected +Nm` 배지(**읽는 쪽 없이 저장만 하면 같은 결함을 하나 더
  만드는 것**). 클라우드 `confidence`는 float라 그냥 넣었으면 boto3 예외가 기록기의 `except`에
  잡혀 **레코드 전체가 사라졌을** 것 → `Decimal`.
- **time-to-resolve(1520)**: 이 부류의 **가장 비싼 변종** — 앞의 여덟은 값이 *버려졌지만*
  이번엔 값이 **있는 척했다.** `resolved_at`이 `created_at`의 복사본이라 주간 온콜 리포트가
  **존재 내내 "MTTR 0.0분"을 자신 있게 발송**했다(fetch가 한 키를 `started_at`·`resolved_at`
  양쪽 끝에 넣었다). 부재는 눈에 띄지만 **그럴듯한 기본값은 안 띈다.** 같이 나온 둘:
  `runbook_id`에 `alarm_name` 복사 → 재발 패턴 그룹핑 붕괴 · 대시보드 Scan 투영이 **자기
  리더가 읽는 4필드**를 안 불러 전날 수정이 배지 한 층 앞에서 멈춰 있었다.
  실측 0.0→45.0, 라이브 P1/AUTO 1502초 보존·열린 인시던트는 부재.
- **롤백 비용 패널(1528)**: 이 부류가 **반대 방향으로도** 열린 첫 사례 — 읽는 쪽은 멀쩡한데
  ACTIVITY를 쓰는 셋 중 `record_rollback`만 `cost_metrics`를 빠뜨렸다. 그 자체론 과소보고인데,
  reader `mergeActivity`가 **trace만 합집합**으로 두고 나머지를 `{...latest}`로 최신 행에서
  가져가 **롤백되는 순간 도구/추론/토큰 수가 페이지에서 사라졌다**(패널이 조건부라 예외도
  "0"도 없이, 바로 아래 트레이스는 오히려 길어진 채). 라이브 BEFORE 미렌더 → AFTER
  `tool calls 5 · tokens 920`, 내역이 두 실행에 걸침. **절반씩은 각각 방어 가능한데 겹칠
  때만 터진다** · 생산자가 여럿이면 **하나만 침묵해도** 나머지가 정상을 계속 증명해준다.
- **읽기 모델 문서 드리프트(1533)**: 한 층 위 — 필드가 아니라 **선언 자체를 아무도 안 읽는**
  경우. `activity-model.ts`는 **importer가 0**이라 어긋나도 안 깨졌고, 아무도 안 쓰는
  `duration_ms`를 선언하면서 상세 페이지가 딛고 선 `trace`·`cost_metrics`·`deployment_id`는
  빠뜨렸다. 거짓 주장 둘(**`ttl` "30일 보관"인데 주 writer가 안 써서 만료 안 됨** · `GSI1`은
  절반만 채워지고 무쿼리라 그대로 짰으면 **조용히 짧은 목록**). 지키던 테스트가 **부분문자열
  존재만** 봤다 — 이 마일스톤이 적어둔 안티패턴이 **그 파일의 수호 테스트에** 있었다.
- **리포트 창(1544)**: 위 건이 연 TTL 실마리를 따라가 나왔다 — `ttl`("쓴 시각+90일")을 두
  리포트가 **시각처럼** 읽었다. 일일 SLO 필터 `ttl >= now-24h`는 만료 안 된 모든 행에 참이라
  **24시간 창이 보관 기간 전체**였고(90행 중 90 → 2), 주간은 `ttl-90일` 역산이라 상수가 바뀌면
  조용히 밀리고 **`ttl` 없는 행은 90일 과거로 떨어져 늘 누락**됐다. `created_at`으로 배치 +
  폴백 상수를 **writer AST에서 파생 검증**. **라이브 미실행**(스케줄 Lambda) — 과대집계는 추론.
- **배포 tier 발명(1552, D36)**: 이 부류의 **양층 변종** — 대시보드 NL 배포가 `environment`를
  안 보내는데 **HTTP 경계가 `"dev"`를, 매퍼가 같은 부재를 `"production"`을** 채웠다. 한 미상값에
  두 층이 서로 다른 답을 자신 있게 발명한 것. 부재를 끝까지 보존. **내 가드가 잡으려던 홀을
  자기가 갖고 있었다** — 조건부 저장(`item["k"]=v`)을 dict 리터럴 walker가 못 봐서, 그대로
  뒀으면 가드가 **버그 쪽을 편들었을** 것이다(무조건/조건부 분리로 수정).
- **배포 네임스페이스 출처(1565)**: 위 건과 **같은 축의 반대 면** — 티어는 미상이라 발명이
  틀렸고, 네임스페이스는 **실행기가 알고 있었는데 안 적었다**(`--namespace`를 정한 게 자기고
  어댑터가 돌려주기까지 했다). 그래서 하류 **네 층이 각자 `"default"`를** 채웠다: 롤백 버튼 ·
  Next 라우트 · `RollbackRequest` · 그리고 `ServiceSpec`(유일하게 정당한 곳). **라이브 kind
  3노드**: 같은 이름이 두 ns에 있으면 `rollout undo -n default`는 **실패하지 않는다** — 찾아서
  되돌리고 **성공을 보고한다, 엉뚱한 쪽을**(BEFORE default 1.28→1.27, 대상은 1.28 그대로 =
  운영자가 누른 그 서비스 / AFTER 실 배포→실 행→실 HTTP 롤백→대상만, default 무변). 승계도
  이어받게 했다 — 사라지는 게 **다음 롤백의 조준값**이라 한 번의 롤백이 다음 것을 위해
  **버그를 재장전**한다(`cost_metrics` 교훈의 날 선 판본). 그리고 **D36이 세 번째·네 번째
  경계에서 살아 있었다**: D36 가드가 두 경계를 **열거**해 롤백·트리거 라우트의
  `environment = "production"`이 남아 있었고, 파생 스윕으로 바꾸니 즉시 나왔다(교훈 ⑤의 실증).

**반복된 교훈(테스트 규율 7종)**: ①가드를 쓰면 **호출부에서** 반증하라 — 새 테스트 20건이
전부 통과하는데 호출자만 플래그를 잊은 상태였다. ②픽스처는 코드가 아니라 **실제 입력**에서
가져와라 — 내가 쓴 summary에 런북 키워드를 심어놔 유닛은 초록인데 라이브는 계속 틀렸다.
③**소비자를 단언하라, 생산자 말고** — `severity_hint`를 "설정되는가"로 봤다면 그 필드가 존재한
내내 통과했을 것이고, 그게 이 부류가 여태 살아남은 방식이다. ④**투영/스키마 계층도 소비자다**
— `ProjectionExpression`이 부르지 않은 속성은 리더가 아무리 방어적으로 짜여도 복구할 수 없다.
⑤**가드는 파생시켜라, 열거하지 말고** — 매퍼가 읽는 속성을 파싱해 Scan에 요구하면 *다음*
필드에도 실패한다. 손으로 적은 목록이었다면 당시 투영에 맞춰 쓰였을 테고 그대로 통과했다.
⑥**생산자가 여럿이면 다수결이 결함을 가린다** — 셋 중 하나만 침묵하면 나머지 둘이 그 필드가
정상이라고 계속 증명해준다. 열 번째 건은 그래서 ③(소비자를 단언하라)으로도 안 잡혔다:
소비자는 멀쩡했다. ⑦**수호 테스트 자신이 안티패턴일 수 있다** — 열한 번째 건에서 파일을
지키던 테스트가 `'GSI1PK:' in content` 식 **부분문자열 존재**만 봤다. 키워드는 모양을 못 보므로
그 파일이 얼마나 어긋나든 초록이었다. **덧붙여 내가 새로 쓴 가드도 처음엔 같은 병이었다**:
두 곳에 선언된 필드를 `re.search`로 봐서 **한 곳만 옵셔널이면 통과**했다 — `any`를 쓸 자리에
`all`이 필요했고, 반증을 돌리지 않았으면 그대로 뒀을 것이다.
스윕은 두 방향 모두 반복 가능하게 남겼다(후보≠결함) —
`scripts/find_unconsumed_fields.py`(선언됐는데 안 읽힘) ·
`scripts/find_unwritten_keys.py`(읽는데 생산자 없음).

## M12 — 멀티테넌트 Phase 3(인가 강화) 완결 + 읽기 경계 (완료, 2026-07-27~28)

**gate 1290 → 1411.** 증거 `docs/evidence/phase3-*.log` · `mcp-gateway-scope.log`.
결정 → `DECISIONS` D31·D32.

Phase 2가 "테넌트 하나의 잘못이 이웃에게 안 번지게"를 클러스터 안에서 증명했다면,
Phase 3는 **누가 무엇을 할 수 있고 볼 수 있는가**를 닫았다. 그리고 이 단계에서 나온
결함은 거의 전부 **앞문은 잠갔는데 옆문이 열려 있던** 형태였다.

- **①자격증명 격리 full**: fail-closed 가드를 `guard_scoped_action` 하나로 모으고 세 러너가
  그것을 부른다(닮은꼴 금지). `resolve_incident_scope` 이관으로 **GCP Cloud Workflows 경로의
  스코프 부재** 해소 — 디스패치 경로가 둘인데 로직이 한쪽에만 있었다. 라이브가 Phase 1a
  증명 자체의 구멍을 적발: `render_rbac`가 바인딩 대상 **ServiceAccount를 렌더하지 않아**
  RoleBinding이 없는 신원을 가리키고 있었다(fail-closed라 안 드러남 → RBAC 팔이 한 번도
  행사된 적 없음). DoD가 "Forbidden **또는** 자격증명 부재"라 약한 쪽으로 통과 중이었다.
- **②reconciler 충돌 거부**: `rollout undo`는 0을 반환하고 `resolved=True`가 기록된 뒤
  깨진 버전이 돌아온다 — out-of-band 변경이 **10초 만에** selfHeal에 되돌려짐을 먼저 실증한
  위에서 거부를 세웠다. 되돌리는 액션만 막는다(restart·scale은 desired로 수렴).
  **selfHeal pause는 채택 안 함**: Application이 `argocd` ns에 있어 테넌트 스코프
  자격증명으로 도달 불가(D32). 설계의 권장안(registry write-back)은 Phase 5 의존 —
  계획 자체의 순서 충돌.
- **③읽기 쪽 테넌트 경계**: `visibility.ts` 단일 seam(플릿 + 인시던트). 인시던트 파티션이
  막혀 있던 원인은 읽기가 아니라 **쓰기**였다 — `NormalizedIncident.tenant`가 Phase 1a부터
  있는데 기록 시점에 버려졌다. 기록 없는 행은 admin 전용, `withheld` 카운트 반환,
  캐시 `public, s-maxage` → **`private, no-store`**.
- **MCP 게이트웨이 옆문**: 모든 도구가 맨 `kubectl`을 쐈고 `kubectl_apply`는 임의 매니페스트를
  임의 ns에 썼다. Phase 1a가 executor에서 없앤 fail-open이 그대로 있었다. argv를 스코프
  kubeconfig로 고정(ContextVar — 도구 인자로 두면 **호출자가 자기 자격증명을 지명**한다),
  변경 도구는 fail-closed. 라이브: 스코프 안 ns인데도 `secrets`는 **API 서버**가 `Forbidden`.
- **테넌트 call budget**: 쿼터는 무엇을 *보유*하는지만 묶었다. sliding window, 레지스트리
  `quota.calls_per_min` 선언, 미선언=무제한(additive).
- **외부 대조**(Qwiklabs GENAI120 · GCP Architecture Center · Developers Blog): Agent Card가
  **가상 주소**와 **집행하지 않는 인증**을 광고하던 것 적발·수정. → `docs/reference/`.

**반복된 교훈**: 이 단계의 결함은 전부 **테스트가 선언을 단언해서** 살아남았다
(`assert "supportedInterfaces" in card` · `ROUTE_PROTECTION` 존재 단언 ·
"Read path remains public" 문구 고정). 값이 어디를 가리키는지, 누가 그것을 소비하는지를
묻지 않는 가드는 정책보다 오래 산다. 그리고 **가드를 쓰면 가드도 반증해야 한다** —
rate-limit 테스트 하나가 결함을 주입해도 통과했다(재시도를 시계 멈춘 순간에 해서
아무것도 단언하지 않고 있었다).

## M11 — 멀티테넌트 Phase 2 완결 (완료, 2026-07-26)

**gate 1191 → 1290.** 증거 `docs/evidence/phase2-*.log`. 설계 →
`docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5).

소프트 티어가 선언에서 **실측된 격리**가 됐다. 목적은 테넌트 하나의 잘못이 이웃에게
번지지 않게 하는 것이고, 이번 단계에서 그 경계가 네임스페이스·쿼터·데이터플레인·자격증명
네 층에서 각각 라이브로 증명됐다.

- **tenancy + Capsule**: 레지스트리가 Namespace(tenant/env/capability + PSS 라벨)·Capsule
  Tenant(`scope: Tenant` 합산 쿼터)·네임스페이스 스코프 RBAC를 렌더. 쿼터 합산은 정지
  조회로는 4배 버그로 보이고 **소비 실험만이 사실을 말한다**(`limited: 6` = 16−10).
- **⑥ 데이터플레인 격리**: 손수 관리하던 차트(데카르트 곱 16 vs 구독 6, 설치 주체 없음)를
  폐기하고 네임스페이스와 **같은 호출**에서 렌더 → 두 집합이 구성상 동일. 집행이 실험으로
  증명된 기판에만 렌더. 라이브 4종(same 통과·cross 차단·kubelet 프로브 생존·DNS 무영향).
- **push 2축 수집기 + 대시보드 스위처**: 허브는 스포크 read 자격증명 0, 신원=서명을 검증한
  키, 침묵은 UNKNOWN 강등. UI가 허브 불가/미푸시/침묵을 구분한다.
- **capability scope 축**: 클러스터 싱글턴을 테넌트별로 렌더하면 컨트롤러 둘이 같은 객체를
  조정한다(라이브에서 발생). 거부 가드는 어댑터가 아니라 **계약**에 둔다.
- **삭제 cascade + values seam**: 삭제 의미를 계약이 말하게 하고(엔진 기본값이 정반대),
  values는 복사하지 않고 가리킨다. 라이브가 **PSS restricted가 우리 애드온을 거부**
  (Argo는 Synced인데 파드 0개)하고 **구독 해지가 데이터를 파괴**(차트가 k8s 기본값을 뒤집음)
  하는 것을 잡아 둘 다 근본수정.
- **managed 경로 + DR**: faked 디스크립터로 과금 없이 `applicable=false` 증명(조회 안 한
  백엔드에 health를 단언하지 않는다). globex/dev를 실제 파괴 후 레지스트리만으로 재구축 —
  라벨 완전 동일, 채택 검증기 신설(`verify_tenancy_adoption.py`).

**반복된 교훈**: 라이브가 잡은 결함 대부분은 "테스트는 초록인데 아무 효과가 없는 코드"와
"정지 조회가 거짓말하는 상태"였다. 그리고 검증기 자신이 거짓 초록/거짓 경보를 낸 사례가
세 번 있었다(`dns-suffix`가 질의를 안 보냄 · 다른 클러스터를 broken으로 보고 · scope 누락을
fail-closed로 올려 게이트 27개 파손).

## M10 — GitAIOps 대조 7/7 + 멀티테넌트 Phase 0·1a·1b + 공급망 하드닝 (완료, 2026-07-20~26)

**gate 870 → 1191.** 상세 이력 → `PROGRESS_LOG.md`(최신 3–5건) · `docs/archive/progress-2026-07.md` ·
증거 `docs/evidence/*`. 설계 → `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5, S 93.5).

- **On-Prem 애드온 스택 IaC** Phase 1~5(ArgoCD GitOps · kube-prometheus-stack · Argo Rollouts ·
  Loki/Fluent Bit) + k3s 기판 패리티. Gateway API는 소비처 부재로 의도적 보류.
- **GitAIOps 실습서 대조 7/7**: ①Rollouts AnalysisTemplate + **에이전트 릴리스 게이트 3종 판별**
  (정상→pass / 크래시→165s auto-abort / 관측 불가→unknown) · ②OTel→Tempo + 인시던트 딥링크
  (MTTR의 82%가 로컬 LLM 추론) · ③런북 사후검증 provider 실행부 · ④권한 통제 3단 ·
  ⑤Sync Wave(Phase 1b 흡수) · ⑥NetworkPolicy 집행 + **PSS restricted · Cosign** ·
  ⑦고아 클러스터 스위퍼 + **CronJob·coverage 정직성**.
- **멀티테넌트 플랫폼**: Phase 0(레지스트리·로더·`DeliveryAdapter` 계약) · Phase 1a(자격증명이 경계 —
  `IncidentScope` + provenance 바인딩 `TokenBroker`, 라이브 RBAC `Forbidden`으로 증명) ·
  Phase 1b(argocd/flux 어댑터 2개 + 핸드오프 프리플라이트 5검사 + **rollouts-demo 소유권 TF→ArgoCD 이관 실행**).
- **런북이 선언대로 실행됨**: capability step(순서·조건·on_failure·per-step verify)을 executor가 실제 소비.
  ⚠️**단 `verify`가 실제로 도는 건 onprem뿐이다**(`executor.py:221` `if provider == "onprem"`) —
  AWS/GCP/Azure는 계획에 싣고 실행하지 않으며, 그래서 `verified`를 True가 아니라 **None(unknown)**
  으로 정직하게 보고한다(코드가 명시·가드도 있음). 2026-08-13에 **잰 것**이고, 그 전까지 이
  줄은 무조건이었다 — "과대 해석 금지"는 완료 요약에도 걸린다.

**이 마일스톤에서 반복해 나온 결함 형태 — 전부 "선언은 됐는데 소비/전달이 없음":**
`llm.endpoint`(차트에 있는데 webhook이 못 받음 → 모든 판정 unknown) · `capability_schema.steps`
(스키마에 있는데 executor가 안 읽음) · `_deserialise_decision`(steps를 직렬화 경계에서 버림) ·
`CAPABILITY_RUNBOOKS`(9런북이 죽은 데이터) · `scripts/`(이미지에 미포함) · 스위퍼 `_run_json`
(CLI 부재를 clean으로) · DynamoDB `Decimal`(rto 선언 런북 전량 탈락).
**공통점: 테스트는 선언을 검증해 초록이었고, 라이브 실행이 소비 부재를 드러냈다.**

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
