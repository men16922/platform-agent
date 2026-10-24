# PROGRESS_LOG — platform-agent

최종 갱신: 2026-10-25

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-10.md` · `docs/archive/progress-2026-09.md` · `…-2026-08.md` · `…-2026-07.md`

---

## 2026-10-25 — 병합 가드의 진짜 표본 측정: 코드가 막았고, 표식 없는 지시문은 통과했다

- Status: 사용자 /goal "잔여 작업 우선순위에 따라 수행". 원격 3항목은 10-21 보류 유지, 유일한 로컬 열린 항목(§13 "진짜 표본에서의 후보 측정")을 수행. 10-21 미커밋 세션 종료 기록도 같은 브랜치에 커밋.
- Measured: 호출 전 manifest에 기준 고정. 개입 서버+proxy, 온도0.7·seed5·5case·2arm(baseline 5fa41040/main d7ebf0a6), arm마다 재기동, shard SHA 재확인. 10칸 모두 raw5종, 50/50 완료. 서버 종료.
- Result: counterexample 통과 3/5→0/5(코드 거부4·모델 정정0), 표식 제거 fail 5/5→2/5(지시문 인용 recovery_evidence 코드 통과=우회 실측), 양성 복구 2/5→4/5, 지시문 양성 거부0/5. 무효 사유는 raw 재검증으로 분류(길이 초과 다수·JSON1·인용 불일치).
- Gate: `make check` 3385 passed·3 skipped·116.73초(2026-10-25 로컬 macOS·Python3.13.5·Homebrew Node26.11.0(이전 공식Node22.23.3 임시 경로 소실)). 제품 코드 변경0.
- Next: 우회 대응과 원격 3항목은 사용자 결정. `injection-guard-sampled/review.json`, 계획서 §13-3.

## 2026-10-21 — 세션 종료: 로컬 잔여 작업 완료, 원격 보류

- Status: "잔여 작업 완료시까지 수행" 목표의 로컬 범위 완료. #76(4be35d5)·#77(d44f742) CI 통과 후 squash 병합.
- Blockers: Phase5 운영 연결·PR writer·Phase4b는 사용자 결정으로 보류("None now"), 승인 전 시작하지 않는다.
- Cleanup: 세션 소유 MLX/proxy/task 서버 종료, Docker(kind) 사용자 요청으로 다시 중지, ~/.holmes 캐시 삭제. 갱신한 SA 토큰은 task-private 파일에만 있으며 1h 후 만료.
- Next: 원격 항목 중 사용자 선택. 로컬 진단 트랙 열린 `[auto]` 씨앗 없음.

## 2026-10-21 — #76 병합, get_logs(previous) 채택, R5 HolmesGPT 비교

- Status: 사용자 승인(병합·previous·R5)분 완료. 원격 범위는 미승인 유지.
- Changed: `ops_tools.get_logs`에 previous 옵션·카탈로그 설명. 테스트(읽기 동사·previous 조건부) 추가, append 제거 변이 red.
- Verified: kind 재기동으로 재시작7인 실제 대상, 같은 원래 SA 1h 토큰(RBAC0). 실제 도구 함수가 현재/이전 시도 로그를 구분 반환. 모델 선택: tool 4 상한은 5읽기 요청으로 실행 전 거부·unknown 2/2(보존), tool 5는 cold 14.7초·warm 10.6초 성공, previous 포함 5읽기 범위 내, workload 불변.
- R5: HolmesGPT 0.43.0(격리 venv, 47 toolset 비활성, 출력1024, 텔레메트리/가격표 외부 호출 차단, ~/.holmes 캐시 삭제) 대 원래7 snapshot. 1/7 수용, 5/7 kubectl 문장 반복 잘림, 양성 복구 거부, 다른 tenant 읽기 계획. 도구0 조건 한계로 에이전트 효과 분리 불가. 미채택.
- Evidence: live-api-previous-logs/·r5-holmes/의 review.json, 계획서 §13-2.

## 2026-10-20 — PR #76 CI 전용 실패 2종 수정

- Status: 사용자 선택으로 전체 WIP를 feat/2026-10-20-diagnosis-injection-guard에 커밋·push, PR #76. 첫 CI는 35 failed/3350 passed/2 skipped(로컬 3384/3 통과).
- Diagnosed: (1) 34건은 루트 `npx tsc`가 `tsc@2.0.4`로 해석돼 emit 없음 — 깨끗한 worktree·공식 Node22만의 PATH에서 재현. (2) 1건은 131073자 매개변수가 node id→`PYTEST_CURRENT_TEST`(131153자)로 들어가 Linux E2BIG.
- Changed: 테스트4개를 dashboard 자체 tsc+`require_ts_toolchain`로, writer_capture에 짧은 ids. 제품 코드 변경0, 테스트 수 불변. CI 조건 재현(CI=true, 전역 tsc 없음) 105 passed.

## 2026-10-20 — D53 사람 검토 경계 채택, R3 충족 처리와 R4 첫 묶음 정리

- Status: 사용자 결정으로 lookalike는 사람 검토 경계(D53), R3 시나리오 묶음 충족 처리(모델 의미 통과 아님). R4 첫 묶음 정리. R5·원격 미승인.
- Reviewed: 기록 증거만으로 수동 기준(describe→rollout→pods→logs·이전 로그) 대비 모델 선택 4/5, 대상 범위 내·retry0. 이전 컨테이너 로그는 도구 미지원 공백. API run 10.739초·snapshot 호출 중앙5.01초(n10). 수동 시간 미측정. `r4-first-bundle/review.json`.
- Commit: 사용자 "Branch+PR" 선택했으나 삽입 지시 가드가 미커밋 WIP(model_router·local_deployer 수정, inspection_report 등 380항목)에 의존해 부분 커밋은 CI를 통과할 수 없다. 범위 재확인 대기, commit/push0.

## 2026-10-20 — lookalike 관계 필드 실험 미채택과 R3/R4 판정

- Status: 로컬 잔여 작업은 사용자 결정 대기. lookalike·R3 진단 시나리오·R4 수동 대비 평가·R5 미완료.
- Measured: 실험 모듈(cause_relation+양쪽 relation_evidence 코드 검사) 대 현재 후보, cold/warm 각5 case. 합성 양성 same 2/2·different 2/2 정답, lookalike는 증상 문장 인용으로 different 2/2(형식 통과·의미 오답), counterexample 2/2 형식 무효 회귀. 미채택·제품 소스 불변.
- Judged: R3 진단 시나리오는 범위 확대0·보류4·지시문 정정·양성 유지지만 lookalike가 불충분함을 밝히지 못해 미통과. R4 첫 묶음은 사례/보류/하네스는 있으나 수동 절차 대비 평가 미완료.
- Evidence/Next: relation-probe/review.json, 계획서 §13-1. 사용자 선택(사람 검토 경계/모델 고정 해제/R5 승인) 전 같은 계약 반복 중지. 서버 세션 소유로 기동 후 종료, commit/push0.

## 2026-10-20 — sampler 경계 규명과 삽입 지시 복구 가드 채택

- Status: "잔여 작업 완료시까지 수행"으로 재개. sampler 경계 완료, snapshot 지시문 추종은 가드 후보로 정정, lookalike·R3/R4 전체·R5 미완료.
- Measured: mlx_lm 0.31.3의 컴파일 `categorical_sampling`은 생성 스레드의 seed를 받지 못한다(모델 없는 worker 재현 seed3·12draw 동일 토큰, stock 서버 모든 그룹1종, 비컴파일 개입 서버 seed별 상이·같은 seed 재현, proxy=upstream). §12 0.7 arm은 표본이 아니었다. 온도0도 cache 이력/batch 경로로 갈린다(cold 대 부분캐시 566토큰 다른 raw, 같은 이력 재현).
- Reverified: 지시문 ablation을 cold/warm 이력·진짜 표본으로 재현. 개입 서버 0.7 재측정(파생 스크립트) counterexample3/3 지시문 추종 유지→0.7 미채택 유지.
- Changed: `snapshot_diagnosis.py` 표식 기반 삽입 지시 탐지·주석(원문 불변), `recovery_evidence` 필수, 지시 구간 인용 코드 거부, 보고서/렌더 반영. 테스트4 신규, 변이4 red·바이트 복원.
- Verified: baseline(§12 동일 소스 5fa41040) 대비 cold/warm 각5 case: counterexample·표식 제거 4/4 not_established, 양성2/2 유지, 지시문 덧붙인 양성1/2 거부, lookalike2/2 길이 초과 회귀. `make check` 첫 실행 3383/1 failed(문서 수치), 문서 갱신 후 3384 passed·3 skipped·118.68초(로컬 macOS·py3.13.5·공식Node22.23.3/임시prefix).
- Evidence/Next: sampler-boundary/·injection-cache-control/·injection-guard/의 review.json, 계획서 §13. 다음은 lookalike 원인 단정. 서버는 세션 소유로 기동 후 종료, 모델/클러스터/유료API/삭제/commit/push0.

## 2026-10-20 — 고정 Qwen 온도 대조 보존과 사용자 일시중지

- Status: 사용자 요청으로 목표 paused. 추가 구현/모델 호출/클러스터 작업 중지, 진단/R3/R4 전체/R5 미완료.
- Measured: 원래3입력·고정 Qwen·prompt/schema·1024/request1/tool0/retry0, seed42/31415/27182 각각 온도0/0.7을 한 변수 대조했다. 두 arm 모두 명시seed의 MLX nonbatch 경로다. 18응답과 실제 HTTP 요청·원문/hash 보존.
- Verified: 온도0은9완료/인용9통과지만 기존 지시문·원인 단정 오류 유지.0.7은6완료/3잘림·유효 진단0이라 미채택. 각 case/온도에서 서로 다른seed3개의 원문 hash가 동일하며 원인은 미확정, 독립 표본/개선으로 해석하지 않는다.
- Preserved: 제품11소스 hash는 W 전체3380/3 후보와 일치. 전체gate 재실행 없음. 기존 WIP/실패/양성 복구·서버 보존, 새 모델/클러스터 조회/설정 변경/권한 확대/삭제/commit/push0. 체크포인트 문서 검증은 아래 evidence에 기록한다.
- Next: 재개 지시 후 사용성 계획 §12·snapshot-temperature/review.json과 pause-checkpoint.json에서 sampler/RNG/cache/proxy 구분 측정부터 이어간다. 기존 같은 prompt/schema 반복은 중지한다.

## 2026-10-20 — 범위 설명 대조·실제 읽기 UI 통과와 snapshot 오류 재확인

- Status: 목표 active, 진단/R3/R4 전체/R5 미완료. 모델 복원/LFS SHA 검증은 이미 완료했음을 재확인했다.
- Measured: 같은5도구/parameter schema/요청/모델 설정의 첫 선택 대조에서 범위 설명만 추가하자 list_namespaces 요청이 사라졌다. 양쪽 dispatch0, 원래 failed run 보존. task wrapper 설명 정렬이며 production universal scope 도입 아님.
- Verified: API18779와 W 격리 대시보드13001의 로컬 Credentials 세션 각1 succeeded·4reads, 동일UUID 재생/새로고침 추가read0·다른actor404·raw JSON 보존. 기존SA/guard/예산 유지, UID/full spec/rev37/replicas2 불변. GitHub OAuth/tenant 격리/반복 성능 증거 아님. live-api-scoped/review.json·ui-reloaded.png.
- Failed: snapshot 원래7건은 모델3/제외4, 의미1충족·1부분·1실패. 원문의 rollback 지시문만 제거한 대조는 recovery not_established. 역할별 근거 계약도1충족·1부분·1실패이며 format-only 반증 통과로 미채택. 제품 변경0·전건 보류/프롬프트 반복으로 성공 처리하지 않음.
- Evidence/Next: snapshot-resume-review.json·scope-selection/·사용성 계획 §11. 기존11소스/전체3380/3 baseline 유지, 문서61통과·2.59초·diff check 통과. 별도 witness도3형식거부/timeout→healthy 오류로 미채택. 기존 Qwen 고정 확정, 다른 모델/유료API/배포/권한변경/삭제/commit/push0.

## 2026-10-20 — 제안 적용 조건을 실제 읽기 전용 소비 경계에 연결

- Status: 목표 active, R3/R4 전체/R5 미완료. V의 자유 서술 실패를 보존하고 W의 역할을 상태/복구 판정과 분리된 가능성·다음 증거 선택으로 제한했다.
- Changed: investigation_proposals의 단계/출처 검증과 readonly describe의 계약 metadata, 실제 factory/router의 정상·거부·재수집 결과, UI/SSE/SQLite 재조회 연결. 같은 Investigate5 도구/신원/조치 권한 유지, 원래 모델 text/trace 보존·재시도0.
- Measured: 기존 S 잘못된4제안은 출처ID만으로 통과했다. 새 경계는4거부·양성 복구 유지·합성6유효 유지. prototype 모델6/7유효·모순1거부. W 실제7건은 제안5·재수집1·형식거부1, 상충 prose/JSON 지시만 제거한 대조는 해당1건 통과. 최종 동일후보7건은 제안6/코드 재수집1·응답완료7, 원문ID 오타는 그대로 보존.
- Verified: 새 factory/router·SSE/SQLite9검사와 UI projection1검사·기존 관련79/TS 통과. 전체 W make check3380/3·20warnings·119.20초(로컬 macOS·py3.13.5·공식Node22.23.3/임시prefix) 통과. 코드/형식 통과는 인과 정확도가 아니다.
- Evidence/Next: production-contract*/ · applicable-review.json · isolation-review.json. 전용 기본/반복 억제 둘 다7/7완료라 설정 변화 미채택. 기존 앱 전환/유료API/삭제/commit/push0. 격리 API18778의 실제5도구 read는 describe/rollout/list_pods dispatch3·list_namespaces 거부1로 failed. 같은 원래 SA UID의1h 토큰만 task-private 갱신·RBAC/자원 변경0, 현재 UID/full spec/rev37/replicas2는 T와 일치. 다음은 scope 광고/모델 불준수 가설 분리이며 live-api/review.json과 resume-checkpoint.json 참조.

## 2026-10-20 — 집계 모순 재현·수정과 모델 전후 실패 보존

- Status: 잔여 작업 완료 지시로 로컬 목표 재개. T 반복/데모는 유지, 진단/R3/R4 전체/R5는 미완료.
- Changed: V는 Deployment 집계·소유 RS/Pod 불일치와 unknown을 별도 기록해 거짓 완료/복구 후보를 막는다. current 컨테이너의 현재/이전 시도 로그 적용 근거·단계별 다음 증거, UI/영속 요약의 불일치 값 표시. 원문/모델 오류 응답 보존.
- Verified: Q/S raw와 양성7종 전후 대조. 집계만 완료+실패Pod의 true→false, 실제 복구 완료와 revision1 후보 유지. 관련54·TS 검사·Chrome 실제 컴포넌트 새로고침 통과(과거 raw, 인증앱/클러스터 E2E 아님). 전체 make check3370통과·3skip·20warnings·123.81초(로컬 macOS·py3.13.5·공식Node22.23.3/임시prefix), gate-final.log.
- Actual: 동일 raw·모델 revision·1024/temperature0·HTTP2/frozen describe1/retry0, 각7사례. 코드 경계7/7씩·응답완료6/7→4/7·의미0/7→1/7. 삽입문/이미지 이름/시작 전 로그/이력 오독/잘림 유지, 진단 성공 미선언. lexical 대조3건은 이름 민감성을 보였지만 원래 실패를 대체하지 않음.
- Environment: 과거 Coder revision task-local 복원/LFS SHA 검증·소유 MLX/proxy 기동. Node22 공식 SHA 검증/임시 npm prefix 사용. Homebrew dylib·npx 경로로 초기 gate 실패를 보존. 제품 후보 미활성화, 새 cluster/유료API/원격변경/삭제/commit/push0.
- Evidence/Next: `docs/evidence/diagnosis-20261020/paired-review.json`, 사용성 계획 §9. MLX 반복 억제 한 변수 실험을 먼저 검토하고 종료 안정성과 의미를 분리한다. 전체 Investigate 선택·supplied-text·인증 UI 진단/R5는 남음.
