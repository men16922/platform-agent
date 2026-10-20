# P5-E 원격 실증 실행 검토 — 2026-09-12

**현재 상태(M70):** 사용자 키 인계 후 네 호출 실측 완료: App ref 403·진단 branch 대상 200·형제 403·PR 422(0건). PR 오류 본문 미수집으로 원인 미확인. 토큰·설치·App 폐기/삭제 후 사용자가 정리를 중단했다. **lab 1367338348과 로컬 PEM/checkout 보존, 추가 삭제 금지.** 아래 M69 재개 조건은 과거 기록이다. 현재 다음 작업/발행 검토는 `docs/plans/2026-09-05-phase5-planner-runtime.md` §11·§12가 권위다.

## 2026-09-06 실행 검토 기록

상태: **M69 생성 시도·정리 완료, 실제 권한 실증은 미완료**. 본인 재인증과 실행 범위 확인 후 lab/App을 생성했으나 키 다운로드가 Chrome에서 차단됐다. 생성한 App·키·lab은 삭제하고 부재를 확인했다. 증거 `docs/evidence/phase5-writer-attempt-2026-09-06.log`.

## 당시 확인한 사실

- `gh api user`: men16922. 조회 자격증명으로 접근 가능한 소유 저장소 전체 페이지에서 `men16922/platform-agent-p5e-authz-lab`은 없었다. 해당 저장소 API도 404였다. 이것은 생성 시 이름 충돌이 없다는 보장이 아니다.
- 인증된 GitHub Settings → GitHub Apps 목록에 `men16922-platform-agent-p5e`가 없었다. 공개 App 조회 API의 404만으로 이 결론을 내리지 않았다.
- `GET /versions`: 2026-03-10과 2022-11-28 지원. 제안의 API 버전을 유지한다.
- 공식 문서는 App 등록의 single_file 경로를 지원하지만 ref 생성과 Contents PUT의 endpoint 권한표에는 Contents write가 적혀 있다. single_file만으로 자동 흐름이 되는지는 **실제 설치 토큰으로 검증할 가설**이다. 실패 시 자동 권한 확대를 하지 않는다.

근거: [App URL 등록](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-using-url-parameters), [ref 생성](https://docs.github.com/en/rest/git/refs#create-a-reference), [파일 수정](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents).

## 확인받을 정확한 원격 변경 범위

1. 새 private 저장소 `men16922/platform-agent-p5e-authz-lab` 하나를 생성하고 Actions를 끈다. 기존 seed의 가상 acme/globex YAML 두 파일만 초기 commit으로 올린다. 실제 저장소 ID/full_name을 기록한다.
2. 새 private App `men16922-platform-agent-p5e` 하나를 생성한다. single_file write는 `platform/tenants/acme.yaml` 하나, pull_requests write, 필수 metadata read. lab 저장소 하나에만 설치한다. Contents/Actions/Administration 권한·webhook·OAuth는 추가하지 않는다.
3. 새 App key 하나와 설치 토큰을 준비한다. key는 레포 밖 0600, JWT/토큰은 메모리에서 사용한다. 설치 토큰의 저장소/권한 제한을 별도 조회와 대조하고 토큰을 증거에 저장하지 않는다.
4. `p5e/20260905-01` ref 생성 → acme 한 줄 수정 → globex 쓰기 거부 → 조건부 draft PR 최대 하나를 검증한다. PR은 merge하지 않는다. App의 ref 생성이 유효하게 거부된 경우에만 운영자가 B에서 `p5e/20260905-01-diagnostic`을 만들어 나머지 시험을 분리할 수 있고 전체 결과에 diagnostic_only를 유지한다.
5. 성공/실패 모두 증거 저장, token revoke, 생성 PR close/merged=false 확인, App uninstall·App/key 삭제, **이번에 생성한 ID의 lab만 삭제**, 인증된 부재 재조회와 소유자 목록 확인, 임시 로컬 key/checkout 제거까지 수행한다. 202 Accepted는 정리 완료로 세지 않는다.

원본 platform-agent 저장소의 push/PR/CI·운영 자원·기존 App 변경은 이 범위에 포함하지 않는다. 상세 요청 본문과 중단 조건은 `review.json` 및 `docs/plans/2026-09-05-phase5-planner-runtime.md` §10을 따른다. 이름 충돌·예상 밖 권한·tree 변경이 나타나면 그 사실을 기록하고 권한을 넓혀 재시도하지 않는다.

## 실행 산출물과 판정

- 실제 생성된 ID, 신원별 method/path/status, request ID/비밀을 제외한 관측, complete tree·commit parent·main/target/sibling SHA, PR URL/작성 App/파일 목록, 정리 후 부재 증거를 기록한다.
- `README.md`의 정규화 계약으로 `judge_registry_writer.py`에 넣는다. 판정기가 supported여도 출처의 진위나 실호출 여부를 대신 인증하지 않는다.
- M65에서 JSON 중복 키·NaN/Infinity·boolean/float를 정수로 오인하던 입력 허점을 수정했다. 합성 입력 성공을 실측 성공으로 승격하지 않는다.

2026-09-06 사용자가 제시된 범위 확인 요청 이후 완료까지 재개를 지시해 위 원격 변경 범위는 확인된 것으로 처리한다. 본인 재인증 후 위 범위의 생성을 시도했으나 키 다운로드 차단으로 중단·정리했다. 아래 M69 재개 조건을 따른다.

## M69 이후 재개 조건

사용자가 App 전용 키 다운로드를 직접 완료할 수 있는 인계를 먼저 확보한다. 키 내용은 대화에 보내지 않는다. Browser Use가 chrome://downloads/를 URL 정책으로 거부했으므로 다른 브라우저 표면·CDP·내부 API로 우회하지 않는다. 생성했던 App ID 4848286·lab ID 1358934947은 삭제됐으므로 재사용하지 않는다. 새 시도에서도 같은 범위와 새 생성 ID를 대조하며 마지막 정리까지 수행한다. 이번 시도의 설치·토큰·권한 API·PR은 0건으로, single_file 가설은 여전히 판정 불가다.
