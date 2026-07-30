# 결정 5 브리프 — "배포 요청이 무엇으로 테넌트를 말하는가"

작성: 2026-07-30 · gate 1565 · 선행 = D36(귀속) · `6beebbc`(네임스페이스 출처)

> D36에서 **인가**만 떼어낸 항목이다. 질문은 "배포 경로에 `guard_scoped_action`을 태우려면
> 무엇으로 스코프하나"였다. **조사 결과 질문이 틀렸다.**

---

## 요약 (30초)

원래 계획은 "배포 요청이 테넌트를 말하게 한 뒤 인시던트 경로와 같은 가드를 태운다"였다.
그런데 **인시던트 경로의 그 가드는 프로덕션에서 한 번도 열린 적이 없다.**

`guard_scoped_action`은 `IncidentScope` 없이는 거부한다. 그 스코프를 만드는 유일한 생산자는
`resolve_incident_scope`이고, 그것은 인시던트의 `source_metadata["attested_approval"]`을 읽는다.
**그 키를 쓰는 프로덕션 코드가 없다.** `sign_approval`의 호출부는 테스트·스크립트 17곳뿐이고
`src/` 안에는 0이다. 브로커가 요구하는 `PLATFORM_CREDENTIAL_DIR`·`PLATFORM_APPROVAL_SIGNING_KEY`는
**어느 CDK 스택·Makefile·스크립트도 설정하지 않는다**(정의 파일 자신 외 참조 0).

라이브 관측(`docs/evidence/deploy-path-authorization.log`):

```
실제 Alertmanager 페이로드 → 실제 온프렘 시그널 어댑터 → NormalizedIncident
  source_metadata keys      : ['alertname','generator_url','labels','source_event']
  carries attested_approval : False
  resolve_incident_scope    → None   (executor.scope.absent)
  guard_scoped_action       → REFUSED (onprem_runner.no_scope)
```

즉 **두 경로가 서로 반대 방향으로 고장 나 있다:**

| | 가드 | 실제 신원 |
|---|---|---|
| 인시던트 (3 러너 + MCP) | 있다, 올바르다 — 그런데 **열 수 없다** | 라이브 시 **전부 거부** |
| 배포 (`local_deployer`) | **없다** | `kubernetes-admin` / `kubeadm:cluster-admins` = **cluster-admin** |

라이브 실측(kind `platform-agent`):

```
kubectl auth whoami → kubernetes-admin, groups [kubeadm:cluster-admins]
  can-i create deployments -A              : yes
  can-i delete namespaces -A               : yes
  can-i get secrets -A                     : yes
  can-i delete deployments -n kube-system  : yes
  can-i create clusterrolebindings         : yes
```

**그래서 결정 5는 "무엇으로 스코프하나"가 아니라 "어느 쪽을 먼저 세우나"다.**

---

## 확인된 사실 (코드 기준)

### F1. 스코프 생산자가 프로덕션에 없다 — 이번 조사의 새 발견

`grep -rn sign_approval src/` → `def sign_approval` 정의 한 줄뿐. 호출은 `tests/` 17곳.
`attested_approval`를 **쓰는** 코드는 0, **읽는** 코드는 `scope.py:253` 하나.
네 시그널 어댑터(aws/gcp/azure/onprem) 전부 `source_metadata`에 그 키를 넣지 않는다.

### F2. 브로커의 전제 조건도 배포되지 않는다

`TokenBroker.from_env`는 두 환경변수가 없으면 `ScopeError`로 fail-closed한다. 두 변수는
`scope.py` 안에서만 등장한다 — 스택도, Makefile도, `dev-up`도 설정하지 않는다. 따라서
`resolve_incident_scope`의 `except Exception`이 `executor.scope.unavailable`을 남기고 None을
돌려주는 경로가 **정상 경로**다.

### F3. 이게 여태 안 보인 이유: 라이브 모드가 기본 OFF다

`ONPREM_EXECUTOR_LIVE`(기본 `false`)가 아니면 러너는 로그만 찍고 가드에 **도달하지 않는다**.
그래서 배포 기본값에서는 아무것도 깨지지 않는다. **켜는 순간 모든 원격조치가 거부된다.**
방향은 안전하지만(fail-closed) "Phase 1a에서 강제 완료"라는 문서 표현은 **집행이 아니라
차단**을 가리키고 있었다. Phase 3의 라이브 증거도 `approval_id='APR-PHASE3-LIVE'` —
스크립트가 브로커를 **직접** 불러 만든 스코프다. 격리 자체는 진짜로 증명됐다(API 서버가
이웃 테넌트를 `Forbidden`으로 판정). 증명되지 않은 건 **그 스코프가 인시던트에서 나온다**는 것.

### F4. 배포 경로는 가드가 없고 신원이 cluster-admin이다

`OnPremClusterAdapter.deploy`는 `kubectl apply -f - --namespace <ns>` — `--kubeconfig`도
`--context`도 없다. 즉 ambient이고, 라이브 클러스터에서 그 ambient는 cluster-admin이다.
**인시던트 경로에서 제거한 바로 그 ambient 실행이 배포 경로에는 그대로 있다.**

### F5. 요청은 여전히 테넌트를 말하지 않는다 (D36의 제약이 그대로)

`DeployRequest` = `instruction/model/provider/environment`. 시스템 프롬프트는 namespace·tenant를
한 번도 언급하지 않는다. `6beebbc`로 **행**은 착지 네임스페이스를 적게 됐지만 그건 사후 기록이다.
모델이 아무것도 안 넘기면 `ServiceSpec`이 `default`로 해소하고, 그건 무테넌트다.

### F6. 라우터에 인증이 없다 — D36의 그 사실이 인가에도 걸린다, 단 다르게

D36은 "본문의 테넌트는 자진신고이므로 예산이 아니다"로 과금을 접었다. 인가에도 같은 사실이
적용되지만 **결론은 같지 않다**. 자진신고 테넌트는 **공격**을 막지 못한다(원하는 값을 쓰면 된다).
그러나 **오류**는 막는다 — LLM이 엉뚱한 네임스페이스를 고르는 것, 프롬프트 인젝션이 대상을
바꾸는 것, 회귀가 대상을 넓히는 것. 인시던트 경로의 attested 모델은 공격을 막는 설계이고,
배포 경로에서 오늘 얻을 수 있는 최대치는 **오류 방어**다. 그 둘을 같은 단어로 부르면 안 된다.

### F7. 반대로, 신원을 좁히는 건 요청이 테넌트를 말하지 않아도 가능하다

`kubectl apply`가 cluster-admin으로 도는 것은 **요청이 무엇을 말하든 상관없다.** 배포용
kubeconfig를 테넌트-무관하게 한 단계만 좁혀도(예: `namespaces`·`secrets`·`clusterrolebindings`
제거) 반경은 줄어든다. **이 축은 결정 5의 답을 기다리지 않는다.**

---

## 선택지

### A. 인시던트 경로를 먼저 실제로 열 수 있게 만든다 (생산자를 세운다)

승인/파킹 시점에 `sign_approval`을 불러 `source_metadata["attested_approval"]`에 실어보내고,
두 환경변수를 배포 대상에 넣는다.
- **얻는 것**: "blast radius = 1 tenant/env"가 문서 주장에서 **동작하는 사실**이 된다.
  현재 라이브를 켜면 전부 거부되는 상태도 해소된다.
- **비용**: 승인 경로(AWS Step Functions + SQS callback)와 온프렘 웹훅 양쪽에 서명 지점을 심어야
  한다. 서명키 custody·rotation은 이미 NEXT_PLAN 2차 잔여로 열려 있다.
- **주의**: 이건 **배포 경로 인가와 무관**하다. 인시던트 경로를 정직하게 만드는 일이다.

### B. 배포 신원을 좁힌다 (요청이 테넌트를 말하지 않아도 된다)

배포에 전용 kubeconfig/SA를 주고 cluster-admin을 뗀다. `naming_prefix` 밖 네임스페이스,
`secrets`, `namespaces`, RBAC 객체를 제거.
- **얻는 것**: 반경이 **오늘** 줄어든다. 집행자는 API 서버 — 우리 코드가 아니라(레포의 기존
  원칙 D31: "가드는 advisory, RBAC가 진실").
- **비용**: 배포가 실제로 필요한 동작(네임스페이스 생성? `setup_tenancy`가 하는 일과의 경계)을
  먼저 열거해야 한다. 너무 좁히면 조용히 `Forbidden`으로 깨지는데, **그게 옳은 방향의 깨짐**이다.
- **한계**: 테넌트 간 구분은 못 한다. "플랫폼 배포자"라는 한 신원이 될 뿐.

### C. 요청이 테넌트를 선언한다 — `DeployRequest.tenant/env` + 가드

D36 브리프의 선택지 A와 같은 모양. 대시보드가 신원/grant를 전달하고, 경계가 레지스트리와
대조한 뒤 스코프를 민팅한다.
- **얻는 것**: 배포도 인시던트와 같은 가드를 탄다.
- **비용**: 라우터 인증이 선행(F6). 인증 없이 켜면 **오류 방어일 뿐인데 공격 방어처럼 읽히는**
  카드가 하나 더 생긴다 — 이 레포가 반복해서 지운 결함(집행하지 않는 것을 광고하지 말 것).

### D. 프롬프트/도구 시그니처가 테넌트를 요구한다

`deploy_service(tenant, env, ...)`를 필수로 만들고 프롬프트가 물어보게 한다.
- **얻는 것**: 값이 **추론의 입력**이 되어 사후 기록이 아니라 사전 제약이 된다.
- **비용**: 자연어 UX가 바뀐다("orders-api v1.4.2 배포해줘"가 되묻기로 이어진다). 그리고
  **LLM이 채우는 값을 인가에 쓰는 것**은 자진신고보다 약하다 — 모델은 그럴듯한 값을 만든다.
  이 레포가 방금 두 번(D36 tier, `6beebbc` namespace) 지운 것이 바로 "그럴듯한 기본값"이다.

---

## 추천

**B를 먼저, 단독으로. 그다음 A. C·D는 라우터 인증까지 보류.**

근거 세 가지:

1. **B만이 답을 기다리지 않는다.** cluster-admin으로 `kubectl apply`가 도는 것은 결정 5의
   어느 답과도 무관하게 지금 참이고, 좁히면 지금 줄어든다. 나머지 셋은 전부 다른 것이 선행이다
   (A=서명 지점, C=라우터 인증, D=UX 변경 + 여전히 모델이 채운 값).

2. **A는 "완결"이라고 적힌 것을 실제로 완결시킨다.** 지금 문서의 최우선 불변식
   ("blast radius=1 tenant/env — 자격증명이 경계 — Phase 1a에서 강제 완료")은 **집행이 아니라
   차단**을 서술하고 있다. 라이브를 켜면 전부 거부된다는 사실이 그 증거다. 이건 새 기능이
   아니라 **문서가 이미 주장하는 것을 참으로 만드는 일**이고, 우선순위가 C·D보다 높다.

3. **C·D를 먼저 하면 이 레포가 반복해서 지운 결함을 만든다.** 인증 없는 자진신고 테넌트로
   가드를 세우면 카드·문서·대시보드에 "테넌트 스코프됨"이 하나 더 붙는데, 실제로는 오류
   방어다. D31/D24가 남긴 원칙 — **집행하지 않는 것을 광고하지 말 것** — 에 정면으로 걸린다.
   오류 방어가 무가치하다는 말이 아니다. **오류 방어라고 부르면** 괜찮다.

### 반대 논거 (기록용)

- "B는 테넌트를 구분하지 못하니 반쪽이다." → 맞다. 다만 반경 축소는 구분과 독립적이고,
  cluster-admin에서 한 단계 내려오는 것이 구분보다 크다(오늘 `get secrets -A`가 yes다).
- "A는 배포 인가와 무관한데 왜 결정 5에 들어오나." → 결정 5가 "인시던트 경로와 같은 가드를
  태운다"를 전제했기 때문이다. 그 전제가 성립하지 않는다는 것이 이 브리프의 핵심이고,
  전제를 세우는 일이 A다.

---

## 결정하면 내가 할 일

- **B**: 배포용 SA/Role을 `render_tenancy.py` 계열로 렌더 → `deploy`/`validate`/`rollback`
  어댑터가 `--kubeconfig`를 받게 배선 → **라이브에서 반증**(`secrets` 읽기가 `Forbidden`이
  되는지, 정상 배포는 계속 되는지). 가드는 **파생**: 어댑터가 만드는 argv를 파싱해
  `--kubeconfig` 부재를 실패로 만든다(D37의 교훈 — 열거하면 다음 어댑터를 놓친다).
- **A**: 승인 파킹 지점 2곳(SFN 콜백 · 온프렘 웹훅)에 `sign_approval` → `source_metadata`,
  두 환경변수를 `dev-up`과 스택에 배선 → **라이브에서 원격조치가 실제로 실행되는지** 확인
  (지금은 거부된다는 것부터가 관측 대상).
- **C/D**: 라우터 인증 결정 이후.

---

## 이번 조사에서 같이 나온 것 (결정과 별개)

- **`STATUS` 최우선 불변식 표현을 고쳐야 한다** — "Phase 1a에서 강제 완료"는 스코프가
  민팅될 때만 참이고, 프로덕션에서 민팅되지 않는다. 이건 결정이 아니라 **문서 정직성**이라
  결정과 무관하게 반영한다.
- **MCP 게이트웨이도 같은 모양** — `MCPServer(scope=...)`를 프로덕션에서 구성하는 곳이 없어
  항상 무스코프 읽기 경로로 간다(= 기존 결정 2). 결정 2와 결정 5는 **같은 뿌리**였다:
  스코프 생산자가 없다.
- **`sign_approval`이 테스트에서만 불린다는 사실을 잡는 가드가 없다** — 17개 테스트가 전부
  자기가 만든 attested 레코드로 통과한다. M13의 "픽스처는 실제 입력에서" 교훈의 정확한 재발:
  생산자를 테스트가 대신하고 있으면 생산자 부재는 영원히 초록이다.
