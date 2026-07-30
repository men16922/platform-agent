# AGENT_BRIEF — platform-agent

최종 갱신: 2026-07-31

> ▶ NEXT SESSION: **결정 2도 닫혔다(2026-07-31, D39).** 남은 것은 **결정 2건(3·4) + 승인 3건**. ⓪**결정 4(k3s를 proven 기판에)** — 집행은 라이브 증명됐고 시맨틱만 미증명이다. 막는 건 하나: `verify_tenant_isolation.py`가 **k3s-lab에 피어 테넌트가 없어 못 돈다**(acme/prod가 유일한 env). globex/prod를 만들면 실 네임스페이스·쿼터·애드온이 프로비저닝되므로 **인프라 결정**이다 — 만들지 말지가 질문의 전부다. ①**결정 3(Capsule `limitRanges`)**: `GlobalTenantResource`=클러스터 스코프라 **D30 위반** vs `TenantResource`=**SA+RBAC 새 권한 표면**. 지금은 동작하며 경고만 뜬다(2→1건). **승인 3건**: 실 DynamoDB 왕복 · GCP/Azure 보관 켜기(실 데이터 삭제) · Cosign 어드미션. 그 뒤는 **Phase 4**(managed, billable) 또는 **Phase 5**(레지스트리 쓰기 → D32 재검토 조건). ⚠️**핵심 주의**: 스코프·배포 신원은 **옵트인**이다 — `make scope-credentials`·`make deploy-identity`를 안 하면 인시던트는 전부 거부되고 배포는 ambient(cluster-admin)로 돈다. 묻는 법: `python scripts/probe_scope_reachability.py` · `make deploy-identity-check`. **"설정하면 집행되고, 안 하면 조용히 안 된다"를 "집행된다"로 줄여 쓰지 말 것.** **D39도 마찬가지**: 무스코프 읽기를 닫은 건 "스코프가 강제된다"가 아니라 "스코프 없이는 못 읽는다"다 — 스코프를 넘기는 프로덕션 경로는 아직 없고, `src/`에 `MCPServer` 생성자가 **0**이다. 그 밖의 주의: 카드/스키마/문서에 **집행하지 않는 것을 광고하지 말 것**(배포 신원은 **무엇을**만 좁힌다, **누구의**가 아니다) · 가드는 **파생시켜라, 열거하지 말고** · **읽는 것과 돌리는 것은 다르다** · 푸시/네트워크 신규 필드는 항상 optional+폴백 · 대시보드는 `dashboard/AGENTS.md`대로 **Next 문서 먼저**. **직전 완료**: **결정 2 = D39**(`b062d98`, gate **1605**) — 예외를 붙잡던 **근거가 사실이 아니었다**. "닫으면 검증된 익명 kagent 왕복이 깨진다"였는데 ①그 왕복은 **아웃바운드**이고 `k8s_get_resources`는 **kagent 자신의 도구**다 ②`a2a_server`는 Supervisor로 라우팅한다 ③**`src/`에 `MCPServer` 생성자가 0**이라 무스코프 경로를 실행하던 유일한 코드는 **그것을 고정하던 테스트**였다. 대가는 적어둔 것보다 컸다 — `resource`가 자유 문자열이라 "읽기"가 좁지 않고, 라이브에서 무스코프 `kubectl_get`이 `secrets -n kube-system`·`nodes` 둘 다 성공했다(문서엔 "남의 로그 = 유출"이라 적혀 있었다). 읽기도 기본 거부 + 시끄러운 탈출구. 그 앞은 **결정 5 A·B**(`b92b54e`+`2a21b86`, gate 1596) — **두 경로가 반대 방향으로 고장**이었다: 인시던트는 게이트가 옳은데 **생산자가 테스트뿐이라 열 수 없었고**, 배포는 **가드 없이 cluster-admin**이었다. **세 층에서 같은 결함**: M13=**소비자 없는 필드**, D38=**생산자 없는 메커니즘**, D39=**사용처 없는 예외**. **교훈**: **없는 것은 테스트에서 영원히 초록이다**(무엇이 그 코드를 부르는지 물어야 잡힌다) · **내 가드가 나를 잡았고**(생산자만 생기고 자격증명이 없자 red) **그 가드도 심볼 하나만 봐서 새 생산자를 놓쳤다** · **예외의 근거는 코드로 확인 가능해야 한다**(`tests/test_carveout_consumers_exist.py`). **M13 전체(14건) → `COMPLETED_SUMMARY.md` M13. 교훈 7종**: 가드는 **호출부에서** 반증 · 픽스처는 **실제 입력**에서 · **소비자를 단언하라, 생산자 말고** · **투영/스키마 계층도 소비자**다 · 가드는 **파생시켜라, 열거하지 말고** · **생산자가 여럿이면 다수결이 결함을 가린다** · **수호 테스트 자신이 안티패턴일 수 있다**(5회). 반복 스윕 **양방향**: `scripts/find_unconsumed_fields.py` · `scripts/find_unwritten_keys.py`. 둘 다 **후보≠결함**.
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
- **검증:** `make check` → **1605 passed, 1 skipped** (2026-07-31); **무스코프 MCP 읽기 차단**(D39 — 근거였던 kagent 왕복이 그 경로를 안 쓴다; 라이브에서 무스코프 `kubectl_get`이 secrets·nodes에 닿던 것을 차단); **결정 5 A·B**(배포 신원 축소 + 스코프 생산자 — 라이브에서 축소 신원으로 실 배포·롤백이 되면서 `get secrets -A`는 Forbidden이고, 실 인시던트가 실제로 스코프를 얻는다. **둘 다 옵트인**); **배포 네임스페이스 출처**(행이 착지 ns를 안 적어 네 층이 `"default"`를 발명 → 라이브에서 `rollout undo -n default`가 **엉뚱한 워크로드를 되돌리고 성공을 보고**했다; D36이 세 번째·네 번째 경계에서 살아 있던 것도 함께); **tier 발명 제거**(경계는 `dev`를, 매퍼는 `production`을 발명 → 부재 보존, D36); **리포트 창**(`ttl`을 시각으로 읽어 일일 SLO 24h 창이 보관 전체였다 — 90행 중 90 → 2, 라이브 미실행); **읽기 모델 문서 드리프트**(importer 0인 스키마 문서가 양방향 드리프트 + `ttl`/`GSI1` 거짓 주장 — writer AST 파생 가드로 교체); **롤백 비용 패널**(ACTIVITY writer 셋 중 하나만 `cost_metrics`를 빠뜨렸고 reader가 `{...latest}`라 롤백 시 패널이 통째로 사라졌다 — 라이브 미렌더→`tool calls 5`); **time-to-resolve**(`resolved_at`이 `created_at` 복사본이라 주간 MTTR이 구조적 0.0 · fetch가 한 키를 양쪽 끝에 · 대시보드 투영이 리더가 읽는 4필드를 안 불렀다 → 0.0→45.0, 라이브 1502초); **클라우드 인시던트 필드**(공용 기록기가 `triggered_at`·`confidence`를 버렸다 — 둘 다 읽는 쪽이 이미 있었고, confidence는 float라 그냥 넣었으면 boto3 예외가 `except`에 잡혀 **레코드 전체가 사라졌을** 것) · **인시던트 발생 시각**(행이 '우리가 쓴 시각'만 알아 탐지 소요시간을 못 구했다 — 저장+`detected +Nm` 배지까지, **읽는 쪽 없이 저장만 하면 같은 결함을 하나 더 만드는 것**) · **계통 스윕**(437개 중 20 후보 → **`severity_hint`**를 네 어댑터가 채우는데 아무도 안 읽어, **AUTO/APPROVE를 정하는 축**이 산문에서만 추론됐다. 라이브 A/B: warning이 자동실행→승인대기로) · **온프렘 런북 매칭**(설계 결정인 줄 알았던 게 결함 3개 — `reason`이 `metric_name` 복사본 · `resource_types` 미소비 · 스테일 시드가 **더 나쁜 매칭으로** 빌트인을 가림) · **executor span**(웹훅이 루트 span을 닫은 뒤 실행해서 AUTO·승인 **양쪽 다** 무추적이었다 — 승인은 부모가 아니라 링크) · **grant 레지스트리 대조**(줄 방법 자체가 없었고 역할 변경이 조용히 지웠다) · **선택 불가 런북 4개 + 티어 셰도잉**(시드 테이블의 generic 행 때문에 빌트인 티어가 배포 환경에서 한 번도 도달된 적 없었다) · **Capsule `additionalMetadataList` 이관**; **MCP 게이트웨이 ambient 자격증명 차단**(라이브에서 스코프 안 ns인데도 `secrets`는 **API 서버**가 `Forbidden`) · **테넌트별 call budget**(레지스트리 선언, 미선언=무제한); **Phase 3 완결** — ①자격증명 격리 full(가드 1곳을 세 러너가 공유, 라이브에서 **API 서버가** 이웃 테넌트를 `Forbidden`으로 판정) · ②reconciler가 되돌릴 롤백 거부(out-of-band 변경이 **10초 만에** selfHeal에 되돌려짐을 먼저 실증) · ③읽기 쪽 테넌트 경계(익명 curl → `restricted:true`, fail-open 주입 반증); **자연어 → 테넌트 경계 + 애드온 설치 체인**(`tenancy_tools.py` 2도구, 라이브 브라우저 실검증, 컨텍스트 불일치 시 거부); **아키텍처 배선 ①②**(supervisor 프론트도어 `local_deploy_api` · deploy↔runtime `host` 스텝 `pipeline.py`) + **대시보드 관측 3종 노출**(cost_metrics·reconciliation·consensus/steps) + **레퍼런스 Tier 2 완결(#2·#3·#4) 라이브 실증**(agents-as-tools+self-consistency `orchestration.py` · MCP-over-HTTP+kill-switch `mcp_server.py` · cross-account STS+fallback `adapters/aws_session.py`, 3종 옵트인) + **Tier 1 반영**(reconciliation gate·비용 3단계 게이트·서킷브레이커+readiness·비용 서브메트릭) + **Agent Runtime 호스팅 3/3 클라우드 실 배포 라이브**(AgentCore/Agent Engine/Foundry) + **provisioning 4-provider parity**(GCP/Azure GKE·AKS, AKS 라이브); **On-Prem Day-2 완결**: `onprem_webhook_api` Alertmanager→in-process 4-step + P1 즉시/P2 승인게이트/P3 알림 + **대시보드 Incidents hybrid**(승인 카드 + 타임라인) + **실 executor**(`onprem_runner`, 기본 OFF·`ONPREM_EXECUTOR_LIVE`로 실 kubectl 되돌리기-가능 4조치 restart/undo/**scale**/**polite drain**, kind 라이브 실증) 라이브 실증; Dashboard `next build` 성공; Live 7B provision→deploy→validate ~39s·app/cluster 롤백·hybrid 병합·추적 IA 자연어 4스텝 라이브 실증; **A2A 라이브 E2E**: Phase 1(자체 게이트웨이) + **Phase 2 실 kagent 에이전트**(local Qwen 30B) discovery→JSON-RPC 위임→실 `k8s_get_resources` 진단(2026-07-14).
- **현재 초점:** **Phase 3 완결(M12) + 결정 5(D38)로 집행 가능해짐 — 단 옵트인**(`STATUS` Risk 3) + **차단 없는 잔여 소진**(M13, 14건). 남은 잔여는 **작업이 아니라 결정** 2건(Capsule `limitRanges` 경로 · k3s proven 게이트) 뒤 **Phase 4/5**. 발행 3종(Notion 전문 · YouTube Shorts · LinkedIn)은 **전부 완료**(2026-07-28), 레포 원고 동기화만 잔여. **자연어 한 문장이 테넌트를 세운다** — 에이전트 mutating 범위는 테넌트 스코프까지고 공유 스택 9개는 TF 소유(D30). 시연은 `make dev-up` → `make demo-baseline` 두 줄로 재현되고, 격리 반증(netpol 1개 삭제 → network 축만 ✕ → 복구)까지 실증됐다. 대시보드가 멀티테넌시를 관제하고(플릿 표+격리 4축), 검증은 훅으로 강제된다(Stop→make check, PostToolUse→tsc). Phase 2 완결 — 소프트 티어 격리가 네 층(네임스페이스·쿼터·데이터플레인·자격증명)에서 라이브 실측됨. 소프트 티어는 이제 네임스페이스+쿼터(Capsule)에 더해 **데이터플레인 격리**까지 실측됐고(same 통과/cross 차단/kubelet·DNS 무영향), 2축 상태는 각 클러스터의 **push**로 모인다(허브 read 자격증명 0). Phase 1b rollouts-demo 이관 완료(stateful 3건은 스냅샷 선행). 런북은 **선언한 순서·조건·검증대로 실행**된다. 관측성은 metrics+logs+**traces** 삼각(OTel→Tempo). 과금 가드 3중(모두 report-only). 공급망: PSS restricted 기본 ON + Cosign 검증 게이트(어드미션 집행은 미도입, 의도적).

## Guardrails

- 에이전트=Python 3.11 / IaC=CDK TS / 모델은 `src/agents/models.py` 한 곳.
- IAM 최소 권한(`Resource:"*"` 금지), `Delete/Drop/Terminate` 액션은 강제 APPROVE.
- 요청 이상 기능 추가 금지. 테스트 통과 전 완료 선언 금지.
- Gate 명령: `make check`.

## Skills (overnight-harness)

- `/sync` — Read Path 따라 상태 복원(읽기 전용).
- `/checkpoint` — PROGRESS_LOG append + current docs 갱신.
- `/tidy-docs` — 문서 정리/압축.
- `/overnight-report` — 루프 결과 리포트.
- `/overnight-seed` — backlog 시드.
- `/diagnose` — 루프 실패 진단.
