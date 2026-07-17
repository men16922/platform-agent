# Plan — 대시보드 SSE 하드닝 + 회수가능 메모리 tier (NEXT_PLAN ⑨, 설계)

최종 갱신: 2026-07-17 · 상태: **✅ 승인됨(사용자 "전부 다") — 실행 대기** (큐 순서: NEXT_PLAN ★)

> cwc-workshops 후속 ⑨. 두 독립 트랙: (A) 배포 SSE 스트림 견고화, (B) `deploy_recorder`
> 트레이스를 회수가능 메모리 tier로 증류. 둘 다 **비파괴 증분** 설계이나 런타임 표면(스트림
> 프로토콜·실행 시작 경로)을 건드려 승인 후 구현한다.

## 현재 상태 (근거)

- SSE: `local_deploy_api.py:216-276` — `_sse(obj)`가 `data: {json}\n\n`만 방출. **없는 것**:
  SSE `id:` 필드(→ `Last-Event-ID` 재개·dedup 불가), 스트림 오픈 시 READY 센티넬, heartbeat,
  per-agent 귀속(단일 deploy 스트림). 이벤트 순서 tool_call→tool_result→done|error.
- 메모리: `deploy_recorder.py` — `_write_row`/`record_route_activity`가 **풀 트레이스**(`trace`
  JSON, `cost_metrics` 서브메트릭)를 DynamoDB/로컬 JSONL에 기록(`read_deploys`로 읽음). 과거 실행이
  **저장은 되나 다음 실행에 주입되지 않음**(수동 대시보드 조회만). distilled/시그니처-키드 tier 없음.

## (A) SSE 하드닝 — 제안

### A-1. 이벤트 ID + 재개 (프로토콜 증분, 낮은 리스크)
- **무엇**: 각 프레임에 단조 `id: <seq>` 부여(`_sse(obj, seq)`), 클라이언트 `Last-Event-ID` 헤더로
  재연결 시 서버가 그 이후만 재방출(또는 최소한 dedup 키 제공). 스트림 상태를 seq로.
- **리스크**: 낮음. `data:`만 보던 클라이언트는 `id:` 무시(하위호환). 재개는 스트림 버퍼 유지 필요 →
  1차는 **dedup만**(id 방출), 실제 backfill-on-reconnect는 2차.
- **권고**: 1차 = `id:` 방출 + 클라이언트 dedup. 서버측 replay 버퍼는 옵트인 후속.

### A-2. READY 센티넬 + 라이브 tail 먼저 (동작 증분, 낮은 리스크)
- **무엇**: 스트림 오픈 즉시 `{"type":"ready"}` 방출(연결 확립 신호) → 클라이언트가 backfill 이전에
  라이브 tail을 먼저 붙이고, 과거 이벤트는 그 뒤 backfill. 초기 렌더 공백 제거.
- **리스크**: 낮음(순수 추가 이벤트, 기존 소비자는 미지 type 무시). heartbeat(`:keepalive\n\n`)도 동반
  권장(프록시 idle 타임아웃 방지, 이미 `X-Accel-Buffering:no` 있음).
- **권고**: ready 센티넬 + 주기 heartbeat 코멘트. A-1과 함께.

### A-3. Thread→agent 귀속 (per-agent 탭) (동작 변경, 중간 리스크)
- **무엇**: 이벤트에 `agent`/`threadId` 필드 → 대시보드가 에이전트별 탭으로 분리. 멀티에이전트
  오케스트레이션(Orchestrator step별) 스트림에 유효.
- **리스크**: 중간. deploy 스트림은 현재 단일 에이전트라 즉시 실익 적음; Orchestrator 스트리밍이
  선행돼야 진짜 값. 대시보드 UI 변경 동반.
- **권고**: A-1/A-2 이후, Orchestrator 스트리밍이 생길 때. **지금은 필드만 예약**(옵셔널 `agent`).

## (B) 회수가능 메모리 tier — 제안

### B-1. 시그니처-키드 distilled 메모리 (신규 계층, 중간 리스크)
- **무엇**: `deploy_recorder` 트레이스 → 증류 레코드(시그니처 키 = {provider, service, 실패단계/증상}
  해시)로 축약 저장. 풀 트레이스와 별개의 경량 tier(`~/.platform-agent/memory.jsonl` + DynamoDB).
- **리스크**: 중간. 저장은 비파괴(신규 파일/GSI)이나 시그니처 스킴·PII/시크릿 스크럽 설계 필요.
- **권고**: 오프라인·결정론 증류 함수 + eval처럼 injectable. 실 기록 경로는 옵트인 env.

### B-2. 실행 시작 시 과거 인시던트 주입 (동작 변경, 중간 리스크)
- **무엇**: 새 실행 시작 시 현재 요청 시그니처로 매칭되는 과거 distilled 메모리를 조회→에이전트
  컨텍스트에 주입("이 서비스가 지난번 X단계에서 Y로 실패").
- **리스크**: 중간. 실행 경로/프롬프트에 개입 → 회귀 위험. 주입은 **읽기 힌트만**(결정 강제 안 함),
  Guardian/reconciliation 게이트와 상충 없게.
- **권고**: 옵트인 DI seam(`memory_provider`), 미주입 시 무변경. 힌트는 조언적(non-binding).

### B-3. 주기 consolidation (Dreaming식) (배치, 낮은 리스크)
- **무엇**: 주기적으로 distilled 메모리를 병합/승격(중복 시그니처 집계·신뢰도 갱신).
- **리스크**: 낮음(오프라인 배치, 런타임 무관).
- **권고**: 순수 함수 + 스케줄은 사용자(cron/loop). 마지막 순위.

## 권고 실행 순서 (승인 시)
1. **A-1 + A-2**(SSE id/dedup + READY/heartbeat) — 낮은 리스크·즉시 UX 실익, 비파괴.
2. **B-1**(distilled 메모리 저장, 오프라인·injectable) — 표면 없음, 회귀 0.
3. **B-2**(과거 주입, 옵트인 DI·조언적) — 실 값이나 실행경로 개입, 신중.
4. A-3(per-agent) / B-3(consolidation) — Orchestrator 스트리밍·스케줄 선행 후.

## 참고 (범위 밖/안티)
- 정적 무조건 컨텍스트 주입 금지(회귀). 메모리는 시그니처 매칭 시에만·조언적.
- SSE replay 버퍼는 메모리 상한 필요(무한 버퍼 금지).
- 시크릿/PII를 distilled 메모리에 저장 금지(스크럽 게이트 선행).
