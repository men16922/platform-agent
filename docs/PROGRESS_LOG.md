# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-30

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-30 — "지금 비용 나가는 거 없지?"를 재다: 예 — 단 4a가 안 접혔고 한 리전만 보고 답할 뻔했다

- Status: 사용자 질문에 문서 인용이 아니라 **재서** 답했다. 상시 지출은 **AWS 하루 $0.0034**
  (≈$0.10/월)뿐. 권위 `docs/evidence/what-is-actually-billing-2026-08-30.log`.
- Verified(**MTD로 답했으면 15배 틀렸다**): `make spend-check`는 **MTD $10.25**를 먼저 답한다.
  일별로 가르면 바닥은 **$0.0034/일**이고 MTD의 $9.00(EC2+VPC)은 **08-09에 멈춘 지출**이다.
  ⚠️바닥 위로 올라온 유일한 항목은 **Cost Explorer 자기 자신**(이번 달 **$0.64** = 우리가 만든
  최대 항목) · **08-30 줄의 $0.0000은 CE 지연 이틀+ 때문이지 "0"이 아니다** · 도는 EC2 전 리전 0대.
- Verified(**⚠️새 함정 — 세는 함정 넷째**): `aws amp list-workspaces --region us-east-1`이 `[]`를
  답해 **"4a 워크스페이스는 지워졌다"고 쓸 뻔했다.** 막은 건 옆의 측정이었다 — 키의 마지막 사용
  리전이 `ap-northeast-2`였고, 거기 **`platform-agent-4a`가 ACTIVE**였다. **리전 서비스에 대고
  "없다"를 말하려면 리전을 돌 것**(한 리전으로 전역을 답한 것 = M18~M20 형제-집합 실패와 같은 모양).
- Verified(**4a 접기(D50) 미완**): 워크스페이스 ACTIVE · IAM `amp-remote-write-4a`의 키
  `AKIA…62VN` **Active**, 마지막 사용 **오늘 13:50Z `aps`** · 로컬 kind가 1시간 전 재기동돼
  Prometheus가 **지금도 remote_write 중**(허용목록 메트릭 **4개** 그대로 ⇒ 청구 **$0.00**).
  **비용 문제가 아니다** — M38이 미리 적은 대로 **대가는 장기 액세스 키 하나**다.
  ⚠️그래서 **M38·STATUS의 duty cycle 기록이 stale해졌다**(*"08-27T19:55Z 이후 죽음"*은 더는 참이
  아니다) — 그 13%는 **그 창의 측정**이지 현재 상태가 아니다.
- Verified(**Azure ₩7,063 전액이 남의 프로젝트**): ⚠️첫 조회는 **429**로 실패했고 프로브가
  *"이것은 '0'이 아니다"*라 답한 그대로 **재시도가 답이었다**. ActualCost = ACR
  `acrroadpilot23842f7d`(`rg-roadpilot`) **₩7,063** · Cosmos ₩0 · Log Analytics ₩0 ·
  우리 `platform-agent-foundry-rg` **₩0**. Risk 4의 "ACR ₩6,600(타 프로젝트)"이 **재서 성립**.
- Verified(**GCP는 여전히 못 잰다**): 프로젝트 5개에 내보내기 테이블 0 — **'₩0'이 아니다**.
  상시 추정 ~$0.72/월은 **추정이지 측정이 아니다**. 여는 길은 콘솔 수동 하나.
- Blockers: 없음. 오늘의 코드 변경(M39)은 **배포한 게 없어 비용과 무관**하다.
- Next: **4a 접기 여부가 사용자 결정**(워크스페이스+IAM+키 · 지우면 로컬 remote_write가 실패
  하기 시작한다) · `onprem` extra의 `mlx-lm` · BQ 결제 내보내기(콘솔 수동).

## 2026-08-30 — Azure는 하지 않은 조치를 "해결됨"으로 보고했다 — 배선했고, 게이트 숫자가 내려갔다 (gate 2332)

- Status: 승인 사안이었다(08-16 발견, 배선하면 라이브 ARM/AKS를 친다). 사용자 승인 후 배선.
  진입점 셋이 13일간 `▶ NEXT SESSION` 첫 행동으로 가리켜 온 항목이다.
- Verified(**기록된 근거를 먼저 다시 돌렸다**): 디스패치 비대칭 유효(gcp 325줄 러너를 부르고
  azure 311줄은 안 부른다) · `_execute_aks_call`의 롤백 분기가 **patch 직전 이미 GET을 한다**
  ⇒ Phase 3② 배선도 **추가 API 호출 0**, GCP에서 성립한 근거가 그대로 성립.
- Changed(**배선**): `azure/executor.py`가 `run_azure_action`을 `resolve_incident_scope`와 함께
  부른다(GCP와 같은 모양, 발명 없음). 미구현 11종은 러너의 `ValueError`가 `except`를 타고
  **`success: False`**가 된다 — 조용한 성공이 안 된다. `azure_runner` AKS 롤백에 `guard_rollback`.
- Changed(**기록 둘이 같은 커밋에서 움직였다 — 설계된 결합**): `EXPECTED`의 azure 면제 →
  `{run_azure_action}` · `JUSTIFIED_GAPS` **비었다**(그 항목이 자기 만료 조건을 적어 뒀고
  `test_a_justified_gap_that_closed_must_be_removed`가 집행했다).
- Changed(**가드 +9**): 신규 `test_executor_reports_only_what_the_runner_did.py`(**+7**) —
  AST는 *"호출이 소스에 있나"*는 물어도 ***"성공이라 보고한 것이 실제로 일어났나"는 못 묻는다***.
  gcp·azure 둘 다에 대고 러너 호출·실패 전파·`resolved` 판정을 묻는다(형제 하나만 순회 금지,
  `WIRED`가 디스패치 표와 어긋나면 red). 면제 표가 비어 **하중 없는 규칙이 된 둘**은 합성 표에
  대고 한 번 더 물었다(**+2**) — **실패할 수 없는 규칙은 규칙이 아니다**(Risk 12③).
- Verified(**⚠️예상 못 한 것 — 비대칭 7건이 한 번에 닫혔다**): `test_contract_symbol_parity`가
  red. 배선이 Azure를 스코프/reconciler 계약 표면에 닿게 만들어 `guard_rollback`·`IncidentScope`·
  `resolve_incident_scope`·`guard_scoped_action`·`IsolationTier`·`Registry`·`load_registry`의
  정당화가 stale이 됐다. M29의 *"one cause, six symptoms"*가 **반대 방향으로 확인된 것**이다.
  ⚠️그 파일의 공허성 검사(`>= 20`)가 26→19로 red가 됐고 **초록으로 가는 길이 숫자를 내려 적는
  것뿐**이었다 — 그건 이 파일이 스스로 이름 붙인 *allowlist nobody prunes*다. **구조적 양성
  대조로 교체**(`paginated_scan=={aws}` · `run_gcp_action=={aws,gcp}`) — 결함이 닫혀도 안 낡는다.
- Verified(**변이 6종 red, 생존 0**): 호출 삭제(**4 failed** — AST 표 + 행동 셋이 다른 각도로
  잡는다) · except가 success:True · `guard_rollback` 삭제 · `WIRED`에서 azure 제거 · 면제 규칙 둘
  무력화. 기준선 먼저 찍고 `__pycache__` 삭제 후 복구 확인(35 passed, 기준선과 동일).
- Verified: `make check` **2332 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
  ⚠️**숫자가 내려갔다**(2337에서 −5) — 분해: 정당화 7건 해소 **−14**(parity가 양쪽에
  파라미터라이즈) · 새 행동 가드 **+7** · 공허성 둘 **+2**. **결함이 닫히면 그 결함을 설명하던
  줄도 사라진다** ⇒ 게이트 숫자는 단조증가 지표가 아니다. **줄어든 숫자는 분해해 적을 것.**
- Blockers: 없음. **blast radius는 오늘 0**(러너가 만지는 AKS·FunctionApp 둘 다 구독에 0개) —
  ⚠️**오늘의 사실이지 불변식이 아니다**. 자격증명 테넌트 바인딩은 여전히 Phase 4(Risk 10).
- Next: **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정) · **Phase 3② AWS 잔여**
  (SSM Automation 경로라 러너가 없다 — 가드가 그 사실을 박아 뒀다).

## 2026-08-30 — 인용된 마일스톤 넷이 기록된 적이 없었다 (gate 2337)

- Status: `/tidy-docs` 3단계(완료분을 `COMPLETED_SUMMARY`로 압축)를 하려다, **진입점이 M34~M37을
  인용하는데 `COMPLETED_SUMMARY`는 M33에서 끝나 있는 것**을 봤다.
- Verified(**가드가 있었는데 이 모양을 못 봤다**): `test_milestone_pointer_claims`는 바로 그 실패
  (*"/checkpoint의 compress-into-completed 단계가 여섯 번 건너뛰어졌다"*)를 위해 쓰인 파일인데,
  **`COMPLETED_SUMMARY **Ma~Mb**` 범위 인용만** 검사한다. 문서가 그사이 **개별 이름(`M35`)으로
  가리키게** 바뀌었고, 그래서 **넷이 빠진 채로 초록**이었다. 오늘 `test_amp_bill_claims`가 §10은
  검사하면서 경로를 자기가 들고 있어 문서의 경로 상실을 못 본 것과 **같은 모양**이다 —
  **한 형식을 검사하는 가드는 다른 형식을 안 본다.**
- Changed(**M34~M37 기록**): archive의 원본 증분에서 뽑아 형식대로 썼다. M34=계약 세 형식 중 walk가
  둘만 물었다(도크스트링은 셋을 정확히 열거했다) · M35=ⓐ는 현행 유지, 스윕이 결함 넷(⚠️**내 픽스처가
  한 번 틀렸다** — 쌍 키를 잘못 걸어 "전부 미구현"으로 읽었고 주장 전에 잡았다) · M36=가드가
  **생산에서 도달 불가한 입력**으로만 통과했다 · M37=티어 2가 **조건 평가 없이** 추천에서 액션.
- Changed(**M38 = 오늘의 4a 종료**): 청구 $0.00 · 사유는 `Always Free` 40M · 교차 확인 2.4% ·
  유출 0 · ⚠️믿으면 안 되는 요약 둘("어차피 공짜"·"$1.42"). 이걸로 `NEXT_PLAN`의 닫힌 4a 블록을
  **4줄 → 2줄 포인터**로 줄였다(120 → 118줄).
- Changed(**가드 +4**): 같은 파일에 **맨 `Mnn` 인용도 실재해야 한다**를 더했다(BRIEF·STATUS·NEXT_PLAN).
  ⚠️`\bM(\d+)\b`는 `40M`·`15.8M`을 안 잡는다(숫자가 M 뒤에 와야 한다) — 라이브 문서에 대고 확인하고 박았다.
- Verified(**변이 3종 red**): **M34~M37 다시 지우기**(오늘 이전 상태 재현) · M35 제목만 깨뜨리기 ·
  인용 정규식 무력화. 복구 확인 전에 `__pycache__` 삭제.
- Verified: `make check` **2337 passed, 2 skipped**(2026-08-30 로컬 macOS·py3.13).
- Blockers: 없음. **예산**: brief 60/60·6,698자 · status 120/120·9,074자 · plan **118**/120·9,417자 · log 99/120.
- Next: **Azure executor 배선**(승인) · **BQ 결제 내보내기**(콘솔 수동) · **정적검사 게이트 편입**(결정).
