# P5-E 오프라인 결과 판정

`review.json`은 원격 실험 제안이고 `fixtures/supported.synthetic.json`은 판정기 시험용 합성 입력이다. **실제 실행 결과가 아니다.** 예제의 ID와 commit SHA는 가상 값이며 GitHub 요청을 보내지 않는다.

```sh
python scripts/judge_registry_writer.py experiments/phase5-writer/fixtures/supported.synthetic.json
```

stdout은 JSON 한 개다. 종료 코드는 `supported`만 0, 다른 판정은 1, 파일 읽기/JSON/1 MiB 상한 오류는 2다(오류 설명은 stderr). 출력은 고정된 reason 코드만 사용하며 입력 본문·토큰·HTTP 원문을 출력하지 않는다.

| verdict | 의미 |
|---|---|
| supported | 입력 증거가 App의 네 호출 성공/경계 조건과 모두 일치 |
| diagnostic_only | App ref 생성 거부 후 운영자 진단 branch에서 나머지 조건 일치 |
| unsupported | 유효한 거부 근거와 불변 관측이 있어 App의 ref/대상 쓰기 성공 가설이 실패 |
| boundary_failure | 형제 파일 2xx, 예상 밖 tree/main 변경 등 경계 위반 관측 |
| inconclusive | 증거 부족/모순, 신원 불일치, timeout·인증·충돌·rate limit 등 판정 불가 |

`diagnostic_only` 불리언은 중간 실패 결과에도 유지된다. `sibling_boundary`는 전체 성공과 별개로 `not_tested`/`inconclusive`/`supported`/`violated`를 구분한다. `live_verified`는 **항상 false**다. 이 도구는 제공된 관측의 일관성만 검사하며 출처의 진위·토큰 신원·실제 호출 여부를 인증할 수 없다. 판정기 통과만으로 원격 실증 완료를 선언하지 않는다.

M65 실행 전 검토와 정확한 원격 변경 범위는 `execution-review.md`에 있다.

## 입력 계약 v1

합성 예제와 같은 구조로 **별도로 수집·검토한 관측을 정규화**한다. raw API 응답 전체를 바로 넣는 형식이 아니다. 중복 JSON 키와 NaN/Infinity는 파일 입력 오류로 거부한다. numeric ID·HTTP 상태·추가/삭제 줄 수는 JSON 정수이며 boolean/float로 대체하지 않는다. 관측이 없으면 예제 값을 복사해 채우지 않는다. 필수 증거 누락은 `inconclusive`다.

- `schema_version=1`, 정확한 실험 `repository`, `expected_identity`의 App/설치/저장소 numeric ID를 생성 응답과 대조한다. `credential_control`은 installation token의 읽기 대조 결과와 별도로 확인한 설치 metadata/권한/selected 저장소를 합친 기록이다. 세 ID·최소 permission·single_file 경로·selected 저장소 하나가 제안과 일치해야 한다. App JWT/운영자 토큰의 호출은 권한 시험으로 인정하지 않는다.
- `seed`, `branch_snapshot`, 각 쓰기의 `before`/`after`는 운영자 읽기 관측이다. `observer=operator`, `ref`, `commit`, `parents`, 같은 시점의 `main`, 완전한 재귀 tree의 `files`(경로 → Git blob SHA·mode)를 기록한다. `complete=true`는 tree 잘림/페이지 누락이 없음을 확인한 뒤만 적는다. Git blob SHA는 내용으로 계산한 기존 seed/expected YAML의 SHA와 대조한다. target 후 전체 tree는 acme의 예상 변경 하나뿐이어야 하고 mode도 100644다. 실제 commit 객체와 관측 시간의 진위는 별도 검토 대상이다.
- `branch_origin`은 `app` 또는 `operator`이며 `selected_branch`는 제안의 branch 또는 diagnostic_branch다. 운영자 branch도 B에서 출발해야 하고 앞선 App ref 거부/branch 부재/main 불변 증거가 필요하다. 진단 분기 기록을 App의 ref 생성 성공으로 바꾸지 않는다.
- 네 호출은 `identity`, `method`, `path`, `status`, 정규화한 `body`를 가진다. timeout의 status는 null이다. body에는 예제에 있는 **판정 관련 필드만 실제 요청에서 추출**한다(ref/sha, branch/기존 blob/content base64, head/base/draft/maintainer_can_modify). title/message 같은 비판정 필드는 제외하며 실제 값 대신 예상 값을 채우지 않는다. response도 예제처럼 필요한 관측 필드만 추출한다.
- 403/404의 `denial_controls`는 `token_valid`, `target_exists`, `sha_matches`, `rate_limit_excluded` 네 조건을 독립적인 읽기 대조·요청 SHA·오류/헤더 관측으로 확인한 기록이다. 불확실하면 true로 적지 않는다. 401/409/422/429/5xx/timeout/redirect는 이 플래그를 채워도 거부 증거가 아니다. 대상 쓰기 실패 후 형제 호출을 거부의 양성 증거로 세지 않는다.
- `pull_request.response`는 실제 PR number/URL/작성 App ID/head·base ref·SHA·repo/draft/merged를 기록한다. `files`는 해당 PR files API의 identity/method/path/status/완전 수집 여부/items다. files의 대상 경로·blob·추가 1/삭제 0과 운영자 tree를 함께 검사한다. head/parent/main과 형제 불변은 모든 단계에서 이어져야 한다.

Authorization, token/JWT/PEM, mint 응답 원문은 이 입력에도 저장하지 않는다. 실험 제안/권한·정리 절차의 권위는 `docs/plans/2026-09-05-phase5-planner-runtime.md` §10이다. 이 판정기는 네 호출의 일관성만 다루며 revoke·PR close·App/lab 삭제 완료나 운영 writer의 안전성을 판정하지 않는다.

## 실패 응답 수집 (M73, 로컬 완료)

`writer_capture.py`는 응답 원문을 보존하지 않고 고정 message 분류, 허용한 `errors.resource/field/code`, 형태를 검사한 GitHub request ID만 기록한다. [GitHub 오류 문서](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api)는 422의 `errors.code`를 진단 단서로 설명한다. `custom`의 자유문장은 그대로 저장하지 않는다. 현재 알려진 `No commits between … and …`/`A pull request already exists for …` 형태만 고정 분류로 바꾸며, 참조 이름·알 수 없는 메시지는 버린다. `unclassified`는 원인이 확인됐다는 뜻이 아니다.

로컬 CLI는 stdin의 `{status, headers, body, transport}` JSON을 받는다. `headers`는 이름/값 쌍의 배열, `body`는 문자열 또는 null, `transport`는 response/timeout/connection_error/body_unavailable 중 하나다. 출력 디렉터리는 사전에 소유자 전용(0700)으로 만든 새 실험 디렉터리를 지정한다. 디렉터리 생성·권한 변경·네트워크 호출은 CLI가 하지 않는다.

```sh
python scripts/capture_registry_writer_response.py --directory /path/to/private-run --operation create_pr
```

민감한 입력은 명령행 인자가 아닌 stdin으로 전달한다. CLI stdin은 128 KiB, 응답 본문은 64 KiB, JSON 깊이는 64, 오류 목록은 16개, 최종 기록은 8 KiB로 제한한다. stdout은 저장을 마친 정규화 JSON 하나이고, 실패 시 stdout은 비우고 stderr에 고정 진단만 출력한다. 파일은 서버가 생성한 event_id별 0600 JSON이며 flush/fsync 후 배타적으로 공개한다. 저장 실패는 성공으로 덮지 않는다. 디렉터리 fsync 실패 때 완전한 파일이 남을 수 있어도 성공 응답을 반환하지 않는다.

실제 HTTP 클라이언트에서는 `capture_http_response(journal, response, operation=...)`에 stdlib HTTPResponse/HTTPError를 넘긴다. 본문은 상한까지만 읽고 응답을 닫은 뒤 영속 기록한다. 본문 timeout은 기존 HTTP 상태와 request ID를 남기고 body_unavailable로 기록한다. 응답이 없는 timeout/연결 실패는 `journal.record(status=None, transport=..., operation=...)`으로 기록한다. HTTP 호출·재시도·token revoke는 이 수집기가 수행하지 않는다.

이 기록은 진단용 관측이며 위 v1 판정기의 완전한 입력을 대체하지 않는다. 요청의 실제 신원, commit/tree 전후 상태, 부작용 존재와 token 폐기는 따로 검증해야 한다. 2xx가 기록돼도 PR 성공이 아니고 403/404만으로 권한 격리가 증명되지 않는다. 과거 M70의 잃어버린 PR 422 본문은 복원하지 못했다. 다음은 호출 전에 intent를 영속 기록하고 불확실한 결과 뒤에 자동 재전송하지 않는 실행 경계다.

## 호출 전 intent와 재시작 경계 (M74, 로컬 완료)

`writer_attempt.run_once(directory, operation=..., send=...)`는 **한 번 검토한 작업 하나에 고정된 private 디렉터리**를 사용한다. 실제 요청·신원·timeout·redirect 정책은 서버가 구성한 `send`가 소유한다. 이 함수에 네트워크 클라이언트나 사용자 지정 URL 기능은 없다.

1. intent.json을 O_EXCL·0600으로 생성하고 파일과 디렉터리를 fsync한다. 이 단계가 실패하면 send를 호출하지 않는다.
2. 기존 intent가 있으면 상태·operation과 관계없이 BLOCKED다. 동시 실행·재시작에도 다시 전송하지 않는다.
3. send의 HTTPResponse/HTTPError는 M73 수집기로 영속 기록하고 receipt.json에 해당 event_id만 연결한다. 자유문장/요청/비밀값은 intent·receipt에도 들어가지 않는다.
4. 완전한 HTTP 관측은 OBSERVED, 응답/본문/저장 손실은 UNKNOWN이다. OBSERVED는 HTTP 상태를 수집했다는 뜻이며 PR 성공이나 다음 쓰기의 허가가 아니다.

`inspect_attempt(directory)`는 읽기 전용이다. 빈 정상 디렉터리는 NOT_STARTED, intent 이후 receipt가 없거나 기록이 불완전하면 UNKNOWN이다. 호출 전 프로세스가 죽어 실제 전송이 없었더라도 자동 재전송하지 않는 보수적인 경계다. TTL/lease/reset/자동 파일 삭제는 없다.

상위 실행기는 동일한 검토 작업에 같은 디렉터리를 계속 매핑해야 한다. 재시도마다 새 디렉터리를 만들면 이 경계를 우회하므로 그렇게 연결하지 않는다. 서로 다른 단계(예: create_pr와 revoke_token)는 별도 디렉터리를 사용하되, 단계별 진행 여부는 독립적인 관측 검증으로 결정해야 한다. 실제 token revoke나 PR/ref 조정을 수행하는 실행기는 아직 연결되지 않았다. 운영 preview의 DynamoDB CLAIMED 상태를 이 로컬 파일 계약으로 교체하지 않는다.

## 단계 제어와 고정 작업 매핑 (M75, 로컬 완료)

`writer_workflow.execute_workflow(root, review, send=..., observe=..., policy_root=...)`는 M73 수집기·M74 단일 실행권과 기존 증거 판정기를 연결한다. root와 policy_root는 서버 설정이며, review는 검토한 신원/seed/branch 관측이다. HTTP 사용자 본문이나 모델 출력으로 이 인자를 선택하지 않는다. policy_root 생략 시 기존 실험 번들을 사용하므로 과거 판정기 동작은 유지된다.

저장소·App/설치/저장소 ID·seed commit·선택 branch·branch_origin으로 고정 디렉터리를 만든다. 동일 작업 재시도는 같은 디렉터리를 쓰며 review/policy digest가 달라지면 기존 실행을 바꾸지 않는다. 실제 파일 잠금으로 동시에 한 실행자만 진행한다. 각 단계의 검증 기록은 관측 digest와 해당 M74 attempt ID/HTTP 상태에 묶이며 원본 관측 본문은 저장하지 않는다.

- `send(RequestSpec)`는 고정 method/path/JSON body와 연결된 설치 토큰으로 요청한다. 컨트롤러가 ref/target/sibling/PR 본문을 구성한다. 단계 선택이나 URL을 응답에서 가져오지 않는다. GitHub transport와 새 자격증명 준비는 아직 구현하지 않았다.
- `observe('before', stage)`는 이전 단계까지의 누적 evidence와 현재 Git snapshot을 반환한다. 현재 credential control·고정 review·과거 검증 digest·현재 snapshot이 모두 맞아야 전송한다. 관측 전후 policy 파일 digest도 확인한다.
- `observe('after', stage)`는 해당 단계까지의 누적 evidence를 반환한다. 자체 수집한 HTTP 상태와 일치해야 하며 `validate_stage()`가 parent/tree/main·대상 파일·sibling 거부 대조·PR 작성 App/파일 목록을 검증한다. 미래 단계나 여분의 최상위 필드는 거부한다. 검증 실패에는 해당 단계의 verified 기록을 만들지 않는다.
- operator branch 흐름은 branch 거부와 운영자가 준비한 branch snapshot까지 이미 검토한 prefix로 시작한다. 자동 ref 실패 후 같은 실행에서 임의로 diagnostic branch를 생성하지 않는다.

불확실한 intent는 자동 재전송하지 않는다. 검증 기록을 남긴 직후 프로세스가 죽었다면 다음 실행에서 그 기록과 새로운 관측을 대조한 뒤 남은 단계만 진행한다. 정상적인 완료/중단 후에는 result.json으로 닫아 새 실행처럼 다시 보내지 않는다.

종료 시 revoke_token을 별도 고정 디렉터리에서 한 번 요청한다. 204만으로 정리 완료를 표시하지 않고 `observe('after', 'revoke_token')`의 같은 신원에 대한 installation repositories 조회 401을 요구한다. 확인되지 않으면 cleanup=UNVERIFIED다. 이 역시 주입한 어댑터의 로컬 검증이며 실제 토큰 폐기 증명이 아니다.

CONSISTENT는 네 호출의 제공된 관측이 일치한다는 의미다. live_verified는 false이며 GitHub 출처 인증·실제 설치 권한·운영 배포를 증명하지 않는다. 다음은 실제 응답에서 필요한 성공 필드를 안전하게 추출하는 request/observation 어댑터와 새 실증의 실행 검토다. 보존된 lab/PEM/checkout을 변경하거나 새 원격 호출을 자동 승인하는 기능은 없다.
