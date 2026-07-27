# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-28

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

## 2026-07-28 — Phase 3 완결: ②reconciler 충돌 거부 · ③읽기 쪽 테넌트 경계 (gate 1355→1377)

- Status: Phase 3 ①②③ 종료. ②는 **거부까지**가 최종 상태이고 그 이유가 구조적이다.
- Changed(②, `9e78f81`): `platform/reconciler.py` — 소유 표식을 **라이브 객체에서** 읽어
  reconciler가 되돌릴 롤백을 거부. 되돌리는 액션만 막는다(restart·scale은 desired로 수렴).
- Changed(③, `1c13a59`): `dashboard/src/lib/visibility.ts` 단일 seam + 플릿 라우트 배선 ·
  `UserRecord.tenants` · `middleware.ts`→`proxy.ts`(Next 16 deprecation) · 죽은
  `ROUTE_PROTECTION` 제거.
- Verified: `make check` **1377**(+22 누적) · `tsc` 클린 · `next build` 성공.
  **라이브(kind, $0)**: ② 같은 워크로드에 out-of-band 변경 → **10초 만에 selfHeal이 되돌림**
  (전제 자체를 먼저 반증) → ArgoCD 관리 롤백 거부 / 같은 워크로드 restart는 정상 실행.
  ③ 빌드 산출물에 익명 curl → `restricted:true` + 빈 플릿. **fail-open 주입 반증**으로
  테스트가 실제로 잡는 것도 확인(2건 실패 → 되돌리니 8건 통과).
  증거 `docs/evidence/phase3-{reconciler-conflict,viewer-visibility}.log`.
- Blockers: 없음.
- 품질 메모: ②의 후반(selfHeal pause)은 **구조적으로 막혔다** — Application이 `argocd`
  네임스페이스에 있고 테넌트 스코프 자격증명은 그것을 읽지도 못한다(`Forbidden` 실측).
  즉 Phase 3①과 3② 경로1이 정면 충돌하고, `apps-in-any-namespace`도 비활성이라
  테넌트 로컬 우회로가 없다. 설계의 권장안인 registry write-back은 Phase 5 의존이라
  Phase 3 안에서 실행 불가 — **계획 자체의 순서 충돌**이다(→ D32).
  ③에서는 정책이 **두 군데 적혀 있고 둘 다 안 도는** 상태를 발견했다.
  `ROUTE_PROTECTION`은 소비자 0이었고, **테스트가 그 죽은 코드의 존재를 고정**하고
  있었다 — 선언을 단언하는 가드가 선언-미소비 정책이 살아남는 방식이다.
  그리고 `AGENTS.md` 지시대로 Next 문서를 먼저 읽은 덕에 `middleware` deprecation을
  잡았다. 안 고쳤으면 고장 모드는 **쓰기 라우트 matcher가 조용히 안 도는 것**이었다.
- Next: Phase 4(managed 어댑터, billable) 또는 Phase 5(레지스트리 쓰기 → ②를 GitOps-native로
  닫음). 잔여: grant 있는 viewer의 브라우저 왕복 · incidents/deployments는 여전히 무파티션.

## 2026-07-27 — Phase 3① 자격증명 격리 full (gate 1341→1355)

- Status: Phase 1a가 온프렘에서만 세운 "자격증명이 경계"를 전 러너·두 디스패치 경로로 확장.
  라이브가 Phase 1a 증명 자체의 구멍을 드러냈다.
- Changed: `scope.py`에 `guard_scoped_action` 단일 가드 + `resolve_incident_scope` 이관(디스패치
  경로가 둘인데 로직이 `aws/executor.py`에만 있어 **GCP 경로는 스코프가 없었다**) ·
  `run_gcp_action`/`run_azure_action`이 scope 수령 · seam이 전 분기에 전달 ·
  `render_rbac`가 바인딩 대상 **ServiceAccount를 렌더**(누락돼 있었음).
- Verified: `make check` **1355**(+14). **라이브(kind, $0)**: SA 생성 후 실 토큰 발급 →
  자기 ns `yes` / 이웃 테넌트 `Forbidden` / 클러스터 스코프 `Forbidden`(판정 주체가 **API 서버**) ·
  실 러너 in-scope 재시작 성공(새 ReplicaSet, rollout 정상) · cross-tenant/무-스코프는 kubectl
  이전 거부 · gcp/azure 4케이스 전부 **인증·네트워크 이전** 거부.
  증거 `docs/evidence/phase3-scoped-credentials-all-runners.log`.
- Blockers: 없음.
- 품질 메모: **RoleBinding이 존재하지 않는 SA를 가리키고 있었다.** k8s는 없는 subject로의
  바인딩을 조용히 받으므로 `kubectl get rolebinding`은 내내 건강해 보였다. fail-closed라
  아무것도 안 깨졌고 그래서 드러나지도 않았다 — values 파일·Capsule과 같은 "에러 없이 안 읽히는"
  부류. 실질은 구멍이 아니라 **Phase 1a 증명의 RBAC 팔이 한 번도 행사된 적 없다**는 것이다
  (DoD가 "Forbidden **또는** 자격증명 부재"라 약한 쪽으로 통과 중이었다). 구조 가드는 subset이
  아니라 equality로 비교한다 — subset은 정규식이 아무것도 못 찾을 때도 통과해서, 감시 대상이
  모양을 바꾸는 바로 그 순간 조용해진다.
- Next: Phase 3② 롤백↔selfHeal 우선순위 · ③viewer 가시성. `docs/PROGRESS_LOG.md`가 예산
  초과(145줄) → `/tidy-docs` 필요.

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
