# P5-E 재실증 R2 — 실행 전 검토

상태: **R2 실측 완료, PR 발행 미성공(M77)**. 새 App 4924748·설치 161238144·private lab 1367740190에서 ref 403, 운영자 진단 branch의 acme PUT 200·globex PUT 403·PR 422를 관측했다. 두 토큰은 각각 revoke 204 후 GET 401 확인. lab/App/설치/새 PEM/checkout과 기존 자원은 보존한다. 상세는 `docs/evidence/phase5-writer-r2-live-2026-09-13.json`. 아래 절차와 review.json은 이번 실행의 검토 스냅샷이며 재실행 지시가 아니다.

## 확인할 변경 범위

| 대상 | 이번 제안 |
|---|---|
| 새 private lab | `men16922/platform-agent-p5e-authz-r2` 하나. 기존 이름/ID가 있으면 재사용하지 않고 중단 |
| 새 private App | `men16922-platform-agent-p5e-r2` 하나, 위 lab 하나에만 설치 |
| 권한 | `single_file:write` → `platform/tenants/acme.yaml` 한 경로, `pull_requests:write`, `metadata:read`. Contents 권한 없음 |
| 실행 방지 설정 | Actions disabled를 seed 전 확인. webhook/OAuth 없음. 두 synthetic YAML만 seed |
| 시험 | `p5e/20260913-02` ref → acme 한 줄 변경 → globex 변경 거부 → draft PR 최대 1건. merge 없음 |
| 조건부 진단 | App ref 거부가 유효한 토큰·변경 없는 seed로 확인된 경우만, 운영자가 B에서 `p5e/20260913-02-diagnostic`을 생성. 새 설치 토큰으로 진단 실행하며 `diagnostic_only` 유지 |
| 종료 | 실행에 제공한 설치 토큰 revoke와 같은 신원 GET 401 확인. 불확실 호출 자동 재전송 없음 |
| 보존 | 새 lab·branch·PR·App·installation·키·checkout을 유지. 닫기·삭제·uninstall은 이 제안에 포함하지 않음 |

기존 lab **1367338348**, Downloads의 `men16922-platform-agent-p5e.2026-09-12.private-key.pem`, 기존 checkout은 보존한다. 기존 App 4921024와 설치 161148520은 삭제되어 그 PEM으로 새 토큰을 만들 수 없다. production 저장소 변경·CI·배포·권한 확대는 포함하지 않는다. 새 이름의 가용성과 설정은 생성 직전에 다시 확인한다.

## 새 자격증명 인계와 실행 순서

1. 위 원격 변경 범위가 확인되면 새 lab/App을 생성한다. `app-registration.url`은 등록 화면의 입력 보조일 뿐 실제 저장된 설정은 별도 조회한다. App key 다운로드는 사용자가 직접 완료하고 **파일 경로만** 전달한다. 키 내용은 대화·로그에 넣지 않는다. 브라우저 다운로드 차단은 우회하지 않는다.
2. 새 키는 저장소 밖 0600으로 유지한다. App ID·설치 ID·저장소 ID는 생성 결과를 조회해 채운다. JWT/설치 토큰 생성은 이 CLI에 들어 있지 않으며, 승인된 준비 단계가 새 키에서 JWT를 만들고 `review.json`의 정확한 repository_ids·permissions로 토큰을 발급해야 한다. 삭제된 옛 App/키나 운영자 토큰을 writer 신원으로 대체하지 않는다.
3. 민팅 응답에서 permissions·repository IDs·expires_at을 검증하고 설치 토큰의 SHA-256을 `credential_fingerprint`로 기록한다. `config.template.json`의 null은 실제 값으로 바꿔 저장소 밖 0600 설정 파일로 저장한다. 토큰/JWT 원문은 이 설정에 넣지 않는다. 신원별 비밀은 실행 프로세스의 `P5E_OPERATOR_TOKEN`, `P5E_APP_JWT`, `P5E_INSTALLATION_TOKEN` 환경에만 전달한다. 셸 이력·명령행·출력으로 전달하지 않는다.
4. 새 0700 상태 디렉터리를 한 번 만들고 재시작에도 같은 디렉터리를 사용한다. 아래의 `PRIVATE_CONFIG`와 `PRIVATE_STATE`는 비밀 값이 아닌 그 경로를 가리킨다. 기본 실행은 구성/fixture/만료 검증만 하며 API 0회다. 실제 GitHub 상태·권한을 증명하지 않는다.

```sh
python scripts/run_registry_writer.py \
  --config "$PRIVATE_CONFIG" \
  --policy-root experiments/phase5-writer/retry-20260913 \
  --state-root "$PRIVATE_STATE"
```

5. 원격 범위 확인과 새 키 인계가 끝난 뒤 같은 명령에 `--execute`를 추가한다. 준비 조회부터 실행하고 종료 토큰 폐기를 담당한다. 설정 검증만 수행한 경우에는 토큰을 사용하거나 폐기하지 않으므로, 준비 단계가 사용하지 않은 토큰을 관리해야 한다. M81 이후 --execute는 private state 디렉터리 확인 뒤 설치 토큰을 인수한 시점부터 정리를 담당하므로 이후 설정/권한 검증 오류도 revoke/401로 종료한다. 디렉터리 미확보·토큰 미인수 또는 오프라인 검사는 준비 단계 책임이다.
6. 유효한 ref 거부 뒤에는 자동 fallback이 없다. 저장된 `branch-denial.json`의 App/설치/repo/seed를 재확인하고 검토 범위 내에서 운영자 진단 branch를 준비한 뒤, 새 토큰과 갱신한 config에 `--diagnostic-prefix`로 해당 파일을 지정한다. 동일 App/설치/repo/seed가 아니면 진단을 거부한다. 불확실 intent를 지우거나 새 디렉터리로 우회하지 않는다.

`CONFIG_VALID`는 오프라인 설정 검사, `CONSISTENT`는 수집한 관측의 일치다. `live_verified:false`를 사람이 실제 신원·호출 기록을 검토하기 전에 성공으로 바꾸지 않는다. `UNKNOWN` 또는 cleanup `UNVERIFIED`는 재전송 허가가 아니다. 필요한 GET 조정부터 하고, 토큰 폐기 확인 실패는 별도 기록한다.

## 독립 관측과 판정

운영자 GET으로 seed/head의 commit·parent·tree·mode와 main 불변을 확인한다. PR과 연결 Issue의 번호·작성 사용자·저장소를 대조하고, Issue의 `performed_via_github_app.id`를 실제 App ID와 비교한다. PR 파일 목록은 설치 신원으로 읽어 페이지 누락·changed_files 불일치를 거부한다. 필드 위치는 [GitHub 공식 OpenAPI](https://github.com/github/rest-api-description/blob/main/descriptions/api.github.com/api.github.com.json)의 issue와 pull-request 스키마를 대조했다. 필드가 없으면 기대 App ID로 채우지 않고 미확인으로 멈춘다.

원본 오류 본문·토큰은 저장하지 않는다. M73의 허용된 오류 분류/field/code/request ID만 저장하므로 이번에도 보존된 정보로 원인을 결정하지 못할 수 있다. 그 경우 원인을 추측하거나 권한을 넓혀 재시도하지 않는다. 로컬 합성 GitHub 응답 테스트와 운영자 읽기 13회는 실제 설치 토큰의 쓰기 권한 증거가 아니다.

세부 요청은 이 폴더의 `review.json`, seed/변경 파일은 `seed/`와 `expected/`가 기준이다. 현재 승인 범위에서 seed 준비까지 실제 수행했다. App·키·설치 토큰 시험의 다음 단계는 새 PEM 경로 인계 후 이어가며 재승인을 요청하지 않는다.

## R2 종료와 남은 원인 진단

원격 diff는 acme 한 줄 추가, sibling/main 불변, PR 0건이다. 422는 validation_failed / PullRequest / custom / field null까지 확보했다. custom 문구가 기존 분류에 없어 unclassified로 남았으며 원문은 보존하지 않았으므로 정확한 원인은 미확정이다. 소유자 비교 UI는 정상 diff·merge 가능·draft 옵션을 표시했지만 이는 App 권한 증거가 아니다. 권한 오류나 요금제 문제로 단정하지 않는다.

다음은 분류되지 않은 custom 진단을 비밀 없이 관측하는 수집 계약을 준비하는 것이다. 고정 phase intent와 종료 결과를 지우거나 다른 디렉터리로 우회하지 않는다. 추가 API 쓰기·새 토큰 민팅·일반 PR 전환·권한 확대는 이번 종료 흐름에 자동으로 이어 붙이지 않는다. 앱/설치/키를 다시 만들 필요는 없으며 보존 자원과 현재 head를 다음 검토의 출발점으로 삼는다.
