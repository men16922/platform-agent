# PROGRESS_LOG Archive — September 2026

이 파일은 `docs/PROGRESS_LOG.md`가 예산(≤120줄)을 넘길 때 밀려난 2026년 9월 이력입니다. 최신이 위.

---

## 2026-09-13 — 호출 전에 의도를 보존하고 자동 재전송을 막는다 (M74)

- Status: 실험용 단일 호출 실행권·읽기 전용 상태 조회 완료. 전체 실험의 단계 제어/원격 transport는 미연결이다.
- Changed: O_EXCL intent 생성·파일/디렉터리 fsync 후에만 sender를 호출한다. 기존 intent는 재시작/다른 operation에도 차단한다. M73 응답 기록과 receipt를 연결하며 OBSERVED는 발행 성공이 아니다. 불확실 상태를 자동으로 열지 않는다.
- Verified: 호출/수집 집중 회귀 71 passed. 실제 HTTP 8개 경쟁→1회 전송, 전송 직전/직후 자식 프로세스 사망, fsync 6개 실패 지점, 변조/불완전 기록과 새 프로세스 조회를 검증. 배타 생성/intent 기록/fsync 제거 변이 3종 검출 후 바이트 복구. 전체 게이트 2951 passed·2 skipped(2026-09-13 로컬 macOS·py3.13, +25).
- Finding: 최초 HTTP fixture는 POST 본문을 읽지 않고 연결을 닫아 간헐적 본문 손실을 일으켰다. 보존된 201/body_unavailable 기록과 재현을 확인한 뒤 fixture에서 본문을 소비하도록 수정했다. 실행기의 UNKNOWN 처리는 유지했다.
- Evidence: `docs/evidence/writer-attempt-verification-2026-09-13.json`, `docs/evidence/writer-attempt-mutations-2026-09-13.json`.
- Blockers/Next: 상위 실행기의 고정 작업 매핑·별도 관측에 따른 단계 제어가 다음이다. 실제 발행/자격증명/읽기 조정은 미연결이며 lab/PEM/checkout 보존 지시는 유지한다.

## 2026-09-13 — 실패 응답의 진단 필드만 영속 기록한다 (M73)

- Status: 제한된 오류 수집기·로컬 CLI·HTTP response adapter 완료. 원격 writer/재시도는 미연결이다.
- Changed: 고정 message 분류·허용 errors 필드·request ID만 기록한다. 본문/깊이/목록/기록 크기 제한, private 디렉터리·0600 파일·fsync·배타적 공개를 적용했다. 본문 timeout과 저장 실패를 성공으로 덮지 않는다.
- Verified: 오류/판정/출력 회귀 208 passed. 실제 loopback HTTP/HTTPError·8개 CLI 프로세스·새 프로세스 읽기·로컬 저장 장애를 검증. raw message/필드 누출·파일 공개 생략·중복 헤더 허용 변이 4종 검출 후 바이트 복구. 전체 게이트 2926 passed·2 skipped(2026-09-13 로컬 macOS·py3.13, +46).
- Finding: 깊은 JSON이 런타임 재귀 한도에 따라 파싱돼 최초 검사 1건 실패; 명시적 깊이 64 제한으로 고쳤다. 비밀 원문은 어떤 진단에도 복제하지 않는다.
- Evidence: `docs/evidence/writer-capture-verification-2026-09-13.json`, `docs/evidence/writer-capture-mutations-2026-09-13.json`.
- Blockers/Next: 과거 PR 422는 원인 미확인. 다음은 호출 전 intent·불확실 결과 중단 경계이며 lab/PEM/checkout 보존·원격 변경 경계는 유지한다.

## 2026-09-13 — preview를 저장한 뒤 제출 준비권을 한 번만 부여한다 (M72)

- Status: 로컬 preview 저장·제출 준비 API 완료. production Lambda 저장·PR writer·제출 UI는 후속이다.
- Changed: planner 내부 artifact의 전체 output을 서비스에서 저장한 후 기존 envelope를 반환한다. local adapter는 명시한 loopback DynamoDB 테이블을 필수로 사용한다. prepare API는 세션 주체와 request_id만 전달하고 CLAIMED/published=false만 반환한다.
- Verified: 집중 회귀 248 passed, dashboard production build 성공. 실제 DynamoDB Local·별도 CLI·Auth.js HTTP에서 저장 보존, 8개 소비 중 1개 성공/7개 충돌, 권한 회수·타 주체·만료·Git 변경·실제 테이블 장애를 검증했다. 저장 생략·추가 입력 허용·현재 grant 검사 생략 변이 3종 red→바이트 복구 후 green. 전체 게이트 2880 passed·2 skipped(2026-09-13 로컬 macOS·py3.13, +35).
- Evidence: `docs/evidence/registry-preview-service-local-2026-09-13.log`, `docs/evidence/registry-preview-http-2026-09-13.log`, `docs/evidence/registry-preview-service-mutations-2026-09-13.json`.
- Blockers: CLAIMED는 발행 완료가 아니며 자동 재소비하지 않는다. production 테이블/IAM·발행 방식·PR 422 원인은 미해결. 보존 lab/PEM/checkout은 그대로 두었다.
- Next: Phase 5 계획서 §12의 실패 응답 수집 계약을 오프라인으로 구현한다. 새 원격 실증/권한 확대/삭제는 포함하지 않는다.

## 2026-09-12 — 서버 변경안을 저장하고 소비권을 한 번만 부여한다 (M71)

- Status: 저장·소비 준비 계약 로컬 완료. production preview/제출 UI·PR writer에는 아직 연결하지 않았다.
- Changed: `registry_plan_store.py`에 envelope/output 바인딩·DynamoDB 조건부 생성/소비를 추가했다. 기존 현재 사용자 인가를 공유 함수로 추출하고 로컬 검증 스크립트를 추가했다. 자동 재소비·만료 lease 없음.
- Verified: 순수 artifact·기존 인가 71 passed. 실제 DynamoDB Local에서 프로세스 간 보존·8개 동시 소비 1개 성공/7개 충돌, 회수·만료·SHA 변경·변조·실제 테이블 장애 거부. CAS/소비 만료/CLAIMED TTL 조건 제거 3종 red→원본 바이트 복구 후 green. 전체 게이트 2845 passed·2 skipped(2026-09-12 로컬 macOS·py3.13, +14).
- Gate follow-up: 첫 전체 검증은 문서 문자 상한·NEXT_PLAN 숫자·신규 스크립트 출력 분류 누락 3건으로 실패했고 해당 항목을 보완했다.
- Boundary: CLAIMED는 PR 성공이 아니다. 결과 상태·불확실한 발행의 조정·서비스 배선은 후속이다. 사용자 보존 lab/PEM/checkout 변경·원격 쓰기·원본 commit/push·배포 없음.
- Next: 계획서 §12의 preview 저장 연결·제출 준비 경계. 증거 `docs/evidence/registry-plan-store-local-2026-09-12.log`, `docs/evidence/registry-plan-store-mutations-2026-09-12.json`.

## 2026-09-12 — single_file 경계를 실측하고 후속 저장 계약을 분리했다 (M70)

- Status: 네 API 호출 실측 완료, 전체 자동 PR 흐름은 미완료다. App ref 403, 운영자 진단 branch 대상 PUT 200·형제 PUT 403, draft PR 422. 정규화 CLI는 inconclusive/pr_creation_not_proven·diagnostic_only=true·sibling_boundary=supported로 종료 1이다(예상 판정).
- Changed: 새 private lab 1367338348·App 4921024·설치 161148520. 가상 YAML 두 파일, Actions off. App/설치/토큰의 정확 저장소·single_file/PR/metadata 최소 권한을 대조했다. 원본 코드·commit/push·AWS 배포 없음.
- Verified: 운영자 재조회에서 main 불변·head parent=B·acme logging 한 줄 추가·globex 불변·PR 0건. 준비 게이트 2831 passed·2 skipped(2026-09-12 로컬 macOS·py3.13, 64.32초). 원격 CI와 배포는 별도다.
- Boundary: PR 오류 본문 미수집으로 422 원인 미확인. private draft 미지원 가설은 2025-05-01 GitHub 변경 이력과 불일치한다. 브랜치 생성 실패를 PR 권한 거부로 확대하지 않는다.
- Cleanup: token revoke 204→401, uninstall 202→404·UI, App 소유자 목록 부재·설정 404. lab DELETE API 403 후 UI 삭제 중 사용자가 중단: lab과 로컬 PEM/checkout 보존, 추가 삭제 금지. 전체 정리 완료가 아니다.
- Next: Phase 5 계획서 §12의 서버 변경안 저장·소비 계약을 로컬로 구현한다. 발행 방식은 공유 레지스트리+운영자 준비 branch부터 검토하며 새 App/원격 재시도·repo 이관·권한 확대는 하지 않는다.
- Evidence: `docs/evidence/phase5-writer-live-2026-09-12.json`, `docs/evidence/phase5-writer-normalized-2026-09-12.json`, `docs/evidence/phase5-writer-followup-2026-09-12.json`.

## 2026-09-06 — P5-E 키 다운로드 차단을 확인하고 실험 자원을 정리했다 (M69)

- Status: 생성 시도·정리 완료, 실제 권한 실증은 미완료다. 사용자 재개 지시로 실행 범위를 확인했고 GitHub 본인 재인증도 통과했다. 전체 목표는 사용자 키 다운로드 인계를 기다리는 blocked 상태다.
- Changed: private lab ID 1358934947·App ID 4848286 생성, Actions off·지정 최소 권한 확인. 키 ID 4366703 생성 응답은 Chrome ERR_BLOCKED_BY_CLIENT였고 다운로드 기록 접근은 브라우저 URL 정책이 거부했다.
- Verified: App 삭제 큐 응답 뒤 소유자 App 목록과 직접 설정 404를 확인했다. lab API 삭제 403 후 동일 ID/full_name을 소유자 UI로 삭제했고 성공 화면·API 404·소유자 목록 부재를 대조했다. 설치·토큰·seed push·시험 호출·PR은 0건이다.
- Blockers: 사용자가 직접 완료할 수 있는 키 다운로드 인계가 필요하다. 권한 확대·보안 차단 우회·기존 App 재사용은 하지 않았다. 증거 `docs/evidence/phase5-writer-attempt-2026-09-06.log`.
- Next: 인계 조건이 갖춰진 뒤 §10 재실행. 그 전에는 실험 자원을 반복 생성하지 않는다. 원본 commit/push·AWS 배포 없음. 로컬 게이트는 M68의 2831 passed·2 skipped다.

## 2026-09-06 — Lambda 패키징 실패를 성공으로 덮지 않는다 (M68)

- Status: Docker bundling 실패 전파를 로컬 수정했다. 전체 `make check` **2831 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 59.28초, +5)로 통과했다.
- Changed: 마지막 || true가 필수 설치·복사 실패까지 종료 코드 0으로 만들었다. 선택적 __init__.py 복사만 괄호로 묶어 기존 선택성을 유지했다. 실제 pip와 파일 I/O로 회귀 5개를 추가했다.
- Verified: 변경 전 requirements 없음에서 exit 0·출력 0파일, 신규 3 failed·2 passed → 수정 후 5 passed. 공식 Lambda Python 3.11.16/aarch64에서 정상 패키징과 네트워크 없는 핸들러 13개 import/callable 검증 성공. AWS 호출·배포 검증은 아니다.
- Boundary: host local bundler의 플랫폼 선택과 실제 서비스 동작은 별도 검증이다. 증거 `docs/evidence/incident-lambda-bundling-2026-09-06.log`.
- Next: 사용자의 재개 지시로 P5-E 원격 범위는 확인했다. 새 Chrome 등록 탭의 Confirm access 본인 재인증을 기다린다. 원본 commit/push·원격 변경 없음.

## 2026-09-06 — CDK 기본 앱의 숨은 전역 도구 의존성을 제거했다 (M67)

- Status: 실제 CDK 앱 진입점의 의존성 누락을 재현하고 로컬 수정했다. 체크포인트 반영 후 전체 `make check` **2826 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 56.49초, +1)로 완료했다.
- Changed: 기본 app 명령이 쓰는 ts-node ^10.9.2를 devDependency·lockfile에 추가했다. 실제 cdk.json 앱을 제한된 PATH·빈 npm 캐시·offline 설정으로 실행하는 회귀 1개를 추가했다. source-map-support는 ts-node의 호환 경로로 동작하므로 별도 변경하지 않았다.
- Verified: 변경 전 Node 22 npm run synth는 ts-node 다운로드에서 ENOTCACHED, 변경 후에는 Lambda bundling까지 진입했다. 앱 bundling을 끈 별도 기본 진입점 검사로 새 Linux npm ci 후 98개 리소스 합성 성공, 호스트 회귀 1 failed → 1 passed. npm audit 0건. 첫 전체 게이트는 M67 요약 누락으로 문서 연결 2개 실패(2824 passed, 2 skipped).
- Boundary: Node 전용 컨테이너는 pip·Docker가 없어 실제 Lambda 패키징까지 검증하지 않았다. 합성 결과를 원격 배포 증거로 읽지 않는다. 증거 `docs/evidence/cdk-app-entrypoint-2026-09-06.log`.
- Next: P5-E 재인증·원격 실행 범위 확인은 대기 중이다. 원본 commit/push·원격 변경 없음.

## 2026-09-06 — 새 Linux 환경 검증과 npm 보안 의존성 갱신 (M66)

- Status: M61의 신선한 의존성 설치 검증을 로컬 Linux/Node 22에서 보완하고 두 lockfile을 갱신했다. 원격 GitHub CI 결과는 별도다.
- Changed: 기존 package.json 범위 안에서 browserslist 4.28.9·aws-cdk-lib 2.268.0·CDK CLI 2.1140.0으로 갱신했다. 신규 assembly schema 54를 기존 CLI가 거부해 CLI도 맞췄다. 혼합 WIP와 기존 manifest를 보존했다.
- Verified: 초기/갱신 후 깨끗한 npm ci 성공, Linux·Node 22.23.2·py3.13.15의 CI selector 검사 각각 **69 passed, 0 skipped**. npm audit high dashboard 1·stacks 3 → 각각 0건, dashboard production build 통과. 원본 전체 `make check` **2825 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 55.56초, 테스트 증감 0).
- Boundary: 실제 CDK context로 98개 리소스를 비교하면 seed provider의 Node 22→24와 S3Key 두 필드만 다르다. 앱 Lambda bundling은 비활성화했으므로 패키징·배포 검증은 아니다. 증거 `docs/evidence/ci-node22-lockfile-refresh-2026-09-06.log`.
- Next: P5-E 사용자 재인증·원격 실행 범위 확인은 대기 중이다. 기존 등록 탭은 닫혔으며 인증 완료는 미확인이다. 원본 commit/push·원격 쓰기 없음.

## 2026-09-06 — P5-E 실행안을 대조하고 모순된 JSON 성공 판정을 막았다 (M65)

- Status: 원격 실증 변경안의 읽기 검토와 로컬 입력 검증 보완 완료. 전체 게이트 검증도 완료했으며 원격 생성/권한 부여는 미실행이다.
- Changed: Python의 True==1·float==int 비교로 줄 수/저장소 ID를 오인하던 경로를 고쳤다. 중복 JSON 키·NaN/Infinity는 파일 입력 오류다. 정확 원격 변경 범위를 `experiments/phase5-writer/execution-review.md`에 정리했다.
- Verified: 변경 전 신규 12 failed → 판정기 **116 passed**, 변이 5종 검출·바이트 복구. 실제 gh 소유 저장소 목록과 GitHub App 설정 UI에서 lab/App 미관측, API 버전 지원 확인. 404만으로 이름 사용 가능을 단정하지 않았다. 전체 `make check` **2825 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 54.14초).
- Blockers: App 등록 URL은 GitHub Confirm access 재인증에 멈췄다. 사용자 인증과 계획서 §10의 원격 생성·설치·시험·정리 범위 확인이 남았다. 토큰/자격증명은 읽거나 출력하지 않았다.
- Next: 열린 Chrome에서 사용자 재인증 후 실행 검토안의 정확 원격 범위 확인. 증거 `docs/evidence/phase5-writer-execution-review-2026-09-06.log`. 목표는 진행 중이며 commit/push·원격 변경 없음.

## 2026-09-06 — P5-E 증거를 성공·진단 전용·판정 불가로 구분한다 (M64)

- Status: P5-E 결과 판정기와 JSON CLI를 로컬 구현했다. 로컬 구현·전체 게이트 검증 완료이며 원격 실증 완료는 아니다.
- Changed: 최소 신원/권한·실제 요청 필드·ref/parent/tree/main·형제 불변·PR 작성 App/파일 목록을 대조한다. 진단 branch는 diagnostic_only를 유지하고 401/409/422/429/5xx/timeout을 거부 증거로 세지 않는다. 입력 정규화 계약·합성 예제·CLI 종료 코드를 문서화했다.
- Verified: 관련 **104 passed**, 변이 8종 검출·소스 바이트 복구. 처음 parent 가드 삭제를 놓쳐 후속 snapshot 모두 같은 잘못된 parent를 갖도록 회귀를 보완했다. CLI 실제 subprocess의 JSON stdout·실패 코드·입력 오류 비노출을 확인했다. 전체 `make check` **2813 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 52.99초).
- Blockers: 로컬 판정에는 없음. 입력 증거 출처/실제 토큰·원격 API 호출·정리 완료는 검증하지 않으며 live_verified는 항상 false다.
- Next: 계획서 §10의 P5-E App/lab 생성·설치·네 호출·정리 범위 검토. 증거 `docs/evidence/phase5-writer-judge-2026-09-06.log`. 혼합 WIP 보존, commit/push·원격 변경 없음.

## 2026-09-06 — preview 스트림의 거부 응답과 reader 정리를 보장했다 (M63)

- Status: 다음 로컬 우선순위인 preview 스트림 경계 회귀를 구현했다. 원본 혼합 WIP를 보존하면서 구현·전체 게이트 검증을 완료했다.
- Changed: 누적 4 KiB 초과 시 취소 완료를 기다리지 않고 413을 반환한다. 취소 거부도 413을 덮지 못한다. 읽기 실패를 422로 정규화하고 finally에서 reader 잠금을 해제한다.
- Verified: 실제 Node Request/ReadableStream으로 신규 13개 중 변경 전 12 failed·1 passed, 수정 후 preview 전체 **46 passed**. 정확 4096바이트 허용·4097 거부, 청크 누적/헤더 위조/미소비 tail, 취소 실패·미완료, 빈 본문·잘못된 JSON/UTF-8·읽기 실패를 검사했다. 변이 6종 검출·바이트 복구 후 `make check` **2709 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 53.10초).
- Blockers: 로컬 계약 수정에는 없음. 원격 CI/배포 및 실제 HTTP 업로드·호스팅 시간 제한은 이번 검증 범위 밖이다.
- Next: P5-E 결과 판정기(계획서 §10의 API 응답·변경 전후 SHA 판정, 오프라인 fixture). 증거 `docs/evidence/preview-stream-boundaries-2026-09-06.log`. commit/push·원격 자원 변경 없음.

## 2026-09-06 — overnight 독립 검수와 실제 fixture 회귀 보완 (M62)

- Status: M61 결과 diff만 원본 WIP에 반영했다. 별도 import 제거 두 건은 보존했다. 격리 branch의 결과 커밋은 유지하며 원본은 미커밋이다.
- Changed: 호출 문자열 검사 대신 실제 두 fixture의 compiler/node 누락과 로컬/CI/GITHUB_ACTIONS 조합을 실행한다. CI의 잘못된 skip은 실패로 판정한다. M61 실행·커밋 기록과 workflow 주석을 정정하고 완료 seed를 제거했다.
- Verified: 격리 HEAD `2e81799`의 독립 `make check` **2686 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, 51.44초). 보완 가드 **17 passed**. 호출을 주석만 남기고 bare skip으로 되돌린 변이는 기존 7개에서 초록이었다. 보완 후 같은 변이와 CI/GITHUB_ACTIONS 분기 삭제 변이를 검출했다. 원본 최종 `make check` **2696 passed, 2 skipped**(49.76초). 첫 원본 게이트의 문서 숫자 불일치 1건을 세 문서에서 갱신한 뒤 통과했다.
- Blockers: 로컬 후속 수정에는 없음. 새 러너 npm ci·원격 CI·P5-E 자격증명 실증은 미검증이다.
- Next: preview 스트림 경계 회귀·P5-E 결과 판정기는 미등록 후보다. 증거 `docs/evidence/overnight-review-followup-2026-09-06.log`. push·배포·원격 자원 변경 없음.

## 2026-09-06 — CI가 TS/CDK 계약을 skip으로 숨기지 못하게 막았다 (M61)

- Status: 격리 worktree에서 overnight로 완료. 구현 커밋 `2e81799`, 2회차 후 DONE(drained). 원본 혼합 WIP는 별도로 보존했다.
- Changed: `gate.yml`에 `actions/setup-node`(Node 22, 두 lockfile 캐시) + `npm ci` 두 스텝 추가. `tests/_ts_toolchain.py`(신규)가 `require_ts_toolchain`을 제공하고, `test_registry_preview_ui.py`·`test_registry_planner_stack.py`가 bare `pytest.skip` 대신 이를 호출해 `CI`/`GITHUB_ACTIONS`에서는 skip 대신 fail한다.
- Verified: `tests/test_ci_ts_dependency_guard.py`(신규 7)로 가드 자체 동작과 두 계약 파일의 호출 문자열을 검사(실제 fixture 연결 검증은 M62에서 보완). 로컬에 이미 있던 `dashboard`·`src/stacks`의 `node_modules`로 TS 계약·CDK 합성이 변경 전후 모두 실제로 통과함을 확인(스킵 아님). 전체 `make check` **2686 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13, +7).
- Blockers: 이 수정에는 없음. `npm ci`가 신선한 ubuntu 러너에서 실제로 성공하는지, 실제 원격 CI 실행 결과는 검증하지 않았다 — 이번 범위에서 의도적으로 제외.
- Next: 후보는 preview 스트림 경계 회귀·P5-E 결과 판정기(아직 `[auto]` 미등록). 증거 `docs/evidence/ci-ts-cdk-dependency-guard-2026-09-06.log`. 격리 branch에 로컬 커밋 1개를 만들었고 push/배포/P5-E 자원 생성은 없다.

## 2026-09-05 — P5-A: 같은 SHA의 스냅샷과 한 파일 변경안 (M55)

- Status: 오프라인 진입 함수 `plan_snapshot()` 구현 완료. 다음은 P5-B 쓰기 grant 판정이다.
- Changed: 요청 필드 4개만 허용, 고정 commit/path/blob 검증, 크기·UTF-8·YAML 검증, 요청별 임시 파일, canonical diff와 주체·revision·출력 digest를 구현했다. 실제 I/O는 주입되는 읽기 어댑터 경계다.
- Found: M53의 두 파일 실증은 `values_for()`가 호스트 파일을 추가로 읽었다. 호스트 경로를 끊자 실패했다. 대상 Helm values를 같은 SHA로 읽고 `values_repo_root`를 명시해 설치 가능성 검사를 유지했다. D52·계획서·lesson의 잘못된 근거를 정정했다.
- Verified: 실제 파일 세 개로 입력 불변·호스트 의존성 차단·결정적 출력, 잘못된 요청·변조·형제 tenant/env 변경 거부. 관련 테스트 **130 passed**. `make check` **2534 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 45.96초). 변이 **8종 red** → 소스 바이트 복구. 첫 변이에서 빠진 잘못된 환경의 한 줄 삽입 사례를 보강했다.
- Blockers: P5-A에는 없음. 인증·현재 grant·계획 저장·제출 시 만료/revision 검증은 후속 작업이다. digest는 서명이 아니다. 네트워크·자격증명·UI·배포·commit/PR 생성은 실행하지 않았다.
- Next: `docs/plans/2026-09-05-phase5-planner-runtime.md` P5-B. 증거 `docs/evidence/phase5-snapshot-planner-2026-09-05.log`.

## 2026-09-05 — Phase 5 실행 위치를 정하고 GCP 사용액을 다시 쟀다 (M53·M54)

- Status: Phase 5 설계·로컬 실증 완료(D52), GCP 재측정 완료. 런타임 코드 변경·원격 자원 생성 없음.
- Changed: 독립 Python Lambda를 선택하고 snapshot/인가/PR writer 계약과 P5-A~F를 계획서에 기록했다. FastAPI/Python 부재라는 옛 근거를 교체했고, 다음 `[auto]`는 P5-A다.
- Verified: 기존 플래너가 catalog와 대상 tenant 파일 둘만으로 실행됐다. git 실행·network 금지, 입력 불변. 기존 쓰기 테스트 **25 passed**. `make check` **2429 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 41.97초).
- Verified: GCP 이 프로젝트 사용액 **₩14.80** − PROMOTION **₩12.36** − 기타 크레딧 **₩2.44** → 청구 **≈₩0**. export 3,053행. 일별 서비스 구성이 달라 **월액을 추정하지 않았다**. AWS CE 0회·BQ SELECT 3회.
- Blockers: UI·원격 배포·자동 PR은 미구현. GitHub single_file 권한은 존재하지만 branch 생성까지 tenant 한 곳으로 제한되는지는 미증명이다. Phase 4b의 상시 운영 요금·기간·종료 장치는 여전히 선행 조건이다.
- Next: `docs/plans/2026-09-05-phase5-planner-runtime.md` **P5-A**. 상세 증거는 M53·M54가 가리키는 로그에 있다.

## 2026-09-05 — 문서 가드 세 가지와 STATUS 줄 여유: 열린 씨앗 네 건 완료 (M52)

- Status: `[auto]` 네 건 완료. 런타임·클라우드 변경 없음. 다음 우선순위는 `NEXT_PLAN`에 기록했다.
- Changed: Markdown 경로(진입점 6개)·D번호(진입점 3개)·문자 예산 유일 표기(archive 포함) 가드 **16개**. 숫자 복제는 계획의 archive 4곳보다 넓었다 — **9개 문서 21건**을 설정 참조로 바꿨다.
- Changed: `STATUS` 기존 본문을 **119→99줄**로 병합(공백 정규화 동일), 체크포인트 증분을 더해도 완료 기준 이내. 기존 로그 하단 두 건은 월별 archive로 그대로 이동했다. 이전 NEXT SESSION 전문도 brief archive에 보존했다.
- Verified: **변이 19종 전부 red**, 바이트 복구 후 새 가드 **16 passed**. 첫 전체 게이트는 **2425 passed, 2 skipped, 1 failed** — 새 테스트 수를 반영하기 전 게이트 숫자 가드만 실패했다. 최종 `make check` **2429 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 42.53초).
- Changed: 기존 날짜 가드가 미래 예정일을 완료 기록으로 읽어 진입점 세 개를 오탐했다. `예정: YYYY-MM-DD` 토큰만 구분하고 같은 줄의 완료일은 계속 검사한다(+3). 변이 2종 red → 바이트 복구 후 날짜 가드 12 passed.
- Learned: 예산 선언을 넓게 찾으면 `Status: 09-02`의 날짜·여유 글자 수도 상한으로 오인한다. 실제 선언과 실측 수치를 구분하는 회귀 사례를 추가했다.
- Blockers: 이 네 건에는 없음. Phase 4b는 billable·별 승인, Phase 5는 플래너 실행 위치 결정 선행. **이번에 CI·클라우드 라이브 조회는 하지 않았다.**
- Next: **예정: 2026-09-06 이후 GCP만 `report_gcp()` 재측정** — 창·특이 지출·프로젝트 범위를 먼저 판정한다. 7일 경과만으로 월 런레이트를 확정하지 않는다.

## 2026-09-02 — `MEASURABLE`이 금액을 대신 묻는다: 첫 가드는 한 글자 때문에 변이를 놓쳤다 (gate 2407)

- Status: 브리프가 지목한 다음 행동 — 설정문서 §4가 *"데이터가 생기면 그때 붙인다"*로 미뤄 둔 분기. **완결**, M50. 권위 `docs/evidence/the-guard-let-the-mutation-through-because-of-one-character.log`.
- Changed(`scripts/probe_cloud_spend.py`): `MEASURABLE`이 **질의를 돌린다**(`_export_sql`/`_export_spend`/`_print_gcp_amounts` 신설, `bq show`는 `_table_meta` 한 곳으로). 인쇄는 프로젝트별 **총사용액·PROMOTION·기타크레딧·청구** 넷 + 창 + 스캔 바이트.
- Changed(**크레딧을 한 컬럼으로 합치지 않았다**): 프로모션은 **마르는 잔액**이고 `DISCOUNT`는 **요율의 성질**인데, 합치면 화면이 똑같아지고 독자는 *"GCP는 싸다"*로 읽는다 — **잔액이 다할 때까지만 참인 문장**이다. 질의가 `= 'PROMOTION'`과 `!= 'PROMOTION'`을 따로 센다.
- Verified(**⚠️첫 가드가 그 변이를 통과시켰다 — 한 글자다**): `"= 'PROMOTION'" in sql`은 **`!= 'PROMOTION'`에도 참**이라, promo 컬럼을 전 크레딧으로 넓혀도 **남은 반쪽이 사라진 반쪽 대신 답했다**. 부등호를 가르는 lookbehind로 고쳤다. **M48의 접두 매칭 함정과 같은 계열**(Risk 12④) — 이번에도 가드가 **제 창문**에 물고 있었다.
- Verified(**⚠️프로브가 제가 경고하는 오독을 하고 있었다**): 첫 판이 인쇄한 창은 `2026-08-01 ~ 2026-09-02` — **한 달**이다. 그 08-01은 `project`가 없는 **Invoice 행 하나**이고 실사용은 08-30부터다(**M49 ⓑ가 적은 바로 그 행**). ⇒ 창은 **계정 수준 행을 뺀** 사용 행에서만 잰다: `08-30 ~ 09-02 (729행, 계정 수준 1행 제외)`. **경고를 문서에 적는 것과 도구가 그 함정을 피하는 것은 다른 일이다.**
- Verified(**안 하는 쪽도 정했다**): 질의 실패는 **0이 아니라** *"직접 물어볼 것"* + 붙여넣을 명령 · `--project_id`를 넘긴다(없으면 **다른 프로젝트에 과금**, 09-01 실측) · **스캔 바이트를 인쇄한다** — 이 프로브에서 **유일하게 과금되는 호출**이고, CE가 청구서의 84%가 된 방식이 *"반복해서 물은 것"*이다.
- Verified: `make check` **2407 passed + 2 skipped**(2397 → **+10**), 실패 0. **변이 12종 전부 red**. 변이·실행·복구는 한 스크립트, **복구는 바이트 사본에서**(Risk 12⑦). 라이브 확인은 **`report_gcp()` 직접 호출**(BQ 질의 1건 ~40KB) — **AWS CE 0건**.
- Changed(`docs/AGENT_BRIEF.md`): 7,265→**6,935자**. 증분 내역의 산문(M40~M48 열거)을 접었다 — **`STATUS` Baseline이 이미 권위**이고 브리프가 복제하고 있었다. ⚠️중간에 **7,200 정확히**에 앉았는데, 직전 세션이 *"7,199는 통과였지 여유가 아니었다"*를 적어 둔 그 자리라 더 접었다.
- Blockers: 없음.
- Next: **며칠 뒤 `make spend-check`를 그냥 돌려 볼 것** — 창이 3일→7일이 되면 런레이트가 가정 없이 나온다. ⚠️단 `spend-check` 전체는 **AWS CE $0.01**을 문다(GCP만 보려면 `report_gcp()` 직접 호출).

## 2026-09-02 — 적재가 도착했다: 그런데 ₩0은 요율이 아니라 프로모션 크레딧이었다 (gate 2397)

- Status: 사람의 다음 수(▶ NEXT SESSION 첫 행동) — GCP 내보내기 테이블 `numRows` 판정. **완결**, M49. 권위 `docs/evidence/the-gcp-zero-is-a-promotion-credit-not-a-rate.log`.
- Verified(**판정: 0이 아니다**): `numRows` **730**(422,688바이트 · `lastModifiedTime` 09-02 06:29:40Z, 생성은 09-01 01:53:42Z). 프로브의 GCP 분기를 직접 불러 **`MEASURABLE`** 확인 — `EXPORTED_EMPTY`에서 넘어갔다(M46이 만든 넷째 상태가 제 일을 했다). 2026-07 이래 열려 있던 *"GCP 실지출은 못 읽는다"*가 닫혔다.
- Verified(**⚠️₩0의 정체 — 요율이 아니다**): 총사용액 **₩67.87** → 청구 **≈₩0**인데, 상쇄의 **99.4%(₩67.4773)**가 `FreeTrialUpgrade:…` **`type=PROMOTION`**이고 티어성 `DISCOUNT`는 **₩0.39**뿐이다. **AMP와 같은 계열의 반대 방향** — 거기선 절벽이 요율→**한도**였고 여기선 **크레딧 잔액**이다. ⛔*"GCP는 어차피 공짜"*로 요약 금지. **소진 시점은 내보내기가 말해 주지 않는다.**
- Verified(**⚠️월별 집계 하나만 봤으면 없는 백필을 적을 뻔했다**): `invoice.month=202608`이 310행에 `first_usage 2026-08-01 07:00`이라 **한 달치 백필로 읽혔다**. **일별로 가르니** 08-01은 **1행**이고 `project=null`인 **Invoice 행**이다 — 실제 사용은 **08-30부터**(41→124→548→16). ⇒ 설정 문서 **§0("소급 적용 안 됨")은 성립한다**. **집계 축을 하나만 보면 없는 것이 보인다.**
- Verified(**⚠️월 런레이트는 아직 못 잰다 — 곱하지 않았다**): 창이 **3일**이고 마지막 날은 안 찼으며 총액의 **81%가 하루치 4행**(`claude-study-501117` Cloud Storage ₩54.90, 09-01에만). 30을 곱하면 **가정이 총액을 지배**한다(4a 추정표가 100배 틀렸던 그 모양). **며칠 뒤 다시 묻는 것이 무료인 다음 측정이다.**
- Verified(**⚠️총액의 90%는 다른 프로젝트 것**): 결제계정에 프로젝트 **5개**, 비용 행이 있는 건 **3개**(`claude-study-501117` ₩59.27 · **platform-agent의 `project-ec7809f7…` ₩6.55** · `warranty-hack` ₩2.05, `gen-lang-client-*` 둘은 0행). 브리프의 *"0행은 ₩0이 아니다 — 프로젝트 5개"*가 답을 얻었다. **결제계정 총액을 이 레포 비용으로 읽으면 10배 틀린다.**
- Verified(**안 한 것도 측정이다**): **AWS Cost Explorer 호출 0건** — `make spend-check` 전체는 CE **$0.01**을 물어서 GCP 분기만 직접 불렀다. `bq show`는 메타데이터라 스캔 **0바이트**, 질의 5건 합계 **~250KB**(무료 티어 1TB/월). **증거 로그는 손으로 옮기지 않고 명령 출력을 그대로 받았다.**
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 측정과 문서만 바뀌었다).
- Blockers: 없음.
- Next: **며칠 뒤 같은 질의를 다시**(무료) — 창이 3일→7일이 되면 런레이트가 가정 없이 나온다. 그리고 `GCP_BILLING_EXPORT_SETUP.md` **§4가 예고한 것**(*"데이터가 생기면 그때 붙인다"*)이 이제 조건을 만족한다 — `spend-check`의 `MEASURABLE` 분기가 **금액을 대신 물어 주게** 할 수 있고, ⚠️그때 **`cost`만 더하면 안 된다**(위 ⓐ가 그 이유다).

## 2026-09-02 — AGENT_BRIEF도 접었다: 7,199자는 통과였지 여유가 아니었다 (gate 2397)

- Status: overnight `[auto]` 1건 — `docs/AGENT_BRIEF.md`를 문자 예산 90% 이하로. **완결**(7,606 → **7,049자** = 예산의 **88.1%** · 58줄/60). 압축 씨앗 셋(STATUS·NEXT_PLAN·BRIEF)이 다 닫혔다.
- Changed(신규 `docs/archive/brief-detail-2026-09.md`): 닫힌 항목 여섯(ⓐ·ⓒ·`rollback_release`·런북 walk ②·`slack_live_approval`·`triggered_at`) · 직전 세션 09-01 전문 + **배운 것 둘** · **▶ NEXT SESSION의 09-01 세 결함**. 줄은 **줄 번호로**, 문단은 **마커로** 잘라 **스크립트가 복사**했다 — 손으로 옮기지 않았다(09-02 STATUS 압축의 그 교훈).
- Changed(`docs/AGENT_BRIEF.md`): 네 자리를 **주장 한 줄 + archive 지목**으로 접었다. ▶ NEXT SESSION의 **첫 행동은 건드리지 않았다** — `/sync`가 그 줄을 제일 먼저 그대로 읽는다.
- Verified(**첫 판은 7,199/7,200이었다 — 한 글자**): 기준은 통과했지만 다음 세션이 한 문장만 더해도 red다. 그래서 **가장 긴 줄**(1,058자 = 파일의 15%, 문자 예산 가드가 애초에 겨눈 그 병리)을 한 번 더 접었다 ⇒ **7,049자 · 최장 줄 908**.
- Verified(**삭제 0을 두 축으로 물었고 둘 다 제 창문에 걸렸다**): ⓐ ⚠️/⛔/✅ **33조각** · ⓑ `·`·줄 **83조각** → **6건이 "없다"**로 나왔는데 전부 **이음매 artifact**였다. 조각이 내가 자른 자리를 가로지르면 앞은 archive에, 뒤는 브리프에 있어 **통짜로는 안 맞는다**. 꼬리를 떼어 따로 물어 5건 생존 확인.
- Verified(**남은 1건이 진짜 함정**): 1,659자 조각이 `LOST`로 나온 원인은 삭제가 아니라 **내가 헤더에 두 줄을 끼워 넣어 연속성이 깨진 것**이었다. 꼬리를 **줄 단위로** 다시 물으니 15줄 **0 missing**. ⚠️**연속성은 불변식이 아니다 — 생존이 불변식이다**(대조기를 안 고쳤으면 없는 결함을 되돌릴 뻔했다).
- Verified(**옮긴 것은 바이트로 물었다**): line5 슬라이스 **344자** · 줄 11(496) · 12(179) · 18(520) 넷 다 archive에 **byte-identical**. 옛 브리프 **전 줄 스윕**에서 verbatim이 아닌 줄은 **접은 line5 하나뿐**.
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 문서만 바뀌었다). 가드 초록: 문자 7,049 ≤ config의 brief 상한 · 줄 58 ≤ 60 · 게이트 숫자 정확히 1회 · 인용 M번호 전부 M0~M48 안 · `COMPLETED_SUMMARY` **M10~M46** 범위 유지 · 모델명(`Qwen3-Coder-30B`)·`$0.00`+`Always Free` 캐리어 유지.
- Verified(**안 한 것도 측정이다**): brief 예산 숫자를 브리프에도 archive에도 **적지 않았다** — `harness-config.json`이 유일한 표기이고 **네 번째 표기가 드리프트**다(M19). ⚠️`next-plan-detail`은 plan 상한을 숫자로 복제하고 있었다(선행 사례, 이번 범위 밖).
- Blockers: 없음.
- Next: **`[auto]` 씨앗이 말랐다** — 다음 이터는 **DONE(drained)**이다. 사람의 다음 수는 여전히 **GCP 내보내기 테이블 `numRows`**(`bq show --format=json <table>`, 무료). ⚠️**브리프에 남은 여유는 151자**다 — 다음에 한 문장을 더하려면 그만큼 접어야 한다.

## 2026-09-02 — NEXT_PLAN도 접었다 · 한 줄이 조용히 날짜 하나를 잃었다 (gate 2397)

- Status: overnight `[auto]` 1건 — `docs/NEXT_PLAN.md`를 문자 예산 90% 이하로. **완결**(10,777 → **8,003자**, 목표 9,900의 81% · 줄 117 → **112**).
- Changed(신규 `docs/archive/next-plan-detail-2026-09.md`): 닫힌 항목 여덟과 열린 항목 넷의 경위·측정·⚠️/⛔ 전문. **파일을 손으로 쓰지 않고 옛 NEXT_PLAN의 줄 범위를 스크립트로 복사**했다 — 09-02 STATUS 압축이 *"압축은 재작성이고 재작성은 조용히 지운다"*를 남겼으니, **바이트 동일성은 손이 아니라 도구에게** 맡겼다.
- Changed(`docs/NEXT_PLAN.md`): 열린 `[ ]` 항목은 **전부 그대로 열려 있고**(수 변화 0), 닫힌 ⛔ 여덟은 **한 줄 목록**으로 접었다. 헤더가 archive를 **권위로 지목**하고 *"요약만 읽고 결론 내지 말 것"*을 적는다.
- Verified(**삭제 0을 두 번 다르게 물었다**): ⓐ ⚠️/⛔/✅ 마커 **55조각** 전수 대조 — 0 missing. ⓑ **옛 파일의 모든 줄**(≥12자)이 새 NEXT_PLAN+archive에 남아 있는지 — 여기서 **ⓐ가 못 본 것 하나**가 나왔다.
- Verified(**⚠️마커 검사만 했으면 놓쳤다**): Azure Foundry 줄에서 **`(08-12)`가 사라져 있었다** — ₩6,600을 **언제 잰 값인지**가 빠진 것이고, 그 줄엔 마커가 없어 ⓐ의 55조각에 애초에 들어오지 않았다. **가드는 자기 창문 밖을 못 본다**(Risk 12④) — 전수 줄 대조가 그 창문을 넓힌 쪽이다. 복원했다.
- Verified(**첫 판은 글자 예산을 통과하며 줄 예산을 깼다**): 8,028자(≤9,900 ✓)인데 **133줄**(>120 ✗). 두 예산은 **반대 방향으로 당긴다** — 문단을 넓히면 줄이 줄고 글자는 그대로다. 인접 줄을 쌍으로 이어 112줄, 최대 줄 **179자**(브리프를 만든 3,621자 병리와는 다른 자리).
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 문서만 바뀌었다). 예산 가드 넷 초록: 문자 8,003 ≤ config의 plan 상한 · 줄 112 ≤ 120 · 게이트 숫자 `gate 2397` **정확히 1회** · 인용한 M번호 전부 `COMPLETED_SUMMARY` M0~M48 안.
- Changed(`docs/PROGRESS_LOG.md`): 이 항목을 넣을 자리가 없어(11,772자 / config의 log 상한) 09-01 두 건(비용체크 · 지운 뒤에도)을 `docs/archive/progress-2026-09.md`로 **옮겼다**. 순서는 git 이력으로 확인했다(정적검사 D51 < 지운뒤에도 < 비용체크).
- Blockers: 없음.
- Next: **GCP 내보내기 테이블 `numRows`** — 판정 시점(09-02 01:11Z)이 지났다. `bq show --format=json <table>`(무료). 0이면 그때가 문제다. 남은 `[auto]`는 **`AGENT_BRIEF` 압축 하나**(7,606 → ≤7,200)이고 ⚠️**거기는 줄 예산이 60이라 이번 함정이 더 좁다**.

## 2026-09-02 — STATUS를 반으로 접었다: 옮긴 것이지 지운 게 아니다 (gate 2397)

- Status: overnight `[auto]` 1건 — `docs/STATUS.md`를 문자 예산 90% 이하로. **완결**(10,994 → **5,197자**, config의 status 상한 대비 47%).
- Changed(신규 `docs/archive/status-baseline-2026-09.md`): 09-01~09-02의 baseline 줄 여덟(2392·2381·2368·2358·2350·2346·2342·2339) **전문 그대로**. 최신 줄(2397)만 STATUS에 남겼다 — **게이트 숫자 가드가 거기서 읽는다**.
- Changed(신규 `docs/archive/status-risk-detail-2026-09.md`): Active Focus와 Risk 1~12의 경위·측정·⚠️/⛔ 문장. **위험 번호는 STATUS와 같은 번호**다 — 번호가 갈리면 두 문서가 다른 목록이 된다.
- Changed(`docs/STATUS.md`): 주장 한 줄 + 재개 조건만 남겼다. 헤더가 archive 둘을 **권위로** 지목하고 *"요약만 읽고 결론 내지 말 것"*을 적는다.
- Verified(**삭제 0을 기계로 물었다**): 옛 STATUS를 `⚠️`/`⛔`로 쪼개 **48조각**을 새 STATUS + archive 셋에 대조 — **전부 남아 있다**. ⚠️첫 판에서 한 조각(*"같은 계열이 08-15에 재발했고 D49가 일반화해 집행"*)이 실제로 빠져 있었고, 그건 내가 그 줄을 **옮기지 않고 다시 쓴** 자리였다 — **압축은 재작성이고 재작성은 조용히 지운다**. 전문으로 되돌렸다.
- Verified: `make check` **2397 passed + 2 skipped**(변동 0 — 문서만 바뀌었다). 예산 가드 넷 초록: 문자 5,197 ≤ config의 status 상한 · 줄 96 ≤ 120 · 게이트 숫자 2397 세 문서 일치 · M0~M45 범위 실존.
- Verified(**⚠️예산의 단위는 바이트가 아니다**): `wc -c`는 8,354를 말하고 가드는 5,197을 말한다 — 한글이 UTF-8에서 3바이트다. `wc`로 재면 **예산 초과로 착각한다**. 가드가 쓰는 건 `len(read_text())`다.
- Blockers: 없음.
- Next(⚠️**이건 이득만은 아니다**): 옮긴 절반은 `/sync` 읽기 경로(brief→status→plan→log)에 **없다** — 다음 세션의 기본 문맥에서 빠진다. 그게 압축의 대가고, 그래서 STATUS 헤더가 archive를 권위로 **지목만** 하고 요약하지 않는다. 남은 `[auto]` 둘(NEXT_PLAN 10,797 · AGENT_BRIEF 7,606)도 **같은 함정**이다.

## 2026-09-02 — 인쇄된 경로도 주장이다: 39개를 전수로 물었고 0개가 dangling이었다 (gate 2397)

- Status: overnight `[auto]` 1건 — M46이 남긴 교훈("인쇄된 지시도 주장이다")을 가드로 만들었다. **완결**, M48. 권위 `docs/evidence/the-printed-path-was-a-claim-nobody-checked.log`.
- Changed(`tests/test_script_printed_paths_resolve.py`, 신규): `scripts/*.py`의 **문자열 리터럴 속 레포-상대 경로 전수**가 레포에 실존하는지 묻는다. 앵커(top-level 디렉터리)는 **git에서 유도**해 새 디렉터리가 생기면 그날 스윕된다.
- Verified(**쓰기 전에 쟀다**): 23 스크립트 · **39개**(distinct) · 그중 **stdout에 닿는 것 4개** · **dangling 0**. 초록에서 시작하는 가드지 청소 과제가 아니다.
- Verified(**존재는 git에게 물었다, 이 노트북이 아니라**): `pathlib.exists()`면 여기선 초록, CI에선 red다 — `src/stacks/node_modules`가 디스크엔 있고 `.gitignore:16`에 있다. 불변식은 *"레포가 담고 있다"*지 *"내 파일시스템에 있다"*가 아니다(Risk 12②). 변이 3이 이걸 직접 태운다.
- Verified(**첫 판이 false red를 냈고, 면제 목록으로 덮지 않았다**): `probe_scope_reachability.py:116`의 `.endswith("platform/scope.py")`는 경로가 아니라 **grep 출력에 맞대는 조각**이다(`platform/`이 top-level이라 경로처럼 보였다). **쓰임으로** 갈랐다 — `startswith`/`endswith`의 인자와 `in`의 좌변은 독자에게 보여지지 않는다. ⚠️*"중의적인 top-level 이름은 뺀다"*는 규칙은 `src`(↔`dashboard/src`)까지 죽여서 안 썼다.
- Verified(**접두 매칭 함정은 양쪽에 다 있었다**): 추출 쪽 — 확장자를 `json|jsonl` 순서로 나열하면 `.jsonl`이 잘린다(실제 짝: `model-sweep-live-points.jsonl` ↔ 없는 `.json`) ⇒ 꼬리는 **탐욕적 문자 클래스 하나**. 검사 쪽 — `startswith` 멤버십이면 그 없는 `.json`이 **있는 것으로 통과**한다 ⇒ 정확 일치.
- Verified(**⚠️가드 자신이 한 번 틀렸다 — 변이 하나가 살아남았다**): 접두 함정 테스트가 `_repo_paths()`(집합)에 물었는데 dangling 검사는 **별도의 식**을 써서, 멤버십을 `startswith`로 느슨하게 해도 5개가 전부 초록이었다. **가드가 독자가 쓰는 그 물건이 아니라 제 창문에 물고 있었다**(Risk 12④). 판정을 `_in_repo()` 한 곳으로 뽑아 둘이 같은 것을 묻게 하니 red.
- Verified: `make check` **2397 passed + 2 skipped**(2392 → **+5**), 실패 0. **변이 8종 전부 red**(없는 이름 · `.jsonl`→`.json` · gitignore된 경로 · 추출기를 확장자 나열로 · 스윕 비우기 · `print()` 미인식 · 멤버십 `startswith` · 조각 예외 제거). 변이·실행·복구는 한 스크립트이고 **복구는 바이트 사본에서**(Risk 12⑦, `git checkout --` 아님).
- Verified(**기존 가드와 안 겹친다**): `test_evidence_pointers_resolve`는 `docs/evidence/*.log` **한 종류**를 `tests`·`docs`·`src`에서 훑고 **`scripts/`는 안 읽는다**. 이 파일이 나머지 절반이다.
- Verified(**안 한 것도 측정이다**): `#` 주석은 안 훑는다 — 주석에만 사는 경로를 재니 `src/stacks/node_modules` 하나였고 **의도적으로 tracked가 아니다**(훑으면 가드가 vendored 의존성을 커밋하라 요구한다). 점 top-level(`.github/` 등)은 앵커 밖 — scripts의 참조 횟수를 **0으로 쟀다**. 라이브 호출 0건.
- Changed(`docs/STATUS.md`): 문자 예산이 **10,998자 / config의 status 상한**이라 새 baseline 줄이 안 들어갔다 — 08-30(2332) 전문을 `docs/archive/status-baseline-2026-08.md`로 **옮겼다**(삭제 아님). ⚠️**STATUS 압축 `[auto]`(≤9,900)는 여전히 열려 있다** — 여기선 한 줄 들어갈 만큼만 비웠다.
- Blockers: 없음.
- Next: **GCP 내보내기 테이블 `numRows`** — 판정 시점(09-02 01:11Z)이 지났다. `bq show --format=json <table>`(무료). 0이면 그때가 문제다.

## 2026-09-02 — 서버는 대기 시간을 말하고 있었고 전송 계층이 그걸 버렸다 (gate 2392)

- Status: overnight `[auto]` 1건 — M46ⓒ가 남긴 잔여(Azure 429 자동 재시도). **완결**, M47.
- Changed(`probe_cloud_spend.py`): 전송 계층 **`az rest` → `curl -D -` + `az` 토큰**(`az rest`가 헤더를 버려서 이 항목이 별도였다) · `_cost_query_with_retry`가 **`clienttype-retry-after`가 말한 만큼만** 기다렸다 다시 묻는다(최대 3회, 매 대기 60초 클램프, **기다린다고 인쇄**) · `_split_http`/`_retry_after`/`_azure_token`/`_curl` 신설.
- Changed(**⚠️토큰은 argv에 두지 않았다**): `--config -`(stdin)로 넘긴다 — `ps`는 이 기계의 아무 프로세스나 읽는다. **URL은 argv에 남겼다**(비밀이 아니고 가드가 무는 게 그것이다).
- Verified(**핵심은 안 하는 쪽이다**): **헤더가 없으면 재시도하지 않는다.** 없는 간격을 지어내는 것이 애초에 429를 영구 실패로 읽게 만든 방식이다(20초<40초). 파싱 안 되는 값(`Retry-After`는 날짜도 허용)도 **0초가 아니라 재시도 없음** — 0으로 읽으면 스로틀 중인 서버에 타이트 루프를 돈다.
- Verified(**가드가 아무것도 안 보고 있었다**): `test_only_the_cost_query_endpoint_is_posted_to`가 사라진 `az rest --url`을 무는 형태라 **매치가 0이면 영원히 통과**였다. curl 계층에 대고 묻고 **POST 0건이면 red**로 바꿨다(Risk 12④의 그 모양).
- Verified: `make check` **2392 passed + 2 skipped**(2381 → **+11**), 실패 0. **변이 7종 전부 red**(URL 이동 · `-D -` 제거 · 없는 간격을 20초로 추측 · 토큰을 argv로 · 재시도 상한 완화 · 클램프 제거 · 파싱 실패를 0초로). 변이·실행·복구는 한 스크립트(Risk 12⑦).
- Verified(**안 한 것도 측정이다**): **라이브 재측정 안 함** — 429를 다시 부르는 건 그 자체로 스로틀을 쓰는 것이고, 이 변경의 내용은 **간격을 어디서 얻는가**라 오프라인에서 전부 물어진다. AWS/GCP도 안 물었다(무인 루프는 청구서를 만들지 않는다).
- Blockers: 없음.
- Next: **GCP 내보내기 테이블 `numRows`** — 판정 시점(09-02 01:11Z)이 지났다. `bq show --format=json <table>`(무료). 0이면 그때가 문제다.

## 2026-09-01 — 테이블은 생겼는데 아무것도 안 들어 있었다 · 묻는 도구 셋이 틀렸다 (gate 2381)

- Status: 전날의 Next("`spend-check`의 GCP 줄")를 물으러 갔다가 **묻는 도구 자신의 결함 셋**이 나왔다. 셋 다 **읽어선 안 보이고 태워야 보인다**. 권위 `docs/evidence/the-table-existed-and-held-nothing.log`.
- Verified(**GCP — 켠 것·실린 것·읽히는 것은 셋 다 다르다**): 13시간 뒤 테이블이 **생겼고**(01:53Z 생성, 토글 42분 뒤) 프로브는 *"잴 수 있다"*로 바뀌었다. 그런데 **`numRows` 0**이고 `lastModifiedTime`은 **조회 4분 전**(14:08Z)이었다 — 작성기는 살아서 도는데 실린 게 없다. ⚠️**"잴 수 있다"고 말해 놓고 물으면 답이 없었다**: `MEASURABLE`이 **테이블 존재**만 보고 **행 수**를 안 봤다. 이 파일이 존재하는 이유(*빈 절은 0으로 읽힌다*)가 **한 층 위에서 재발**. ⚠️**0행을 "₩0"으로 읽지 말 것** — 결제 계정에 프로젝트가 **5개**고, 적재 미도착과 실릴 것 없음은 **지금은 구분 불가**다(판정 시점은 §3대로 **하루**).
- Verified(**GCP — 프로브가 인쇄하던 `bq` 명령은 돌지 않는다**): MEASURABLE 분기는 **라이브 내보내기가 있어야 도달**해서 **한 번도 실행된 적이 없었다** — 오늘 처음 태우니 즉시 에러. 한 줄에 결함 셋: ⓐ`project:dataset.table` **콜론**(표준 SQL은 점) ⓑ`--project_id` 없음 → **다른 프로젝트**(`claude-study-501117`)에서 실행됐다 ⓒ`SUM(cost)`만 = **크레딧 미반영**. ⚠️ⓒ는 `GCP_BILLING_EXPORT_SETUP.md` **§4가 명시한 함정**인데 **그 문서를 가리키는 도구가 그걸 인쇄하고 있었다** — 같은 명령이 **두 벌이었고 한 벌만 맞았다**. ⚠️**인쇄된 지시도 주장이다.**
- Verified(**Azure — 기록된 결론이 뒤집혔다**): 13시간 뒤에도 429(5회째)라 헤더를 봤다. 고갈된 건 **`clienttype-requests: DefaultQuota:0` 하나**고(entity 2·tenant 18·QPU 58 여유) 서버가 **`clienttype-retry-after`로 대기 시간을 말하고 있었다**(5→**40**). 40을 기다리니 **200** — ACR **₩76.67** · Cosmos DB ₩0.00(08-30 기준선과 같은 성질, 전액 남의 것). ⚠️**재시도는 두 번 다 답이었다**: 09-01의 *"이번엔 아니었다"*는 **간격이 서버 요구값 아래**(20초<40초)였던 것이고, **고정 간격 재시도는 영구 실패와 구분되지 않는다**. ⚠️`_why()`가 docstring에 적은 값어치(*"1분 뒤 재시도인지 깨진 자격증명인지"*)를 **헤더를 버리는 전송 계층(`az rest`)이 못 주고 있었다** — 이유의 **이름**은 줬고 **행동에 필요한 값**은 못 줬다.
- Changed(`probe_cloud_spend.py`): 상태 **셋→넷**(`EXPORTED_EMPTY` 신설 — MEASURABLE에 접으면 **없는 답을 약속**하고 NOT_EXPORTED에 접으면 **이미 옳게 켜진 토글로 되돌려 보낸다**) · 행 수는 **`bq show` 메타데이터**로 센다(스캔 0바이트 = **$0**; `bq query`로 셌으면 **프로브가 돌 때마다 과금** = CE가 청구서 84%가 된 그 방식) · `_export_query()`로 명령을 **한 곳에서만** 만든다 · `AZURE_429_HINT`는 **429일 때만** 붙는다.
- Verified(**⚠️새 함정 둘을 미리 막았다**): **`bq show` 실패는 0행이 아니다**(`AccessDenied`·리전 `[]`·429와 같은 부류 → MEASURABLE로 두고 질의가 독자 앞에서 시끄럽게 실패하게 둔다) · **빈 테이블이 스윕을 멈추지 않는다**(멈추면 스윕이 지우려던 **단일 위치 가정**이 되살아난다). **고친 명령은 쓰기 전에 라이브에 태웠다**(exit 0).
- Verified: `make check` **2381 passed + 2 skipped**(2368 → **+13**), 실패 0. **변이 8종 전부 red**(존재만으로 MEASURABLE·콜론 복원·`--project_id` 제거·credits 제거·힌트 제거·메타데이터 실패를 0행으로·빈 테이블이 스윕 중단·모든 실패에 힌트).
- Verified(**안 한 것도 측정이다**): AWS는 **재측정하지 않았다** — 13시간 전 값이 유효하고 **다시 묻는 것 자체가 청구서**다. GCP 확인도 `bq ls`/`bq show`(무료)로 했고 `spend-check` 전체는 안 돌렸다.
- Blockers: GCP 적재(시간) · Azure는 `az rest`가 헤더를 버리는 것 그대로(전송 계층 교체는 별도 승인).
- Next: **토글 01:11Z로부터 하루 뒤**(09-02 01:11Z) `numRows` 재확인 — **여전히 0이면 그때가 문제**다. 이제 프로브가 그 구분을 스스로 한다.

## 2026-09-01 — "비용체크"를 재다: 지출의 84%가 얼마 나가는지 물어본 값이었다 (gate 2368)

- Status: 문서 인용이 아니라 **재서** 답했다. 코드 변경 없음. 권위 `docs/evidence/the-measurement-is-the-bill.log`.
- Verified(**AWS — 서비스별로 가르니 결론이 바뀐다**, 08-20~09-01 크레딧 제외): **Cost Explorer $0.2000 = 전체 $0.2380의 84%** · EC2-Other(EBS 잔여) $0.0295 · S3 $0.0056 · ECR $0.0025 · DynamoDB $0.0004 ⇒ **진짜 인프라는 13일에 $0.038 ≈ 월 $0.09**. 바닥 $0.0034/일은 08-30과 동일하고, 봉우리는 **CE 단가 $0.01의 배수**로 뛴다(08-30·08-31이 $0.06대 = 그 이틀에 비용 조사를 했다).
- Verified(**⚠️08-30 기록의 재확인이 아니라 악화**): 그때는 *"이번 달 $0.64 중 최대 항목"*이었고 지금은 **전체의 84%**다. ⚠️**이 기록을 쓰려고 CE를 2회 더 불렀다 — $0.02가 곧 붙는다.** 관측이 관측 대상을 만드는 계정이고, **조회 남발 금지는 취향이 아니라 산수다**.
- Verified(**⚠️09-01 줄의 $0.0000은 0이 아니다**): CE 지연 이틀+. 오늘 창만 보고 답하면 틀린다.
- Verified(**Azure — 못 쟀다. 이번엔 재시도가 답이 아니었다**): spend-check 1회 + 20초 간격 3회 = **4회 연속 429**. 08-30 기록은 *"재시도가 답이었다"*였는데 **이번엔 아니었다** — ⚠️**기록된 처방이 항상 듣는 건 아니고, 안 들었다고 답이 바뀌지도 않는다**: **'0'이 아니라 '측정 실패'**다. 기준선은 08-30의 **₩7,063 전액 남의 ACR**. ⚠️`az costmanagement` 확장이 없어 손으로 우회하려던 첫 시도가 실패했다 — **레포 프로브(management.azure.com 직접 POST)를 쓰는 게 맞았다**.
- Verified(**GCP — 아직인 게 맞다**): 켠 지 **11분**(01:11→01:22 UTC), `bq ls` 테이블 0개. `GCP_BILLING_EXPORT_SETUP.md` §3이 예고한 정상 상태이고 **판정 시점은 하루 뒤**다.
- Blockers: Azure 스로틀(시간) · GCP 테이블 생성(시간). 둘 다 **지금 할 수 있는 일이 없다**.
- Next: ⚠️**세 답의 모양이 각각 다르다 — 하나로 요약하지 말 것**(AWS=쟀다/지연 · Azure=못 쟀다 · GCP=아직). **하루 뒤 `make spend-check`** 재확인이 다음 행동이다.


## 2026-09-01 — 지운 뒤에도 파이프는 계속 말을 걸고 있었다 · 결제 내보내기를 켰다 (gate 2368)

- Status: "환경이 없어서" 막혀 있던 둘을 수행했다(사용자가 Docker 기동 + 브라우저 제공). 권위 `docs/evidence/the-pipe-kept-403ing-after-the-key-was-gone.log`.
- Verified(**예고한 실패가 라이브였다**): kind를 띄우니 Prometheus가 **삭제된 워크스페이스로 계속 remote_write**했다 — `403 Forbidden: "The security token included in the request is invalid."`(지운 IAM 키). D50이 *"지우면 실패하기 시작한다"*고 적은 그것이고 **그게 결정의 내용이었다**.
- Verified(**⚠️값 파일을 고친 것만으로는 안 끝났다**): git의 값 파일엔 블록이 없는데 **배포된 helm 릴리스(rev 5)는 그대로**였다. **선언을 고치는 것과 도는 것을 고치는 것은 다르다** — 이 레포의 반복 주제가 인프라 층에서 재발.
- Changed(**helm rev 5→6**): 계획서와 같은 순서(`helm get values` 먼저). ⚠️**함정**: `--reuse-values`를 붙인 dry-run엔 **remoteWrite가 1건 남았다**(기존 릴리스 값을 병합하므로) — 그대로 적용했으면 *"고쳤다"*고 보고하며 아무것도 안 바뀌었을 것이다. 뺀 dry-run은 0건 + 알람 룰 유지 ⇒ 적용. 고아 Secret `monitoring/amp-remote-write` 삭제(`NotFound` 확인) · PrometheusRule 31개·`PlatformDemoCrashLoop` **그대로**.
- Verified(**⚠️"설정이 사라졌다"와 "도는 것이 멈췄다"도 다르다**): CR·config가 비었는데도 오류는 01:09:54까지 계속됐다(파드가 옛 설정). 그래서 **로그가 아니라 런타임 API에 물었다**(`/api/v1/status/config` → `remote_write` **0건**), 리로드(01:10:47) **이후 깨끗한 창**으로 다시 셌다 → **40초간 0건**. ⚠️`--since=90s`로는 **7건**이 나왔다 — **창이 사건보다 넓으면 지나간 실패를 현재로 읽는다**(MTD로 "지금"을 답하지 말라던 것과 같은 모양).
- Verified(**곁에서 나온 기존 고장 — 내 것이 아니다**): 오퍼레이터가 alertmanager를 `invalid URL: unsupported scheme ""`로 못 만든다. 값 파일 74행이 **렌더 안 된 `${webhook_url}`**이고 파드는 **42일간 34회 재시작**, 업그레이드 **전** 로그에도 이미 연결 거부가 있었다 ⇒ **기존 고장.** 고치려면 Terraform이 렌더해야 해서 **범위 밖이라 손대지 않았고, 기록만 남긴다.**
- Changed(**GCP 결제 내보내기 켬**): 표준 사용량 비용 → **사용 설정됨**(프로젝트 `project-ec7809f7-0fb5-45d4-b6d` · 데이터 세트 `billing_export`, 새로 안 만듦). ⚠️**첫 시도는 틀린 Chrome 프로필**이었다(아바타 "B", 페이지 로드 실패) — 문서 §1이 적어 둔 함정 그대로. ⚠️**편집 폼의 프로젝트 기본값이 `Claude Study`**여서 그대로 저장했으면 **엉뚱한 프로젝트에 켜졌다.**
- Verified(**⚠️아직 "잴 수 있다"가 아니다**): `make spend-check`는 여전히 *"아직 못 잰다 — 내보내기 테이블이 없다"*이고 **그건 문서 §3이 예고한 정상 상태**다(첫 테이블까지 수 시간). **켠 것은 확인됐고 읽히는 것은 미확인이다 — 둘을 같은 문장으로 쓰지 않는다.** ⚠️소급 안 됨(§0): 07월 GKE 비용은 복구되지 않는다.
- Blockers: 없음. **게이트 숫자 변화 없음**(코드 변경 없음).
- Next: **`make spend-check`의 GCP 줄을 수 시간 뒤 재확인**(하루가 지나도 그대로면 그때부터가 문제) · alertmanager `${webhook_url}` 미렌더(기존 고장, 인프라 결정).

## 2026-09-01 — 정적검사 결정을 닫았다: 측정 위에서, "나중에 보자"가 아니라 (gate 2368)

- Status: 08-30부터 열려 있던 **사용자/레포 결정**을 **숫자를 갖고** 물어 닫았다 → **D51**.
- Decision(**D51 — 정적검사는 게이트에 안 들어간다. 측정만 기록한다**): `gate.yml`의 *"a CI job is a bad place to introduce a standard nobody agreed to"*를 유지한다.
- Verified(**근거 ① ruff는 잡을 게 없다**): 20건, **여섯을 직접 열어** 확인 — 전부 미관/죽은 변수, **결함 0**. ⇒ 넣으면 **스타일을 집행하는 것이지 버그를 막는 게 아니다.**
- Verified(**근거 ② mypy는 신호는 있는데 비율이 나쁘고 비싸다**): 253 중 **200(79%)이 주석 부채**, **53이 실제 주장**. 그 53 중 **21건을 열어 고칠 값이 있던 건 2건**(M44 계약 갭 · M45 선언 불일치) — 나머지 19는 노이즈이거나 *"코드는 옳고 타입이 못 따라간다"*. 그리고 **`mypy src/`가 45초**로 게이트(38초)를 두 배로 만든다 ⇒ **D49가 288s→39s를 얻어낸 이유와 정면 충돌.**
- Verified(**⚠️요약 금지**): **"정적검사는 쓸모없다"가 아니다** — 이번 세션의 **실제 결함 둘을 찾은 건 mypy이고 테스트 스위트는 둘 다 놓쳤다**. 결정된 건 *가치*가 아니라 **게이트에 상주시킬 값어치가 아직 아니라는 것**이고, 여는 조건은 D51에 적었다.
- Changed: `DECISIONS` **D51** 신설 · `NEXT_PLAN`의 항목을 닫음 · `AGENT_BRIEF`의 `▶ NEXT SESSION`을 **남은 것**으로 교체(BQ 내보내기 · 고아 Secret · 4b · Phase 5 attach UI).
- Blockers: 없음. **게이트 숫자 변화 없음**(문서·결정만).
- Next: ⚠️**무과금 목록이 또 비었다 — 그게 사실이 아니라는 게 이 레포의 기록이다**(여섯 번 틀렸다). 09-01의 증분 넷은 **전부 다른 일을 하다가** 나왔다.

## 2026-09-01 — 시그니처는 필수라 했고 본문은 선택이라 했다: 그 기본값이 정책이었다 (gate 2368)

- Status: mypy 253을 **분류하다가** 나왔다. **결정은 여전히 안 내렸다.** 권위 `docs/evidence/the-signature-said-required-the-body-said-optional.log`.
- Verified(**`arg-type` 15 중 10이 한 함수**): `onprem_webhook_api`가 `summary.get(...)`를 `record_incident(severity: str, …)`의 **필수 `str`** 자리로 넘긴다. 그런데 본문은 다섯 다 **`x or "기본값"`** — **본문은 처음부터 `None`을 받도록 쓰여 있었다. 코드가 옳고 선언이 거짓이었다.**
- Verified(**`None`은 도달 가능하다**): 파이프라인 결과는 **키를 항상 갖지만 값이 `.get()` 결과**이고, 그 위에 파이프라인이 스스로 `incident = detector_out.get("normalized_incident") or {}`라 적어 뒀다 — **부재를 예상했다는 저자들 자신의 진술**이다. 없으면 `service`가 `None`으로 `alarm_name`에 도착한다. ⚠️`else: # MANUAL` 가지는 **`mode`가 `None`일 때도 걸린다**.
- Changed: 다섯을 `str | None`로. ⚠️**문을 닫는 쪽이 아니다** — 거부하면 **저하된 인시던트가 "인시던트 없음"이 된다**. `arg-type` **15→5**, mypy **253→241**.
- Changed(**⚠️진짜 발견은 그다음 — 가드 +10**): 주석을 고치는 건 **도는 것을 하나도 안 바꾼다**. 도는 것은 **기본값 부여**이고, `record_incident`를 쓰는 테스트 7개 중 **다섯 필드에 `None`을 넘기는 파일이 0개**였다 ⇒ **저하된 인시던트의 분류가 무단언**이었다. 둘은 그냥 기본값이 아니라 **축의 안전한 끝**이다: **MANUAL**=실행하지 **않는** 모드(AUTO로 기본값이 되면 **아무도 고르지 않은 조치가 나간다** — M39의 반대편) · **P3**=척도의 **바닥**(P1이면 불완전한 analyzer 출력마다 사람을 호출한다). 신규 가드는 문자열이 아니라 **어느 끝인지**를 묻고 **저장된 행까지** 읽는다(반환값만 보면 파일에 `null`이 적혀도 통과한다).
- Verified(**변이 4 red · 1은 못 쟀다**): mode→AUTO(3 failed) · severity→P1(3) · 기본값 제거(2) · 주어진 값 무시(1). ⚠️**M5(저장 건너뛰기)는 단일 호출 지점이 없어 변이가 안 붙었다** — *"안 쟀다"*로 남긴다.
- Verified(**곁가지 — mypy 오탐 하나를 격리했다**): `return-value` 4건이 전부 `x or os.getenv(k, DEF)` 모양인데, `os.getenv(k, DEF)` 단독은 `str`, `x or "literal"`도 `str`, `x or y`도 `str`인데 **`x or os.getenv(k, DEF)`만 `str | None`**이다 — `or`의 오른쪽에서 **오버로드가 첫 번째로 재해석**된다(mypy 1.14.1). **런타임엔 None이 될 수 없다** ⇒ 고치지 않았다.
- Verified(**누적 그림 — 결정에 줄 숫자**): 실제 주장 53 중 **21건을 열었다** → **실제로 고칠 값이 있던 건 2건**(M44의 계약 갭 + 이 선언 불일치), 나머지 19는 노이즈이거나 *"코드는 옳고 타입이 못 따라간다"*(오탐 4 · 도달 불가 2 · 재-export 3 · 이종 dict 2 · 이름 재선언 1 · 미설치 라이브러리 2 · 기타). **그게 이 도구의 이 레포에서의 신호 대 잡음비다.**
- Blockers: 없음.
- Next: **정적검사 게이트 편입 — 이제 숫자를 갖고 물을 수 있다**(사용자/레포 결정) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

## 2026-09-01 — 계약이 모두가 부르는 메서드를 빠뜨리고 있었다: 찾은 건 mypy였다 (gate 2358)

- Status: *"정적검사를 게이트에 넣을지"*의 **선행 실측을 다시 돌리다가** 나왔다. **결정은 내리지 않았다.** 권위 `docs/evidence/the-contract-omitted-the-method-everyone-calls.log`.
- Verified(**기록의 "전수 분류 결함 0"이 재현된다**): 가장 위험해 보이는 여섯을 실제로 열었다 — `dep_id`(넘길 파라미터가 **아예 없다**) · `azure_runner.url`(각 분기가 자기 URL을 만든다, **죽은 코드**) · F402(문자열 루프 변수와 **이름만** 겹침) · `original_guard`(**새 인스턴스**라 복원할 게 없다) · `result`(단언은 put_item 부작용에 건다) · E701 ×5(열 맞춤). **20건 전부 미관/죽은 변수.**
- Verified(**없던 반쪽 — mypy 253의 성격**): `type-arg` 71·`import-untyped` 40·`no-any-return` 36·`no-untyped-def` 32·`no-untyped-call` 21 = **200/253(79%)이 주석 부채**이고 나머지 **53이 실제 타입 주장**이다. **"253"은 절망적으로 읽히고 "200은 부채, 53이 주장"은 결정 가능하게 읽힌다.**
- Verified(**나머지 여섯은 닫았다 — "모른다"와 "도달 불가"는 다른 답이다**): 재-export 셋은 런타임 무관 · `model_router`의 `None` 역참조 둘은 **재서 도달 불가**다 — 업스트림이 *"if it has ended, otherwise None"*이라 관건은 **어디서 읽는가**이고, `result = run.result`가 `async for`를 **완주한 뒤**(본문에 `break` 없음)에 있다. 예외도 `GeneratorExit`도 그 줄에 못 닿는다. **mypy는 선언 타입에 대해 옳고 코드도 옳다** — 좁히기를 안 썼을 뿐. **다음 세션이 같은 줄을 다시 파지 않게 적어 둔다**(마른 스윕도 측정, M26).
- Verified(**⚠️그 53 중 하나가 진짜였다**): `"ExecutionAdapter" has no attribute "parameters_for_action"` — 네 어댑터가 **다 구현**하고 `aws/executor.py`가 **베이스 타입을 통해 부르는데** 계약이 선언하지 않았고 **테스트는 그 이름을 한 번도 언급하지 않는다(0건)**. ⚠️**오늘 런타임 결함은 없다**(넷 다 있다). 나쁜 건 호출부가 `except Exception: pass`라는 것 — 베이스를 만족시키는 데 `resolve_action` **하나면 충분**했으므로, 다섯째 provider가 그 조건만 채우면 `AttributeError`가 **삼켜지고 AWS 모양 파라미터**를 받는다. **에러 나지 않는 방식으로 실패한다**(Risk 8).
- Verified(**⚠️`from_alarm_context`는 고치지 않았다**): 정의가 **AWS 하나**뿐이고 호출도 `get_signal_adapter("aws")`로 **리터럴 고정**이라, 베이스에 선언하면 나머지 셋에 **거짓**이 된다. 기준은 *읽는 쪽의 provider 간 비대칭*이지 고아 선언이 아니다(M19 ⓑ) — **리터럴 고정 호출엔 틀릴 비대칭이 없다.**
- Changed(**가드 +8**): 베이스에 `parameters_for_action` 선언 + 신규 `test_adapter_contract_declares_what_callers_call.py` — **목록이 아니라 AST 유도**: provider가 **변수면 베이스가 선언해야 하고 리터럴이면 면제**(정규식으론 둘을 못 가른다) · 형제 넷이 계약 전체를 구현하는가(선언만 하면 `NotImplementedError`가 같은 `except`에 삼켜지니 **선언은 절반**).
- Verified(**⚠️내가 두 번 더 틀렸다**): ⓐ면제 테스트를 **`assert … or True`**로 끝냈다 — assertion이 아니고 무엇에 대고도 통과한다. 세션 내내 *실패할 수 없는 규칙*을 찾아 온 손이 그걸 썼다 ⇒ **면제가 실제로 무언가를 면제하는지** 묻게 고쳤다. ⓑM3(호출부 provider를 리터럴로)이 이 파일에서 초록이라 **또 한 파일에서 읽을 뻔했는데, 전체 스위트에 물으니 이번엔 진짜였다**(2356 passed — 아무것도 안 잡는다): provider를 **인자로 받은 함수가 그걸 무시하고 AWS를 하드코딩해도** 레포가 초록이다(M23과 같은 모양). **내 면제가 만든 탈출구라 내가 닫았다.**
- Verified(**변이 5종 전부 red**): 베이스 선언 제거 · gcp 구현 제거 · **호출부 리터럴화**(닫기 전엔 전체 스위트도 초록) · 스윕 공허화 · 면제 무력화. 복구는 `__pycache__` 삭제 후 확인.
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 여전히 사용자/레포 결정** — 이 증분은 *"켜라"*가 아니라 **"이 도구가 이 레포에서 무엇을 찾는가"의 한 표본**이다 · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.


## 2026-09-01 — 게이트가 안 돈 PR을 "CI 초록"으로 읽었다: 없는 것과 통과한 것이 같은 색이다 (gate 2350)

- Status: 이번 세션이 **직접 밟은** 것을 고쳤다. 권위 `.github/workflows/gate.yml` 트리거 블록 주석 · `tests/test_the_gate_runs_on_every_pull_request.py`.
- Verified(**⛔먼저 오해를 막을 것 — `main`은 무방비였던 적이 없다**): 브랜치 보호가 `check` 컨텍스트를 **요구**하고(`required_status_checks.contexts == ["check"]`), 게이트는 **main 대상 PR에선 언제나 돌았다**. **D43은 계속 성립했다.**
- Verified(**그럼 무엇이 문제였나 — 스택 PR**): `pull_request: branches: [main]` 필터 때문에 **base가 다른 브랜치인 PR엔 이 job이 아예 안 돈다**. PR **#58**(base = M39 브랜치)에서 `gh pr checks`가 *Amazon Q: pass / Vercel: pass / Vercel Preview Comments: pass*를 답했고 **`check` 행이 아예 없었다** — 그걸 "CI 초록"으로 읽었다. ⚠️**없는 것과 통과한 것은 그 목록에서 같아 보이고, 차이는 읽는 사람이 채운다.**
- Verified(**이건 이 레포가 이미 이름 붙인 실패의 한 층 위다**): Risk 12②가 *"skip은 실패가 아니라서 **검사 안 하는 게이트와 통과한 게이트가 같은 색**"*이라 적었다 — 거기선 **건너뛴 테스트**였고 여기선 **안 돈 워크플로**다. 같은 모양, 한 층 위.
- Changed: `pull_request`에서 `branches` 필터 제거 ⇒ **모든 PR이 게이트를 받는다**. CI 몇 분을 더 쓰고 **초록이 어디서나 같은 뜻이 된다**. 이유는 트리거 블록 주석에 적었다.
- Changed(**가드 +4**): 트리거가 존재하는가(공허성) · **base 필터가 없는가**(진짜 고침) · 이유 주석이 `#58`·`Risk 12`를 계속 가리키는가. ⚠️**YAML 1.1은 맨 `on:`을 불리언 `True`로 읽는다** — `wf["on"]`만 본 테스트는 KeyError로 *"트리거가 없다"*를 답했을 것이라 **둘 다** 조회한다(자기가 막는 실패와 같은 모양).
- Verified(**⚠️경계**): **게이트가 병합 조건이라는 것은 이 파일이 주장하지 않는다** — 그건 GitHub 브랜치 보호에 있지 레포에 없다. `test_signature_gate_claims`가 **배선을 앞질러 간 주장**의 표준 사례다. 레포 안에 있는 절반만 묻는다.
- Verified(**변이 4종 전부 red**): `branches` 필터 복귀 · `branches-ignore` 형태 · `pull_request` 트리거 제거 · 이유 주석 삭제.
- Changed(**재개 방지**): `docs/plans/2026-08-08-phase4-scope-and-cost.md`의 4a 절이 아직 **착수 대상**으로 읽혀 *"끝났고 접혔다"* 박스를 얹었다(§10·§11 · M38·M40 · D50 Folded를 가리킨다).
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 사용자/레포 결정**(선행 둘 다 재기 좋다) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

## 2026-09-01 — 셋째 형제는 mypy였다: 정적검사 선행을 재다가 나왔다 (gate 2346)

- Status: `NEXT_PLAN`의 *"정적검사를 게이트에 넣을지"*는 **레포의 결정**이라 묻지 않고 **선행 실측 둘만** 다시 쟀다. 재는 도중에 나왔다. 권위 `docs/evidence/the-third-sibling-was-mypy.log`.
- Verified(**기록은 둘 다 맞았다**): `make lint` **20건**(F841 8·E731 5·E701 5·F402 1·E712 1 · src 7·tests 13, ruff 0.15.10) · mypy **253 errors in 88 files (166 checked)** — 기록 *"253 across 88 of 165"*와 일치(파일이 하나 늘었다).
- Verified(**⚠️그런데 그 253은 그냥은 안 나온다**): `mypy src/`는 `cdk.out`의 **중복 모듈에서 수집 단계에 죽는다** — *"Found 1 error in 1 file (errors prevented further checking)"*. 253을 보려면 `--exclude`를 손으로 붙여야 했다 ⇒ **선언된 설정이 그대로는 실행조차 안 됐다.** `pyproject.toml`은 그 블록을 *"the settings are the target"*이라 적어 뒀는데 **못 돌리는 target은 돌려서 실패하는 target보다 약하다.**
- Verified(**⚠️Risk 12⑥ 재발 — 그것도 그 규칙을 집행하려고 만든 가드 안에서**): 08-30에 pytest↔ruff 비대칭을 고치며 만든 가드의 파일명이 **`..._from_both_tools.py`(both=둘)**였는데 같은 `pyproject.toml`에 **`[tool.mypy]`가 셋째 형제로 있었고 두 경로 중 아무것도 안 적고 있었다**. ⚠️**빠진 쪽이 하필 가장 나쁜 형제였다** — ruff의 실패는 시끄럽고 오락가락(20↔6,527)인데 mypy의 실패는 **총체적**이고(우리 코드를 한 줄도 안 본다) 문장이 *"1 error"*라 **작아 보인다**.
- Changed: `[tool.mypy] exclude` 추가 ⇒ `mypy src/`가 이제 그냥 돈다. 가드는 `..._from_every_tool.py`로 개명하고 **셋 다 순회**. ⚠️**게이트 편입은 바뀐 게 없다** — 선언을 실행 가능하게 만든 것뿐이고 결정은 그대로 레포의 것이다.
- Changed(**가드의 가드 — 변이가 시켜서 만들었다, +3**): 첫 판의 `TOOLS`는 **손으로 적은 dict**라 **M5(=TOOLS에서 mypy 제거)가 초록으로 살아남았다** — **이 파일의 주제가 이 파일에 그대로 일어났다: 세는 일 자체를 아무도 안 세고 있었다**(내 docstring은 *"derived, not listed"*라고 **코드가 안 하는 걸 주장**했다). ⇒ `pyproject`의 `[tool.*]`에서 제외 키를 **유도**해 `TOOLS`와 양방향 대조.
- Verified(**⚠️재는 동안 두 번 더 틀렸다**): ⓐ`mypy src/`가 **252**를 답한 적이 있는데 그건 **증분 캐시**였다(`--no-incremental`·캐시 삭제 둘 다 253) — 하마터면 *"기록이 틀렸다"*고 쓸 뻔했다. **캐시된 답은 측정이 아니다**(Risk 12⑦ `.pyc` 계열). ⓑ**변이를 적용하지 않고 변이를 쟀다** — 정규식이 과도 이스케이프돼 한 건도 안 지웠는데 두 후보의 시간을 쟀고, `diff`로 대조해서야 알았다. **변이 적용부터 확인하고 결과를 읽을 것.**
- Verified(**게이트 비용**): `mypy src/` **49.2s**(게이트 36초의 배)를 `mypy src/stacks/` **0.13s**로 바꿨다 — 결함이 사는 바로 그 자리이고 답이 둘뿐이라 공허하지 않다. 진짜 253은 손으로 재서 `pyproject`에 적었다. **집행 안 하기로 한 숫자를 재느라 게이트를 두 배로 만드는 건 나쁜 거래**(D49가 288s→39s를 얻은 이유).
- Verified(**변이 8종**): M1 mypy exclude 삭제 red(2) · M2 부분 드리프트 red · M3 ruff 삭제 red(3) · M4 pytest 삭제 red · **M5 red(고치기 전엔 초록)** · M6 초록—**설명됨**(위반 0건이라 꺼도 관측 불변; 하중은 M1이 재고 M1이 그 테스트를 죽인다, 귀속 확인) · M7 새 도구가 exclude 선언 red · M8 유도 무력화 red.
- Blockers: 없음.
- Next: **정적검사 게이트 편입은 사용자/레포 결정**(선행 둘 다 이제 재기 좋다) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

## 2026-09-01 — `onprem` extra의 `mlx-lm`: 선언은 있고 그걸 쓰는 곳이 없었다 (gate 2342)

- Status: `NEXT_PLAN` 08-30 항목. 기록된 근거를 먼저 다시 돌렸고 **적을 당시엔 참**이었다. 권위 `docs/evidence/the-onprem-extra-declared-a-mechanism-nobody-used.log`.
- Verified(**근거가 stale해진 게 아니라 더 나빠졌다**): PyPI 메타데이터 재측정 — 선언 하한 `mlx-lm==0.19.0`은 `mlx>=0.17.0`에 **플랫폼 마커가 없어** 리눅스 resolve가 진짜 실패한다. 그런데 `>=0.19`는 리졸버에게 **0.31.3**을 고르게 하고 거기엔 `platform_system == "Darwin"` 마커 + `py3-none-any` 휠이 있다 ⇒ **설치는 되고 엔진만 조용히 빠진다.** ⚠️**우회를 "이제 필요 없다"고 풀었으면 CI는 엔진 없는 mlx-lm을 초록으로 깔았을 것이다.**
- Verified(**그래서 우회가 아니라 선언을 물었다**): `src/`가 mlx를 임포트하는 곳 **0건**(에이전트는 MLX **서버**와 HTTP로 말한다 ⇒ 엔진은 임포트가 아니라 **프로세스**) · `.venv-mlx`엔 mlx-lm은 있고 `pydantic-ai-slim`은 없다 ⇒ **`.[onprem]`의 산물이 아니다**(08-30) · 실제 메커니즘은 `make mlx-setup`.
- Verified(**⚠️"안 쓰이니 지운다"가 아니다**): Makefile 최상단이 *"활성화된 `.venv-mlx`가 pytest를 가린다"*고 적고 인터프리터를 **탐침으로 고른다** — `.venv-mlx`가 프로젝트 env와 떨어진 건 **설계**다. `.[onprem]`이 mlx를 프로젝트 env로 들이면 그 분리를 정면으로 뒤집는다. **미사용이 아니라 틀린 메커니즘이었다.**
- Changed: `onprem`에서 `mlx-lm` 제거(근거는 주석에) · `gate.yml`이 인라인 `pydantic-ai-slim[openai]` 대신 **`.[onprem]`을 깐다** ⇒ **인라인 패키지 0개**(`serving` extra가 없앤 것과 같은 모양의 우회가 하나 남아 있었다).
- Changed(**가드 +3**): `TestMlxIsNotAProjectDependency` — 어떤 extra도 `mlx*`를 선언하지 않는다 · `src/`를 rglob으로 훑어 **전제를 코드에 묻는다** · `test_ci_requests_the_onprem_extra` + 인라인 금지 목록에 `pydantic-ai-slim` 추가.
- Verified(**⚠️내가 만든 가드 하나가 주석으로 통과했다**): *"`make mlx-setup`이 여전히 메커니즘인가"*를 `"mlx-lm" in Makefile`로 물었는데 **`MLX_BIN` 위 주석**에 그 문자열이 있어 레시피를 깨도 초록이었다. **주석이 주어인 규칙은 규칙이 아니다.**
- Verified(**⚠️그걸 "레시피 가드가 없다"로 읽은 것도 틀렸다 — Risk 12⑦ 재발**): 변이를 **이 파일에만** 물어서였다. 전체 스위트엔 red고, `test_local_stack_prerequisites.py::test_something_creates_the_venv_the_stack_runs_from`이 **레시피를 직접 읽는 옳은 자리의 옳은 질문**이었다 ⇒ 내 약한 사본은 **지우고** 어디가 그 자리인지 주석으로 적었다(두 번째 사본은 첫 번째의 그림자).
- Verified(**변이**): M1 extra 복귀 red · M2 인라인 복귀 red(2건) · M3 `src/`가 mlx 임포트 red · M4 레시피 깸 red(**전체 스위트에서**) · M5 규칙 무력화 **초록 — 설명됨**(현재 위반 0건이라 꺼도 관측 불변; 그 규칙의 하중을 재는 변이는 **M1**이고 red다).
- Blockers: 없음. ⚠️**리눅스 resolve는 로컬에서 증명 못 한다** — 이 PR의 CI 체크가 그 답이다.
- Next: **정적검사를 게이트에 넣을지**(lint 20건·mypy 253건 — **레포의 결정**) · BQ 결제 내보내기(콘솔 수동) · kind 재기동 시 `monitoring/amp-remote-write` Secret 삭제.

## 2026-09-01 — 4a를 접었다: 청구액이 $0.00이라 지운 게 아니다 — 대가는 장기 키였다 (gate 2339)

- Status: 사용자 결정으로 D50의 약속을 집행했다. **셋 다 삭제** — AMP 워크스페이스
  `ws-929b8da9…`(ap-northeast-2) · IAM 사용자 `amp-remote-write-4a` · 키 `AKIA…62VN`.
  권위 `docs/evidence/folding-4a-the-price-was-a-long-lived-key.log` · 계획서 **§11** · **D50 Folded**.
- Verified(**삭제 전 실측 — 정책이 기록과 정확히 일치했다**): 관리형 정책 **0건**, 인라인 **1건**이
  전부 `aps:RemoteWrite` **하나**를 그 워크스페이스 **하나**에. 키 마지막 사용 08-30T14:25Z `aps`.
  ⚠️**좁은 키도 장기 키다** — 그래서 지웠다. **$0.00은 지울 이유를 줄이지 않았다**(D50이 미리 그렇게 적어 뒀다).
- Verified(**"없다"를 어떻게 봤는지까지**): 8리전 스윕 전부 0 · `describe-workspace`를 **id로 직접**
  물어 `ResourceNotFoundException` · `get-user` `NoSuchEntity` · `list-users|amp` `[]`.
  ⚠️**`get-access-key-last-used`는 `AccessDenied`였고 그건 부재의 증거가 아니다** — 권한이 없어
  나온 답이라 키가 살아 있어도 같다. **증거는 소유 사용자의 부재**(키는 사용자보다 오래 못 산다).
  08-30 프로브의 429가 *"이것은 '0'이 아니다"*였던 것과 같은 모양.
- Changed(**레포에도 있었다**): `values/kube-prometheus-stack.yaml`의 `remoteWrite:` 블록 삭제 —
  안 지우면 **삭제된 워크스페이스를 가리키는 설정**이 git에 남는다. ⚠️**찾다가 내가 한 번 틀렸다**:
  `git grep`에 `| head -30`을 붙였는데 `docs/`가 `infra/`보다 먼저 정렬돼 **정작 그 파일이 잘렸고**
  "레포엔 없다"고 쓸 뻔했다 — 도구 함정이 아니라 **내 절단**이다.
- Changed(**가드를 지울 뻔했다 — 지웠으면 $180짜리 구멍**): `test_amp_cost_handles.py`의 9건은
  목적지가 사라지면 **전부 공허하게 참**이 된다(*"허용목록은 정확히 이 넷"*은 허용목록이 없을 때
  잘 통과한다). 지우는 쪽도 답이 아니다 — **D48은 4a를 접어도 안 죽고**(필터 없음 = 프리티어
  **128배**, ≈$180/월 = 4b 값 ⇒ 4a를 고른 이유가 지워진다) 그걸 적어 둔 유일한 물건이다.
  계약을 **함수로 빼** 두 호출자에 물렸다: 살아 있는 파일(목적지 **없어야** 한다) + **합성 표 9종**.
- Verified(**⚠️첫 판이 틀렸다 — 그림자로 세고 있었다**): 합성 표를 `violations != []`로만 묻자
  **와일드카드 검사를 통째로 지워도 초록**이었다(M2 생존) — `kube_.*`가 `allowlist-drift`에도
  걸려서다. **M17의 "결함을 그 그림자로 세지 말 것"** 그대로. 위반에 코드 7종을 붙이고 케이스가
  **어느 규칙이 물어야 하는지**를 지정하게 고쳤다 + 함수 본문에서 코드를 긁어 표와 대조하는
  가드(새 규칙이 케이스 없이 늘면 red). 재변이 **7종 전부 red**, 복구는 `__pycache__` 삭제 후 확인.
- Verified(**남긴 것의 이유가 바뀌었다**): KSM interval **60s 유지** — 더는 비용 손잡이가 아니고,
  데모 알람 룰이 `[5m]`로 적분하니 **60초=5샘플**(120초면 2샘플이라 `> 2`가 **원리상 도달 불가**).
  ⚠️**워크스페이스 id는 이제 안 박는다** — 없는 것을 박으면 **영원히 틀릴 수만 있는 규칙**이다.
- Blockers: 없음. 로컬 kind는 도커가 꺼져 이미 멈춰 있었다 — 다음에 띄우면 고아가 될
  `monitoring/amp-remote-write` Secret 삭제할 것.
- Next: **`onprem` extra의 `mlx-lm`**(승인 게이트 없는 유일한 코드 항목) · 정적검사 게이트 편입
  여부(레포의 결정) · BQ 결제 내보내기(콘솔 수동).

## 2026-09-02 — 재개 조건이 2년 전에 멈춘 이슈를 보고 있었다 (gate 2407)

- Status: 열린 항목 중 **날짜가 박힌 재확인 지시**를 단 유일한 것(Risk 6 / Cosign 어드미션, *"이 날짜부터 볼 것"*)을 판정했다. **완결**, M51. 권위 `docs/evidence/the-resume-condition-was-watching-a-dead-issue.log`.
- Verified(**결론은 유지된다**): 어드미션은 **아직 못 켠다**. 08-08 kind 실측이 *"서명된 것도 no signatures found"*였고 그 판정은 그대로다.
- Verified(**⚠️근거는 틀렸다 — 물고 있던 신호가 죽어 있었다**): 재개 조건이던 `policy-controller#1406`은 **2024-09-30 이후 갱신이 없다**. 그 이슈가 요구하던 구현은 **`#1725`로 2025-04-23에 머지**됐다. **"이슈가 열려 있다"는 "지원이 없다"의 증거가 아니었다** — Risk 4의 *"'없다'는 어떻게 봤는지까지"*가 업스트림 쪽에서 재발한 모양이다.
- Verified(**⚠️그럼 고치기 전 버전을 시험한 것인가 — 아니다**): 08-08에 쓴 chart **0.10.6**의 appVersion은 **0.13.1**(2025-09-17)로 **`#1725` 머지 이후**다. 즉 **지원이 들어간 버전에서 이미 실패했다.** 이 확인을 안 했으면 *"낡은 버전을 시험했다"*는 틀린 이야기를 적을 뻔했다.
- Verified(**진짜 신호는 따로 있었다**): `#1899`(*"cosign v3.0.2 서명을 policy-controller **0.13.1**이 검증 못 한다"*, **open**)가 **우리 조합 그대로**이고, 고침은 `#1968`(*"fix: Support cosign v3 signature verification"*, **미머지**)이다. ⇒ **새 조건 = `#1968` 머지 또는 `#2007`(2026-08-24 머지)을 담은 릴리스** — 최신 v0.15.1은 **2026-03-26**이고 그 뒤 **51 커밋이 미출시**다.
- Verified(**cosign 쪽 기록은 정확했고, 더 넓게 참이다**): `--new-bundle-format`은 v3.1.2의 **여섯 하위 명령**(`sign`·`sign-blob`·`attest`·`attest-blob`·`verify`·`verify-blob`) **어디에도 없다** — v2의 옵트인 플래그였고 v3에선 그 형식이 기본이라 사라졌다. ⇒ **간극은 서명하는 쪽이 아니라 검증하는 쪽**이고, `#2007`(policy-controller를 cosign v3.1.3으로 올림)이 그 방향을 가리킨다.
- Verified(**안 한 것도 측정이다**): **클러스터를 건드리지 않았다** — 재시도는 kind 변경이라 승인 후다. 클라우드 호출 **0건**(GitHub API와 로컬 `cosign --help`뿐). `make check` **2407 passed + 2 skipped**(변동 0 — 문서와 증거만 바뀌었다).
- Blockers: 업스트림. **단 이제 기다리는 대상이 살아 있는 것으로 바뀌었다.**
- Next: 며칠 뒤 **`make spend-check`**(창 3일→7일이면 GCP 런레이트가 가정 없이 나온다) · Risk 6은 **`#1968`/릴리스**를 볼 것.

## 2026-09-03 — 씨앗을 다시 채웠다: 넷은 초록에서 시작하는 가드다 (gate 2407)

- Status: 09-02에 `[auto]`가 5/5 소진돼 무인 루프가 집어갈 것이 **0**이었다. `/overnight-seed`로 판단하고 **다섯**을 기록했다(PR #73). 이 체크포인트로 ①은 **닫혔다** ⇒ 남은 씨앗 **넷**.
- Changed(`docs/NEXT_PLAN.md`): ①`PROGRESS_LOG` 압축 · ②진입점 문서의 `docs/**/*.md` 지목 실존 가드 · ③진입점 문서의 `D<번호>` 실존 가드 · ④문자 예산 숫자의 **유일 표기** 가드 · ⑤`STATUS` **줄** 예산 회복. ②③은 **오늘 dangling 0 / 14개 전부 실재** — **초록에서 시작하는 가드**지 청소 과제가 아니다.
- Verified(**⚠️씨앗을 만들다 세는 함정을 밟고 잡았다**): ②를 처음 재니 dangling **11건**이었는데 그중 **3건은 내 정규식이 만든 것**이다 — `bin/docs/archive/agents.md`에서 `docs/…`만 잘라냈다. 경계를 넣으니 **8건**이고 전부 **2026-07 archive**가 가리키는 사라진 파일이라 **진입점 기준으로는 0**이다. **잘못 센 수치로 씨앗을 만들면 루프가 한 이터를 버린다** ⇒ 그 함정을 씨앗 줄에 같이 적었다.
- Verified(**"없다"를 실측으로 적는다**): 린트 부채 쪽엔 씨앗이 **없다** — 추적 소스에 `type: ignore` **1건**, TODO/FIXME/XXX/HACK **0건**. 첫 조사에서 3,026건이 나온 건 vendored 경로가 섞인 것이다.
- Verified(**⚠️분량은 벽시계가 아니라 씨앗 수다**): 러너 로그 실측 — 실작업 이터 **8.7·9.0·9.9·15.0·15.5분**(평균 **~12분**), 이터당 **$2.99~$7.19**. *"몇 분"이 아니다.* 넷이면 **~48분·대략 $20**이고 **마르면 멈춘다**(정상). `MAX_ITER`는 씨앗 수보다 크게.
- Changed(`docs/PROGRESS_LOG.md`): 이 항목 자리를 내려고 09-02 두 건(NEXT_PLAN 압축·STATUS 압축)을 `docs/archive/progress-2026-09.md`로 **옮겼다**(삭제 아님) ⇒ 씨앗 ①의 Done 기준(≤10,800자)을 **여기서 충족했다**. 그래서 ①을 열어 둔 채로 두지 않고 **닫고 결과를 적었다**.
- Changed(`docs/AGENT_BRIEF.md`): ▶ NEXT SESSION이 **이미 끝난 일**(M50)을 가리키고 있어 교체했다 — 다음 세션의 첫 행동은 **씨앗 절**이다.
- Verified: `make check` **2407 passed + 2 skipped**(변동 0 — 계획·기록 문서만 바뀌었다). 세션 전체로는 **2397 → 2407**(M50의 +10)이고 M49·M51은 측정이라 게이트 변동이 없다.
- Blockers: 없음. ⚠️**루프는 돌리지 않았다** — 이터당 실비가 붙는 무인 실행이라 시작은 사람 신호를 받는다.
- Next: **씨앗 넷 중 하나**(`NEXT_PLAN`의 «Overnight 씨앗» 절) 또는 `MAX_ITER=7 make overnight`. 그리고 **며칠 뒤 `make spend-check`** — 창이 3일→7일이면 GCP 런레이트가 가정 없이 나온다.

## 2026-09-03 — harness 1.4.0: 무인 루프의 기본값이 바뀌었고, 새 문서는 가드가 먼저 잡았다 (gate 2410)

- Status: overnight-harness **1.2.0 → 1.4.0**. Makefile harness 블록을 새 스니펫으로 교체(모델 라우팅 actor `claude-sonnet-5` / critic `claude-fable-5-1`, ledger·resume·trajectory 타깃), `docs/LESSONS.md` 생성, `harness-config`에 `lessons` 경로·예산(40줄) 추가. 설치기가 되살린 `docs/engineering/`은 b078094에서 지운 경로라 다시 뺐다.
- Behavior change (1.4.0 기본값, Claude 엔진): `OVERNIGHT_CONTRACT=auto`(lean WorkContract), `OVERNIGHT_CRITIC` 빈 값 = `auto`, 턴 예산 초과는 **기록만**(되돌리지 않음, `OVERNIGHT_TURN_FAIL_CLOSE=1`로 복원). 다음 `make overnight`부터 적용.
- Verified: `make check` **2410 passed + 2 skipped**(2407 → **+3**). 첫 실행은 **4 red** — 새 `lessons` 예산이 세 선언 검사(정책표·머리말·vacuity 집합)에 없었고 진입점 gate 숫자가 2409≠2412였다. 가드가 설계대로 잡은 것이라 숫자 대신 선언을 맞췄다. `harness-init.sh --check` OK, `make overnight-where` → 1.4.0.

## 2026-09-05 — P5-C: Lambda·읽기 어댑터·독립 CDK와 로컬 SDK 실증 (M57)

- Status: P5-C 구현 완료. 기존 운영 스택을 바꾸지 않는 별도 app·공개 GitHub 익명 읽기·현재 사용자 DynamoDB 조회를 연결했다.
- Changed: commit→tree→blob 경로·mode·SHA 검증, redirect/큰 응답 거부, Lambda 업무 오류 계약, Linux ARM64 전용 패키징. IAM은 production Invoke와 지정 table/log group만 허용한다.
- Verified: 신규 테스트 **38 passed**, 전체 `make check` **2629 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 51.37초), TypeScript build·CDK 합성, 패키지 격리 import. 실제 DynamoDB Local에서 허용 200·읽기 grant만 가진 admin/삭제 사용자 403·테이블 장애 503. 임시 테이블·컨테이너 정리 완료. 인가/읽기/IAM 변이 **7종 red** → 바이트 복구.
- Learned: 첫 전체 게이트는 새 스크립트 출력 분류 누락으로 1 failed였다. REPORT 선언과 stdout 실패 보고·회귀 검사 둘을 추가했다. 첫 blob 변이는 길이 검사도 실패해 SHA 가드 제거를 놓쳤다. 같은 길이의 내용 변조로 바꾸자 SHA 검사 제거를 검출했다. boto3와 botocore 버전 숫자는 일치 가정 대신 실제 배포 metadata에 맞췄다.
- Blockers: P5-C에는 없음. private GitHub·원격 Lambda·세션/UI·PR 연결은 미검증/미구현. CDK 의존성이 없는 CI 환경에서는 관련 테스트가 skip한다.
- Next: `docs/plans/2026-09-05-phase5-planner-runtime.md` P5-D. 증거 `docs/evidence/phase5-lambda-runtime-2026-09-05.log`. 클라우드 배포·grant 설정·commit·push·PR 발행 없음.

## 2026-09-05 — P5-B: 현재 레코드로 tenant 쓰기 권한을 판정한다 (M56)

- Status: 오프라인 인가 진입점 구현 완료. 현재 레코드 확인을 통과한 요청만 P5-A로 전달한다.
- Changed: 정규화한 세션 주체와 조회 레코드 username 일치, operator/admin + 명시적 `registry_write_tenants`를 검사한다. 읽기 grant 승격·admin 우회·캐시/demo fallback 없음. 요청은 조회 전에 검증·복사한다.
- Verified: 관련 테스트 **187 passed**(+57). `make check` **2591 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 48.40초). 실제 스냅샷 플래너 연결, 거부 시 registry 읽기 0, 다음 요청에서 역할·grant 회수·사용자 삭제·조회 장애 반영. 인가 변이 **7종 red**, 소스 바이트 복구.
- Blockers: P5-B에는 없음. 현재성은 주입되는 저장소 어댑터의 책임이다. 실제 저장소·세션·Lambda 연결과 제출 시 재인가는 후속 범위이며 원격 변경은 없다.
- Next: `docs/plans/2026-09-05-phase5-planner-runtime.md` P5-C. 증거 `docs/evidence/phase5-write-grants-2026-09-05.log`.

## 2026-09-05 — P5-D: 실제 세션의 preview UI와 grant 보존 (M58)

- Status: P5-D 로컬 구현·검증 완료. 다음은 P5-E 발행 자격증명 실증안이다.
- Changed: Provisioning diff/SHA/만료 화면, 세션 username만 전달하는 bounded same-origin route, 전용 Lambda Invoke/local Git 어댑터. 기존 사용자 변경은 partial Update로 write grant를 보존한다.
- Verified: 신규 **38 passed**, 전체 `make check` **2667 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13), 최종 Next.js build·TypeScript. 실제 Auth.js operator/admin 허용·viewer 거부, 같은 쿠키의 grant 회수·위조·CSRF·익명·장애/미연결 구분. 실제 DynamoDB Local grant 보존/감사 기록/실패, 브라우저 preview 성공/오류 확인. 변이 6종 red → 바이트 복구 후 38 passed.
- Blockers: P5-D에는 없음. 원격 IAM Invoke·Vercel 배포·writer 토큰 경계·PR 제출은 미검증/미구현. TS 계약 검사는 dashboard npm 의존성이 없으면 skip한다.
- Next: `docs/plans/2026-09-05-phase5-planner-runtime.md` §5·§9. 증거 `docs/evidence/phase5-preview-ui-2026-09-05.log`. 임시 로컬 서버·컨테이너 정리; 클라우드·실사용자 grant·commit·push·PR 변경 없음.

## 2026-09-05 — P5-E: 실험 신원을 나누고 검토 가능한 요청 본문을 준비했다 (M59)

- Status: 발행 경계 실증 **준비 완료**, 실제 App/저장소 생성과 권한 시험은 미실행이다.
- Changed: 계획서 §10, 가상 tenant YAML 두 개·한 줄 diff·신원별 API 요청 템플릿·최소 권한 등록 URL. ref 거부 후 운영자 진단 branch를 end-to-end 성공으로 오인하지 않도록 판정 분리.
- Verified: 실제 GitHub 등록 화면 single_file acme + PR write, Contents 미허용 확인(Create 안 누름). 실제 P5-A로 가상 fixture/diff 검증, blob/base64·등록안 대조. `make check` **2667 passed, 2 skipped**(2026-09-05 로컬 macOS·py3.13, 테스트 증감 0).
- Found: 현재 gh의 installation 목록 403은 토큰 종류 제한이다. single_file 등록 UI 존재와 ref/file PUT의 Contents 요구 표를 따로 확인했다. 설치 삭제는 202 Accepted이므로 부재 재조회까지 정리 절차에 넣었다.
- Blockers: 새 private lab/App 생성·권한 부여·시험·삭제는 아직 실행하지 않았다. 기존 App/운영 저장소·클라우드·실사용자 grant 변경·commit·push 없음.
- Next: 계획서 §10의 정확 변경 범위를 검토받고 실제 installation token으로 호출한다. 증거 `docs/evidence/phase5-writer-preflight-2026-09-05.log`. P5-E 전체나 PR adapter 완료로 읽지 않는다.

## 2026-09-06 — Codex critic에 Claude 기본값이 전달되던 경로를 분리했다 (M60)

- Status: 다음 로컬 우선순위 1건 완료. 혼합 WIP를 보존하려고 이번에는 overnight 대신 직접 수행했다.
- Changed: Makefile·재설치 snippet에서 `CLAUDE_CRITIC_MODEL`을 export하고 공통 override 기본값을 비웠다. 엔진과 교차 critic 선택은 플러그인 1.5.0의 기존 코드가 맡는다.
- Verified: 실제 make 하위 환경 검사 변경 전 12 failed → 변경 후 12 passed. 설치된 선택/argv 생성 코드를 전송 없이 확인해 Codex critic 모델이 Astra임을 검사했다. 전체 `make check` **2679 passed, 2 skipped**(2026-09-06 로컬 macOS·py3.13).
- Blockers: 이 수정에는 없음. 실제 모델 서비스 호출과 overnight 실행은 검증하지 않았다. 플러그인 캐시·권한·기존 WIP·원격 자원 변경이나 commit/push 없음.
- Next: CI의 TS/CDK 검증 누락 방지. 증거 `docs/evidence/harness-critic-routing-2026-09-06.log`. P5-E App/lab 원격 실증은 기존 계획서 §10의 별도 범위다.

## 2026-09-13 — 승인된 읽기 권한 적용 후 키 경로에서 중단했다 (M82)

- Changed: 명시적 승인 후 기존 R2 App에 Contents Read-only만 저장하고 기존 설치의 새 권한을 수락했다. UI에서 acme write·code/metadata read·PR write·선택 repo 한 곳 확인. 새 App/키/설치 생성이나 파일 삭제 없음.
- Blocker: R2 PEM이 기록된 Downloads 경로에 없어 첫 키 열기에서 중단. 동일 파일명 Spotlight 검색도 결과 없음. 토큰 mint 및 branch/파일/PR 작업 intent 0개, 실제 시험 0회.
- Verified: 운영자 GET으로 private/Actions disabled·고정 main/기존 head 불변·새 branch 부재·PR 0건. API JWT의 네 권한 확인은 미실행이다.
- Evidence: `docs/evidence/phase5-writer-ref-read-setup-2026-09-13.json`. 최초 실패 기록과 미사용 슬롯을 보존했다.
- Next: 사용자에게 현재 PEM 경로를 인계받고 이미 승인된 범위를 계속한다. 재승인·새 키 생성·불확실 호출 재전송은 하지 않는다.

## 2026-09-13 — 실행 전 설정 실패도 인수한 토큰을 정리한다 (M81)

- Diagnose: --execute라도 executing=True가 어댑터 생성/설정 검증 뒤에 있어 오류 7종에서 cleanup NOT_ATTEMPTED·유효 토큰 잔존을 실제 로컬 HTTP로 재현했다(7 failed·7 passed).
- Changed: private state 디렉터리 확인 후 설치 토큰을 먼저 인수하고, --execute의 이후 설정/권한/진단 오류는 폐기와 같은 신원 GET 401로 정리한다. 디렉터리 미확보/토큰 미인수는 준비 단계 책임이고 오프라인은 API 0회다.
- Verified: 관련 70 passed, 신규 16건. 폐기 생략·오프라인 폐기·기록 디렉터리 전 토큰 인수 변이 3종 검출 후 바이트 복구. 이미 폐기된 토큰으로 재시작해도 DELETE를 반복하지 않는다.
- Evidence: `docs/evidence/writer-bootstrap-cleanup-verification-2026-09-13.json`, `docs/evidence/writer-bootstrap-cleanup-mutations-2026-09-13.json`. 실험 HTTP/로컬 파일 검증이며 실제 GitHub 호출·키 접근·토큰 민팅 없음.
- Next: M80 권한 확대 질문 답변 대기. 기존 어댑터의 네 권한 거부는 유지하며 자동 승인을 추론하지 않는다.

## 2026-09-13 — ref 읽기 추가 후보를 실제 설정 폼과 대조했다 (M80)

- Changed: 기존 App 권한 폼에서 Contents Read-only를 미저장 선택해 single_file write/acme 경로 유지 확인 후 새로고침 취소. 설치 161238144는 기존 권한·lab 1367740190 한 곳이다. 실제 권한 저장/민팅/API 쓰기/삭제 0회.
- Prepared: ref-read-execution-review.md와 ref-read-review.json에 네 권한·새 운영자 branch 1개·파일 시험 2회·draft PR 최대 1건·토큰 폐기/자원 보존 고정. base64/hash와 fixture별 +1/-0을 로컬 대조했다.
- Evidence: `docs/evidence/phase5-writer-ref-read-review-2026-09-13.json`. 미저장 폼 공존은 서버 저장·토큰 동작 증거가 아니다. 새 권한 조합의 파일 경계·PR 성공은 아직 미실증이다.
- Next: 기존 R2 App/설치의 Contents read 추가와 위 한정 시험 범위를 확인한다. 기존 exact-permission 가드·종료 intent는 유지하며 새 App/키 인계는 필요 없다.

## 2026-09-13 — PR 422의 ref 읽기 오류를 확인했다 (M79)

- Changed: 사용자 계속 지시로 승인된 r2-pr-diagnostic-01에서 고정 PR POST 1회. 기존 전체 workflow·권한·ref/파일은 변경하지 않았다.
- Verified: HTTP 422의 private 상세는 not all refs are readable. PR 0건, main/head/부모/두 파일 불변, 새 토큰 revoke 204→GET 401. 기존 및 R2 App/설치/lab/PEM/checkout/branch·종료 intent 보존.
- Evidence: `docs/evidence/phase5-writer-r2-pr-diagnostic-2026-09-13.json`. request ID F81B:2770AE:7361A7:A95F38:6AA5D885. M70/M77의 버린 상세까지 같은 원인으로 단정하지 않는다.
- Check: `make check` 3058 passed·2 skipped(2026-09-13 로컬 macOS·py3.13), 테스트 증감 0. 옛 PEM은 기록된 Downloads 경로에서 미발견이며 이번 작업에는 삭제가 없다. R2 PEM·두 checkout은 존재 확인.
- Next: ref-read-followup.md의 Contents read 추가 후보와 PR publisher 분리안을 검토한다. 공식 ref 조회는 Contents read를 요구하지만 추가 후 PR 성공·새 권한 조합의 파일 경계는 미실증이다.

## 2026-09-13 — 미분류 PR 오류를 별도 진단 파일에 남긴다 (M78)

- Changed: 기본 M73 기록은 유지, 명시적 --error-details-dir에서 알려진 자격증명/일반 비밀 형태를 제거한 message만 512/합계 1024 UTF-8 바이트·0600 파일에 저장. 실패는 UNKNOWN, 문구는 실행 결과/stdout에 포함하지 않는다.
- Verified: 관련 224 passed, 전체 3058 passed·2 skipped(로컬 macOS·py3.13, +20), 제거/연결/실패 처리 변이 3종 검출 후 바이트 복구. UTF-8 한계에서 빈 항목 대신 누락 표시하도록 수정했다.
- Evidence: `docs/evidence/writer-diagnostics-verification-2026-09-13.json`. 합성 미분류 문구의 보존 전후를 확인했으며 M77 실제 문구를 복원한 것은 아니다. 원격 호출 없음.
- Next: `experiments/phase5-writer/retry-20260913/pr-diagnostic-review.md`의 PR-only 1회 관측 범위 확인. 기존 App/설치/키/branch·종료 기록 보존; 새 생성/권한 확대 없음.

## 2026-09-13 — R2 실측에서 단일 파일 경계와 PR 422를 확인했다 (M77)

- Changed: 사용자 새 PEM 인계 후 JWT App 4924748 대조·lab 1367740190 한 곳 설치(161238144). 제한된 설치 토큰으로 ref 403 관측·폐기 후, 승인된 운영자 진단 branch에서 새 토큰으로 acme PUT 200·globex PUT 403·PR 422를 관측했다.
- Verified: 원격 main/형제 불변, 진단 branch는 seed 부모와 acme 한 줄 추가만 존재, PR 0건. 두 토큰 모두 revoke 204→GET 401. 기존 및 새 lab/App/설치/키/checkout 보존. production 변경/merge 없음.
- Finding: PR 오류는 validation_failed / PullRequest / custom / field null. custom 상세가 unclassified로 버려져 정확한 원인은 여전히 미확정이다. 소유자 UI의 정상 diff·draft 옵션은 App 권한 증거가 아니다.
- Evidence: `docs/evidence/phase5-writer-r2-live-2026-09-13.json`, `docs/evidence/phase5-writer-r2-readback-2026-09-13.json`. 키 원문·JWT·토큰은 저장하지 않았다.
- Next: PR custom 상세를 비밀 없이 관측하는 계약을 준비하고 후속 실행을 검토한다. 종료 intent 삭제·같은 호출 재전송·새 App 생성·권한 확대는 자동으로 하지 않는다.

## 2026-09-13 — 실제 GitHub 응답을 단계별 관측으로 연결했다 (M76)

- Status: GitHub 요청·관측 어댑터와 R2 실행 검토 준비 로컬 완료. 실제 설치 토큰 권한·PR 422 원인은 미확인이다.
- Changed: 운영자 GET·App JWT 조회·설치 신원 쓰기 분리, 고정 API origin/redirect 차단·응답/페이지 상한·독립 commit/tree·PR/Issue 작성 App 대조. 검증된 관측을 저장해 프로세스 재시작을 연결하고 CLI 기본 동작은 오프라인 검증으로 제한했다.
- Verified: 관련 회귀 249 passed. 새 어댑터/CLI 50건, 전체 게이트 3038 passed·2 skipped(2026-09-13 로컬 macOS·py3.13). 초기 전체 실행은 문서 수집 수 불일치 1건만 실패해 baseline을 갱신했다. 잘린 tree·작성 App 추정·요청 매핑·redirect·PR 페이지 변이 5종 검출 후 원본 바이트 복구.
- Evidence: `docs/evidence/writer-github-verification-2026-09-13.json`, `docs/evidence/writer-github-mutations-2026-09-13.json`, `docs/evidence/writer-github-readonly-2026-09-13.json`.
- External read: 실제 어댑터로 운영자 GET 13회, 보존 lab의 main/진단 SHA와 두 파일 일치 확인. 원격 쓰기·PEM/기존 checkout 접근 없음.
- Next: `experiments/phase5-writer/retry-20260913/execution-review.md`의 새 private lab/App·새 키·조건부 진단·최대 draft PR 1건·토큰 폐기·자원 보존 범위 확인. 새 원격 자원 생성은 실행하지 않았다.

## 2026-09-13 — 독립 관측이 맞는 단계만 다음 쓰기로 진행한다 (M75)

- Status: M73/M74와 단계별 증거 판정을 연결한 로컬 실험 제어 완료. 실제 GitHub transport/관측·새 자격증명 인계는 후속이다.
- Changed: 검토 신원/seed/branch의 고정 작업 디렉터리·파일 잠금·policy/review digest를 묶었다. 자체 HTTP 상태와 독립 prefix·current snapshot을 대조해 검증 기록을 남긴 뒤 진행한다. operator branch는 별도 검토 prefix로 시작한다. 종료 시 별도 revoke와 같은 신원 401 읽기를 요구한다.
- Verified: 제어/기존 판정 회귀 153 passed. 실제 loopback HTTP+합성 Git 관측으로 동시 실행·프로세스 사망/재시작·관측/상태 위조·저장/정책 변경·폐기 확인 누락을 검증했다. 관측 검증/HTTP 대조/현재 snapshot/고정 매핑/폐기 대조 제거 변이 5종 검출 후 바이트 복구. 전체 게이트 2988 passed·2 skipped(2026-09-13 로컬 macOS·py3.13, +37).
- Finding: diagnostic fixture의 과거 ref 403을 공통 응답 기본값 201로 덮던 테스트 설정을 수정했다. 실제 권한이나 GitHub 출처를 합성 관측으로 증명하지 않는다.
- Evidence: `docs/evidence/writer-workflow-verification-2026-09-13.json`, `docs/evidence/writer-workflow-mutations-2026-09-13.json`.
- External read audit: 보존 lab ID 1367338348·Actions disabled·PR 0·main/진단 SHA 불변을 GET 4회로 재확인했다. 쓰기/삭제·PEM/기존 checkout 접근 없음.
- Blockers/Next: 실제 요청/관측 어댑터와 재실증 실행 검토·키 인계를 준비한다. 원격 writer/배포·과거 PR 422 원인은 미해결이다.

## 2026-09-13 — 읽기 권한 추가로 PR은 생성됐고 작성 App 필드는 null이었다 (M83)

- Changed: 사용자 재다운로드 R2 PEM을 RSA 2048/0600으로 확인하고 승인된 네 권한을 API 대조했다. 고정 scope에서 민팅 1회·운영자 branch 1회·파일 PUT 각 1회·PR POST 1회 수행.
- Verified: 설치 신원 ref 200·acme PUT 200·globex PUT 403·draft PR #1 생성 201. 별도 운영자 조회에서 R2 App 봇·정확한 head/base·acme 한 줄(+1/-0)·main/형제/기존 branch 불변·PR 1건 확인.
- Diagnosis: 실제 Issue performed_via_github_app=null에서 TypeError 재현. 기대 App ID로 메우지 않았고 엄격한 독립 작성 App ID와 설치 신원 PR 파일 조회는 미검증이다. 원래 STOPPED 결과를 보존했다.
- Cleanup: 새 토큰 revoke 204→같은 토큰 GET 401. 모든 key/lab/App/설치/branch/PR/checkout·종료 intent 보존. 후속 조회는 운영자 GET만, 재민팅/쓰기 재시도 0회.
- Evidence: `docs/evidence/phase5-writer-ref-read-live-2026-09-13.json`. 직전 키 발급/다운로드 차단은 `docs/evidence/phase5-writer-r2-key-reissue-2026-09-13.json`.
- Check: `make check` 3074 passed·2 skipped(84.38초, 2026-09-13 로컬 macOS·py3.13). 코드 변경·원격 CI 실행 없음.
- Next: nullable 작성 App 관측 계약과 독립 신원 증거를 로컬에서 보완한다. production writer·자동 branch·배포·UI 완료는 아니다.

## 2026-09-13 — nullable App 필드와 작성 계정 검증을 분리했다 (M84)

- Diagnose: 실제 null 응답과 같은 로컬 HTTP 입력에서 TypeError/KeyError 5건 재현. 명시적 형태 검사로 고정 pr_author_app_unavailable을 반환하며 기대 ID로 채우지 않는다.
- Changed: 별도 writer_pr_identity.observe_pr_author가 App JWT의 실제 ID/slug→운영자 봇 ID 조회→PR/Issue 작성자 ID를 대조한다. App/저장소/PR/봇/필드 충돌·조회 중 App 변경을 거부하며 writer 성공 증거로 자동 승격하지 않는다.
- Verified: 관련 95 passed, 신규 25건. 계정 ID 검사·상충 App 검사·App 재대조 제거 변이 3종 red 후 원본 바이트 복구. null 이후 기존 workflow 재호출은 BLOCKED·추가 쓰기 없음.
- Live: App 4924748↔봇 328527925↔PR #1 작성자 대조, GET 11회·설치 토큰 민팅/원격 쓰기 0회. PR/files/refs 불변 확인. 원래 Issue null·M83 STOPPED·종료 intent를 보존하며 설치 신원 파일 조회는 추가하지 않았다.
- Retention: 저장소 루트의 PEM도 0600으로 보존하고 해당 파일만 .git/info/exclude에 추가. 키 삭제·이동·글로벌 설정 변경·커밋/푸시 없음.
- Evidence: `docs/evidence/writer-pr-author-verification-2026-09-13.json`, `docs/evidence/phase5-writer-pr-author-live-2026-09-13.json`, `docs/evidence/writer-pr-author-mutations-2026-09-13.json`.
- Check: `make check` 3099 passed·2 skipped(91.79초, 2026-09-13 로컬 macOS·py3.13). 원격 CI 미실행.
- Next: 네 권한 진단의 부분 증거·작성 계정·파일 관측·종료 상태를 연결하는 판정 계약을 로컬에서 검증한다.

## 2026-09-13 — 다른 시점의 진단 증거를 부분 판정으로 연결했다 (M85)

- Changed: writer_reconciliation과 오프라인 CLI를 추가했다. 고정 review bytes SHA·App/설치/repo/권한·intent/receipt/event ID·요청/응답·시각·Git snapshot·작성 계정·PR 파일·폐기 기록을 대조한다. 새 원격 요청/키 접근 없음.
- Contract: consistent_partial/inconclusive/boundary_failure만 반환한다. 원래 STOPPED/TypeError와 Issue null·설치 신원 PR 파일 미관측·과거 요청 자격증명/오프라인 기록 출처 한계를 보존한다. live_verified/writer_success_verified/retry_authorized는 항상 false.
- Verified: 신규 55 passed. 토큰 401·작성 계정·관측 유효 기간·최종 snapshot 검사 제거 변이 4종에서 각각 1 failed를 확인한 뒤 바이트 복구. 누락/상충/다른 실행/시간 역전/중복 키/과대 입력/반복 조회 검사.
- Replay: M84 관측 시각을 명시한 과거 기록 재평가에서 consistent_partial. CLI 두 번 결과 동일·입력 4개 SHA 불변. 현재 원격 상태의 새 관측으로 주장하지 않는다.
- Evidence: `docs/evidence/writer-reconciliation-verification-2026-09-13.json`, `docs/evidence/writer-reconciliation-result-2026-09-13.json`, `docs/evidence/writer-reconciliation-mutations-2026-09-13.json`.
- Check: 새 CLI DOCUMENT 분류 누락 1건을 수정한 뒤 `make check` 3154 passed·2 skipped(87.21초, 2026-09-13 로컬 macOS·py3.13). 원격 CI 미실행.
- Next: preview/prepare 뒤 본인 준비 요청의 PREVIEW/CLAIMED 상태 조회를 로컬로 연결한다. 진단 판정을 production 성공에 대입하지 않는다.


## 2026-09-13 — 준비 응답을 잃어도 기존 요청 상태로 복구한다 (M87)

- Changed: trusted Auth.js session의 subject로 status HTTP를 연결했다. 본문은 request_id만 받고 현재 권한을 재검사한다. 로컬 화면에 준비·상태 조회를 연결하고 응답 유실 뒤 준비 재전송을 막는다.
- Verified: TS 계약 81 passed(+21), Next production build 통과. 실제 로그인 HTTP에서 PREVIEW→CLAIMED·현재 grant 회수 403·타 사용자/없는 ID 404·위조 입력 422·교차 출처 403·미인증 401·과대 입력 413·실제 테이블 부재 503·no-store 확인.
- Browser: 실제 Chrome에서 prepare 200 응답만 끊었다. 미확인 안내·준비 버튼 비활성화 뒤 status로 CLAIMED 복구, 새로고침 후 수동 ID 조회도 성공. prepare는 1회이며 두 후속 status 모두 200. published=false 유지.
- Mutations: 요청 ID·published=false·비공개 필드 검사 제거 3종에서 1/1/2 failed, 원본 바이트 복구. 기존 CLAIMED를 재개하거나 발행 성공으로 바꾸지 않는다.
- Evidence: `docs/evidence/registry-status-http-verification-2026-09-13.json`, `registry-status-http-local-2026-09-13.log`, `registry-status-http-browser-2026-09-13.json`, `registry-status-http-mutations-2026-09-13.json`.
- Retention: 이번 임시 로컬 서버·테이블·fixture·컨테이너만 정리. 기존 네 Docker 컨테이너·GitHub 자원·PEM·checkout 보존. 원격 AWS/GitHub 호출·커밋/푸시 없음.
- Check: 첫 전체 게이트 3194 passed·2 skipped·문서 수 불일치 1 failed(88.57초). 기준 수 갱신 후 make check 3195 passed·2 skipped(88.14초, 2026-09-13 로컬 macOS·py3.13). 원격 CI 미실행.
- Next: Lambda 저장·상태 조회 배선을 로컬로 검증한다. production 배포/발행·테이블 생성·민팅은 별도다.

## 2026-09-13 — 준비된 요청을 재실행하지 않고 상태를 읽는다 (M86)

- Changed: read_stored_status와 service status/local --status를 연결했다. 본인 저장 레코드/불변 payload·현재 권한을 확인하고 재조회한다. PREVIEW/CLAIMED·만료 여부만 반환하며 claim_id/output을 노출하지 않고 published=false를 유지한다.
- Verified: 관련 60 passed, 신규 20건. 실제 DynamoDB Local에서 만료 claim 보존·동시 claim 최신 상태·준비권 재개 거부·타 사용자/권한 회수/잘못된 저장 값/실제 테이블 부재·별도 CLI preview/prepare/status 확인.
- Mutations: 소유자/현재 권한/두 번째 읽기/claim 재개 검사 제거 4종 모두 실제 로컬 DB 실험에서 AssertionError, 원본 바이트 복구 후 전체 실험 통과.
- Evidence: `docs/evidence/registry-status-verification-2026-09-13.json`, `docs/evidence/registry-status-local-2026-09-13.log`, `docs/evidence/registry-status-mutations-2026-09-13.json`.
- Retention: 이번 임시 로컬 테이블·컨테이너만 제거했다. 기존 GitHub 자원·PEM·checkout과 기존 Docker 컨테이너는 보존. 원격 AWS/GitHub 호출 없음.
- Check: `make check` 3174 passed·2 skipped(91.86초, 2026-09-13 로컬 macOS·py3.13). 원격 CI 미실행.
- Next: trusted session 기반 상태 조회 HTTP와 화면을 로컬로 연결한다. production Lambda/테이블/IAM·발행 어댑터는 별도다.


## 2026-09-14 — 배포 후보와 인증 대기 상태를 저장했다 (M90 checkpoint)

- Status: 09-13 완료한 M90 기록을 갱신했다. 같은 Vercel 2FA 조건을 3개 goal 턴에서 확인해 blocked로 전환. 09-14 checkpoint에서 goal 상태를 확인했고 브라우저/원격 상태는 재조회하지 않았다.
- Observed: us-east-1 기존 사용자 테이블/OIDC/bootstrap 확인. 새 RegistryPlannerStack 없음, men16922 Item 없음. 공개 main에서 GET 12회로 계획 계산; 인가/저장/발행 증거는 아니다.
- Candidate: HEAD+대시보드 WIP 12경로만 내보내고 소스/assembly SHA를 고정했다. 실제 credential 없이 깨끗한 Linux ARM64 Node 24 npm ci/build 통과. M88 Lambda asset 소스 일치, 실제 계정/리전 CDK no-lookups 합성 8자원.
- Review: docs/plans/2026-09-05-phase5-planner-runtime.md §13에 자원/IAM·본인 acme 권한·환경 값·단계별 실행/검증·중단/복구·보관 비용을 구체화했다. 이전 R2 승인을 운영 배포로 확대하지 않는다.
- Follow-up: 세 API의 필수 Origin이 배포 환경 목록에서 빠진 것을 보완했다. 로컬 env 캐시 두 곳에 Origin/Auth URL 없음(현행 서버는 미확인). 운영 Origin과 후보 URL 차이 때문에 승격 전 검사와 승격 직후 인증 E2E/복구를 구분했다. 증거 docs/evidence/registry-planner-origin-review-2026-09-13.json.
- Blocker: Vercel CLI 인증 만료, 브라우저 authenticator 인계. 캐시 project/rootDirectory/Node를 현재 서버 설정으로 주장하지 않는다. 현재 production/복구 URL·callback은 확인 대기다.
- Evidence: docs/evidence/registry-planner-auth-blocked-audit-2026-09-13.json, registry-planner-production-preflight-2026-09-13.json, registry-planner-candidate-verification-2026-09-13.json, registry-planner-candidate-source-2026-09-13.json, registry-planner-candidate-build-2026-09-13.log.
- Retention: 원본 WIP·기존 Docker/GitHub 자원·PEM/checkout·전역 설정 보존. 후보는 /tmp/platform-agent-planner-release-20260913에 보관. 배포·권한 수정·커밋/푸시 없음.
- Check: 기존 M89 gate 3252 passed·2 skipped(2026-09-13 로컬 macOS·py3.13). M90 첫 게이트는 새 문서가 untracked라 경로 검사 5건 실패(3247 passed·2 skipped, 95.11초). 검토안 전문을 기존 계획서 §13에 이동 후 최종 make check 3252 passed·2 skipped(94.28초), 관련 문서 28 passed. 원격 CI/실제 Invoke 미실행.
- Checkpoint check: 2026-09-14 문서 검사 28 passed(로컬 macOS·py3.13), git diff --check 통과.
- Next: 재개 시 Vercel 인증 상태와 /tmp 후보 해시를 다시 확인한다. 인증 후 현행 설정/배포·도메인·복구 URL을 읽어 §13을 완성한다. 이번 checkpoint는 문서만 수정하며 전체 게이트/원격 검증을 다시 실행하지 않는다.

## 2026-09-13 — 대시보드의 준비·상태 조회를 Lambda 호출에 연결했다 (M89)

- Changed: 공통 설정 판정과 AWS Invoke input/응답 처리를 preview/prepare/status에 연결했다. operation·session subject·request_id는 검증한 요청으로 고정하고 FunctionError/비200·UTF-8·크기·업무 실패를 거부한다. SDK는 한 번만 시도한다.
- UI: 유효한 AWS 설정과 REGISTRY_PLANNER_STORED_REQUESTS=1일 때만 준비/조회 화면을 연다. 직접 API 호출도 같은 opt-in을 요구한다. 이는 운영자 배포 선언이며 health 증거가 아니다. 로컬은 다섯 저장 설정을 모두 요구한다.
- Verified: TS 118 passed(+37), Next build. 네트워크 차단 Linux에서 실제 SDK/OIDC의 preview/prepare/status 자격증명 실패가 고정 503. 실제 SDK single-attempt/region 설정 검사, TS payload→실제 Python service/DynamoDB Local→TS 응답 왕복에서 200·409·404 확인.
- HTTP/Browser: 실제 Auth.js 세션의 로컬 저장/준비/조회·권한 회수/위조/타 사용자/테이블 장애 검사. AWS opt-in 미설정 API 503·화면 숨김. Chrome prepare 응답 유실 뒤 버튼 비활성화·status 복구, 재전송 없음·발행 미검증 유지.
- Mutations: opt-in·production 한정·FunctionError·SDK 시도 수·wire operation 제거/변경 5종 red 후 바이트 복구.
- Evidence: `docs/evidence/registry-aws-transport-verification-2026-09-13.json`, `registry-aws-transport-browser-2026-09-13.json`, `registry-aws-transport-roundtrip-2026-09-13.log`, `registry-aws-transport-mutations-2026-09-13.json`.
- Retention: 이번 임시 HTTP 서버·로컬 테이블/컨테이너만 정리. 기존 Docker/GitHub 자원·키/checkout·글로벌 설정 보존. 원격 AWS/GitHub API·배포·커밋/푸시 없음.
- Check: make check 3252 passed·2 skipped(106.21초, 2026-09-13 로컬 macOS·py3.13). 원격 CI 미실행. 다음은 실제 운영 대상 읽기 전용 사전 점검·배포 실행안이며 발행은 별도다.

## 2026-09-13 — Lambda에서도 저장한 변경안만 준비한다 (M88)

- Changed: 실제 IAM Lambda handler가 preview 저장·prepare·status 공통 서비스를 호출한다. 기존 preview 입력 모양은 유지하고 trusted operation만 추가한다. SDK endpoint override와 자동 재시도를 막고 별도 계획 테이블을 요구한다.
- CDK: 전용 request_id 테이블·ttl·PITR·deletion protection·Retain과 정확 테이블 GetItem/PutItem/UpdateItem만 정의했다. 기존 사용자 GetItem·로그·production OIDC Invoke 범위 유지. 새 함수 URL/발행 권한 없음.
- Verified: 관련 113 passed(+20). 격리 패키지의 실제 handler+실제 DynamoDB Local에서 저장 후 응답·중복 ID 거부·준비 8개 중 1개 성공/7개 충돌·만료 claim 보존·권한 회수/타 사용자/테이블 부재 거부 확인. 상태 조회는 Git 읽기/저장 변경 없음.
- Packaging: 모듈 8개를 Linux ARM64 asset에 포함했다. 공식 Lambda Python 3.13 이미지에서 네트워크 차단·native PyYAML/import/handler·실제 패키지 SDK 설정 확인. 실제 CDK 앱 no-lookups 합성 통과(앱 7개+CDK metadata 1개).
- Mutations: SDK 재시도·계획 UpdateItem 권한·Retain·패키지 operation 분기 변이 4종 검출. 마지막은 실제 DB 검증에서 실패했고 원본/asset 복구 후 통과했다.
- Evidence: `docs/evidence/registry-lambda-storage-verification-2026-09-13.json`, `registry-lambda-storage-local-2026-09-13.log`, `registry-lambda-storage-linux-2026-09-13.log`, `registry-lambda-storage-mutations-2026-09-13.json`.
- Retention: 이번 임시 테이블/컨테이너/공개 이미지용 임시 Docker 설정만 정리했다. 기존 Docker·GitHub 자원·키/checkout/글로벌 설정 보존. 원격 AWS/GitHub API·배포·커밋/푸시 없음.
- Check: make check 3215 passed·2 skipped(97.44초, 2026-09-13 로컬 macOS·py3.13). 원격 CI 미실행. 다음은 대시보드 AWS 준비/상태 transport이며 발행 상태는 추가하지 않는다.


## 2026-09-15 — 인증 대기를 해소하고 사라진 배포 후보를 다시 만들었다 (M91)

- Status: 직전 sync는 문맥 복원만 한 no-progress 턴이었다. 이번에는 Vercel device 인증 완료/CLI men16922·현행 project 조회로 기존 차단을 해소했다.
- Observed: 실제 rootDirectory=dashboard/Node 24.x/OIDC enabled-team·production READY·운영/복구 URL GET 200·서버 반환 callback 확인. Hobby active와 rollback 직전 production 제약을 §13에 반영했다. OAuth App 등록 callback/로그인 E2E는 미검증이다.
- AWS: STS q-user/908601828278·us-east-1 users ACTIVE/OIDC/bootstrap 재확인. 본인 Item은 HTTP 200에 없음, 새 스택은 명시적 부재 응답. 실제 Invoke/원격 자원 변경 없음.
- Candidate: 옛 tmp 후보 부재를 확인하고 `_workspace/planner-release-20260915`에 재생성. dashboard 106파일/12 WIP 경로가 M90과 일치, 공식 Node 24.21.0 Linux ARM64 clean npm ci/build 성공·audit 0. install-scripts 경고는 보존했다.
- Lambda: 기본 Apple Python 3.9의 pip marker 충돌로 첫 빌드 실패 → 기준 Python 3.13.5로 같은 빌드 성공. 소스/의존성 2,138파일 일치, 옛 pyc 192개만 미포함. 공식 3.13 ARM64에서 network none/read-only 8모듈·native YAML·잘못된 요청 422 통과.
- CDK: 실제 대상 no-lookups 합성 8자원. 원본 JSON의 asset 해시를 치환하면 M90 template SHA와 일치한다. stdout YAML은 Rules를 생략하므로 서로 다른 출력 표현을 변경으로 세지 않았다.
- Evidence: `docs/evidence/registry-planner-resume-verification-2026-09-15.json`과 같은 날짜 resume build/import/CDK 로그. 문서의 인증 대기/옛 후보 포인터를 갱신하고 이전 brief 전문은 archive에 보존했다.
- Check: 첫 게이트는 STATUS가 문자 상한을 129자 넘겨 실패(3251 passed·2 skipped, 104.45초). 중복 요약을 줄인 두 번째는 초과량 기록을 상한 선언으로 읽는 가드 1건만 실패(동일 수, 97.37초). 실측 의미가 분명하도록 고친 후 make check **3252 passed·2 skipped**(98.96초, 2026-09-15 로컬 macOS·py3.13.5), 문서 61 passed. 원격 자원 변경·GitHub 쓰기·커밋/푸시 없음. Docker Desktop을 시작했으며 기존 자원/키/WIP 보존.
- Goal: 운영 실증 승인 미응답이 M91과 후속 2턴에서 반복돼 09-15 blocked 전환을 확인했다. Vercel 인증 차단과는 별개다. 후속 두 턴은 무진전이며 추가 원격 호출 없이 기존 후보를 보존했다. 상태 기록 후 문서 61 passed·git diff --check 통과. 증거 `docs/evidence/registry-planner-approval-audit-2026-09-15.json`.
- Next: 계획서 §13의 새 AWS 자원·본인 acme 권한·production 설정/승격·검증/복구·보관 비용 범위를 확인한다. 승인 후 신원/후보/복구 대상을 재확인하고 동결 CDK 배포부터 진행한다.

## 2026-10-03 — AI 운영 에이전트 조사와 단일 환경 실사용 검증 계획

- Status: 기능 확대보다 기존 배포·검증·복구 흐름을 반복 사용하는 방향으로 우선순위를 조정했다. Phase 5는 별도 원격 우선순위로 유지한다.
- Changed: docs/plans/2026-10-03-platform-agent-usage-and-evidence.md에 공식 자료 기반 6개 에이전트 비교, 프로토콜/정책/평가 동향, R0~R5·완료 기준·보류 조건을 기록했다. 진입점의 다음 행동을 비변경 사전 점검(R0)으로 맞췄다.
- Verified: 공식 웹 자료와 로컬 관련 코드/문서를 대조했다. 09-03 피드백의 플래너 실행 위치 미결 조건은 M53~M91로 해소된 과거 조건이며, 외부 에이전트 직접 실행·실사용 흐름·원격 CI/배포/Invoke는 이번에 검증하지 않았다. 문서 검사 50 passed. 첫 전체 게이트는 3092 passed·37 failed·123 errors·2 skipped: 문구 변경으로 gate 수 파싱 2건 실패, 나머지는 기본 Node 26의 libsimdutf.34.dylib 누락/SIGABRT였다. gate 문구를 복원하고 명령별 PATH에 기존 Node 22.23.3을 지정해 관련 131 passed. Node PATH만 바꾼 재검증은 npx가 전역 bin을 앞세워 34 failed·3218 passed·2 skipped였다. 기존 Node/npm/npx·프로젝트 TS 5.9.3을 임시 prefix에 연결하고 npm offline으로 후속 59 passed. 최종 `make check PY=/opt/anaconda3/bin/python`은 임시 prefix PATH·npm_config_prefix·npm_config_offline=true 조건에서 **3252 passed·2 skipped·21 warnings**(2026-10-03 로컬 macOS·py3.13.5·Node 22.23.3, 112.11초). 전역 설정·제품 코드 변경 없음.
- Blockers: 대상 환경·서비스의 현재 동작과 신원 적용은 미측정. Phase 5 원격 변경 범위·PR writer 경계, Phase 4b 조건은 유지. 기존 WIP·lab/App/키/branch/PR/checkout 보존, 실행 씨앗·커밋/푸시 없음.
- Next: R0에서 WIP 포함 후보·로컬 대상·신원·복구 상태를 읽기만 해서 확인하고 정상/거부/실패/복구 재현 범위를 구체화한다.
