# Reference — enterprise-ai-governance-dashboard

> 외부 레포 분석 노트. **차용 후보 패턴**만 추린다. 우리 코드에 이식하기 전 검토용. 되돌리기 어려운 결정은 `DECISIONS.md`.

- **출처:** https://github.com/ldu1225/enterprise-ai-governance-dashboard
- **검토일:** 2026-07-13
- **레포 상태:** Python 100%, 최근 push 2026-07-10, LGES 브랜딩. 파일: `src/backend_server.py`(2067줄, `http.server` 단일 파일) + `src/index.html`(Vanilla JS/Chart.js) + `config.yaml` + `terraform/{main,variables}.tf` + `Dockerfile`.

## 무엇인가

GCP 기반 **AI 거버넌스 / FinOps 관제 대시보드**. Vertex AI/Gemini Enterprise·Model Armor·Billing·Cloud Audit·NotebookLM 로그를 **BigQuery 6개 데이터셋**으로 수집하고, 백엔드가 표준 SQL로 직접 쿼리해 비용·보안차단·사용자활동을 통합 관제. Gemini 3.5 Flash 챗봇으로 자연어 분석을 붙임. Cloud Run + 최소권한 SA로 배포.

우리 `platform-agent`(멀티클라우드 Day1/Day2 배포·장애복구 에이전트)와 **도메인은 다르다**(저쪽=GCP 사용량/거버넌스 관측). 아키텍처 품질은 우리가 우위(단일 2000줄 `http.server`·SQL 하드코딩·무테스트 vs. 우리 Python 에이전트 + Next.js + `make check` 600 passed). 아래 3패턴만 이식 가치.

## 차용 후보 패턴

### P1 — 2-Pass Fact-Based NL→SQL 챗봇 (가장 가치 높음)
`backend_server.py:1723` `handle_conversational_analytics_chat`.

- **1st pass (생성):** 시스템 프롬프트에 6개 테이블 스키마 + "이 질문엔 반드시 이 exemplar SQL을 써라"는 정답 SQL 예시를 박고, Gemini `response_schema`(Pydantic `sql`/`answerComment`/`suggestedQuestions`)로 **구조화 출력 강제** → SQL 생성. (`backend_server.py:1823`)
- **2nd pass (팩트 요약):** **실제 BigQuery 실행 결과 rows를 다시 LLM에 먹여** "generic boilerplate 금지, 결과의 실제 숫자/이름만 언급" 프롬프트로 요약 생성 → 환각 억제. (`backend_server.py:1988`)
- **Self-healing 루프:** SQL 실행 실패 시 `에러 메시지 + 실패 SQL + 스키마`를 LLM에 되먹여 **최대 3회 자동 교정** 후 재실행. (`backend_server.py:1882`)
- **부가 하드닝:** `TIMESTAMP_SUB(..., INTERVAL n MONTH)` → `INTERVAL n*30 DAY` 정규식 치환, ```` ```sql ```` 펜스 제거, 숫자형 컬럼(cost/count/token…) 휴리스틱 감지 시에만 차트 렌더.

**우리 접점:** On-Prem NL 에이전트(`mlx_qwen_tool_proxy`의 7B tool-call 파싱, `local_deployer`)와 문제의식 동일. **2nd-pass 결과-되먹임 요약**과 **에러-되먹임 self-heal**은 우리 대시보드 챗봇/에이전트 응답 품질에 이식 가치. (우리 tool-call 재시도 현황과 비교해 델타만 취사.)

### P2 — LLM 기반 동적 SKU 그룹핑
`backend_server.py:165` `llm_group_skus_via_gemini`. 가변적 GCP Billing SKU 문자열을 LLM으로 대표 모델명(Claude Sonnet 4.5 / Gemini 3.5 Flash …)으로 묶어 합산·정렬. 향후 **FinOps/비용 리포트** 붙일 때 참고.

### P3 — Terraform Cloud Run + 최소권한 SA
`terraform/main.tf`. 대시보드 전용 SA에 `bigquery.dataViewer` + `bigquery.jobUser` + `aiplatform.user`만 부여(least privilege), 컨피그는 런타임 env로 주입(소스/인프라 분리). 우리 가드레일(`Resource:"*"` 금지)과 정합하는 깔끔한 예시.

## 안티패턴 — 베끼지 말 것

- **아키텍처:** `http.server.SimpleHTTPRequestHandler` 단일 2000줄, 핸들러마다 SQL 하드코딩, 테스트/타입 부재.
- **LLM 생성 SQL 직접 실행:** SQL injection·비용폭탄 리스크. 이식 시 **read-only + 쿼리 화이트리스트/파라미터화** 필수.
- **GCP 종속:** BigQuery/Model Armor/Discovery Engine 결합도 높아 멀티클라우드 이식성 낮음. 패턴(2-pass, self-heal)만 추상화해 차용.

## 액션

- 현 우선순위(추적 IA 라이브 실증→커밋/머지)에는 무영향. **차후 대시보드 챗봇/FinOps 확장 시** P1을 우선 검토.
