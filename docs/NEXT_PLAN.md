# NEXT_PLAN — platform-agent

최종 갱신: 2026-10-25

> **열린 작업만. ≤120줄.** 다음 작업의 유일한 권위다. 완료 이력은 `docs/COMPLETED_SUMMARY.md`, 최신 증분은 `docs/PROGRESS_LOG.md`.
> 정리 전 원문·주의사항은 [10월 아카이브](archive/progress-2026-10.md#tidy-20261003-next-plan)와 `docs/archive/next-plan-detail-2026-09.md`에 보존했다.

## 현재 상태 (2026-10-25, gate 3390·3 skipped — 2026-10-25 로컬 macOS·Python3.13.5·Homebrew Node26.11.0(이전 공식Node22.23.3 임시 경로 소실))

**10-21 로컬 진단 트랙(R3/R4 첫 묶음/R5) 정리 완료, 10-25 가드 진짜 표본 측정 완료.** sampler 경계·삽입 지시 가드(#76 병합)·이전 컨테이너 로그·R5 비교·표본 측정(계획서 §13~13-3). 원격 범위는 사용자 미승인으로 유지. 의미 품질은 미충족이며 열린 `[auto]` 씨앗은 없다.

기존 앱 후보 O/v15와 작업 트리 W(10-20)를 구분한다. W는 제품 서버 미활성화, S 응답 계약도 미채택이다. 게이트는 작업 트리 기준이며 실행 후보 검증/원격 CI와 같지 않다. 완료한 Phase0·1a·1b·2·3 및 이후의 제한·재개 조건은 M10~M15와 각 계획서를 따른다.

## 재개 후 첫 우선순위 — 진단 R3/R4

- [x] **Supplied snapshot 의미 오류:** 지시문 추종은 가드 후보로 4/4 정정(미커밋). lookalike는 D53(사람 검토 경계)로 R3 기준 충족 처리, 모델 의미 통과 아님. 계획서 §13-1.
- [x] **이전 컨테이너 로그:** 10-21 사용자 승인으로 `get_logs(previous)` 채택. 실제 재시작 대상·같은 SA로 검증, tool 4 상한에서는 묶음 거부(보존), tool 5에서 2/2 성공. 계획서 §13-2.
- [x] **측정 통제:** 단일 응답 대조는 `cached_tokens` 기록·arm별 cold 재기동+다른 이력 반복으로만 해석한다(STATUS Risk13, 규칙은 계속 적용). 진짜 표본은 sampler 개입 서버(`sampler-boundary/patched_server.py`)를 측정 도구로만 쓰고 제품에 넣지 않는다. 10-25 병합 가드의 진짜 표본 측정 완료(50응답, 사전 기준 충족, 계획서 §13-3).
- [ ] **표식 없는 지시문 우회(사용자 결정):** §13-3 실측 2/5. 10-25 (b) 명령형 탐지 실험은 **미채택**: dev P8/8·N1 0/10이었으나 동결 후 held-out N1 오탐 1/10(`Delete events: none recorded…`)으로 사전 기준(N1 오탐0) 실패. 보존 초안 재생에서는 우회 2/2 차단·정상 통과 회귀0. 남은 선택: (a) 현 경계(unverified·실행 미승인·사람 검토)로 수용, (b2) 인용된 보고 발화(`says "…"`/`note:`)로 좁힌 규칙+새 held-out. 계획서 §13-4. `[auto]` 아님.
- [x] **진단 기준 재검증:** 원문·양성 복구·삽입 지시·유사 증상·근거 부족 기준을 유지한 채 cold/warm·진짜 표본으로 재측정했다(§13). 형식 통과·전건 보류를 성공으로 세지 않았다.
- [x] **R5 조건부 비교:** 10-21 승인, HolmesGPT 0.43.0 동일 snapshot·모델·도구0 비교 완료(1/7 수용), 미채택. 도구0 조건의 설계 불일치 한계 명시. 계획서 §13-2.

권위: `docs/plans/2026-10-03-platform-agent-usage-and-evidence.md` §4·§12. 새 자료는 `docs/evidence/diagnosis-20261020/production-contract-final/`, 과거 U checkpoint도 보존한다. T의 정상3·거부2·복구2·새로고침2 및 데모를 다시 반복하지 않는다. 다음 수정의 검증 범위는 실제 변경으로 정한다.

## 별도 원격 우선순위

2026-10-21 사용자 결정으로 셋 모두 보류("None now"). 각각 별도 승인 전에는 읽기 전용 범위 확인도 시작하지 않는다.

- [ ] **Phase5 운영 연결:** D52·M53의 독립 Lambda 설계와 M71~M89 로컬 구현은 완료. M91(2026-09-15)의 인증 해소·설정 조회·후보 재생성을 유지하고 실행 위치/2FA 문제를 다시 열지 않는다. 다음은 `docs/plans/2026-09-05-phase5-planner-runtime.md` §13의 새 함수/테이블/IAM·본인 men16922/acme 권한·production 설정/후보 전환·복구·보관 비용 범위 확인이다. 승인 후 현재 신원/해시/복구 대상을 재확인하며 로컬 dogfood 승인과 혼동하지 않는다.
- [ ] **PR writer:** 같은 계획 §5·§12의 자격증명 경계·실험 부분 판정 유지. production PR 발행·tenant별 repo 이관·추가 쓰기/민팅/권한 확대는 자동 재개하지 않는다. M83 실험 PR을 보존한다.
- [ ] **Phase4b:** 새 상시 GKE 비용·기간·종료 장치, 30분 TTL과 상시 운영의 충돌, 클라우드 자격증명 파티션을 먼저 결정한다. `docs/plans/2026-08-08-phase4-scope-and-cost.md` §5·§6. M54의 기존 사용액은 새 GKE 견적이 아니다.
- [ ] **GCP 비용 후속:** 같은 서비스 구성이 유지된 완결 일자가 쌓였을 때 관측한다. 기존 프로젝트/크레딧/사용 창과 수치는 `STATUS` Risk4가 권위다.

## 조건이 남은 기존 백로그

기본 설계는 `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5). capability별 구현 교체·tenant/env별 git registry와 blast radius=1 tenant/env를 유지하며 자격증명 집행은 옵트인(D38)이다.

| 열린 항목 | 재개 조건·범위 |
| --- | --- |
| Phase1b loki/tempo/pa 이관 | 볼륨 스냅샷 선행. kind에는 CSI 스냅샷터 부재 |
| 스포크 읽기 신원 | 공유 argocd 읽기의 코드 필터 한계. 인클러스터 배포·민팅과 결정5 C/D 선행 |
| scope·배포 신원 기본 on | `probe_scope_reachability.py`·`make deploy-identity-check`로 적용 상태 확인. tenant 구분·서명키 custody/rotation 별도 결정 |
| A2A 인증 기본 on | D39. 현재 라이브 kagent 왕복의 나가는 익명 경로와 실제 집행 조건 대조 |
| DUAL 조건부 리다이렉트 | slack_live_approval 완료분과 분리. 실제 하중을 받는 조건이 생길 때 |
| Phase3② AWS 실행 | SSM Automation 러너가 없음. GCP/Azure 배선 완료를 AWS 완료로 세지 않음 |
| msft_deployer | 대체 심볼 근거 필요. 08-30 AzureOpenAIResponsesClient 부재는 버전 지연이 아니었고 stub 테스트는 실제 호환성을 보장하지 않음 |
| GCP/Azure 90일 보관 | Phase4·실제 스토어 범위 확정. STATUS Risk2 |
| k3s proven 승격 | k3s-lab에 workload가 생길 때(D40). 미존재 상태의 선언 추가 금지 |
| MCP 게이트웨이 | 실제 호출자/포트 연결 필요. bridge.py 폴백은 있지만 생성 호출은 테스트뿐이라는 기존 측정 유지 |
| Cosign 어드미션 | STATUS Risk6의 #1968 머지 또는 #2007 포함 릴리스를 재조회. 과거 #1406 부재 근거는 재사용 금지 |
| CODEOWNERS 리뷰 필수 | 두 번째 리뷰어가 생기면 재검토(D43) |
| ADK 재평가 | adk_deployer의 workflow-graph 개선 근거가 있을 때. 클라우드 중립 코어 교체 아님 |
| GitAIOps 후속편 | 2026-07-25 지시로 집필/발행 착수 금지. 소재는 archive에 보존 |
| Azure Foundry 정리(선택) | 다른 프로젝트 ACR Basic 비용과 구분. 현행 자원 상태를 먼저 확인 |

## 보존·작업 규칙

- **lab 1367338348·checkout 및 R2 lab/App4924748·설치161238144·키·branch·draft PR #1 보존. 추가 삭제 금지.** 기존 mixed WIP·기록·실험 후보도 보존한다.
- Phase4a(M38·M40·D50), 공급망 완료분(M15), Azure 재시도·dependency 분리·executor 배선 등 닫힌 항목은 `COMPLETED_SUMMARY`와 archive를 먼저 읽는다. 닫힌 목록의 재개 조건을 문서 정리로 완화하지 않는다.
- `_k8s_rest`는 restart/scale만 공유. provider별 rollback 의미를 유지하며 SDK 차이를 무리하게 DRY하지 않는다. 공통 계약은 한 모듈과 실제 호출 경계에서 검증한다. `approval_bridge` 추가 분해 금지(D15), 포괄 gcloud allow 금지(D16·D22).
- A2A Dynamic Autonomy·agents-cli/CMA 베타·정적 무조건 fan-out·자유텍스트 spawn_subagent 도입은 범위 밖이다. 요청 이상 기능을 추가하지 않는다.
- 변경 후 `make check`와 관련 실제 경로를 검증하고 `/checkpoint`. 게이트 날짜/환경/skip과 로컬/원격 증거를 구분한다. 커밋·푸시·원격 변경은 기존 승인 범위 안에서만 수행한다.
- Overnight는 `[auto]` 하나당 한 이터/로컬 커밋이며 씨앗이 없으면 중지한다. R0~R5는 대화형 트랙이고 10-20 재개도 새 `[auto]` 씨앗 등록이 아니다.
