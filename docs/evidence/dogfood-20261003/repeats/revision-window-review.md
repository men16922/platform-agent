# Q — 실제 실패·복구의 관측과 조사 도구 비교

2026-10-03. O 제품 후보의 소스287개는 그대로다. P의 모델 교체/critic 미채택 이후, 승인된 `orders-api-dogfood` 실패·복구 1회를 실제 Chrome에서 실행했다. 같은 신원의 2시간 토큰만 갱신했고 RBAC는 변경하지 않았다.

## 실제 상태와 사용자 기록

| 단계 | 현재 관측 | 사용자 기록 |
| --- | --- | --- |
| 시작 | r0/revision27, 두 Pod | 원본 Deployment/spec·RS/Pod·로그 수집 |
| 실패 | missing-r1/revision28, 새 Pod의 ErrImagePull→ImagePullBackOff, 이전 두 Pod 유지 | 요청3173b5a5…의 claim1/deploy1, 60.638초 후 failed, DEP-06D6643F |
| 조사 | 읽기 전용 rollout_status·describe_deployment·list_pods 각1. 변경0 | 요청fb3cdde2… claim1, 22.723초, 모델 응답2·input4562/output540. 도구 하나의 timeout도 실패로 보존 |
| 복구 | 기존 UI의 명시적 rollback1. r0/revision29, 원래 UID·전체 spec·복제 수2 복원 | 같은 DEP-06D6643F가 rolled-back으로 새로고침 뒤 유지. 원래 실패 요청/이력도 보존 |

복구 확인 클릭은11:10:53.715UTC, 복구 뒤 관측은11:11:13~14UTC다. 두 Pod에 확인 클릭 이후의 `/healthz` HTTP200 로그가 각각 남았다. **이전 Pod는 실패 중에도 실행 중이었으므로 서비스 중단이나 MTTR을 측정한 실험은 아니다.** readinessProbe/의존성·외부 서비스 health가 모두 증명된 것으로 읽지 않는다. 현재 구조화 판정도 이전 revision 건강성은 미확인으로 유지한다.

[실행·복구·해시 검증](revision-window-verification.json), [동일 deployment ID의 원본 기록](q-revision-window/cycle-records.json), [복구 화면](q-revision-window/recovery-ui.png).

## 같은 모델 입력으로 수동 기준 대조

[manual-shared-input.json](q-revision-window/manual-shared-input.json)은 모델이 실제로 받은 도구 결과 세 개를 그대로 담는다. 아래 기준은 코딩 에이전트가 이 원본을 읽어 작성했으며 독립 전문가나 사람의 작업 시간 측정이 아니다. 후속 운영자 조회를 모델에게 이미 주어진 정보처럼 소급하지 않았다.

| 평가 항목 | 수동 기준 | 실제 모델 |
| --- | --- | --- |
| 새/이전 revision 구분 | 새28은 pull 실패, 이전27은 Pod2개 Running. 이것이 새 rollout 성공을 뜻하지 않음 | 올바르게 구분 |
| 원인·health·복구 | 공유 입력만으로 image 부재/인증/네트워크 중 하나를 확정할 수 없음. 이전 health·복구 후보 미확인 | 불확실성을 명시하고 rollback을 승인하지 않음 |
| 조회 선택 | describe의 revision 근거가 핵심. current Pod의 waiting message/이벤트로 pull 실패를 좁힐 필요 | 허용된 도구3개 사용. rollout_status의 추가 10초 대기는 상세 오류를 주지 못함 |
| 다음 확인 | 시작하지 못한 현재 컨테이너는 애플리케이션 로그가 없을 수 있으므로 Pod status/UID별 이벤트를 먼저 확인 | “Fetch logs from the pod(s) to confirm the image pull error.”를 제안. 실제 새 Pod 로그 조회는 waiting 오류로 실패 |

사실 구분과 불확실성은 이 한 사례의 기준을 충족했다. 도구 선택/다음 조회는 부분 판정이며 **전체 의미 판정은 부분, 합격으로 세지 않는다.** [원문과 hash에 묶인 검토](q-revision-window/manual-comparison.json). 과거 삽입문·유사 증상 사례의 실패를 이 사례로 상쇄하지 않는다.

## 추가 관측으로 확인한 병목

모델 호출 전후에 Deployment→ReplicaSet→Pod의 UID/소유 관계와 각 수집 시각을 저장했다. 모델에게 전달된 describe 결과에는 `ImagePullBackOff`만 있었지만, **collector가 이미 읽은 Pod JSON의 waiting.message에는 해당 이미지 reference를 찾지 못했다는 원문**이 있었다. 현재 `summarize_deployment`에서 이 진단 자료가 빠진다. 새 도구·권한·프레임워크에 앞서 이 손실을 해결할 수 있다.

운영자 추가 조회의 Pod 이벤트도 같은 이미지의 NotFound를 기록했다. 기존 r0 Pod의 Unhealthy 이벤트 마지막 시각10:50:57UTC는 이번 실패 이전이므로 현재 실패로 세지 않았다. 최근30초 로그의 HTTP200과 오래된 경고를 섞지 않는다.

레지스트리 첫 요청은 Docker manifest만 허용해 r0의 OCI index를404로 돌려받았다. 응답 본문이 Accept 불일치를 명시했고, OCI-aware 후속 조회에서 missing-r1은 manifest404, r0는 index200이었다. 첫 실패도 보존했다. **상태 코드404 하나를 태그 부재의 증명으로 쓰지 않는다.** [첫 응답](q-revision-window/registry-observation.json), [헤더 보완 후 응답](q-revision-window/registry-observation-oci.json). 이 조회는 모델의 세 도구에 포함되지 않았으며 두 경로의 지연을 직접 비교해 생산성 향상을 주장하지 않는다.

다음은 기존 describe 경로에서 이미 읽은 현재 Pod의 identity와 waiting 원문을 **신뢰되지 않은 진단 자료**로 보존하는 작은 변경이다. 구조화 health/복구 판정은 계속 분리하고 원문 문자열로 원인을 확정하거나 승인을 만들지 않는다. 이 고정 관측과 기존 삽입문·양성·불확실성 사례를 재생해 실제 설명 변화부터 확인한다. 최종 같은 후보 시나리오 묶음·재현/비교/데모 갱신 및 R5는 여전히 남아 있다.
