# AGENT_BRIEF — platform-agent

최종 갱신: 2026-08-09

> ▶ NEXT SESSION: **Phase 4 산정은 끝났다 — 이제 필요한 건 사용자 결정이다**
> (`docs/plans/2026-08-08-phase4-scope-and-cost.md`). 요지: Phase 4는 **비용이 40배 다른 둘로
> 쪼개진다**(4a 관리형 어댑터 ≈$5/월, 원격 클러스터 불요 · 4b 원격 클러스터+DR ≈$185/월).
> ⚠️**$0·무승인 선행 둘 중 하나는 닫혔다**(₩20 상시 발화 예산 → ₩28,000). 남은 하나는
> **BQ 결제 내보내기**(콘솔 수동 → `docs/GCP_BILLING_EXPORT_SETUP.md`) — 없으면 **금액을 모른다**.
> GCP에 지출을 읽는 API가 **없다는 건 재측정으로 확정됐다**(discovery 실측, Risk 4).
> 켠 뒤 먹혔는지는 **`make spend-check`가 답한다**(이제 GCP 상태를 출력한다).
>
> ⚠️ `main` 보호 — 직접 push 불가(소유자 포함), **PR + CI 통과로만 병합**(D43).
> ⚠️ 초록에는 조건이 붙는다(Risk 12): **새 가드는 지워 보고 red를 확인**(③) · **skip은 실패가 아니다** — 게이트 숫자엔 **잰 기계**까지 붙일 것(②).
> 직전 세션 상세 → `COMPLETED_SUMMARY` **M15**.
>
> 1분 압축 문맥. 에이전트 진입점. 이 파일은 **≤60줄**로 유지한다.

## Read Path (순서대로, bulk-read 금지)

1. `docs/AGENT_BRIEF.md` — 이 파일
2. `docs/STATUS.md` — 현재 상태 / 검증 baseline / risks
3. `docs/NEXT_PLAN.md` — 열린 작업만
4. (필요 시) `docs/PROGRESS_LOG.md` 상단 — 최신 증분
5. (필요 시) `docs/engineering/` — harness/loop/context 엔지니어링

권위 순서: `NEXT_PLAN.md` (유일한 source of truth).

## Snapshot

- **무엇:** AWS-native 플랫폼 에이전트. provision → deploy 검증 → detect → analyze → decide → execute → Slack 리포트.
- **동작하는 것:** Operations 4단계 + 3-cloud AI Agent + **On-Prem Ops**(12도구, trace) + Terraform kind/실 Multipass VM Ansible k3s Provision + kagent↔Local Qwen A2A + Agents UI. **On-Prem 오프라인 완결**: Local Qwen **7B**로 NL provision→deploy→validate ~39s, 로컬 JSONL 기록 + 대시보드 **hybrid**(AWS+On-Prem 병합) + 실 **롤백**(app/cluster). **추적 IA**: activity에 `type`(provision/deploy)·`cluster` 연결키, 대시보드 **Provisioning/Deployments/History** 분리 + **중첩 상세**(provisioning⊃deploys), 롤백 **단일-row 승계**·**teardown→deploy cascade**, 자연어 rollback/teardown도 동일 라우팅.
- **하네스:** overnight-harness 플러그인 기반 (5 engine). `make overnight-kiro-once` 로 smoke. `make dev-up`으로 로컬 스택(MLX+proxy+router+dashboard) 한 방 기동.
- **Kiro 특화:** aws-ops / cdk-dev / overnight-harness 3개 에이전트 + safety hook + AWS MCP Server.
- **검증:** `make check` → **1718 passed, 1 skipped** (**2026-08-09, 로컬 macOS·py3.13** — 게이트 숫자는 날짜와 **잰 기계** 없이는 주장이 아니다, Risk 12①②). CI(`gate.yml`)가 **main 병합 조건**이고 이제 **terraform 검증까지 실제로 돈다**. 이력·근거는 `STATUS` 검증 Baseline과 `COMPLETED_SUMMARY` **M10~M15**에 있다 — 여기에 다시 적지 말 것.
- **현재 초점:** **Phase 4(billable, 별 승인)만 남았다.** 공급망은 생산자→소비자→CI 키리스까지 섰고 **어드미션만 업스트림 대기**(cosign v3 ↔ policy-controller 저장 위치 불일치, 양방향 실증). Phase 5는 **경계까지**(UI·PR 생성 없음). ⚠️**과대 해석 금지**: 스코프·배포 신원·이미지 서명 게이트는 전부 **옵트인** · 자격증명이 테넌트-바운드인 건 **온프렘뿐** · CODEOWNERS는 **라우팅** · `main` 보호는 **게이트 집행**이지 리뷰 집행이 아니다. **반복 확인된 것**: 새 항목은 **기록된 이유를 한 번 돌려 보고** 시작할 것 — 다만 **틀려 있을 때만 값이 나오는 게 아니다**(08-09 GCP 3건은 전부 성립했는데, 확인하는 과정에서 **프로브의 provider 누락**이 나왔다).

## Guardrails

- 에이전트=Python(**게이트는 3.13에서만 검증됨** — `requires-python = ">=3.11"`은 미검증 주장,
  Risk 12②) / IaC=CDK TS / 모델은 `src/agents/models.py` 한 곳.
- IAM 최소 권한(`Resource:"*"` 금지), `Delete/Drop/Terminate` 액션은 강제 APPROVE.
- 요청 이상 기능 추가 금지. 테스트 통과 전 완료 선언 금지.
- Gate 명령: `make check`. **`main`은 보호됨** — 직접 push 불가, PR + CI 통과로만 병합(D43).

## Skills (overnight-harness)

- `/sync` — Read Path 따라 상태 복원(읽기 전용).
- `/checkpoint` — PROGRESS_LOG append + current docs 갱신.
- `/tidy-docs` — 문서 정리/압축.
- `/overnight-report` — 루프 결과 리포트.
- `/overnight-seed` — backlog 시드.
- `/diagnose` — 루프 실패 진단.
