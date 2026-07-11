# NEXT_PLAN — platform-agent

최종 갱신: 2026-07-11

> **열린 작업만.** 완료 이력은 `COMPLETED_SUMMARY.md` / `PROGRESS_LOG.md`를 참조한다. **≤120줄** 유지.

## 다음 작업 리스트

- [ ] 세션 외 미커밋 워킹트리 변경 검토/정리 — 특히 `src/agents/models.py` 재수출 제거로 인한 `from src.agents.models import ServiceSpec` ImportError 복구 여부 결정
- [ ] AI Model Router 채팅 **live 데모** — MLX-LM(:8080) + proxy(:18081) + kind + 로컬 대시보드(`LOCAL_DEPLOY_API_URL`, `DASHBOARD_DATA_SOURCE=aws`)로 자연어 배포 → Deployments 추적 실증
- [ ] (deferred) Slack App 실 생성/토큰 설정 — 코드+하네스(`scripts/slack_live_approval.py`) ready, 실 workspace만 필요
- [ ] (deferred) 테크 아티클(LinkedIn / Medium) 리뷰 및 소셜 채널 배포

## 작업 규칙

- 멀티파일 변경 후 `make check` 실행, pass/fail 보고.
- 묶음 완료 시 `/checkpoint`로 PROGRESS_LOG append + STATUS 갱신.
- 요청 범위 밖 기능 추가 금지.
