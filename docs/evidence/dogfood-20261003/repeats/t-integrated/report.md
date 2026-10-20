# T — 동일 실행 후보의 배포·거부·복구 반복

2026-10-03 12:50–13:13 UTC · 로컬 kind · 실행 O/v15, 작업 트리 R/v16.

**실행 경로의 반복 검증은 통과했다. AI 진단 기준은 여전히 미충족이다.** 정상 3회, 실행 중 새로고침 2회, 실패 후 사용자 확인 복구 2회, 제한 신원의 다른 namespace 요청 거부 2회를 같은 O/v15 소스로 수행했다. 정상 요청은 모두 claim 1·배포 호출 1이며 복구 후에도 원래 실패 요청과 이력이 남았다. 최종 Deployment는 시작과 같은 UID·전체 spec·replicas 2로 복원했다. revision은 29에서 37로 증가했다.

검증기는 [verify.py](verify.py), 결과·원본 해시는 [verification.json](verification.json), 시각 원본은 [ui-events.jsonl](ui-events.jsonl)이다. 검증기는 저장 파일만 읽으며 클러스터나 모델을 호출하지 않는다. 13:12 UTC의 최종 캡처를 현재 시점의 상시 건강성으로 해석하지 않는다.

## 실행과 측정

| 시나리오 | 요청 또는 배포 ID | 결과 | 서버 접수→저장(초) | 확인 클릭→Pod health 관측(초) |
| --- | --- | --- | ---: | ---: |
| 정상 1, r1 | DEP-8E3CDB34 | 성공, revision 30 | 4.004 | 14.331 |
| 정상 2, r0 + 새로고침 | DEP-57EEF307 | 같은 요청 복원, revision 31 | 3.134 | 13.562 |
| 정상 3, r1 + 새로고침 | DEP-6CEDCC65 | 같은 요청 복원, revision 32 | 4.728 | 13.892 |
| 실패 1, missing-r1 | DEP-D26A511A | 실패, revision 33 | 60.346 | 해당 없음 |
| 복구 1 | DEP-D26A511A | 같은 배포 rolled-back, revision 34 | 미측정 | 11.903 |
| 실패 2, missing-r1 | DEP-D34C9BB1 | 실패, revision 35 | 60.319 | 해당 없음 |
| 복구 2 | DEP-D34C9BB1 | 같은 배포 rolled-back, revision 36 | 미측정 | 8.791 |
| 제한 신원 거부 1 | DEP-8D72581B | Forbidden, 적용 없음 | 0.268 | 해당 없음 |
| 제한 신원 거부 2 | DEP-EF326505 | Forbidden, 적용 없음 | 0.245 | 해당 없음 |
| 예정된 원상 복원, r0 | DEP-430B078A | revision 37, 시작 spec와 동일 | 4.632 | 14.421 |

정상 3회의 클릭→health 중앙값은 **13.892초**, 범위는 **13.562–14.331초**다. 서버 구간 중앙값은 4.004초다. UI 실패를 관측한 시각부터 복구 health까지는 34.926/25.288초로, 사용자의 복구 확인 시간을 포함한다. 복구 직후 임시 UI 행에는 이전 실패의 60.3초가 잠시 남았지만 새로고침 후에는 실제 저장값인 **Not measured**를 표시했다. 이 숫자를 복구 실행 시간으로 사용하지 않았다.

health는 current Pod 각각에서 ready 관측 이후 발생한 kubelet `/healthz` 200 로그다. 외부 Service 경유 요청이나 의존성 건강성 검사가 아니다. 실패 rollout 동안 이전 Pod가 살아 있었으므로 장애 시간이나 MTTR로 표현하지 않는다. r0/r1은 같은 캐시 digest를 가리켜 새 앱 바이너리 검증도 아니다.

## 이전 문제와 이번 확인

비교의 앞쪽은 README의 최초 실측 및 A/B 후보 기록이다. T에서 수정 전 소스를 다시 실행한 통제 실험은 아니며 일반 성능 향상률을 계산하지 않는다.

| 항목 | 수정 전 기록 | T의 확인 | 근거와 한계 |
| --- | --- | --- | --- |
| 검토한 입력 보존 | replicas 누락 또는 이미지 URI 오타 | 정상 3회 모두 image/namespace/replicas 2 유지 | 각 normal run의 요청·tool args·실제 Deployment 대조. 준비된 이미지 경로 |
| 계획 밖 개입 | 복구 뒤 replicas 또는 이미지 재수정 필요. 전체 횟수 미계측 | 정상 3회 재입력·수정 shell 개입 0 | 입력·Review·Confirm·관측은 예정 단계. 신원 전환과 환경 준비는 별도 |
| 실패 판정 | ImagePullBackOff인데 SUCCESS | 없는 태그 2회 모두 FAILED, current Pod pull 실패 | failure run과 failing 캡처. 기존 Pod health를 새 rollout 성공으로 합산하지 않음 |
| 복구 | image만 복원되고 replicas 1 | 사용자 확인 복구 2회, 실패 전 전체 spec 복원 | recovery run의 failed→rolled-back 및 ACTIVITY 연결. 자동 복구 아님 |
| 응답 유실 | 실행 뒤 기록을 잃음 | running 상태에서 새로고침 2회, 동일 UUID 결과·실행 1회 | normal2/3 before-loss·after-loss와 click/server 시각 |
| 권한 경계 | 공통 deployer는 테넌트 격리 신원이 아님 | 기존 acme 제한 SA로 globex UI 요청 2회 거부 | 같은 소스에서 신원만 명시 전환. 공유 deployer 격리 증명 아님 |
| 직접 API 경계 | UI 적용 전 GET 거부만으로 write 거부를 단정할 수 없음 | GET 2회 및 create `dryRun=All` 2회 모두 Forbidden | credential-denials.json. 실제 create 인가를 물었으나 영속 쓰기는 실행하지 않음 |
| 승인 거부 연결 | 과거 F/G/I에서 보완 | 합성 pending 2개를 UI에서 거부, 사유·APR↔INC·조치 0 유지 | approval-records.json, 두 상세 reload. 하나는 실제 개행, 하나는 빈 사유 |
| scope 누락 | 설정 존재만으로 실제 호출 차단을 주장할 수 없음 | O의 live runner restart/rollback 모두 ScopeError, dispatch 0 | missing-scope.json. 프로세스/네트워크 dispatch audit hook 동반 |
| 진단 내용 | 근거 밖 원인·이전 건강성·복구 방향 단정 | 이번에는 모델 호출 없음. O/S 오류 유지 | [S 검토](../proposal-contract-review.md), [O 검토](../r4-snapshot-ui-review.md). R3/R4 전체 통과 아님 |

거부 전후 globex의 선택한 Deployment/Service 집합은 둘 다 비어 있었고, acme workload의 UID/spec/generation은 불변이었다. 거부 실험 뒤 원래 deployer 신원을 복원했다. 같은 두 SA의 2시간 토큰만 갱신했고 RBAC는 바꾸지 않았다. 합성 승인 요청은 alert 수집과 분석을 거치지 않았으며 `reported_by=local-dev`는 호출자 기록이지 webhook 인증 증거가 아니다.

## 재현 절차

저장 증거는 저장소 루트에서 다음 한 줄로 다시 대조한다. 결과 JSON을 갱신하지만 배포·네트워크 호출은 없다.

```sh
python3 docs/evidence/dogfood-20261003/repeats/t-integrated/verify.py
```

실제 흐름의 재현에는 기존 승인된 로컬 환경이 필요하다. 새 클론 설치 절차와 동일하지 않다. [원래 재현 절차](../../README.md)의 환경 준비를 사용하되, T의 기준은 다음과 같다.

1. `candidate-v15-snapshot-contract.json`의 287개 소스를 실행 export와 대조한다. 작업 트리의 R/v16을 O 실행 결과로 표기하지 않는다. 현재 context·SA·토큰 유효기간·기존 registry·Deployment UID/spec를 확인하고 시작 캡처를 새 경로에 보존한다. 비밀 값은 기록하지 않는다.
2. 실행 신원은 기존 `dogfood-deployer`, 제한 신원 검증은 `dogfood-tenant`다. T 관측도 전역 admin context 대신 `_workspace/dogfood-20261003/private/deployer.kubeconfig`를 명시했다. 당시 UID는 `8567c751-fc44-4e28-b63e-e21af534661f`였다. 다른 UID면 같은 자원 검증으로 이어서 세지 않는다.
3. Deployments → Deploy image에서 service `orders-api-dogfood`, namespace `acme-dev-observability`, replicas `2`, environment `dev`, image `localhost:5001/orders-api-dogfood:r1`을 입력한다. Review의 값을 확인하고 Confirm한다. 다음 두 번은 r0, r1 순서다. 각 UUID와 클릭 시각을 기록한다.
4. 두 번째·세 번째 Confirm 직후 running 상태에서 새로고침한다. 저장된 같은 UUID를 조회하여 성공을 확인하고, 각 요청 claim/배포 도구 호출이 1인지 저장 events와 대조한다. 새로고침 시각이 서버 종료 전인지도 확인한다.
5. 각 정상·복구 후 명시된 deployer 신원으로 Deployment·ReplicaSet·Pod와 current Pod 로그를 읽는다. observedGeneration, current image, updated/ready/total replicas 2, 소유 UID를 확인하고 ready 관측 이후 두 Pod 각각의 health 200을 보존한다. T의 실제 관측 스크립트는 세션의 `_workspace/dogfood-20261003/observe_integrated.py`이며 매번 새 label을 사용한다. 그 스크립트는 이 세션의 경로·UID를 고정하므로 다른 환경에 그대로 적용하지 않는다.
6. image만 `:missing-r1`로 바꾸고 FAILED 및 current Pod의 pull 실패를 확인한다. 해당 배포 행의 Rollback을 확인하고 실패 전 r1/spec/replicas 2/health로 복원한다. 이 쌍을 2회 수행한다. 원래 실패 요청은 실패로 남고 같은 DEP에 rolled-back 기록이 이어지는지 새로고침하여 확인한다.
7. r0로 예정된 복원을 한 뒤 기존 tenant 신원으로 소유 router/dashboard만 전환한다. globex namespace 요청 2회가 Forbidden인지 본다. 같은 신원의 직접 GET/create dry-run 거부와 자원 전후 상태를 별도로 기록한다. 원래 deployer 신원으로 복원한다. 권한 확대나 테넌트 자동 선택은 이 절차에 없다.
8. 기존 실험 스토어에 합성임을 명시한 pending 요청 2개를 넣어 Incidents에서 거부한다. 첫 사유에는 실제 개행, 두 번째에는 빈 값을 사용한다. 새로고침 뒤 APR/INC 연결·사유·실행 조치 0을 대조한다. 새 요청 ID를 사용하여 기존 기록을 덮어쓰지 않는다.
9. 시작/종료 Deployment의 UID와 전체 spec를 대조한다. 요청·배포·복구·관측 시각과 원본 파일 해시를 연결한다. 진단 품질은 기존 O/S 원문·판정을 유지하고 별도 과제로 다룬다.

T에서는 제품 소스와 모델 설정을 바꾸지 않았다. 모델/프록시/거부 webhook 프로세스는 유지하고, 신원 전환에 필요한 소유 router/dashboard만 재시작했다. 최초 캡처 helper의 경로 변경 실수는 기존 Q 디렉터리의 `mkdir`에서 읽기 전에 중단되어 과거 자료를 덮지 않았다(`setup-notes.json`).

T의 `make check`는 **3364 passed·2 skipped·20 warnings, 133.83초**였다(로컬 macOS·Python 3.13.5·Node 22.23.3/임시 npm prefix). [gate.log](gate.log)는 작업 트리 R/v16 검사이며 O/v15 실행 소스의 게이트와 구분한다. O 자체의 앞선 게이트는 3356 passed·2 skipped다. T 문서 검사 55개와 diff check도 통과했다. [runtime-check.json](runtime-check.json)은 두 후보 각각 287개 소스의 해시 일치를 기록한다. 원격 CI·R 후보 활성화 증거는 아니다.

## 데모와 남은 일

[72초 데모](../../demo/t-integrated-v2/local-evidence-walkthrough-72s.mp4)는 실제 화면 4장을 편집했다. **연속 녹화가 아니며 재생 시간은 작업 시간이 아니다.** [storyboard](../../demo/t-integrated-v2/storyboard.json)에 원본 해시, [QA](../../demo/t-integrated-v2/qa.json)에 영상 형식과 화면 검수 기록이 있다. 원본 `.png` 이름의 스크린샷은 CUA가 저장한 JPEG 바이트이며 내용은 바꾸지 않았다. 첫 세로 편집본은 폐기하지 않고 superseded로 보존했다.

실행 묶음과 전달물은 완료했다. 남은 우선순위는 현재 revision/실패 단계에 맞는 조회 적용 조건과 모순 관측 처리다. 전건 보류, 잘못된 원문 숨기기, 같은 사례의 프롬프트 반복으로 진단 기준을 통과시키지 않는다. **R3/R4 전체 및 R5 HolmesGPT 비교는 미완료**이며, Phase 5/4b·원격 CI·운영 환경 검증을 이번 결과로 대체하지 않는다.
