# 시연 대본 — 대시보드에서 멀티테넌시 풀스택 (LinkedIn 첨부용 30초)

시연 주제: **오프라인 로컬 Qwen에게 한 문장을 주면, 멀티테넌트 경계와 그 안의 스택이 선다.**
발행 구조 — **Notion에 전문 · LinkedIn에 소개 글 + 영상 + Notion 링크 · YouTube(Shorts)에 영상.**
유튜브 제목·설명 → 이 문서 맨 아래 [유튜브 발행](#유튜브-발행).

## 이 영상이 지켜야 할 것

- **자막 없음.** 서사는 LinkedIn 본문이 한국어로 이미 지고 있다. 영상이 같은 말을 자막으로
  반복하면 본문이 죽고, 영상은 "자막 밑에 깔린 배경"이 된다.
- **화면이 계속 움직여야 한다.** 이전 판이 실패한 지점이 정확히 여기다 — 30초 동안 바뀌는 게
  표 안의 글리프 하나뿐이었고, 자막을 빼면 남는 게 없었다.
  움직임의 출처는 넷: **문장이 타이핑된다 · 도구 블록이 실행된다 · 표가 채워진다 · 화면을 이동한다.**
- **말 없이 읽히게.** 빈칸 → 채워짐, 회색 → 초록, 0 → 3. 색과 숫자는 번역이 필요 없다.
- **실물로 이동한다.** 대시보드에서 ArgoCD를 열어 같은 이름의 Application이 거기 있는 걸 보여준다.
  목업이 아니라는 걸 증명하는 가장 싼 방법이고, 동시에 화면 전환이라 움직임이 크다.
- **오버레이를 아예 쓰지 않는다.** 자막도, 경과 시각 배지도 없다. 프레임은 대시보드뿐이다.
  대신 **컷 편집이라는 사실과 촬영용 푸시 주기(60s→2s)는 게시 본문이 진다**
  (`linkedin-intro-ko.md`). 배속은 쓰지 않았지만, 영상 안에 컷을 드러내는 장치가 없으므로
  고지가 파일 밖에 있어야 한다 — 90초의 대기를 조용히 삼킨 영상은 이 프로젝트가
  피하려고 애쓰는 바로 그 물건이다.

## 스토리: 문장 하나가 테넌트를 세운다

git 레지스트리에 선언만 있고 클러스터엔 아무것도 없는 상태에서 시작해, **사람이 kubectl을 한 번도
치지 않고** 격리 → 풀스택 → 증명까지 간다. **빈칸에서 시작하는 게 핵심**이다. 채워지는 걸 봐야
채워진 게 의미가 있다.

| # | 화면에서 일어나는 일 | 이게 증명하는 것 |
|---|---|---|
| 1 | Provisioning 화면. 플릿 표의 `acme/dev`가 **never reported** (앰버), globex는 초록 | 선언과 실재는 다르다 |
| 2 | Agents로 이동 → 문장 한 줄 입력 → `setup_tenancy` 블록이 **running → done** | 사람이 매니페스트를 만들지 않는다 |
| 3 | 이어서 `install_tenant_addons`가 **running → done**, 요약이 shared 2개를 따로 적는다 | 한 문장이 **체인**을 돈다 |
| 4 | Provisioning으로 이동 → `acme/dev` 행이 살아나며 Namespaces **`4 / 4`**, 4축이 차례로 ✓ | 네임스페이스만 나눈 게 아니다(쿼터·네트워크·RBAC·PSS) |
| 5 | 같은 순간 애드온은 아직 `drifted` · `1 of 4 unhealthy` (빨강), CPU `0 / 16`·pods `1 / 200` | **경계가 먼저 서고 스택이 뒤따른다** — 화면이 진행 중을 숨기지 않는다 |
| 6 | 1분 뒤 `synced / healthy`, CPU **`1500m / 16`**, pods **`3 / 200`**, observability·progressive는 `shared` | 쿼터가 선언이 아니라 **실제로 센다** · 테넌트마다 프로메테우스를 주지 않는다 |
| 7 | globex 탭 클릭 → 같은 클러스터, **자기 쿼터 `0 / 8`** | 한 클러스터에 두 팀 |
| 8 | Add-ons의 **ArgoCD `Open`** 클릭 → 실제 ArgoCD에 `acme-dev-logging`·`acme-dev-tracing` Synced/Healthy | 대시보드가 목업이 아니다 |
| 9 | 대시보드 복귀 → netpol 1개 삭제 → **acme network ✕, globex는 ✓ 유지** → 복구 | 경계는 테넌트별이고, **반증된다** |

9비트는 30초에 빡빡하다. **먼저 버릴 순서: 7 → 6 → 5.** 2·3(체인)과 9(반증)는 이 영상의
논지 자체라 남는다.

## 실측 (2026-07-26, kind, $0)

한 문장이 도는 시간과 화면이 따라오는 시간은 다르고, 편집은 후자에 맞춰야 한다.

| 구간 | 실측 | 비고 |
|---|---|---|
| 문장 → 도구 2개 완료 | **17.6s** | 빈 상태에서. 기존 상태 재실행은 7.9s |
| Application → Healthy | **15~40s** | loki·tempo 파드가 뜨는 시간. 이미지가 캐시돼 있으면 15s |
| 클러스터 → 대시보드 반영 | 촬영 **2s** / 기본 60s | 푸시 주기. 기본값 최악 ≈75s(푸시 60 + 폴링 15) |
| netpol 삭제 → 축이 ✕ | **7.1s** | 촬영 주기 기준 |
| netpol 복구 → 축이 ✓ | **8.9s** | 〃 |

원본은 **2~3분**이 정상이다(실제 153.8초). **30초는 편집 결과물**이다.
영상 안에는 그 사실을 알리는 표시가 없으므로 — 오버레이를 쓰지 않기로 했다 —
**컷 편집이라는 사실과 촬영용 푸시 주기(60s→2s)는 게시 본문이 진다.** 기본값으로 나중에
재보는 사람과 영상이 어긋나면 안 되고, 그 고지가 파일에 없으면 본문에는 반드시 있어야 한다.
실측 플립(7.1s/8.9s)은 촬영 주기 기준이며, 이번 테이크에서는 12.1s/10.4s였다.

## 화면에 칠 문장

```
Stand up tenant acme in the dev environment on this cluster:
create its isolation boundary and then install the add-ons it declares.
```

이 문장이 `setup_tenancy` → `install_tenant_addons`를 부른다. 순서는 우연이 아니라
시스템 프롬프트에 **이유와 함께** 적혀 있다(애드온은 테넌트 네임스페이스 *안의* 객체라
경계가 없으면 실패한다). 클러스터가 없는 상태라면 `provision_cluster`가 앞에 한 칸 더 붙는다.

## 촬영

```bash
make dev-up                      # 스택 + 콘솔 포트포워드 + 푸셔
make stack-consoles-status       # 5개 전부 2xx/3xx 인지 먼저 확인
bash scripts/demo/prep_fullstack.sh   # ★ 빈칸 상태를 만드는 건 이 스크립트다
node scripts/demo/record_fullstack.js
```

`prep_fullstack.sh`를 빠뜨리면 `record_fullstack.js`는 **첫 프레임에서 죽는다**
(`acme/dev is already reporting`). 녹화 스크립트는 빈칸을 만들지 않고 **검사만 한다** —
이미 완성된 화면으로 시작한 컷이 과거에 두 번 나왔기 때문에 일부러 그렇게 돼 있다.

- **ArgoCD 세션은 스크립트가 알아서 만든다.** 클러스터의 `argocd-initial-admin-secret`에서
  비밀번호를 읽어 프레임 밖에서 로그인하고 쿠키를 심는다. 준비할 파일은 없다 —
  예전 판이 요구하던 `.argocd-demo-password`는 **없어졌고, `.gitignore`에도 넣어뒀다**
  (그 파일이 있었다면 공개 아티클이 링크하는 레포에 자격증명이 커밋될 뻔했다).
  세션 없이 8번 비트를 열면 **Applications가 아니라 로그인 폼이 찍힌다**(실제로 확인함).
- 촬영 후 푸시 주기를 60s로 원복하고, netpol 4개·4축 ✓ 복구를 확인한다.
- 파이프라인 상세 → `scripts/demo/README.md`.

### 라이브 검증 (2026-07-26, 실제 브라우저)

대본 전체를 사람이 쓰는 그대로 한 번 통과시켰다. 비트 1(빈칸) → 2·3(채팅에 문장 → 도구
블록 2개) → 4~6(플릿 표 4/4·4축 ✓·`1500m / 16`·`2 ok · 2 not assessed`) → 8(ArgoCD) →
9(netpol 삭제 시 network만 ✕, globex 초록 유지 → 복구 시 ✓) 전부 화면에서 확인됐다.
그 과정에서 8번이 로그인 폼으로 떨어지는 것과 자격증명 파일 문제가 드러나 고쳤다.

## 완성물 (2026-07-26)

**`docs/post/media/multitenancy-fullstack-30s.mp4`** — 1080×1350 · **30.03초** · h264 + 무음 aac · 2.0MB.
원본 **153.8초**(2분 34초)를 10개 컷으로 줄인 것이고, 배속은 쓰지 않았다. **오버레이 없음.**
비트 기록 → `docs/evidence/demo-fullstack-beats.json`.

컷 계획은 `scripts/demo/build_fullstack_cut.js`가 `beats-fullstack.json`에서 생성한다.
합계가 30.0초가 아니거나 비트 순서가 뒤바뀌면 **빌드가 거부한다**.

아래 "경과" 열은 **원본에서의 시각**이다(영상에는 표시되지 않는다). 00:40 → 01:40 사이가
애드온이 Healthy가 되기를 기다린 1분이고, 그 대기가 컷으로 사라진 자리다.

| out | 원본 경과 | 화면 |
|---|---|---|
| 0.0–2.8 | 00:06 | never reported (선언만 있음) |
| 2.8–7.0 | 00:12 | 문장 타이핑 |
| 7.0–10.0 | 00:33 | `setup_tenancy` 완료 |
| 10.0–13.5 | 00:35 | `install_tenant_addons` + 요약 |
| 13.5–17.5 | 00:40 | 4축 ✓ (애드온은 아직 reconcile 중) |
| 17.5–19.7 | 01:40 | `1500m / 16` · `3 / 200` · synced/healthy |
| 19.7–21.7 | 01:44 | globex — 자기 쿼터 `0 / 8` |
| 21.7–25.0 | 01:55 | 실제 ArgoCD의 두 Application |
| 25.0–28.0 | 02:15 | **network ✕** · globex 초록 유지 |
| 28.0–30.0 | 02:30 | 복구 → ✓ |

마지막 두 컷은 `kubectl`을 친 시각이 아니라 **축이 실제로 뒤집힌 시각**
(`network_false`/`network_true`)에 걸어야 한다. 처음 계획은 삭제 시각에 걸었는데, 화면은
그 뒤 12초 동안 아무 변화가 없어서 **아무 일도 일어나지 않는 정지 화면**이 찍혔다.

## 하지 않기로 한 것

- **한글 자막.** 위 참조.
- **터미널 화면.** 조작자 화면 녹화는 사적인 탭까지 담긴다(실제로 테스트에서 확인하고 폐기).
  브라우저 뷰포트만 녹화한다 — 그리고 이제 명령이 **화면 안**(Agents 채팅)에 있으므로
  터미널을 보여줄 이유 자체가 없어졌다.
- **Grafana를 여는 비트.** 클러스터 Grafana의 데이터소스는 `loki-gateway.monitoring.svc`와
  `tempo.monitoring.svc`를 가리킨다. 즉 화면에 뜨는 건 **공유 설치물의 데이터**고, 방금 세운
  테넌트의 loki/tempo(`acme-dev-logging`·`acme-dev-tracing`)는 거기 없다. "테넌트 스택이
  선다"의 증명으로 쓰면 화면이 실제보다 좋게 말한다. 실물 증명은 ArgoCD 한 곳으로 간다.
- **격리 반증 단독 30초.** 그건 주장 하나짜리 정지 화면이었다. 이제 마지막 비트(9번)로 들어간다.
- **속도 조작으로 30초 맞추기.** 배속 대신 **컷**을 쓰고, 경과 시각으로 컷을 드러낸다.

## 유튜브 발행 (영어)

30초 · 1080×1350(4:5) → **Shorts**. 4:5는 플레이어에서 위아래가 약간 남지만, 표를 읽히게
하려고 고른 비율이라 그대로 둔다.

**제목** (하나 고를 것 — 위가 추천)

```
One sentence stands up a Kubernetes tenant — local LLM, no cloud
Delete one NetworkPolicy and the dashboard flips — multi-tenancy you can falsify
A local 7B model built this tenant in 17 seconds (Kubernetes multi-tenancy)
```

**태그** (YouTube tags 필드, 콤마 구분)

```
kubernetes, multi-tenancy, platform engineering, gitops, argocd, local llm, qwen, mlx,
ai agent, sre, devops, networkpolicy, capsule, on-prem kubernetes, kubernetes tenant isolation
```

제목·설명에 붙일 해시태그는 **3개까지만** 쓴다(그 이상은 제목 위에 안 뜬다):
`#Kubernetes #GitOps #LocalLLM`

**설명을 넣는다면 이 두 줄은 반드시 포함할 것** — 영상에 오버레이가 없어 컷을 드러내는 장치가
파일 안에 하나도 없다. 이 고지는 설명란이 진다(LinkedIn 본문도 같은 이유로 같은 문단을 갖는다).

```
Recorded in real time, no speed-up. Only the waiting was cut (2m34s original → 30s).
The dashboard's status refresh was lowered from 60s to 2s for the recording.
```

## 재촬영 트리거

- 대시보드 레이아웃 변경 → 크롭 좌표가 틀어진다. 프레임 한 장 뽑아 확인할 것.
- 콘솔 링크가 하나라도 DEAD → `make stack-consoles-status`가 먼저 걸러야 한다.
  죽은 링크를 클릭하는 장면이 들어가면 시연 전체의 신뢰가 깎인다.
- 축이 의도한 것 말고 같이 뒤집히면 환경 오염 → 정리 후 재촬영.
- 에이전트가 도구를 **다른 순서로** 고르면(모델·프롬프트 변경 후) 2·3번 비트가 무너진다.
  촬영 전에 문장을 한 번 흘려 `setup_tenancy → install_tenant_addons` 순서를 확인할 것.
