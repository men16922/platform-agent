# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-26

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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

## 2026-07-26 — 어댑터 helm values seam + PSS/PVC 결함 2건 (gate 1271→1281)

- Status: 렌더러가 chart+version만 실어 선언한 차트 대부분이 템플릿조차 안 되던 갭 해소.
  라이브가 그 위에서 결함 2건을 더 드러냈고, **둘 다 초록 화면 뒤에 있었다**.
- Changed(`01d3c6d`): 카탈로그가 values 파일을 **가리킨다**(복사 금지 — Terraform과
  어댑터가 사본을 각자 가지면 조용히 갈라진다) · `Registry.values_for` ·
  argocd `helm.valuesObject`(문자열 아님)·flux `spec.values`에 같은 dict ·
  공유 values에 파드 레벨 seccompProfile · `enableStatefulSetAutoDeletePVC: false`.
- Verified: `make check` **1281**(+10). **라이브(kind, $0)**: acme-dev-logging이 PSS
  restricted + Capsule 쿼터 + NetworkPolicy 아래에서 Synced/Healthy(2/2 Running, PVC
  Bound) — Phase 2 첫 진짜 테넌트 스코프 애드온 설치. 수집기 관통(logging=synced/healthy)
  확인 후 정리. 증거 `docs/evidence/phase2-values-seam.log`.
- Blockers: 없음.
- 품질 메모: (1) **PSS restricted 테넌트 네임스페이스가 우리 애드온을 거부**했다. Argo는
  Synced/Progressing인데 파드 0개, 진짜 이유는 StatefulSet 이벤트 세 단계 아래
  (seccompProfile 미설정). Terraform이 쓰는 `monitoring`엔 PSS 라벨이 없어 지금까지
  안 보였다 — D23이 경고한 그 상황이 실제로 일어났다. 추론 대신 렌더된 파드 스펙을
  테넌트 네임스페이스에 **server dry-run**해서 API 서버에 물었고, tempo에서 키 함정도
  잡혔다(최상위 `securityContext`=파드, `tempo.securityContext`=컨테이너 — loki 철자를
  쓰면 Helm이 조용히 무시한다. **values 파일은 에러가 아니라 안 읽히는 방식으로 실패한다**).
  (2) **직전 커밋에서 내가 쓴 주의사항이 틀렸다.** "StatefulSet PVC는 cascade에서 남는다"고
  단정했는데 실제로는 PVC까지 사라졌다. 원인은 Argo가 아니라 차트가 `whenDeleted: Delete`로
  쿠버네티스 기본값(Retain)을 뒤집은 것 — 구독 해지가 테넌트 로그를 같은 초에 파괴한다.
  **진실이 내 주의사항보다 위험했다.**
- Next: faked managed 디스크립터(`applicable=false`) · DR 재구축 확인.
