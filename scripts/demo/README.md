# scripts/demo — 30초 영상 파이프라인

**두 벌이 있다. 섞어 쓰면 안 된다.**

| | 대본 | 촬영 | 편집 | 자막 | 산출물 |
|---|---|---|---|---|---|
| **풀스택**(현행) | `docs/post/video-30s-script.md` | `prep_fullstack.sh` → `record_fullstack.js` | `build_fullstack_cut.js` | **없음** | `multitenancy-fullstack-30s.mp4` |
| 격리 반증(구판) | (대본에서 폐기) | `record_falsification.js` | `render_captions.js` | 있음 | `isolation-falsified-30s.mp4` |

## 현행 — 풀스택 (4단계)

```bash
cd <작업 디렉터리>            # raw-fullstack/, fs-*.png, mp4 가 여기 쌓인다
npm i playwright             # 브라우저는 설치된 Chrome을 쓴다(channel:'chrome')
export NODE_PATH=$PWD/node_modules   # 스크립트는 repo에 있고 require는 스크립트 기준으로 해석된다

bash <repo>/scripts/demo/prep_fullstack.sh          # 1. 빈칸 상태
node <repo>/scripts/demo/record_fullstack.js        # 2. 촬영 (원본 ~2분 30초 + beats)
node <repo>/scripts/demo/build_fullstack_cut.js     # 3. 컷 계획 + 배지 PNG + build 스크립트
bash build_fullstack_video.sh                       # 4. 30.0초 mp4
```

촬영 스크립트는 **프레임 밖에서 두 번 로그인한다** — 대시보드(로컬 dev 프로바이더, admin)와
ArgoCD(클러스터 시크릿). 둘 다 없으면 각각 이렇게 실패한다: 채팅 입력이 비활성이라
문장을 쳐도 아무 도구가 안 돌고(테이크 1회 손실), ArgoCD 비트가 로그인 폼을 찍는다.

`build_fullstack_cut.js`는 합계가 30.0초가 아니거나 비트가 순서를 벗어나면 **거부한다**.
컷은 경과 시각 배지가 튀는 것으로 드러나고, 배지와 ffmpeg의 `enable=` 창은 같은
`SEGMENTS` 목록에서 생성되므로 서로 어긋날 수 없다.

## 구판 — 격리 반증 (참고용)

산출물: `docs/post/media/isolation-falsified-30s.mp4` (1080×1350, 30.0s, 무음 트랙 포함).

영상은 **연출이 아니다**. 스크립트가 진짜 NetworkPolicy를 지우고, 진짜 push 경로를 통해
대시보드가 알아차리는 것을 기다리고, 되돌린다. 자막 타이밍은 DOM이 실제로 바뀐 시각에서
나온다(`beats.json`) — 의도가 아니라 관측에 맞춰 자른다.

## 전제

- `make dev-up` + `make demo-baseline` 으로 4축이 전부 초록인 상태
- Chrome 설치(Playwright `channel: 'chrome'` — 브라우저 다운로드 없음)
- `npm i playwright` 가 된 작업 디렉터리, `ffmpeg`

## 3단계

```bash
cd <작업 디렉터리>   # raw/, cap-*.png, mp4 가 여기 쌓인다

# 1. 촬영 — 푸시 주기를 낮추고(촬영용) 원본 webm + beats.json 생성
pkill -f "push_addon_status.py --tenant acme"
PLATFORM_PUSH_KEY=local-dev python <repo>/scripts/push_addon_status.py \
  --tenant acme --env dev --hub http://127.0.0.1:8077 --interval 2 &
mkdir -p raw && node <repo>/scripts/demo/record_falsification.js

# 2. 자막 PNG + build_video.sh 생성
node <repo>/scripts/demo/render_captions.js

# 3. 합성
bash build_video.sh

# 촬영 후: 푸시 주기를 60초로 되돌린다 (기본값)
```

## 왜 이런 모양인가

- **뷰포트만 녹화한다.** macOS `screencapture -v`는 전체 화면을 담아 조작자의 다른 탭까지
  파일에 들어간다(테스트에서 실제로 확인하고 폐기했다). Playwright는 자기가 띄운
  뷰포트만 기록하고, 새 프로필이라 로그인 세션도 프레임에 없다.
- **자막이 픽셀로 들어온다.** 이 환경의 ffmpeg는 libass·freetype 없이 빌드돼 있어
  `subtitles`/`drawtext` 필터가 아예 없다. 자막을 대시보드와 같은 엔진으로 렌더해
  한글 타이포를 맞춘다.
- **ffmpeg 명령은 생성물이다.** 오버레이의 `enable=` 창과 자막 목록이 어긋나면
  **아무것도 실패하지 않은 채** 화면과 다른 말을 하는 영상이 나온다. 그래서 비트 목록을
  가진 `render_captions.js`가 `build_video.sh`를 직접 쓴다(체크인하지 않는다).
- **배속을 쓰지 않았다.** 실측 전환이 삭제 후 7.1초·복구 후 8.9초라 30초에 그대로 들어갔다.
  대신 낮춘 푸시 주기를 화면 우상단에 상시 표기한다 — 기본 60초 주기를 나중에 재보는
  사람과 영상이 어긋나면 안 된다.

## 다시 찍어야 하는 때

대시보드 레이아웃이 바뀌면 크롭 좌표(`crop=768:960:288:8`)가 틀어진다. 프레임을 한 장
뽑아 확인하고 좌표를 고칠 것 — 크롭이 틀리면 잘린 표가 그대로 발행된다.
