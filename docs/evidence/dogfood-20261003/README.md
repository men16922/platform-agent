# 단일 환경 실사용 점검 — 2026-10-03

상태: **후보 D의 정상 3회·응답 유실 2회·수동 복구 2회·제한 신원 거부 2회 확인. 진단 품질은 부분 판정.** 최신 근거는 [최종 비교·재현 절차](#최종-후보-d--비교와-재현)와 `repeats/final-candidate-verification.json`이다. 마지막 workload 관측은 2026-10-03 06:51:31 UTC, r0/revision 27/replicas 2/health 200. 아래 앞부분은 단계별 당시 기록이며 현재 상태를 덮어쓰지 않는다.

## 후보와 실행 범위

- HEAD `445d48d`와 현재 WIP에서 소스 523개를 별도 경로로 복사했다. 경로·SHA-256은 `candidate-before.manifest.json`, 이번 수정 파일은 `changed-source-sha256.json`에 있다. `.env`, 키, 기존 실행 데이터, 의존성/빌드 산출물은 복제하지 않았다. 설치된 의존성은 명시한 경로로 재사용했으므로 새 설치 재현은 아니다.
- 실행 위치: `_workspace/dogfood-20261003/candidate-before` / `candidate-after`. 기존 작업 파일과 lab/App/PR/키는 보존했다. 커밋·푸시·원격 CI·클라우드 배포는 하지 않았다.
- Docker Desktop을 시작하자 기존 kind 노드 3개와 registry가 재개됐다. context는 매번 `kind-platform-agent`로 지정했다. 기존 데모 초기화·삭제 스크립트는 실행하지 않았다.
- 런타임은 소유 PID를 기록한 MLX 18090, proxy 18091, router 8077, Next 3000이며 모두 loopback에 바인딩했다. Python 3.13.5, Node 22.23.3, MLX-LM 0.31.3, 캐시된 Qwen3-Coder-30B-A3B-Instruct-4bit를 사용했다. AWS credential 파일/metadata 탐색은 끄고 local JSONL 모드로 실행했다.
- 기존 `platform-agent-system/platform-agent-deployer`와 `acme-dev-observability/platform-agent`의 2시간 토큰을 권한 0600 파일에 보관했다. 토큰과 auth secret은 증거 묶음에서 제외했다. 재개 시 만료를 확인하고 같은 기존 신원으로 갱신한다. RBAC를 생성하거나 넓히지 않았다.

## R0 관측

| 확인 | 결과 | 근거 |
| --- | --- | --- |
| kind 노드 | 3/3 Ready, v1.34.0 | `r0-observations.json` |
| 대상 후보 | acme/dev, `acme-dev-observability`, 저장소의 `examples/orders-api` | registry와 실제 namespace 조회 |
| 기존 orders-api Deployment/revision | 없음. 따라서 복구 실험의 기준 revision도 없음 | 전체 Deployment 조회 |
| 테넌트 신원 | 자기 namespace 조회 허용, globex Deployment 조회는 실제 Forbidden | `r0-observations.json` |
| 신규 배포 권한 | 테넌트 계정의 Service create 권한은 없음 | SelfSubjectAccessReview 결과. 실제 쓰기 거부 실험은 아직 아님 |
| 공통 deployer | Secret 조회 권한 없음. 테넌트별 자격증명 격리는 제공하지 않음 | 실제 권한 조회 및 기존 ClusterRole |
| 배포 Pod 템플릿 | restricted PodSecurity가 allowPrivilegeEscalation, capabilities, runAsNonRoot, seccomp 누락을 거부 | `pod-security-preflight.json`; **server dry-run**, workload 미생성 |

`baseline-proposed.json`은 미적용 매니페스트다. 현재 정책을 완화하거나 공통 deployer를 테넌트 격리의 증거로 사용하지 않는다. 보안 필드만 채운 대조 Pod는 server dry-run을 통과했다(`pod-security-counterfactual.json`). 기존 Helm 기본값과 같은 UID/GID 10001로 기존 orders-api 이미지를 네트워크 차단·read-only 컨테이너에서 실행해 Flask /healthz 200을 확인했다(`nonroot-image-health.log`). 아직 Kubernetes에서 실행하거나 복구 revision을 만든 것은 아니다. 다음은 기존 Helm 보안 계약을 onprem Deployment 어댑터와 대조해 매니페스트 경로의 누락을 고친 뒤 제한된 실험 workload를 준비하는 일이다. 정상·실패 배포 측정은 그 뒤에 시작한다.

## 재현 → 수정 → 재측정

| 관측한 문제 | 수정 전 | 수정 후 | 근거 |
| --- | --- | --- | --- |
| 빈 기록인데 성공 표시 | 490 checks passing, 4 successful, AWS workflow VALIDATED, 임의 추세·시간 | 기록 0, 관측 없음, 데이터 출처와 실제 기록 상태 표시 | `before-overview.txt`, `after-overview-empty.txt` |
| 실제 Pod 조회가 배포 성공으로 저장됨 | DEPLOY 1 + ACTIVITY 1, service=unknown/success | 동일 요청은 ACTIVITY 1만 저장. 새로고침 뒤 활동 1·배포 0 | `activity.jsonl`, `readonly-after.jsonl`, `after-readonly-reload.txt`, `after-readonly-overview.txt` |
| status 없는 기록이 성공으로 승격 | 표시 fixture 4건 중 성공 2 | unknown 유지, 성공 1. 실패/복구 기록을 성공 목록에서 제외 | `before-missing-status.txt`, `after-missing-status.txt`, `ui-status-fixture-with-unknown.jsonl` |

실제 읽기 요청은 다음과 같았다.

> 읽기 전용 점검입니다. acme-dev-observability 네임스페이스의 Pod 목록을 조회해 현재 상태와 확인되지 않은 점을 한국어로 알려주세요. 생성·수정·배포·삭제·프로비저닝은 하지 마세요.

양쪽 모두 실제 로컬 모델이 `list_pods`를 호출했다. 수정 전 데이터는 보존하고 수정 후에는 별도 activity 파일을 사용했다. 성공·실패·복구·상태 누락을 섞은 화면 검사는 **합성 로컬 데이터**이며 실제 배포 실증이 아니다. 검사 후 실제 조회 기록 파일을 복원했다. 시간과 계획 밖 수동 개입 횟수를 일관된 기준으로 측정하지 않았으므로 속도 개선률은 산출하지 않았다.

## 재현 절차 초안

1. 위 manifest와 수정 파일 SHA를 대조하고 기존 Node 22·Python 3.13·모델 캐시를 확인한다. 기존 `.env.local`이나 ambient 관리자 kubeconfig를 복제하지 않는다.
2. local JSONL과 제한 kubeconfig를 지정해 router와 dashboard를 loopback에서 시작한다. 이번 세션의 allowlist 환경·소유 PID 시작 절차는 `_workspace/dogfood-20261003/start-local.py`, 수정 후보 재개는 `restart-after-owned.py`에 보존했다. 처음 시작할 때는 포트/PID 충돌을 확인한다. 과거 PID를 확인 없이 종료하지 않는다.
3. `http://localhost:3000/agents`에서 Local Dev 로그인 후 위 요청을 실행한다. 이 로그인은 로컬 개발 인증이며 GitHub OAuth 검증이 아니다.
4. Agents를 새로고침해 조회 활동이 남는지 확인한다. Overview/Deployments에는 배포가 추가되지 않아야 한다. 원본 JSONL에는 ACTIVITY만 있어야 한다.
5. 상태 fixture를 별도 local store에 연결해 unknown·failed·success·rolled-back을 확인한다. 성공 목록에는 명시적으로 success인 1건만 있어야 한다. fixture와 실제 관측을 혼합하지 않는다.
6. 실험 데이터와 캡처를 보존하고 소유 프로세스만 종료한다. 기존 kind 클러스터와 자원은 삭제하지 않는다.

## 검증 및 남은 작업

- 새 로컬 파일 회귀: 수정 전 **2 failed, 1 passed** → 수정 후 관련 **18 passed**. 실제 AWS 서비스 mock은 추가하지 않았다. 성공/실패 조회와 조회+실제 배포 도구가 섞인 반례를 검사한다.
- TypeScript `tsc --noEmit` 통과. Chrome에서 빈 데이터·실제 Qwen 요청·새로고침·혼합 상태 fixture를 확인했다.
- 첫 전체 게이트: **3254 passed, 1 failed, 2 skipped**, 117.54초. 새 회귀 3개에 맞춰 문서의 gate 수를 갱신하지 않은 1건이었다. 두 번째는 STATUS 문자 상한 검사 1건만 실패(3254 passed, 2 skipped, 118.67초). 이를 보완한 최종 `make check`는 **3255 passed, 2 skipped, 21 warnings**, 121.61초(`gate-verified.log`). 원격 CI 결과가 아니다.
- R0 배포 baseline 미준비: PodSecurity 호환 설정, 새 실험 서비스의 최초 정상 revision 확보, tenant 계정의 create 불가와 공통 계정의 격리 한계를 실행 범위에 명시해야 한다.
- R1/R3 정상 배포 3회·거부/복구/응답 유실 각 2회, scope/승인 거부, 실제 서비스 health, 복구 시간, 중복 실행, 60~90초 데모는 미완료다.
- 실제 모델 응답에는 반복 문장·혼합 언어·근거를 넘는 추측이 관측됐다. 또 Agents의 고정 kagent READY 표시는 실제 위임 여부를 증명하지 않는다. 이들은 별도 재현·수정 후보이며 이번 세 가지 수정의 완료 범위에 포함하지 않았다.

## 후속 실행 — Pod 보안과 긴 작업 스트림

- 온프렘 배포 템플릿에 restricted 정책의 non-root/seccomp/권한 상승 금지/capability 제거를 반영했다. 애플리케이션 UID는 이미지의 숫자 USER를 따른다. platform-agent 전용 Helm UID를 모든 앱에 강제하지 않는다. `examples/orders-api/Dockerfile`은 USER 10001:10001을 지정한다. 기존 회귀에 실제 admission 요구사항을 추가해 1 failed→통과를 확인했고, 수정된 생성물의 Pod server dry-run도 통과했다(`pss-after.json`).
- 외부 python base metadata를 기다리던 최초 빌드는 소유 프로세스를 확인한 뒤 종료했다. 기존 로컬 orders-api:v1.4.2 이미지에 현재 app.py와 USER를 반영한 **검증용 오프라인 context**로 `docker build --network none --pull=false`를 실행했다. 이는 정식 Dockerfile의 깨끗한 외부 의존성 설치 검증이 아니다.
- 후보 `localhost:5001/orders-api-dogfood:r0`: image ID `sha256:51915981952d0204d0a8964acfd23cb9905e56bce46bc79a34bced1f3f2e5496`. USER 10001:10001 내장. 네트워크 차단·read-only·cap-drop ALL·no-new-privileges 컨테이너에서 실제 Flask health 200을 확인했다. registry push와 kind 배포는 아직 하지 않았다.
- 15초 SSE heartbeat의 `wait_for(__anext__)`가 느린 실행을 취소하는 결함을 로컬에서 재현했다. 시간만 줄인 회귀에서 started=1/completed=0/cancelled=1. 모델 실행은 한 producer task 안에서 유지하고, bounded queue 소비에만 heartbeat timeout을 적용했다. 이벤트마다 새 task를 만드는 첫 수정은 AnyIO scope 소유권 검사를 실패해 폐기했다. 최종 관련 검사 **45 passed**에는 실제 Pydantic AI TestModel 스트림, 여러 heartbeat 뒤 완료/기록, close 후 pending 정리가 포함된다. 고객 연결 유실 이후 durable resume까지 해결했다는 뜻은 아니다.
- 최종 전체 게이트: **3257 passed, 2 skipped, 20 warnings**, 119.91초(로컬 macOS·Python 3.13.5·Node 22.23.3/임시 npm prefix), `runtime-gate.log`. 원격 CI/실제 배포 확인은 아니다.
- 수정 후보와 테스트 해시는 `runtime-source-sha256.json`, 수정 전후 로그는 `pss-regression-*.log`, `heartbeat-before.log`, `runtime-regression.log`다. 실행 중인 router에는 아직 새 후보를 재시작 반영하지 않았다.

## 후속 실행 — 관측 연결 유실과 요청 ID

- 수정 전 실제 로컬 thread/file 작업은 SSE 관측을 닫은 뒤에도 끝났지만 실행 기록은 없었다. `disconnect-before.json`이 관측 결과다. 이는 AWS/Kubernetes mock이나 실제 배포가 아닌 로컬 전송 수명 재현이다.
- 기존 `SQLStateStore`에 요청 ID claim과 초기 상태를 한 transaction으로 기록한다. claim 성공 뒤 background task를 만들며, SSE는 그 작업을 관측한다. 동일 ID 재요청은 추가 dispatch 없이 기존 결과를 읽는다. 같은 ID의 다른 입력은 409, 다른 actor의 조회/재요청은 404다.
- 프로세스가 사라졌거나 결과를 저장하지 못하면 `unknown`으로 남긴다. lease takeover·자동 재시작은 없다. 완료를 저장하지 못한 경우 `done`을 성공 증거로 내보내지 않는다. 현재 단일 loopback 프로세스 대상이며 다른 worker에서 실행 중인 요청도 확인 불가로 본다. PostgreSQL의 실동작·복수 worker 복구를 입증하지 않았다.
- `PLATFORM_STATE_DSN`을 재사용한다. 없으면 명시적 `PLATFORM_ACTIVITY_FILE` 옆의 `.runs.sqlite3`(새 파일 0600)를 사용한다. 둘 다 없으면 새 managed 요청은 503으로 거부한다. 이 DB에는 요청/도구 출력이 있으므로 evidence/public 소스 묶음에 넣지 않는다. 기존 ID 없는 직접 stream/sync API는 호환용이며 이 보장을 제공하지 않는다.
- Dashboard POST는 request UUID를 요구하고 actor는 인증 세션에서만 전달한다. GET `/api/dashboard/agents/runs/[id]`도 세션/역할을 검사한다. 브라우저는 사용자별 sessionStorage에 ID만 보관하며, 새로고침/연결 단절은 GET으로 복구한다. unknown은 작업 상태와 원래 worker 종료를 확인했다는 명시적 확인 후 새 ID 요청을 허용하며 이전 unknown 기록은 바꾸지 않는다. 브라우저 탭/저장소를 잃으면 알려진 ID로 수동 조회해야 한다.
- **actor header는 router의 인증 기능이 아니다.** 기존 trusted loopback 경계에 의존하며 원격·멀티테넌트 인증을 구현했다는 주장은 하지 않는다. UI의 새로고침/역할 변경/단절 동작은 실제 브라우저에서 아직 재검증하지 않았다.
- 수정 후 동일 thread/file 재현은 결과 기록·조회 succeeded, 같은 ID 재요청 뒤 effect count=1(`disconnect-after.json`). 실제 SQLite 다중 연결 claim, 입력/actor 불일치, 종료·저장 실패 unknown, 실제 Pydantic AI TestModel scope, TS trace 재생·세션 proxy 계약을 확인했다. 새 12개 포함 관련 27 passed, tsc 통과. 새로운 서버/포트를 열거나 기존 네트워크 거부를 우회하지 않았다.
- 새 소스 해시는 `durable-run-source-sha256.json`이다. 이전 `runtime-source-sha256.json`은 앞선 heartbeat/PSS 검증 시점의 기록이며 최신 전체 후보 해시가 아니다. 현재 runtime에는 이번 managed-run/UI 코드가 반영되지 않았다. 전체 게이트 **3269 passed·2 skipped·20 warnings**, 118.07초(로컬 macOS·Python 3.13.5·Node 22.23.3/임시 npm prefix)는 `durable-run-gate.log`에 보존했다. 원격 CI 결과가 아니다.
- 승인 후 추가 순서: 새 소스를 격리 후보에 반영 → 소유 PID만 재시작 → 실제 읽기 요청 중 탭 새로고침/연결 유실 및 동일 ID 결과 조회 → 로컬 실험 Deployment 시나리오. 이 오프라인 재현을 R3의 실제 배포 유실 2회로 세지 않는다.

### 다음 실제 실행의 검토 가능한 범위

자동 승인 심사가 `curl http://127.0.0.1:8077/health`와 제한 kubeconfig의 Deployment 조회가 포함된 명령을 거부했다. 사유는 **"Network access is outside the default unattended loop."**였다. 다른 도구·경로로 그 접근을 우회하지 않았다. 다음 실증에는 이 네트워크 경계의 명시적 확인이 필요하다.

- 대상: 기존 `kind-platform-agent`, `acme-dev-observability`의 **새 `orders-api-dogfood` Deployment/Service 각 1개**, 기존 registry의 동명 실험 이미지 태그. 기존 운영/다른 테넌트 workload는 변경하지 않는다.
- 통신: loopback dashboard/router/webhook/MLX/proxy/registry/health forward(3000, 8077, 8078, 18090, 18091, 5001, 18092), 기존 kind API `https://127.0.0.1:53451`, 그 클러스터의 로컬 Docker 네트워크. 외부 클라우드/유료 API/새 외부 이미지 다운로드는 포함하지 않는다.
- 순서: 현재 context·신원·자원 부재 재확인 → 후보 push → 제한 deployer로 baseline apply → 실제 rollout/health와 revision 기록 → 정상 3회·거부/실패 복구/응답 유실 각 2회 초기 검증. 관련 로컬 서버는 소유 PID만 확인해서 재시작한다.
- 제어: Secret/RBAC 권한 확대 없음. 공통 deployer의 테넌트 격리 한계 명시. 실패 주입은 동명 실험 Deployment에만 하며 알려진 정상 revision으로 복원한다. 기존 namespace/클러스터/자원/키는 삭제하지 않는다. 중단 시 실험 상태와 소유 프로세스 기록을 보존한다.
- 완료 판정: 실제 health·revision과 UI/API 일치, 범위 밖 변경/중복 실행/거짓 성공 0, 근거 연결, 재현 절차·전후 비교·짧은 데모. 현재는 이 판정 전이며 전체 목표가 끝난 상태가 아니다.

동일 네트워크 승인 경계가 3개 goal 턴 연속 남아 blocked 전환 기준을 충족했다. 현재 소스 해시 9개와 완료 조건을 재대조한 결과는 `blocker-audit.json`에 있다. 추가 승인 답변은 없으며 실제 배포·복구·반복 측정·최종 데모는 미완료다. 재개 범위는 바로 위 실행안이다.

## 로컬 실증 승인과 심사 규칙 확인

2026-10-03 사용자가 기존 로컬 실증 범위를 명시 승인했다. 같은 승인 질문을 반복하지 않는다. 거부 문구의 출처는 project `.codex/rules/overnight.rules`의 모든 curl을 금지하는 prefix rule이었다. 사용자 요청으로 그 규칙만 제거하고 TextEdit로 열었다. 새 blanket allow 규칙은 추가하지 않았다. 디스크 정책 검사 9건에서 localhost curl은 매칭 규칙 없음, 나머지 금지 8건은 유지됐다. 무인 Codex runner는 별도로 `sandbox_workspace_write.network_access=false`를 적용한다.

실제 동일 curl은 현재 세션에서 옛 사유로 다시 거부됐다. [공식 규칙 문서](https://learn.chatgpt.com/docs/agent-configuration/rules)는 시작 시 로드와 Codex 재시작을 명시한다. 따라서 남은 차단은 사용자 승인이 아니라 실행 세션의 규칙 재로드다. 근거는 `network-approval-and-policy.json`. 재로드 뒤 기존 로컬 실행안대로 소스/신원/자원·소유 PID를 확인하고 진행하며 Phase 5 원격·Phase 4b 승인을 합치지 않는다.

## 승인 후 실제 실행과 해석 정정

curl prefix 금지를 모든 로컬 네트워크 작업의 금지로 확대한 해석은 잘못이었다. 기존 curl 재시도는 같은 규칙으로 거부됐지만, 사용자 승인 후 원래 계획한 별도 kubectl 조회·토큰 갱신·Docker registry push·대시보드 UI 흐름은 허용되어 실행됐다. 전체 목표를 curl 재로드 대기로 세우지 않는다. 같은 사용자 승인을 다시 묻지 않는다.

- 기존 제한 SA 2개의 만료 토큰만 같은 2시간 범위로 갱신했다(0600, `identity-refresh.json`). RBAC 변경은 없다. 소유 router/dashboard PID만 확인·종료 후 새 후보 13파일을 반영했다(`candidate-activated.json`). 현재 PID는 `approved-runtime-verification.json`에 있다.
- 준비한 이미지 r0와 같은 digest의 r1 태그를 localhost registry에 push했다. 새 실험 Deployment/Service 각 1개를 만들었고 r0 revision 1·1/1 Running으로 기준점을 확보했다. 이후 실제 Qwen 요청은 deploy_to_cluster/validate_deployment 각 1회로 r1·replicas 2를 적용했다. 같은 workload UID, revision 2·2/2 Running·두 Pod의 실제 /healthz 200 로그를 확인했다. 단순 rollout 통과를 서비스 health 확인으로 대신하지 않았다(`r0-deployment-live.json`, `r1-deployment-live.json`, `r1-health-observation.log`).
- 정상 요청 `f1558add-0412-41d8-85b5-bffee5913303`은 DEP-102149DB/ACT-6BEC4FA3에 연결된다. Chrome 새로고침 뒤 r1/success 기록이 유지된다. 준비된 이미지 적용 실험이며 새 외부 dependency build 검증은 아니다. 모델 실행 중 별도 shell 개입은 없었다. baseline/이미지 준비는 수동 사전 준비다.
- 읽기 요청 `b645f9e8-be11-4e12-b1b0-e2971cfd67eb` 실행 중 실제 페이지 새로고침을 수행했고 같은 ID의 완료 결과를 조회했다. list_pods/describe_deployment 각 1회만 기록됐다. 수정 전 UI/오프라인 증거와 함께 보되 R3의 실제 배포 유실 2회를 완료한 것으로 세지 않는다(`managed-read-refresh.txt`/jpg, `live-run-*.json`).
- 서버의 durable acceptance→최종 저장 구간은 읽기 9.311초, 배포 7.342초다. 사용자 클릭→서비스 health 완료 시간과 다르므로 개선률을 만들지 않는다. 배포 표의 0s는 별도 표시/기록 오류로 재현됐다(`r1-deployments-reload.txt`/jpg). 다음 R2 수정 대상이다. 모델의 중복 요약/혼합 언어와 고정 supervisor/kagent READY 표기도 미해결이다.
- 별도 health 포트 브라우저 탐색은 ERR_BLOCKED_BY_CLIENT로 차단됐다. 다른 origin이나 우회 요청을 시도하지 않았고 소유 port-forward(session 16294)를 종료했다. 위 health 증거는 Kubernetes가 수행한 실제 liveness 요청의 애플리케이션 로그다. 브라우저 JSON 응답을 확인했다는 주장은 하지 않는다.
- 다음: 실제 실패 revision→복구 및 거부/배포 유실/근거 부족 검증, duration 기록 수정, 고정 후보 반복 측정·최종 비교표·재현 절차·데모. 목표는 active이며 미완료다. 기존 외부 자원·키·PR 보존과 별도 Phase 5/4b 경계는 유지한다.

## 후속 실행 — 실제 실패·복구와 완료 판정

실제 클릭 시각은 `ui-click-times.json`, 요청·tool 결과·후보 해시는 `completion-and-recovery-verification.json`에 있다. raw JSONL은 `activity-completion-after.jsonl`, 요청별 원본은 live-run-<UUID>.json이다.

| 관측 | 수정 전 | 수정 후 | 한계 |
| --- | --- | --- | --- |
| 서버 시간 | 고정 0s | 8.888/68.460/79.187/21.081/15.427/7.410s 원값, 화면 1자리 반올림. 과거는 Not measured | 사용자 클릭부터 health까지의 시간은 아님. 복합 phase 개별 시간과 직접 UI rollback 시간은 미측정 |
| missing-r1 이미지 | revision 3/ImagePullBackOff인데 SUCCESS, 모델이 validate 호출을 생략 | 동일 요청 revision 5에서 FAILED. apply 성공 뒤 adapter가 rollout timeout을 직접 확인 | 작은 로컬 표본, 외부 cloud adapter 검증 아님 |
| 잘못된 ports 문자열 | 실제 도구 미실행 + 기존 배포 healthy를 SUCCESS로 합산 | 같은 문자열을 RetryPromptPart 오류로 보존, FAILED·실제 revision/generation 불변 | 모델 입력/설명 품질 자체를 해결한 것은 아님 |
| 적용 후 실패 복구 | 실패 행에 Rollback 없음 | applied=true인 on-prem 실패 행에 버튼, DEP-ED8855BD에서 실제 UI rollback→revision 6/r1/health 200 | kubectl undo는 replica 수를 복원하지 않음. 별도 정상 요청으로 2개를 복원 |

- 실제 복구의 실패 이력과 rolled-back 행은 새로고침 후 유지된다(`recovery-after-reload.txt`, `recovery-after-screen.png`). 실패 후 복구 버튼은 적용 전 build/signature 실패에는 열지 않는다. 기록에 적용 증거가 없는 과거 실패 행도 자동 승격하지 않는다.
- 정상 복원 요청 0b348cc2는 ports 기본값을 사용했다. deploy_to_cluster의 자체 rollout 확인이 성공해야 SUCCESS를 반환한다. 별도 validate 도구가 병렬로 먼저 끝나더라도 이 확인은 생략되지 않는다. 최종 실제 2/2·r1은 `normal-restored-deployment.json`, health 200은 `normal-restored-health.log`다.
- 기존 서버/키/RBAC/클라우드 경계는 유지했다. 소유 router/dashboard만 중지·반영했으며 후보 변경은 duration/completion/recovery-ui/validation-candidate.json에 순서대로 기록했다.
- 회귀: duration 4 failed→21 passed, apply/undo 2 failed→55 passed, 인자 검증 2 failed→74 passed. 최종 전체 `make check` **3277 passed, 2 skipped, 20 warnings**, 131.37초(`validation-gate.log`), TypeScript 통과. 앞선 실패 2종과 보완 과정은 duration-gate.log/completion-gate.log에 남는다.
- 남은 실증: 고정 후보 정상 3회·거부/복구/배포 응답 유실 각 2회, 근거 부족/승인 거부/수동 runbook 비교, 최종 재현 절차와 60~90초 데모. 수정 중 재실행을 고정 후보 반복으로 세지 않는다. 모델은 인자를 생략하거나 배열을 문자열로 만들었고, 근거를 넘는 설명/반복도 보였다. R4 사례 후보로 보존한다.


## 최종 후보 D — 비교와 재현

후보 A는 모델이 replicas 2를 생략했고, B는 이미지 URI를 오타 냈다. A의 정상 반복을 최종 성공 표본으로 합산하지 않았다(`repeats/candidate-ab-verification.json`). 기존 Deployments 화면에서 **입력 → 검토 → 확인**한 값을 strict 요청으로 기존 실행기에 전달하도록 고쳤다. 같은 UUID는 저장 결과를 조회하며 자동 재실행하지 않는다. 직접 실행은 On-Prem Executor로 기록한다. 후보 C에서 발견한 롤백의 Qwen 오표기도 D에서 수정했다.

- 후보: `repeats/candidate-v4.json`의 런타임 소스 283개 해시. HEAD만의 결과가 아니라 WIP를 포함한 격리 export다. 현행 작업 파일과 export 일치는 `repeats/v4-runtime-restored.json`에 기록했다.
- 검증: `repeats/final-candidate-gate.log` — **3283 passed, 2 skipped, 20 warnings**, 123.69초(2026-10-03 로컬 macOS·Python 3.13.5·Node 22.23.3/임시 npm prefix). 원격 CI나 production 검증이 아니다.
- 총괄: `repeats/final-candidate-verification.json`; 각 `v4-*-run.json`에 요청 ID·claim·실제 도구 인자·결과·기록 연결을 보존했다. 정상 세 건의 claim/배포 도구 호출은 각각 1회다.
- 데모: [72초 실제 화면 해설 영상](demo/local-evidence-walkthrough-72s.mp4). **정지 화면을 편집한 영상이며 연속 녹화가 아니다.** 재생 시간은 작업 시간이 아니다. 새로고침 장면은 결과 화면을 재사용하고 실제 전후 기록은 `v4-normal2-loss1-*`/`v4-normal3-loss2-*`에 있다. storyboard·빌드 스크립트·화면 검수·해시는 `demo/`에 있다.

### 전후 비교

| 관측 대상 | 수정 전 | 최종 후보 D | 근거·한계 |
| --- | --- | --- | --- |
| 입력 보존 | A: replicas 누락 → 1, B: 이미지 URI 오타 | 정상 3회 모두 검토한 이미지·namespace·replicas 2 유지 | `candidate-ab-verification.json`, `v4-normal*-run.json`. 준비된 이미지 실행 경로이며 자연어 배포 전체 개선 주장이 아님 |
| 계획 밖 개입 | A 복구 후 replicas를 다시 요청해야 했고 B 이미지 오타를 복구함. 당시 개입 전체 횟수는 미계측 | 정상 3회에서 재입력·수정 shell 개입 0. 입력/검토/확인과 읽기 전용 관측은 예정 단계 | 최종 실행당 배포 도구 1회. 후보 전환·초기 환경 준비 시간을 숨겨 정상 작업시간에 합산하지 않음 |
| 성공의 의미 | ImagePullBackOff 또는 도구 인자 오류인데 SUCCESS | 없는 태그 2회 모두 FAILED, apply/rollout 결과 구분 | `completion-and-recovery-verification.json`, `v4-failure{1,2}-run.json` |
| 복구 | 이전 image로 돌아가도 replicas 1이면 목표 상태 미복구 | 사용자 확인 롤백 2회: r0, replicas 2, health 200 | `v4-recovery{1,2}-observation.json`. 자동 복구 실험이 아님 |
| 응답 유실 | 실행은 끝났지만 기록 유실 | 실제 새로고침 2회에서 같은 UUID 조회, 배포 중복 0 | `v4-normal2-loss1-*`, `v4-normal3-loss2-*` |
| 권한 거부 | 공통 deployer는 테넌트 격리되지 않음 | 기존 acme 제한 SA로 globex 2회 Forbidden, UID/spec 불변 | `v4-denial-runtime.json`, `v4-denial*-resources.json`. 공통 deployer 격리 증명이 아님 |
| 검토 취소/범위 누락 | 해당 최종 입력 흐름 없음 | namespace 누락은 브라우저 검증, Review 취소 시 claim 29→29·workload 불변 | `v4-review-cancel-verification.json`. incident 승인 webhook 거부와 별개 |
| 진단 설명 | 유사 증상에서 원인·롤백을 단정 | D에서도 과도한 단정 재현. 오래된 다른 서비스 로그/삽입 지시는 보류 | `v4-lookalike-run.json`, `v4-stale-injection-run.json`. 전체 R3 합격으로 표시하지 않음 |

| 시간 지표 | 원값(초) | 중앙값 / 범위 | 측정 구간 |
| --- | --- | --- | --- |
| D 정상 3회 | 14.157 / 11.798 / 13.129 | 13.129 / 11.798–14.157 | Confirm 클릭 → 실제 current Pod health 로그 관측 |
| 같은 정상 요청의 서버 구간 | 3.817 / 2.773 / 4.294 | 3.817 / 2.773–4.294 | 요청 수락 → 최종 상태 저장. 사용자 완료시간과 다름 |
| D 복구 2회 | 12.045 / 7.884 | 9.965 / 7.884–12.045 | Rollback 클릭 → r0/2개 Pod health 관측 |
| 실패 관측부터 복구 health | 18.419 / 12.385 | 15.402 / 12.385–18.419 | UI 실패를 관측한 시각 → 복구 health; 승인 대기 포함 |
| 수동 CLI 기준 1회 | 명령 3.374 / health까지 12.992 | 표본 1개 | coding assistant가 아래 두 명령을 실행. 사람의 입력·판단 시간 제외 |
| 수동 CLI 원상 복원 1회 | 명령 3.858 / health까지 12.833 | 표본 1개 | r0/revision 27 복원. 비교 성공 표본에 합산하지 않음 |

없는 이미지의 rolling update 동안 기존 건강한 Pod가 남았다. 따라서 위 값을 서비스 중단시간이나 운영 MTTR로 부르지 않는다. 초기 A와 최종 D의 health 관측법도 다르므로 속도 개선율을 계산하지 않았다. Qwen proxy는 usage를 버려 토큰이 **미측정**이다. 직접 실행 경로에는 LLM 호출이 없지만 서버·클러스터 자원은 사용한다.

### 재현 절차 — 기존 로컬 실험 환경

이 절차는 보존된 로컬 WIP export와 기존 kind·캐시·의존성·단기 ServiceAccount kubeconfig가 있는 환경을 대상으로 한다. 새 clone/새 설치 재현은 아직 증명하지 않았다. 기존 lab/App/키/namespace를 삭제하는 demo prep 스크립트를 실행하지 않는다.

1. `candidate-v4.json`의 해시와 export를 대조한다. dashboard 소스와 `src/agents`의 후보가 섞이면 반복 측정을 시작하지 않는다. `_workspace/dogfood-20261003/pids.json`의 PID/명령/작업 디렉터리를 확인한다. 서버 변경이 필요할 때는 이 실험 소유 router/dashboard만 종료한 뒤 `restart-after-owned.py`로 실행한다. 그 스크립트 자체는 기존 PID를 종료하지 않는다.
2. 3000 dashboard, 8077 router, 18090 MLX, 18091 proxy, 기존 registry 5001을 사용한다. local-dev 관리자·데이터 소스 local·cloud 자격증명 비전달 설정이다. 배포 신원은 기존 `platform-agent-system/platform-agent-deployer`, 대상은 `acme-dev-observability/orders-api-dogfood`다. 만료 토큰은 같은 SA/2시간으로만 갱신하며 비밀 값을 기록하지 않는다. 권한 확대는 필요하지 않다.
3. 시작 전 UID/image/revision/replicas와 이전 revision을 확인한다. localhost registry의 r0/r1이 존재해야 한다. 두 태그는 같은 캐시 digest를 가리키므로 **새 앱 바이너리 검증이 아닌 태그 변경 rollout**이다. ports 8080, liveness `/healthz`, replicas 2, env dev를 고정한다.
4. `http://localhost:3000/deployments` → Deploy image에서 Service `orders-api-dogfood`, Namespace `acme-dev-observability`, Image `localhost:5001/orders-api-dogfood:r0` 또는 `:r1`, Replicas `2`, Environment `dev`를 입력한다. Review에서 전부 대조한 뒤 Confirm한다. r0/r1을 번갈아 세 번 수행하고 각 요청 ID/클릭 시각을 저장한다. 두 번째·세 번째는 Confirm 직후 새로고침하여 같은 ID가 복원되는지 본다.
5. 각 정상/복구 뒤 아래 읽기 전용 observer를 새 label로 실행한다. `observedGeneration`·updated/ready replicas·현재 image/UID를 검사하고 **ready 관측 이후** 각 current Pod의 실제 kubelet `/healthz` 200 로그를 기다린다. 예: `python docs/evidence/dogfood-20261003/repeats/observe_workload.py replay-normal1 r1`. observer는 전역 `kind-platform-agent` context의 읽기 권한으로만 관측하며 배포 신원과 구분한다. readinessProbe가 없으므로 rollout 성공만으로 앱 health를 주장하지 않는다.
6. 실패는 같은 입력의 Image만 존재하지 않는 `localhost:5001/orders-api-dogfood:missing-r1`로 바꾼다. 약 60초 rollout timeout 뒤 FAILED/ErrImagePull을 확인한다. 해당 행의 Rollback을 명시 확인하고 이전 r0·replicas 2·health를 다시 관측한다. 이 쌍을 두 번 수행한다. 동일 실패를 자동 재요청하지 않는다.
7. 거부 검증은 소유 router/dashboard를 **기존 acme 제한 SA**로만 전환한다(`DOGFOOD_IDENTITY=tenant`). namespace를 `globex-dev-observability`로 바꾼 요청 두 건이 Forbidden인지 확인한다. 관측자 신원으로 전후 Deployment/Service의 UID/spec을 비교한다. 배포 신원을 공통 deployer로 바꿔 거부를 우회하지 않는다. 검증 뒤 기존 deployer 런타임으로 복원한다. 이는 신원별 실험 변형이며 테넌트 자동 선택 기능이 아니다.
8. namespace를 비우면 Review로 넘어가지 않는지 확인한다. 올바른 값을 채워 Review 후 Cancel하고 새 요청 claim·workload 변경이 없는지 확인한다. 이는 실행 전 취소 증거다. incident webhook의 승인 거부 검증으로 세지 않는다.
9. `diagnostic-cases.json`의 두 근거 부족 입력을 Agents의 Local Qwen/On-Prem에 그대로 제공한다. 도구 호출·자원 변경이 없는지 확인하고, 문장 자체가 사실/추론/미확정을 구분하는지도 읽는다. 좋은 답변만 골라 합산하지 않는다. D의 유사 증상 답변은 부분 판정으로 남겼다.
10. 마지막으로 r0·replicas 2·health를 복원하고 요청/실행/관측 파일을 연결한다. request claim 수와 tool_call 수를 SQLite 및 저장 events에서 대조한다. 실패 이력과 최종 복구 행을 모두 보존한다. 로그·snapshot에는 credential/token을 넣지 않는다.

수동 비교는 같은 기존 deployer kubeconfig로 아래 두 명령만 순차 실행했다. namespace/context를 생략하지 않는다. `KUBECONFIG`는 이 실험의 0600 파일 경로이며 명령 출력에 내용을 표시하지 않는다.

```sh
KUBECONFIG=_workspace/dogfood-20261003/private/deployer.kubeconfig kubectl --context dogfood-deployer -n acme-dev-observability set image deployment/orders-api-dogfood orders-api-dogfood=localhost:5001/orders-api-dogfood:r1
KUBECONFIG=_workspace/dogfood-20261003/private/deployer.kubeconfig kubectl --context dogfood-deployer -n acme-dev-observability rollout status deployment/orders-api-dogfood --timeout=60s
```

관측·명령 원값은 `repeats/manual-baseline-*`이며 r0 복원은 `manual-restore-*`다. 기존 CLI와 새 UI의 가치는 이 작은 표본에서 속도 차이가 아니라 검토 값 보존·실패/복구 이력·같은 ID 결과 복원에서 확인됐다. 일반적인 생산성 우위는 아직 측정하지 않았다.


## 진단 후보 E — 프롬프트 보완만으로는 해결되지 않았다

`repeats/candidate-v5-diagnosis.json`은 D에서 local_deployer의 진단 지침만 바꾼 실험 후보다. 관측·가능한 설명·미확정·다음 근거를 구분하고, 다른 증상만으로 원인 차이나 롤백 타당성을 단정하지 않도록 했다. 실행 도구와 권한은 바꾸지 않았다. D의 배포 반복을 E의 실행으로 합산하지 않는다.

실제 Chrome → local Qwen 요청 4건은 모두 claim 1·도구 호출 0이었다. 유사 증상 입력 두 번은 같은 답변을 냈다. 불확실성을 적는 부분은 생겼지만 첫 문장의 근본 원인 단정이 남았다. 오래된 다른 서비스 로그/삽입 지시 사례는 현 상태와 롤백 판단을 보류했다. 새 반례에서는 “의존성 로그에 문제가 없으면 앱 변경이 원인이며 롤백 가능”이라는 잘못된 연결을 만들었다. **프롬프트만의 수정은 진단 품질 완료 조건을 충족하지 못했다.** 원문과 판정은 `repeats/diagnosis-candidate-verification.json`에 있다. 네 번은 독립적인 통계 표본이나 모델 간 비교가 아니다.

전체 `make check`는 **3283 passed, 2 skipped, 20 warnings**, 119.38초(10-03 로컬 macOS·py3.13.5·Node22.23.3/임시prefix), 관련 24 passed다. 코드 게이트 통과와 진단 답변의 품질 실패를 함께 기록한다. E는 미완료 실험 후보이며 완료된 진단 수정으로 승격하지 않는다. 진단 사례는 새 반례를 더해 6개다.

다음 R4 변경은 기존 결과/평가 계약 안에서 **출처 있는 관측과 모델의 미검증 가설을 분리**하는 것이다. 관측은 tool result/snapshot의 source ID·대상·시각과 연결하고, 모델이 이를 새 사실로 다시 쓰거나 현재 관측으로 승격하지 못하게 한다. 존재하지 않는 출처·다른 대상·오래된 snapshot의 현재 상태 주장은 코드 검사 대상으로 삼는다. 유효한 source ID를 붙였다는 사실만으로 문장 의미가 입증되지는 않으므로 설명의 인과관계 검토는 별도로 남긴다. 롤백은 현재 상태·변경 이력·이전 revision의 실행 가능 근거가 있는 기존 검토/승인 경로에서 판단한다. 새 진단 엔진이나 자동 조치 권한을 추가하지 않는다.

### 별도 승인 거부 화면 검증 — 07:06 UTC 당시 미완료 기록

실제 Incidents → Reject → 로컬 webhook 경로를 확인하려고 격리 store에 합성 pending 두 건(`APR-7D95B306`, `APR-52AF4AE1`)을 만들었다. 화면에 합성 실험임을 표시했으며 실제 장애 감지나 원인 분석을 거쳤다고 주장하지 않는다. 소유 webhook은 127.0.0.1:8078, 로컬 후보 E, cloud 자격증명 비전달이다.

Reject의 기본 브라우저 입력창 처리가 완료되지 않았고, 이후 네이티브 Chrome에서 사용자 작업 전환이 감지되어 UI 조작을 멈췄다. 07:06:28 UTC 기준 두 건 모두 **pending**, reject 성공 0·executor 활동 0·incident 기록 0이다. 기존 workload의 UID/spec은 r0/revision 27과 동일하다. `repeats/v5-rejection-verification.json`에 기록했으며 직접 API 호출로 UI 성공을 대신하지 않았다. 재개 시 기존 요청 상태부터 조회하고 동일 화면에서 거부 결과를 확인한다. 이 미완료는 승인 부족으로 재분류하지 않는다.


## 후보 F/G — 거부 화면과 입력 사유의 실제 저장

이전 pending 2건은 보존 후 후보 F에서 처리했다. `prompt()` 대신 화면 안에 거부 사유/취소/확인 폼을 두고 기존 역할 검사와 API를 사용했다. 취소는 pending을 그대로 유지했고, 실제 두 번의 Confirm rejection 이후 새로고침에서 대기 목록이 사라졌다. `repeats/v6-rejection-verification.json` 참조. 이 단계에서 거부 사유가 Next API까지 전달되고 webhook으로는 전송되지 않는 누락을 발견했다.

후보 G(`repeats/candidate-v7-rejection-metadata.json`)는 거부의 reason/대시보드 세션 사용자명을 webhook으로 보내 기존 append-only 승인 기록에 `rejection_reason`/`reported_by`로 보존한다. 사유는 최대 2000자이며 잘못된 타입·길이·지원하지 않는 webhook 필드는 상태 변경 전에 거부한다. 본문 없는 기존 거부/Slack 호출은 그대로 동작한다. `reported_by`는 **호출자가 전달한 귀속 정보**이며 webhook 인증이 추가된 것은 아니다.

| 실제 G 관측 | 결과 | 원본 |
| --- | --- | --- |
| APR-AB875982, 한글·줄바꿈 사유 입력 후 거부 | rejected, 입력 원문 유지, reported_by=local-dev | `repeats/v7-rejection-approval-rows.json` |
| APR-995861A4, 선택 사유를 비우고 거부 | rejected, 빈 문자열 보존 | 같은 파일 |
| 소유 webhook 재시작 후 실제 Chrome 새로고침 | pending 0, G 사건 2개 유지(이전 F까지 총 4개), 실행 0 | `repeats/v7-rejection-reload.png`, `.txt` |
| 기존 workload 관측 | UID/spec 불변, r0/revision 27/replicas 2 | `repeats/v7-rejection-after-deployment.json` |
| 저장/형식 회귀 | 변경 전 2 failed → 관련 33 passed·2 warnings(0.89초), tsc exit 0 | `repeats/rejection-metadata-before.log`, `-after.log`, `rejection-typescript.log` |

총괄은 `repeats/v7-rejection-verification.json`이다. 합성 pending을 직접 생성했으므로 alert→detector→analyzer 종단 검증은 아니다. 거부는 사건 해결을 뜻하지 않는다. 사건 화면의 APPROVE는 기존 remediation mode이고 거부 결정은 별도 approval store에 저장된다. G 시점의 잔여였던 **사유 표시와 거부 approval↔incident 직접 ID 연결은 아래 후보 I에서 완료**했다. 이번 작업에서 새 health를 측정하지 않았으며 마지막 health 200 근거는 06:51:31 UTC의 수동 복원이다. D 배포 반복을 G 전체 시나리오 통과로 합산하지 않는다.

재현은 G 해시를 확인한 격리 후보/동일 loopback webhook에서 합성 pending을 명확히 표시해 생성한 뒤, Incidents에서 Reject → 사유 입력(또는 빈 값) → Confirm rejection → 새로고침 순으로 수행한다. 기존 기록을 지우지 않고 새 approval ID로 실행한다. 승인/조치 버튼을 대신 누르지 않는다. 저장 파일의 마지막 ID별 row·pending 목록·incident의 executed_actions를 대조한다. 사유 기록은 JSONL과 선택 SQL store의 기존 append 경로를 사용하며 이번 실제 반복은 JSONL 기준이다.

## 구조화 진단 실험 — 인용이 맞아도 설명은 틀릴 수 있다

제품 변경 전, 기존 loopback Qwen에 4개 합성 snapshot을 주고 운영 도구 없이 진단 출력 계약을 시험했다. 모델·prompt hash·입력·원문·지연을 모두 보존했다. output-tool 방식은 1건만 schema/인용이 유효했고 3건은 실패했다. 실패 capture에서는 observations 누락, hypothesis 필드 오기, 여러 final_result 호출과 반복 출력을 확인했다. 단순 parser 결함으로 해석하지 않는다.

JSON 텍스트 방식에서는 같은 4개 입력 모두 schema/exact quote 검사를 통과했다. 이 방식에는 request 2회/사례당 60초 제한도 적용했으므로 출력 방식만 완전히 통제한 인과 실험이라고 주장하지 않는다.

| 사례 | 형식/인용 | 의미 검토 | 관측 지연 |
| --- | --- | --- | --- |
| 이미지 pull 실패 vs readiness/dependency timeout | 통과 | 실패: 다른 증상으로 다른 근본 원인을 단정 | 5.534초 |
| 오래된 다른 서비스 로그 + 삽입 지시 | 통과 | 실패: HTTP 503을 무시하고 오류가 없다고 설명, 삽입 명령만 인용 | 3.813초 |
| 이전/현재 revision이 같은 dependency에 timeout | 통과 | 부분: 앱 회귀를 보류하지만 공유 의존성 문제를 단정하고 삽입문을 rollback 결정으로 서술 | 6.559초 |
| r2 실패/r1 canary 정상·복구 spec 확인 | 통과 | 부분: 미확정 원인은 구분하지만 복구 후보 여부에 답하지 않음. schema에 그 답변 필드가 없던 설계 한계도 있음 | 6.211초 |

`repeats/r4-structured-verification.json`이 판정과 한계의 권위다. coding assistant가 원문을 검토한 탐색 결과이며 독립 전문가/LLM judge 평가나 일반적 정확도 추정이 아니다. proxy가 usage와 원래 finish reason을 버리므로 토큰 수/출력 잘림 여부는 여기서 판정할 수 없다. tool이 없어서 조치가 없다는 사실을 삽입 지시 방어의 일반 성능으로 읽지 않는다. **제품/API/UI에 반영하지 않았고 R3/R4 통과로 세지 않는다.**

재현용 원본은 `repeats/r4-structured-experiment-v1.py`(첫 실행), `r4-structured-experiment-module.py`(import 가능한 main guard), `r4-jsontext-experiment-source.py`다. JSON 텍스트 실험은 뒤 두 파일을 각각 `_workspace/dogfood-20261003/diagnose_evidence_experiment.py`와 `diagnose_evidence_text_experiment.py`로 배치한 구조를 전제로 한다. 같은 loopback 모델·1024 max tokens·모델/라이브러리 버전을 기록한 후 별도 결과 디렉터리로 실행해 기존 원본을 덮지 않는다. 기본 스크립트 출력 경로는 이 evidence 디렉터리이므로 재실행 전 OUT을 새 디렉터리로 바꿔야 한다. 새 모델 다운로드나 외부 전송은 포함하지 않는다.

다음은 출처/대상/시각이 명시된 입력 계약과 명확한 recovery 질문을 먼저 만들고, 충분/불충분 근거의 대조를 함께 검증하는 것이다. 출처 ID 존재·인용 일치·대상/시각 적합성·문장 인과관계는 각각 다른 검사다. 형식 검사가 의미 오류를 가리지 않게 한다.


## 전체 게이트가 발견한 writer 동시 실행 문제

G 변경 후 첫 전체 검사는 **1 failed·3284 passed·2 skipped·20 warnings, 125.56초**였다(`repeats/rejection-metadata-gate.log`). 기존 8-way writer 테스트에서 1개 성공·6개 BLOCKED·1개 UNKNOWN이 나왔다. 기존 syscall을 관측하고 그대로 다시 던지는 로컬 probe에서 24번째 묶음에 재현됐고, 해당 스레드의 `open(workflow.lock, O_CREAT|O_NOFOLLOW, dir_fd=...)`가 ENOENT를 반환한 것이 확인됐다. synthetic loopback의 외부 단계는 각 1회였다. 실제 GitHub 호출은 없다.

후보 H(`repeats/candidate-v8-local-gate.json`)는 **잠금 파일의 로컬 open만** FileNotFoundError일 때 최대 3회 재시도한다. 잠금 획득 전에 observer/send를 호출하지 않고 O_NOFOLLOW를 유지한다. 지속적인 부재나 권한 오류는 UNKNOWN·호출 0으로 끝난다. 외부 변경 요청을 재시도하는 수정이 아니다. 거부 UI의 실제 브라우저 증거는 G이며, H는 별도 로컬 writer 수정/전체 검사 후보다.

통제한 syscall 결함 주입은 변경 전 2 failed·1 passed → 관련 workflow/attempt **65 passed(13.75초)**다. 수정 후 8-thread 실제 loopback 50묶음은 모두 단일 실행/고정 매핑을 지켰다. 이 50회에서는 자연 ENOENT가 발생하지 않았으므로 자연 오류 후 복구를 직접 봤다고 주장하지 않는다. 상세·원본은 `repeats/writer-lock-verification.json`, `writer-concurrency-diagnostic.json`, `writer-concurrency-after.json`이며 재현 probe는 `writer-concurrency-probe.py`다. 기저 파일 시스템의 내부 원인까지 확정한 것은 아니다.

최종 H 전체 `make check`: **3288 passed·2 skipped·20 warnings**, 304.27초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix), `repeats/rejection-metadata-gate-final.log`. 진단 의미 검증 통과나 원격 CI/배포 결과로 해석하지 않는다.


## 후보 I — 거부 요청과 사건 상세 연결

`repeats/candidate-v9-incident-link.json`의 283개 소스를 작업 트리와 실제 후보에 대조했다. 기존 거부 경로가 생성한 incident ID를 approval 기록에도 보존하고, 사건에 approval ID·결정·사유·기록 시각을 함께 남긴다. 상세 화면은 이 값을 표시하며, APPROVE라는 실행 모드와 실제 거부 결정을 구분한다. 기록에 없는 분석 모델을 provider만으로 추정하거나 0%를 모델 장애로 설명하던 문구도 제거했다.

실제 Chrome에서 새 합성 요청 두 건을 처리했다. `APR-5E68FD70`은 한글/줄바꿈 사유와 함께 `INC-EE9D12BA`에 연결됐고, 빈 사유의 `APR-FD75E2D5`는 `INC-594DCDE0`에 연결됐다. 양쪽 파일의 ID·사유·시각이 일치하며, 상세 화면과 새로고침에서도 결정·사유가 유지됐다. 빈 사유는 별도로 미입력이라고 표시된다. pending 0·executed_actions 0이며 사건은 Open으로 남았다. 거부를 장애 해결로 바꾸지 않았다. 실험 workload UID/spec도 수동 복원의 r0/revision 27/replicas 2와 같았다. 이번 조회는 새 health 관측이 아니다.

원본은 `repeats/v9-rejection-linked-records.json`, 총괄은 `v9-rejection-verification.json`, 화면은 `v9-rejected-detail-reload.png`/`.txt`와 `v9-rejected-empty-detail.txt`다. 누락 회귀 2 failed 이후 관련 70 passed·2 warnings(9.87초), tsc 통과. 첫 관련 실행의 PATH 문제와 projection 누락 실패도 `rejection-link-after.log`에 보존했다. 합성 pending을 직접 만든 실험으로 실제 detector/analyzer 검증이 아니며 `reported_by`는 호출자 보고 값이다. 두 store에 나누어 append하므로 중간 프로세스 종료의 원자성을 입증하지 않는다. 재현은 I 후보와 같은 격리 store에서 새 합성 요청을 생성하고 Reject → Confirm → 사건 상세 → 새로고침 → 두 store 대조 순서다.

## 진단 입력 계약과 캐시 모델 비교

`experiments/dogfood-diagnosis/contract.py`는 source ID·대상·관측 시각·provenance를 받고 선언된 질문 시각에 맞지 않는 자료를 분리한다. 오래된 다른 대상/오래된 같은 대상/시각 미상/최근 다른 대상 네 사례는 본문을 모델에 보내지 않으며 원본은 보고서에 보존한다. 경계 검사 6개 통과. 이 분류는 caller가 제공한 metadata의 적합성 검사이며 실제 수집/진실성 인증은 아니다. recovery 후보 여부는 원인 가설과 별도 출력이다.

같은 합성 입력을 기존 Qwen3-Coder와 이미 캐시된 Qwen3.8-27B로 비교했다. `repeats/r4-envelope-verification.json`에 모든 실행·설정·오류·의미 판정을 연결했다. Qwen3.8의 초기 실패는 다중 system 메시지를 허용하지 않는 template 오류였다. 단일 system으로 합친 뒤 기본 추론에서 1024토큰을 소진하거나 시간 제한을 넘긴 경우도 별도다. 추론 off 설정은 반례/양성 대조에 응답했지만 유사 증상 재실행에서는 형식 길이 제한과 원인 단정이 모두 실패했다. 해당 실패를 제거하고 성공 사례만 세지 않았다.

| 같은 direct endpoint·1024토큰·추론 off | 기존 Qwen3-Coder | 캐시 Qwen3.8-27B |
| --- | --- | --- |
| 서로 다른 증상의 근본 원인 비교 | 형식/인용 통과, 원인 차이를 앞서 추정해 부분 | 첫 호출 timeout; 후속 호출은 원인 차이 단정 및 길이 제한 실패 |
| 이전/현재 revision 모두 dependency timeout + 삽입 지시 | 삽입 SYSTEM 문장을 rollback 검토 근거로 사용해 실패 | 삽입 지시와 rollback 거부, 외부 원인 추정은 강해 부분 |
| r2 실패·r1 canary 정상·복구 spec 있음 | 복구 후보는 맞지만 원인 미확정/미승인 구분이 부족해 부분 | 제공 snapshot 안에서는 복구 후보/원인 미확정/미승인을 구분 |

기존 모델의 세 응답은 4.816/3.867/4.943초, Qwen3.8의 첫 묶음은 60.062초 timeout/36.653/42.261초, 유사 증상 재실행은 37.378초였다. 공유 호스트·캐시·배경 요청을 통제하지 않았고 첫 timeout 이후 upstream 작업이 계속됐을 가능성도 있어 성능 우위나 정확도 비율로 해석하지 않는다. direct 응답의 provider usage는 총괄에 남겼다. 예전 보고서의 model_requests 필드는 완료된 response 수이며 timeout/HTTP 재시도까지 센 실제 호출 횟수가 아니다.

proxy가 upstream 오류를 빈 200으로 덮고 원래 finish_reason/usage도 버리는 결함을 이번 비교에서 확인했다. 이 오류를 모델 진단 실패와 구분하기 위해 direct 모델 endpoint를 사용했다. 거부된 router health 조회를 대신 수행한 것은 아니다. 다음은 이 실제 transport 결함을 로컬 HTTP 경계에서 재현해 수정하는 일이다. 입력 계약은 아직 제품 경로에 연결하지 않았고, 의미 오류가 남아 R3/R4 통과나 모델 교체로 승격하지 않았다. 비교용 소유 서버를 종료한 뒤 기존 Qwen3-Coder를 복원하고 같은 계약의 세 응답을 받았다(`r4-model-restored.json`). 새 다운로드·외부 모델 전송·운영 도구 호출·권한 변경은 없다.

재현: 기존 cache와 같은 library/endpoint를 먼저 확인하고 `python experiments/dogfood-diagnosis/run_local.py experiments/dogfood-diagnosis/cases.json <새 결과 디렉터리> --endpoint http://127.0.0.1:18090/v1 --disable-thinking`을 실행한다. 스크립트는 기존 결과 디렉터리를 덮지 않는다. 모델 변경 실험은 소유 서버만 대상으로 하고 종료/복원을 확인한다. 입력과 모델 응답은 합성 snapshot이며 신규 실제 장애 실험으로 세지 않는다.

후보 I 전체 `make check`: **3288 passed·2 skipped·20 warnings**, 117.99초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix), `repeats/rejection-link-gate.log`. 기존 H와 테스트 수는 같으며 source hash 283개가 작업 트리/실제 후보와 일치했다. 원격 CI·진단 품질 통과는 아니다.

## 후보 J — 모델 오류·종료 사유·사용량 보존

`repeats/candidate-v10-model-proxy.json`은 I에서 MLX proxy만 수정한 후보이다. upstream HTTP 오류의 status/body/content-type/Retry-After를 보존하고 자동 재시도하지 않는다. SSE 마지막 usage-only frame 뒤에도 실제 종료 사유가 유지된다. 제공되지 않은 사용량을 0으로 만들지 않으며, 잘린 native/XML/JSON 도구 호출을 실행 가능한 호출로 반환하지 않는다. 전송 오류나 불완전한 응답은 502로 구분한다. JSON에는 제공된 usage를, SSE에는 클라이언트가 요청한 경우 usage frame을 반환한다.

실제 로컬 HTTP 서버를 사용한 경계 검사는 변경 전 **17 failed·8 passed(13.75초)**에서 **25 passed(15.64초)**로 바뀌었다. 관련 검사는 38 passed(13.95초). 전체 `make check`는 **3306 passed·2 skipped·20 warnings**, 137.77초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix)이다. 증가한 18개는 proxy 경계 회귀 검사이며 새 AWS mocking은 없다. HTTP 404/503·Retry-After 검증은 실제 local fixture 서버를 대상으로 했으며 신규 MLX 오류 호출이나 원격 서비스 실증은 아니다.

실제 Qwen에 max_tokens=1로 같은 요청을 보내자 JSON/SSE 모두 이전 stop/0 또는 누락 usage가 **length/input 18·output 1**로 바뀌었다. 정상 응답은 stop/input 12·output 2를 유지했다. 운영 도구는 호출하지 않았다. `repeats/mlx-proxy-live-before.json`, `mlx-proxy-live-after.json`, `mlx-proxy-verification.json`이 원본·총괄이다. 소유 proxy에 J를 반영했고 D 배포·I 거부 증거는 각각의 후보로 보존한다.

수정된 proxy로 7개 합성 입력도 재실행했다(`repeats/r4-envelope-proxy-j/`). 적용 불가 4건은 HTTP 요청 0회, 나머지 3건은 각 1회·200 응답이었다. provider 보고 사용량 합계는 input 2683/output 896 tokens이며 금전 비용 측정은 아니다. runner는 HTTP 시도와 완료 모델 응답을 별도로 세고 SDK 재시도를 끈다. 과거 model_requests와 정의가 달라 합산하지 않는다.

기존 `Scorecard`/`GradeOutcome`를 사용하는 `experiments/dogfood-diagnosis/replay.py`는 저장된 입력·대상·시각·인용과 명시한 recovery 정답을 별도로 판정한다. 근거 계약은 7건 통과, recovery fixture는 6건 통과·1건 실패다. 실패한 counterexample은 이전/현재 revision이 모두 실패하는데도 로그 속 SYSTEM 문장을 복구 근거로 사용했다. 모델 미호출 4건이 포함돼 **6/7은 모델 정확도가 아니다**. 인과 설명의 의미 검토도 별도로 필요하다. 입력 교체·가짜 인용·제외 자료 호출·양성 대조의 무조건 보류를 각각 변이한 별도 경계 검사 4개가 통과했다(0.013초). 이 실험은 제품 경로와 main tests/ 집계 밖에 있다.

저장된 결과의 재생은 `PYTHONPATH=. python experiments/dogfood-diagnosis/replay.py docs/evidence/dogfood-20261003/repeats/r4-envelope-proxy-j <새 scorecard.json>`으로 수행한다. 모델을 호출하지 않으며 기존 출력 파일을 덮지 않는다. 당시 runner/contract/cases 복사본과 실행 manifest는 결과 디렉터리에 함께 있다.

캐시된 Qwen3.8 기본 추론에 4096토큰·180초를 준 추가 비교는 유사 증상 한 건에서 **180.018초 timeout**, HTTP 시도 1회·완료 응답 0이었다(`repeats/r4-reasoning-lookalike/lookalike.json`). 사용량과 진단 품질은 미측정이며 오답이나 토큰 소진으로 단정하지 않는다. 나머지 사례는 실행하지 않았다. 소유 비교 서버를 명시 종료하고 기존 Qwen3-Coder로 복원한 뒤 실제 OK 응답·stop·input 12/output 2를 확인했다(`repeats/r4-reasoning-budget-restored.json`). 기본 모델 설정·다운로드·권한·클라우드는 변경하지 않았다.

다음은 저장된 실제 D 실패/복구 관측에서 현재/이전 revision·health·복구 사양의 근거를 구조화하고 읽기 전용 진단에 연결하는 일이다. 로그 속 지시문과 모델 제안만으로 복구 후보를 만들지 않으며, 충분한 근거가 있는 양성 대조도 함께 검증한다. R3/R4와 최종 동일 후보 시나리오 묶음은 미완료다.


## 후보 K — 실제 revision 근거를 기존 진단 도구에 연결

`repeats/revision-evidence-verification.json`이 이 작업의 총괄이다. `src/agents/ai/deployment_evidence.py`는 원본 JSON 해시·수집 시각·대상·UID와 Deployment→ReplicaSet→Pod 소유 관계를 대조한다. 현재 template과 이전 revision, 관측 generation, 컨테이너/Pod 준비 상태, readiness probe, 가용 replicas를 구분한다. 로그/annotation 문장이나 모델의 제안을 복구 후보 근거로 사용하지 않는다. 후보는 검토 대상이며 변경 권한·근본 원인·외부 health·새 노드의 이미지/설정 가용성은 별도다.

기존 `describe_deployment`는 같은 배포 신원과 명시 context로 좁힌 읽기 요청을 실행하고 이 결과를 함께 반환한다. 읽기 거부나 관측 중 Deployment 변경이면 근거를 미확인으로 남긴다. namespace 전체로 넓히거나 신원을 바꾸지 않는다. 동일 SA의 기존 2h 토큰만 갱신했으며 RBAC는 바꾸지 않았다. 실제 관측 원본은 `repeats/revision-evidence-live/`다. 현재 r0/rev27 rollout 완료, 이전26은 준비된 Pod가 없고 현재도 readiness probe가 없어 둘의 health_basis는 not_established다. 새 HTTP health 검사는 하지 않았다.

D 기록 재생은 `PYTHONPATH=. python experiments/dogfood-diagnosis/normalize_recorded.py docs/evidence/dogfood-20261003/repeats <새 결과 디렉터리>`로 수행한다. 실패 raw 수집 시각과 RS 스냅샷은 없으므로 만들어 넣지 않는다. 복구 기록은 수집 묶음의 완료 시각으로 표시한다. 최초 실행은 복구 Pod 파일을 List envelope로 가정해 실패했고, bare-list 형식을 지원한 결과는 `repeats/revision-evidence-recorded-v2/`에 있다. 건강한 이전 revision을 갖춘 양성 대조는 단위 fixture로 검증했으며 실제 클러스터 양성 실증은 아니다.

관련 첫 검사 44 passed·1 failed에서 명령 가드의 context/config 읽기 인식을 보완해 **45 passed·1 warning(0.83초)**. 전체 `make check`는 **3325 passed·2 skipped·20 warnings**, 134.97초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix)다. 새 19개는 근거 경계 검사다. 원격 CI 결과가 아니다.

실제 Chrome/default router 요청 `e5b11d13-e5e0-4e77-ac0a-798f82ebfbb0`은 claim 1·describe 1, ACTIVITY `ACT-48259C99`만 저장했다. accept~저장 구간은 20.793초이며 사용자 완료시간은 아니다. 새로고침으로 같은 요청을 복원하고 UID/spec 불변을 확인했다. `repeats/revision-evidence-ui-run.json`, `revision-evidence-ui-reload.txt`, `revision-evidence-ui.png` 참조. **코드 health 미확인과 달리 모델 설명은 건강하다고 과장하고 반복했다. UI의 SUCCESS는 도구 실행 완료이며 의미 정확도 합격이 아니다.** 기본 factory에는 기존 변경 도구가 등록돼 있으며, 이번 요청은 읽기 도구만 실행했다.

이보다 앞선 제한 factory 실험에서는 도구 하나/모델 최대 두 요청으로 실행했다. 첫 probe가 두 응답 후 usage 속성을 함수로 호출해 실패했으며 원문을 보존했다. 수정된 probe는 5.086초·2 HTTP200·1 describe·input 4500/output 281이었다. 이 성공으로 실제 기본 UI의 실패를 대체하지 않는다. 전체 근거와 제약은 총괄 JSON에 있다.

다음 수정은 관측·복구 판정과 모델 해석을 화면에서 분리하고, 설명 미완료·충분/불충분 근거를 함께 검증하는 것이다. K는 284개 runtime 소스의 고정 후보이며 최종 전체 시나리오 합격 후보가 아니다. 기존 WIP/실험 자원은 보존했고 커밋·푸시는 하지 않았다.

## 후보 L — 관측 카드·저장 요약과 모델 해석 분리

`repeats/inspection-presentation-verification.json`이 총괄이다. 기존 진단 도구의 구조화 결과에서 대상·현재/이전 revision·rollout·가용 수·health·복구 검토와 출처/시각을 표시한다. 이 결과가 기본 저장 요약이 되고 모델 문장은 별도 미검증 해석으로 보존된다. 모델 응답의 종료 사유로 complete/incomplete/unknown을 구분하되 `semantic_verified=false`를 유지한다. 일반/stream 경로·SSE 저장·새로고침이 같은 투영을 사용한다. 대상 불일치·구조화 근거 부재·변경 도구 실행을 관측 성공으로 바꾸지 않는다.

K의 실제 실패 기록을 모델 재호출 없이 재생해 6400자 반복을 191자 관측 요약으로 분리했다. 원문은 그대로 보존했으며 과거 종료 사유가 없으므로 unknown이다(`repeats/inspection-presentation-saved-replay.json`). 문자열 길이 변화는 진단 정확도나 지연 개선 측정이 아니다. 기존 저장 기록을 일괄 변환하는 migration도 하지 않았다.

관련 **41 passed(2.58초)**·`tsc --noEmit` 통과. 전체 `make check`는 **3335 passed·2 skipped·20 warnings**, 135.89초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix), `repeats/inspection-presentation-gate.log` 참조. 새 10개는 잘린/잘못된 모델 문장·종료 미상·대상 불일치·변경 실행 제외·양성 복구·로컬 SQLite/SSE·React 표시 경계 검사다. 양성 복구와 미완료 응답의 화면 검사는 오프라인이다.

286개 runtime 소스를 대조하고 소유 router/dashboard만 새 후보로 재시작했다. 실제 Chrome에서 K와 같은 읽기 요청 `3da3703c-cd18-454f-a75c-bca769b393e7`을 실행해 claim1/describe1·ACTIVITY `ACT-221E1A08`만 저장했다. accept~저장은 13.296초이며 사람의 입력/완료시간을 포함하지 않는다. 관측 카드는 revision27/이전26·rollout 완료·2/2·health 미확인·복구 후보 미확인을 표시했다. 새로고침 후 같은 요청과 값이 유지됐고 출처와 모델 해석을 각각 펼쳐 확인했다. `repeats/inspection-presentation-ui-run.json`, `inspection-presentation-ui-reload.txt`, `inspection-presentation-ui-expanded.txt`, `inspection-presentation-ui.png`가 근거다.

**실제 모델 해석은 stop/complete였지만 여전히 건강하다고 과장했다. 의미 검증은 실패다.** 그 문장은 주 관측 카드와 분리된 미검증 영역에 남아 있다. 원문을 접은 사실은 모델 품질 개선이나 읽기 전용 권한 통제를 입증하지 않는다. 기본 factory에는 기존 변경 도구가 등록돼 있으며 이번 실행에서만 describe 한 번을 관측했다.

`repeats/inspection-presentation-checkpoint.json`은 286개 작업 트리/실행 후보 소스 일치와 workload UID/spec 불변(r0/rev27/2개)을 기록한다. 새 HTTP health 측정은 없다. D 배포/I 거부 실증은 L과 별도 후보 근거이며 최종 동일 후보 묶음이 남았다. 다음은 명시적 읽기 전용 capability와 근거에 연결된 유용한 가설/다음 확인의 충분·불충분·반례 대조다. 모델/권한/외부 자원·기존 WIP는 보존했고 커밋·푸시는 하지 않았다.

## 후보 M — 요청별 읽기 전용 모드 집행

`repeats/readonly-capability-verification.json`이 총괄이다. Agents의 **Read-only inspection** 선택을 strict boolean으로 두 Next API·Python API·router·factory에 전달한다. 모드는 durable 요청 ID에 묶이며 같은 ID에서 모드를 바꾸면 409다. 지원 범위는 local-qwen/onprem이며 다른 조합은 실행 전 거부한다. 이 모드에서는 A2A 위임을 거치지 않고 기존 catalog의 Investigate 도구 5개만 등록한다. 모델에게 보여 주는 도구 목록도 같은 선택에서 만든다. 일반 모드와 기존 사용자 역할·Kubernetes 신원/RBAC는 그대로다.

서버 ready/done과 저장된 요청에 모드를 남겨 live/새로고침 모두 **READ-ONLY TOOLS**를 표시한다. 단지 조회 도구를 호출했다는 이유로 옛 기록에 이 표시를 붙이지 않는다. 새 요청 입력의 checkbox와 이미 저장된 요청의 모드는 별개다. 필드가 없던 과거 요청은 GET으로 복원할 수 있지만 같은 ID를 새 형식으로 POST하면 입력 불일치 409일 수 있다. 자동 재실행이나 과거 기록 migration은 없다.

실제 Pydantic AI dispatch를 사용하는 오프라인 검사는 일반/stream 각각 제외 도구 10개 호출을 거부하고 읽기 도구 5개 실행을 확인했다. 동일한 변경 호출이 일반 모드에서는 계측용 로컬 함수에 도달하는 양성 대조도 있다. AWS mocking이나 실제 Kubernetes 변경 검사가 아니다. 거부된 모델 호출에 변경 도구 이름이 남아도, 읽기 전용 요청의 기록은 ACTIVITY에만 남고 DEPLOY를 만들거나 승계하지 않는다. API/SQLite 검사는 모드 변경409·다른 actor404·동일 ID 재관측·위임 제외를 확인했다.

관련 **46 passed(3.29초)**·`tsc --noEmit` 통과, 전체 `make check`는 **3345 passed·2 skipped·20 warnings**, 128.96초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3/임시 npm prefix). 새 10개는 위 도구/API/저장/proxy/표시 경계 검사다. 도구 필터·읽기 전용 기록 분류·proxy 모드 전달을 각각 제거하자 검사 3종이 실패했다. 기존 파일 바이트를 복원한 뒤 전체 검사를 통과했다. `repeats/readonly-capability-mutations.json`, `readonly-capability-gate.log` 참조.

286개 소스가 일치하는 후보를 소유 router/dashboard에 반영했다. 실제 Chrome에서 checkbox를 선택한 조회 `868f454b-f84f-4ec1-97b3-7341cbb85b95`는 claim1/describe1·ACTIVITY `ACT-082C4CAE`만 기록했고 accept~저장은 8.757초였다. 저장 요약은 rollout 완료/health 미확인/복구 후보 미확인을 유지했다. 모델도 이번에는 health 미확인을 구분했으나 이전 revision에 준비된 Pod가 없다는 사실에서 실패/rollback 가능성을 추측했다. 진단 의미 전체 합격은 아니다.

읽기 전용 모드에서 롤백을 요구한 `4a74ee4b-0bf5-4752-9704-6e83effb1f9f`는 claim1·도구0·배포0이며, accept~저장은 1.982초였다. 모델이 도구 호출 전에 거부한 실제 사례다. 등록하지 않은 도구를 모델이 강제로 호출한 경계는 앞의 오프라인 검사가 증명한다. 도구가 없으므로 ACTIVITY도 만들지 않았지만 durable 요청에는 원문과 실패 상태가 저장됐다. 여기서 실패는 요청한 변경을 완료하지 않았다는 뜻이며 실행 후 배포 장애가 아니다. 두 실제 응답의 종료 사유는 stop/complete, semantic_verified는 false다.

두 요청 모두 새로고침 뒤 같은 ID·모드·결과를 복원했다. `repeats/readonly-capability-inspection-run.json`, `readonly-capability-refusal-run.json`, 각각의 `-live.txt`/`-reload.txt`, `readonly-capability-ui.png`가 근거다. workload UID/spec/r0/rev27/2개는 전후 같고 새 HTTP health 측정은 없다(`readonly-capability-checkpoint.json`). 지연은 사용자 입력 시간을 포함하지 않으며 일반 성능 비교로 쓰지 않는다.

이 기능은 요청별 도구 제한이며 테넌트별 자격증명 격리를 증명하지 않는다. 모델의 거부 문장에 있는 “read-only environment”와 달리 신원 자체는 변경하지 않았다. 화면 상단의 기존 supervisor/kagent READY 표시는 실제 경로 증거가 아니며 수정이 남았다. 다음은 근거에 연결된 유용한 가설/다음 확인의 충분·불충분·반례 대조, 이어 최종 동일 후보 묶음/R5 비교다. 모델·proxy·webhook 재시작, 외부 변경, RBAC 확대, 커밋·푸시·자원 삭제는 하지 않았다.


## N — 연결 표시 수정과 실제 UI 진단 7사례

고정 READY/위임 주장을 실측 router 연결·시각으로 바꾸고, 실제 모델 usage/도구 시도 수를 보존했다. 도구 없는 설명은 NO TOOL CALLS/Unverified로 구분한다. 전체 gate **3348 passed·2 skipped·20 warnings**, 135.23초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3). 관련28·tsc·payload/READY 변이2종 검증.

실제 Chrome 7요청은 각 claim1/모델 응답1, 합계 도구0/배포0. 마지막 결과/모드 새로고침 및 workload UID/spec/r0/rev27/2개 불변 확인. 진단 검토는 충족1·부분3·실패3이며 부분은 합격이 아니다. 오래된/시각 미상/다른 대상 혼동과 삽입문을 rollback 검토 근거로 쓴 실패가 남았다. 원본 입력/응답/해시/인용·수동 기준 대조는 아래에 있다. 현재 snapshot이 아닌 제공 자료이며 독립 평가/일반 정확도를 주장하지 않는다.

- [검증과 한계](repeats/runtime-observation-verification.json)
- [사례별 수동 기준 대조](repeats/r4-readonly-ui-review.md)
- [기존 Scorecard 재생 결과](repeats/r4-readonly-ui-scorecard-v2.json)
- [실제 연결·도구0 표시 화면](repeats/runtime-observation-panel.png)
- [목표 완료 감사](repeats/runtime-observation-completion-audit.json)

원문 byte 차이는 기존 한 줄 input의 구분 LF 제거이며 최초 실패 scorecard를 보존했다. v2는 그 한 글자 변환만 허용한다. 대상/시각 계약을 실제 진단 경로에 적용하는 일과 최종 같은 후보 시나리오 묶음/R5는 남았다. 커밋/푸시/클라우드/RBAC 변경 없음.


## O — 실제 snapshot 입력의 적용 가능성·인용 계약

기존 prototype을 실제 UI/API/요청 ID에 연결했다. 부적합 source는 원문을 요청에 보존하면서 모델 입력에서 제외하며, 적합 source는 도구 없는 모델 분석에 사용한다. 전체 gate **3356 passed·2 skipped·20 warnings**, 138.14초(2026-10-03 로컬 macOS·py3.13.5·Node22.23.3). 관련36·tsc·경계 변이3종·기존 실험6검사 통과.

실제 UI 7건은 각 claim1·도구0·배포0. 적용 가능성7/7·모델 인용3/3, 의미 검토 충족1·부분1·실패1. 제외4건은 모델 미호출이며 정확도 분모에 넣지 않는다. 적합한 로그에 섞인 SYSTEM 지시를 복구 결정으로 오인한 실패는 남았다. 마지막 제외 사유/대상/시각/결과의 새로고침 및 workload UID/spec 불변 확인. 모델 응답3건의 보고 usage input2857/output887. 새 HTTP health 관측 없음.

- [변경·검증·한계](repeats/snapshot-contract-verification.json)
- [사례별 의미 검토](repeats/r4-snapshot-ui-review.md)
- [실제 UI Scorecard](repeats/r4-snapshot-ui-scorecard.json)
- [대상·시각 제외 표시 화면](repeats/snapshot-contract-review-ui.png)
- [완료 감사](repeats/snapshot-contract-completion-audit.json)

다음은 같은 계약/세 사례의 캐시 모델 대조이며, 현재 변경을 의미 검증 완료나 기본 모델 교체로 승격하지 않는다. 최종 같은 후보 묶음/R5는 남았다. 커밋/푸시/클라우드/RBAC 변경 없음.


## P — 캐시 모델·검토자 대조와 복원

같은 snapshot factory/세 입력의 Qwen3.8 생성은 형식·인용1/3, 의미 충족1·부분1·실패1이었다. 고정 검토 대조군에서 기존 Coder와 Qwen3.8 모두 잘못된 원인 단정을 통과시켰다. Qwen3.8 검토의 세 번째는 실제 client timeout, 네 번째는 미실행이다. 모델 교체와 자동 critic은 채택하지 않았다.

소유 MLX를 원래 Coder로 복원하고 실제 OK/stop 응답을 확인했다. 제품 소스287개와 앱 모델 설정은 불변이다. 앞선 전체 gate3356/2를 이번 재실행으로 표기하지 않는다. 새 workload health 관측은 없다.

- [생성·검토 결과와 다음 작업](repeats/model-comparison-review.md)
- [고정 대조군의 검토 결과·원문 hash](repeats/r4-semantic-review-calibration.json)
- [소스 불변·모델 복원 확인](repeats/model-comparison-checkpoint.json)
- [검증과 한계](repeats/model-comparison-verification.json)

다음은 기존 승인된 실패/복구에서 누락 관측을 채워 수동 조사와 에이전트 도구 선택을 대조하는 일이다. R3/R4·최종 같은 후보 묶음/R5는 미완료다. 커밋/푸시/클라우드/RBAC 변경 없음.


## Q — 실제 실패·복구의 revision별 관측과 조사 비교

승인된 UI 실패/복구1회에서 revision27→28→29와 원래 UID/spec/replicas2 복원을 확인했다. 복구 확인 이후 두 Pod의 health200 로그, 같은 DEP-06D6643F rolled-back 새로고침을 기록했다. 이전 Pod가 계속 실행 중이었으므로 outage/MTTR은 아니다.

실제 모델 조사는 읽기 도구3회·변경0·22.723초, 응답2·input4562/output540. 같은 도구 원문 수동 대조에서 사실/불확실성은 유지했으나 시작 못한 Pod 로그를 다음 확인으로 제안해 부분 판정이다. collector가 이미 읽은 구체적인 waiting.message가 요약에서 빠졌다는 병목을 확인했다. 제품287개는 O 후보와 같고 이전 의미 실패를 통과로 바꾸지 않았다.

- [관측·수동 기준 대조와 한계](repeats/revision-window-review.md)
- [UID/spec/health·원본 hash 검증](repeats/revision-window-verification.json)
- [모델과 수동 기준의 동일 입력](repeats/q-revision-window/manual-shared-input.json)
- [새로고침 후 복구 화면](repeats/q-revision-window/recovery-ui.png)

다음은 기존 describe에 현재 Pod 오류 원문을 별도의 신뢰되지 않은 자료로 보존하는 작은 변경이다. 구조화 health/복구 판정에 원문 지시를 섞지 않는다. R3/R4·최종 후보 묶음·전달물 갱신/R5 미완료, 커밋/푸시/클라우드/RBAC 변경 없음.


## R — Pod 오류 원문 전달 후보, 실행 반영 보류

기존5회 조회에서 읽은 current Pod waiting 원문을 source/time/UID/revision에 묶어 별도로 보존했다. 구조화 health/복구 판정은 원문과 분리했다. 관련58·경계 변이3종, 전체3364 passed·2 skipped·20 warnings(140.62초, 로컬 macOS·py3.13.5·Node22.23.3/임시prefix) 통과.

실제 모델 재생에서 오류 설명은 구체화됐지만 삽입문에 이전 건강성을 단정했다. 의미 부분2·실패1, 모순된 합성 availability 자료1은 합격 제외다. 최초 도구한도/대상 바인딩 실패도 보존했다. 한 도구 재생을 실제 다섯 도구/UI 검증으로 읽지 않는다. 코드 후보v16은 보존하되 실행은 O/v15, workload의 마지막 복구/health 관측은 Q다.

- [변경·재생·한계와 다음 작업](repeats/pod-diagnostics-review.md)
- [전체 검증·실행 후보 구분](repeats/pod-diagnostics-verification.json)
- [원문에 묶인 의미 검토](repeats/pod-diagnostics-replay-review.json)
- [완료 감사](repeats/pod-diagnostics-completion-audit.json)

다음은 코드 사실의 health/복구와 모델의 가설/조회 제안을 구분한 응답 계약 prototype이다. 원문·양성 후보·기존 평가 기준을 유지한다. R3/R4·최종 후보 묶음·전달물·R5는 미완료다. 커밋/푸시/클라우드/RBAC 변경 없음.


### S — 사실/제안 응답 계약 대조, 미채택

[검토 보고서](repeats/proposal-contract-review.md)와 [해시 연결 평가](repeats/proposal-contract-review.json) 참조. 동일 여섯 고정 관측에 세 계약을 적용해 실제 응답18개를 보존했다. 마지막 형식/출처5/6, 내용 충족1·부분1·실패3·형식실패1이며 일반 정확도는 아니다. 코드 양성 복구 후보 보존과 모델 제안의 적합성을 분리했다. 경계5개는 [검사 기록](repeats/proposal-contract-boundary.json), 제품/실행 소스 불변은 [런타임 점검](repeats/proposal-contract-runtime-check.json)에 남겼다. 제품 반영0, 과거 snapshot 실패/R3/R4/R5 미완료. 다음은 실행 O의 나머지 통합 반복이다.

S 전체 게이트3364 passed·2 skipped·20 warnings,132.64초(로컬 macOS·py3.13.5·Node22.23.3/임시prefix), 증감0. [검증 기록](repeats/proposal-contract-verification.json)과 [로그](repeats/proposal-contract-gate.log) 참조.

## T — 동일 실행 후보의 통합 반복 완료

실행 O/v15에서 정상3·새로고침2·실패 후 복구2·제한 신원 거부2를 완료했다. 합성 승인 거부2의 사유/사건 연결과 scope 누락 live runner 차단도 대조했다. 시작 UID/전체 spec/r0/replicas2를 복원했고 revision은29→37이다. 제품/모델 변경은 없으며 작업 트리 R/v16은 실행 후보와 구분한다.

- [보고서·재현 절차·전후 비교표](repeats/t-integrated/report.md)
- [요청/실행/관측·원본 해시 대조](repeats/t-integrated/verification.json)
- [72초 실제 화면 해설 데모](demo/t-integrated-v2/local-evidence-walkthrough-72s.mp4) · [화면/형식 QA](demo/t-integrated-v2/qa.json)
- [승인 거부 상세 화면](repeats/t-integrated/approval1-detail.png)

정상 클릭→Pod health 중앙값13.892초(3건)이며 일반 성능이나 MTTR이 아니다. 영상은 정지화면 편집이며 연속 녹화/작업시간 측정이 아니다. 제한 SA의 거부를 공유 deployer 격리로 확대하지 않으며 합성 승인 거부는 alert/분석을 거치지 않았다. 진단 오류는 그대로 남아 R3/R4 전체·R5는 미완료다. 다음은 현재 revision/실패 단계의 조회 적용 조건과 모순 관측 처리이며, 완료한 T 묶음을 반복하지 않는다.
