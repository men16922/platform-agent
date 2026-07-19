# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-19

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md`(M9=eval·하드닝 스프린트+라이브 E2E, M8=레퍼런스 8/8) / `PROGRESS_LOG.md`(+`docs/archive/`)를 참조한다. **≤120줄** 유지.

## 현재 상태 — 자율 백로그 전면 소진 (2026-07-19, gate 847)

승인된 실행 큐 8건·Google/cwc 대조 후속 ①~⑦·레퍼런스 8항목·라이브 E2E 2종(OAuth 배포 클릭·Slack 인터랙티브 승인)·표면화 버그 7건 근본수정까지 전부 완료 → `COMPLETED_SUMMARY.md` M8/M9. **아래는 전부 사용자 결정/외부 의존.**

## 사용자 게이트

- [ ] **push 여부** — 로컬 main이 origin 대비 ahead(Slack E2E~tidy 커밋들). 승인 시 `git push`.
- [ ] **테크 아티클 배포(LinkedIn/Medium)** — **작성 전부 완료(잔여=배포)**: EN `docs/post/platform-agent-architecture.md` + KO `-ko.md` + LinkedIn 컷(EN/KO) `platform-agent-linkedin-cut.md` + 데모 영상 `local-onprem-edited.mp4`.
- [ ] (billable) **`terraform apply`** — `infra/terraform/aws-production/`(EKS+Aurora+NAT, init/fmt/validate 완료). 시간당 과금 — apply→검증→즉시 destroy 권장.
- [x] ~~(선택) On-Prem 승인 게이트 Slack 버튼 연동~~ — **완료(2026-07-19, `617839b`, gate 854)**: DynamoDB 공유 매체 + 옵트인 폴러, 라이브 왕복(APR-3E6D2540→INC-FA2143AF resolved). 증거 `docs/evidence/onprem-slack-approval-live.log`.
- [ ] (선택) **Azure Foundry 스택 정리** — 유휴 ≈$0라 유지 중.

## 리팩토링 후속 (선택 — 2026-07-17 구조 패스에서 판단 보류, 별도 승인)

- [ ] **`operations` 그룹핑 축 통일** — AWS=role별 서브패키지 vs gcp/azure=cloud별 패키지. 통일하면 일관성↑이나 import churn(테스트+CDK asset 경로) 반나절.
- [ ] **`approval_bridge/handler.py`(600줄+) 분리** — slack_interactive + request_store 분리 여지. 단 테스트가 내부심볼 12개+를 `handler` 경로에 `@patch` 강결합 → 실익<리스크, 하려면 patch 타깃 재작성 동반.
- 참고: `_k8s_rest`는 restart/scale만 공유(rollback은 GKE/AKS 시맨틱 상이). detector/analyzer/decision은 SDK 90%+ 상이라 DRY 안 함(의도적).

## 캘린더 / 메모

- **ADK 재평가(2026-03 GA 후)**: workflow-graph API가 Gemini 서브에이전트 경로(`adk_deployer.py`)를 개선하는지 재평가 — 우리 Orchestrator는 클라우드-중립이라 코어 대체 아님.
- 안티패턴 메모(범위 밖): A2A "Dynamic Autonomy"·agents-cli(GCP lock-in·Pre-GA)·CMA 베타 API 채택 금지(계약/방법론만); 정적 무조건 fan-out은 self-consistency 라우팅 회귀라 금지; 자유텍스트 spawn_subagent 핵 금지.

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지. 하드-투-리버스(클러스터 변경/클라우드/대규모 리팩터)는 승인 후.
