# AGENT_BRIEF — platform-agent

최종 갱신: 2026-08-15

> ▶ NEXT SESSION: **4a는 승인됐고, 착수 전 결정이 하나 남았다 — `write_relabel_configs`
> 허용목록**(`docs/plans/2026-08-08-phase4-scope-and-cost.md` **§4 정정 박스가 권위**).
> ⚠️**승인 근거였던 "≈$5/월"이 100배 틀렸다**: 실측 **52,438 시계열 = 월 5.13B 샘플** →
> 필터 없이 remote_write하면 **≥$180/월**로 4b(≈$185)를 넘본다. $5는 **60초 간격 1,285
> 시계열**(전체의 2.5%)을 산다. ✅**허용목록 제안서 나왔다** —
> `docs/plans/2026-08-15-4a-remote-write-allowlist.md`(메트릭 4종·**308 시계열**·**$1.20/월**). **승인만 남았다.**
> ⚠️**$0 선행**: BQ 결제 내보내기만 남았다(콘솔 수동 → `docs/GCP_BILLING_EXPORT_SETUP.md`,
> 확인은 `make spend-check`).
> **무과금으로 이어서 할 것**: capability 스캔 잔여 **ⓐ·ⓒ**(정책) · "런북 walk ②"(`severity` 축) ·
> ⛔`slack_live_approval`도 **닫혔다**(08-16 — 데모 선행은 틀린 기록이었다). ⛔**`triggered_at`·`metric_name`은 닫혔다**(08-15 전수 스윕, M21 증거 §8 — 결함이 아니라 **범위**, 8필드 중 닿는 건 `reason` 하나). **다시 열지 말 것.**
>
> ⚠️ `main` 보호 — 직접 push 불가(소유자 포함), **PR + CI 통과로만 병합**(D43).
> ⚠️ 초록에는 조건이 붙는다(Risk 12, 이제 **일곱**): **새 가드는 지워 보고 red를 확인**(③) · **skip은 실패가 아니다** — 게이트 숫자엔 **잰 기계**까지 붙일 것(②) · **가드는 독자가 읽는 그 물건에 대고 물을 것**(④ — **결함을 그 그림자로 세지 말 것**, **경고는 주장만 묻지 말고 지시까지**, **문은 넷**) · ⑤**가드 자신도 틀린다**(08-13: 픽스처로 고른 값이 **틀린 기본값과 같아** 결함을 통과시켰다 · 변이 하네스가 `git checkout --`로 **커밋 안 된 고침을 날리고** 있었다 — **초록으로 안 돌아오는 복구는 복구가 아니다**) · ⑦**변이 결과는 어디에 물었는지까지 말할 것**(08-15: **틀린 테스트 파일**에 물어 "가드 없음"으로 읽었는데 전체 스위트로는 red였다 · **변이·실행·복구는 한 스크립트 안에** 둘 것).
> ⚠️ **"소진"은 이제 여섯 번 틀렸다** — 가장 값싼 다음 수는 대개 **직전 세션이 이미 적어 뒀다**. ⚠️**목록에 적힌 항목 자체가 틀릴 수도 있다**(08-15: ⓑ는 "매핑 없음"이었는데 네 provider 전부 있었고 **기록보다 한 달 먼저** 있었다) — **틀린 항목도 값이 난다**(시험하다 옆의 진짜 결함이 나왔다). 단 **`git log -L`로 "언제부터"까지** 물어야 stale과 오기를 가른다.
> ⚠️ **"안 봤다"를 시험하면 결함이 아니라 범위가 나올 때도 있다**(08-13에 두 번). ⚠️**형제 집합은 세는 순간 전부 셀 것** — 08-13에 세 번(**세 번째는 그걸 찾으려고 만든 스윕 안에서**), **08-15에 둘 더**(한쪽만 import가 되돌아가 죽어 있었다 · **네 어댑터를 열거한 도크스트링 아래 `aws.analyzer`만 임포트**한 가드 — ⚠️**산문이 참이어도 임포트 줄이 범위다**). ⚠️**"선언됐는데 안 읽힌다"는 자동으로 결함이 아니다** — 기준은 **읽는 쪽의 provider 간 비대칭**이다(`provider` 필드를 읽기 시작하면 GCP/Azure는 전부 폴백으로 떨어진다).
> ⚠️ **추정표는 어느 칸이 측정이고 어느 칸이 가정인지 표시할 것**(08-15, 4a): 정가는 맞았는데 **안 잰 시계열 수**가 총액을 100배 지배했다 — **가정이 지배하는 추정은 추정이 아니라 그 가정이다.** 그리고 **권위 문서가 틀리면 복제본이 그것을 사실로 굳힌다**(진입점 3곳이 "$5"를 복제해 승인까지 갔다 — **복제 금지 규약이 겨냥한 실패**).
> 직전 세션 → **M26**(렌즈가 `ExecutorOutput`에서 **말랐다** — 값 사본만 계약에 모았다, 동작 변경 0) · **M25**(optional 임포트 **여섯이 미선언** — `.[azure]`엔 LLM조차 없었다, +19) · **M24**(게이트가 **테스트마다 Gemini를 과금 호출**하고 있었다 — 288s→39s, D49) · **M23**(파괴 액션 `Destroy`가 **AWS에만 없어** 두 클라우드엔 APPROVE·AWS엔 **AUTO**였다, +79) · **M22**(승인자에게 보여 준 "과거 유사 인시던트"가 **랜덤 ID 사전순**이었다 — 이번엔 **AWS만** 틀렸다, +13) · **M21**(`reason`이 규칙 이름을 잃어 등급이 P3↔P1로 뒤집혔다 — 형제가 provider가 아니라 **같은 provider의 진입점**이었다, +17) · **M20**(운영자 severity가 두 모델에 안 닿았다, +18) · **M19**(`resource_types` 미판독, +32) · **M18**(형제 집합, D47).
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
- **동작하는 것:** Operations 4단계 + 3-cloud AI Agent + **On-Prem Ops**(12도구, trace) + Terraform kind/실 Multipass VM Ansible k3s Provision + kagent↔Local Qwen A2A + Agents UI. **On-Prem 오프라인 완결**: Local **Qwen3-Coder-30B-A3B**(MoE·활성 3B, `Makefile:58`)로 NL provision→deploy→validate ~39s, 로컬 JSONL 기록 + 대시보드 **hybrid**(AWS+On-Prem 병합) + 실 **롤백**(app/cluster). **추적 IA**: activity에 `type`(provision/deploy)·`cluster` 연결키, 대시보드 **Provisioning/Deployments/History** 분리 + **중첩 상세**(provisioning⊃deploys), 롤백 **단일-row 승계**·**teardown→deploy cascade**, 자연어 rollback/teardown도 동일 라우팅.
- **하네스:** overnight-harness 플러그인 기반 (5 engine). `make overnight-kiro-once` 로 smoke. `make dev-up`으로 로컬 스택(MLX+proxy+router+dashboard) 한 방 기동.
- **Kiro 특화:** aws-ops / cdk-dev / overnight-harness 3개 에이전트 + safety hook + AWS MCP Server.
- **검증:** `make check` → **2102 passed, 2 skipped** (**2026-08-15 로컬 macOS·py3.13** / **CI도 동일** — 2026-08-16 `aa1c913` ubuntu·py3.13, PR #39; 게이트 숫자는 날짜와 **잰 기계** 없이는 주장이 아니다, Risk 12①②). CI(`gate.yml`)가 **main 병합 조건**이고 **terraform 검증까지 실제로 돈다**. 이력·근거는 `STATUS` 검증 Baseline과 `COMPLETED_SUMMARY` **M10~M26**에 있다 — 여기에 다시 적지 말 것.
- **현재 초점:** **Phase 4(billable, 별 승인)만 남았다.** 공급망은 생산자→소비자→CI 키리스까지 섰고 **어드미션만 업스트림 대기**(cosign v3 ↔ policy-controller 저장 위치 불일치, 양방향 실증). Phase 5는 **경계까지**(UI·PR 생성 없음). ⚠️**과대 해석 금지**: 스코프·배포 신원·이미지 서명 게이트는 전부 **옵트인** · 자격증명이 테넌트-바운드인 건 **온프렘뿐** · CODEOWNERS는 **라우팅** · `main` 보호는 **게이트 집행**이지 리뷰 집행이 아니다. **반복 확인된 것**: 새 항목은 **기록된 이유를 한 번 돌려 보고** 시작할 것 — 다만 **틀려 있을 때만 값이 나오는 게 아니다**(08-09 GCP 3건은 전부 성립했는데, 확인하는 과정에서 **프로브의 provider 누락**이 나왔다). 그리고 **읽는 쪽으로 갈 것**: "이 dict를 덮는 테스트가 있나"의 답은 "다섯 개 있다"였는데 **전부 dict의 모양만 물었고**, 읽는 쪽엔 두 provider에 복사된 **죽은 티어**가 있었다(08-13).

## Guardrails

- 에이전트=Python(**게이트는 3.13에서만 검증됨** — `requires-python = ">=3.11"`은 미검증 주장,
  Risk 12②) / IaC=CDK TS / 모델은 `src/agents/models.py` 한 곳.
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
