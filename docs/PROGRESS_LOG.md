# PROGRESS_LOG — platform-agent

최종 갱신: 2026-08-09

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-08.md` · `docs/archive/progress-2026-07.md`

---
## 2026-08-09 — "AWS 이번 달 $0"을 두 번 보고했고 두 번 다 틀렸다 (실제 $8.81)

- Status: 사용자가 AWS 예산 경보($8.50 임계, 실제 $8.81)를 전달했다. 내가 같은 날 두 번
  "AWS 8월 $0"이라고 보고한 직후다. **점검이 아니라 경보가 잡았다.**
- Changed(원인 2개, 둘 다 안심시키는 방향): ①`aws ce get-cost-and-usage`는 **크레딧을 포함**해
  집계한다 — 크레딧이 사용액을 상계해 **순액 ≈$0**이 나왔다. 예산은
  `Not RECORD_TYPE in [Credit,Refund]`로 **총사용액**을 잰다. **두 숫자는 다른 질문의 답**이고
  (얼마가 청구되나 vs 얼마를 쓰고 있나) 방치 리소스는 후자로만 보인다. ②EKS·AMP만 보고
  **EC2를 안 봤다**. 전 리전 스윕이 필요했다.
- Verified(실측): 8월 실사용 **$8.81**(EC2 $7.54 · VPC 공인IPv4 $0.92 · 나머지 $0.33),
  월말 예측 ~$35.6. 원인은 **`slackops-devops-agent`(t3.medium, us-east-1)가 07-22부터
  18일째** 실행. 전 리전 스윕에서 running은 그 하나뿐, NAT/EIP/VPC엔드포인트 0.
- Changed(조치): **중지**(종료 아님 — 되돌릴 수 있다). `stopped` + 공인 IP 해제 확인,
  남는 건 gp3 8GB ~$0.64/월. 중지 후 전 리전 running **0대**. 남은 21일 ~$24 절감.
  다른 프로젝트(`Project=slackops-devops-agent`) 리소스라 **종료는 소유자 판단**으로 남겼다.
- Blockers: 이 레포의 07월 과금 감사 기록은 "slackops **EBS 월~$5만 잔존**"이라고 적었다 —
  그건 인스턴스가 꺼져 있다는 전제다. 기록과 실제가 달랐다.
- 품질 메모: **기본값이 안심시키는 답을 주는 도구가 셋이었다** — 크레딧 포함 집계 · `head`로
  자른 출력 · 단일 리전 조회. 오늘 산정 문서가 밟은 함정 셋이 전부 같은 계열이고 전부
  **"없다"를 성급히 주장**했다(관측 수단 0 · managed 어댑터 없음 · AWS $0). **"없다"는
  "안 보였다"보다 강한 주장이라 어떻게 봤는지를 같이 적어야 한다.**
- Next: GCP ₩20 예산(상시 발화) 재보정이 더 급해졌다 — AWS 경보는 작동했지만 GCP는 그
  채널이 이미 포화다.

## 2026-08-09 — managed 백엔드를 세 경로가 다르게 알고 있었다 (gate 1676→1685)

- Status: 추천안 2번(4a)의 **과금 없는 코드 부분**을 진행하려다, 4a 코드가 이미 대부분
  있다는 것과 **렌더 경로 하나만 비어 있다**는 것을 찾았다.
- Changed(정정): 어제 산정 문서의 *"managed 어댑터 구현 없다"*는 부정확했다. `from_managed`
  (`applicable=False`)도 `collector.py:451`의 managed 분기도 이미 있다 — 설계 문서가 Phase 2에서
  faked 디스크립터로 증명하라던 게 실제로 되어 있었다. **세션에서 "없다"를 세 번째로 잘못 말했다.**
- Changed(진짜 구멍): 세 경로가 서로 다르게 안다 — **읽기**는 알아보고, **쓰기**는 만들 수 없고
  (`registry_write`가 `managed=True` 없이 해석), **렌더는 모른다**. `desired_addons`가 백엔드를
  Helm 차트 이름으로 그대로 넘겨(`argocd.py`: `"chart": addon.backend`), `logging: cloudwatch-logs`
  선언 시 GitOps가 **Grafana 저장소에서 `cloudwatch-logs` 차트를 찾는다**(라이브 실증).
  `ManagedBackendNotRenderable`로 거부하고, `is_managed`를 **collector와 같은 콜러블**로 받는다
  (두 경로가 "managed인가"에 두 답을 갖지 않도록 — 431aeab가 지운 모양).
- Verified: 반증 2건 red(가드 제거 시). `make check` **1685**(+9).
  ⚠️정밀화 2회: `observability`로 재려다 **클러스터 스코프라 싱글턴 가드가 먼저 잡는 것**을
  발견 → 막히지 않는 조합은 **네임스페이스 스코프 + managed**(`logging`·`tracing`)뿐이라 그걸로
  교체 · 현재 레지스트리엔 **클라우드 substrate가 0**이라(kind·k3s) 이 경로가 도달 불가여서
  테스트가 env를 **짓는다** — 그게 정확히 Phase 4가 만드는 것이다.
- Blockers: 4a의 나머지는 **과금**이다(AMP 워크스페이스). 승인 대기.
- 품질 메모: 클러스터 스코프 managed는 싱글턴 가드가 잡되 **안내가 틀린다**("Prometheus CR을
  주라" — 관리형엔 설치할 것이 없다). 고치지 않고 기록했다 — 가드 순서를 바꾸면 기존 에러의
  정체가 바뀌고, 그건 "managed가 무엇을 렌더해야 하는가"라는 Phase 4 결정과 같이 가야 한다.
  **무엇을 렌더할지는 일부러 발명하지 않았다.**
- Next: 4a 승인(≈$5/월) 또는 $0 선행(예산 재보정·결제 내보내기) — 둘 다 사용자 몫.

## 2026-08-08 — 커밋을 경로에 한정 + 막힌 근거 재측정 (gate 1668→1676)

- Status: attach UI를 재려다 **그 앞의 구멍**을 먼저 찾았고, 이어서 남은 막힌 항목의
  근거를 돌려 봤다. PR #6·#7 병합.
- Changed(**구멍**): `attach_addon.py`가 조작자에게 `git commit -am`을 시켰다. `-a`는
  **수정된 모든 추적 파일**을 담으므로, 다른 게 더러우면 계획이 이름 댄 적 없는 파일까지 든
  PR이 열린다 — **"한 파일만" 불변식을 세우려고 존재하는 도구가 자기 지시로 그걸 깨는 경로**를
  들고 있었다. `commit_attachment`로 **경로 한정 커밋**(`-- <path>`) + `--commit`.
  브랜치 선점검은 **파일을 쓰기 전에** 돈다(아니면 "거부했는데 편집은 남는다").
  push·API는 그대로 조작자 몫.
- Verified: 반증 — `-- <path>`→`-a`로 **3건 red**, 브랜치 가드 제거로 **2건 red**.
  테스트는 트리를 **일부러 더럽힌 채** 잰다(**깨끗한 트리에선 두 방식이 구별되지 않고, 그래서
  안 보였다**). 라이브(임시 클론, 3파일 더럽힘): 커밋에 담긴 파일 **1개**, push 0 —
  하필 그 더러운 둘이 **이 도구의 소스**였다. `make check` **1676**(CI 일치, 새 git 테스트
  8건 리눅스에서도 PASSED).
- Verified(내 가드가 또 틀렸다): 처음 쓴 브랜치 테스트는 **가드를 지워도 초록**이었다 —
  `switch -c`가 내는 **git 자신의** 메시지에도 `already exists`가 있어 match가 그걸 받았다.
  그리고 "같은 첨부 두 번"은 이 가드의 시나리오가 아니었다(**플래너가 한 층 먼저** 거부).
- Changed(**근거 재측정**): attach UI가 막힌 이유가 "Next+FastAPI 두 층"이 아니다 —
  **FastAPI 층이 아예 없다**(Next→OIDC→DynamoDB). 진짜 구속 조건은 쓰기 대상이 git 파일인데
  UI는 Vercel이라 파일시스템·git·python이 없다는 것 → 같은 줄의 "실제 PR 생성"은 별개 잔여가
  아니라 **이 항목의 구속 조건**이다. MCP 항목도 근거만 틀렸다(생성자 0이 아니라 `bridge.py:35`
  하나, 그걸 만드는 건 테스트뿐). **성립한 근거 3건**(cost_metrics·kind 스냅샷·Cosign/k3s)은
  그대로 뒀다 — **성립하는 것도 결과다.**
- Blockers: 남은 항목은 전부 **승인·비용 / 정책 결정 / 외부 조건 / 선행 인프라 / 보류 지시**.
- 품질 메모: **세는 함정 둘을 실제로 밟았다** — `src/stacks/cdk.out`은 untracked인데 파일
  grep은 무시된 디렉터리까지 훑고(첫 측정 10건이 전부 빌드 사본), **docstring 사용 예시가
  호출로 보인다**. 후자는 **D39가 이미 밟은 함정**이라 이번엔 결론이 아니라 **세는 방법**을
  계획에 적었다.
- Next: Phase 4(billable, 별 승인)와 attach UI(플래너를 어디서 돌릴지) 둘 다 승인 사안.

## 2026-08-08 — 게이트가 검사하지 않는 것과 통과하는 것이 같은 색이었다

- Status: 미커밋 `/tidy-docs` 증분을 PR로 랜딩하다가(**PR #2**) CI 로그에서 문서와
  어긋나는 숫자를 봤다 — 문서 baseline `1668 passed, 1 skipped`인데 CI는 **1666/3**.
- Changed(원인): 수집 총계는 1669로 같고 **2개가 pass→skip**이었다. 하필
  `test_terraform_module`·`test_onprem_addons_module`의 `test_terraform_validate_passes`
  = **이 레포가 배포하는 IaC를 검증하는 둘**. `skipif` 조건이 **`terraform 미설치 OR
  모듈 미초기화`**인데 러너가 **두 절을 다** 만족했다(바이너리 없음 + `.terraform/`는
  gitignore라 새 체크아웃은 초기화된 적 없음 → **설치만 해도 여전히 skip**).
  즉 **D43이 병합 조건으로 삼은 게이트가 자기가 대체한 기계보다 적게 검사했다.**
- Changed(수정, **PR #3**): `gate.yml`에 `setup-terraform` **1.15.8 핀**
  (python 3.13 핀과 같은 이유=로컬에서 검증된 버전) + `terraform_wrapper: false`
  (테스트가 subprocess로 파싱) + `init -backend=false` **두 모듈만**
  (`infra/onprem/terraform`을 주장하는 테스트는 없다). 버전은 **커밋된 lock 파일**이
  고정하므로 자격증명 없이 결정적이다.
- Verified(반증 먼저 선언): *"init을 지우면 1666/3으로 돌아간다"* → 수정 후 CI가
  **1668/1**, 두 테스트 **PASSED**, 남은 skip 1건은 의도된 인-테스트 skip.
  run `31250113860`(전)↔`31250493800`(후). 증거
  `docs/evidence/ci-terraform-validate-skipped.log`. PR #2·#3 병합 완료.
- Changed(정리 중): 아카이브가 **자기 자신**을 "이전 이력"으로 가리키던 순환 포인터 1건 정정.
- Blockers: 없음. 남은 건 Phase 4(billable, 별 승인).
- 품질 메모: **skip은 실패가 아니라서, 검사하지 않는 게이트와 통과한 게이트가 같은
  색이다.** Risk 12②와 같은 계열이되 방향이 반대다 — 12②는 "로컬만 통과"였는데 이건
  **로컬이 통과시키고 CI가 안 도는** 쪽. 그래서 게이트 숫자에는 날짜(12①)뿐 아니라
  **어느 기계에서 쟀는지**도 붙어야 한다.
- Next: Phase 4(billable, 별 승인)만 남았다.

