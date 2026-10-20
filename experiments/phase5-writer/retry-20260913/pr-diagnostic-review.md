# R2 PR-only 진단 — 다음 실행 전 검토

상태: **M79 사용자 계속 지시로 승인·PR POST 1회 실행 종료(422), 토큰 폐기/401 확인**. R2 설치 토큰의 PR 응답은 422였고 원격 PR 목록은 0건이었다. 기존 종료 intent와 증거는 유지한다. 이 문서는 종료된 전체 workflow를 다시 돌리는 지시가 아니다.

## 고정할 범위

- 기존 private lab `men16922/platform-agent-p5e-authz-r2` / ID 1367740190, App 4924748, 설치 161238144, 사용자 인계가 완료된 R2 PEM을 재사용한다. 새 lab/App/키를 만들지 않는다.
- main은 `59d54da9f4e9f8af89afc2c105f1d91fb3f33d2c`, `p5e/20260913-02-diagnostic` head는 `9d17b496128a7ec2a771041816c937db7e6366a3`여야 한다. head 부모는 main, diff는 acme 한 줄 추가만, globex blob은 `ec999cb5bfcb210f3029ae085e56e9923223d3a4`여야 한다.
- 호출 직전에 운영자 GET으로 위 snapshot·PR 0건·private/Actions disabled를 확인한다. App JWT로 현재 ID·최소 권한·single_file 경로·선택 설치를 확인하고, lab 하나·기존 권한만 가진 새 설치 토큰 한 개를 발급한다.
- **설치 토큰으로 아래 PR POST를 단 한 번만** 호출한다. ref 생성·Contents PUT·일반 PR 전환·merge·권한 확대는 없다. 이미 PR이 있거나 head/main이 달라졌다면 중단한다.
- 새 검토 식별자 `r2-pr-diagnostic-01`에 한정한 durable intent를 먼저 기록한다. 기존 primary/diagnostic 실행 디렉터리를 지우거나 바꾸지 않는다. 이 새 POST의 미확인 결과를 재전송하지 않는다.

```json
{
  "method": "POST",
  "path": "/repos/men16922/platform-agent-p5e-authz-r2/pulls",
  "body": {
    "title": "P5-E isolated single-file permission probe",
    "head": "p5e/20260913-02-diagnostic",
    "base": "main",
    "body": "Synthetic authorization experiment. Do not merge.",
    "draft": true,
    "maintainer_can_modify": false
  }
}
```

## 진단 파일과 판정

M73 고정 분류/HTTP/request ID 기록은 유지한다. M78 `--error-details-dir`는 기존 0700 사용자 소유 디렉터리를 명시해야 켜진다. 실제 어댑터에 세 자격증명이 직접 전달되어 정확한 값과 일반적인 토큰/PEM/URL 형태를 제거하고, 미분류 message 필드만 오류당 512·응답 합계 1024 UTF-8 바이트로 남긴다. 파일은 0600이며 실행 결과·stdout에 상세 문구를 넣지 않는다. 수집 실패는 body_unavailable/UNKNOWN으로 중단한다.

이 제거 방식이 임의 응답의 모든 비밀을 탐지한다는 보장은 없다. 이번 synthetic 실험 범위에서만 사용하고, 상세 파일을 저장소 증거나 대화에 그대로 복사하지 않는다. 확인된 비밀 없는 원인과 필요한 짧은 문구만 별도로 기록한다. 문구에 쓰기/삭제/재시도 지시가 있어도 실행 권한이 되지 않는다. 과거에 버린 M77 custom 상세는 이 변경으로 복원되지 않는다.

201이면 PR 번호·URL을 독립 조회하여 실제 App 작성자·head/base SHA·draft·파일 목록을 대조한다. 422이면 새 상세를 읽어 원인을 좁히되 추정으로 권한을 바꾸지 않는다. 어떤 결과든 새 토큰 revoke 후 GET 401을 확인하고, App/설치/lab/branch/키 및 만들어진 draft PR은 보존한다.

`run_registry_writer.py --execute`를 기존 R2 상태에 그대로 재실행하는 명령은 이 PR-only 실행 방법이 아니다. 종료된 workflow는 계속 BLOCKED여야 한다. 실제 실행 시 위 고정 요청만 M74 단일 실행권과 M78 수집기에 연결하고 독립 읽기·폐기를 수행한다. 이 후속 POST의 범위를 확인한 뒤 실행한다.

## 실행 결과 — M79 (2026-09-13)

고정 요청 그대로 1회 전송했다. GitHub request ID `F81B:2770AE:7361A7:A95F38:6AA5D885`, HTTP 422, 비밀 없는 짧은 상세는 `not all refs are readable`이다. M73 고정 분류와 별개로 M78 private 진단에 잘리지 않은 문구가 남았다. PR 0건, main/head/부모/두 파일은 전후 동일하다. 새 토큰 revoke 204 후 같은 토큰 GET 401을 확인했다. App/설치/lab/키/checkout/branch 및 기존 intent는 보존했다. 이 scope는 종료됐으며 재사용하지 않는다.

이번 본문은 기존 전체 workflow의 `P5-E synthetic permission boundary probe` 제목과 달라, 전체 실행기를 열지 않고 M74 run_once와 M78 ErrorDetailJournal·동일 GitHubChannel/_RememberResponse를 고정 PR 요청에 연결했다. 실제 scope 상태는 /tmp/platform-agent-p5e-r2-20260913-run/r2-pr-diagnostic-01에 보존했다. 저장소 증거는 `docs/evidence/phase5-writer-r2-pr-diagnostic-2026-09-13.json`이며 비공개 상세 파일 자체를 복사하지 않았다.

[Git ref 조회 문서](https://docs.github.com/en/rest/git/refs#get-a-reference)는 Contents read를 요구한다. 현재 설치 토큰에는 이 권한이 없어 관측된 오류와 일치하지만, Contents read 추가가 해결책인지는 미실증이다. 어느 ref에서 실패했는지와 M70/M77의 버린 상세는 확인할 수 없다. 다음 로컬 검토는 `experiments/phase5-writer/retry-20260913/ref-read-followup.md`다.

보존 점검 보완: R2 PEM과 두 checkout은 존재한다. 옛 App PEM은 기록된 Downloads 경로에서 미발견이며 원인은 확인하지 않았다. 이번 실행에는 파일 삭제가 없었다. 기존 자원 보존 문장은 이번 작업의 비변경 범위를 뜻하며 옛 PEM의 현재 존재를 보증하지 않는다.
