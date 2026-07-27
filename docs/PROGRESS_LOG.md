# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-26

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-26 — 멀티테넌트 실험 전문 재작성·Notion 발행

- Status: **Notion 전문 발행 완료**. 전체 발행에서 남은 것은 LinkedIn 게시뿐이다.
- Changed: `docs/post/notion-article-ko.md`를 영상의 실제 흐름(setup→install→상태 검증→격리 반증)에
  맞춰 5,641→4,477자로 재구성하고 Humanize Korean 적용(A·변경률 14.6%·자체검증 6/6).
- Published: Notion `3a94c2420ac4801cbe99e36c16ed90fd`에 목차·표·YouTube Shorts
  (`2J9WfZV0TPE`) 영상 블록과 전문 반영.
- Verified: MP4 1080×1350·30.033s + 6시점 프레임 검토 · Notion 재조회로 제목/본문/영상 블록 확인 ·
  `git diff --check -- docs/post/notion-article-ko.md` 통과. `make check`는 문서·외부 발행 작업이라 미실행.
- Blockers: 없음. Next: `docs/post/linkedin-intro-ko.md` 최종 확인 후 LinkedIn 게시 → Phase 3(인가 강화).

## 2026-07-26 — 자연어 한 문장이 테넌트를 세운다 + 풀스택 30초 영상 (gate 1322→1341)

- Status: Agents 채팅에 문장 하나를 치면 `setup_tenancy → install_tenant_addons`가 체인으로
  돈다(17.6s). 실제 브라우저로 전 비트를 통과시킨 뒤 그 상태를 찍어 30초로 편집했다.
- Changed(코드): `src/agents/ai/tenancy_tools.py`(도구 2개) · `src/agents/platform/cluster_io.py`
  (렌더된 객체가 클러스터를 만지는 **유일한 자리**) · `Registry.uninstallable_reason` +
  `build_delivery_adapter`로 `render_*` 스크립트와 **같은 구현** 공유(복사본 0) · 시스템
  프롬프트에 체인 순서와 **그 이유**(애드온은 테넌트 ns *안의* 객체) 명시.
- Changed(영상): `scripts/demo/{prep_fullstack.sh,record_fullstack.js,build_fullstack_cut.js}` ·
  `docs/post/media/multitenancy-fullstack-30s.mp4`(1080×1350 · 30.03s · **오버레이 없음**,
  원본 153.8s를 10컷으로) · 아티클/LinkedIn/유튜브 문구 반영.
- Verified: `make check` **1341**(+19) · `render_tenancy.py` 출력이 HEAD와 stdout·stderr·exit
  code 전부 동일(리팩터 무해 증명) · **라이브 브라우저 왕복**: 빈칸 → 문장 → 체인 2단 →
  `4 / 4`·4축 ✓ → `1500m / 16`·`3 / 200` → 실제 ArgoCD Synced/Healthy → netpol 1개 삭제 시
  **network만 ✕**(globex 초록 유지) → 복구 ✓. 증거 `docs/evidence/demo-fullstack-beats.json`.
- Blockers: 없음.
- 품질 메모: 라이브가 결함 4건을 잡았고 전부 내 코드였다. (1) `apply_manifests`가 kubectl
  **경고**를 `error`에 담아 **전 스텝 성공인 실행이 `ok:False`** 로 기록됐다(Capsule deprecation
  2줄). 지금까지 잡은 건 화면이 실제보다 **좋게** 말하는 결함이었는데 이건 **나쁘게** 말한
  첫 사례다. (2) 도구 완료를 "running 문자열 부재"로 판정했는데 DOM엔 그 단어가 없다(아이콘뿐)
  → **일어나지 않은 체인을 찍을** 뻔했다. (3) 녹화 프로필엔 세션이 없어 채팅이 읽기 전용 —
  비활성 입력칸에 문장을 치고 5분 대기, 테이크 1회 손실. (4) `.argocd-demo-password`가 없어
  첫 프레임 전에 죽고 `.gitignore`에도 없었다 — **공개 아티클이 링크할 레포에 자격증명이
  커밋될** 뻔했다(클러스터 시크릿에서 읽도록 변경).
- Next: 발행(Notion 전문 · LinkedIn · YouTube Shorts) · LinkedIn "7B가 30B를 이겼습니다" 정정
  (1건·1시행 차이, temp 1.0에선 역전) · Phase 3(인가 강화).

## 2026-07-26 — 30초 영상 촬영 완료 (배속 없는 실시간)

- Status: 시나리오 A를 **실제로 찍었다**. `docs/post/media/isolation-falsified-30s.mp4`
  (1080×1350 · 30.0초). 연출 없음 — 진짜 NetworkPolicy를 지우고 진짜 push 경로로
  대시보드가 알아차리는 걸 기다렸다가 되돌린다.
- Changed: `scripts/demo/`(record_falsification.js · render_captions.js · README) +
  산출물 2종. 대본은 **최종본 실제 타임코드**로 갱신.
- Verified: 컨택트시트로 6개 시점(1·6·13·16·19·28초) 전부 자막↔화면 상태 일치 확인.
  실측 전환 **삭제 후 7.1초 · 복구 후 8.9초** → 30초에 그대로 들어가 **배속 0**.
  촬영용으로 낮춘 푸시 주기(60s→2s)는 우상단에 상시 표기. 촬영 후 60s로 원복,
  netpol 4개·4축 ✓ 복구 확인.
- Blockers: 없음. 남은 것은 발행(사용자 게이트).
- 품질 메모: **전체 화면 녹화를 폐기했다.** macOS `screencapture -v`는 권한이 있어
  동작했지만 테스트 프레임에 조작자의 다른 탭(학습 사이트·ChatGPT 대화)이 그대로
  담겼다 — 발행용 영상에 들어가면 되돌릴 수 없는 종류의 사고라 테스트 파일을 즉시
  지우고 뷰포트만 녹화하는 Playwright로 바꿨다. 부수 효과로 로그인 세션도 프레임에서
  사라졌다. 그리고 ffmpeg가 libass·freetype 없이 빌드돼 있어 `subtitles`/`drawtext`가
  **아예 없었다** — 자막을 대시보드와 같은 엔진으로 렌더해 픽셀로 넣었다. 오버레이
  `enable=` 창이 자막 목록과 어긋나면 **아무것도 실패하지 않은 채** 화면과 다른 말을
  하는 영상이 나오므로, ffmpeg 명령을 비트 목록이 생성하게 했다(체크인 안 함).
- Next: 아티클 발행(Notion 전문 + LinkedIn 링크, 영상 첨부) · Phase 3(인가 강화).

## 2026-07-26 — 시연 가능 레벨: 레지스트리→클러스터 설치 경로 + 격리 반증 리허설 (gate 1302→1322)

- Status: 영상 시나리오를 멀티테넌시+풀스택으로 재작성하고, **그 대본이 실제로 찍히는
  상태**까지 만들었다. 준비 과정에서 "레지스트리만으로는 애드온을 설치할 수 없다"는
  구조적 갭이 드러나 근본수정했다.
- Changed(문서): `docs/post/video-30s-script.md` 전면 재작성 — 추천안이 A(자연어 39초,
  **이미 발행한 소재**)에서 **격리 반증**으로 교체. 대안 B(풀스택)·C(세 종류의 부재)·D(DR).
- Changed(코드): 카탈로그 `self_hosted_repo` + `Registry.repo_for`/`capabilities_missing_repo`
  — repo URL이 `infra/onprem/addons/*.tf`에만 있어 **레지스트리가 설치 불가능한 애드온을
  선언**하고 있었다(values·scope 갭과 같은 족보). 이 필드는 이 파일의 **유일한 복사**라
  `test_catalog_repos_match_terraform`이 TF helm_release를 파싱해 불일치 시 게이트를 깬다 ·
  `scripts/render_addons.py`(읽기 전용 렌더, 클러스터 싱글턴은 **이름을 대며** 거부,
  빈 출력의 두 의미를 exit code로 구분) · `make demo-baseline`(테넌시+애드온+강제 푸시 1회).
- Verified: `make check` **1322**(+20) · `tsc` 클린 · `next build` 성공 ·
  `verify_tenancy_adoption.py` acme/globex 둘 다 adopted and bounded.
  **라이브(kind, $0)**: acme-dev-logging·acme-dev-tracing Synced/Healthy(테넌트 스코프에서
  **tempo는 이번이 처음**), 쿼터가 비로소 소비를 센다(cpu 2/16·pods 3/200).
  **반증 리허설**: netpol 4개 중 1개 삭제 → acme/dev network만 ✕, 나머지 3축과 **이웃
  globex/dev 행은 초록 유지** → 복구 시 ✓. 강제 푸시 없는 실측 지연 **18s/61s/59s**
  (푸시 60s 주기 + 폴링 15s → 최악 ≈75s). 증거 `docs/evidence/demo-isolation-falsification.log`.
- Blockers: 없음.
- 품질 메모: 라이브가 **화면이 실제보다 좋게 말하는** 결함 2건을 잡았다. (1) 플릿 표가
  `4 ok`라고 했는데 2개는 에이전트가 health를 단언할 수 없는 공유 설치였다 —
  `unknownCount`는 이미 계산돼 있었고 **아무도 쓰지 않았다**(또 소비 부재) → `N ok · M not
  assessed`. (2) `push_addon_status.py` 독스트링이 광고하던 `--once`가 미구현이라 **문서에
  적힌 명령이 그대로 죽었다**. `make dev-up`은 `--interval 60`을 써서 아무도 안 밟았고,
  문서를 읽은 내가 촬영 체크리스트에 옮겨 적으며 밟았다. 그 가드의 첫 판은 스위트를 멈춰
  세웠다(`--interval` 폼을 그냥 부르면 60초씩 영원히 잔다) — 루프는 끝나지 않는 것이
  정상이므로 sleep을 끊어서 단언하도록 고쳤다.
- Next: 아티클 발행(Notion 전문 + LinkedIn 링크) · 영상 촬영 · Phase 3(인가 강화).

## 2026-07-26 — 대시보드 멀티테넌시 관제 + 검증 훅 (gate 1290→1302)

- Status: 멀티테넌시가 CLI로만 보이던 것을 대시보드로 올렸고, 그동안 문서에만 있던
  검증 규칙을 훅으로 강제했다. 아티클 초안 3종도 `docs/post/`에 작성(발행은 사용자 게이트).
- Changed(`654c7e5`·`eebc19e`): `TenancyPosture`(채택 ns 수·쿼터 hard/used·격리 4축·티어·
  자격증명 스코프·네임스페이스 목록)를 **기존 push 경로에 실어** 대시보드까지 전달 —
  대시보드가 클러스터를 직접 조회하면 D26(허브 read 자격증명 0)이 깨진다 · 플릿 표
  (전 테넌트 × 4축, 미보고 테넌트도 행 유지) + 격리 패널(티어별 분리/공유/**미보장** 명시) ·
  Platform Add-ons 누락 4건 추가(Loki·Fluent Bit·Tempo·Capsule, 콘솔 없는 것은 사유 표기) ·
  대시보드 문구 영어화 · `make dev-up`이 push 키와 스포크 푸셔 2개를 함께 기동.
- Changed(`bad2642`): Stop 훅 `make check`(소스 변경 시만, async+asyncRewake라 실패할 때만
  깨움) + PostToolUse 훅 `tsc --noEmit`(dashboard 경로만). 기존 ruff 훅 보존.
- Verified: `make check` **1302**(+12) · `tsc` 클린 · `next build` 성공. **라이브**: acme/dev
  4/4·globex/dev 1/1이 tier=soft, credential per tenant로 대시보드에 표시. **반증까지 확인** —
  NetworkPolicy 삭제 시 network 축이 False로 뒤집히고 복구 시 True 복귀. 훅도 등록 전에
  양방향 검증(정상 exit 0 / 일부러 만든 실패 exit 2 + 정확한 요약).
- Blockers: 없음. 영상 시나리오는 A(자연어 39초)가 이미 발행된 소재라 멀티테넌시+풀스택
  기준으로 재작성 필요.
- 품질 메모: **런타임 TypeError가 났고 tsc는 내내 초록이었다.** `posture.namespaces.length`가
  구버전 에이전트 페이로드에서 터졌다 — TS 타입은 네트워크를 건너온 데이터에 대한 컴파일
  시점 주장일 뿐이고, 롤링 업그레이드 중엔 허브가 두 버전 리포트를 동시에 서빙한다.
  신규 필드를 optional로 내리고 모든 읽기 지점에 폴백을 넣었다. 같은 사건이 **필드 하나가
  푸셔·허브·대시보드 세 프로세스를 전부 통과해야 한다**는 것도 다시 보여줬다(푸셔만 재기동
  했을 때 허브가 모르는 필드를 버렸다). 훅 스크립트 자신도 첫 판이 틀렸다 — `tail -25`가
  pytest 끝의 경고 벽을 잘라 실패가 안 보였고, 요약 라인 grep으로 교체했다.
- Next: 영상 시나리오 재작성 → 촬영 · 아티클 발행(Notion+LinkedIn) · Phase 3(인가 강화).

## 2026-07-26 — faked managed 디스크립터 + DR 재구축 검증 (gate 1281→1290)

- Status: **Phase 2 완결**(M11). 남아 있던 2건을 소진했다.
- Changed(`c6d930d`): `Registry.is_managed_backend`(카탈로그에서 파생 — env가 다시 태그하면
  한 선택에 두 사실이 생긴다) + 수집기의 managed 경로(`applicable=False`·health=None) ·
  `scripts/verify_tenancy_adoption.py`(status.size와 ResourceQuota를 직접 묻는다).
- Verified: `make check` **1290**(+9). **라이브 DR 드릴**: globex/dev를 실제로 파괴하고
  레지스트리만으로 재구축 → 라벨 `diff` 완전 동일, 10초 뒤 ns=1 + ResourceQuota가 선언값
  일치(pods 100·cpu 8·mem 32Gi). 증거 `docs/evidence/phase2-managed-and-dr.log`.
- Blockers: 없음. Phase 2 잔여 0.
- 품질 메모: 재구축 직후 `Tenant ns=0`을 보고 실패로 읽었는데 **또 이른 시점의 정지
  조회**였다(첫 슬라이스의 쿼터 오판과 같은 교훈이 DR 경로에서 재발). 다만 그 10초 창은
  진짜 위험이라 — 네임스페이스는 있고 라벨도 맞고 모든 화면이 완료로 보이는데 쿼터가
  아무것도 안 묶고, **영구 고장과 육안 구별이 안 된다** — 검증기를 만들었다. 그런데
  **그 검증기가 첫 실행에서 거짓 경보를 냈다**: 다른 클러스터(k3s-lab)의 acme/prod를
  "quota unenforced"로 보고했고, 독스트링엔 cannot-check로 하겠다고 써놓고 코드가 안
  지킨 것이었다. **안 본 것은 발견이 아니다.**
- Next: Phase 3(인가 강화) · Phase 1b 잔여(스냅샷 선행) · 선택 항목들.
