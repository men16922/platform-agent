# PROGRESS_LOG — platform-agent

최종 갱신: 2026-07-26

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs` 로 압축.
> 이전 이력: `docs/archive/progress-2026-07.md`

---

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

## 2026-07-26 — 삭제는 cascade한다: 계약이 삭제 의미를 말하게 (gate 1267→1271)

- Status: 직전 라이브의 고아 워크로드를 닫았다. 진짜 문제는 파이널라이저 부재가 아니라
  **계약이 삭제 의미를 말한 적이 없다**는 것 — Flux는 uninstall, ArgoCD는 고아라
  "구독 해지" 하나의 의도가 엔진마다 반대 결과를 낸다.
- Changed(`e1ea15f`): `DeliveryAdapter.render`에 "Deletion must cascade" 명시 ·
  argocd 렌더러가 `resources-finalizer.argocd.argoproj.io` 부착 · prune≠삭제정책 가드 ·
  flux uninstall 비활성화 금지 가드(부재 단언).
- Verified: `make check` **1271**(+4). **라이브 A/B(kind, $0)**: 같은 차트 Application
  2개를 파이널라이저만 다르게 두고 둘 다 삭제 → 있는 쪽은 사라지고 없는 쪽
  (`podinfo-orphan`)은 소유자 없이 Running. 증거 `docs/evidence/phase2-deletion-cascade.log`.
- Blockers: 없음. 정리 완료(probe ns 삭제), rollouts-demo·테넌트 정책 5개 무손상.
- 품질 메모: 선언한 차트(loki 7.1.0)로 실증하려다 **어댑터가 helm values를 못 싣는다**는
  갭이 드러났다 — `Please define loki.storage.bucketNames.chunks`로 템플릿 자체가 실패한다.
  파이널라이저는 차트와 무관한 엔진 동작이라 기본값으로 설치되는 차트로 통제 실험을 했고,
  **대체 차트를 썼다는 사실을 증거에 명시**했다. 또 이 수정이 덮지 않는 것도 적었다:
  cascade는 엔진이 관리하는 것까지라 StatefulSet PVC는 남는다("깨끗이 제거됨" 아님).
  **[정정 2026-07-26]** 이 마지막 문장은 틀렸다 — 다음 증분에서 실측하니 PVC까지 사라졌고,
  원인은 차트가 `whenDeleted: Delete`로 쿠버네티스 기본값을 뒤집은 것이었다. 위 항목 참조.
- Next: 어댑터 helm values seam · faked managed 디스크립터(`applicable=false`) · DR 재구축.

## 2026-07-26 — capability scope 축: 클러스터 싱글턴 렌더 거부 (gate 1251→1267)

- Status: 직전 라이브가 낸 사고(컨트롤러 2개가 같은 Rollout을 조정)를 닫았다. STATUS에
  "렌더 결과를 그대로 적용하지 말 것"으로 남겨뒀던 리스크가 해소됐다.
- Changed(`bb7a819`): 카탈로그에 capability별 `scope: cluster|namespace` ·
  `reject_cluster_singletons`를 **delivery 계약**에 배치(엔진마다 복제하면 세 번째 엔진이
  빠뜨린다) · 수집기가 공유 설치물을 테넌트 drift로 세지 않음(`applicable=False`, 안 보이면
  MISSING 아니라 UNKNOWN) · 대시보드 sync 칸에 "shared" 표기 · 미선언은 cluster로 fail-safe.
- Verified: `make check` **1267**(+16) · `tsc --noEmit` 클린. **라이브**: 사고를 낸 그
  매니페스트를 argocd·flux 둘 다 거부하고 namespace scope 2개(logging/tracing)는 정상 렌더 ·
  재푸시 결과가 4행 전부 missing에서 (2 진짜 missing / 2 shared-unknown)으로 정직해짐.
  증거 `docs/evidence/phase2-capability-scope.log`.
- Blockers: 없음.
- 품질 메모: **내 첫 구현이 게이트를 27 errors로 깨뜨렸다.** scope 누락을
  `validate_registry`의 problem으로 올렸는데, 로더가 fail-closed라 이 필드가 생기기 전에
  쓰인 최소 카탈로그가 전부 로드 자체를 거부했다 — 문서 공백을 "플랫폼 뷰가 아예 안 뜸"으로
  바꾼 셈이고, 막으려던 실패보다 나쁘다. 게다가 **가드는 이미 다른 곳에 있었다**(fail-safe
  기본값 cluster → 어댑터가 거부). 부재는 리포팅으로 내리고 **오값만** 거부한다 —
  부재는 공백이지만 오값은 주장이고, 주장은 믿긴다.
- Next: ArgoCD Application 삭제 시 워크로드 고아(파이널라이저) · faked managed 디스크립터
  (`applicable=false`) · DR 재구축 확인.
