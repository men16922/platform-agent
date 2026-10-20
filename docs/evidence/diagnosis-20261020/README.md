# 진단 객체 일관성 수정과 전후 대조 — 2026-10-20

목표는 단일 환경 배포·검증·복구의 남은 진단 품질이다. **코드의 거짓 완료 판정은 수정했으며, 모델 진단/R3/R4 전체·R5는 미완료다.** 원래 실패 응답은 모든 출력 파일에 보존했다. 이 자료는 현재 클러스터 health나 운영 배포·일반 정확도를 입증하지 않는다.

## 재현과 변경

```sh
PYTHONPATH=. python experiments/dogfood-diagnosis/consistency-resume/measure.py /tmp/diagnosis-measure-new.json
PYTHONPATH=. python experiments/dogfood-diagnosis/consistency-resume/review.py docs/evidence/diagnosis-20261020
```

두 번째 명령은 `paired-review.json`이 있으면 덮어쓰기를 거부한다. 검토 함수 `review(directory)`를 직접 호출하면 파일을 변경하지 않고 재검증할 수 있다. 모델 실험은 `replay.py`의 frozen-tool 하네스이며, 실행 대상/최대 토큰/요청 수/사용 모델은 각 manifest에 고정된다. 원본을 다시 조회하거나 실패 입력을 고쳐 쓰지 않는다.

| 구분 | 수정 전 | 수정 후 | 증거 |
| --- | --- | --- | --- |
| 집계만 완료·current Pod 실패 | 거짓 `rollout_complete=true` | 불일치 값 보존·완료 false | before.json / after.json |
| 실제 Q 실패 / 복구 관측 | 실패 false / 복구 true | 각각 유지, source SHA 동일 | before.json / after.json |
| 일관된 양성 복구 | revision1 review_candidate | 유지, 실행 미승인 | before.json / after.json |
| S 원래 모순 | 모순 표시 없음 | reported1 / observed0와 재조회 필요 | after.json / ui-reports.json |
| 현재/이전 컨테이너 로그 | 적용 조건 없음 | 현재 state와 이전 terminated 관측을 분리 | after.json |

일관성 평가는 원자적 읽기의 증명이 아니다. 차이는 controller lag나 수집 누락일 수 있어 근본 원인으로 단정하지 않는다. Ready가 minReadySeconds availability를 뜻하지 않으며, readiness probe가 없는 실제 Q 복구는 rollout 완료와 application/external health 미확인을 함께 보존한다.

## 모델 대조: 품질 미충족

`paired-review.json`은 기존 `Scorecard`를 재사용한다. 전체 원문을 읽은 코딩 에이전트의 명시적 판정이며 독립 전문가/교정된 critic이 아니다. 기대 기준은 `expectations.json`, 판단·인용·응답 hash는 `semantic-reviews.json`에 있다. 원본은 `replay-before/`, `replay-after/`다.

| 항목 | 전 | 후 |
| --- | --- | --- |
| 동일 raw 입력/실제 HTTP·한 frozen describe 경계 | 7/7 | 7/7 |
| 응답 완료 | 6/7 | 4/7 |
| 의미 충족 | 0/7 | 1/7 |

동일 모델 revision·temperature0·1024토큰·요청2·도구1·retry0. 실제 전후 HTTP는 28회다. 단일 describe가 고정된 실험이며 실제 도구 선택·인증 UI·전체 supplied-text snapshot 진단의 성공을 입증하지 않는다. 프롬프트와 구조화 입력의 변경을 함께 평가한 후보 대조이므로 각각의 기여를 분리한 인과 실험도 아니다. 작은 적응적 탐색 표본의 비율을 일반 정확도/성능 개선으로 인용하지 않는다.

후보는 삽입문·시작 전 로그·이전 scale-down 오독·이미지 이름을 원인으로 읽는 오류를 남겼다. `lexical-neutral/`은 **이미지 이름만** 바꾼 합성3건이다. 상태/계수/복구/조회 근거는 같고 완료 사례의 invalid-image 추정은 사라졌지만, 다른 오류가 남았다. `lexical-review.json` 참조. 이 대조군으로 원래 실패를 대체하지 않았다.

## 환경·검증 경계

- Node22 Homebrew의 simdjson dylib 누락과 npx의 전역 경로를 재현했다. 공식 Node22.23.3 tar SHA256 `72d5d8832b41c9d9646197af614ffd751406ea4d215060eb91b98864e1919a3e`를 확인하고 `_workspace/diagnosis-20261020/npm-prefix`를 사용했다. 전역 설정 변경 없음.
- 관련54개 검사·TypeScript 검사가 통과했다. `related-final.log`, `typescript.log`. Chrome에서 실제 projection/component와 현행 Tailwind CSS를 렌더·새로고침 확인했다. `browser-review.json`, `review.html`. 인증된 대시보드나 라이브 클러스터 검증은 아니다.
- 초기 전체 실패는 각각 툴체인(npx emit 실패)과 새 테스트를 반영하지 않은 문서 gate 숫자였다. 로그를 삭제하지 않았다. 최종 전체 gate 결과는 `gate-final.log`가 권위다.
- 과거와 동일한 Coder revision을 task-local 폴더로 복원했다. `model-provenance.json`은 모든 LFS SHA 대조 결과다. 모델 weights/캐시는 Git 산출물에 넣지 않았다. 유료 API/cloud 변경 없음. 초기 V는 cluster 조회가 없었고, 후속 W의 현재 kind 읽기는 아래 실제 failed run에 별도로 기록한다.
- 실험용 MLX/proxy를 기존18090/18091에 기동해 다른 로컬 Docker 클라이언트 요청이 섞였다. **시간 수치는 성능 비교에서 제외한다.** 한 변수 반복 억제 실험 중 혼합 batch에서 upstream worker가 `NoneType` 예외로 종료됐고 proxy502가 보존됐다(`repetition-penalty/q-failing.json`, `mlx-batch-error.log`). 해당 모델/proxy만 종료하고 전용18190/18191로 분리했다. 실제 paired 입력/자신의 호출 경계는 파일로 검증되지만, 앞선 서버를 독점 사용했다고 주장하지 않는다.
- 반복 억제는 모델 권장값과 MLX의 실제 defaults 차이를 보고 별도로 측정한다. `penalty-isolated/`의 raw/manifest와 후속 검토가 권위이며 원래 진단 실패를 대체하지 않는다. [Qwen 모델 카드](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct)의 권장값은 정확도 보장이 아니다.

초기 V source는 `source-manifest.json`과 `evaluated-source/`, 최종 W는 `w-source-manifest.json`과 `w-final-source/`에 고정했다. 기존 앱/기본 포트는 전환하지 않고 W만 격리 API18778에서 실행했다. 기존 WIP·lab/App/키/PR을 보존했다. commit/push/cloud 배포/삭제는 없다.

## W 실제 factory/router·UI 연결

`investigation_proposals.py`를 read-only factory/router와 기존 inspection 결과에 연결했다. 일반 모드의 도구/권한·supplied-text snapshot은 전환하지 않았다. 정상/단계 위반/잘림/재수집, 일반·streaming·SQLite actor별 재조회, UI의 원래 응답 보존을 검사했다. 최종 전체 gate는 `production-gate.log` → **3380 passed, 3 skipped, 20 warnings, 119.20s**다. skip2는 온프렘 serverless 미지원, skip1은 기존 Terraform 도구/초기화 부재다.

`production-contract-final/`은 같은7개 raw를 production factory/router에서 실행한 기록이다. 응답7완료, 제안6 적용 조건 통과, 불일치1은 코드 재수집 요구다. 그1건의 모델 source ID 오타는 원문에 남으며 모델 성공으로 세지 않는다. `production-contract-review.json`은 출처/HTTP2·frozen describe1/최종 소스 hash와 코딩 에이전트의 제안 검토다. V 자유 서술과 W는 응답 계약/역할이 다르므로0→7 정확도 향상으로 인용하지 않는다.

초기 W는 복구 후1건에서 기존 prose-section 지시와 JSON 형식을 함께 받아 혼합 출력으로 거부됐다. 형식 지시 하나를 제거한 `production-format-control/`과 최종7건을 보존했다. `review-contract-final.html`은 실제 W 모델 결과를 실제 projection/component로 렌더·새로고침 확인한 Chrome 자료이며, 인증 앱이나 라이브 클러스터 UI가 아니다.

## 실제 현재 workload 읽기: 실패를 보존

원래 제한 토큰이 만료돼 Unauthorized였다. 원래 SA UID가 동일함을 확인하고1h 토큰만 task-private0600 파일로 갱신했다(`live-identity-refresh.json`). 원래 credential·RBAC는 보존했다. 모델/proxy는 전용18190/18191, 읽기 전용 task API는18778이며 기존 앱 런타임은 바꾸지 않았다.

`live-api/`는 실제 현재 kind workload와 전체 Investigate5를 사용한 HTTP/SSE·SQLite 재조회다. describe/rollout_status/list_pods3요청은 target guard를 통과했고 list_namespaces1요청은 cluster-wide 범위라 dispatch 전에 거부됐다. 따라서 run은 **failed**다. 관측과 제안이 존재해도 정상 종단 통과로 세지 않는다. 같은 request 재조회에 추가 도구 실행은 없었고 다른 actor는404였다. `live-api/review.json`, `verification.json`, `persisted-run.json`, `tool-calls.jsonl` 참조.

현재 Deployment UID·전체 spec·rev37/replicas2는10-03 T 최종값과 같았고 workload 변경0이다. rollout 완료와 app/external health 미확인을 함께 유지한다. 다음은 실제 scope guard와 광고한 도구 schema/설명의 불일치 가설을 먼저 구분하는 측정이다. 실패/거부를 숨기거나 도구 수를 줄여 동일 조건 성공으로 바꾸지 않는다. `resume-checkpoint.json`에 소유 프로세스와 정확한 재개 위치를 기록했다. R3/R4 전체·원문 snapshot·인증 UI·R5는 미완료다.


## 범위 설명 정렬 대조와 실제 UI 읽기

`scope-selection/`은 같은5개 tool parameter schema·사용자 요청·모델 설정에서 실제 scope 정보를 tool hints/docstrings에만 추가한 대조다. 기존 설명에서는 list_namespaces를 요청했고 정렬 후 대상 reads만 요청했다. 둘 다 dispatch0. 이 한 쌍을 일반적인 모델 지시 준수율로 해석하지 않는다.

`live-api-scoped/review.json`은 설명을 맞춘 API18779와 W 격리 dashboard13001의 local-dev Credentials 로그인 실증이다. 각각 succeeded·읽기4회, 동일UUID 재조회/새로고침 추가read0·raw JSON 유지·다른actor404·기존 workload UID/full spec/rev37/replicas2 불변이다. 첫 failed run은 `live-api/`에 그대로 남았다. GitHub OAuth·tenant 격리·외부 health 증명은 아니다. [실제 UI 새로고침 결과](live-api-scoped/ui-reloaded.png). helpers는 당시 task-only 서버용이며 이미 존재하는 evidence 경로/DB를 재사용해 덮어쓰지 않는다.

## Supplied snapshot: 재현된 의미 실패와 미채택 계약

`snapshot-resume/`는 원래7입력을 현재 제품 경로에 재생했다. 모델3/코드 제외4, 의미1충족·1부분·1실패. `snapshot-injection-control/`에서 지시문만 제거하자 잘못된 recovery candidate가 not_established로 바뀌었다. 수정된 입력으로 원래 오류를 대체하지 않았다.

`snapshot-support/`는 역할별 정확인용 schema/validator만 추가한 실험이며 제품 변경은 없다. 의미 오류는 유지됐다. `unsupported-role-control.json`은 지시문을 건강성/복원 가능성 role에 붙여도 계약을 통과하는 반증이다. 형식 거부·인용 통과를 의미 정확도로 세지 않았고 후보는 미채택이다. 원문·SHA·코딩 에이전트 검토는 `snapshot-resume-review.json`이 권위다. 사용자가 기존 Qwen 고정을 확정했다. 다른 모델 비교는 수행하지 않는다.


고정 Qwen의 별도 evidence-to-claim witness도 `snapshot-witness/`에3건 저장했다. 이는 recovery draft/질문을 주지 않는 추가 모델 호출 프로토콜이며 기존 한 호출 진단과 같은 조건의 정확도 비교가 아니다. 응답3완료지만 key 내부 공백으로 binding0/3, 그와 별개로 counterexample은 두 revision timeout을 previous healthy의 supported 근거로 인용했다. 자동 key 보정/소스 정제 없이 원문 보존·미채택이다. 다음은 모델 고정 상태에서 독립 검사가 가능한 구조화 관측과 명시적 사람 검토 경계의 설계이며, 기존 declared-text 의미 기준을 통과했다고 세지 않는다. `snapshot-witness/review.json` 참조.


## 고정 Qwen 온도 대조·사용자 일시중지

`snapshot-temperature/review.json`은 동일3입력·3seed·온도0/0.7의18응답을 보존한다. 온도0은9완료/인용9통과지만 기존 의미 오류 유지,0.7은6완료/3잘림·유효 진단0이라 미채택이다. 각 case/온도에서 서로 다른seed의 raw hash가 동일했다. 요청seed 전달은 확인했지만 원인은 미확정이며 독립 확률 표본으로 세지 않는다. 사용자 요청으로 paused. 재개 첫 행동과 소유 프로세스·보존 범위는 `pause-checkpoint.json`, 사용성 계획 §12가 권위다. 제품11소스 hash와 직전 전체3380/3 baseline을 유지하며 이번 전체gate 재실행/새 cluster 조회는 없다.
