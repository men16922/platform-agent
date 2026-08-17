# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-17

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-17 — ⓒ: 앞쪽은 맞았고 "테스트가 고정했다"가 틀렸다 (gate 2269)

- Status: 마지막 미측정 항목 **ⓒ**(*"티어 2는 첫 매치가 이긴다(AWS는 점수제) — 테스트가
  고정했으니 우연이 아니라 결정이다"*). **앞쪽은 정확하고 뒤쪽이 틀렸다.**
- Verified(**기존 가드가 생산 경로를 한 번도 안 물었다**): `test_capability_catalog_scan`의
  케이스는 **후보를 유일하게 가리는 capability 집합을 손으로 골랐다**(`["rollback_release"]` →
  health-check-failure, `["drain_node"]` → network-latency-high). ⚠️**어떤 signal 어댑터도
  그런 집합을 안 낸다** — `kubernetes-workload`엔 전부 `restart_workload`+`scale_out`을 내고
  그건 **후보 셋과 동시에 겹친다.** 즉 **첫-매치 구현과 점수제 구현이 답이 같은 경우만
  태웠다**(Risk 12⑤). 게다가 `["rollback_release"]`는 **그 세 provider가 추천하지 않는 값**이다
  (오늘 M35에서 측정) — 생산에서 도달 불가한 입력으로 통과하고 있었다.
- Verified(**실제 집합으로 물은 결과**): GCP/Azure는 OOM·health-check·latency **셋 다**
  `eks-pod-oom`/**rto 180**을 보고한다. AWS는 namespace(+2)·keyword(+1) 점수로 **셋을
  구분한다** — health-check는 `health-check-failure`/**rto 240**. 액션은 추천에서 오므로
  같지만 **운영자에게 보고되는 runbook_id·rto_sec이 다르다**(M22 계열: 사람에게 틀린 걸 보여준다).
- Verified(**catalog 규약의 안전 속성이 provider마다 다르다**): *"appending은 선택을 못
  바꾼다"*는 주석은 **AWS 점수 동점 규칙**에 대한 것이다. GCP/Azure는 점수가 없어 **순서가 곧
  알고리즘**이라, 앞에 끼운 런북이 **모든 선택을 훔친다**(실측: `thief`/rto 9999). 주석에
  provider 범위를 적고 가드로 집행했다.
- Changed: `catalog.py` 주석에 **AWS-scoped임과 "append, never insert"**를 명시. `src` 동작
  변경은 **0** — 판별 수단을 줄지는 **설계 결정**이라 손대지 않았다(`NEXT_PLAN` ⓒ).
- Changed(가드 +12, `test_tier2_selection_is_ordered_not_scored.py` 신규): 입력을 **어댑터에서
  직접 읽어** 픽스처가 생산과 어긋날 수 없게 했다 · 전제(후보>1)를 먼저 묻는다 · GCP/Azure ×
  세 인시던트 · AWS가 셋을 구분함 · **앞에 끼우면 훔치고 뒤에 붙이면 안 훔친다.**
- Verified(**변이 4종 전부 red**): 첫→마지막 매치(9건) · overlap 게이트 제거(6건) · 추천 집합
  축소로 모호성 제거(4건) · **AWS namespace 점수 죽이기(1건)**. ⚠️**마지막이 1건인 게 요지다** —
  AWS 점수제가 셋을 구분한다는 사실을 잡는 건 **오늘 만든 가드 하나뿐**이었다.
  `make check` **2269 passed, 2 skipped**(로컬 macOS·py3.13).
- Blockers: 없음. ⛔설계 결정 하나가 열렸다(GCP/Azure 판별 수단) + M35의 `rollback_release` 정책.
- Next: 08-19 이후 AMP 청구액 대조.

## 2026-08-17 — ⓐ를 시험하니 답은 "현행 유지"였고, 스윕이 결함 넷을 냈다 (gate 2257)

- Status: 무과금 목록에 남은 **capability 스캔 ⓐ·ⓒ**. 규율대로 **기록된 이유부터 시험**했다.
- Verified(**ⓐ의 주장은 성립**): `kafka-lag-spike`가 유일하고 어긋남은 **한 방향뿐**(반대 0건 —
  ⚠️처음엔 한 방향만 물었다). ⚠️**내 픽스처가 한 번 틀렸다**: resolve는 **(capability,
  resource_type) 쌍**으로 키를 거는데 `kafka-topic`으로 물어 *"네 provider 전부 미구현"*으로
  읽었다. 올바른 `streaming-consumer`로는 **전부 resolve된다.** 주장 전에 잡았다.
- Verified(**두 선택지는 대칭이 아니다** — 08-12엔 "둘 다 동작 변경"이었다): 티어 2(GCP/Azure)는
  액션을 **steps가 아니라 `recommended_capabilities`에서** 만들고 `capabilities`는 **매치
  게이트일 뿐**이다. `scale_out_workers`가 이미 겹쳐 **더해도 관측 변화 0**, **빼면 네 provider가
  다 resolve하는 에스컬레이션 스텝을 잃는다.** ⇒ **현행 유지로 닫는다.**
- Verified(**스윕이 결함 넷 — 찾던 건 하나였다**): 네 signal 어댑터 × 전 resource_type을 AST로
  훑고 **빠진 capability가 그 provider에서 resolve되는지**까지 물었다. ①`streaming-consumer`/
  `rebalance_consumer`가 **Azure만 없다**(3대1)는데 Azure는 **구현하고 있다**. 네 어댑터는 **같은
  커밋 `a22a283`에서 태어났고 Azure는 처음부터 빠져 있었다**(stale이 아니라 **쓰일 때부터 틀림**).
  ②③④`kubernetes-workload`/`rollback_release`는 **onprem만 추천**하고 셋은 구현했는데 안 한다 —
  ⚠️**1대3, 소수가 갖고 있다**. 롤백은 파괴적이라 **내가 정할 게 아니라** 알로리스트에 이유를
  달아 **사람 결정으로 남겼다.**
- Changed: Azure 추천에 `rebalance_consumer` 하나(+이유). ⚠️**Azure executor가 실행 없이
  resolved를 보고하는 열린 항목과 맞닿는다** — 클레임이 하나 늘지만 **라이브 변경은 없다**(no-op).
  그 항목을 고칠 이유이지, 구현을 못 쓰게 둘 이유는 아니다.
- Changed(가드 +6, `test_signal_capability_parity.py` 신규): 규칙은 **"추천 안 해도 되는 건 실행
  못 하는 것뿐"**. 알로리스트는 이유 없으면 못 넣고 ⚠️**현실과 어긋나면 red**. 공허 통과 방지도
  뒀다 — **AST가 아무것도 못 읽으면 나머지가 저절로 통과**한다(내가 그 함정에 빠졌다).
- Verified(**변이 4종 전부 red**): 고침 되돌리기 · 다른 provider에 새 구멍 심기 · 알로리스트 한
  줄 비우기(=실재하는 구멍을 덮고 있다) · 알로리스트 stale화. `make check` **2257 passed, 2 skipped**.
- Blockers: 없음. ⛔남은 정책 결정(`rollback_release`)은 `NEXT_PLAN`에 있다.
- Next: 08-19 이후 AMP 청구액 대조 · ⓒ(첫-매치 vs 점수제)는 **미측정**.

## 2026-08-17 — 검증을 세운 그 커밋이 같은 결함을 한 문 옆에 남겼다 (gate 2251)

- Status: 앞 증분(조건 검증)에 **ultrareview**를 돌렸다. 결함 하나(normal)와 죽은
  참조 하나(nit)가 나왔고 **둘 다 성립했다**. 재현해서 확인하고 고쳤다.
- Verified(**리뷰가 맞았다**): `steps: null`은 `_step_problems`가 **0 problems로 통과**
  시키는데, GCP/Azure walk가 `runbook.get("steps", [])`로 읽는다 — **기본값은 키가
  없을 때만** 쓰이므로 저장된 `None`이 그대로 나오고 `for step in None`이 **TypeError**.
  ⚠️**내가 "막겠다"고 주석에 적어 둔 바로 그 500을, 그 주석을 쓴 커밋이 만들었다.**
- Verified(**리뷰보다 넓었다 — 형제를 다시 셌다**): `steps`를 읽는 자리는 넷이고
  **AWS만 `or []`로 None-safe**였다 = **읽는 쪽의 provider 간 비대칭**(이 레포가 정한
  "진짜 결함" 기준). 리뷰가 지적한 둘 외에 **`CapabilityRunbook.from_dict`도 같이
  터진다**(실측). 넷째(`executor.py`)는 생산자가 `default_factory=list`라 도달 불가지만
  **홀수를 남기지 않으려고** 같이 고쳤다.
- Changed: 넷 다 `get("steps") or []` · `schema.py` 계약 도크스트링에 **null 허용**을
  명시(에러 메시지는 "list or null"인데 도크스트링은 `list[dict]`이라 **두 출처가
  달랐다**) · nit: `CONDITION_KEYS` 주석이 **없는 파일**을 가리키고 있었다(드리프트
  가드는 `test_store_runbook_validation.py` 안에 있다) → 실제 이름으로 고쳤다.
- Changed(가드 +4, `test_steps_reads_are_none_safe.py` 신규): 행동 셋(GCP·Azure 라이브
  경로 + `from_dict`) + **구조 하나** — `src` 추적 파일을 AST로 훑어 `get("steps", …)`
  형태를 금지한다. ⚠️**`glob`로 짰다가 터졌다**: `src/stacks/node_modules/`의 CDK 템플릿
  6개가 `%name.PascalCased%` 때문에 파싱 불가다 — 조용히 건너뛰면 진짜 reader를 놓치니
  **`git ls-files`로 스캔 면을 좁혔다**(레포가 이미 쓰는 방식).
- Verified(**변이 5종, 전부 red**): 네 고침을 하나씩 되돌리면 red(R1~R3는 2건씩,
  R4는 구조 가드만 — 그 경로에 행동 테스트가 없는 게 정직하다) · ⚠️**공허 통과 방지로
  위반을 일부러 심었더니**(R5) red = 스캔이 정말 파일을 열어 본다.
  `make check` **2251 passed, 2 skipped**(로컬 macOS·py3.13).
- Blockers: PR #42는 **병합 권한이 막혀** 열려 있다.
- Next: 08-19 이후 AMP 실제 청구액 대조.
