# PROGRESS_LOG — platform-agent

최종 갱신: 2026-09-01

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---

## 2026-09-01 — 4a를 접었다: 청구액이 $0.00이라 지운 게 아니다 — 대가는 장기 키였다 (gate 2339)

- Status: 사용자 결정으로 D50의 약속을 집행했다. **셋 다 삭제** — AMP 워크스페이스
  `ws-929b8da9…`(ap-northeast-2) · IAM 사용자 `amp-remote-write-4a` · 키 `AKIA…62VN`.
  권위 `docs/evidence/folding-4a-the-price-was-a-long-lived-key.log` · 계획서 **§11** · **D50 Folded**.
- Verified(**삭제 전 실측 — 정책이 기록과 정확히 일치했다**): 관리형 정책 **0건**, 인라인 **1건**이
  전부 `aps:RemoteWrite` **하나**를 그 워크스페이스 **하나**에. 키 마지막 사용 08-30T14:25Z `aps`.
  ⚠️**좁은 키도 장기 키다** — 그래서 지웠다. **$0.00은 지울 이유를 줄이지 않았다**(D50이 미리 그렇게 적어 뒀다).
- Verified(**"없다"를 어떻게 봤는지까지**): 8리전 스윕 전부 0 · `describe-workspace`를 **id로 직접**
  물어 `ResourceNotFoundException` · `get-user` `NoSuchEntity` · `list-users|amp` `[]`.
  ⚠️**`get-access-key-last-used`는 `AccessDenied`였고 그건 부재의 증거가 아니다** — 권한이 없어
  나온 답이라 키가 살아 있어도 같다. **증거는 소유 사용자의 부재**(키는 사용자보다 오래 못 산다).
  08-30 프로브의 429가 *"이것은 '0'이 아니다"*였던 것과 같은 모양.
- Changed(**레포에도 있었다**): `values/kube-prometheus-stack.yaml`의 `remoteWrite:` 블록 삭제 —
  안 지우면 **삭제된 워크스페이스를 가리키는 설정**이 git에 남는다. ⚠️**찾다가 내가 한 번 틀렸다**:
  `git grep`에 `| head -30`을 붙였는데 `docs/`가 `infra/`보다 먼저 정렬돼 **정작 그 파일이 잘렸고**
  "레포엔 없다"고 쓸 뻔했다 — 도구 함정이 아니라 **내 절단**이다.
- Changed(**가드를 지울 뻔했다 — 지웠으면 $180짜리 구멍**): `test_amp_cost_handles.py`의 9건은
  목적지가 사라지면 **전부 공허하게 참**이 된다(*"허용목록은 정확히 이 넷"*은 허용목록이 없을 때
  잘 통과한다). 지우는 쪽도 답이 아니다 — **D48은 4a를 접어도 안 죽고**(필터 없음 = 프리티어
  **128배**, ≈$180/월 = 4b 값 ⇒ 4a를 고른 이유가 지워진다) 그걸 적어 둔 유일한 물건이다.
  계약을 **함수로 빼** 두 호출자에 물렸다: 살아 있는 파일(목적지 **없어야** 한다) + **합성 표 9종**.
- Verified(**⚠️첫 판이 틀렸다 — 그림자로 세고 있었다**): 합성 표를 `violations != []`로만 묻자
  **와일드카드 검사를 통째로 지워도 초록**이었다(M2 생존) — `kube_.*`가 `allowlist-drift`에도
  걸려서다. **M17의 "결함을 그 그림자로 세지 말 것"** 그대로. 위반에 코드 7종을 붙이고 케이스가
  **어느 규칙이 물어야 하는지**를 지정하게 고쳤다 + 함수 본문에서 코드를 긁어 표와 대조하는
  가드(새 규칙이 케이스 없이 늘면 red). 재변이 **7종 전부 red**, 복구는 `__pycache__` 삭제 후 확인.
- Verified(**남긴 것의 이유가 바뀌었다**): KSM interval **60s 유지** — 더는 비용 손잡이가 아니고,
  데모 알람 룰이 `[5m]`로 적분하니 **60초=5샘플**(120초면 2샘플이라 `> 2`가 **원리상 도달 불가**).
  ⚠️**워크스페이스 id는 이제 안 박는다** — 없는 것을 박으면 **영원히 틀릴 수만 있는 규칙**이다.
- Blockers: 없음. 로컬 kind는 도커가 꺼져 이미 멈춰 있었다 — 다음에 띄우면 고아가 될
  `monitoring/amp-remote-write` Secret 삭제할 것.
- Next: **`onprem` extra의 `mlx-lm`**(승인 게이트 없는 유일한 코드 항목) · 정적검사 게이트 편입
  여부(레포의 결정) · BQ 결제 내보내기(콘솔 수동).

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
