# R2 Contents read 추가 시험 — 실행 전 검토

상태: **M83 실행 종료: draft PR #1 생성, 독립 작성 App ID 미검증, 토큰 폐기/401 완료**. 아래 제안·M82 문단은 실행 전 이력이다. 기존 App 설정의 미저장 폼에서 Contents Read-only와 Single file Read and write가 함께 표시됨을 확인했다. 저장하지 않고 새로고침해 기존 두 선택 권한·필수 metadata와 설치 한 곳이 유지됨을 확인했다. 폼 공존은 서버 저장 성공이나 새 토큰의 파일 쓰기 경계 증거가 아니다.

## 제안하는 변경

- App `men16922-platform-agent-p5e-r2` / 4924748, 설치 161238144, private lab `men16922/platform-agent-p5e-authz-r2` / 1367740190을 재사용한다. 새 App·키·설치는 만들지 않는다.
- App 권한에 **Contents read 하나만 추가**하고 기존 설치의 변경 승인을 적용한다. 기존 single_file write(acme 한 경로)·pull_requests write·metadata read는 유지한다. App 설정 저장과 설치 권한 승인을 모두 실제 API 조회로 확인한다. 다른 권한·경로·설치·저장소가 늘면 중단한다.
- 읽기 범위는 이 lab 저장소 전체로 넓어진다. tenant 읽기 격리의 증거로 쓰지 않는다. **Contents write는 추가하지 않는다.** 쓰기 경계는 새 토큰으로 다시 측정한다.
- 새 검토 식별자는 `r2-ref-read-01`, 새 진단 branch는 `p5e/20260913-03-ref-read`. 기존 M77/M79 branch와 종료 intent는 그대로 보존한다. 운영자 branch 준비를 포함하므로 성공하더라도 자동 branch 생성 완료가 아니다.

## 고정 데이터와 요청

기준 main B=`59d54da9f4e9f8af89afc2c105f1d91fb3f33d2c`, main 부모 없음, acme seed blob=`398abe6c528238244a8e3713bc2b48523ae8b915`, globex seed blob=`ec999cb5bfcb210f3029ae085e56e9923223d3a4`. 파일은 이 폴더 seed/·expected/의 synthetic YAML 두 개뿐이다. 기존 진단 head `9d17b496128a7ec2a771041816c937db7e6366a3`도 불변이어야 한다.

정확한 API 본문과 content hash는 `experiments/phase5-writer/retry-20260913/ref-read-review.json`에 고정했다. 아래 각 쓰기는 durable intent를 먼저 저장하고 **한 번만** 수행한다. 예외/timeout/불완전 응답 이후 재전송·새 디렉터리로 우회하지 않는다.

| 순서 | 신원·호출 | 통과 조건 |
|---|---|---|
| 1 | 운영자·App JWT GET | App/설치/repo ID·정확한 네 권한·acme 경로·설치 한 곳·선택 repo 한 곳, private/Actions disabled, seed/기존 head 불변, 새 branch 없음·PR 0건 |
| 2 | App JWT 설치 토큰 mint 최대 1회 | repository_ids=[1367740190]와 네 권한 명시. 실제 응답·현재 설치 범위·만료·토큰 fingerprint 대조. 원문은 메모리에만 유지 |
| 3 | 설치 신원 GET main ref | 200, 정확한 B. 실패 시 branch를 만들지 않고 토큰 폐기/중단 |
| 4 | 운영자 POST 새 ref 최대 1회 | refs/heads/p5e/20260913-03-ref-read를 B에서 생성, 응답 201 및 독립 snapshot=seed |
| 5 | 설치 신원 GET 새 ref | 200, 정확한 B. main도 다시 B인지 대조 |
| 6 | 설치 신원 acme PUT 최대 1회 | 200, 새 commit 부모=B, acme는 expected blob, globex/main/기존 branch 불변. diff는 acme 한 줄 추가만 |
| 7 | 설치 신원 globex PUT 최대 1회 | 유효 토큰 상태의 권한 거부 403/404와 독립 snapshot 불변. 다른 응답 또는 파일 변경이면 즉시 중단, PR 없음 |
| 8 | 설치 신원 draft PR POST 최대 1회 | 호출 직전 두 ref·scope·PR 0건 재확인. 201이면 독립 PR+Issue 작성 App 4924748·head/base SHA·draft·파일 한 개(+1/-0) 검증 |
| 종료 | 같은 설치 토큰 DELETE 최대 1회 + GET | revoke 204 및 같은 토큰 GET /installation/repositories 401. 미확인이면 cleanup unresolved를 기록하고 자동 재전송 없음 |

순서 1의 새 branch 부재는 404 하나만으로 단정하지 않고 저장소 신원·권한·main 조회와 함께 대조한다. 순서 7에서 거부되었다는 상태 코드만으로 파일 경계를 통과시키지 않는다. 권한 거부 메시지·rate limit과 독립 tree 불변이 필요하다. 예기치 않은 2xx로 globex가 바뀌면 synthetic branch를 보존하고 실패를 기록한다. 롤백/삭제로 증거를 지우지 않는다.

## 관측·종료와 보존

M74 단일 실행권·M73 응답 분류·M78 opt-in 422 상세 수집을 사용한다. 비공개 진단 파일은 0700 디렉터리·0600 파일, 세 실제 자격증명 제거와 길이 상한을 적용한다. 자유문구는 실행 권한이나 성공 판정으로 쓰지 않는다.

기존 M76 어댑터는 정확한 세 권한용이다. 이 네 권한 실험에 기존 CLI --execute를 재사용하거나 가드를 삭제하지 않는다. 승인된 위 요청을 별도 고정 scope의 transport/독립 관측에 연결하고, 네 권한 하나라도 다르면 전송을 금지한다. 기존 종료 workflow는 계속 BLOCKED여야 한다.

성공은 **운영자가 준비한 branch + 저장소 전체 읽기 + 단일 파일 쓰기 조합의 실측**이다. 자동 branch 생성·tenant 읽기 격리·production writer/배포/UI의 완료로 승격하지 않는다. publisher 신원 분리는 이 조합의 실제 결과가 불충분할 때 검토하며 자동으로 새 App을 만들지 않는다.

어떤 결과든 App·설치·키·lab·새/기존 branch·draft PR·checkout을 보존한다. 권한은 승인된 네 권한 상태로 유지하며 자동 복구/축소하지 않는다. 보존 중인 R2 PEM을 재사용하므로 새 키 다운로드는 필요 없다. 옛 App PEM은 기록 경로에서 미발견이며 이번 작업의 삭제 대상이 아니다.

## 승인할 범위

**기존 R2 App/설치에 Contents read 추가, 위 새 진단 branch 1개, acme 허용·globex 거부 시험 각 1회, 통과 시 draft PR 최대 1건, 새 토큰 폐기와 모든 자원 보존**이다. 원격 권한을 넓히는 작업이므로 사용자 확인 전에는 저장/설치 승인·토큰 mint·API 쓰기를 수행하지 않는다.

## M82 승인 이후 현재 상태 (2026-09-13)

사용자의 명시적 승인 후 기존 App의 Contents Read-only만 저장하고 설치 161238144의 새 권한을 수락했다. UI에서 acme 파일 write·code/metadata read·PR read/write, 선택 저장소 한 곳을 확인했다. API JWT 재대조는 아직 하지 못했다. 기록된 R2 PEM 경로가 없어 첫 키 열기에서 중단했으며 토큰 민팅 intent와 네 작업 intent는 모두 없다. 원격 branch/파일/PR 시험은 0회다.

운영자 읽기로 private/Actions disabled·고정 main/기존 head 불변·새 branch 부재·PR 0건을 확인했다. 증거 `docs/evidence/phase5-writer-ref-read-setup-2026-09-13.json`. 기존 키를 찾으면 이미 승인된 범위로 이어가며 추가 승인이나 새 키 생성을 요구하지 않는다. 키가 이동한 경우 사용자에게 현재 경로만 인계받는다.

ref-read-review.json은 승인 당시 요청을 고정한 스냅샷이므로 그 안의 PROPOSED 상태 문자열을 덮어쓰지 않는다. 현재 승인/적용 상태는 위 M82 증거가 권위다. 기존 preflight 실패 summary는 보존하고, 실제 mint/쓰기 intent가 없음을 대조한 뒤 같은 scope의 미사용 슬롯에서 첫 호출만 시작한다. 이미 시작한 호출의 재전송이나 기존 종료 workflow의 재개는 허용하지 않는다.

## 키 재발급 인계 (2026-09-13)

사용자가 누락된 키를 다시 받도록 요청해 기존 R2 App에서 새 키를 한 번 발급했다. 이전의 기존 키 재사용 조건은 이 요청으로 변경됐으며 권한·저장소·시험 범위는 그대로다. 새 키 ID 4449076은 설정에 나타났으나 다운로드는 Chrome ERR_BLOCKED_BY_CLIENT로 차단됐고 Downloads의 해당 PEM은 0개다. 기존 키 4447759와 새 키를 모두 보존했다. 사용자가 설정 페이지에서 직접 사용 가능한 PEM을 발급·다운로드하고 경로만 인계해야 한다. 토큰 민팅과 branch/파일/PR 시험은 여전히 0회다. 근거: `docs/evidence/phase5-writer-r2-key-reissue-2026-09-13.json`.

## M83 실행 결과 (2026-09-13)

사용자가 재다운로드한 R2 PEM으로 승인된 범위를 실행했다. ref GET 200·운영자 branch 201·acme PUT 200·globex PUT 403·draft PR #1 POST 201. 운영자 독립 조회에서 App 봇·draft·head/base SHA·acme 한 파일 +1/-0·main/형제/기존 branch 불변을 확인했다. Issue performed_via_github_app=null로 검증기 TypeError가 발생해 엄격한 작성 App ID와 설치 신원 PR 파일 조회는 미검증이다. 원래 STOPPED 결과를 보존하고 토큰 revoke 204→GET 401을 확인했다. 재민팅/쓰기 재시도 없이 GET으로 조정했으며 모든 키/자원/intent를 보존한다. 현재 근거는 `docs/evidence/phase5-writer-ref-read-live-2026-09-13.json`이며 이 scope는 종료돼 재실행하지 않는다.
