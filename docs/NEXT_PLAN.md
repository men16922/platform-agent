# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-05

> **열린 작업만.** 완료 이력은 여기 두지 않는다(→ `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`). **≤120줄** 유지.

---

## P0 — 인프라 배포 + E2E 검증 [auto]

- [ ] `git init` + 초기 커밋 (overnight 루프 전제조건)
- [ ] `npx cdk deploy` 실행 (ap-northeast-2, q-user)
- [ ] 테스트 알람 트리거 → Operations 파이프라인 E2E 확인 (alarm → detect → analyze → decide → execute → Slack)
- [ ] 검증 결과를 STATUS.md baseline에 반영
- 근거: q-user 접근 확인됨. CDK synth 통과. 실 배포만 남음.

## P1 — 비-AWS provider 런타임 연결

- [ ] detector가 provider registry를 통해 GCP/Azure/on-prem signal adapter를 실제 dispatch하도록 연결
- [ ] executor가 비-AWS execution adapter로 capability→provider action 해석을 실제 호출하도록 연결
- [ ] 연결된 비-AWS 경로에 대한 단위 + (가능 시) 통합 테스트 추가
- 근거: 현재 비-AWS는 scaffold. production path는 AWS-native 한정.

## P2 — overnight-harness 루프 검증

- [ ] `MAX_ITER=1 make overnight-kiro-once` smoke test
- [ ] gate 통과 + commit 생성 확인
- [ ] 실패 시 diagnose + 수정
- 근거: 하네스 전환 완료. 첫 자동 루프 동작 확인 필요.

## P3 — runbook override 등록 자동화

- [ ] `incident-runbooks` override 등록을 위한 CLI 도구
- [ ] 등록 시 `validate_runbook` 사전 검증으로 malformed 차단

---

## 작업 규칙 (요약)

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
