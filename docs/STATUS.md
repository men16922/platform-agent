# STATUS — platform-agent

최종 갱신: 2026-10-25

> 현재 검증 baseline / active focus / risks. **≤120줄** 유지.
> 상세 이력은 `COMPLETED_SUMMARY` **M0~M91** (`docs/COMPLETED_SUMMARY.md`)과 아카이브가 권위다. 아래 날짜는 관측일이며 현재 원격 상태를 뜻하지 않는다.

## 검증 Baseline (실제로 돌린 것만)

- 2026-10-25 가드 표본 측정 브랜치 `make check` → **3385** passed·3 skipped·20warnings,116.73초. 2026-10-25 로컬 macOS·Python3.13.5·Homebrew Node26.11.0(이전 공식Node22.23.3 임시 경로 소실). 제품 코드 변경0(실험 스크립트2·evidence·문서), 증감0. 문서 수치 반영 후 재실행도 3385/3·111.47초. `injection-guard-sampled/gate.log`·`gate-final.log`.

- 2026-10-21 main+`get_logs(previous)` `make check` → **3385** passed·3 skipped·20warnings,107.20초. 로컬 macOS·Python3.13.5·공식Node22.23.3/임시 npm prefix. 신규 previous 조건부 테스트1. 원격 CI는 PR에서 확인.

- 2026-10-20 W+삽입 지시 가드 `make check` → **3384** passed·3 skipped·20warnings,118.68초. 로컬 macOS·Python3.13.5·공식Node22.23.3/임시 npm prefix. 신규 snapshot 가드 단위4. 첫 실행은 문서 수치 미갱신으로 gate_number_claims 1 failed(3383/3)였고 문서 갱신 후 재실행한 값이다.

- 2026-10-20 W `make check` → **3380** passed·3 skipped·20warnings,119.20초. 로컬 macOS·Python3.13.5·공식Node22.23.3/임시 npm prefix. 새 factory/router/SSE·SQLite9검사와 UI projection1검사 포함. skip2=온프렘serverless, skip1=기존Terraform도구/초기화 부재.

- 2026-10-20 `make check` → **3370** passed·3 skipped·20 warnings,123.81초. macOS·Python3.13.5·공식 Node22.23.3/임시 npm prefix. 관련54·TypeScript 검사 통과. skip2=온프렘 serverless 미지원, skip1=기존 Terraform 도구/초기화 부재. 원격 CI/제품 서버 적용 검증은 아니다.

- 2026-10-03 `make check` → **3364** passed·2 skipped·20 warnings, 133.83초. 로컬 macOS·Python3.13.5·Node22.23.3/임시 npm prefix, T에서 작업 트리R/v16 검사. 증감0.
- 실행 O/v15의 자체 게이트는 같은 날 앞선 **3356 passed·2 skipped**, 138.14초. 작업 트리R 결과를 실행O의 결과로 바꾸어 쓰지 않는다. 두 후보 각각287소스 일치는 U checkpoint에 기록됐다.
- T 실제 Chrome/로컬 kind: 정상3·거부2·실패 후 수동 복구2·실행 중 새로고침2. 각 준비 요청 claim1/deploy1. 최종 UID·전체 spec·r0/replicas2 복원, revision29→37. 합성 승인 거부2의 사유·APR↔INC·조치0도 확인.
- 측정 한계: r0/r1은 같은 digest. health는 Pod liveness200 로그이며 외부 Service/의존성 검사가 아니다. 이전 Pod가 생존해 outage/MTTR로 세지 않는다. 제한 tenant SA의 거부는 공유 deployer 격리 증명이 아니다.
- 증거 권위: `docs/evidence/dogfood-20261003/repeats/t-integrated/verification.json`과 같은 폴더 report, 데모는 evidence README의 T 항목. 마지막 workload 관측은 13:12 UTC이며 U에서 새로 조회하지 않았다.
- M89(2026-09-13): AWS transport의 로컬 SDK/HTTP/DB·브라우저·변이·빌드 검증 완료. M91(2026-09-15): 인증 해소·원격 설정 읽기·로컬 후보 재생성. 운영 Invoke/배포/PR 발행·원격 CI는 별도다.
- 과거 게이트 증감/환경 원문은 [10월 정리 아카이브](archive/progress-2026-10.md#tidy-20261003-status), 더 이전은 `docs/archive/status-baseline-2026-09.md` 참조. 테스트 수는 단조증가 지표가 아니다.

## Active Focus

**2026-10-20 사용자의 "잔여 작업 완료시까지 수행"으로 재개.** 기존 Qwen 고정, 계획서 §13이 권위다.

§12의 seed 동일 원문은 mlx_lm 0.31.3 서버가 생성 스레드에서 seed를 컴파일 sampler에 전달하지 못한 결과로 확정했다(모델 없는 재현·stock 대 개입 서버·proxy 배제, `sampler-boundary/review.json`). §12 0.7 arm은 표본이 아니었고, 개입 서버의 진짜 표본으로 재측정해도 counterexample 지시문 추종이 남아 0.7 미채택을 유지한다. 제품은 온도/seed를 보내지 않아 영향 없음.

지시문 ablation은 두 cache 이력·진짜 표본에서 재현돼 원인으로 확인했다. 작업 트리에 삽입 지시 복구 가드를 채택했다: 표식 기반 탐지 주석(원문 불변)+`review_candidate`의 `recovery_evidence` 필수+지시 구간 인용 코드 거부. baseline 대비 counterexample·표식 제거 변형 4/4 정정, 양성 복구 2/2 유지, 지시문 덧붙인 양성 1/2 fail-closed 거부, lookalike 2/2 길이 초과 형식 무효 회귀. 의미 해결·R3/R4 통과가 아니다. `injection-guard/review.json`.

lookalike는 관계 필드 실험까지 실패(relation-probe/review.json)해 사용자 결정 D53으로 사람 검토 경계에 둔다. R3 시나리오 묶음은 이 경계와 T 완료분으로 충족 처리(모델 의미 통과 아님), R4 첫 묶음은 수동 기준 대비 도구 선택 4/5·이전 컨테이너 로그 공백으로 정리했다(r4-first-bundle/review.json). 10-21 사용자 승인으로 #76·#77 병합, `get_logs(previous)` 채택(실제 재시작 대상·같은 SA, tool 4 상한 묶음 거부 2/2·tool 5 성공 2/2), R5 HolmesGPT 비교 완료(1/7 수용, 도구0 조건 한계, 미채택). 원격은 미승인.

10-25 병합 가드의 진짜 표본 측정(개입 서버·온도0.7·seed5×5case×2arm, 사전 기준 충족): counterexample 통과 baseline3/5→0/5이나 코드 거부4/5로 막았고 모델 정정은0/5, 표식 제거 변형 fail 5/5→2/5로 **표식 없는 지시문 인용 우회를 실측**, 양성 복구 2/5→4/5. 가드 효과는 유지, 기전은 표식 있는 지시문의 코드 차단에 한정된다. 우회 대응은 사용자 설계 결정(NEXT_PLAN). 계획서 §13-3, `injection-guard-sampled/review.json`.

## Open Risks / Gaps

번호는 기존 인용을 위해 유지한다. 경위·반증·주의사항 전문은 `docs/archive/status-risk-detail-2026-09.md`의 같은 번호와 정리 전 원문에 있다.

1. **CDK context:** diff/deploy에 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent` 필수. 미지정으로 OIDC provider가 삭제된 실제 이력이 있다.
2. **GCP/Azure 보관:** 90일 보관 정책 미구현. 2026-08-30에는 스토어가 없어 삭제 대상0이었다. Phase4에서 재개하며 현재도 0이라고 추정하지 않는다.
3. **스코프·배포 신원(D38·D39):** 전체 구성은 옵트인. 온프렘 live 조치는 scope 누락 시 거부하지만 배포 신원 미설정은 ambient kubeconfig 경고/폴백이다. 공유 deployer의 tenant 구분·기본 on·서명키 custody/rotation 결정이 남았다.
4. **비용:** 프로젝트·크레딧·사용 창을 분리한다. M54(2026-09-05) GCP 총사용액₩14.80, PROMOTION−₩12.36·기타−₩2.44·청구≈₩0. 미완 일자/서비스 구성 변화가 있어 월 런레이트와 새 GKE 견적으로 전용하지 않는다. 다음 관측은 같은 구성이 유지된 완결 일자다.
5. **k3s(D40):** 집행 기능과 proven 집합을 구분한다. k3s-lab에 실제 workload가 생길 때만 승격 재검토한다.
6. **Cosign 어드미션:** 2026-09-02 재측정 당시 업스트림 대기. 재개 신호는 `#1968` 머지 또는 `#2007`을 담은 릴리스다. `#1406`/`#1725`가 이미 구현된 일을 미지원으로 읽었던 근거 오류를 반복하지 않는다. 당시 v0.15.1·후속51커밋 수치는 현재 상태가 아니다.
7. **TS/전송 호환:** 롤링 중 두 버전 공존. 새 push 필드는 optional+폴백이어야 한다.
8. **PodSecurity:** 새 addon은 PSS restricted에서 server dry-run과 Pod 실제 상태를 확인한다. Argo Synced만으로 동작을 확정하지 않는다.
9. **해소 이력:** Capsule deprecation(D41), GCP 예산 상시 발화, 리포트 스트림 분리는 완료 기록 참조. 현재 재개 작업이 아니다.
10. **테넌트 자격증명:** GCP/Azure는 아직 tenant-bound 미증명. 온프렘 제한 신원의 경계와 공통 deployer를 구분한다. 대상 자원0은 격리의 증거가 아니다.
11. **대시보드 audit:** 2026-08-30 `npm audit` 0건으로 해소. 과거 “upstream 대기” 기록은 세 군데 모두 틀렸다. 당시 결과를 현재 취약점 조회로 표시하지 않는다.
12. **게이트 해석:** 날짜·환경·skip, 실제 소비 경계, 형제 전체, 변이 red와 WIP 복구까지 기록한다. 가드/픽스처/변이 하네스도 틀릴 수 있으며 선언·테스트 통과만으로 라이브 실행을 입증하지 않는다. 아홉 사례의 전문은 archive Risk12 참조.
13. **모델 측정 재현성:** mlx_lm 0.31.3 서버에서 온도>0 seed는 독립 표본을 만들지 않고, 온도0 출력은 prompt-cache 이력·batch/nonbatch 경로에 따라 갈린다. 과거 단일 응답 대조(V·§11·W 형식)는 이 변수를 통제하지 않았다. 새 대조는 `cached_tokens`를 기록하고 arm별 cold 재기동+다른 이력으로 반복한다. 서버 logprobs는 출력 토큰과 어긋나 지표로 쓰지 않는다.

## 닫힌 범위와 별도 경계

- **Phase4a는 닫힘(M38·M40·D50).** AMP 실측798,331샘플·청구 **$0.00**, 이유는 **Always Free 40M/월**이었다. 계획의 프리티어 배제 근거가 틀렸으며 “어차피 공짜”가 아니다. 필터 없이는 한도128배 초과다. 접은 이유는 $0가 아니라 장기 키의 대가이며 D48은 유효하다.
- **Phase5:** 독립 Lambda 실행 위치(D52)와 저장/준비/상태 UI는 정해졌다. M91 이후 남은 것은 계획 §13의 운영 실행 범위·전환/복구·보관 비용과 writer 경계다. 실행 위치 부재/Vercel 2FA를 현재 blocker로 반복하지 않는다.
- **main 보호(D43):** PR+CI 게이트 집행이며 코드 소유자 리뷰 집행은 아니다. 어드미션·클라우드 테넌트 격리·production 발행 완료를 암시하지 않는다.
- 다음 작업·기존 lab/App/키/checkout/branch/PR 보존 범위는 `docs/NEXT_PLAN.md`. 10-20 재개는 로컬 진단 작업이며 Phase5/4b 원격 실행 승인을 뜻하지 않는다.
