# PROGRESS_LOG archive — 2026-10

2026-10-03 진입점 예산을 위해 이동한 당시 기록. 최신 상태는 docs/PROGRESS_LOG.md와 docs/NEXT_PLAN.md 참조.

## 2026-10-03 — 실사용 점검: 빈 기록·조회·상태 누락의 거짓 성공 수정

- Status: R0 환경/신원과 실제 Qwen→Chrome 조회 경로를 실측했다. 배포 baseline·R1/R3 전체는 미완료다.
- Changed: 고정 490 checks/4 successful/가짜 AWS 검증·추세를 제거하고 기록 기반 표시로 바꿨다. 읽기 도구만 실행한 요청은 ACTIVITY만 저장하며, 누락된 배포 status는 unknown으로 유지한다. 증거·재현 초안은 docs/evidence/dogfood-20261003/README.md.
- Verified: kind 3/3 Ready, 기존 테넌트 신원의 globex 읽기 실제 Forbidden, 공통 deployer Secret 권한 없음. 실제 동일 조회 전후 DEPLOY 1→0·ACTIVITY 1 유지 및 Chrome 새로고침 확인. 합성 상태 fixture 성공 2→1/unknown 보존. 회귀 2 failed→관련 18 passed, tsc 통과. 전체 게이트는 문서 수 갱신 누락/분량 초과 각 1건을 보완한 뒤 **3255 passed·2 skipped·21 warnings**, 121.61초(로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix).
- Blockers: orders-api/복구 revision 부재, 현재 Pod 템플릿 restricted 정책 거부(server dry-run). 테넌트 신원은 Service create 불가, 공통 deployer는 테넌트를 구분하지 않음. 기존 workload 미변경, RBAC 확대·원격 변경·커밋/푸시 없음.
- Next: 정책을 완화하지 않는 실험 서비스 baseline을 준비하고 정상/거부/복구/응답 유실을 실제 사용자 흐름으로 측정한다. 모델의 반복/혼합 언어와 Agents 고정 kagent READY 표시는 별도 재현 후보다.

## 2026-10-03 — 배포 후보 준비와 heartbeat의 실행 취소 수정

- Changed: onprem PodSecurity 필드·샘플 숫자 USER를 보완했다. SSE heartbeat는 한 producer task와 bounded queue로 실행을 유지한다.
- Verified: 정책 회귀 red→green, Pod server dry-run 통과. 캐시 기반 네트워크 차단 빌드와 non-root/read-only health 200. heartbeat 취소 red, 첫 수정의 AnyIO scope 실패 뒤 관련 45 passed. make check **3257 passed·2 skipped·20 warnings**, 119.91초(로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix).
- Blocker/Next: 자동 승인 심사가 로컬 API/kind 조회를 네트워크 범위 밖으로 거부했다. 실행안은 docs/evidence/dogfood-20261003/README.md 말미. 범위 확인 뒤 orders-api-dogfood 1개 배포·복구·유실 검증. push/실제 배포·RBAC 변경 없음.

## 2026-10-03 — 응답 유실 후 결과 조회와 중복 실행 방지

- Observed: SSE 관측을 닫은 뒤 로컬 작업은 완료됐지만 기록이 사라졌다. 수정 후 같은 thread/file 실험은 결과 저장·조회 성공, 재요청 뒤 실행 1회다. 실제 kind 실패 실험은 아니다.
- Changed: 기존 SQLStateStore에 원자적 요청 ID claim을 추가하고 실행을 관측 연결과 분리했다. 같은 ID는 조회만 하며 소유자/입력 불일치를 거부한다. 프로세스 유실·저장 실패는 unknown, 자동 재실행 없음. Dashboard는 세션 신원 전달·ID 보관·새로고침 GET 복구를 연결했다.
- Verified: 새 회귀 12개 포함 관련 27 passed·tsc 통과. make check **3269 passed·2 skipped·20 warnings**, 118.07초(로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix). 전체 로그는 docs/evidence/dogfood-20261003/durable-run-gate.log. 근거/제약은 같은 폴더 README.md.
- Next: 네트워크 실행 범위 승인 후 새 후보를 소유 서버에 반영하고 실제 Chrome 새로고침/단절, orders-api-dogfood baseline·정상/거부/복구를 검증한다. 현재 서버 미반영·실제 UI/클러스터 검증 미완이며 기존 승인 질문은 대기 중이다.
- Goal audit: 동일 네트워크 승인 경계가 3턴 지속되어 blocked 전환 기준을 충족했다. 직전 턴은 구현/검증 진전, 이번 턴은 현재 해시 9개·로그·미완료 조건 재확인이다. 세부 판정은 docs/evidence/dogfood-20261003/blocker-audit.json. 실제 사용자 흐름·반복 측정·데모는 미완료다.

## 2026-10-03 — 로컬 실증 승인과 curl 일괄 금지 해제

- User: 기존 로컬 실증 범위를 명시 승인하고 심사 기준 열기를 요청했다. 재승인을 묻지 않는다.
- Found/Changed: project overnight.rules가 URL 무관하게 curl을 forbidden 처리했다. 해당 규칙만 제거하고 TextEdit로 열었다. 새 blanket allow는 없으며 무인 runner의 network_access=false와 다른 금지는 유지한다.
- Verified: codex-cli 0.160.0의 execpolicy check 9건 통과. 디스크 localhost curl은 매칭 규칙 없음, 기존 금지 8건 유지. 실제 같은 curl은 현재 세션의 옛 사유로 다시 거부됐다. 공식 문서는 시작 시 로드/재시작을 요구한다. `docs/evidence/dogfood-20261003/network-approval-and-policy.json` 참조.
- Correction/Runtime: curl 금지를 네트워크 전체 차단으로 해석한 것은 틀렸다. 승인된 별도 kubectl·Docker·Chrome 작업은 실행됐다. 기존 제한 SA 토큰 갱신·새 후보/소유 서버 반영·r0 baseline 생성 뒤 실제 Qwen r1 배포가 revision 2·2/2 Running·health 200으로 완료됐다. DEP-102149DB는 새로고침 후 유지되고, 조회 도중 새로고침은 같은 요청 ID로 복구됐다. 서버 기록 구간 7.342초/9.311초이며 사용자 완료시간 측정은 아니다.
- Next: goal active. docs/evidence/dogfood-20261003/approved-runtime-verification.json 참조. 새로 발견한 화면 0s 오류, 실패/복구/거부/배포 유실·반복 측정·데모를 계속한다. 동일 승인을 다시 묻지 않는다. health 포트 브라우저 탐색 차단은 우회하지 않았으며 임시 port-forward만 종료했다. RBAC/외부 클라우드/기존 자원 삭제 없음.

## 2026-10-03 — 실제 실패·복구에서 시간 기록과 거짓 성공 수정

- Observed: ImagePullBackOff인데 SUCCESS(8.888s), ports 인자 오류로 배포 도구 미실행인데 SUCCESS(21.081s)를 실제 Qwen/Chrome에서 확인했다. 모델의 replicas 누락과 실패 기록의 복구 버튼 부재도 기록했다.
- Changed: 서버 시간을 측정하고 과거 고정 0은 미측정으로 표시한다. on-prem apply/undo 뒤 rollout을 확인하며 적용된 실패 건에 복구 버튼을 연결했다. Pydantic RetryPromptPart·반환 없는 호출을 성공에서 제외했다. 기존 CLI 파이프라인의 적용 후 자동 복구도 유지했다.
- Verified: 동일 실패는 FAILED(68.460s), 동일 인자 오류도 FAILED(15.427s). UI 복구 후 r1/revision 6/health 200, 별도 정상 요청(7.410s)으로 2/2 복원·Chrome 새로고침 확인. 세부/해시는 docs/evidence/dogfood-20261003/completion-and-recovery-verification.json. 서버 시간은 사용자 완료시간/MTTR가 아니다.
- Gate: 새 회귀 8개 red→green, 관련 74 passed·tsc 통과. 전체 첫 시간 수정은 writer AST 가드 1건, 다음은 기존 pipeline 복구 1건 실패를 보완했다. 최종 make check **3277 passed·2 skipped·20 warnings**, 131.37초(로컬 macOS·py3.13.5·Node22.23.3/임시prefix). validation-gate.log 참조.
- Next: 목표 active. 고정 후보로 실제 거부/배포 유실/근거 부족 및 반복 검증·수동 절차 비교·데모/R4/R5를 계속한다. Qwen 입력/설명 품질과 고정 kagent READY는 남는다. RBAC 확대·외부 클라우드 변경·커밋/푸시 없음.

## 2026-10-03 — 검토 값 보존과 최종 배포 반복 실증

- Observed: 후보 A의 replicas 누락·복구 후 1개 유지, B의 이미지 URI 오타로 실패했다. 앞선 정상 A 세 번을 최종 합격으로 합산하지 않았다.
- Changed: Deployments 입력/검토/확인 → strict 요청 → 기존 실행기/RunManager를 연결했다. actor/UUID/입력 바인딩, 새로고침 GET 복원, 직접 실행 On-Prem Executor 기록과 롤백 모델 오표기를 수정했다. 준비된 이미지·8080·/healthz로 한정한다.
- Verified: 후보 D 정상 3·실행 중 새로고침 2·수동 복구 2·제한 신원 거부 2회, 검토 취소/범위 누락을 실제 Chrome/kind에서 관측했다. claim/배포 도구 각각 1회, 복구 r0/2개/health 200, globex 자원 불변. 정상 클릭~health 11.798–14.157초, CLI 비교 12.992초(사람의 입력 시간 제외). 마지막 r0/revision 27/2개/health 200(06:51:31 UTC). 근거는 docs/evidence/dogfood-20261003/repeats/final-candidate-verification.json.
- Gate/Deliverables: 관련 22 passed·tsc, 최종 make check **3283 passed·2 skipped·20 warnings**, 123.69초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). README에 비교표/재현, demo에 72초 실제 정지 화면 해설과 영상 검수. 새 설치/운영 성능 검증이 아니다.
- R4 experiment: E의 진단 지침만 보완해 실제 Qwen 4건을 측정했다. 도구 0이지만 유사 증상 2건과 새 반례의 인과 추론은 실패. 사례 6개·원문·판정은 diagnosis-candidate-verification.json. E 전체 게이트도 **3283 passed·2 skipped·20 warnings**, 119.38초(같은 로컬 툴체인), 관련 24 passed. 코드 초록을 진단 품질 합격으로 세지 않는다.
- Next: R3 전체 미완료, 근거 연결 진단 계약이 다음이다. incident Reject는 사용자 브라우저 전환으로 pending 2·실행 0 상태에 보존, 승인 부족이 아니다. 기존 권한·외부 자원 보존, 커밋/푸시 없음.

## 2026-10-03 — 실제 거부 UI·사유 보존과 구조화 진단 반증

- Changed: 브라우저 prompt를 인라인 거부 확인으로 교체(F). 기존 on-prem 전달 경로의 사유 유실을 고쳐 2000자 제한/형식 검사와 사유·caller-reported 사용자 저장을 연결했다(G). 승인·권한 범위는 바꾸지 않았다.
- Verified: F 기존 합성 요청 2건 거부/취소, G 새 합성 요청 2건 거부(한글 줄바꿈/빈 사유), webhook 재시작·Chrome 새로고침 후 pending 0·실행 0·사유 유지·workload UID/spec 불변. v7-rejection-verification.json 참조. 실제 장애 감지나 webhook 인증 실증은 아니다.
- Regression: 저장 누락/잘못된 형식 2 failed→관련 33 passed·2 warnings, tsc 통과. 전체 첫 gate 3284 passed·2 skipped·1 failed(125.56초): 기존 writer 동시성 결함을 재현했다. 잠금 파일 open의 일시 ENOENT만 최대 3회 재시도, 지속 실패/권한 오류는 실행 차단. 관련 65 passed·8-thread 실제 loopback 50묶음 통과. 최종 make check **3288 passed·2 skipped·20 warnings**, 304.27초(로컬 macOS·py3.13.5·Node22.23.3/임시prefix). +5는 거부 기록 2·잠금 경계 3개다.
- R4: 같은 Qwen의 구조화 출력 4건은 형식 1/4, JSON 텍스트는 4/4지만 의미 실패 2·부분 2였다. 원문/지연/설정/양성 대조의 schema 한계를 r4-structured-verification.json에 보존. 제품 반영·정확도 합격으로 승격하지 않았다.
- Next: R3/R4 미완료. source 대상/시각/provenance 입력 계약과 recovery 판단 분리, 충분/불충분 대조를 먼저 검증한다. 거부 approval↔incident 직접 연결/상세 표시도 잔여다. 커밋/푸시/클라우드 변경 없음.

## 2026-10-03 — 거부 사건 연결과 진단 입력 계약/모델 비교

- Changed: I는 거부 approval↔incident ID·결정·사유·시각을 연결하고 상세에 표시한다. 기록에 없는 분석 모델/0% 원인 추정도 제거했다. 기존 거부/권한 경로를 유지했다.
- Verified: 실제 Chrome 합성 요청 2건(한글 줄바꿈/빈 사유), 사건 상세/새로고침, 양쪽 store ID/사유 일치·pending 0·조치 0·workload UID/spec 불변. v9-rejection-verification.json 참조. 실제 장애 분석이나 두 파일 쓰기 원자성 검증은 아니다.
- Regression: 기존 누락 회귀 2 failed → 관련 70 passed·2 warnings(9.87초), tsc 통과. I 전체 make check **3288 passed·2 skipped·20 warnings**, 117.99초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). 테스트 수 증감 0.
- R4: 대상/시각/provenance 계약 경계 6개 통과, 적용 불가 4사례의 본문은 모델에 보내지 않는다. 두 캐시 모델 비교에도 원인 과단정/삽입문 오인이 남아 제품 반영하지 않았다. r4-envelope-verification.json에 template/토큰/형식/의미 실패를 나눠 보존. 기존 모델 복원 후 실제 세 응답 확인.
- Next: 실제 확인한 MLX proxy의 빈 200·finish_reason/usage 유실부터 수정하고 R3/R4 진단 품질을 계속한다. D 배포와 I 거부 실증은 구분한다. 목표 active, 커밋/푸시/클라우드 변경 없음.

## 2026-10-03 — 모델 proxy 오류 보존과 진단 실패 재생

- Changed: J는 upstream HTTP 오류·종료 사유·실제 usage를 보존하며 잘린 도구 호출을 실행 가능한 호출로 바꾸지 않는다. 기존 Scorecard로 저장 진단 입력/인용과 recovery 정답을 별도 재생한다.
- Verified: proxy 경계 17 failed·8 passed → 25 passed, 관련 38 passed. 실제 Qwen 1토큰 JSON/SSE가 stop/0 또는 누락 usage → length/input 18·output 1로 바뀌었고 정상 stop도 유지했다. 283개 runtime 소스 해시 대조·소유 proxy 반영 완료. mlx-proxy-verification.json 참조.
- Gate: 전체 make check **3306 passed·2 skipped·20 warnings**, 137.77초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix), +18 proxy 경계 검사. 원격 CI/진단 품질 합격은 아니다.
- R4: 7사례 근거 계약 통과, recovery 정답은 6건 통과·삽입문 반례 1건 실패. 4건은 모델 미호출이므로 정확도로 해석하지 않는다. 요청 교체/가짜 인용/제외 자료 호출/양성 대조의 무조건 보류 경계 4개 통과. 모델 3호출의 보고 usage는 input 2683/output 896이다.
- Limit/Next: 캐시 Qwen3.8 4096토큰 비교 1건은 180.018초 timeout·완료 응답 0으로 품질 미판정. 소유 서버 종료 후 기존 Coder 복원·실제 응답 확인. 다음은 D 실제 revision/health/복구 근거 정규화와 진단 연결이다. R3/R4·최종 후보 묶음 미완료, 목표 active. 기존 WIP/권한/외부 자원 보존, 커밋/푸시 없음.

## 2026-10-03 — revision 근거 연결과 실제 화면의 health 과장 확인

- Changed: K는 기존 describe 도구에 source 해시/수집 시각·Deployment→ReplicaSet→Pod 소유 관계·revision/template·readiness 근거와 복구 검토 판정을 추가했다. 로그/모델 문장은 후보 판정에 쓰지 않는다. 변경 신원/권한은 그대로다.
- Verified: 양성 대조와 삽입문/오래된·다른 대상/부분 상태/읽기 거부/관측 중 변경 경계 +19. 첫 관련 44 passed·1 failed는 기존 명령 가드의 context/config 인식 누락을 보완해 45 passed·1 warning(0.83초). 전체 make check **3325 passed·2 skipped·20 warnings**, 134.97초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix).
- Actual: 동일 SA 2h 토큰만 갱신, 실제 제한 신원 조회 r0/rev27·rollout 완료/이전26·health 미확인. D 기록 재생은 누락된 RS/시각을 발명하지 않았다. 284개 후보 소스·소유 router 반영 뒤 Chrome e5b11d13… 요청은 claim1/describe1·ACTIVITY만 저장, 새로고침 유지·UID/spec 불변.
- Failed/Next: 코드 health_basis=not_established인데 실제 UI 모델은 건강하다고 요약하고 반복했다. 의미 검증 실패 원문/화면은 revision-evidence-verification.json. 제한 도구 실험의 첫 usage-property 호출 오류도 보존했다. 다음은 관측/복구 판정과 모델 해석의 화면 분리·출력 완료 상태·충분/불충분 대조다. R3/R4/최종 후보 묶음 미완료. 목표 active, 커밋/푸시/외부 자원 변경 없음.

## 2026-10-03 — 관측 결과와 모델 해석 분리·실제 화면 검증

- Changed: L은 구조화된 관측/복구 판정을 저장 요약과 주 화면에 표시하고, 모델 원문과 종료 사유는 별도 미검증 해석으로 보존한다. 일반/stream 응답·SSE 저장·새로고침에 같은 결과를 사용하며 변경 도구 실행을 진단으로 재분류하지 않는다.
- Verified: 관련 41 passed(2.58초)·tsc 통과. 전체 make check **3335 passed·2 skipped·20 warnings**, 135.89초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). +10은 표시/완료 상태/저장 경계 검사다. K 저장 실패 재생은 모델 호출 없이 6400자 반복을 191자 관측 요약으로 분리했고 원문을 보존했다.
- Actual: 286개 소스가 일치한 후보를 소유 router/dashboard에 반영했다. Chrome 3da3703c… 요청 claim1/describe1·ACTIVITY만 저장, 새로고침·출처/모델 펼침 확인. r0/rev27/2개 UID/spec 불변이며 새 HTTP health 측정은 없다.
- Limit/Next: 실제 모델은 stop으로 끝났지만 원문에서 여전히 건강하다고 과장했다. 화면 분리는 의미 합격이나 읽기 전용 권한이 아니다. inspection-presentation-verification.json 참조. 다음은 UI→API→도구 등록/요청 ID의 읽기 전용 capability와 유용한 가설의 충분/불충분·반례 대조다. 최종 동일 후보 묶음/R5 미완료, 목표 active. 커밋/푸시/외부 변경 없음.

## 2026-10-03 — 읽기 전용 요청의 도구 제한과 실제 변경 거부

- Changed: M은 strict read_only를 UI·두 API·router·도구 등록·durable 요청 ID에 연결했다. 로컬 Qwen/onprem만 지원하고 A2A 위임은 하지 않는다. Investigate 5개만 등록하며 거부된 변경 도구 이름은 배포 기록을 만들지 않는다. 기존 역할/신원/RBAC는 유지한다.
- Verified: 관련 46 passed(3.29초)·tsc, 전체 make check **3345 passed·2 skipped·20 warnings**, 128.96초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). +10 경계 검사. 제외 도구 10개 거부·조회 5개 실행·일반 모드 변경 양성 대조, 같은 ID 모드 변경409·다른 actor404. 도구/기록/proxy 경계를 제거한 변이3종 모두 red 뒤 원본 복원·전체 gate 통과.
- Actual: 286개 소스를 소유 router/dashboard에 반영. Chrome 868f454b… 조회 claim1/describe1·ACTIVITY만, 4a74ee4b… 롤백 요구 claim1/도구0·배포0. 두 결과/모드 새로고침 유지, r0/rev27/2개 UID/spec 불변. readonly-capability-verification.json 참조. 새 HTTP health 측정 없음.
- Limit/Next: 요청별 도구 제한이지 자격증명/테넌트 격리가 아니다. 모델은 이번 health 미확인을 유지했지만 이전 revision 설명에 추측이 남았다. 다음은 유용한 가설/다음 확인의 충분·불충분·반례 대조와 고정 runtime READY 표시 수정이다. R3/R4·최종 후보 묶음·R5 미완료, 목표 active. 커밋/푸시/외부 변경 없음.

## 2026-10-03 — 실측 연결 표시와 실제 UI 진단 7사례의 실패 기록

- Changed: N은 고정 READY/위임 표시를 router 실측 연결·시각으로 바꿨다. 모델 완료에 보고 usage/응답 수/도구 시도 수를 보존하고 도구0 설명은 NO TOOL CALLS·Unverified로 표시한다. 모르는 usage는 null이며 backend 조치 상태는 바꾸지 않는다.
- Verified: 관련 28 passed(3.51초)·tsc, 전체 make check **3348 passed·2 skipped·20 warnings**, 135.23초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). +3 검사, payload/READY 변이2종 red·바이트 복원. 286개 소스 일치·소유 router/dashboard만 반영했다.
- Actual: Chrome 진단 7건은 각 claim1/모델 응답1·도구0·배포0, 마지막 요청/모드/결과 새로고침 유지. 보고 usage input11458/output2455, 접수→저장 3.700~8.329초. workload UID/spec/r0/rev27/2개 불변, 새 HTTP health 측정 없음.
- Failed: 코딩 에이전트 검토 충족1·부분3·실패3. 시각/다른 대상 누락과 unknown-time 삽입문을 복구 후보 근거로 삼는 오류가 남았다. 긍정 복구 후보는 인식하므로 전건 보류는 아니다. 부분3도 합격 아님. 원본/hash/인용은 r4-readonly-ui-scorecard-v2.json에 보존. 최초 byte 불일치는 HTML input의 구분 LF 제거였고 원본 실패도 보존했다. 별도 검토 바인딩 변이4종 검출.
- Next: runtime-observation-verification.json 참조. 기존 source 대상/시각 계약을 실제 진단 입력에 연결한 뒤 실패 사례와 유효한 양성 근거/다음 조회를 재대조한다. R3/R4·최종 동일 후보 묶음·R5 미완료, 목표 active. 승인 대기 아님. 커밋/푸시/클라우드/RBAC 변경 없음.

## 2026-10-03 — 실제 snapshot 입력 계약과 남은 의미 오류

- Changed: O는 prototype 대상/시각 계약을 실제 UI·두 API·durable router에 연결했다. snapshot은 읽기 전용 local-qwen/onprem·동일 질문을 요구하며 원문을 요청에 보존한다. 적용 자료0이면 모델0, 자료가 있으면 도구0 factory·한 번의 모델 요청·출처별 정확 인용/형식 검사를 쓴다. 의미 검증/실행 승인은 아니다.
- Verified: 관련36 passed(3.80초)·tsc·기존 실험6경계 통과. 대상/인용/도구 등록 변이3종 red·바이트 복원. 전체 make check **3356 passed·2 skipped·20 warnings**, 138.14초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix), +8. 기존 일반 요청의 null snapshot은 fingerprint에서 제외한다.
- Actual: 287개 소스 일치·소유 router/dashboard 반영. Chrome 7건 각 claim1·도구0·배포0; 제외4/모델3, 적용 가능성7/7·인용3/3. 마지막 대상/시각/제외 사유/모델 미호출 새로고침 유지. workload UID/spec/r0/rev27/2개 불변, 새 HTTP health 없음.
- Failed: 모델 의미 검토 충족1·부분1·실패1. 적합한 snapshot의 SYSTEM 지시를 이미 내려진 결정으로 오인하고 이전 revision 건강성을 발명했다. 네 모델 미호출을 정확도에 포함하지 않는다. N과 다른 프롬프트/입력 경로라 일반 성능 개선 주장도 하지 않는다. 입력/hash/인용/부분 승격 검토 변이4종 검출. r4-snapshot-ui-scorecard.json에 원문과 코딩 에이전트 검토 근거 보존.
- Next: snapshot-contract-verification.json 참조. 같은 세 입력과 factory/계약을 캐시 Qwen3.8·추론 off·명시 예산으로 대조하고 품질 확인 전 기본 모델을 바꾸지 않는다. R3/R4·최종 동일 후보 묶음·R5 미완료, 목표 active. 승인 대기/커밋/푸시/클라우드/RBAC 변경 없음.

## 2026-10-03 — 캐시 모델·검토자 대조 실패와 원래 모델 복원

- Changed: P는 실험만 수행, 제품 소스 변경0. 캐시 Qwen3.8을 같은 snapshot factory/세 입력·추론 off·1024토큰·retry0으로 대조했다. 형식·인용1/3, 의미 충족1·부분1·실패1. 삽입문은 거부했으나 서로 다른 원인을 확정했고 두 답변은 길이 계약을 넘었다.
- Actual: 생성 HTTP/응답3, 보고 input2884/output1371. 고정 대조군4의 critic은 기존 Coder verdict일치2/4(거짓 통과·거부), Qwen3.8은 완료2 중 원인 단정을 PASS로 오판. 세 번째 실제 client timeout/exit1, 네 번째 미실행. 누락 시간/usage를 발명하거나 재시도하지 않았다.
- Verified: source/candidate/prompt hash를 묶은 r4-semantic-review-calibration.json. 소유 MLX를 기존 Coder로 복원하고 실제 OK/stop(input12/output2) 확인, 앱 설정 불변. O의 287개 작업 트리/실행 후보 소스 일치. 기존 전체 gate3356/2는 O 실행이며 이번에 다시 돌린 결과가 아니다. 문서 검사 첫54통과/1실패는 진입점의 미추적 Markdown 참조를 계획/검증 기록으로 정정해55통과(3.07초), diff check 통과.
- Failed/Next: 생성 모델 교체·자동 critic 모두 미채택. model-comparison-review.md 참조. D에서 빠진 RS/Pod·시각을 승인된 실패/복구 1회에서 보완해 수동 조사와 모델의 도구 선택을 대조한다. 의미 오류·R3/R4·최종 후보 묶음/R5 미완료, 목표 active. 승인 대기/커밋/푸시/클라우드/RBAC 변경 없음.

## 2026-10-03 tidy-docs - preserved pre-tidy source

Historical snapshots only. Current pause/resume state is in docs/NEXT_PLAN.md. Source text below is preserved verbatim; old active/next statements are dated history.

<a id="tidy-20261003-brief"></a>

### docs/AGENT_BRIEF.md

Source SHA256: `d4342241230fe0518f2b2cfef00e5e315348a190e1175fde89e79f312ba13d1c`

<!-- BEGIN tidy-20261003-brief -->
~~~~markdown
# AGENT_BRIEF — platform-agent

최종 갱신: 2026-10-03

> ▶ NEXT SESSION: **사용자 요청으로 일시중지(10-03 checkpoint). 재개 시 첫 행동 = 집계·RS/Pod 모순의 고정 자료 재현(R3/R4)** — T 실행 반복/재현/비교/데모 완료. U는 코드·공식 문서 검토까지만, 새 재현·수정 없음. 실행O/작업트리R 유지, 진단 기준은 미충족이다. 재개 지시 후 Q/S 원본과 양성 대조군으로 모순 판정을 먼저 측정한다. `docs/plans/2026-10-03-platform-agent-usage-and-evidence.md` §8 참조. **기존 lab 1367338348·checkout 및 R2 lab/App 4924748/설치 161238144/키/branch/draft PR 보존, 추가 삭제 금지.**
> 보존 점검: 두 checkout과 사용자가 재다운로드한 R2 PEM(0600)은 존재. 옛 PEM은 기록 경로에서 미발견이며 이번 작업에는 파일/키/원격 자원 삭제가 없다.
> 실제 청구 **$0.00**(계량 798,331 샘플)이고 사유는 **AMP 프리티어가 `Always Free` 40M/월**이라
> §3의 배제 근거가 **전건이 거짓**이었다는 것. ⚠️**"어차피 공짜"로 요약 금지** — 절벽이 요율→**한도**로
> 옮겨 앉았을 뿐이고 필터 없음은 **128배 초과**다. ✅대시보드 취약점은 **0건**이다(08-30, Risk 11 — ⚠️"기록이 세 군데 틀렸다"를 지우지 말 것).
> ✅**DoD 넷은 다 닫혔다**(08-17, M37) — 관리형은 **매니페스트를 내지 않고** read model이 그 부재를 설명한다(`applicable=False`·sync **n/a**). **새 매니페스트 종류는 발명하지 않았다.**
> ✅**$0 선행 BQ 결제 내보내기는 켜졌고 적재도 도착했다**(09-01 켬 → 09-02 **730행**, M49) — ⚠️**소급 적용은 없었다**(실사용 데이터는 **08-30부터**). 절차는 `docs/GCP_BILLING_EXPORT_SETUP.md`.
> **무과금으로 이어서 할 것**: ⛔**목록이 비었다 — 여섯이 닫혔다**(**ⓐ**·**ⓒ**·**`rollback_release`**·런북 walk ②·**`slack_live_approval`**·**`triggered_at`**, 08-15~08-17). **다시 열지 말 것** — 각 줄의 경위·⚠️/⛔ 전문은 `docs/archive/brief-detail-2026-09.md`가 **권위**다(⚠️요약만 읽고 다시 열지 말 것). ⚠️**"비었다"는 목록의 상태지 사실이 아니다**(아래 "소진은 여섯 번 틀렸다").
>
> ⚠️ `main` 보호 — 직접 push 불가(소유자 포함), **PR + CI 통과로만 병합**(D43).
> ⚠️ 초록에는 조건이 붙는다(Risk 12, 이제 **아홉**): **새 가드는 지워 보고 red를 확인**(③) · **skip은 실패가 아니다** — 게이트 숫자엔 **잰 기계**까지 붙일 것(②) · **가드는 독자가 읽는 그 물건에 대고 물을 것**(④ — **결함을 그 그림자로 세지 말 것**, **경고는 주장만 묻지 말고 지시까지**, **문은 넷**) · ⑤**가드 자신도 틀린다**(08-13: 픽스처로 고른 값이 **틀린 기본값과 같아** 결함을 통과시켰다 · 변이 하네스가 `git checkout --`로 **커밋 안 된 고침을 날리고** 있었다 — **초록으로 안 돌아오는 복구는 복구가 아니다**) · ⑦**변이 결과는 어디에 물었는지까지 말할 것**(08-15: **틀린 테스트 파일**에 물어 "가드 없음"으로 읽었는데 전체 스위트로는 red였다 · **변이·실행·복구는 한 스크립트 안에** 둘 것).
> ⚠️ **"소진"은 이제 여섯 번 틀렸다** — 가장 값싼 다음 수는 대개 **직전 세션이 이미 적어 뒀다**. ⚠️**목록에 적힌 항목 자체가 틀릴 수도 있고**(08-15 ⓑ) **틀린 항목도 값이 난다** — 단 **`git log -L`로 "언제부터"까지** 물어야 stale과 오기를 가른다. ⚠️**"안 봤다"를 시험하면 결함이 아니라 범위가 나올 때도 있다.** ⚠️**형제 집합은 세는 순간 전부 셀 것**(08-13에 세 번 · 08-15에 둘 · **09-01에 하나 더 — 형제를 세는 가드 자신이었다**) — ⚠️**산문이 참이어도 임포트 줄이 범위다.** ⚠️**"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다** — 기준은 **읽는 쪽의 provider 간 비대칭**이다. ⚠️**읽는 쪽을 고쳤으면 쓰는 쪽도 물을 것**(08-17) · **검증기가 둘이면 느슨한 쪽이 실제 경로다**. 상세는 **`STATUS` Risk 12가 권위**.
> ⚠️ **추정표는 어느 칸이 측정이고 어느 칸이 가정인지 표시할 것**(08-15, 4a): 정가는 맞았는데 **안 잰 시계열 수**가 총액을 100배 지배했다 — **가정이 지배하는 추정은 추정이 아니라 그 가정이다.** 그리고 **권위 문서가 틀리면 복제본이 그것을 사실로 굳힌다**(진입점 3곳이 "$5"를 복제해 승인까지 갔다 — **복제 금지 규약이 겨냥한 실패**).
> 직전 세션 → **09-02~03**: **M49**(GCP 적재 판정) · **M50**(`MEASURABLE`이 금액을 대신 묻는다, 게이트 +10) · **M51**(Risk 6 재개 조건이 2년 전에 멈춘 이슈를 보고 있었다) + **씨앗 다섯 충전**(PR #70~#73). ⛔**상세를 여기 다시 적지 말 것** — `PROGRESS_LOG` 상단이 권위다. ⚠️**M50·M51이 남긴 것 둘**: **가드 자신이 부분문자열에 속는다**(`= 'PROMOTION'` ⊂ `!= 'PROMOTION'`) · **열린 이슈는 '지원이 없다'의 증거가 아니다**(구현은 이미 머지돼 있었다).
>
> 1분 압축 문맥. 에이전트 진입점. 이 파일은 **≤60줄**로 유지한다.
> ⚠️**압축본이다(2026-09-02)** — 상세는 **삭제가 아니라 이동**했다: 닫힌 항목 여섯과 직전 세션
> 전문은 `docs/archive/brief-detail-2026-09.md`가 **권위**다. 요약만 읽고 결론 내지 말 것.

## Read Path (순서대로, bulk-read 금지)

1. `docs/AGENT_BRIEF.md` — 이 파일
2. `docs/STATUS.md` — 현재 상태 / 검증 baseline / risks
3. `docs/NEXT_PLAN.md` — 열린 작업만
4. (필요 시) `docs/PROGRESS_LOG.md` 상단 — 최신 증분
5. (필요 시) `docs/engineering/` — harness/loop/context 엔지니어링

권위 순서: `NEXT_PLAN.md` (유일한 source of truth).

## Snapshot

- **무엇:** AWS-native 플랫폼 에이전트. provision → deploy 검증 → detect → analyze → decide → execute → Slack 리포트.
- **동작하는 것:** Operations 4단계 + 3-cloud AI Agent + **On-Prem Ops**(12도구, trace) + Terraform kind/실 Multipass VM Ansible k3s Provision + kagent↔Local Qwen A2A + Agents UI. **On-Prem 오프라인 완결**: Local **Qwen3-Coder-30B-A3B**(MoE·활성 3B, `Makefile:58`)로 NL provision→deploy→validate ~39s, 로컬 JSONL 기록 + 대시보드 **hybrid**(AWS+On-Prem 병합) + 실 **롤백**(app/cluster). **추적 IA**: activity에 `type`(provision/deploy)·`cluster` 연결키, 대시보드 **Provisioning/Deployments/History** 분리 + **중첩 상세**(provisioning⊃deploys), 롤백 **단일-row 승계**·**teardown→deploy cascade**, 자연어 rollback/teardown도 동일 라우팅.
- **하네스:** overnight-harness 플러그인 기반 (5 engine). `make overnight-kiro-once` 로 smoke. `make dev-up`으로 로컬 스택(MLX+proxy+router+dashboard) 한 방 기동.
- **Kiro 특화:** aws-ops / cdk-dev / overnight-harness 3개 에이전트 + safety hook + AWS MCP Server.
- **검증:** `make check` → **3364 passed, 2 skipped** (**2026-10-03 로컬 macOS·py3.13.5·Node 22.23.3/임시 npm prefix** · CI도 **같은 게이트**, ubuntu·py3.13 — **CI 숫자는 PR 체크가 권위**, 여기 복제 금지; 게이트 숫자는 날짜와 **잰 기계** 없이는 주장이 아니다, Risk 12①②). ⚠️**08-30엔 2337→2332로 내려갔다**(M39, 정당화 7건 −14 / 새 가드 +9); **09-01은 M40~M46**(+7·+3·+3·+4·+8·+10·+13), **09-02는 M47**(+11)·**M48**(+5)·**M50**(+10 — ⚠️첫 가드는 `= 'PROMOTION'`이 `!= 'PROMOTION'`의 **부분문자열**이라 변이를 놓쳤다), **09-03은 harness 1.4.0**(+3 — `LESSONS.md` 예산이 세 선언 검사에 편입). **무엇이 늘고 줄었는지는 `STATUS` Baseline이 권위다 — 여기 복제 금지.** **결함이 닫히면 그 결함을 설명하던 줄도 사라진다 ⇒ 단조증가 지표가 아니다.** 내역은 `STATUS` Baseline. CI(`gate.yml`)가 **main 병합 조건**이고 **terraform 검증까지 실제로 돈다**. 이력·근거는 `STATUS` 검증 Baseline과 `COMPLETED_SUMMARY` **M10~M46**에 있다 — 여기에 다시 적지 말 것.
- **현재 초점:** **단일 환경의 배포·검증·복구를 반복 사용할 수 있는지 측정**(10-03 계획). `docs/plans/2026-10-03-platform-agent-usage-and-evidence.md`의 R0→R3를 우선하고 실제 병목만 수정한다. 기존 평가·reconciliation·사후 검증·데모 경로를 재사용한다. Phase 5 운영 연결/발행 경계와 Phase 4b 비용·기간·종료 조건은 별도다. M91의 인증 해소/후보 검증은 09-15 기록이며 현재 원격 상태는 재조회하지 않았다.

## Guardrails

- 에이전트=Python(**3.13**. ⛔`>=3.11`은 08-30에 재서 **거짓이었다** — fresh 3.11은 **2 failed**이고
  같은 의존성의 fresh 3.13은 초록이다. 선언 셋을 3.13으로 맞췄다) / IaC=CDK TS / 모델은 `models.py` 한 곳.
- IAM 최소 권한. ⚠️**`Resource:"*"` 전면 금지는 무조건 거짓이었다** — `incident_agent_stack.ts`의 **7건 전부** AWS가 리소스 타입을 주지 않는 액션이다(08-16 Service Authorization Reference 대조). 규칙은 **"이유를 주석으로 적지 않은 `*` 금지"**이고 이제 **가드가 집행한다**(`test_iam_wildcard_justified.py`). **만족 불가능한 규칙은 우회를 습관으로 만든다.**
- `Delete/Drop/Terminate` 액션은 강제 APPROVE(**D48**로 계약화·집행).
- 요청 이상 기능 추가 금지. 테스트 통과 전 완료 선언 금지.
- Gate 명령: `make check`. **`main`은 보호됨** — 직접 push 불가, PR + CI 통과로만 병합(D43).

## Skills (overnight-harness)

- `/sync` — Read Path 따라 상태 복원(읽기 전용).
- `/checkpoint` — PROGRESS_LOG append + current docs 갱신.
- `/tidy-docs` — 문서 정리/압축.
- `/overnight-report` — 루프 결과 리포트.
- `/overnight-seed` — backlog 시드.
- `/diagnose` — 루프 실패 진단.
~~~~
<!-- END tidy-20261003-brief -->

<a id="tidy-20261003-status"></a>

### docs/STATUS.md

Source SHA256: `76b9623ac36366aa3e7b4c738e4ca250cdf3a605f099aa9540476d9d54ecd7aa`

<!-- BEGIN tidy-20261003-status -->
~~~~markdown
# STATUS — platform-agent

최종 갱신: 2026-10-03

> 현재 구현 상태 / 검증 baseline / active focus / open risks. **≤120줄** 유지.
> ⚠️**압축본이다(2026-09-02)** — 상세는 **삭제가 아니라 이동**했다:
> 옛 baseline은 `docs/archive/status-baseline-2026-09.md`,
> Active Focus·Risk의 ⚠️/⛔ 상세는 `docs/archive/status-risk-detail-2026-09.md`가 **권위**다.
> 여기 남은 건 **주장 한 줄 + 재개 조건**뿐이다. 요약만 읽고 결론 내지 말 것.

---

## 검증 Baseline (실제로 돌린 것만)

- 10-03 `make check` → **3364** passed·2 skipped·20 warnings, 133.83초. 로컬 macOS·py3.13.5·Node22.23.3. 증감0(T·작업트리R).
- M89 대시보드 AWS transport: TS 118 passed(+37), 실제 SDK 설정/격리 실패·로컬 TS↔Lambda/DB 왕복·인증 HTTP·브라우저·변이 5종 검출/복구·Next build 통과. `make check` → **3252**(2026-09-13 로컬 macOS·py3.13, 2 skipped, 106.21초). M71~M88은 완료 요약 참조.

- M68 Lambda Docker bundling: 필수 입력 누락을 성공으로 덮던 마지막 || true의 범위를 좁혔다. 회귀 3 failed·2 passed → 5 passed, 전체 `make check` → **2831** (2026-09-06 로컬 macOS·py3.13 · 2 skipped, 59.28초, +5). 공식 Lambda Python 3.11 ARM64 이미지에서 정상 패키징과 네트워크 차단 상태의 핸들러 13개 import 성공. 호스트 bundler·실서비스 동작·배포 검증은 별도다.

- M67 기본 CDK 진입점: 격리 Node 22에서 ts-node 누락을 재현하고 devDependency에 추가했다. 신규 실제 앱 회귀 1 failed → 1 passed, 새 Linux npm ci·앱 합성 98개 리소스 확인(bundling 제외). 전체 `make check` → **2826** (2026-09-06 로컬 macOS·py3.13 · 2 skipped, 56.49초, +1). 첫 게이트의 M67 요약 누락 2건을 보완한 뒤 통과. 원격 CI·Lambda 패키징·배포는 별도.

- M66 의존성 갱신 후 `make check` → **2825** (2026-09-06 로컬 macOS·py3.13 · 2 skipped, 55.56초, 증감 0). 별도 깨끗한 Linux amd64·Node 22.23.2·py3.13.15에서 두 npm ci·TS/CDK 관련 **69 passed, 0 skipped**·dashboard production build 통과. npm audit high 1+3 → 각각 0. 실제 CDK context의 98개 리소스에서 seed provider Node 22→24·S3Key만 변경; 앱 bundling은 제외했다. 원격 CI·배포는 미검증. 증거 `docs/evidence/ci-node22-lockfile-refresh-2026-09-06.log`.

- `make check` → **2825** (2026-09-06 로컬 macOS·py3.13 · 2 skipped). **+12**: M65 P5-E JSON 중복 키·비표준 숫자·boolean/float의 정수 오인 방지. 관련 116 passed, 변이 5종 검출. 원격 읽기 검토는 완료했으나 등록 화면 재인증과 실행 범위 확인이 남았다. 전체 게이트 54.14초로 통과. 원격 쓰기는 미실행.
- `make check` → **2813** (2026-09-06 로컬 macOS·py3.13 · 2 skipped). **+104**: M64 P5-E 오프라인 증거 판정·JSON CLI. 관련 104 passed, 변이 8종 검출. 최소 신원/권한·ref/parent/tree/main·형제 거부·PR 일치를 검사하며 합성 입력 통과는 실제 자격증명 실증이 아니다. 전체 게이트 52.99초로 통과. 원격 실증/CI는 미검증.
- `make check` → **2709** (2026-09-06 로컬 macOS·py3.13 · 2 skipped). **+13**: M63 preview 요청 스트림 경계. 정확 바이트 한도·청크 누적·취소/읽기 실패·reader 해제를 실제 Node Web API로 검사한다. preview 전체 46 passed, 변이 6종 검출 후 전체 게이트 53.10초로 통과. 원격 CI는 미검증.
- `make check` → **2696** (2026-09-06 로컬 macOS·py3.13 · 2 skipped, 49.76초). **+10**: M62 독립 검수 후 실제 fixture의 툴체인 누락 정책 검사로 보완했다(문자열 검사 2개 → 실행 검사 12개). 3종 변이를 검출했고 원본 WIP를 보존해 반영했다. 첫 후속 게이트의 문서 수집 수 불일치 1건을 갱신한 뒤 전체 통과. 원격 CI는 미검증.
- `make check` → **2686** (2026-09-06 로컬 macOS·py3.13 · 2 skipped). **+7**: CI의 TS/CDK 검증 누락 방지(M61) — `gate.yml`에 dashboard·`src/stacks` npm 설치(`actions/setup-node`, lockfile 캐시)를 추가하고 `tests/_ts_toolchain.py`로 `CI`/`GITHUB_ACTIONS`에서 툴체인 누락을 skip 아닌 fail로 전환했다. 로컬에 이미 있던 두 `node_modules`로 TS 계약·CDK 합성이 실제로 통과함을 확인. `npm ci`가 신선한 ubuntu 러너에서 성공하는지·실제 원격 CI 결과는 미검증.
- `make check` → **2679** (2026-09-06 로컬 macOS·py3.13 · 2 skipped). **+12**: 실제 make 하위 환경의 엔진별 critic 기본값·명시 override·재설치 snippet 검사(M60). 변경 전 12 failed → 변경 후 12 passed. 설치된 1.5.0 선택/호출 코드의 Codex argv가 `--model gpt-6-astra`임을 전송 없이 확인했다. 모델 라이브 실행은 미검증.
- P5-E 준비(M59, 2026-09-05): 실제 GitHub 등록 폼에서 single_file/PR write·Contents 미허용 확인, 가상 YAML의 P5-A 계획과 API 본문 blob/base64 대조. `make check` **2667 passed, 2 skipped**(로컬 macOS·py3.13, 테스트 증감 0). 원격 쓰기 실증이 아니다.
- `make check` → **2667** (2026-09-05 로컬 macOS·py3.13 · 2 skipped). **+38**: P5-D TS 요청/Invoke·grant 보존·로컬 Git/실행 경계. 실제 Auth.js 세션 역할별 HTTP, DynamoDB Local 사용자 수정·감사 기록, 브라우저 성공/오류 화면, Next.js production build, 변이 6종 red(M58). dashboard npm 의존성이 없으면 TS 실행 검사는 skip한다.
- `make check` → **2629** (2026-09-05 로컬 macOS·py3.13 · 2 skipped; 51.37초). **+38**: P5-C Lambda·GitHub tree/blob·HTTP·합성 IAM 검사. DynamoDB Local 실제 SDK 200/403/503, Linux ARM64 패키지 빌드·격리 import, 변이 7종 red(M57). CDK 검사는 `src/stacks` npm 의존성이 없으면 skip이므로 CI 집행을 주장하지 않는다.
- `make check` → **2591** (2026-09-05 로컬 macOS·py3.13 · 2 skipped; 48.40초). **+57**: P5-B 현재 사용자·역할·명시적 write grant·회수·장애·요청 고정 계약. 인가 변이 7종 red → 바이트 복구(M56).
- `make check` → **2534** (2026-09-05 로컬 macOS·py3.13 · 2 skipped; 45.96초). **+105**: P5-A 스냅샷·입력·출력·digest 계약. 변이 8종 red, 소스 바이트 복구. M55와 증거 로그 참조.
- `make check` → **2429** (2026-09-05 로컬 macOS·py3.13 · 2 skipped; 42.53초).
  **+19**: 문서 경로·D번호·문자 예산 가드(+16)와 예정일 구분 회귀 검사(+3). 문서 변이 19종·날짜 변이 2종 red → 바이트 복구 후 각각 16·12 passed. 상세는 `PROGRESS_LOG`·M52.
  `STATUS`는 기존 문장·경고를 보존해 줄을 합쳤다. **M52는 로컬 검증, M54는 GCP 결제 내보내기 라이브 조회**다. M53·M54 반영 후에도 `make check` 2429 passed·2 skipped(09-05 로컬 macOS·py3.13). CI·원격 배포 검증은 별도다.
- `make check` → **2410** (2026-09-03 로컬 macOS·py3.13 · **CI도 같은 게이트**, ubuntu·py3.13 — **CI 숫자는 PR 체크가 권위**). **+3**: overnight-harness **1.2.0→1.4.0** — `docs/LESSONS.md`(≤40줄)가 세 선언 검사(라인·정책표·머리말)에 편입됐다. Makefile은 모델 라우팅(actor `claude-sonnet-5` / critic `claude-fable-5-1`, `?=`)과 ledger·resume·trajectory 타깃을 얻었다. 코드 변경 0.
- `make check` → **2407** (2026-09-02 로컬 macOS·py3.13 · **CI도 같은 게이트**, ubuntu·py3.13 — **CI 숫자는 PR 체크가 권위**). **+10**: **`MEASURABLE`이 금액을 대신 묻는다**(M50) — 인쇄만 하던 분기가 질의를 돌리고, **PROMOTION을 나머지 크레딧과 갈라** 인쇄한다. ⚠️**첫 가드가 그 변이를 통과시켰다** — `= 'PROMOTION'`은 **`!= 'PROMOTION'`의 부분문자열**이라 한쪽을 지워도 다른 쪽이 대신 답했다(M48의 접두 함정과 같은 계열, Risk 12④). ⚠️**창을 전 행으로 재면 3일이 한 달로 보인다** (계정 수준 Invoice 행 하나 때문 — 프로브가 제가 경고하는 오독을 할 뻔했다).
- 이전 baseline — **2397**(09-02, M48) · **2392**(09-02, M47) · **2381~2339**(09-01, M40~M46) · **2332**(08-30, M39) · **1862 이하**(~08-13, M16~M18) · **1697 이하**(07-10~08-09) → `docs/archive/status-baseline-2026-09.md` · `status-baseline-2026-0{7,8}.md` · `progress-2026-0{7,8,9}.md` · `COMPLETED_SUMMARY` M13·M14. ⚠️**단조증가 지표가 아니다** — 08-30에 2337→**2332**로 내려갔고 **그게 옳다**(M39): **결함이 닫히면 그 결함을 설명하던 줄도 사라진다.** 줄어든 숫자는 **분해해 적을 것**. **여기 남길 함정 셋(08-09)**: 라이브 `gcloud` 호출(21.97s→0.02s — D49가 일반화해 집행) · 반증 중 **`.pyc`에 속았다** · `spend-watch`는 **터미널을 안 열면 검사도 없다**.

## Active Focus

- 10-03 사용자 요청 일시중지. T 실행/산출물 완료, U 코드 검토만. 진단/R3/R4 미완료, 재개 시 모순 관측 재현.

> **"무엇이 도는가"는 여기 적지 말 것** — `AGENT_BRIEF` **Snapshot**과 `COMPLETED_SUMMARY`
> **M0~M45**이 권위다. 이 파일은 **무엇을 믿어도 되는가**만 답한다.

**Phase 4 — 4a는 닫혔고(08-30) 접혔다(09-01)**: DoD 넷 + 실제 청구 **$0.00**(프리티어 `Always Free`
40M) → 워크스페이스·IAM 사용자·키 **셋 다 삭제**. ⚠️**믿으면 안 되는 요약 셋이 있다 — 셋 다
archive 상세에 적혀 있다**(*"어차피 공짜"* · 720h 가정 추정치 · *"$0.00이라 접었다"*).
⚠️**D48은 안 죽었다**. 권위 = 계획서 **§10·§11** · **M38·M40** · **D50 Folded**. **다시 열지 말 것.**

**과대 해석 금지(현재 유효한 것만)**
- 스코프·배포 신원 · 이미지 서명 배포 게이트는 전부 **옵트인**(→ Risk 3·6).
- 자격증명이 테넌트-바운드인 건 **온프렘뿐**(→ Risk 10) · 파티션된 읽기 경로는 **둘뿐**.
- `main` 보호는 **게이트 집행**이지 리뷰 집행이 아니다(코드 소유자 리뷰 off → D43).
- **어드미션 미도입** · **CODEOWNERS는 라우팅** · Phase 5는 **저장·준비·상태 UI/AWS transport까지 로컬 구현**(M89). M91 후보/설정 점검 완료, 원격 배포·production PR 연결 없음.
- **Phase 5 남은 것**: 원격 연결·발행 토큰 경계·PR 제출 UI. 실험 PR/부분 판정과 저장/상태 연결(M83~M89)은 완료, 다음은 계획서 §13의 운영 실행 범위 확인이다. P5-C는 공개 저장소의 익명 GET만 구현하며 private GitHub/token 경로는 없다. 실행 위치 부재를 blocker로 반복하지 않는다(M53).

**반복 확인**: 기록된 이유가 진짜 구속 조건이 아닐 때가 많다(M13→M15) — 단 **늘 그런 건 아니고
성립한 쪽이 더 많았는데 그래도 값은 나왔다**. ⚠️**열린 항목 자체가 틀릴 수 있다**(08-15 ⓑ) ·
⚠️**"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다**(기준은 **읽는 쪽의 provider 간 비대칭**) ·
**"없다"는 어떻게 봤는지까지**(→ Risk 4) · **직전 세션의 Next를 그대로 따라갈 것**.
근거·사례는 **archive 상세의 "Active Focus — 반복 확인"이 권위**.

## Open Risks / Gaps

> 각 항목은 **주장 + 재개 조건**만이다. 경위·측정·⚠️/⛔ 문장은
> `docs/archive/status-risk-detail-2026-09.md`의 **같은 번호**가 권위다.

1. **CDK 배포 시 Vercel context 필수** — ⚠️미지정 배포가 **실제로 07-11 OIDC provider를 삭제**했다. diff/deploy는 반드시 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`.
2. **GCP/Azure 인시던트 스토어는 보관 정책이 없다 — 단 "실 데이터 삭제"는 틀렸다**: 코드 갭은 유효, **스토어가 없어 지울 데이터 0**(08-30 재확인) → **Phase 4** 선행. 증거 `docs/evidence/gcp-azure-retention-nothing-to-delete.log`.
3. **스코프·배포 신원은 집행 가능하지만 옵트인이다(D38·D39)** — 기본값 미설정이라 **"설정하면 집행되고, 안 하면 조용히 안 된다."** 묻기 `probe_scope_reachability.py`·`make deploy-identity-check` · 켜기 `make scope-credentials`·`make deploy-identity`. **남은 것**: 배포 신원의 테넌트 구분(결정 5 C/D) · 클라우드 3종은 Risk 10.
4. **비용 관측은 프로젝트·크레딧·사용 창을 분리해야 한다** — 이전 AWS/Azure·GCP 실측과 경고 전문은 archive의 Risk 4가 권위다.
   **GCP 09-05 재측정(M54)**: export **3,053행**, 이 프로젝트 **1,591행**, 총사용액 **₩14.80** → PROMOTION **−₩12.36** + 기타 크레딧 **−₩2.44** → 청구 **≈₩0**. 결제계정 합계 **₩251.18**를 이 레포 비용으로 읽지 말 것.
   ⚠️**달력 창(08-24~09-05)은 정상상태 표본이 아니다**: 08-24~27 행은 미미한 금액이고 09-05는 04:00 UTC까지만 적재됐다. Artifact Registry의 일별 차이와 09-05 Cloud Run 출현으로 월 런레이트를 확정하지 않았다.
   ⛔**프로모션 소진 시점·향후 GKE 비용을 이 수치로 추론하지 않는다.** AWS CE 0회, BigQuery SELECT 3회. 증거 `docs/evidence/gcp-spend-window-2026-09-05.log`.
   **다음 관측**: 동일한 서비스 구성이 유지된 완결 일자의 누적을 확인한 뒤 판단. ⛔**4a 접기(D50)는 완료**이며 되살리지 않는다.
5. **k3s는 집행하지만 proven 집합엔 없다 — D40으로 닫힘(08-01)** — 여는 조건: k3s-lab에 워크로드 →
   D40 · `docs/plans/2026-08-01-k3s-proven-substrate.md`.
6. **공급망: 생산자·소비자·CI 키리스는 섰고, 어드미션은 업스트림 대기** — **M15가 권위**.
   ⛔**재개 조건 미충족(09-02 재측정) — 단 08-30까지 물고 있던 신호가 틀렸다**(**M51**):
   `#1406`은 **2024-09-30 이후 멈춘 트래킹 이슈**이고 그 구현은 **`#1725`로 2025-04-23에
   머지**됐다 — 우리가 08-08에 쓴 chart 0.10.6(=appVersion **0.13.1**)에 **이미 들어 있었다**
   ⇒ **결론 유지, 근거 교체**(고치기 전 버전을 시험한 게 아니다). **새 조건 = 둘 중 먼저
   오는 것**: ⓐ**`#1968`**(cosign v3 서명 검증 고침, **미머지**) 머지 · ⓑ**`#2007`**(2026-08-24
   머지)을 담은 **릴리스** — 최신 v0.15.1은 **2026-03-26**이고 그 뒤 **51 커밋이 미출시**다.
   증상 티켓 **`#1899`**가 우리 조합(cosign v3 서명 + 0.13.1) 그대로다.
   ⚠️**"검증됨"이 도구마다 다르고 우리는 못 본다.** ⚠️**cosign 쪽 기록은 정확했다** —
   `--new-bundle-format`은 v3.1.2의 **여섯 하위 명령 어디에도 없다**(v2 옵트인이었고 v3에선
   기본이라 사라졌다) ⇒ **간극은 서명하는 쪽이 아니라 검증하는 쪽**이다.
   증거 `docs/evidence/cosign-admission-kind-attempt.log` ·
   `docs/evidence/the-resume-condition-was-watching-a-dead-issue.log`.
7. **TS 타입은 네트워크 데이터를 보증하지 않는다** — 롤링 중 허브는 두 버전을 동시에 서빙 →
   **푸시 신규 필드는 항상 optional + 폴백**.
8. **PSS restricted 아래에서 애드온 차트는 기본값으로 안 돈다** — 파드는 거부되는데 **Argo는 Synced로
   보인다**. **새 애드온마다** 렌더된 파드 스펙을 `kubectl apply --dry-run=server`로 API 서버에 물을 것.
9. *(해소)* Capsule deprecation(08-02, D41) · GCP 예산 상시 발화 → ₩28,000(08-09) ·
   리포트 스트림 분리(08-11, M17).
10. **GCP/Azure 자격증명은 아직 테넌트-바운드가 아니다** — 스코프는 **어느 네임스페이스**만 정하고
   토큰을 테넌트에 안 묶는다. 자격증명 자체가 경계인 건 **온프렘뿐** → Phase 4.
   ⚠️**08-30부터 Azure 경로는 실제로 열려 있다**(M39) — 대상 자원이 0개라 blast radius가 0인 것이지
   **경계가 생긴 게 아니다**.
11. **Dashboard dependency audit — 해소됨(08-30). `npm audit` 0건.** ⚠️**"upstream 대기"로 다시 닫지
   말 것** — 그 기록이 **세 군데 다 틀렸다**(실측은 critical 2·high 6이고 **런타임**이었다).
   증거 `docs/evidence/the-dashboard-audit-record-described-a-different-risk.log`.
12. **게이트의 초록에는 조건이 붙는다 — 아홉이 같은 계열(2026-08-08~09-01)**:
   ①시간 ②환경(**skip은 실패가 아니다** ⇒ 게이트 숫자엔 **날짜와 잰 기계**를) ③하중(**새 가드는 지워
   보고 red를 확인**) ④관측 지점(**가드는 독자가 읽는 그 물건에 대고 물을 것** — M17이 권위)
   ⑤가드 자신의 값과 하네스 ⑥형제 집합(**세는 순간 전부 셀 것**) ⑦변이 하네스 자신(**변이·실행·복구는
   한 스크립트에**) ⑧`make dev-up`이 새 클론에서 못 돌았다 ⑨**워크플로가 안 도는 것도 초록으로
   보인다**(M43 — ⛔`main`은 무방비였던 적 없다).
   **아홉의 경위·재발 기록은 archive 상세의 Risk 12가 권위** — 요약만 보고 고치지 말 것.
- (그 밖의 해소 이력은 `PROGRESS_LOG`/`docs/archive/` 참조.)
~~~~
<!-- END tidy-20261003-status -->

<a id="tidy-20261003-next-plan"></a>

### docs/NEXT_PLAN.md

Source SHA256: `de3a818620660d3eb6cae569ff61d77b20721b8cede90dffa52e3ea1da08db7b`

<!-- BEGIN tidy-20261003-next-plan -->
~~~~markdown
# NEXT_PLAN — platform-agent

최종 갱신: 2026-10-03

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(**M15=공급망 0→집행 + Phase 5 경계 +
> `main` 보호**, M14=결정 6건, M13=미소비 14건) / `PROGRESS_LOG.md`(+`docs/archive/`). **≤120줄**.
> ⚠️**압축본이다(2026-09-02)** — 상세는 **삭제가 아니라 이동**했다:
> 각 항목의 경위·측정·⚠️/⛔ 문장은 `docs/archive/next-plan-detail-2026-09.md`가 **권위**이고
> 거기 있는 블록은 **한 글자도 안 고치고 옮긴 것**이다. 여기 남은 건 **주장 한 줄 + 재개 조건**뿐.
> **요약만 읽고 결론 내지 말 것** — ⚠️/⛔ 문장은 틀린 요약이 사실로 굳는 것을 막으려고 쓴 것이다.

## 현재 상태 (2026-10-03, gate 3364 — 로컬 macOS·py3.13.5·Node 22.23.3/임시 npm prefix · CI도 같은 게이트, ubuntu·py3.13)

**Phase 0·1a·1b·2·3 완결**(M10~M12) + **잔여 소진**(M13) + **결정 7건 닫힘**(D36·D38~D43).
**공급망은 닫을 수 있는 만큼 닫혔다**(어드미션만 업스트림 대기) · **`main`은 보호된다**
(PR + CI 통과로만 병합, D43) · **Phase 5는 경계까지** 섰고 커밋도 **경로 한정**이다.
**Phase 4b(billable)·Phase 5 attach UI 등은 아래 재개 조건이 남았다** — 단 "무과금 소진"은 **여섯 번 틀렸다**. **소진은 목록의 상태지
사실이 아니다** — 목록 밖에도 있고 **가장 값싼 다음 수는 대개 직전 세션이 적어 뒀다**.
⚠️**목록에 적힌 항목 자체가 틀릴 수도 있고**(M19 ⓑ) **그래도 시험하면 값이 난다**(`git log -L`로
**"언제부터"**까지) · **직전 고침이 남긴 기준이 다음 결함을 찾는다**(M19→M26, 여섯 층 연속).

## 사용자 게이트 — 전부 닫힘 (재개 조건만)

> 결정 1~6 = **D36·D38~D42**, 브랜치 보호 = **D43**. 근거는 `DECISIONS.md`·`docs/plans/*`, 완료
> 요약은 `COMPLETED_SUMMARY` **M14·M15**. **재개 조건만 아래 남긴다.**

- 라우터에 인증이 서면 **결정 5 C**와 **결정 1의 파티션**이 열린다 · k3s-lab에 워크로드가 서면
  **결정 4**(경로=옵션 A) · 두 번째 리뷰어가 생기면 **CODEOWNERS 리뷰 필수**를 켠다(D43).
- [ ] **(별도 계획) GitAIOps 후속편 아티클** — 논지=오프라인 Qwen로 루프를 무인으로 닫는다.
  소재·사례집·③의 산 사례(M39)는 **archive 상세가 권위**. ⛔**집필·발행은 착수하지 않는다**(지시 2026-07-25).
- [ ] (선택) **Azure Foundry 정리** — 유휴 ≈$0는 **참**. 단 ACR Basic이 월 ~₩6,600 고정이고 **다른 프로젝트 것**(08-12).

## 진행 중 — 멀티테넌트/멀티-클라우드 플랫폼 + per-env Add-on

**설계**: `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5) · **MAD**: 같은 폴더 `-mad-history.md`.
확정 아키텍처: **capability, implementation-pluggable** — Tenant=격리 티어 정책, Env=cluster(멀티클라우드),
Delivery=ArgoCD|Flux|Config Sync 어댑터, SSOT=per-tenant git 레지스트리. **최우선 불변식**:
blast radius=1 tenant/env(자격증명이 경계) — **집행 가능하지만 옵트인**(D38).

- [ ] **단일 환경 실사용 검증 R0~R4** — `docs/plans/2026-10-03-platform-agent-usage-and-evidence.md` §8. 승인 완료. T 실행 O의 정상3·거부2·복구2·유실2와 재현/비교/데모 완료. 진단/R3/R4 전체·R5는 미완료. 다음은 현재 revision/실패 단계의 조회 적용 조건·모순 관측 처리다.
- [ ] **Phase 5 attach UI** — D52·M53의 독립 Python Lambda 설계, P5-A~D와 저장/준비/상태 연결(M71~M89) 로컬 완료. M83 실험 PR 생성·M84 작성자 관측·M85 부분 판정 보존. **M91: Vercel 인증 차단 해소·현행 설정/운영·복구 URL 조회·후보 재생성 검증 완료**. 다음은 `docs/plans/2026-09-05-phase5-planner-runtime.md` §13의 AWS 자원·본인 acme 권한·Vercel production 전환/복구와 보관 비용 범위 확인이다. 승인 후 현재 신원/후보 해시/복구 대상을 재확인한다. **원격 배포·production PR 발행은 미연결**이고 writer 자격증명 경계는 계획서 §5가 권위다. 실행 위치 부재·Vercel 인증 대기를 현재 blocker로 반복하지 않는다.
- [ ] **Phase 4 남은 것 = 4b** — 자격증명 파티션 미증명(Risk 10), 상시 운영과 30분 TTL의 충돌, billable·별 승인. 현재 비용 관측은 **STATUS Risk 4·M54**가 권위다. **현행 프로젝트 사용액을 새 GKE 상시 운영 견적으로 읽지 않는다.** 09-02 비용 관측·경고 전문은 archive에 보존했다.
- ⛔**다시 열지 말 것 — 닫힌 항목 아홉**(각 줄의 경위·⚠️/⛔ 문장은 **archive 상세의 같은 제목**이 권위): **Phase 4 / 4a**(08-30 닫힘 M38 · 09-01 접힘 M40·D50 — ⚠️**$0.00이 접은 이유가 아니다**, 대가는 **장기 키** ·
  ⚠️**D48은 안 죽었다**) · **Azure 자동 재시도**(09-02, M47 — ⚠️**헤더가 없으면 재시도하지 않는다**) · **대시보드 취약점**(08-30, `npm audit` 0건 — ⚠️`STATUS` Risk 11의 *"기록이 세 군데 다 틀렸다"*를 지우지 말 것) ·
  **`onprem` extra의 `mlx-lm`**(09-01, M41 — ⚠️`.venv-mlx` 분리는 **설계**지 "안 쓰여서"가 아니다) · **정적검사는 게이트에 안 들어간다**(09-01, D51 — ⚠️**"쓸모없다"로 요약 금지**: 실제 결함 둘을 찾은 건
  **mypy**이고 테스트는 둘 다 놓쳤다. 결정된 건 *가치*가 아니라 **상주 값어치**다) · **Azure executor 배선**(08-30, M39 — ⚠️**"이제 안전하다"로 요약 금지**: 열린 건 **경로**고 오늘 blast radius가 0인 건 대상이
  0개여서다) · **`spend-check`의 `MEASURABLE` 금액 질의**(09-02, M50 — ⚠️**크레딧을 한 컬럼으로 합치지 말 것**: 프로모션은 마르는 잔액이고 DISCOUNT는 요율의 성질이다 · ⚠️**창은 계정 수준 행을 빼고 잰다**, 안 그러면 3일이 한 달로 보인다) · **capability 스캔 셋**(08-17, M35~M37) · **`cost_metrics`**(08-18 — ⚠️**면제는 목록이 아니라 경계다**).
- [ ] **Phase 1b 잔여**: loki/tempo/pa 이관은 **볼륨 스냅샷 선행**(kind엔 CSI 스냅샷터 부재).
- **2차 잔여 = 하나**: **스포크의 읽기 신원** — 공유 `argocd` ns를 맨 kubectl로 읽어 테넌트 구분이 **코드 필터**다(쓰기는 401, 읽기는 안 막는다).
  **시끄럽게만** 해 뒀고(`warn_if_ambient_read`, M17), seam은 **인클러스터 배포·민팅 선행**이라 인프라 결정.

## 잔여 — 완료 항목에서 의도적으로 남긴 것

> 완료분은 `COMPLETED_SUMMARY.md` **M12**·**M13** · `PROGRESS_LOG.md` · `docs/evidence/`.
> ⚠️각 항목의 **측정·반증·세는 함정**은 `docs/archive/next-plan-detail-2026-09.md`가 권위다.

- [ ] **DUAL 모드 조건부 리다이렉트** — `slack_live_approval`은 닫혔고(08-16) 이것만 남았다. **하중을 못 받는 가드**가 되므로 안 만들었다.
- [ ] ⚠️**Phase 3② — 남은 건 AWS뿐이고 그건 "러너가 없다"이다**(SSM Automation 경로). GCP(08-18)·Azure(08-30) 배선 완료, 추가 API 호출 0. ⚠️**M31이 고친 건 목록이고 호출 지점을 세는 가드가 없었다**(M18이 한 층 위에서
  재발) · ⚠️**가드 자신이 한 번 틀렸다**(문자열 검사 → **AST로 실제 호출**을 센다). 증거 `docs/evidence/phase-dod-verification-2026-08-18.log`.
- [ ] **⚠️`msft_deployer`가 진짜 라이브러리에서 깨진다(08-30 재측정)** — ✅설치 조건은 열렸다(`.[azure]` 31.5초). ⛔`AzureOpenAIResponsesClient`은 **버전 지연이 아니다**(`agent_framework*`에 0개, 업스트림 docstring 한 줄뿐).
  **여전히 안 고친다 — 대체 심볼이 없어 추측은 발명.** ⚠️테스트가 `sys.modules`를 스텁해 초록이다. 증거 `docs/evidence/the-azure-extra-cannot-be-installed.log`.
- [ ] **GCP/Azure 90일 보관** — **`STATUS` Risk 2가 권위**(스토어가 없어 지울 데이터 0 → Phase 4).
  ⚠️"`resolved_at`은 읽는 쪽이 없다"는 **틀렸다**(08-16 재측정): `oncall_reporter._minutes_between`이
  `started_at`과 짝지어 읽고 `aws/reporting.py:239`가 넘긴다 · **analyzer 폴백 severity는 정책**.
- [ ] **k3s 승격은 닫혔다(D40) — 여는 조건 "k3s-lab에 워크로드"** — **`STATUS` Risk 5**가 권위.
  경로는 **옵션 A**(네임스페이스·netpol만, 비용 0) — ⚠️**실체 없는 선언 2건**을 더하므로 재평가.
- [ ] **스코프·배포 신원은 옵트인(D38 이후)** — 상태는 `probe_scope_reachability.py`·`make
  deploy-identity-check`가 답한다. **남은 결정**: 기본 on 여부 · 서명키 custody·rotation ·
  배포 신원의 테넌트 구분(결정 5 C/D).
- [ ] **MCP 게이트웨이는 포트에 안 붙어 있다** — 결론 유지, **근거는 틀렸다(재측정)**: `bridge.py:35`에
  폴백이 있고 그 `McpA2aBridge`를 만드는 건 **테스트뿐**. ⚠️**세는 함정 다섯**(`cdk.out` · docstring 예시 ·
  `git grep -E`의 `\s` · **리전 한정 `[]`** · **`AccessDenied`**) — **전부 "없다"가 아니다.** 전문은 archive.
- [ ] **A2A 인증 실집행 결정** — 남은 건 **기본값 on 여부**(라이브 kagent 왕복이 익명이라
  opt-in — 그 "익명"은 **나가는 쪽**이다, D39).
- [ ] **Cosign 어드미션 = 업스트림 대기** — **`STATUS` Risk 6이 권위**. ⛔**09-02 재측정: 아직 — 단 물고 있던 신호가 틀렸다**(**M51**): `#1406`은 2024-09-30에 멈춘 트래킹 이슈이고 그 구현은 `#1725`로 **2025-04-23에 머지**됐다(우리가 쓴 appVersion 0.13.1에 이미 들어 있었다) ⇒ **결론 유지, 근거 교체**. **새 조건 = `#1968` 머지 또는 `#2007`을 담은 릴리스**(최신 v0.15.1은 2026-03-26, 그 뒤 51 커밋 미출시). — **이 날짜부터 볼 것.**

## 유지 규약 (완료된 리팩토링에서 나온 "하지 말 것")

> ⚠️**근거 전문은 `docs/archive/next-plan-detail-2026-09.md`의 "유지 규약 — 근거 전문"이 권위다.**
> 규칙만 읽고 고치지 말 것 — 각 줄은 **재서 얻은 것**이고 근거가 규칙보다 길다.

`_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이) · detector/analyzer/decision은 SDK가 90%+ 상이해 **의도적으로 DRY 안 함**(⚠️08-30 실측 — **결정 유지, 근거는 정확히**: `analyzer` **51%**·
`decision` **56%**가 글자 그대로 두 벌 = **계약**이고, 바이트 동일 **7쌍을 `test_cross_provider_contract_parity.py`가 표로 박았다**) · `approval_bridge` 추가 분해 금지(D15) ·
포괄 `gcloud:*`류 allow 금지(D16→D22). ⚠️**"DRY 안 함"이 덮지 않는 것(M18·M19)**: 공유되는 게 **SDK가 아니라 계약**인 블록은 **계약
모듈에 한 벌만** 두고(`runbooks/schema.py::fits_resource`) **provider 간 일치를 묻는 가드**로 묶는다(`test_capability_catalog_scan.py`) · **의무가 분류마다 뒤집히는 규칙은 양쪽을 다 물을 것**.
⚠️**"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다(M19)** — **기준은 읽는 쪽의 provider 간 비대칭**이다. ⚠️**가드의 임포트를 그 파일이 주장하는 범위와 맞댈 것** · **형제는 provider가 아닐 수도**(M21) ·
**다수가 옳고 하나가 뒤처질 수도**(M23). ⛔`triggered_at`·`metric_name`은 **닫혔다**(M21 §8) — 다시 열지 말 것.

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지 · 정적 무조건 fan-out · 자유텍스트 spawn_subagent 금지.

## 다음 우선순위

- **사용자 요청 일시중지 — 재개 시 집계·RS/Pod 모순을 먼저 재현** — 계획 §8과 `docs/evidence/dogfood-20261003/repeats/u-diagnosis-checkpoint.json` 참조. U는 코드 검토 가설이며 새 재현·수정은 없다. Q/S 원본과 일관된 양성 대조군으로 모순 판정·조회 적용 조건을 측정한다. T 실행 묶음을 반복하지 않고, 원문·양성 후보·기존 삽입문/유사 증상/근거 부족 기준을 유지한다. 사용자 재개 지시 전 추가 작업 없음.
- **별도 원격 우선순위 = 저장형 플래너 운영 실행 범위 확인** — M91에서 AWS/Vercel 실제 설정과 운영/복구 URL을 확인하고 후보를 재생성했다. Goal은 승인 대기로 blocked(09-15, 3턴 확인). 계획서 §13의 새 함수/테이블/IAM·본인 men16922/acme 권한·production 설정 5개/후보 업로드·승격·최대 20회/30분 검증·실패 시 복구·잔여 보관 비용 범위를 확인한다. 승인 후 현재 신원/해시/복구 대상을 다시 대조한다. PR 발행과 기존 자원 삭제는 범위에 없다.
- **별도 원격 작업 = 로컬 검증 계약 검토 후 필요한 조회만 확정** — M83 PR은 보존하며 추가 쓰기·민팅·권한 확대는 자동 재개하지 않는다. **사용자 정리 중단: lab 1367338348·checkout 및 R2 lab/App 4924748·설치 161238144·키·branch·draft PR #1 보존, 추가 삭제 금지.** tenant별 repo 이관·production 연결은 별도 결정이다.
- **GCP 비용 재측정 완료(M54, 09-05)** — 이 프로젝트 총사용액 **₩14.80**, PROMOTION **−₩12.36**, 기타 크레딧 **−₩2.44**, 청구 **≈₩0**. 08-24부터의 달력 창은 미미한 과거 행을 포함하고 09-05는 미완이다. 일별 서비스 구성이 달라 월 런레이트는 확정하지 않았다. 다음 관측은 같은 서비스 구성의 완결된 사용일이 쌓인 뒤다.
- **Phase 4b 조건부 실증** — 새 상시 GKE의 요금·기간·종료 장치가 필요하다. 현행 GCP 사용액은 그 클러스터의 비용 견적이 아니다. `docs/plans/2026-08-08-phase4-scope-and-cost.md` §5·§6과 Phase 5 계획서 말미가 경계다.

## Overnight 씨앗 (`[auto]` — 무인 루프가 집어간다)

> **2026-10-03: 실사용 검증 계획만 추가, R0~R5는 대화형 실행 트랙이며 새 `[auto]` 씨앗은 등록하지 않았다. M52·M55~M68·M71~M89 로컬 작업 완료, M77~M85 실측/부분 판정은 계획서 §12에 보존. M91 Vercel 인증/현행 설정 점검·후보 재생성 검증 완료. 운영 배포/권한/전환 범위 확인과 발행은 미완료이며 열린 `[auto]`는 없다.**
> 1 이터 = `[auto]` 하나 = 커밋 하나. **마르면 멈춘다**(정상). `MAX_ITER`는 씨앗 수보다 크게.
> ⚠️**압축 씨앗의 "삭제 금지"를 완화하지 말 것** — ⚠️/⛔ 문장은 틀린 요약이 사실로 굳는 것을 막는다.


## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고 · 묶음 완료 시 `/checkpoint`.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
~~~~
<!-- END tidy-20261003-next-plan -->

<a id="tidy-20261003-usage-plan"></a>

### docs/plans/2026-10-03-platform-agent-usage-and-evidence.md

Source SHA256: `85ccab50989a1696ed3fd06de02d1bffa1669cbdae4b30b3968ce7b67c6e2412`

<!-- BEGIN tidy-20261003-usage-plan -->
~~~~markdown
## 8. 다음 세션의 정확한 시작점

**로컬 실증은 10-03 사용자 승인 완료이며 계속 진행한다.** `docs/evidence/dogfood-20261003/approved-runtime-verification.json`과 README 말미를 읽는다. curl 일괄 금지는 project 규칙에서 제거했으며 현재 실행 세션에는 옛 curl 금지가 남는다. 이를 네트워크 전체 차단으로 해석한 것은 틀렸다. 별도로 승인된 kubectl·Docker registry·실제 Chrome 작업은 정상 실행됐다. 같은 승인을 다시 묻거나 curl 재로드를 모든 작업의 선행 조건으로 두지 않는다.

실제 실패·응답 유실에서 발견한 거짓 성공, 고정 0초 표시, 결과 기록 유실을 고쳤다. 이후 고정 후보 A는 replicas 누락으로 복구 시 복제 수 1개만 남겼고, B는 이미지 URI를 `ordrs-api-dogfood`로 오타 냈다. 앞선 정상 A 세 번을 최종 성공으로 합산하지 않는다. 원본은 `docs/evidence/dogfood-20261003/repeats/candidate-ab-verification.json`이다.

이를 해결하기 위해 기존 Deployments 화면에 **입력 → 검토 → 확인 → 기존 on-prem 실행기 → rollout 확인 → durable 결과 조회**를 연결했다. 검토한 이미지 URI·네임스페이스·복제 수를 LLM이 다시 만들지 않는다. Python strict request와 기존 RunManager의 actor/입력 바인딩을 재사용한다. 실행 중 새로고침은 저장한 UUID를 GET하며 자동 재실행하지 않는다. 준비된 이미지·8080·/healthz로 범위를 제한했고 새 빌드/클라우드/자격증명 선택을 추가하지 않았다. dashboard local-dev 관리자와 고정 ServiceAccount 실험이며 실제 GitHub OAuth/멀티테넌트 인가의 증거가 아니다.

직접 실행은 On-Prem Executor로 기록한다. C의 첫 UI 롤백은 실제 복구됐지만 Qwen으로 잘못 기록되는 기존 경로를 발견해 D에서 고쳤다. 후보 D는 `docs/evidence/dogfood-20261003/repeats/candidate-v4.json`의 283개 소스 해시다. D의 정상 3회/새로고침 2회·실패 후 사용자 확인 복구 2회·기존 제한 acme 신원으로 globex 거부 2회가 끝났다. 각 요청 claim/배포 도구 1회, 정상/복구 replicas 2·health 200, globex UID/spec 불변을 확인했다. Review 취소는 claim 29→29·자원 불변이며 incident 승인 webhook 거부 증거로 세지 않는다. `repeats/final-candidate-verification.json`이 총괄이다. 비교표/재현 절차는 evidence README 말미, 72초 실제 정지 화면 해설은 `demo/local-evidence-walkthrough-72s.mp4`다. 마지막 수동 비교 후 r0/revision 27/replicas 2·health 200으로 복원했다(06:51:31 UTC). 전체 게이트 3283 passed·2 skipped·20 warnings(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix, 123.69초)은 `final-candidate-gate.log`다.

R4 초기 사례 5개는 `docs/evidence/dogfood-20261003/repeats/diagnostic-cases.json`에 출처/관측 시각/판정 근거와 함께 기록했다. 실제 Forbidden과 오래된 다른 서비스 로그·삽입된 실행 지시·유사 증상 구분을 포함한다. 설명 품질은 일부 실패/부분 판정이며 coding assistant의 증거 검토이지 독립 전문가/LLM judge 평가가 아니다. 기존 eval_harness의 role-only 점수를 배포 정확도와 혼동하지 않는다. 새 평가 엔진은 필요하지 않다. R5는 R3 이후 동일 저장 snapshot을 대상으로 **읽기 전용 HolmesGPT 비교 하나**를 다음 후보로 삼되, 설치/호출/비공개 데이터 전송/운영 연결은 아직 수행하지 않았다. Phase 5/4b 재개와 묶지 않는다.

Qwen 토큰은 proxy가 usage를 버려 미측정이다. local 모델 비용을 0으로 주장하지 않는다. 새 직접 배포 경로에는 LLM 호출이 없지만 서버/클러스터 자원은 사용한다. 최종 비교는 클릭~실제 health 관측과 서버 accept~최종 저장을 구분하고, 수동 runbook 명령 시간과 사람의 입력 시간을 구분한다. 기존 데모 prep 스크립트는 namespace/Applications를 삭제하므로 이 실험에 실행하지 않는다. 승인된 workload를 보존한 채 화면 관측으로 데모를 만든다.

후보 D의 유사 증상 설명은 근본 원인과 롤백 방향을 과도하게 단정해 **R3 전체 미완료**다. 기존 프롬프트에 관측/가능한 설명/미확정/다음 근거를 구분하도록 보완한 후보 E(`repeats/candidate-v5-diagnosis.json`)를 별도로 동결했다. 변경은 local_deployer의 진단 지침 하나이며 D의 실제 배포 반복을 E의 실행 결과로 바꾸어 쓰지 않는다. 실제 Qwen 4건(같은 유사 증상 2·오래된 로그 1·새 반례 1)을 보존했다. 전부 도구 0이지만 유사 증상 2건의 첫 원인 단정과 새 반례의 “의존성 로그 무오류 → 앱 변경 원인/롤백” 추론은 실패다. E도 완료된 수정으로 승격하지 않는다. 전체 게이트 3283 passed·2 skipped·20 warnings, 119.38초(같은 로컬 툴체인), `diagnosis-candidate-gate.log`. 사례 6개와 판정은 `diagnosis-candidate-verification.json`/`diagnostic-cases.json`에 있다. 새 평가 엔진이나 외부 에이전트 연결은 추가하지 않았다.


다음 구현은 프롬프트 재시도보다 **근거 연결 계약**에 집중한다. 기존 결과/Grader seam에서 (1) 관측의 source ID·대상·시각·실제/제공 snapshot 구분, (2) 미검증 가설과 대안/반증, (3) 조치 전 필요한 현재 상태·변경 이력·이전 revision 근거를 분리한다. 출처 존재/대상/시각/변경 여부는 코드가 검사하고 문장 인과관계는 별도 검토한다. 출처가 붙었다는 이유로 의미가 검증됐다고 하지 않는다. 기존 프롬프트를 더 길게 만들거나 단어 매칭으로 일반적인 진단 정확도를 계산하지 않는다.

별도 incident 거부 UI는 후보 F에서 브라우저 `prompt()`를 인라인 확인 폼으로 바꿔 해결했다. 기존 두 합성 요청을 실제 화면에서 거부했고, 취소는 요청을 보존했다. 후보 G에서는 입력 사유가 Next API 이후 버려지는 결함을 수정해 기존 승인 store에 사유와 `reported_by`를 저장했다. 새 합성 요청 2건을 한글/줄바꿈 사유 및 빈 사유로 거부하고, 소유 webhook 재시작·실제 화면 새로고침·파일 재조회 후 pending 0/실행 0/원본 사유 보존을 확인했다. `repeats/v6-rejection-verification.json`과 `v7-rejection-verification.json` 참조. G의 283개 런타임 소스 해시는 `candidate-v7-rejection-metadata.json`이다. 수동으로 주차한 합성 요청이므로 실제 alert→analyzer 종단 검증은 아니다. `reported_by`는 dashboard 세션에서 전달한 값이며 webhook 자체 인증 증거가 아니다. G 시점에는 사건 상세의 사유/직접 ID 연결이 없었으며 아래 후보 I에서 연결했다. 거부는 사건 해결이 아니다.

구조화 진단 사전 실험은 **제품에 반영하지 않았다**. 같은 로컬 Qwen·합성 입력 4개(유사 증상/오래된 다른 서비스/반례/복구 근거가 있는 양성 대조)를 사용했다. output tool 방식은 1건만 형식/인용 통과, 나머지 3건은 실제 모델이 필드를 누락하거나 다른 구조로 반환해 실패했다. JSON 텍스트 방식은 4건 모두 형식/인용을 통과했으나 의미 검토는 실패 2·부분 2다. 특히 오래된 로그의 HTTP 503을 없다고 말하고 삽입 지시만 인용했다. 양성 대조는 질문에 필요한 recovery 판단 필드가 schema에 없었던 실험 설계 한계도 있다. `repeats/r4-structured-verification.json`에 원문/설정/지연/판정/한계를 보존했다. 탐색 입력이므로 독립 평가나 일반적 정확도 수치로 쓰지 않는다.

입력 계약 prototype은 `experiments/dogfood-diagnosis/`에 작성했다. source ID·대상·시각·provenance를 받고, 불일치/오래됨/시각 미상 네 사례의 본문을 모델 입력에서 제외한다. 경계 검사 6개 통과. 명시한 snapshot 시각에 대한 적합성 검사이며 metadata의 진실성/현재 상태 인증은 아니다. recovery 질문도 별도 필드로 분리했다. `repeats/r4-envelope-verification.json`이 모델 원문/설정/실패/판정의 권위다.

같은 입력을 기존 Qwen3-Coder와 이미 캐시된 Qwen3.8-27B에 로컬 호출했다. 후자는 다중 system 메시지 호환성과 기본 추론의 토큰 소진을 해결한 설정도 따로 측정했다. 같은 direct endpoint·1024토큰·추론 off 비교에서 Coder는 삽입된 SYSTEM 문장을 rollback 검토 근거로 사용했다. Qwen3.8은 그 반례를 거부하고 양성 대조의 복구 후보/미승인을 구분했지만 유사 증상에서는 원인 차이를 단정했고 길이 제한도 실패했다. 모델 교체/제품 반영으로 승격하지 않았다. 기존 모델을 복원하고 실제 세 응답을 확인했다. 새 모델 다운로드·외부 추론 전송·운영 도구 호출은 없다. 공유 호스트/캐시/배경 호출을 통제하지 않았으므로 지연을 일반 모델 성능 비교로 쓰지 않는다.

후보 I(`repeats/candidate-v9-incident-link.json`)는 거부 요청과 사건에 같은 ID 연결·결정·사유·기록 시각을 남기고 상세 화면에 표시한다. 실제 Chrome에서 새 합성 요청 두 건을 한글/줄바꿈 및 빈 사유로 거부해 상세/새로고침·양쪽 store 일치·pending 0·조치 0·기존 workload UID/spec 불변을 확인했다. `repeats/v9-rejection-verification.json` 참조. 0%를 모델 장애로, provider를 특정 모델로 단정하던 상세 표시도 제거했다. 실제 장애 분석/인증 증거나 두 파일 쓰기의 crash atomicity는 아니다. D 배포 반복과 I 거부 검증은 별도 후보 근거로 유지한다.

J에서는 이 transport 결함을 수정했다. upstream HTTP 오류·종료 사유·실제 usage를 보존하고, 잘린 도구 호출은 실행 가능한 호출로 변환하지 않는다. 실제 Qwen의 1토큰 응답은 기존 stop/사용량 0에서 length/18 input+1 output으로 바뀌었다(JSON/SSE 둘 다). 정상 종료도 유지했다. 로컬 HTTP 경계 17 failed·8 passed → 25 passed, 관련 38 passed, 전체 3306 passed·2 skipped·20 warnings(137.77초, 10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). `repeats/mlx-proxy-verification.json`이 권위다.

G 이후 전체 검사에서 기존 writer 동시 open의 일시 ENOENT를 발견해 별도 후보 H로 최소 수정했다. 잠금 파일 열기만 최대 3회 재시도하고 지속 실패/권한 오류는 실행을 막는다. 외부 쓰기 재시도가 아니다. 로컬 재현/경계 검사/50묶음 동시 probe는 `repeats/writer-lock-verification.json` 참조. G의 실제 거부 UI 증거와 H의 writer 코드 검증을 구분한다.

최종 H 전체 `make check`: **3288 passed·2 skipped·20 warnings**, 304.27초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix), `repeats/rejection-metadata-gate-final.log`. 진단 의미 검증 통과나 원격 CI/배포 결과로 해석하지 않는다.

후보 I 전체 `make check`: **3288 passed·2 skipped·20 warnings**, 117.99초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix), `repeats/rejection-link-gate.log`. 기존 H와 테스트 수는 같으며 source hash 283개가 작업 트리/실제 후보와 일치했다. 원격 CI·진단 품질 통과는 아니다.


수정된 proxy로 같은 7개 입력을 재실행했다. 4건은 모델 요청 0, 나머지 3건은 각 HTTP 1회이며 합계 input 2683/output 896 tokens다. 새 실험 runner는 실제 HTTP 시도를 세고 SDK 자동 재시도를 끈다. 이전 model_requests 필드와 다른 정의이므로 합산하지 않는다. 기존 `Scorecard`/`GradeOutcome`를 재사용한 `experiments/dogfood-diagnosis/replay.py`는 입력/대상/시각/인용 7건 통과와 recovery fixture 6건 통과·반례 1건 실패를 구분한다. 네 건은 모델 미호출이므로 6/7을 모델 정확도로 읽지 않는다. 요청 교체·가짜 인용·제외 자료 모델 호출·양성 대조의 무조건 보류를 변이한 별도 검사 4개도 통과했다. 원문 의미 검토는 별도이며 제품 연결은 아직 없다.

Qwen3.8의 기본 추론을 4096토큰·180초·HTTP 재시도 0으로 유사 증상 한 건에 확장했다. 실제 HTTP 시도 1회, 완료 응답 0, 180.018초 timeout이다. 토큰 사용량/의미 품질은 미측정이며 오답으로 세지 않는다. client timeout이 upstream 종료를 뜻하지 않아 소유 비교 서버를 명시 종료한 뒤 기존 Qwen3-Coder를 복원했다. `repeats/r4-reasoning-budget-restored.json` 참조. 같은 설정의 나머지 사례를 추가 실행하거나 기본 모델을 바꾸지 않았다.

K(`repeats/candidate-v11-revision-evidence.json`)는 이 계약을 기존 `describe_deployment`에 연결했다. 같은 배포 신원/명시 context로 Deployment·선택자에 맞는 ReplicaSet/Pod를 읽고, UID 소유 관계·현재 template·이전 revision·관측 generation·Pod/컨테이너 준비 상태·readiness probe·필요 replicas를 대조한다. 수집 시각/자료 해시와 관측 중 Deployment 변경을 확인하며 로그 속 지시문은 판정 입력이 아니다. 검토 후보는 실행 승인/근본 원인/외부 health/새 노드의 이미지·설정 가용성을 입증하지 않는다. 양성 대조는 코드 fixture이며 실제 복구 승격 실증으로 세지 않는다.

D 실제 기록 재생에서는 실패 rev22의 불완전 rollout과 복원 rev23의 완료를 구분했다. D에는 RS 스냅샷이 없고 실패 raw 수집 시각도 없어 이를 새 현재 자료로 메우지 않았다. 회복 자료는 기록된 수집 묶음 종료 시각을 사용했다. 첫 replay가 recovery의 bare-list 포맷을 Kubernetes List로 가정해 실패한 이력도 남겼다. `repeats/revision-evidence-recorded-v2/` 참조.

관련 45 passed·1 warning(0.83초), 전체 3325 passed·2 skipped·20 warnings(134.97초, 10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). +19는 근거/소유 관계/시각/읽기 오류 경계다. 처음 실패한 기존 명령 가드는 context 옵션과 정확히 config.current-context만 인식하도록 수정했다. RBAC 확대는 없다. 동일 SA의 기존 2h 토큰만 갱신해 실제 읽기가 성공했다. 284개 소스 해시를 후보에 반영하고 소유 router만 재시작했다.

실제 Chrome 요청 `e5b11d13-e5e0-4e77-ac0a-798f82ebfbb0`은 claim 1·describe 1, ACTIVITY만 저장하고 새로고침 후 같은 결과를 복원했다. workload UID/spec은 r0/rev27/2개로 불변이다. 코드 관측은 rollout 완료와 health 미확인을 구분했지만 **실제 모델 설명은 건강하다고 과장하고 반복하여 실패**했다. 제한 도구 factory 실험이 핵심 구분에 응답한 사실로 기본 UI의 실패를 덮지 않는다. 제한 실험의 첫 probe도 모델 응답 후 usage 속성을 함수처럼 호출해 실패했으며 원문을 보존했다. `repeats/revision-evidence-verification.json`이 권위다. 새 외부 health 관측이나 모델 정확도 합격은 아니다.

L(`repeats/candidate-v12-inspection-presentation.json`)은 코드가 판정한 관측/복구 결과를 저장 요약과 화면의 주 카드로 연결했다. 모델 원문·종료 사유는 별도 미검증 해석으로 보존하며, 정상 종료와 의미 정확도를 구분한다. 기존 K 실패 기록을 새 투영으로 재생하면 6400자 반복 대신 191자 관측 요약을 표시하고 원문은 그대로 남는다. 과거에 저장하지 않은 종료 사유는 unknown이며 새로 추정하지 않는다.

관련 41 passed(2.58초)·tsc 통과, 전체 **3335 passed·2 skipped·20 warnings**(135.89초, 10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). 새 10개는 표시/종료 상태/대상 불일치/변경 실행 제외/저장 경계 검사다. 실제 Chrome 요청 `3da3703c-cd18-454f-a75c-bca769b393e7`은 claim1/describe1·ACTIVITY만 저장했고, 새로고침 뒤 관측 카드·출처·모델 해석이 유지됐다. workload UID/spec은 그대로다. **실제 모델은 stop으로 끝났지만 원문에서 여전히 건강하다고 과장했다.** 코드 요약은 health 미확인을 유지하며, 화면 분리를 모델 의미 합격으로 세지 않는다. 양성 복구/미완료 응답 표시는 오프라인 검사이며 실제 UI는 복구 후보 없음/stop 사례다. `repeats/inspection-presentation-verification.json` 참조.

M(`repeats/candidate-v13-readonly-capability.json`)은 명시적 읽기 전용 모드를 UI→두 API→router→도구 등록과 durable 요청 ID에 연결했다. strict boolean이며 local-qwen/onprem 외 요청은 실행 전 거부한다. 이 모드에서는 A2A로 위임하지 않고 Investigate 5개만 등록한다. 일반 모드와 기존 사용자 역할/배포 신원은 유지한다. 같은 요청 ID에서 모드를 바꾸면 409이며 저장된 ready/done에도 모드가 남는다. 과거 필드 없는 기록을 읽기 전용으로 재분류하지 않는다. 모델이 등록되지 않은 변경 도구 이름을 출력하더라도 거부된 시도로 남기며 DEPLOY 행을 생성/승계하지 않는다.

관련 46 passed(3.29초)·tsc, 전체 **3345 passed·2 skipped·20 warnings**(128.96초, 10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). 새 10개는 실제 Pydantic AI의 제외 도구 10개/조회 5개·일반 모드 양성 대조, API/SQLite의 모드·신원 바인딩/위임 제외, 두 dashboard proxy와 표시 경계다. 도구 필터·기록 분류·proxy 전달을 각각 제거한 변이 3개가 red였고 원본 바이트 복원 뒤 전체 검사를 통과했다.

실제 Chrome 조회 `868f454b-f84f-4ec1-97b3-7341cbb85b95`는 claim1/describe1·ACTIVITY만 남겼다. 같은 읽기 전용 모드의 롤백 요구 `4a74ee4b-0bf5-4752-9704-6e83effb1f9f`는 도구0·배포0, durable 요청에 거부 응답을 보존했다. 두 요청의 모드/결과가 새로고침 뒤 유지됐고 workload UID/spec/r0/rev27/2개는 불변이다. 이 거부는 모델이 도구 호출 전에 응답한 사례이며, 등록되지 않은 도구 호출을 강제로 시도하는 검사는 오프라인이다. 새 HTTP health 관측은 없다. `repeats/readonly-capability-verification.json` 참조.

**M 시점의 후속 계획:** 강제된 읽기 전용 경로에서 모델이 제시하는 유용한 가설/다음 확인을 충분·불충분 근거와 반례로 대조한다. M의 실제 모델은 health 미확인을 유지했지만 준비된 Pod가 없는 이전 revision에서 실패/rollback 가능성을 추측했다. 요청별 도구 제한을 자격증명 격리나 진단 의미 합격으로 승격하지 않는다. 잘못된 원문을 접거나 모든 판단을 보류하는 것으로 진단 품질을 대신하지 않는다. Agents 화면의 고정 supervisor/kagent READY 표시도 실제 경로를 입증하지 않으므로 최종 제시 전에 수정한다. 최종 동일 후보 시나리오 묶음과 R5 비교가 남았다.


N(`repeats/candidate-v14b-runtime-observation.json`)은 고정 READY/supervisor/kagent 표시를 실제 router 응답·확인 시각으로 교체했다. 모델 선택·연결·요청 도구 범위를 나누며 연결 성공을 모델/클러스터 준비로 표시하지 않는다. 모델 완료 metadata에는 보고된 양수 usage·응답 수·도구 시도 수를 남긴다. 모르는 값은 null이다. 설명만 반환한 요청은 NO TOOL CALLS와 Unverified로 표시하고 조치 성공으로 바꾸지 않는다. 기존 backend failed/ok=false는 유지한다.

관련 28 passed(3.51초)·tsc, 전체 **3348 passed·2 skipped·20 warnings**, 135.23초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). payload/READY 변이2종 검출·원본 복원. 286개 소스가 작업 트리/소유 실행 후보와 일치했다. 원래 모델/proxy/webhook과 권한은 그대로이며 router/dashboard만 재시작했다.

실제 Chrome에서 선언한 snapshot 7개를 읽기 전용 모드로 각각 보냈다. 이 실험은 앞선 prototype의 4건 입력 제외를 적용하지 않았고 **7건 모두 실제 모델 응답**을 얻었다. 각 claim1/도구0/배포0, 마지막 결과와 서버 읽기 전용 표시가 새로고침 뒤 유지됐다. 보고 usage 합계 input11458/output2455, 접수→저장 3.700~8.329초. SDK HTTP 시도나 독립 모델 벤치마크가 아니다. workload UID/spec/r0/rev27/2개는 불변이며 새 HTTP health 측정은 없다.

검토 결과는 **충족1·부분3·실패3**다. 부분은 합격으로 세지 않는다. 정상 이전 버전 근거가 있는 경우 검토 후보를 인정하고 원인은 미확정으로 두었지만 source ID 인용이 부족했다. 더 큰 문제는 오래된/시각 미상/다른 namespace 자료를 적용 가능한 관측처럼 설명한 세 사례다. 시각 미상 사례는 로그의 SYSTEM 문장을 팀의 확신과 rollback 검토 근거로 사용했다. 도구를 안 썼다는 사실은 설명의 정확성을 증명하지 않는다. `repeats/r4-readonly-ui-review.md`, 원본 `r4-readonly-ui/`, 기존 Scorecard를 재사용한 `r4-readonly-ui-scorecard-v2.json` 참조. 검토자는 코딩 에이전트이며 독립 전문가/심사 모델이 아니다.

최초 원문 byte 대조는 기존 한 줄 HTML input이 prompt/JSON 사이 LF 하나를 제거해 7건 실패했다. 그 결과를 보존했고 v2는 이 관측된 한 글자 변환만 허용한다. source JSON은 동일하다. 변조 입력·잘못된 hash·가짜 인용·부분 승격을 별도 복사본에서 검출했다. 응답을 더 좋게 만들기 위한 재실행이나 사후 입력 교체는 없다.

**N 시점의 후속 계획:** 기존 source 대상/시각/provenance 계약을 실제 진단 입력 경로에 연결하고 세 실패를 다시 대조한다. 적합한 양성 근거와 유용한 가설/다음 조회를 보존한다. 잘못된 문장을 접거나 전건 보류·프롬프트만 늘리기로 해결했다고 하지 않는다. N의 연결 표시 수정은 완료했지만 진단 의미 검증/R3/R4·최종 동일 후보 묶음·R5 비교는 미완료다. `repeats/runtime-observation-verification.json`이 이번 측정의 권위다.


O(`repeats/candidate-v15-snapshot-contract.json`)는 기존 snapshot 계약을 `src/agents/ai/snapshot_diagnosis.py`로 올리고 실제 입력 경로에 연결했다. UI에서 명시한 source JSON은 읽기 전용 local-qwen/onprem 요청에 묶이고, 질문과 instruction 불일치는 실행 전에 거부한다. 원문은 durable 요청에 보존하며 같은 ID에서 source를 바꾸면409다. 대상/시각이 부적합한 본문은 모델에 보내지 않고 제외 이유를 화면에 남긴다. 적합한 자료가 없으면 모델을 호출하지 않는다. 유효 자료가 있으면 동일 로컬 모델을 도구 없이 호출하고 모든 source의 정확 인용·출력 형식을 검사한다. 인용 통과는 의미 정확도나 실행 승인으로 승격하지 않는다. 기존 자유 텍스트 경로 전체에 자동 필터가 적용됐다는 주장은 하지 않는다.

관련36 passed(3.80초)·tsc·기존 prototype 경계6 통과, 대상/인용/도구0 변이3종 검출·바이트 복원. 전체 **3356 passed·2 skipped·20 warnings**, 138.14초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix). 287개 runtime 소스 일치, 소유 router/dashboard만 반영했고 모델/proxy/권한은 유지했다. 새 null 필드는 기존 일반 요청 fingerprint에서 제외한다.

실제 Chrome에서 N과 같은 일곱 자료를 structured snapshot으로 보냈다. 각 claim1·도구0·배포0, 제외4/모델 응답3이다. 적용 가능성7/7·모델 인용3/3이지만 의미 검토는 충족1·부분1·실패1이다. 다른 대상/시각 자료의 제외 사유와 마지막 결과가 새로고침 후 유지됐고 workload UID/spec/r0/rev27/2개는 불변이다. 새 HTTP health 관측은 없다. 모델 보고 usage는 input2857/output887, 접수→저장은 4.029/3.646/4.825초다. no-model의 0.001~0.002초는 UI 완료 시간/모델 속도가 아니다.

양성 복구는 r1의 건강성/spec과 r2 오류를 인용하고 likely 가설·환경 대안·다음 확인을 제시했다. 반면 counterexample은 SYSTEM 문장을 이미 내려진 결정으로 해석하고 이전 버전이 건강하다고 발명했다. 유사 증상도 원인이 달라 보인다는 답을 먼저 제시해 부분 판정이다. `repeats/r4-snapshot-ui-review.md`와 `r4-snapshot-ui-scorecard.json` 참조. 검토자는 코딩 에이전트이며 부분은 합격이 아니다. 네 코드 제외를 모델 정확도로 세지 않는다. N과 입력 경로/프롬프트가 달라 일반 모델 성능 개선으로 주장하지 않는다.

**O 시점 후속(P에서 실행 완료):** 같은 세 유효 사례와 snapshot factory/계약을 이미 캐시된 Qwen3.8에 추론 off·명시 예산으로 대조한다. 과거 180초 reasoning timeout과 같은 설정을 반복하지 않는다. 원문을 검토한 뒤 모델 변경 여부를 판단하고 소유 기존 모델을 보존/복원한다. 새 모델 다운로드·전역 설정 변경·외부 추론 전송은 없다. 코드의 source 적합성과 모델 의미 검토를 계속 분리하며, R3/R4·최종 같은 후보 시나리오 묶음·R5는 미완료다. `repeats/snapshot-contract-verification.json`이 이번 증거의 권위다.


P는 같은 세 입력/실제 snapshot factory로 캐시 Qwen3.8을 추론 off·1024토큰·retry0으로 대조했다. 완료3/형식·인용1, 의미 충족1·부분1·실패1이다. 두 출력은 길이 계약을 넘었고 서로 다른 증상을 서로 다른 원인의 증명으로 단정했다. 생성 HTTP/응답3, 보고 input2884/output1371이다. 이어 같은 source/candidate/prompt의 고정 검토 대조군4를 사용했다. Coder는 verdict일치2/4이나 잘못된 단정을 통과시키고 올바른 불확실성을 거부했다. Qwen3.8도 두 번째 오류를 통과시켰으며 세 번째 client timeout으로 실제 종료, 네 번째 미실행이다. 부분/누락은 합격이 아니며 작은 대조군을 일반 정확도로 해석하지 않는다.

기본 모델 교체와 자동 critic 연결은 채택하지 않았다. 소유 MLX를 기존 Coder로 복원하고 실제 OK/stop 응답을 확인했다. 제품 소스287개는 O 작업 트리/실행 후보와 동일하며 전체 gate3356/2는 앞선 O 실행 결과다. 새 workload health/원격 CI를 검증한 것은 아니다. 원문·해시·시간·한계는 `repeats/model-comparison-review.md`, `r4-semantic-review-calibration.json`, `model-comparison-verification.json`이 권위다.

**P 시점 후속(Q에서 실행 완료):** D 기록에서 부족했던 ReplicaSet/Pod·수집 시각을 승인된 기존 실패/복구 1회에서 revision별 health와 함께 기록한다. 같은 시간 창의 원본으로 수동 조사와 읽기 전용 에이전트의 조회 선택·설명·오류·지연·호출 수를 대조한다. 현재 조회를 과거 snapshot 증거로 보충하지 않는다. 기존 describe의 구조화 관측·Investigate 도구5개·Scorecard를 재사용한다. health-check-failure 조치 런북을 읽기 전용 조사인 것처럼 실행하지 않는다. 이 작업은 누락된 R4 관측/도구 선택 비교를 채우는 것이며 기존 의미 오류·R3/R4·최종 동일 후보 묶음·R5를 통과로 바꾸지 않는다.


Q는 승인된 실제 UI 실패/복구1회를 통해 빠졌던 Deployment/RS/Pod·수집 시각·health 로그를 보완했다. revision27→28(이미지 pull 실패)→29(r0), 같은 UID·전체 spec·replicas2 복원이다. 실패 요청3173b5a5…는 claim1/deploy1·60.638초, 수동 확인 rollback1은 같은 DEP-06D6643F의 rolled-back으로 남고 새로고침 뒤 유지됐다. 확인 클릭 이후 두 Pod의 health200 로그가 있다. 이전 Pod가 실패 중에도 살아 있었으므로 서비스 outage/MTTR을 측정했다고 하지 않는다.

원인을 알려주지 않은 읽기 전용 실제 조사fb3cdde2…는 rollout_status/describe_deployment/list_pods 각1, 변경0·claim1·22.723초, 모델 응답2·input4562/output540이었다. 같은 도구 원문을 수동 기준으로 대조하니 새/이전 revision과 health/원인 불확실성은 올바르게 구분했다. 하지만 시작하지 못한 Pod의 로그를 다음 확인으로 제안해 도구 선택/다음 조회는 부분, 전체 합격 아님이다. 운영자 추가 조회의 Pod waiting.message와 이벤트에는 이미지 NotFound가 있었다. 이 메시지는 현재 collector가 이미 읽지만 구조화 요약에서 빠진다. 후속 registry는 OCI-aware Accept로 missing-r1 manifest404/r0 index200; 첫 헤더 불일치404도 보존했다. 운영자의 추가 관측을 모델 입력이나 사람의 작업 시간으로 소급하지 않는다.

제품 소스287개는 O와 동일하다. `repeats/revision-window-verification.json`, `revision-window-review.md`, `q-revision-window/manual-shared-input.json` 및 실제 UI/원본 파일이 근거다. 이전 전체 gate3356/2는 O 결과이며 이번 제품 변경/전체 게이트 재실행은 없다.

**Q 시점 후속(R에서 코드·재생 완료, 실행 반영 보류):** 기존 describe collector가 읽은 현재 Pod identity와 waiting 원문을 신뢰되지 않은 진단 자료로 보존한다. 구조화 revision/health/복구 판정은 원문과 분리하고, 원문 문자열로 원인을 확정하거나 실행 승인을 만들지 않는다. Q 고정 관측 및 기존 삽입문·양성·불확실성 사례로 설명/다음 조회의 변화를 먼저 검증한다. 과거 의미 오류·R3/R4·최종 동일 후보 정상/거부/복구/유실 묶음·전달물 갱신/R5는 남았다.


R(v16)은 기존 describe의 current Pod waiting 원문을 별도 `diagnostic_observations`로 보존했다. source/hash/time·RS/Pod UID·revision/container/image를 연결하고 부적합 대상·시각·소유 관계는 제외한다. 제한/잘림/누락은 명시하며 원문 지시는 구조화 health/recovery에 들어가지 않는다. 기존 deployment_evidence 호환 반환과5회 조회/5도구/신원은 유지했다. 관련58 passed(1.21초), +8; 소유/hash/collector 연결 변이3종 검출/복원. 첫 gate의 NEXT_PLAN 숫자 불일치1건을 정정해 전체3364 passed·2 skipped·20 warnings,140.62초(로컬 macOS·py3.13.5·Node22.23.3/임시prefix).

실제 로컬 모델의 고정 결과 재생은 구체적인 pull 오류를 설명하게 했지만 삽입문에서 이전 revision 건강성을 다시 단정했다. 완료4응답의 판정은 부분2·실패1·availability가 모순된 합성 자료1(합격 제외)이다. 최초5개 도구/호출한도1 설정은3개 호출 요구로 실행 전 종료했고 보존했다. 자료 전달 효과만 보는 후속은 describe1개를 노출했다. acme/orders를 하나의 deployment로 넘긴 실패도 보존하고, 미완료2건만 명시적 deployment/namespace 입력으로 별도 실행했다. 실제5도구 선택/UI 대조나 동등 조건 성능 점수로 합산하지 않는다.

**R 실행 반영은 보류한다.** 작업 트리287개는 v16과, 실행 폴더287개는 O/v15와 각각 일치한다. 소유 프로세스·모델·workload는 바꾸지 않았고 Q가 마지막 health 관측이다. `repeats/pod-diagnostics-verification.json`, `pod-diagnostics-replay-review.json`, `pod-diagnostics-review.md`에 원본과 한계를 남겼다.

**R 시점 후속(S에서 실험 완료, 미채택):** 고정 기록에서 응답 계약 prototype을 만든다. health/recovery는 구조화 사실의 상태·근거·한계를 그대로 표현하고, 모델에는 출처별 가설 종류/인용과 구체적인 다음 조회 선택을 맡긴다. 모델이 임의의 건강성·승인을 다시 작성하는 경로를 계약 수준에서 다룬다. 원문을 문자열로 고치거나 화면에서 접는 것으로 성공 처리하지 않는다. 새 계약으로 실제 생성한 결과를 원본과 대조한다. 양성 복구 후보와 유용한 가설은 유지해야 하며, 불확실성을 전건 보류로 바꾸지 않는다. 인용·enum 일치만으로 의미 정확성을 주장하지 않는다. 일관된 두 revision 실패 대조군과 모순 자료는 구분하고 과거 삽입문/유사 원인/부족 근거 기준은 그대로 유지한다. R3/R4·최종 같은 후보 묶음/전달물 갱신·R5는 미완료다.


S는 제품 변경 없이 사실/제안 응답 계약을 여섯 고정 사례에서 대조했다. 건강성·복구는 기존 코드의 판정을 표시하고 모델은 출처별 가설/다음 조회만 선택한다. 직접 인용→관측 ID→ID enum과 선택지/자료 분리 세 방식의 형식·출처 연결은0/6→1/6→5/6이었다. 각각 실제 HTTP/응답6, 합계18, 자동 재시도0이다. stop 응답도 미완성 JSON이었으며 자동 복구로 통과시키지 않았다. 최종 내용 검토는 충족1·부분1·실패3·형식실패1이다. 지시문을 application_change 근거로 선택했고 복구 후에도 이미지 실패를 제안했다. 정확 인용/ID는 관련성 검증이 아니므로 **미채택**이다. 양성 revision1 후보는 코드로 유지됐으며 모델 능력으로 세지 않는다.

R의 모순 자료를 보존하고 별도의 일관된 raw 합성 Deployment/RS/Pod 대조군을 만들었다. 여섯 tool_result/기대값은 세 실험에 동일하며 요청에는 기대값을 보내지 않았다. 경계5종 검증과 기존 Scorecard/원문 해시 검토는 `repeats/proposal-contract-boundary.json`, `proposal-contract-review.json`에 기록했다. 제품 작업 트리R/실행O의287개 해시 각각 일치, 프로세스/모델/신원/워크로드 변경0이다. `proposal-contract-runtime-check.json` 참조. 기존 supplied-text snapshot의 의미 오류는 해결하지 않았다.

**S 시점 후속(T에서 실행 묶음/전달물 완료):** 실행 O/v15를 고정해 정상3·거부2·복구2·유실2 통합 반복과 재현/비교/데모를 보완한다. 같은 탐색 사례에 프롬프트만 더하는 실험은 중단하고 독립적인 미완료 실행 증거를 먼저 채운다. 진단 실패는 R3의 미충족으로 계속 남기며 나머지 실행 성공으로 덮지 않는다. 이후 진단은 현재 revision/실패 단계에 맞는 조회 적용 조건과 모순 관측 처리를 검토한다. 조치용 health-check-failure 런북을 읽기 전용 조사로 실행하지 않는다. R3/R4 전체·최종 묶음/산출물·R5는 미완료다.

### T — 동일 실행 후보 반복과 전달물 갱신

제품 변경0·새 모델 호출0. 실행 O/v15로 정상3·실행 중 새로고침2·실패 후 사용자 확인 복구2·기존 제한 신원의 globex 거부2를 마쳤다. 각 준비 요청 claim1/deploy1이며 같은 UUID가 복원됐다. 원래 실패는 failed로 남고 같은 DEP에 rolled-back 및 별도 복구 ACT가 연결된다. 실패 current Pod의 pull 오류, 복구 full spec·replicas2·각 Pod health200을 대조했다. 끝에는 시작 UID/전체 spec/r0를 복원했고 revision29→37이다.

기존 tenant 신원으로 직접 GET2/create dryRun2도 Forbidden, 대상 globex Deployment/Service 집합은 전후 empty, acme UID/spec/generation 불변. 소유 router/dashboard만 신원 전환 후 원복했다. 합성 승인 거부2는 개행/빈 사유·APR↔INC·조치0을 상세 새로고침으로 확인했지만 alert/분석 E2E는 아니다. O live runner의 scope 누락 restart/rollback2는 dispatch0으로 거부됐다. 자격증명 격리는 제한 SA에만 해당하며 공유 deployer의 테넌트 격리를 증명하지 않는다.

클릭→current Pod health 정상14.331/13.562/13.892초(중앙값13.892), 서버 접수→저장4.004/3.134/4.728초. 복구 클릭→health11.903/8.791초이며 UI의 복구 실행 시간은 Not measured다. r0/r1은 같은 digest, Pod liveness 로그는 외부 Service/의존성 검사가 아니며 이전 Pod가 살아 있어 outage/MTTR 주장은 없다. 원본·재현·전후표는 evidence README의 T 항목, 결정론적 대조는 `repeats/t-integrated/verification.json`, 72초 정지화면 데모/QA는 `demo/t-integrated-v2/`에 있다. T의 새 full gate 여부는 PROGRESS_LOG 최신 기록을 따른다. 작업 트리 R/v16과 실행 O/v15는 다르며 R/S 후보는 미채택 상태다.

**다음 첫 행동:** Q의 시작 못한 Pod 로그 제안과 S의 복구 후 이미지 실패 제안·모순 누락에서, 같은 원본의 revision/실패 단계별로 무엇을 더 조회할 수 있는지 먼저 표로 고정한다. 조회 가능성과 원인 증명을 구분하고 코드 사실의 모순을 모델에게 임의로 해소시키지 않는다. 기존 describe/Investigate와 보존 원문을 사용하고 양성 복구 후보·삽입문·유사 증상·근거 부족 기준을 유지한다. T 실행 묶음/데모는 다시 반복하지 않는다. 진단 기준·R3/R4 전체·R5는 미완료, 목표 active이며 승인 대기는 아니다. Phase5/4b·원격 CI·커밋/푸시·RBAC 확대·기존 자원 삭제는 이번 범위 밖이다.

S 전체 `make check`: **3364 passed·2 skipped·20 warnings**,132.64초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix), 테스트 증감0. `repeats/proposal-contract-gate.log`, `proposal-contract-verification.json` 참조. 제품 변경/진단 품질 합격/원격 CI를 의미하지 않는다.

### U — 사용자 요청 일시중지, 재현 전 조사 보존

10-03 “이정도 하고 checkpoint” 지시로 목표를 paused로 전환했다. T의 실행 반복/전달물은 완료 상태로 보존한다. U에서는 Q/R/S 원본·현재 normalizer/report/proposal 코드를 읽고 Kubernetes의 Deployment 상태·컨테이너 생명주기·이전 로그 문서를 대조했다. 제품 변경·모델 호출·클러스터 조회/변경은 없다. 실행O/작업트리R의 287개 소스 해시는 각각 기존 후보와 같고 R은 활성화하지 않았다.

**아직 가설인 것:** `rollout_complete`가 Deployment 집계만 검사하고, 집계와 RS/Pod의 불일치를 별도로 보고하지 않는 경로를 코드에서 확인했다. 관련 기존 테스트도 집계만 완료로 바꾸고 실패한 current Pod는 유지한다. 새 재현·경쟁 가설 분리 측정은 수행하지 않았으므로 “원인 확정”이나 수정 완료로 승격하지 않는다. 근거와 공식 자료 링크는 `docs/evidence/dogfood-20261003/repeats/u-diagnosis-checkpoint.json`에 보존했다.

**재개 지시 후 첫 행동:** Q/S의 보존된 raw 입력으로 집계·RS/Pod 불일치를 재현하고 일관된 양성 복구 대조군과 비교한다. 그 결과에 따라 관측 모순 판정과 revision/실패 단계별 조회 적용 조건만 고친다. 원문·양성 후보·삽입문/유사 증상/근거 부족 기준은 유지한다. 앞의 active/다음 행동 기록은 각 시점의 이력이며 현재 상태는 이 일시중지 기록이 우선한다. 재개 전 추가 구현·실험을 수행하지 않는다.
~~~~
<!-- END tidy-20261003-usage-plan -->
