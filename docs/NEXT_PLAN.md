# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-11

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`를 참조한다. **≤120줄** 유지.

## 다음 작업 리스트 (2026-07-12 갱신)

- [x] ~~**추적 IA 라이브 실증(자연어 4스텝)**~~ — LinkedIn 데모 녹화 세션에서 ①provision+deploy(2행) → ②앱 롤백(단일-row 승계) → ③History 중첩 상세 → ④teardown cascade(자동 rolled-back·Rollback 비활성)를 브라우저 end-to-end 실증 완료(2026-07-13). 증거: `docs/post/local-onprem-edited.mp4`.
- [x] ~~**전체 커밋**~~ — 추적 IA 정리분은 커밋 `930fe98`에 포함 완료.
- [x] ~~대시보드 UI Rollback 팝업/체인~~ — native prompt→인앱 팝업, app(Deployments)/cluster(Provisioning) 분리, 단일-row 승계·teardown cascade 구현. (라이브 클릭 실증은 위 항목)
- [x] ~~**`feat/onprem-offline-recording-hybrid-rollback` push/머지 결정**~~ — 완료: `0b9148c`+`930fe98`가 **origin/main에 푸시·머지됨**(서버 main HEAD=`930fe98`). feat 브랜치는 main과 동일 커밋(중복).
- [x] ~~**중복 `feat` 브랜치 삭제**~~ — 로컬+원격 삭제 완료(2026-07-13). origin에는 `main`(=`a1acfea`)만 존재.
- [x] ~~(선택) **NEXT_PUBLIC 프로덕션 인라인**~~ — 해소/stale(2026-07-13): 16.2.10 `next build` 실측상 `.env.local` NEXT_PUBLIC 정상 인라인(상수 폴딩 확인). 코드 수정 불필요.
- [x] ~~**origin push**~~ — 완료: 로컬 main == origin/main == `930fe98` (ahead/behind 0/0).
- [x] ~~A2A specialist endpoint + Agent Card discovery~~ — kagent Card discovery/skill match + JSON-RPC 0.3 transport 지원 완료.
- [x] ~~kagent ↔ 로컬 Qwen 연결~~ — local Qwen ModelConfig + A2A read-only task(tool result 반환) 실증 완료.
- [x] ~~On-Prem k3s Ansible Provision~~ — 기존 Multipass `k8s-lab`(Ubuntu 24.04)에서 k3s v1.31.4 node Ready 및 재실행 `changed=0` 검증 완료.
- [x] ~~AWS Provision adapter~~ — AWS CDK diff(기본) / approved deploy / approved destroy guard 구현 및 unit test 완료.
- [x] ~~**AWS CDK live diff 재검증**~~ — 완료(2026-07-13). **근본원인**: synth "미완"은 stale **1.8GB 재귀 cdk.out**(exclude 추가 전 산출물) 때문 — 삭제 후 synth **~17s 완료**, 새 cdk.out 37M, 템플릿 **99 resources**. `cdk diff IncidentAgentStack --no-change-set` **exit 0**. **진짜 diff = 인프라/IAM 변화 0, Lambda 13개 코드 asset-hash churn만**(재번들링 노이즈). ⚠️ **주의**: diff는 반드시 context를 줘야 함 — `-c vercelTeamSlug=men16922 -c vercelProjectName=platform-agent -c vercelOidcProviderArn=arn:aws:iam::908601828278:oidc-provider/oidc.vercel.com/men16922`. 안 주면 `VercelDashboardReadRole`(조건부, stack `incident_agent_stack.ts:104`)이 빠져 **가짜 삭제 diff**가 남.
- [x] ~~kagent 기본 에이전트 10개 정리(`helm uninstall`) 또는 데모용 유지 결정~~ — **MOOT(2026-07-13)**: kagent를 호스팅하던 kind 클러스터가 이미 teardown됨. 확인 결과 활성 kube context 없음(kind 0개), Multipass k3s VM `k8s-lab`(Ready, v1.31.4)에도 kagent namespace·helm·비시스템 파드 전무 → 정리 대상 부재, 조치 불필요.

### (이전 리스트 — 참고)

- [x] ~~세션 외 미커밋 변경 검토/정리~~ — models.py ServiceSpec 재수출 복구(`eaff5ac`), 나머지 chore 커밋(`5035913`) 완료.
- [x] ~~AI Model Router 채팅 live 데모 + Deployments 추적 실증~~ — MLX Qwen30B→kind 배포 + recorder→DynamoDB→대시보드 aws-live 노출까지 end-to-end 검증 완료(2026-07-11).
- [ ] 대시보드 **브라우저 UI**에서 인증된 배포 클릭 데모 — GitHub OAuth 로그인 필요(사용자 수행). 백엔드/배선/read 경로는 모두 검증됨.
- [ ] (deferred) Slack App 실 생성/토큰 설정 — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요
- [x] ~~LinkedIn 데모 비디오 편집~~ — `docs/post/local-onprem.mov` 원본 영상을 18.2초 자막(Terraform 등 실제 실행 매핑) 포함된 최적화 mp4로 편집 및 렌더링 완료.
- [ ] (deferred) 테크 아티클(LinkedIn / Medium) 리뷰 및 소셜 채널 배포

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
