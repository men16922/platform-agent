# AGENT_BRIEF — platform-agent

최종 갱신: 2026-10-25

> ▶ NEXT SESSION: **10-25 사용자 지시로 세 클라우드 비용 정리 완료, Phase5 운영 연결은 사용자 "보류". Azure는 크레딧이 없어 사용 금지**(`docs/evidence/cost-teardown-2026-10-25.log`). #78~#80 병합, 표식 없는 지시문은 (a) 수용(Risk14). 남은 원격 항목(Phase5/PR writer/Phase4b)은 모두 보류이며 각각 새 승인 전 미착수. 진단 경위는 `docs/plans/2026-10-03-platform-agent-usage-and-evidence.md` §13~13-3. 단일 응답 대조는 cached_tokens·cold 재기동 반복으로만 해석.
> 에이전트 진입점. **≤60줄** 유지. 다음 작업의 권위는 `docs/NEXT_PLAN.md`다.

## Read Path (순서대로, bulk-read 금지)

1. `docs/AGENT_BRIEF.md` — 현재 문맥
2. `docs/STATUS.md` — 검증 범위와 위험
3. `docs/NEXT_PLAN.md` — 열린 작업과 재개 조건
4. 필요 시 `docs/PROGRESS_LOG.md` 상단과 `docs/LESSONS.md`
5. 해당 작업에 필요한 계획서·증거·`docs/engineering/`만 추가 조회

## Snapshot

- **목적:** AWS-native 플랫폼 에이전트. provision → deploy 검증 → detect → analyze → decide → execute → Slack 리포트.
- **구현:** Operations·3-cloud AI Agent·온프렘 프로비저닝/배포/검증/롤백·kagent A2A·대시보드. Activity는 AWS+On-Prem을 병합하며 Provisioning/Deployments/History와 중첩 상세를 제공한다. 구현/과거 실증과 현재 운영 검증은 구분한다.
- **로컬 모델:** Qwen3-Coder-30B-A3B. `make dev-up`은 MLX+proxy+router+dashboard를 기동한다. 모델 교체 실험은 미채택이다. mlx_lm 0.31.3 서버는 온도>0에서 seed를 무시하고(생성 스레드의 컴파일 sampler), 온도0 출력도 prompt-cache 이력에 따라 갈린다. 제품은 온도/seed 미지정(argmax).
- **현재 후보:** 기존 앱 후보 O/v15, 삽입 지시 복구 가드는 #76으로 main 병합(10-21). W는 격리 API18778(실패 보존)/18779(범위 설명 정렬)·UI13001에서 검증했으며 기존 앱/기본 포트는 전환하지 않았다. 원문/거부 응답을 보존한다. HEAD만으로 WIP 후보를 식별하지 않는다.
- **최근 실측:** 10-20 같은 원래 SA UID의 1h 토큰만 task-private 갱신, 기존 workload 읽기. 현재 rev37/replicas2·Deployment UID/전체 spec은 T 최종값과 같다. 새 app/external health 증명 아님. T 반복/데모는 완료분으로 유지한다.
- **검증:** `make check` → **3390 passed, 3 skipped**·20warnings·116.70초(2026-10-25 로컬 macOS·Python3.13.5·Homebrew Node26.11.0(이전 공식Node22.23.3 임시 경로 소실)). 삽입 지시 가드 단위4·pydantic-ai 2.60 도구 outcome 회귀5 신규(2.9/2.59/2.60/2.61 통과, 변이 red). 모델 측정은 cold/warm 각5 case 단일 응답+10-25 진짜 표본 50응답(코드 차단 유지, 표식 없는 지시문 우회 2/5)이며 의미 해결이 아니다.
- **Phase 5:** 독립 Python Lambda 설계와 저장/준비/상태 UI·AWS transport까지 로컬 완료. M91의 2026-09-15 인증 해소·배포 후보 검증은 운영 배포/Invoke/PR 발행 완료가 아니다.

## Guardrails

- **보존:** lab 1367338348·checkout 및 R2 lab/App 4924748·설치161238144·키·branch·draft PR #1 보존. 추가 삭제 금지. 기존 WIP를 되돌리거나 정리 명목으로 덮어쓰지 않는다.
- 로컬 dogfood는 승인됐고 10-20 사용자 지시로 재개했다. Phase 5 원격 실행과 Phase 4b 비용·기간·종료 조건은 별도 범위다.
- Python **3.13**·IaC CDK TypeScript·모델 정의 `models.py`. 기존 온프렘 Terraform/Ansible 경로의 존재를 새 IaC 도입 근거로 쓰지 않는다.
- IAM 최소 권한. `Resource:"*"`는 이유 없는 사용을 금지한다. `Delete/Drop/Terminate`는 강제 APPROVE(D48). 읽기 전용 도구 제한과 자격증명 격리는 별개다.
- `main` 직접 push 금지, PR+CI로 병합(D43). 코드 소유자 리뷰는 별도다. 커밋/푸시·원격 변경은 기존 승인 범위 안에서만 수행한다.
- 요청 범위 밖 기능 추가 금지. 원인 재현→구분 측정→수정→재측정. 테스트 수·형식/인용 통과를 의미 정확도로 승격하지 않는다. 변경 시 `make check`, 날짜·환경·skip·검증 범위를 함께 기록한다.
- 새 가드는 실제 소비 경계에서 반증하고 WIP를 바이트 단위로 복원한다. 소진된 목록·과거 성공·오래된 재개 조건을 현재 사실로 단정하지 않는다(STATUS Risk12).

## 이력과 도구

- 구현 이력은 `COMPLETED_SUMMARY` **M0~M91** (`docs/COMPLETED_SUMMARY.md`), 최신 증분은 `PROGRESS_LOG`가 권위다. 닫힌 항목의 경위·주의사항은 `docs/archive/brief-detail-2026-09.md` 참조.
- 10-03 정리 전 원문은 [10월 아카이브](archive/progress-2026-10.md#tidy-20261003-brief)에 보존했다. 과거 비용·게이트·직전 세션 상세를 이 진입점에 다시 복제하지 않는다.
- `/sync` 읽기 · `/checkpoint` 기록 · `/tidy-docs` 정리 · `/diagnose` 원인 규명 · `/overnight-report` 무인 결과 검수 · `/overnight-seed` 열린 작업 점검. 현재 열린 `[auto]` 씨앗은 없다.
