# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-29

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-29 — k3s는 NetworkPolicy를 집행한다, 그런데 게이트는 안 열었다 (gate 1544 유지)

- Status: 계획의 **비-결정 항목 마지막**(⑥ k3s 검증기 재실행)을 실행했다. flannel 집행은
  kindnet에서 **전이되지 않으므로** 기판별 실측이 필요했던 항목.
- Changed(코드 경로 무변경): `tenancy.py`의 기판 주석에 측정 결과와 **왜 아직 안 넣는지**를
  기록 · 부작용 프로브를 `scripts/probe_netpol_side_effects.sh`로 남김.
- Verified(라이브, k3s v1.31.4 + flannel + 내장 kube-router): ①`verify_netpol_enforcement.py`
  → **ENFORCED**(컨트롤 유효 — 무정책 시 B→A 도달을 **먼저** 확인) ②default-deny **아래에서
  태어난** 파드의 readinessProbe가 Ready → **노드발 프로브는 차단되지 않는다**(어떤
  namespaceSelector로도 못 잡는 트래픽이라 여기서 막혔으면 며칠 뒤 앱 회귀로 보였을 것)
  ③같은 정책에서 DNS 정상(`10.43.0.1 kubernetes.default`) → ingress 전용 정책이 egress를
  안 건드림. `make check` 1544 유지. 증거 `docs/evidence/k3s-netpol-enforcement.log`.
- Blockers: **게이트(`PROVEN_ENFORCING_SUBSTRATES`)는 열지 않았다** — 3종이 증명한 건
  "기판이 집행할 수 있고 집행해도 안 깨진다"까지고, **이 집합이 실제로 licensing하는 주장**
  (우리 정책 shape이 같은 테넌트 통과·다른 테넌트 차단)은 미검증이다. 그걸 보는
  `verify_tenant_isolation.py`가 **k3s-lab에 피어 테넌트가 없어 못 돈다**(acme/prod가 유일한 env).
  globex/prod를 만들면 실 네임스페이스·쿼터·애드온이 프로비저닝되므로 **테스트를 돌리려고
  인프라를 지어내지 않았다** → 결정 4로 올림.
- 품질 메모: 첫 실행이 **INCONCLUSIVE**("server pod never became Ready")였고 그대로 기록했다 —
  원인은 VM의 콜드 이미지 캐시(직후 `crictl pull`이 "up to date")였고, 두 실행의 차이는
  클러스터가 아니라 캐시였다. 검증기 자신의 규율대로 **컨트롤이 안 선 실험은 통과가 아니다**.
  그리고 kind용으로 확인해둔 "프로브·DNS는 안 깨진다"를 k3s에 **전이시키지 않고 다시 쟀다** —
  기판이 다르면 CNI도 정책 컨트롤러도 다르다.
- Next: 결정 4(위) 외 잔여 없음. 나머지는 전부 기존 결정 3건 + 승인 1건.

## 2026-07-29 — 리포트 창을 시계가 아니라 보관 필드로 재고 있었다 (gate 1533→1544)

- Status: 읽기 모델 건이 연 **TTL 실마리**를 따라갔다. 거기서 `ttl` 커버리지가 writer마다
  다르다는 걸 알았으니 다음 질문은 **누가 `ttl`을 읽는가** — 두 리포트 창이 그걸 **시각처럼**
  읽고 있었다. M13의 열두 번째.
- Changed(`5988d6b`): `ttl`은 **쓴 시각 + 90일**이다. ①**일일 SLO**: 필터가
  `ttl >= now - 24h`인데 ttl은 항상 미래 90일이고 cutoff는 과거라 **만료 안 된 모든 행에 대해
  참** — "최근 24시간"이 보관 기간 전체였다(바로 다음 줄의 파이썬측 재검사도 같은 두 값이라
  항상 거짓). ②**주간 온콜**: `ttl - 90일`로 역산 — 보관 상수를 바꾸면 리포트 전체가 조용히
  밀리고, **`ttl`이 없는 행은 `now`로 기본값이 잡혀 90일 과거로 떨어져 모든 주간 리포트에서
  소리 없이 빠졌다**(`created_at`에 나이가 분명히 적혀 있는데도). 둘 다 모든 writer가 무조건
  쓰는 `created_at`으로 배치. `ttl`은 레거시 행 폴백으로만 남기되(빼면 리포트가 조용히 줄어든다)
  **writer의 `ttl` 식을 AST로 읽어 상수 일치를 강제**했다. 두 필드로도 못 구하면 **제외**(추측 금지).
- Verified: `make check` **1544**(+11). **BEFORE/AFTER 실측**(90일치 90행): 필터 통과
  **90 → 2**, 경계 포함 기대값 2와 일치. 반증 5건 개별 되돌림 전부 red, 복원 시 11건 통과.
  증거 `docs/evidence/report-windows.log`.
- Blockers: **라이브 미실행** — 둘 다 EventBridge 스케줄 Lambda 경로라 실 AWS가 필요하다
  (이미 열려 있는 승인 항목). "프로덕션에서 과대 집계돼 왔다"는 **코드·writer 포맷에서의 추론**
  이지 발송된 리포트의 관측이 아니다.
- 품질 메모: **내 가드 둘이 먼저 틀렸고 둘 다 이 마일스톤의 단골 실패 양식**이었다.
  ①`failed_requests`(원시 카운트)를 `total_requests`(×100)로 오독해 `// 100`을 넣었더니
  `90 // 100 = 0`이라 **수정 전 코드에서 통과**했다 — 형제 테스트가 같은 오독으로 깨져서야
  드러났다. ②되돌림 3이 초록이었다: 픽스처의 `ttl`과 `created_at`이 **일관돼서 두 구현이 모든
  행에 대해 같은 답**을 냈다 — 테스트가 수정과 버그를 구별 못 했다. **갈리는 경우**(created_at은
  있고 ttl 없음 = 이 수정이 겨냥한 바로 그 조용한 누락 / ttl이 다른 보관 기간)를 추가했다.
  **산문으로만 주장하고 코드로 단언하지 않은 게 있으면 그건 아직 안 고친 것이다.**
- Next(같은 세션에 확인 완료): Azure/GCP `ttl` 식 차이는 **시맨틱 차이가 맞았고**(Cosmos는
  상대 초, 그래서 Azure가 옳다) 그런데 **둘 다 집행되지 않는다** — Cosmos 컨테이너는
  `durable_functions.py`가 `--ttl` 없이 만들어 항목 `ttl`이 무효이고, Firestore는 TTL 정책이
  IaC 어디에도 없으며 필드도 **Timestamp가 아닌 정수**라 정책을 붙여도 안 걸린다. 즉 두
  스토어의 인시던트 문서는 **무기한 남는다**. 주석만 사실에 맞추고(집행 안 하는 걸 광고하지
  않는다) **동작은 안 바꿨다** — 보관을 켜는 건 실 데이터 삭제라 승인 사항이고 읽는 쪽도 없다.
  → `STATUS` Open Risk 2 · `NEXT_PLAN`.

## 2026-07-29 — 읽기 모델 문서가 존재 내내 어긋나 있었다 (gate 1528→1533)

- Status: 스윕을 **대시보드 TS 쪽**으로 확장(기존 스윕은 `src/agents`만 본다). M13의 열한 번째
  이자 **한 층 위**: 필드가 아니라 **선언 자체를 아무도 안 읽는** 경우.
- Changed(`61ee2f4`): `activity-model.ts`는 **아무도 import하지 않는다** — 그래서 어긋나도
  아무것도 안 깨졌고, 실제로 양방향으로 어긋났다. 아무도 안 쓰는 `duration_ms`·`error_message`를
  선언하면서 **배포 상세 페이지가 딛고 선 `trace`·`cost_metrics`·`deployment_id`는 없었다**.
  거짓 주장 둘: ①`ttl` 필수 + "30일 보관"이지만 `ttl`을 쓰는 건 `activity_writer`뿐이고
  실제 대부분을 쓰는 `deploy_recorder`는 안 써서 **그 행들은 만료되지 않는다** ②`GSI1`도
  절반만 채워지고 **아무도 쿼리하지 않는다** — 이 문서를 보고 provider 스코프 쿼리를 짰다면
  에이전트가 쓴 행을 전부 빠뜨린 짧은 목록을 **조용히** 받았을 것이다. writer 계열이 둘인데
  어느 쪽도 상위집합이 아니고 선언은 **둘 다와** 불일치. core/optional 분리 + 접근 패턴을
  USED/NOT USED/NOT WRITTEN으로 표기 + `make*Record` 생성자 4개 제거(배선된 적 없는 TS 쪽
  쓰기 경로 = 갈라질 일만 남은 두 번째 진실 소스).
- Verified: `make check` **1533**(+5) · tsc 클린 · `next build` 성공. 반증 5건(**원본 파일
  포함** → 5개 중 3개 red) 전부 red, 복원 시 5건 통과.
  증거 `docs/evidence/activity-read-model-drift.log`. 런타임 동작 변화 없음(importer가 0인 게 요점).
- Blockers: 없음.
- 품질 메모: 왜 안 잡혔나 — `test_activity_model_schema`가 **부분문자열 존재**만 봤다
  (`'GSI1PK:' in content`, `"TTL_30_DAYS" in content`). 키워드는 **모양을 못 본다** — 이
  마일스톤이 이미 적어둔 안티패턴이 **그 파일을 지키는 테스트에** 있었다. writer AST에서
  파생하는 가드로 교체. **그리고 내 가드도 처음엔 같은 병이었다**: `re.search`라 두 선언 중
  하나만 옵셔널이면 통과해서 되돌림 3이 초록으로 나왔다 — `any`를 쓸 자리에 `all`이 필요했다.
  전 선언 지점을 요구하도록 조인 뒤에야 빨개졌다.
- Next: TS 쪽 후보 중 `ApprovalRequest.request_kind/subject/summary`는 **이미 렌더되는
  `alarm_name`/`root_cause`의 중복**(손실 아님, 사문화). TS 후보 47건을 마저 읽은 결과
  **데이터 손실은 이 건 하나뿐**이었고 나머지는 죽은 선언 → NEXT_PLAN에 후보로 기록(고치지 않음).
