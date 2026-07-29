# COMPLETED_SUMMARY — platform-agent

최종 갱신: 2026-07-26

> 완료된 milestone 압축. current docs 에는 링크만, 상세 체크리스트는 여기로 압축.
> 도메인 원문 상세는 `bin/docs/archive/`.

---

## M0 — Operations 파이프라인 기준선 (완료)

Detector / Analyzer / Decision / Executor 4단계 + Approval Bridge. CloudWatch Alarm → Logs Insights / X-Ray / Bedrock RCA → 런북 선택 → SSM Automation → Slack 리포트 → DynamoDB 기록(90일 TTL). canonical 경로 `src/agents/operations/`, flat import 은 compatibility shim 으로 보존. Step Functions pipeline 과 handler 경로 일치.
상세: `bin/docs/archive/agents.md`, `bin/docs/archive/architecture.md`.

## M1 — Human-in-the-loop 승인 (완료)

P2 severity 흐름에 Slack interactive approval. `WaitForTaskToken` + SQS + approval bridge + Step Functions callback(`SendTaskSuccess`/`SendTaskFailure`). Approve/Reject 버튼으로 파이프라인 재개. 인터랙티브 미설정 환경은 `APPROVAL_DEFAULT_DECISION` 폴백.

## M2 — Harness / handoff 레이어 (완료)

`TaskQueue`(.harness/tasks.json), `ContextStore`(.harness/context.json), `TaskRouter`, `AgentHarness`, client 추상화. `python -m harness.handoff` 로 `.harness/handoff.md` 자동 생성(빈 상태면 워크스페이스 스캔 seed). Claude Code ↔ Codex 툴 전환 컨텍스트 보존.

## M3 — Portability runtime seam (완료)

`NormalizedIncident` cloud-neutral envelope. detector 가 alarm context 와 함께 생성 → analyzer RCA prompt 반영 → decision 이 capability 기반 runbook metadata 를 AWS action 으로 해석 → executor 가 normalized incident 기준 SSM 파라미터 우선 구성.

## M4 — 멀티클라우드/온프렘 scaffold (완료, 런타임 미연결)

provider registry + signal adapters(aws/gcp/azure/onprem) + execution adapters(aws/gcp/azure/onprem). 비-AWS 는 normalized incident / capability mapping 검증용 scaffold + 단위 테스트. 실제 provider API 호출은 NEXT_PLAN P1.

## M5 — Runbook registry bootstrap + override 계약 (완료)

`src/agents/runbooks/catalog.py` built-in capability 기반 catalog(eks-pod-oom / lambda-throttle / rds-cpu-high / kafka-lag-spike / generic-recovery). CDK custom resource 가 `incident-runbooks` 에 seed. decision 은 exact `alarm_name` lookup 실패 시 catalog scan heuristic 으로 재매칭. 코드 fallback ≡ DynamoDB 초기값.
override 계약: `src/agents/runbooks/schema.py`(`validate_runbook`). seed 시 malformed skip+로깅, decision 시 malformed 무시+경고 후 heuristic 폴백.
상세: `bin/docs/archive/agents.md` (런북 스키마 표).

## M6 — CDK deprecation 정리 (완료)

DynamoDB `pointInTimeRecovery` → `pointInTimeRecoverySpecification`. Lambda `logRetention` → 함수별 전용 `logs.LogGroup` 을 `logGroup` 으로 주입. legacy `Custom::LogRetention` 커스텀 리소스 + 부수 IAM Role 제거. `npm run synth` deprecation 13건 → 0건.

## M13 — "선언됐지만 아무도 읽지 않는 것들" 12건 (완료, 2026-07-28~29)

**gate 1411 → 1544 (+133).** 증거 `docs/evidence/{phase3-tenant-grant-validation,
runbook-selectability,capsule-deprecation-metadata,executor-span-approval-path,
onprem-runbook-matching,declared-unconsumed-sweep,incident-trigger-time,
cloud-incident-fields,incident-time-to-resolve,rollback-cost-metrics,
activity-read-model-drift,report-windows}.log`.
결정 → `DECISIONS` D33·D34·D35.

Phase 3가 인가를 닫은 뒤 남은 잔여를 우선순위대로 소진했는데, **아홉 건이 전부 같은
결함**이었다: 필드나 계획이 **선언되고, 채워지고, 저장되고, 아무도 읽지 않는다.** 테스트는
아홉 번 다 초록이었다 — 전부 *생산자*를 단언했기 때문이다. 아홉 번 다 **라이브 실행만이**
드러냈고, 그중 네 번은 유닛 테스트가 통과하는 동안 라이브가 다른 답을 냈다.

그 뒤 같은 축의 **변형 두 건**이 더 나왔고, 둘 다 스윕을 **새 방향으로 넓혀서** 찾았다:
**⑩반대 방향**("읽는데 아무도 안 씀" — 생산자 셋 중 하나만 침묵) · **⑪한 층 위**(필드가
아니라 **선언 자체를 아무도 안 읽음** — importer 0인 스키마 문서가 양방향으로 드리프트).

- **grant 대조(1425)**: 기록은 "대조 안 함"이었지만 grant를 **줄 방법 자체가 없었고**(읽기 쪽이
  아무 쓰기 경로도 만들 수 없는 필드를 소비 중) 역할 변경이 whole-item Put으로 grant를 지웠다.
  허브 로스터(못 읽으면 **503**, 회수만 예외) + 저장 전 대조 → D33.
- **런북 선택성(1445)·티어(1470)**: 런북 4개가 BUILTIN에 없어 선택 불가 → 넣었더니 라이브는
  여전히 generic-recovery. 시드 테이블의 generic 행이 티어 4의 답을 대신 내서 **빌트인 티어가
  배포 환경에서 한 번도 도달된 적 없었다**(D34). 고쳤더니 이번엔 **더 나쁜 매칭**이 이겼다 —
  1점짜리 시드 행이 3점짜리 빌트인을 눌렀다(D35, 합집합 휴리스틱).
- **온프렘 매칭(1470)**: `reason`이 `metric_name`의 **복사본**이라 매처가
  "availability availability…"를 읽었고, `resource_types`는 모든 런북에 선언돼 있고 **미소비**라
  엉뚱한 런북이 걸려도 하드코딩 AWS 액션으로 조용히 폴백했다.
- **Capsule metadata(1446)**: `additionalMetadata`는 제거 릴리스에서 **에러 없이 안 읽히는**
  쪽으로 실패할 필드라 선제 이관(라이브에서 probe 라벨 전파로 반증).
- **executor span(1454)**: 웹훅이 루트 span을 닫은 뒤 실행해 **AUTO·승인 양쪽 다 무추적**.
  승인은 부모가 아니라 **링크** — 사이 간격이 사람의 고민 시간이라 접으면 지연 수치가 무의미해진다.
- **severity_hint(1479)**: 우연을 그만두려 **계통 스윕**(437 필드 → 20 후보). 네 어댑터가 전부
  채우는데 아무도 안 읽어, 사람이 **미리** 내린 분류가 버려지고 **AUTO/APPROVE를 정하는 축**이
  산문에서만 추론됐다. 라이브 A/B: warning이 자동실행 → 승인대기로.
- **인시던트 발생 시각(1491·1496)**: 행이 "우리가 쓴 시각"만 알아 탐지 소요시간이 산출 불가.
  온프렘·클라우드 양쪽 + `detected +Nm` 배지(**읽는 쪽 없이 저장만 하면 같은 결함을 하나 더
  만드는 것**). 클라우드 `confidence`는 float라 그냥 넣었으면 boto3 예외가 기록기의 `except`에
  잡혀 **레코드 전체가 사라졌을** 것 → `Decimal`.
- **time-to-resolve(1520)**: 이 부류의 **가장 비싼 변종** — 앞의 여덟은 값이 *버려졌지만*
  이번엔 값이 **있는 척했다.** `resolved_at`이 `created_at`의 복사본이라 주간 온콜 리포트가
  **존재 내내 "MTTR 0.0분"을 자신 있게 발송**했다(fetch가 한 키를 `started_at`·`resolved_at`
  양쪽 끝에 넣었다). 부재는 눈에 띄지만 **그럴듯한 기본값은 안 띈다.** 같이 나온 둘:
  `runbook_id`에 `alarm_name` 복사 → 재발 패턴 그룹핑 붕괴 · 대시보드 Scan 투영이 **자기
  리더가 읽는 4필드**를 안 불러 전날 수정이 배지 한 층 앞에서 멈춰 있었다.
  실측 0.0→45.0, 라이브 P1/AUTO 1502초 보존·열린 인시던트는 부재.
- **롤백 비용 패널(1528)**: 이 부류가 **반대 방향으로도** 열린 첫 사례 — 읽는 쪽은 멀쩡한데
  ACTIVITY를 쓰는 셋 중 `record_rollback`만 `cost_metrics`를 빠뜨렸다. 그 자체론 과소보고인데,
  reader `mergeActivity`가 **trace만 합집합**으로 두고 나머지를 `{...latest}`로 최신 행에서
  가져가 **롤백되는 순간 도구/추론/토큰 수가 페이지에서 사라졌다**(패널이 조건부라 예외도
  "0"도 없이, 바로 아래 트레이스는 오히려 길어진 채). 라이브 BEFORE 미렌더 → AFTER
  `tool calls 5 · tokens 920`, 내역이 두 실행에 걸침. **절반씩은 각각 방어 가능한데 겹칠
  때만 터진다** · 생산자가 여럿이면 **하나만 침묵해도** 나머지가 정상을 계속 증명해준다.
- **읽기 모델 문서 드리프트(1533)**: 한 층 위 — 필드가 아니라 **선언 자체를 아무도 안 읽는**
  경우. `activity-model.ts`는 **importer가 0**이라 어긋나도 안 깨졌고, 아무도 안 쓰는
  `duration_ms`를 선언하면서 상세 페이지가 딛고 선 `trace`·`cost_metrics`·`deployment_id`는
  빠뜨렸다. 거짓 주장 둘(**`ttl` "30일 보관"인데 주 writer가 안 써서 만료 안 됨** · `GSI1`은
  절반만 채워지고 무쿼리라 그대로 짰으면 **조용히 짧은 목록**). 지키던 테스트가 **부분문자열
  존재만** 봤다 — 이 마일스톤이 적어둔 안티패턴이 **그 파일의 수호 테스트에** 있었다.
- **리포트 창(1544)**: 위 건이 연 TTL 실마리를 따라가 나왔다 — `ttl`("쓴 시각+90일")을 두
  리포트가 **시각처럼** 읽었다. 일일 SLO 필터 `ttl >= now-24h`는 만료 안 된 모든 행에 참이라
  **24시간 창이 보관 기간 전체**였고(90행 중 90 → 2), 주간은 `ttl-90일` 역산이라 상수가 바뀌면
  조용히 밀리고 **`ttl` 없는 행은 90일 과거로 떨어져 늘 누락**됐다. `created_at`으로 배치 +
  폴백 상수를 **writer AST에서 파생 검증**. **라이브 미실행**(스케줄 Lambda) — 과대집계는 추론.

**반복된 교훈(테스트 규율 7종)**: ①가드를 쓰면 **호출부에서** 반증하라 — 새 테스트 20건이
전부 통과하는데 호출자만 플래그를 잊은 상태였다. ②픽스처는 코드가 아니라 **실제 입력**에서
가져와라 — 내가 쓴 summary에 런북 키워드를 심어놔 유닛은 초록인데 라이브는 계속 틀렸다.
③**소비자를 단언하라, 생산자 말고** — `severity_hint`를 "설정되는가"로 봤다면 그 필드가 존재한
내내 통과했을 것이고, 그게 이 부류가 여태 살아남은 방식이다. ④**투영/스키마 계층도 소비자다**
— `ProjectionExpression`이 부르지 않은 속성은 리더가 아무리 방어적으로 짜여도 복구할 수 없다.
⑤**가드는 파생시켜라, 열거하지 말고** — 매퍼가 읽는 속성을 파싱해 Scan에 요구하면 *다음*
필드에도 실패한다. 손으로 적은 목록이었다면 당시 투영에 맞춰 쓰였을 테고 그대로 통과했다.
⑥**생산자가 여럿이면 다수결이 결함을 가린다** — 셋 중 하나만 침묵하면 나머지 둘이 그 필드가
정상이라고 계속 증명해준다. 열 번째 건은 그래서 ③(소비자를 단언하라)으로도 안 잡혔다:
소비자는 멀쩡했다. ⑦**수호 테스트 자신이 안티패턴일 수 있다** — 열한 번째 건에서 파일을
지키던 테스트가 `'GSI1PK:' in content` 식 **부분문자열 존재**만 봤다. 키워드는 모양을 못 보므로
그 파일이 얼마나 어긋나든 초록이었다. **덧붙여 내가 새로 쓴 가드도 처음엔 같은 병이었다**:
두 곳에 선언된 필드를 `re.search`로 봐서 **한 곳만 옵셔널이면 통과**했다 — `any`를 쓸 자리에
`all`이 필요했고, 반증을 돌리지 않았으면 그대로 뒀을 것이다.
스윕은 두 방향 모두 반복 가능하게 남겼다(후보≠결함) —
`scripts/find_unconsumed_fields.py`(선언됐는데 안 읽힘) ·
`scripts/find_unwritten_keys.py`(읽는데 생산자 없음).

## M12 — 멀티테넌트 Phase 3(인가 강화) 완결 + 읽기 경계 (완료, 2026-07-27~28)

**gate 1290 → 1411.** 증거 `docs/evidence/phase3-*.log` · `mcp-gateway-scope.log`.
결정 → `DECISIONS` D31·D32.

Phase 2가 "테넌트 하나의 잘못이 이웃에게 안 번지게"를 클러스터 안에서 증명했다면,
Phase 3는 **누가 무엇을 할 수 있고 볼 수 있는가**를 닫았다. 그리고 이 단계에서 나온
결함은 거의 전부 **앞문은 잠갔는데 옆문이 열려 있던** 형태였다.

- **①자격증명 격리 full**: fail-closed 가드를 `guard_scoped_action` 하나로 모으고 세 러너가
  그것을 부른다(닮은꼴 금지). `resolve_incident_scope` 이관으로 **GCP Cloud Workflows 경로의
  스코프 부재** 해소 — 디스패치 경로가 둘인데 로직이 한쪽에만 있었다. 라이브가 Phase 1a
  증명 자체의 구멍을 적발: `render_rbac`가 바인딩 대상 **ServiceAccount를 렌더하지 않아**
  RoleBinding이 없는 신원을 가리키고 있었다(fail-closed라 안 드러남 → RBAC 팔이 한 번도
  행사된 적 없음). DoD가 "Forbidden **또는** 자격증명 부재"라 약한 쪽으로 통과 중이었다.
- **②reconciler 충돌 거부**: `rollout undo`는 0을 반환하고 `resolved=True`가 기록된 뒤
  깨진 버전이 돌아온다 — out-of-band 변경이 **10초 만에** selfHeal에 되돌려짐을 먼저 실증한
  위에서 거부를 세웠다. 되돌리는 액션만 막는다(restart·scale은 desired로 수렴).
  **selfHeal pause는 채택 안 함**: Application이 `argocd` ns에 있어 테넌트 스코프
  자격증명으로 도달 불가(D32). 설계의 권장안(registry write-back)은 Phase 5 의존 —
  계획 자체의 순서 충돌.
- **③읽기 쪽 테넌트 경계**: `visibility.ts` 단일 seam(플릿 + 인시던트). 인시던트 파티션이
  막혀 있던 원인은 읽기가 아니라 **쓰기**였다 — `NormalizedIncident.tenant`가 Phase 1a부터
  있는데 기록 시점에 버려졌다. 기록 없는 행은 admin 전용, `withheld` 카운트 반환,
  캐시 `public, s-maxage` → **`private, no-store`**.
- **MCP 게이트웨이 옆문**: 모든 도구가 맨 `kubectl`을 쐈고 `kubectl_apply`는 임의 매니페스트를
  임의 ns에 썼다. Phase 1a가 executor에서 없앤 fail-open이 그대로 있었다. argv를 스코프
  kubeconfig로 고정(ContextVar — 도구 인자로 두면 **호출자가 자기 자격증명을 지명**한다),
  변경 도구는 fail-closed. 라이브: 스코프 안 ns인데도 `secrets`는 **API 서버**가 `Forbidden`.
- **테넌트 call budget**: 쿼터는 무엇을 *보유*하는지만 묶었다. sliding window, 레지스트리
  `quota.calls_per_min` 선언, 미선언=무제한(additive).
- **외부 대조**(Qwiklabs GENAI120 · GCP Architecture Center · Developers Blog): Agent Card가
  **가상 주소**와 **집행하지 않는 인증**을 광고하던 것 적발·수정. → `docs/reference/`.

**반복된 교훈**: 이 단계의 결함은 전부 **테스트가 선언을 단언해서** 살아남았다
(`assert "supportedInterfaces" in card` · `ROUTE_PROTECTION` 존재 단언 ·
"Read path remains public" 문구 고정). 값이 어디를 가리키는지, 누가 그것을 소비하는지를
묻지 않는 가드는 정책보다 오래 산다. 그리고 **가드를 쓰면 가드도 반증해야 한다** —
rate-limit 테스트 하나가 결함을 주입해도 통과했다(재시도를 시계 멈춘 순간에 해서
아무것도 단언하지 않고 있었다).

## M11 — 멀티테넌트 Phase 2 완결 (완료, 2026-07-26)

**gate 1191 → 1290.** 증거 `docs/evidence/phase2-*.log`. 설계 →
`docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5).

소프트 티어가 선언에서 **실측된 격리**가 됐다. 목적은 테넌트 하나의 잘못이 이웃에게
번지지 않게 하는 것이고, 이번 단계에서 그 경계가 네임스페이스·쿼터·데이터플레인·자격증명
네 층에서 각각 라이브로 증명됐다.

- **tenancy + Capsule**: 레지스트리가 Namespace(tenant/env/capability + PSS 라벨)·Capsule
  Tenant(`scope: Tenant` 합산 쿼터)·네임스페이스 스코프 RBAC를 렌더. 쿼터 합산은 정지
  조회로는 4배 버그로 보이고 **소비 실험만이 사실을 말한다**(`limited: 6` = 16−10).
- **⑥ 데이터플레인 격리**: 손수 관리하던 차트(데카르트 곱 16 vs 구독 6, 설치 주체 없음)를
  폐기하고 네임스페이스와 **같은 호출**에서 렌더 → 두 집합이 구성상 동일. 집행이 실험으로
  증명된 기판에만 렌더. 라이브 4종(same 통과·cross 차단·kubelet 프로브 생존·DNS 무영향).
- **push 2축 수집기 + 대시보드 스위처**: 허브는 스포크 read 자격증명 0, 신원=서명을 검증한
  키, 침묵은 UNKNOWN 강등. UI가 허브 불가/미푸시/침묵을 구분한다.
- **capability scope 축**: 클러스터 싱글턴을 테넌트별로 렌더하면 컨트롤러 둘이 같은 객체를
  조정한다(라이브에서 발생). 거부 가드는 어댑터가 아니라 **계약**에 둔다.
- **삭제 cascade + values seam**: 삭제 의미를 계약이 말하게 하고(엔진 기본값이 정반대),
  values는 복사하지 않고 가리킨다. 라이브가 **PSS restricted가 우리 애드온을 거부**
  (Argo는 Synced인데 파드 0개)하고 **구독 해지가 데이터를 파괴**(차트가 k8s 기본값을 뒤집음)
  하는 것을 잡아 둘 다 근본수정.
- **managed 경로 + DR**: faked 디스크립터로 과금 없이 `applicable=false` 증명(조회 안 한
  백엔드에 health를 단언하지 않는다). globex/dev를 실제 파괴 후 레지스트리만으로 재구축 —
  라벨 완전 동일, 채택 검증기 신설(`verify_tenancy_adoption.py`).

**반복된 교훈**: 라이브가 잡은 결함 대부분은 "테스트는 초록인데 아무 효과가 없는 코드"와
"정지 조회가 거짓말하는 상태"였다. 그리고 검증기 자신이 거짓 초록/거짓 경보를 낸 사례가
세 번 있었다(`dns-suffix`가 질의를 안 보냄 · 다른 클러스터를 broken으로 보고 · scope 누락을
fail-closed로 올려 게이트 27개 파손).

## M10 — GitAIOps 대조 7/7 + 멀티테넌트 Phase 0·1a·1b + 공급망 하드닝 (완료, 2026-07-20~26)

**gate 870 → 1191.** 상세 이력 → `PROGRESS_LOG.md`(최신 3–5건) · `docs/archive/progress-2026-07.md` ·
증거 `docs/evidence/*`. 설계 → `docs/plans/2026-07-21-multi-tenant-env-addons.md`(v5, S 93.5).

- **On-Prem 애드온 스택 IaC** Phase 1~5(ArgoCD GitOps · kube-prometheus-stack · Argo Rollouts ·
  Loki/Fluent Bit) + k3s 기판 패리티. Gateway API는 소비처 부재로 의도적 보류.
- **GitAIOps 실습서 대조 7/7**: ①Rollouts AnalysisTemplate + **에이전트 릴리스 게이트 3종 판별**
  (정상→pass / 크래시→165s auto-abort / 관측 불가→unknown) · ②OTel→Tempo + 인시던트 딥링크
  (MTTR의 82%가 로컬 LLM 추론) · ③런북 사후검증 provider 실행부 · ④권한 통제 3단 ·
  ⑤Sync Wave(Phase 1b 흡수) · ⑥NetworkPolicy 집행 + **PSS restricted · Cosign** ·
  ⑦고아 클러스터 스위퍼 + **CronJob·coverage 정직성**.
- **멀티테넌트 플랫폼**: Phase 0(레지스트리·로더·`DeliveryAdapter` 계약) · Phase 1a(자격증명이 경계 —
  `IncidentScope` + provenance 바인딩 `TokenBroker`, 라이브 RBAC `Forbidden`으로 증명) ·
  Phase 1b(argocd/flux 어댑터 2개 + 핸드오프 프리플라이트 5검사 + **rollouts-demo 소유권 TF→ArgoCD 이관 실행**).
- **런북이 선언대로 실행됨**: capability step(순서·조건·on_failure·per-step verify)을 executor가 실제 소비.

**이 마일스톤에서 반복해 나온 결함 형태 — 전부 "선언은 됐는데 소비/전달이 없음":**
`llm.endpoint`(차트에 있는데 webhook이 못 받음 → 모든 판정 unknown) · `capability_schema.steps`
(스키마에 있는데 executor가 안 읽음) · `_deserialise_decision`(steps를 직렬화 경계에서 버림) ·
`CAPABILITY_RUNBOOKS`(9런북이 죽은 데이터) · `scripts/`(이미지에 미포함) · 스위퍼 `_run_json`
(CLI 부재를 clean으로) · DynamoDB `Decimal`(rto 선언 런북 전량 탈락).
**공통점: 테스트는 선언을 검증해 초록이었고, 라이브 실행이 소비 부재를 드러냈다.**

## M9 — eval·하드닝 스프린트 + 라이브 E2E 2종: 자율 백로그 전면 소진 (완료, 2026-07-19)

**목적:** Google 생태계·cwc-workshops 대조 후속(①~⑦)과 승인된 실행 큐 8건(⑧⑨ 잔여+⑦ 라이브)을 소진하고, 남은 사용자 게이트 2종(OAuth 배포 클릭·Slack App)을 라이브 E2E로 완주. gate 748→847, spend ~$0.
**산출:** (a) **eval 하네스 시리즈(④⑤⑥)** — `eval_harness.py`(injectable Router/Judge·결정론 백스톱)→멀티-grader 스코어카드(PASS_SLOW·action-sink·Scorecard.delta)→데이터셋 20케이스+adversarial 5·judge 반-관대(calibration_probe); 라우팅 갭 4건 발견→`classify_request` precedence 재설계→회귀 가드. (b) **모델 스윕(⑦)** `model_sweep.py`+라이브 160콜(M8 참조). (c) **A2A/SSE/메모리 하드닝(⑧⑨ 8건)** — sanitize·최소권한 힌트·구조화 디스크립터·저-confidence 게이트·SSE id/ready/heartbeat·`memory_tier.py`(distill/recall/consolidate), 전부 옵트인·비파괴. (d) **OAuth 배포 클릭 E2E**(07-18) + **Slack 인터랙티브 승인 E2E**(07-19) — 이 라이브들이 프로덕션 버그 7건 표면화→전부 근본수정(`.vercelignore` 404·OIDC provider 삭제 복구·smoke_tester base_url·detector NameError·approval_bridge float→Decimal·Bedrock 무효 모델 ID·유령 SSM 문서→D17 in-process 알림).
**검증:** `make check` 847 passed. 라이브 증거 `docs/evidence/{oauth-deploy-trigger-live,slack-interactive-approval-live}.log`, SFN SUCCEEDED 3회·DynamoDB APPROVED/resolved 확증, 실 LLM 심각도 P1/P2/P3 3단 관측. 상세 이력: `docs/archive/progress-2026-07.md`·`status-baseline-2026-07.md`.

## M8 — 프로덕션 패키징 + State Store: AWSome 레퍼런스 8/8 완결 (완료, 2026-07-17)

**목적:** 레퍼런스 잔여 #7(Helm/Terraform)과 로드맵 ④(State Store/Alertmanager)를 닫아 AWSome AI Gateway 레퍼런스 전 항목(Tier 1 4종 + Tier 2 3종 + #7)을 소화. gate 822→842(+20 test), 커밋 9개 전부 origin/main, 클라우드 spend $0.
**산출:** (a) **⑦ 라이브 모델 스윕**(로컬 MLX 160콜) — `_classify_prompt` teardown/진단동사 결함 발견→수정→가드, 증거 기반 선택 **7B@temp0=20/20**(30B 반증). (b) **#7-a Helm 차트** `infra/helm/platform-agent/` + 이미지 `infra/onprem/Dockerfile`(kubectl 내장) — 최소권한 RBAC(4조치 동사 열거·drain 별도 게이트)·strict/lenient 프로브 분리·env×substrate values. (c) **④ SQL State Store** `state_store.py`(`PLATFORM_STATE_DSN` 옵트인, 미설정=JSONL 무변경) + 차트 `stateStore` values(secretKeyRef 우선, DSN 모드=RollingUpdate·replicas>1 해금). (d) **#7-b Terraform** `infra/terraform/aws-production/`(VPC/EKS 1.31/**Aurora Serverless v2 `platform_state`**=DSN seam 정합/IRSA 정확-ARN grant; Redis·Cognito=미소비 제외). (e) 부산물 버그 2건: pyproject optional-deps PEP 621 위반(이미지 빌드가 표면화)·이미지 psycopg2 누락.
**검증:** 라이브 4건 — kind 실 install(RBAC can-i allow/deny·P2 승인 루프·PVC 영속), **실 Alertmanager→멀티-레플리카 상태 공유**(docker PG, replica-2 승인→replica-1 즉시 반영), k3s substrate(기존 k8s-lab VM, `local-path` Bound), terraform init+validate. 증거 `docs/evidence/{model-sweep-live,helm-kind-live-install,state-store-alertmanager-live,helm-k3s-substrate-smoke}.log`. 가드 테스트 +20(helm/terraform/state/sweep). 잔여=사용자 게이트만(terraform apply·아티클·OAuth·Slack).

## M7 — 문서·컨텍스트 하네스 이식 (완료, 2026-06-11)

harness.md 기반으로 `harness/CORE_MANDATES.md` + `CONTEXT_BRIDGE.md`, `docs/` current-doc 체계, `.claude/skills/{sync,checkpoint,tidy-docs}` 구축. 기존 도메인 문서는 `bin/docs/archive/` 로 이관.
