# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-18

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-17 — 차트 k3s substrate 스모크: env×substrate 양축 실증 완결 (코드 무변경, gate 842 유지)

- Status: 마지막 선택 소품 수행. **기존** Multipass `k8s-lab`(k3s v1.31.4, Ansible 프로비전 자산) 재사용 — 클러스터 생성 없음, 릴리스 설치→검증→제거·반입 이미지 정리로 VM 원상 복원.
- Changed: `docs/evidence/helm-k3s-substrate-smoke.log`만.
- Verified (라이브): 이미지 tar 전송→`k3s ctr import`(199MB; exec-stdin 스트림은 EOF라 tar 경로가 정석) → `helm install -f values-k3s.yaml` → pod 1/1 Ready ~29s → **PVC가 `local-path`로 Bound**(k3s 오버레이의 핵심 검증; kind는 `standard`) → `/health/ready` 200 → Alertmanager 페이로드→P2 parking(APR-0515026F)→approve→INC-3219D4A8 resolved → uninstall·이미지 제거. **동일 차트가 kind/k3s 양 substrate에서 오버레이만 바꿔 동일 동작 — 레퍼런스 #7 env×substrate 레이아웃 양축 실증 완결.**
- Blockers: 없음.
- Next: **자율 백로그 전면 소진.** 잔여=전부 사용자 게이트(아티클 배포·OAuth 데모·Slack App·terraform apply).

## 2026-07-17 — 차트 State Store 배선(④↔#7 연결 마무리): stateStore values + DSN 멀티-레플리카 모드 (gate 839→842)

- Status: ④(SQL State Store)와 #7(Helm/Terraform)을 잇는 마지막 소품. 차트가 DSN 모드를 1급 values로 지원 — JSONL 기본값 무변경.
- Changed: (1) `values.yaml` `stateStore.{dsn,existingSecret,secretKey}` — **existingSecret(secretKeyRef)=프로덕션 경로**(values에 평문 DSN 금지), plain `dsn`=dev/kind 편의, secret이 plain보다 우선. (2) `_helpers.tpl` `stateStoreEnv`+`strategy`(persistence off→**RollingUpdate**, JSONL RWO일 때만 Recreate) — webhook/router 양쪽 주입. (3) **`infra/onprem/Dockerfile` `.[state]` 설치**(psycopg2 — 없으면 DSN 모드 이미지가 실동작 불가, 재빌드+import 검증). (4) README 2종: 차트=DSN 모드 사용법(라이브 증거 링크), Terraform=`kubectl create secret`+`stateStore.existingSecret` 스니펫(extraEnv 핵 대체). (5) 차트 가드 +3: 기본=DSN env 부재·dsn/secret 모드(secret 우선·평문 무노출)·**DSN 모드=PVC 없음+replicas 2+RollingUpdate**.
- Verified: helm lint 통과, `make check` → **842 passed, 1 skipped**(234.42s, 839→842). 이미지 재빌드 후 `import psycopg2` OK.
- Blockers: 없음.
- Next: 자율 백로그 소진. 잔여=사용자(아티클 배포·OAuth·Slack·terraform apply)·선택(k3s 스모크).

## 2026-07-17 — 레퍼런스 #7-b Terraform 모듈(EKS/Aurora/IRSA) → #7 전체 완결 (gate 834→839, apply 없음·spend 0)

- Status: 레퍼런스 #7 잔여 Terraform 파트 구현·오프라인 검증(사용자 승인 "다음 수행"). apply는 하지 않음(billable=사용자 게이트). 이로써 **레퍼런스 #7 = Helm(#7-a)+Terraform(#7-b) 전체 완결** — AWSome AI Gateway 레퍼런스 8항목 전부 소화(Tier 1 4종+Tier 2 3종+#7).
- Changed: 신규 `infra/terraform/aws-production/`(7파일) — VPC(2AZ·public/private·NAT 1) + EKS 1.31(managed node group, AWS-managed 정책만 ARN attach) + **Aurora PostgreSQL Serverless v2**(min 0.5 ACU·`database_name=platform_state`=④ `PLATFORM_STATE_DSN` seam 정합·`manage_master_user_password`=Secrets Manager, 평문 무노출) + **IRSA**(OIDC provider+차트 SA 전용 trust[sub+aud]·**유일 grant=DynamoDB activity 테이블 정확 ARN**+index, deploy_recorder가 실 소비자) + outputs(DSN 템플릿·IRSA arn·helm 배선 스니펫 README). Redis/Cognito는 **미소비라 의도적 제외** 명시. `tests/test_terraform_module.py` +5(구성 완비·**bare `"*"` 금지**[주석 제외]·state seam 정합·IRSA trust 스코프·validate[init 시]).
- Verified: `terraform init`+`fmt -check`+**`validate` Success**(크레덴셜/spend 0). `make check` → **839 passed, 1 skipped**(238.51s, 834→839). ARCHITECTURE 표 #7 ✅.
- Blockers: `terraform apply`=billable(EKS ~$0.10/h+노드+NAT+Aurora) — 사용자 게이트.
- Next: 자율 코드/인프라 백로그 재소진 — 잔여는 사용자 몫(아티클 배포·OAuth·Slack·apply류) + 선택 소품(k3s 스모크·차트 DSN values).

## 2026-07-17 — 로드맵 ④: SQL State Store(옵트인) + 실 Alertmanager 라이브 E2E — 멀티-레플리카 실증 (gate 829→834)

- Status: ARCHITECTURE 잔여 ④(On-Prem State Store·Alertmanager 실연동)를 로컬 docker($0)로 완결. JSONL 단일-writer 제약(Helm 차트 replicas:1의 근거)을 푸는 productionization seam.
- Changed: (1) 신규 `src/agents/ai/state_store.py` — `SQLStateStore`(DB-API connect 주입·placeholder/autoincrement 파라미터·append-only+latest-wins=JSONL 시맨틱 동일)·`from_dsn`(postgresql→psycopg2, sqlite://→stdlib)·`configured_store`(`PLATFORM_STATE_DSN` 옵트인, 미설정=None=JSONL 무변경). (2) `onprem_approvals`/`onprem_incidents` 읽기·쓰기 양쪽에 seam 배선. (3) pyproject `state = ["psycopg2-binary>=2.9"]` extra. (4) `tests/test_state_store.py` +5(sqlite 오프라인: 시맨틱·라우팅·JSONL 비오염 양방향).
- Verified: `make check` → **834 passed, 1 skipped**(242.90s, 829→834). **라이브 E2E**(docker postgres:16 + prom/alertmanager:v0.28.1): ① **실 Alertmanager가 자체 grouping 후 native 페이로드 배달**(손 페이로드 아님)→4-step→P2 parking→**PostgreSQL row**. ② **레플리카 2개**(동일 DSN, 별개 프로세스): replica-2가 pending 조회·**승인 실행**→replica-1 즉시 pending 0+incident 반영(JSONL 불가능한 것). ③ 양 프로세스 kill→재기동→상태 생존. ④ psql ground truth 3 rows(pending→approved append-only→incident). 전량 teardown. 증거 `docs/evidence/state-store-alertmanager-live.log`.
- Blockers: 없음. Helm 차트에서 DSN 설정 시 replicas>1 해금(차트 values 배선은 후속 소품).
- Next: #7-b Terraform 모듈(클라우드=승인) or 사용자 항목(아티클/OAuth/Slack).

## 2026-07-17 — 레퍼런스 #7-a Helm 차트 kind 라이브 실증 (코드 무변경, gate 829 유지)

- Status: 방금 만든 차트를 전용 kind 클러스터(`pa-helm`)에 실 `helm install`로 end-to-end 실증(사용자 승인). 외부 GKE 컨텍스트 불가침(전 kubectl `--context` 핀), 실증 후 전량 teardown + 원 컨텍스트 복원.
- Changed: `docs/evidence/helm-kind-live-install.log`만(코드 무변경).
- Verified (전부 라이브): (1) `kind load`+`helm install` → deployed·NOTES 정상. (2) webhook pod **1/1 Ready ~12s**(strict `/health/ready` readiness in-cluster 그린)·PVC Bound 1Gi. (3) **RBAC 최소권한 auth can-i 실증**: SA로 patch deployments/get replicasets/patch scale=**yes** · patch nodes/delete pods/create pods\/eviction/delete deployments=**no**(drain off 기본). (4) **Day-2 E2E**: 실 Alertmanager 페이로드 POST → in-pod 4-step(휴리스틱 폴백, Bedrock creds 무=설계) → **P2 APPROVE parking**(APR-284A4249) → `/pending`→`/approve` → executed+resolved(INC-5D000FBD) → `/incidents` 기록. (5) **PVC 영속성**: pod 삭제→새 pod가 동일 인시던트 서빙.
- Blockers: 없음. 잔여=#7 k3s substrate 스모크(선택)·#7-b Terraform 모듈(클라우드=승인).
- Next: ④ State Store/Alertmanager 실연동(로컬 docker) or #7-b or 사용자 항목(아티클/OAuth/Slack).
