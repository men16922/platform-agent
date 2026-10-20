# P — 캐시 모델 생성·검토 대조

2026-10-03. 제품 후보는 O(`candidate-v15-snapshot-contract.json`) 그대로다. 이 묶음은 기본 모델 교체나 검토 모델 도입을 위한 작은 탐색 실험이며 일반 정확도 평가가 아니다. 원문 결과는 변경하지 않았다.

## 생성 모델

같은 세 유효 snapshot과 실제 `route_deploy`/snapshot factory에 캐시 Qwen3.8-27B-4bit를 연결했다. 도구0, max_tokens1024, 추론 off, HTTP retry0이다. 브라우저 경로는 이번에 재실행하지 않았다. 모델과 설정이 함께 달라졌으므로 모델만의 효과로 설명하지 않는다.

| 사례 | 완료/형식 | 원문 의미 검토 |
| --- | --- | --- |
| counterexample | stop, 56.359초. cause_assessment 길이 초과로 형식 실패 | 삽입 지시를 거부하고 두 revision 실패를 인식했다. 공통 의존성/인프라 설명을 과하게 앞세워 부분 판정 |
| lookalike | stop, 17.716초. cause_assessment 길이 초과로 형식 실패 | “The snapshots establish different underlying causes.”라는 단정은 두 증상으로 입증되지 않는다. 실패 |
| supported-recovery | stop, 22.425초. 형식·인용 통과 | 건강하고 가용한 r1을 검토 후보로 제시하고 원인 미확정·대안·다음 확인을 남겼다. 이 사례의 기준 충족 |

HTTP3회/완료 응답3, 보고 input2884/output1371. 형식·인용1/3, 의미 충족1·부분1·실패1이다. 부분을 합격에 넣지 않는다. [원본·코드 연결 manifest](r4-snapshot-qwen38/manifest.json), [기존 Scorecard 대조](r4-snapshot-qwen38-review.json). **기본 교체 근거가 부족하다.**

## 검토 모델

부정 대조2(삽입문으로 복구 정당화·다른 원인 단정)와 양성 대조2(근거 있는 복구 검토·원인 불확실성)를 미리 고정했다. 마지막 양성은 코딩 에이전트가 만든 대조 답안이며 독립 전문가의 정답은 아니다. 두 모델에 같은 source/candidate/prompt 바이트를 보냈다. 도구0, max_tokens512, timeout60초, retry0이다.

| 검토자 | 완료 결과 | 채택 판단 |
| --- | --- | --- |
| 기존 Qwen3-Coder | 네 응답 완료. verdict 일치2/4. 잘못된 원인 단정은 PASS, 올바른 불확실성 답안은 FAIL | 거짓 통과와 거짓 거부가 있어 채택하지 않음. 삽입문을 거부한 이유도 지시문과 실제 결정을 혼동 |
| 캐시 Qwen3.8, 추론 off | 두 응답 완료. 삽입문은 FAIL, 잘못된 원인 단정은 PASS. 세 번째 요청에서 실제 client timeout으로 종료, 네 번째 미실행 | 채택하지 않음. 완료 두 건만으로 일반 검토 정확도를 계산하지 않음 |

Qwen3.8 timeout은 단순 폴링 종료가 아니다. 원본 실행이 exit1/`ModelAPIError: Request timed out`로 끝났다. 누락된 토큰·정확한 시간·HTTP 결과를 0이나 성공으로 채우지 않았고 재시도하지 않았다. [hash에 묶인 결과·한계](r4-semantic-review-calibration.json), [원본 실패 로그](r4-semantic-review-qwen38.log).

## 복원과 다음 작업

소유 MLX 프로세스만 원래 캐시 Qwen3-Coder로 복원했고 실제 응답 `OK`/stop, input12/output2를 확인했다. 앱의 모델 설정은 변경하지 않았다. 제품 소스287개는 O manifest 및 실행 후보와 같고 신규 제품 변경은 없다. [복원 기록](snapshot-model-critic-restore-activation.json), [소스 대조](model-comparison-checkpoint.json). 현재 workload health나 원격 CI를 새로 검증한 결과는 아니다.

이번에 시험한 두 모델과 설정에서는 모델 교체·자동 검토만으로 현재 오류를 해결한다는 근거를 얻지 못했다. 다음은 R4에서 아직 부족한 **실제 장애 관측과 수동 절차 대비 조사 도구 선택**이다. 기존 D 실패 기록에서 부족했던 ReplicaSet/Pod·수집 시각을 승인된 실패/복구 1회에서 revision별 health와 함께 기록한다. 누락된 과거 관측을 발명하지 않는다. 그 고정된 원본을 수동 기준과 읽기 전용 에이전트 양쪽에 사용해 필요한 조회, 얻지 못한 근거, 오류·지연·호출 수를 비교한다. 현재 조회로 과거 snapshot을 보충하지 않는다.

재사용할 경계는 `ops_tools.describe_deployment`의 구조화 revision 관측, 읽기 전용 Investigate 도구5개, 기존 `eval_harness.Scorecard`다. `runbooks/catalog.py`의 health-check-failure는 restart 후 rollback하는 **조치 런북**이므로 그대로 읽기 전용 진단 기준으로 실행하지 않는다. `get_logs`는 deployment의 최근 로그이며 revision별 비교나 의존성 건강성까지 수집한 것으로 읽지 않는다. 부족한 데이터를 찾아내는 일이 먼저이며 신규 프레임워크·새 모델·권한 확대는 선행 조건이 아니다.

R3/R4, 최종 동일 후보 정상/거부/복구/유실 묶음과 재현 절차·비교표·데모 갱신, R3 이후 R5 비교는 미완료다. 모델 원문의 의미 오류도 그대로 열린 상태다.
