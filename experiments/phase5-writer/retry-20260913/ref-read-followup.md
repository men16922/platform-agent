# R2 ref 읽기와 파일 쓰기 권한 — M79 후속 검토

상태: 로컬 후보 비교. 원격 권한 변경·새 토큰·후속 PR 호출은 승인 또는 실행하지 않았다. 기존 PR-only scope r2-pr-diagnostic-01은 422로 종료했고 토큰은 폐기됐다.

## 확인한 사실과 남은 가설

현재 single_file write(acme)·pull_requests write·metadata read 토큰은 기존 branch에서 acme PUT 200, globex PUT 403이었다(M77). M79의 PR POST는 `not all refs are readable`로 422였고 운영자 읽기에서 두 ref와 acme 한 줄 diff·PR 0건을 확인했다. 이것은 이번 요청의 실패 이유이며 과거 버린 상세를 복원한 결과는 아니다.

[GitHub Get a reference](https://docs.github.com/en/rest/git/refs#get-a-reference)는 Contents read, 같은 페이지의 Create a reference는 Contents write를 요구한다. [Create a pull request](https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request)의 endpoint 표는 Pull requests write를 기재한다. PR endpoint 표만으로 내부 ref 읽기 성공을 보장하지 않는다. 현재 토큰에 Contents read가 없는 점은 오류와 일치하지만 권한 추가로 성공한다는 결론은 아직 가설이다.

| 후보 | 기대 효과 | 남는 경계·검증 |
|---|---|---|
| 기존 App에 Contents read만 추가하고 single_file write 유지 | ref 조회를 허용하면서 파일 쓰기 범위를 유지할 가능성 | App 설정에서 두 권한이 공존하는지 미확인. 저장소 전체 읽기 확대이며 tenant 읽기 격리를 보장하지 않음. 새 권한 조합의 acme 허용/globex 거부·PR 성공 재검증 필요 |
| 파일 writer와 ref/PR publisher 신원 분리 | 파일 writer의 기존 권한을 유지하며 PR 신원에 Contents read·PR write 부여 | 두 신원·실행 단계/증거 결합과 custody가 추가됨. PR metadata 권한은 저장소 범위이고 PR 생성자도 publisher가 됨 |
| tenant별 저장소 + Contents writer | 쓰기 자격증명의 저장소 경계와 tenant 경계 일치 | catalog/values·같은 SHA 읽기·delivery 이관/복구 설계가 필요하며 즉시 이관하지 않음 |

공유 저장소 Contents write 확대는 다른 tenant 파일 쓰기 경계를 잃으므로 채택하지 않는다. Contents read가 추가돼도 자동 ref 생성이 해결됐다고 보지 않는다.

## 다음 로컬 작업

기존 App 설정을 읽기 전용으로 확인해 single_file write와 Contents read 공존 여부 및 현재 설치 한 곳을 대조한다. 파일 writer/PR publisher 분리안과 비교하여 읽기 확대·PR metadata 범위·branch 수명주기를 검토한다. 그 결과로 선택한 신원과 정확한 권한·허용 호출·중단 조건을 확정하고 별도 실행안을 작성한다. 이 문서는 원격 권한 변경 지시가 아니다.

후속 실행안에는 검토 식별자 하나, 고정 repo/App/설치 ID·main/head, App과 토큰의 실제 권한 대조, 두 ref의 설치 신원 GET, 검증 통과 시 PR POST 최대 1회, 독립 PR/Issue 작성 App·SHA·draft·파일 목록 확인, revoke/401을 넣는다. 읽기 권한 변경과 파일 쓰기 경계 재시험은 각각 필요한 호출만 별도로 명시한다. 어떤 불확실 결과도 재전송하지 않는다. 기존 App/키/lab/branch/checkout은 계속 보존한다.

현재 M76 어댑터는 세 권한이 정확히 같아야 통과하므로 Contents read를 더한 토큰은 거부하는 것이 정상이다. 후속안을 정한 뒤 별도 policy/실행 경로를 검증하며 기존 실험의 exact-permission 가드를 느슨하게 바꾸지 않는다. production writer 연결·Lambda 배포·제출 UI는 미완료다.

## M80 설정 관측과 우선 후보 (2026-09-13)

실제 기존 App 권한 폼에서 Contents Read-only를 미저장 선택했을 때 Single file Read and write와 acme 경로가 유지되고 Save changes가 활성화됐다. 저장하지 않고 새로고침해 두 선택 권한·필수 metadata로 복귀했으며 설치 161238144의 저장소는 lab 1367740190 하나였다. 이는 폼 공존 증거이고 서버 저장/민팅/쓰기 경계 증거는 아니다.

우선 후보는 기존 App의 Contents read 추가 후 새 진단 branch에서 파일 경계와 PR을 함께 확인하는 것이다. 정확한 변경·요청·중단·보존 범위는 `experiments/phase5-writer/retry-20260913/ref-read-execution-review.md`와 ref-read-review.json에 고정했다. 승인 전 원격 권한 저장·토큰 mint·쓰기 없음. 새 App/키가 필요하지 않다. publisher 분리는 미선택 대안으로 유지한다.
