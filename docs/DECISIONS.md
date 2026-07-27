# DECISIONS — platform-agent

최종 갱신: 2026-07-28

> 되돌리기 어려운 결정만. 형식: **Decision / Reason / Impact**. 최신이 위.

> **Future Reference (차용 후보, 결정 아님):**
> - **enterprise-ai-governance-dashboard** (외부 레포) — 2-Pass Fact NL→SQL 챗봇 + SQL self-heal 루프 + LLM SKU 그룹핑 + 최소권한 Cloud Run SA. 대시보드 챗봇/FinOps 확장 시 검토. 상세 → `docs/reference/enterprise-ai-governance-dashboard.md`. (검토 2026-07-13)
> - **GitAIOps 실습서(Notiflex)** (외부 학습 레포) — Rollouts **AnalysisTemplate 메트릭 자동판정**(우리 무기한 pause 게이트의 미완점) · **OTel→Tempo로 4-step 파이프라인 자체 트레이싱** · 런북 **사전확인/사후검증 3단**(우리 `RunbookStep`엔 없음) · **allow/ask/deny 권한통제** · **Sync Wave**. 안티패턴=Kafka·멀티 노드풀·GKE 종속 시크릿·`--dangerously-skip-permissions`. 상세 → `docs/reference/gitaiops-notiflex-book.md`. (검토 2026-07-25)

---

## D32 — GitOps 관리 워크로드의 자동 롤백은 **거부까지**다 (selfHeal pause 안 함)

- **Decision:** reconciler가 소유한 워크로드에 대한 롤백은 거부하고 사람에게 넘긴다.
  selfHeal을 일시 중지하는 경로는 **채택하지 않는다**.
- **Reason:** 라이브로 확인한 구조적 충돌이다. 소유 Application은 `argocd` 네임스페이스에
  있고, Phase 1a/3①의 테넌트 스코프 자격증명은 그것을 **읽지도 못한다**(`Forbidden` 실측).
  pause를 하려면 (a) 러너에게 크로스-네임스페이스 자격증명을 주거나 — 최우선 불변식을
  되돌리는 일이다 — (b) Application의 `syncPolicy` 한 필드만 만지는 제2 자격증명 클래스를
  신설해야 한다. `apps-in-any-namespace`도 비활성이라 테넌트 로컬 우회로가 없다.
  설계의 권장안(registry write-back)은 git 쓰기라 k8s 경계를 안 건드리지만 **Phase 5**다.
  즉 계획 안에서 Phase 3② 후반을 옳게 닫을 방법이 없다 — 계획 자체의 순서 충돌.
- **Impact:** 거부는 **롤백을 되게 만들지 않는다.** 조용한 되돌림을 시끄러운 거부로 바꿀
  뿐이다(라이브: out-of-band 변경이 **10초 만에** selfHeal에 되돌려졌다 — undo는 0을
  반환하고 `resolved=True`가 기록된 뒤 깨진 버전이 돌아온다). 되돌리는 액션만 막고
  restart·scale은 통과시킨다 — 거기까지 막으면 멀쩡한 조치가 깨지고 가드는 꺼진다.
  Phase 5가 레지스트리 쓰기를 열면 이 결정을 재검토한다.

## D31 — 스코프 가드는 한 곳에 있고, GCP/Azure는 "네임스페이스만" 좁힌다고 명시한다

- **Decision:** 라이브 실행의 fail-closed 게이트는 `platform/scope.py`의
  `guard_scoped_action` **하나**이고 세 러너가 그것을 호출한다(러너별 재구현 금지).
  그리고 GCP/Azure 경로에 대해서는 **"자격증명이 경계"라고 말하지 않는다** — 스코프는
  액션이 건드릴 네임스페이스만 좁히고, 토큰 자체는 여전히 GCP=프로젝트 전역 신원,
  Azure=ARM이 내주는 **cluster-admin kubeconfig**다. 자격증명 자체가 경계인 것은
  **온프렘뿐**이며, 클라우드 자격증명의 테넌트 바인딩은 Phase 4(billable)로 미룬다.
- **Reason:** (1) 가드를 엔진마다 복제하면 세 번째 엔진이 빠뜨린다 — capability scope(D27)에서
  이미 치른 값이고, Phase 1a는 실제로 온프렘에만 가드를 두어 gcp/azure가 무-스코프로 남았다.
  (2) 부분 보증을 전체 보증처럼 적으면 나중에 아무도 그 차이를 복원하지 못한다. Phase 1a의
  DoD가 "Forbidden **또는** 자격증명 부재"라고 적혀 있었기 때문에, 바인딩 대상 SA가 아예
  없어서 RBAC 팔이 한 번도 행사되지 않았는데도 통과로 기록될 수 있었다.
- **Impact:** 네 번째 클라우드를 추가할 때 스코프 전달을 빠뜨리면 구조 가드
  (`test_every_provider_branch_is_covered`)가 게이트를 깬다. 문서·아티클에서 GCP/Azure를
  두고 "테넌트별 자격증명"이라고 쓰면 **과대주장**이다 → `STATUS` Open Risks 7.
  `render_rbac`는 바인딩 대상 ServiceAccount를 반드시 함께 렌더한다(없는 subject로의
  바인딩을 k8s가 조용히 받아들이기 때문).

## D30 — 에이전트가 클러스터에 쓰는 범위는 테넌트 스코프까지다

- **Decision:** 자연어 도구(`setup_tenancy`·`install_tenant_addons`)는 **테넌트 소유 객체만**
  적용한다. 공유 플랫폼 스택 9개(ArgoCD·Capsule·kube-prometheus·Loki·Tempo·Rollouts 등)는
  **Terraform이 계속 소유**하고 에이전트는 건드리지 않는다. 그리고 도구는 kubectl 컨텍스트가
  레지스트리의 대상 클러스터와 다르면 **아무것도 쓰지 않고 거부**한다.
- **Reason:** 에이전트가 TF state 위에 helm을 덮으면 한 객체에 주인이 둘 생기고, **어느 쪽
  기록에도 그렇게 적히지 않는다**(이 레포가 반복해서 당한 "에러 없이 안 읽히는" 실패의 족보).
  컨텍스트 가드는 자연어 특유의 제약 때문이다 — CLI는 `make demo-baseline`처럼 컨텍스트를
  출력해 사람이 읽게 할 수 있지만, **문장은 되물을 기회를 주지 않는다**. kind에서는 무엇을 해도
  성공하므로, 이 검사가 없으면 가장 나쁜 모양(성공처럼 보이는 실패)으로 틀린다.
- **Impact:** "클러스터 전체를 자연어로 세운다"는 시연은 **하지 않는다**(공유 스택은 화면 밖
  전제). 대신 테넌트 온보딩이 17.6초로 닫힌다. Phase 4(managed 어댑터)에서 이 경계를 다시
  검토하되, 넓히려면 소유권 모델을 먼저 정해야 한다.

## D29 — 검증은 문서가 아니라 훅으로 강제한다

- **Decision / Reason:** "멀티파일 변경 후 `make check`"는 `NEXT_PLAN`에 글로만 있었고, 그건
  기억한 만큼만 지켜졌다는 뜻이다. Stop 훅이 게이트를 돌리고 PostToolUse 훅이 대시보드
  `tsc`를 돌린다. 둘 다 **등록 전에 양방향 검증**(정상 exit 0 / 일부러 만든 실패 exit 2).
- **Impact:** 게이트는 **소스가 바뀐 경우만** 돌고(문서 턴 비용 0, 클린 트리는 직전 커밋이
  이미 통과), `async+asyncRewake`라 통과하면 조용하고 실패할 때만 깨운다 — 안 그러면 매 턴
  4분을 세금으로 낸다. `next build`와 라이브 검증은 의도적으로 제외했다(전자는 tsc와 대부분
  겹치고, 후자는 클러스터 상태를 바꾸므로 자동 실행이 위험하다). **훅이 잡는 건 싼 절반이다** —
  같은 세션에 `tsc`가 초록인 채로 런타임 TypeError가 났다.

## D28 — 대시보드는 클러스터를 조회하지 않는다. 격리 상태도 push로 온다

- **Decision / Reason:** 테넌트 격리 4축·쿼터·티어를 화면에 올리면서 대시보드가 클러스터를
  직접 읽고 싶은 유혹이 생겼다. 그러면 D26(허브는 스포크 read 자격증명 0)이 즉시 깨진다.
  그래서 `TenancyPosture`를 **기존 push 리포트에 실어** 스포크가 자기 클러스터만 읽고
  보내게 했다. 대시보드는 허브만 폴링한다.
- **Impact:** 화면에 새 사실을 올리려면 수집기→리포트→허브→UI 네 곳을 지나야 한다(실제로
  푸셔만 재기동했을 때 허브가 모르는 필드를 버렸다). 대가로 관측 범위가 넓어져도 자격증명
  집중이 생기지 않는다. 파생 규율 둘: 축은 **3-state**(True/False/**None=확인 못 함** —
  못 읽은 걸 "격리 없음"으로 칠하면 진짜 침해와 같은 소동이고 초록으로 칠하면 더 나쁘다),
  커버리지는 **ALL 판정**(네임스페이스 하나가 안 덮이면 그 하나가 곧 노출이다).
  그리고 push로 들어오는 필드는 **항상 optional + 폴백** — 롤링 업그레이드 중 허브는 두
  버전의 리포트를 동시에 서빙하고, 구버전 페이로드가 실제로 페이지를 죽였다.

## D27 — capability에는 **scope 축**이 있고, 클러스터 싱글턴은 테넌트별로 렌더하지 않는다

- **Decision / Reason:** 카탈로그의 capability마다 `scope: cluster|namespace`를 선언하고,
  delivery **계약**(어댑터가 아니라)이 클러스터 스코프 capability의 테넌트별 렌더를 거부한다.
  라이브가 근거다 — 어댑터가 렌더한 per-tenant Application이 `--namespaced` 없는
  argo-rollouts를 ClusterRoleBinding과 함께 설치해 기존 컨트롤러와 **같은 Rollout을 둘이
  조정**했고, 에러도 로그도 없이 Application은 Synced/Healthy였다. cluster scope에서
  테넌트별인 것은 **인스턴스**(Prometheus CR·Rollout)이지 오퍼레이터/CRD가 아니다.
- **Impact:** 가드가 계약에 있으므로 세 번째 엔진이 빠뜨릴 수 없다(ordering 원시형과 같은
  이유로 중앙화). 조용한 skip이 아니라 **예외** — skip은 공유 인프라만 빼고 설치해 부재가
  전달 지연과 구분되지 않는다. 수집기 쪽 대응도 따라온다: 공유 설치물은 테넌트의 sync 축이
  아니므로 `applicable=false`이고, 안 보이면 MISSING이 아니라 **UNKNOWN**이다(거짓 장애를
  테넌트 수만큼 만드는 것은 진짜 장애를 숨기는 것만큼 나쁘다). 미선언 scope는 cluster로
  fail-safe하되 **로드를 막지는 않는다** — 처음엔 검증 오류로 올렸다가 fail-closed 로더가
  구 카탈로그 전부를 거부해 게이트가 27개 깨졌다. 부재는 공백이라 리포팅하고, 오값은
  주장이라 거부한다.

## D26 — 상태 수집은 **push 전용**, 신원은 서명을 검증한 키, 침묵은 UNKNOWN

- **Decision / Reason:** 허브가 클러스터를 폴링하지 않는다. 폴링하려면 허브가 N개 클러스터
  자격증명을 **보유**해야 하고, 그건 Phase 1a가 없앤 크로스테넌트 도달범위를 컨트롤플레인에
  되돌려주는 일이다. 각 클러스터의 에이전트가 자기만 읽고 push하며, 허브에는 스포크로 나가는
  코드 경로 자체가 없다(구조 테스트로 고정).
- **Impact:** 신뢰 문제가 뒤집히므로 세 가지가 따라온다. ①리포트가 주장하는 신원의 키로만
  검증한다(acme를 사칭하려면 acme의 키) — D24와 같은 규율. ②리포팅도 **쓰기**라, 서명자
  스코프 밖 row가 섞이면 리포트를 거부한다(blast radius 불변식은 read 경로에도 적용된다).
  ③push 모델의 고장은 "죽은 에이전트"이고 무소식의 기본 해석은 "변화 없음"이므로, 만료된
  리포트는 **삭제가 아니라 UNKNOWN 강등**이다 — 목록에서 사라지면 폐기된 env로 읽힌다.
  신선도는 허브의 **수신 시각** 기준(스포크 시계 오류·리플레이 방어).

## D25 — 데이터플레인 격리는 **레지스트리에서 렌더**하고, 집행이 **증명된 기판에만** 건다

- **Decision / Reason:** 테넌트 NetworkPolicy를 Helm 차트(tenants×envs×capabilities 손수 관리
  목록)에서 렌더하던 것을 폐기하고, 네임스페이스를 렌더하는 같은 호출에서 렌더한다. 차트는
  16개를 렌더하는데 레지스트리 구독은 6개였고, 그 차트를 설치하는 `helm_release`가 아예 없었다
  — 정합 테스트는 부분집합 단언이라 내내 초록이었다. 이제 정책 집합=네임스페이스 집합이
  검사 결과가 아니라 **구성상 동일**하다.
- **Impact:** 기판별로 `scripts/verify_netpol_enforcement.py`가 ENFORCED를 낸 곳에만 렌더한다
  (`PROVEN_ENFORCING_SUBSTRATES`). 미검증 기판은 0개 렌더 + exit 1로 신고 —
  **아무것도 안 렌더하면 정직하게 안전하지 않고, 집행 안 되는 정책을 렌더하면 부정직하게
  안전하다.** 감사에서 조용히 살아남는 쪽은 후자다. 테넌트 시맨틱(same 통과/cross 차단)은
  CNI 집행 프로브와 **다른 질문**이라 `verify_tenant_isolation.py`가 따로 답한다.

## D24 — 릴리스 게이트는 호출자의 **주장**이 아니라 **신원**을 받고, 신호는 스스로 관측한다

- **Decision / Reason:** canary AnalysisTemplate이 `CanaryUnderJudgement` firing 알럿을 **합성**해
  보내던 것을 폐기하고, `{"canary":{namespace, podPrefix}}`만 보낸 뒤 게이트가 Alertmanager를 직접
  조회한다. 합성 알럿은 그 자체가 "문제가 있다"는 주장이라 analyzer가 당연히 문제를 찾았고(라이브에서
  정상 canary가 confidence 0.80으로 `fail`), 판정 규칙 "신호 없음 → pass"가 **도달 불가능**이었다.
  게이트가 판정할 신호를 자기가 만들고 있었다.
- **Impact:** `None`(알럿 소스 없음/도달 불가)과 `[]`(봤는데 조용함)을 엄격히 구분 — 전자는 `unknown`
  (차단), 후자만 `pass`. **관측 안 된 canary는 조용한 canary가 아니다.** 더불어 게이트는 자기가 읽는
  알럿보다 빠를 수 없으므로, 차트가 canary 시간 스케일 룰(`for: 30s`)을 동봉한다 — kps 기본 파드 룰은
  `for: 15m`이라 2~3분 사는 canary엔 영영 발화하지 않아 크래시 중인 canary도 통과시킨다.

## D23 — 파드 보안은 **기본 ON**, 공급망 서명은 **다이제스트** 기준

- **Decision / Reason:** PSS `restricted`(runAsNonRoot·seccomp·capabilities drop)를 차트 기본값으로
  켠다. 다른 옵트인들과 달리 여기서 OFF는 중립이 아니라, 네임스페이스에 `enforce: restricted` 라벨이
  붙는 순간 롤아웃이 거부되기 시작하는 상태다(= 원인과 증상이 멀어지는 실패). 이를 위해 이미지도
  `USER 10001`로 바꿨다 — 차트가 runAsUser로 덮어써서 맞추는 건 이미지가 규격을 못 지킨다는 뜻이다.
- **Impact:** 차트 `securityContext.runAsUser`와 Dockerfile `USER`가 어긋나면 런타임(PVC 쓰기)에서만
  드러나므로 가드로 고정. Cosign 서명은 **태그가 아니라 다이제스트**에 붙는다(라이브로 확인: 같은
  다이제스트의 미서명 태그도 통과, 다른 이미지를 같은 태그로 밀면 실패) → 차트 `image.digest`가 태그보다
  우선한다. **어드미션 집행은 도입하지 않음** — policy controller는 새 클러스터 의존성이고, 지금 있는
  것은 CI/사람용 검증 게이트일 뿐임을 문서에 명시(보증을 과대 해석하지 않기 위해).

## D22 — billable 클라우드 명령은 권한 3단으로 게이팅 + 과금 가드는 2중(로컬 TTL 워치독 ⊕ 인벤토리 스위퍼)

- **Decision:** (1) `.claude/settings.local.json`에서 `Bash(gcloud:*)`·`Bash(aws:*)`·`Bash(az:*)` **포괄 allow를 폐기**하고 조회 동사만 allow(104건), billable 생성/삭제·`terraform apply|destroy`·`helm install|upgrade`는 `ask`(30건). (2) 과금 가드를 두 층으로 둔다 — **로컬 TTL 워치독**(`scripts/provision_gke_live.py`: try/finally + 시그널 + create 이전 무장 detached 프로세스)은 *생성 이후*를, **고아 클러스터 스위퍼**(`orphan_sweeper.py` + `make sweep-orphans`)는 *머신이 죽은 이후*를 담당. 스위퍼는 **보고만** 하고 삭제 명령은 출력만(D5 준수, 삭제 권한 불요).
- **Reason:** D16이 "overnight 무인 루프에서 클라우드 변경이 자동 허용되면 billable=사용자 게이트 설계가 깨진다"고 못박았는데, **포괄 allow가 그 결론을 로컬 설정에서 우회**하고 있었다 — `gcloud container clusters create`가 승인 없이 실행 가능했고 이것이 06-07·06-24(~9h 방치)·07-06·07-14 GKE 생성의 경로다. 워치독만으로는 부족한 이유: 세 층 전부 **이 머신에서** 돌아 머신이 자면/죽으면 같이 죽는다. 스위퍼는 프로세스 생존을 신뢰하는 대신 매 실행마다 클라우드 인벤토리에서 고아 여부를 **재도출**하므로 며칠 뒤 실행해도 올바른 판정.
- **Impact:** 미래 세션은 포괄 `gcloud:*`류를 되살리지 말 것(D16 우회 재발). 조회 동사가 부족해 오버나이트 루프가 막히면 **동사 단위로만** allow 추가. 스위퍼는 활성 gcloud 프로젝트만 훑으므로 `GCP_PROJECT`로 **과금 프로젝트를 명시**해야 함(라이브 실행 중 활성 프로젝트가 공부용이라 정작 과금 프로젝트를 안 훑는 함정을 발견 — Makefile 주석에 명기). `--json`의 `cluster_count`가 "0건 클린"과 "조용한 실패"를 구분하는 신호.

## D21 — 라이브 미검증 보안·자동화 기능은 **기본 OFF**, 켜는 조건은 경험적 검증기 통과

- **Decision:** 동작을 라이브로 증명하지 못한 보안/자동화 기능은 기본값을 OFF로 두고, 켜는 조건을 **문서가 아니라 실행 가능한 검증기**로 둔다. 적용 2건: (1) Rollouts **AnalysisTemplate**(canary 메트릭 자동 abort) = `analysis.enabled: false`, 켜는 것 자체가 라이브 검증 단계. (2) soft 티어 **NetworkPolicy** = `enabled: false`, 선행 조건은 `scripts/verify_netpol_enforcement.py`가 **ENFORCED**를 반환하는 것. 검증기는 대조군(정책 없이 연결 성공)이 실패하면 PASS가 아니라 **INCONCLUSIVE(exit 2)** 를 반환한다.
- **Reason:** 두 기능의 실패 모드가 "안 켜짐"이 아니라 **거짓 초록**이다. 미검증 auto-abort를 기본으로 넣으면 라이브 실증된 Phase 4 수동 promote/abort 데모를 미검증 동작으로 덮어쓴다. 더 심한 건 NetworkPolicy — 집행하지 않는 CNI에 올리면 오브젝트는 존재하고 `kubectl get netpol`은 건강해 보이고 감사·대시보드는 "격리됨"으로 읽는데 트래픽은 그대로 흐른다(= 보안 컨트롤의 거짓 초록, 아무것도 안 한 것보다 나쁨). CNI 집행 여부는 기판·버전마다 달라(kindnet은 과거 미집행, 최근 kindnetd는 지원) **버전 표를 믿지 않고 눈앞의 클러스터에 실험**해야 한다.
- **Impact:** 미래 세션은 이 두 플래그를 **검증 없이 true로 바꾸지 말 것**. ①은 `enabled: true` + canary 재실행으로, ⑥은 검증기 ENFORCED + namespace에 `platform-agent.io/tenant` 라벨 부여(Phase 2 Capsule 담당) 후에 켠다. 검증기가 NOT ENFORCED면 켜는 대신 policy-enforcing CNI(kind `disableDefaultCNI`+Calico) 또는 vcluster/dedicated 티어로 승격. 같은 원칙이 앞으로 추가되는 보안 기능에도 적용된다.

## D20 — 인시던트 analyzer LLM 백엔드는 env-게이트 pluggable (On-Prem=로컬 Qwen 우선, Cloud=Bedrock)

- **Decision:** `analyzer._invoke_llm`이 `ANALYZER_LLM_ENDPOINT` 설정 시 OpenAI 호환 엔드포인트(로컬 Qwen/MLX)를, 없으면 Bedrock을 호출. On-Prem webhook은 Qwen 기본 배선(Makefile). AWS 경로 무변경·역호환. 인시던트 레코드에 confidence 영속화.
- **Reason:** On-Prem의 정체성은 오프라인 로컬 LLM인데 인시던트 analyzer가 Bedrock만 불러 인클러스터(자격증명 없음)에서 휴리스틱 폴백(신뢰도 0%)됐음. env 게이트로 On-Prem은 Qwen, Cloud는 Bedrock을 쓰게 분리. (파서는 Qwen이 JSON 뒤 붙이는 설명 텍스트 내성, onprem 어댑터는 per-alert annotations 캡처로 프롬프트 구체화.)
- **Impact:** On-Prem 인시던트가 로컬 Qwen으로 실제 root cause+신뢰도 산출(라이브: OOMKilled conf 0.95). `analyzer.py`(공용)에 백엔드 분기 추가, AWS/GCP/Azure 무영향. `4aef387`, gate 876.

## D19 — Argo Rollouts는 기존 deployment 러너를 대체하지 않고 **k8s 전용 옵트인 점진배포**로 병존

- **Decision:** On-Prem addons에 Argo Rollouts를 추가하되(Phase 4), 기존 `deployment/` 어댑터의 canary/rollback(cloud-neutral, 4-provider)은 그대로 둔다. Rollouts는 addons 스택에 들어오는 워크로드용 **인프라 레벨** 점진배포 메커니즘, 러너는 에이전트가 provider별로 구동하는 **애플리케이션 레벨** 배포 파이프라인 — 둘은 다른 층.
- **Reason:** 러너는 onprem/aws/gcp/azure 4곳에서 동일 계약으로 동작하는 클라우드-중립 코어라 k8s 전용 CRD(Rollout)로 대체하면 이식성 회귀. 반대로 Rollouts는 트래픽 가중 canary·자동 분석·수동 게이트 등 러너가 재구현할 이유 없는 k8s 네이티브 기능을 제공. 그래서 대체가 아니라 **선택적 병존**(addons를 GitOps로 배포받는 클러스터에서만 opt-in).
- **Impact:** 러너 코드 무변경. Rollouts는 `infra/onprem/addons/rollouts.tf`(컨트롤러 2.41.1 핀) + `charts/rollouts-demo`(canary 데모)에 격리. 라이브 실증: promote/abort 양경로(`docs/evidence/onprem-addons-rollouts-e2e.log`). 프로덕션 워크로드를 Rollout으로 승격할지는 별도 결정(현재는 데모만).

## D18 — On-Prem ArgoCD는 label이 아니라 **annotation** 리소스 추적 (`application.resourceTrackingMethod=annotation`)

- **Decision:** addons ArgoCD를 annotation 기반 추적으로 고정(`values/argocd.yaml` `configs.cm`). 워크로드 Application은 `releaseName=pa`로 렌더.
- **Reason:** platform-agent 차트가 `app.kubernetes.io/instance={{ .Release.Name }}`를 직접 찍는데, ArgoCD 기본 **label 추적**은 같은 라벨을 Application명으로 덮어써 selector 불변식과 충돌한다(Helm 차트용 Argo 공식 권장이 annotation). annotation 추적은 `argocd.argoproj.io/tracking-id`로 소유권을 표기해 라벨을 건드리지 않으므로 기존 `pa` 릴리스 리소스를 **무중단 채택** 가능.
- **Impact:** GitOps가 관리하는 워크로드는 instance 라벨 자유(차트가 소유). ArgoCD 재설치/버전업 시 이 cm 값 유지 필수. 라이브 실증: 6 리소스 채택·drift selfHeal ~16s(`docs/evidence/onprem-addons-gitops-e2e.log`).

## D17 — 알림성 액션은 SSM 문서가 아니라 executor in-process로 실행 (`_NOTIFICATION_ACTIONS`)

- **Decision:** `open_change_request` 캐퍼빌리티류 알림성 액션(현재 `AWS-SendSlackAlert` 1종)은 SSM Automation 문서 디스패치가 아니라 **executor 자신의 Slack 인시던트 리포트로 수행**하고 executed로 집계한다(웹훅 미설정 시 skip 유지). 실 SSM 문서 작성(b)·의도된-skip 문서화(c)는 기각.
- **Reason:** `AWS-SendSlackAlert`는 실존하는 AWS 관리 문서가 아님(라이브 E2E가 표면화; AccessDenied 이면에 NotFound 이중 결함) → generic-recovery가 구조적으로 `resolved=False`. 알림의 실체는 "사람에게 알리기"이고 그 전달 경로(post_webhook)는 executor에 이미 존재 — 별도 SSM 문서는 유지비만 늘림.
- **Impact:** 새 알림성 액션은 `_NOTIFICATION_ACTIONS`에 등록하면 provider 무관 동일 처리. 인시던트 resolved 시맨틱 = "모든 액션이 실행됨"이며 알림도 실행으로 침. 라이브 검증: 실 LLM P1/AUTO→`resolved=True`(INC-E15BA62E, gate 847).

## D16 — Vercel OIDC = team slug `men16922s-projects` 고정 + cdk deploy 해금은 개인 스코프(local settings)만

- **Decision:** (1) Vercel↔AWS OIDC 페더레이션의 ground truth는 **team slug `men16922s-projects`**(Vercel API `/v2/teams` 확증, issuerMode=team)로 고정하고, CDK diff/deploy는 항상 `-c vercelTeamSlug=men16922s-projects -c vercelProjectName=platform-agent`를 넘긴다. (2) 대시보드 트리거용 SFN 권한은 **정확-ARN `states:StartExecution`**(platform-agent-deployment/provisioning 2개)+`ListStateMachines`("*"는 list 계열 API 제약)만 부여. (3) `npx cdk deploy` 하네스 해금은 **`.claude/settings.local.json`(개인·비커밋)**에만 두고 공용 `settings.json` 경계는 유지한다.
- **Reason:** (1) 07-11 context 미지정 배포가 provider를 실제 삭제(CloudTrail)해 대시보드가 조용히 DEMO FALLBACK으로 강등된 전례 — slug 후보가 2개(men16922/men16922s-projects) 존재해 재발 위험이 높아 문서로 고정. (2) IAM 최소권한 가드레일(`Resource:"*"` 금지) 준수. (3) overnight 무인 루프에서 클라우드 변경이 자동 허용되면 "billable=사용자 게이트" 설계가 깨짐 — 개인 스코프면 대화형 세션에서만 유효.
- **Impact:** 미래 세션은 다른 slug로 배포하거나 provider ARN을 하드코딩하지 말 것. 공용 settings.json에 cdk deploy allow를 추가하려면 별도 사용자 결정 필요. provider가 또 사라지면 대시보드는 에러 없이 DEMO FALLBACK 배지만 뜸 — 배지가 곧 헬스 시그널.

## D15 — 크로스클라우드 리팩토링 경계: executor/runner 보일러플레이트만 공유, detector/analyzer/decision·rollback은 분리 유지

- **Decision:** 2026-07-17 구조 패스에서 (1) gcp/azure **executor**의 provider-중립 보일러플레이트(deserialise/serialise/action-loop/slack)는 `operations/_executor_common.py`로, (2) gcp/azure **runner**의 byte-identical한 K8s **rollout-restart/scale** 동사는 `operations/executor/_k8s_rest.py`로 추출한다. 그러나 **detector/analyzer/decision**(SDK·쿼리언어·메모리스토어가 90%+ 상이: Pub/Sub vs EventGrid, Cloud Logging vs KQL, Firestore vs Cosmos, Vertex Gemini vs Azure OpenAI)과 **runner rollback**(GKE는 현재 이미지에서 `:previous` 유도 vs AKS는 `RollbackVersion` 필수)은 **의도적으로 각 provider에 분리 유지**한다. `approval_bridge/handler.py`(604줄) 분리도 **하지 않는다**.
- **Reason:** detector/analyzer/decision을 DRY하면 클라우드별 SDK/시맨틱을 억지로 한 추상으로 눌러 leaky abstraction이 된다(겉만 유사·본질 상이). approval_bridge 분리는 테스트가 내부심볼 12개+를 `handler` 모듈경로에 `@patch`로 강결합해, 옮기면 patch 경로 보존용 재import가 필요→실질 디커플링 이득 없이 15개 patch 타깃 재작성 리스크만 큼(보상<리스크). `_k8s_rest`의 REST 분기는 mock이 앞에서 return해 유닛 커버리지 0이라, 시맨틱이 완전 동일한 restart/scale만 정독-검증 후 이동(rollback 제외).
- **Impact:** 미래 세션은 "cross-cloud 코드가 비슷해 보인다"는 이유로 detector/analyzer/decision을 통합하거나 approval_bridge를 쪼개지 **말 것**(재작업 방지). 공유 대상 변경 시 `_executor_common.py`/`_k8s_rest.py` 한 곳만 고치면 되고, post_webhook 오호출 버그도 이 공통화로 한 곳에서 수정됨. `operations` 그룹핑 축 통일(AWS=role별 vs gcp/azure=cloud별)은 미결 열린작업(`NEXT_PLAN.md`).

## D14 — 대시보드 NL 배포 채팅 = Local Qwen 실행 전용, 클라우드 3종은 "검증만"(미실행), 백엔드는 로컬-only

- **Decision:** 대시보드 Agents 채팅의 배포 경로(`agents/deploy`·`/stream` → 라우터 `/api/local-deploy`)는 (1) **모델과 무관하게 전부 `LOCAL_DEPLOY_API_URL`(기본 127.0.0.1:8077)로 프록시**하고, (2) 라우터 `route_deploy`(`model_router.py`)는 **`framework=="pydantic-ai"`(local-qwen)만 실 실행**(MLX→build/push/deploy/validate→kubectl), strands/adk/msft(bedrock-claude/vertex-gemini/azure-gpt)는 `_cloud_outcome`로 **`ok=False`+"requires {cloud} creds for a live run" 구조화 응답만 반환(미실행)** 한다. 클라우드 3종의 실 배포/tool-calling 실증은 **이 채팅이 아니라** 별도 경로(프레임워크 스크립트·`adapters/deployment/*`·런타임 호스팅 어댑터 AgentCore/Agent Engine/Foundry)에서 수행한다. 이 채팅은 **On-Prem/Local Qwen 오프라인 쇼케이스 전용**으로 유지한다.
- **Reason:** (a) 라이브 클라우드 배포는 서버측에 해당 클라우드 크레덴셜이 있어야 하고 **실 과금**이 발생 → 채팅에서 조용히 과금하는 대신 "검증+미실행"으로 세워두는 게 안전 기본값. (b) 채팅의 정체성은 완전 오프라인 On-Prem 데모(air-gapped Local Qwen)라, 클라우드 브레인은 suitability 조언(`/api/models` verdict)만 노출하는 게 서사에 맞음. (c) 프록시가 127.0.0.1인 것은 executor-writes(로컬 MLX/kubectl 옆)↔dashboard-reads(Vercel read-only) 분리 설계의 귀결 — 대시보드는 얇은 클라이언트.
- **Impact:** **Vercel 공개 URL에선 4종 전부 채팅 배포 불가(502)** — local만이 아니라 전체가 로컬 백엔드 의존. 공개 URL에서 채팅 배포를 시연하려면 로컬 스택을 어딘가 호스팅해 `LOCAL_DEPLOY_API_URL`을 그쪽으로 돌려야 함(서버측 크레덴셜+과금 정책 결정 필요=사용자 판단). 채팅에서 클라우드 3종을 실제 실행시키려면 `route_deploy`의 cloud 분기를 어댑터/프레임워크 실호출로 잇는 후속 작업 필요(현재 의도적 미실행). 라이브 재검증 2026-07-15(로컬 스택 E2E, local-qwen→kind `orders-api 1/1 Running`).

## D13 — 단일 도구 카탈로그는 레이어별로 둘 유지(게이트웨이 raw ↔ 인터랙티브 에이전트) — 병합 안 함

- **Decision:** "도구를 한 곳에만 선언하고 discovery+dispatch를 파생"하는 단일-카탈로그 규율을 **두 레이어에 각각 별도**로 적용한다. (1) 게이트웨이 `TOOL_CATALOG`(`ai/gateway/mcp_server.py`) = raw kubectl/docker MCP 핸들러(`ToolResult` 반환, A2A/외부 에이전트용). (2) 인터랙티브 에이전트 `AGENT_TOOL_CATALOG`(`ai/local_deployer.py`) = 상위 어댑터-백드 LLM-튜닝 도구(provision/deploy/investigate, dict 반환, Pydantic AI 스키마용 docstring). 후자에서 `ALL_OPS_TOOLS`(dispatch)와 시스템프롬프트 `## Tools` 인벤토리(discovery)를 둘 다 카탈로그에서 파생, drift-0 불변식 테스트로 강제. **두 카탈로그를 하나로 병합하지 않는다**(D10의 "인터랙티브↔MCP Gateway 통합은 로드맵"을 "레이어가 달라 통합 부적절"로 종결).
- **Reason:** 두 도구군은 추상화 레이어가 다르다 — 게이트웨이는 raw kubectl/docker 1:1 래퍼, 에이전트 도구는 provider-neutral 배포 어댑터를 오케스트레이션(`deploy_service`=build→push→deploy→validate)하고 LLM 컨텍스트용 출력 캡·docstring 스키마로 튜닝됨. 강제 병합하면 레이어를 뒤섞고 에이전트의 튜닝된 행위를 깨뜨림(회귀 리스크 큼). 얻으려던 실익(선언 1곳·discovery↔dispatch drift 제거)은 레이어별 카탈로그로 이미 100% 달성.
- **Impact:** 도구 추가 = 해당 레이어 카탈로그 1곳. 게이트웨이 `test_gateway`·에이전트 `test_local_deployer` 각각 drift-0 불변식 보유. 배포 경로를 게이트웨이 raw 카탈로그로 수렴하는 후속 리팩터는 **의도적 비채택**(레이어 혼합). 되돌리려면 두 카탈로그 파생 구조를 함께 손봐야 함.

## D12 — On-Prem Day-2 = PATH B webhook + in-process 4-step + 오프라인 승인 게이트 + 실 executor는 기본 OFF

- **Decision:** On-Prem의 이벤트 진입(PATH B)은 **FastAPI webhook**(`onprem_webhook_api`), 오케스트레이션은 **in-process 4-step 직접 호출**(`onprem_incident_pipeline`이 detector→analyzer→decision→executor 핸들러를 출력→입력 체인 — 클라우드의 Step Functions/Workflows/Durable Functions 대응). 승인은 **오프라인 JSONL pending 스토어**(`onprem_approvals`, deploy_recorder식 single-row 승계) + `/approve`(decision 재생 실행)·`/reject`. 인시던트는 **오프라인 JSONL 스토어**(`onprem_incidents`)에 기록하고 webhook `/incidents`로 노출 → 대시보드가 AWS+On-Prem을 **hybrid HTTP 병합**(승인 카드·타임라인, source 배지). **실 remediation(`onprem_runner`, kubectl)은 `ONPREM_EXECUTOR_LIVE`로 기본 OFF**(TESTING 시 강제 OFF), 켜도 **되돌리기-가능 4조치만** 자동 실행 — 각 조치는 "안전하지 않으면 스스로 물러난다"는 기준을 코드 가드로 강제: `rollout restart`/`undo` + `scale --replicas=N`(**양수 타깃일 때만**; 누락/0/비정수→log-only, scale-to-0=셧다운 가드) + polite `drain <node>`(**`--force`·`--delete-emptydir-data` 미사용** → kubectl이 PDB 존중·미관리/로컬데이터 파드 거부=실패→skip, NodeName 없으면 log-only). 공격적 force-drain은 의도적으로 사람 몫.
- **Reason:** On-Prem은 매니지드 오케스트레이터/DynamoDB/SFN이 없어 완전 오프라인이어야 함 → in-process 체인 + 파일 스토어. 대시보드는 Vercel-호환 위해 파일 경로 대신 webhook HTTP로 읽음(onprem-status 패턴 재사용). 자동 remediation이 임의로 클러스터를 변경하면 위험 → 기본 OFF + **되돌리기-가능하고 desired-state가 알림에 실려오며 위험 시 스스로 실패하는 액션만**이 안전 기본값(프로덕션 사고 방지). scale/drain은 각각 타깃 파라미터·polite 플래그 정책으로 이 기준을 충족시켜 편입.
- **Impact:** 신규 `onprem_webhook_api`/`onprem_incident_pipeline`/`onprem_approvals`/`onprem_incidents`/`operations/executor/onprem_runner`; executor `_run_external_action` onprem 분기가 stub→runner. `execution/onprem.py`가 ScaleWorkload에 `DesiredReplicas`(라벨)·DrainNode에 `NodeName`(라벨) 스레딩. 대시보드 `approval-data.ts`/`incident-data.ts` hybrid 병합 + `Incident.provider`에 onprem. `make dev-up`에 webhook 통합. 환경변수 `PLATFORM_{APPROVALS,INCIDENT}_FILE`·`ONPREM_WEBHOOK_URL`·`ONPREM_EXECUTOR_LIVE`. 되돌리려면 webhook·스토어·대시보드 hybrid·executor 분기를 함께 되돌려야 함. kind 라이브로 4조치 실증(rollout restart 파드 교체·scale 2→5·drain 노드 cordon+재배치 아웃티지0, 2026-07-14).

## D11 — 배포 추적 데이터 모델·IA: type/cluster 분류 + 롤백은 status(단일-row 승계) + teardown cascade

- **Decision:** activity 기록에 **`type`(provision/deploy)** 과 **`cluster`(연결키: deploy.cluster == provision.service)** 를 저장하고, **롤백은 별도 type이 아니라 status(`rolled-back`)** 로 표현한다(원본 행을 같은 `deployment_id`로 supersede = 단일-row). **cluster teardown은 그 클러스터의 deploy들을 자동 `rolled-back`으로 cascade**. 자연어(rollback_deployment/teardown_cluster)와 UI 버튼은 **동일 경로**(supersede/cascade)로 기록. 대시보드는 **Provisioning / Deployments / History** 3분리 + **통합 중첩 상세**(provisioning⊃deployments, 한 페이지). `provider`(aws/gcp/azure/onprem)와 `environment`(production/staging/dev)는 직교(더 이상 environment=provider 아님).
- **Reason:** 한 run이 provision+deploy 복합이라 단일 행으론 provisioning/deploy가 뭉개짐 → type 분리 + cluster 상관. 롤백을 type으로 두면 cluster 롤백이 Provisioning→Deployments로 새서 분리 원칙이 깨짐 → status로. 클러스터를 내리면 그 위 앱은 물리적으로 사라지므로 추적도 truthful하게 cascade. 자연어=UI 동일 결과라야 데모가 일관.
- **Impact:** `deploy_recorder`에 `type/cluster/environment`, `record_rollback`(supersede), `record_cluster_teardown`(cascade), `read_deploys`(최신, 동일 timestamp는 나중 우선) 추가. 읽기측 dedupe는 **latest-per-id**. 레거시 행은 `cluster` 없어 롤백 비활성. 대시보드 상세는 `getLifecycleDetail`(cluster로 엮음). 되돌리려면 기록 스키마·읽기 dedupe·페이지 3개를 함께 되돌려야 함.

## D10 — 2-역할 에이전트(Provision/Deploy) + Orchestrator+A2A + On-Prem Provision=Terraform/Ansible, Runtime=kagent

- **Decision:** ServiceSpec 기반 **① Provision(Day-0/1 IaC) + ② Deploy(Day-1 App)** 2-역할로 분리. 온프렘 Provision = **Terraform(kind, Mac Tier1) + Ansible(k3s, VM Tier2)**. 상위 통합은 **Orchestrator(supervisor) + A2A**(에이전트 상호운용) + **MCP 단일 도구 카탈로그**. On-Prem 에이전트 런타임 대응물 = **kagent(CNCF)**. 인터랙티브 에이전트는 현재 in-process 도구 사용(MCP Gateway는 A2A/외부용, 통합은 로드맵).
- **Reason:** "Platform Agent가 클러스터까지 셋업" 컨셉 충족 → 클러스터 프로비저닝을 에이전트 능력으로. 온프렘 IaC 표준 = Terraform(인프라)+Ansible(구성). AgentCore는 AWS 매니지드라 온프렘 불가 → kagent(K8s CRD, MCP/A2A)가 오픈소스 대응물.
- **Impact:** `adapters/provisioning/`(capability→환경별) + `provision_tools` + `infra/onprem/{terraform,ansible}` 추가. Deploy 어댑터(4-provider CodeBuild/Cloud Build/ACR Tasks/docker)는 유지. ARCHITECTURE 상단 통합 스택 표가 단일 레퍼런스. 미구현: 클라우드 Provision apply, Orchestrator+A2A 통합, kagent↔로컬LLM 연결.

---

## D9 — AI Model Router: 모델↔환경 분리, On-Prem = Pydantic AI + MLX

- **Decision:** LLM(두뇌)과 배포 환경(대상)을 분리하고 `model_router.py`가 (model×environment) 적합도 검증 후 라우팅. On-Prem 에이전트는 Strands 대신 **Pydantic AI + 로컬 MLX Qwen** 독립 구현(`local_deployer.py`). 프레임워크 = 각 클라우드 네이티브(aws=Strands, gcp=ADK, azure=MSFT, onprem=Pydantic AI).
- **Reason:** On-Prem에서 Strands는 Bedrock 이점 없이 MLX tool-call 포맷을 맞추는 proxy까지 요구 → "완전 오프라인" 서사와 상충. 배포 tools는 이미 provider-neutral이라 모델↔환경 분리가 자연스러움.
- **Impact:** 어떤 모델이든 어떤 환경에 배포 가능(적합도 배지로 표기). 대시보드 Agents 채팅이 `/api/models`+`/api/local-deploy`로 자연어 배포. 실행부(로컬 API)가 DEPLOY/ACTIVITY 기록 → 대시보드는 read-only 유지. `mlx_qwen_tool_proxy`는 프레임워크 중립 정규화(stream/non-stream)로 잔존.

## D8 — 문서·컨텍스트 하네스 도입 (harness.md 이식)

- **Decision:** "항상 읽는 작은 current docs" 와 "필요 시 여는 archive" 를 물리적으로 분리하고, `/sync`·`/checkpoint`·`/tidy-docs` skill 로 강제. 기존 도메인 문서는 `bin/docs/archive/` 로 전면 이관.
- **Reason:** 멀티세션·멀티에이전트에서 매번 작은 컨텍스트로 상태 복원. 시작 컨텍스트 = 비용·정확도.
- **Impact:** 세션 진입은 Read Path(CONTEXT_BRIDGE→AGENT_BRIEF→STATUS→NEXT_PLAN)만. 도메인 상세는 archive 링크로만 접근. docs/ 전체 bulk-read 중단.

## D7 — runbook catalog: 코드 fallback = DynamoDB seed 초기값 공유

- **Decision:** 단일 built-in catalog 를 코드 fallback 이자 `incident-runbooks` seed 초기값으로 동시 사용. exact `alarm_name` → catalog scan heuristic → 내장 → generic 순.
- **Reason:** 두 소스 이중 관리 제거, registry 비어도 동작 보장.
- **Impact:** catalog 변경이 fallback 과 seed 양쪽에 일관 반영. malformed override 는 `validate_runbook` 으로 무시+폴백.

## D6 — capability 기반 provider-neutral runbook

- **Decision:** 런북은 capability(`restart_workload` 등) 로 표현, executor adapter 가 provider action 으로 해석.
- **Reason:** 멀티클라우드 확장 시 control-plane 재사용.
- **Impact:** AWS 외 provider 추가가 adapter 교체로 가능.

## D5 — `Delete`/`Drop`/`Terminate` 액션 강제 APPROVE

- **Decision:** severity 와 무관하게 파괴적 액션은 무조건 approval 게이트.
- **Reason:** 자동 실행으로 인한 비가역 손실 방지.
- **Impact:** P1 AUTO 라도 파괴적 액션이면 사람 승인 대기.

## D4 — 실행은 SSM Automation (Lambda 직접 호출 아님)

- **Decision / Reason:** 감사 로그·승인 게이트·기존 운영 문서 재사용.
- **Impact:** Executor 만 `StartAutomationExecution` 권한 보유.

## D3 — LLM 은 Bedrock (외부 API 아님)

- **Decision / Reason:** VPC 내 호출, IAM 인증, 데이터 외부 전송 없음.
- **Impact:** Analyzer 만 Bedrock `InvokeModel` 권한.

## D2 — 알람 트리거는 EventBridge (SNS 아님)

- **Decision / Reason:** 이벤트 패턴 매칭, 다중 타겟, 필터링.
- **Impact:** alarm state change 를 EventBridge rule 로 캡처.

## D1 — 오케스트레이터는 Step Functions (SWF 아님)

- **Decision / Reason:** 시각적 디버깅, 재시도/에러 핸들링 내장, CDK 통합. (SAP: SWF vs Step Functions)
- **Impact:** 파이프라인은 `src/step_functions/pipeline.json`, CDK 와 동기 유지.
