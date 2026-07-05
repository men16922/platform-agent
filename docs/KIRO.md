# Kiro CLI — 다른 코딩 에이전트와의 차별화 포인트

Kiro CLI는 AWS에서 만든 AI 코딩 에이전트 CLI 도구입니다. Claude Code, Cursor, GitHub Copilot 등 다른 코딩 에이전트와 비교하여 Kiro CLI만의 차별화된 기능을 정리합니다.

---

## 1. Steering Files (프로젝트 규칙의 영구 적용)

```
.kiro/steering/
├── coding-standards.md
├── team-conventions.md
└── architecture-rules.md
```

- `.kiro/steering/` 디렉토리에 마크다운 파일을 배치하면, **매 세션마다 자동으로 에이전트 컨텍스트에 로드**
- **워크스페이스(로컬)** + **글로벌(~/.kiro/steering/)** 두 레벨로 관리
- `inclusion: always | fileMatch | manual` 프론트매터로 조건부 로드 제어
- 에이전트 프롬프트(정체성)와 분리된 **프로젝트 규칙 레이어** — 팀 컨벤션, 코딩 스탠다드 등을 버전 관리 가능

> 다른 에이전트와의 차이: Claude Code의 `CLAUDE.md`와 유사하지만, Kiro는 글로벌/워크스페이스 2계층 + 조건부 포함(`fileMatch`, `manual`) 등 더 세분화된 제어를 제공

---

## 2. Agent Configuration (에이전트 전문화 시스템)

```json
{
  "name": "rust-dev",
  "prompt": "You are an expert Rust developer...",
  "tools": ["read", "write", "shell", "code"],
  "allowedTools": ["read", "grep"],
  "toolsSettings": { "shell": { "allowedCommands": ["cargo *"] } },
  "resources": ["file://src/**/*.rs"],
  "hooks": { "agentSpawn": [{ "command": "cargo --version" }] },
  "mcpServers": { "git": { "command": "mcp-server-git" } },
  "keyboardShortcut": "ctrl+shift+r"
}
```

- `.kiro/agents/` 디렉토리에 JSON으로 **목적별 에이전트를 정의**
- 도구 제한(`tools`), 자동 승인(`allowedTools`), 경로/명령어 제한(`toolsSettings`)으로 **세분화된 보안 제어**
- 키보드 단축키로 에이전트 간 즉시 전환
- 하나의 프로젝트에서 `rust-dev`, `code-reviewer`, `aws-ops` 등 **역할별 에이전트**를 운용

> 다른 에이전트와의 차이: 대부분의 코딩 에이전트는 단일 페르소나로 동작. Kiro는 프로젝트 내에 복수의 전문화된 에이전트를 정의하고 전환 가능

---

## 3. Hooks System (라이프사이클 이벤트 기반 자동화)

| 트리거 | 시점 | 활용 예 |
|--------|------|---------|
| `agentSpawn` | 에이전트 초기화 시 | `git status`, 환경 정보 수집 |
| `userPromptSubmit` | 사용자 메시지 제출 시 | 타임스탬프, 추가 컨텍스트 주입 |
| `preToolUse` | 도구 실행 전 | 보안 검증, 위험 명령 차단 (exit 2) |
| `postToolUse` | 도구 실행 후 | 로깅, 포맷팅 검증 |
| `stop` | 응답 완료 시 | 코드 포맷팅, 테스트 자동 실행 |

- 쉘 스크립트로 동작하며, **JSON을 stdin으로 수신**하고 exit code로 제어
- `preToolUse`에서 exit 2를 반환하면 **도구 실행을 차단** 가능 (보안 게이트)
- `matcher` 패턴으로 특정 도구에만 훅 적용

> 다른 에이전트와의 차이: 대부분의 코딩 에이전트는 도구 실행 전후에 커스텀 로직을 삽입할 방법이 없음. Kiro는 프로그래밍 가능한 이벤트 시스템 제공

---

## 4. Planning Agent (Spec-Driven Development)

```
> /plan Build a REST API for user authentication

Plan > [구조화된 질문] → [코드베이스 분석] → [구현 계획 생성] → [실행 에이전트로 핸드오프]
```

- `Shift+Tab` 또는 `/plan`으로 **전용 계획 에이전트**로 전환
- 구조화된 질문으로 요구사항 수집 → 코드베이스 분석 → 태스크 분해
- 계획 에이전트는 **읽기 전용** (파일 수정 불가) — 계획과 실행의 명확한 분리
- 승인 후 실행 에이전트로 자동 핸드오프

> 다른 에이전트와의 차이: Claude Code 등은 계획과 실행이 혼재. Kiro는 계획 단계를 별도 에이전트로 분리하여 "먼저 합의, 그 다음 구현" 워크플로우를 구조적으로 지원

---

## 5. Sub-Agent Pipeline (다중 에이전트 DAG 오케스트레이션)

```json
{
  "task": "Audit the authentication module",
  "stages": [
    {"name": "security-scan", "role": "security-agent", "prompt_template": "Scan vulnerabilities in {task}"},
    {"name": "perf-analysis", "role": "perf-agent", "prompt_template": "Analyze performance of {task}"},
    {"name": "report", "role": "report-agent", "prompt_template": "Compile findings", "depends_on": ["security-scan", "perf-analysis"]}
  ]
}
```

- **DAG 기반 병렬/순차 파이프라인** — 의존성 기반으로 스테이지 자동 실행
- 각 스테이지는 독립 세션으로 실행, `Ctrl+G`로 실시간 모니터링
- Fail-fast 시맨틱: 하나가 실패하면 나머지 자동 취소
- Fan-out / Fan-in 패턴 지원

> 다른 에이전트와의 차이: 대부분의 코딩 에이전트는 단일 스레드로 동작. Kiro는 복수 전문 에이전트를 병렬로 실행하는 오케스트레이션 기능 내장

---

## 6. Goal-Driven Autonomous Loop (`/goal`)

```
/goal fix all failing tests in the auth module --max 15
```

- 목표를 설정하면 에이전트가 **자율적으로 반복 시도** (최대 50 iteration)
- 성공 기준을 스스로 검증하고, 다른 전략으로 재시도
- 지수 백오프로 실패 처리, 3회 연속 실패 시 자동 정지
- `/goal clear`로 언제든 중단 가능

> 다른 에이전트와의 차이: Claude Code의 "agentic" 모드와 유사하지만, 명시적인 iteration 제한과 실패 핸들링, 진행 상황 표시가 체계적

---

## 7. Knowledge Base (영구 시맨틱 검색)

```bash
/knowledge add project-docs docs/
# 이후 세션에서:
"프로젝트 인증 플로우에 대해 알려줘"  # → 시맨틱 검색으로 관련 문서 자동 조회
```

- **세션 간 영구 저장** — 한번 인덱싱하면 다음 세션에서도 검색 가능
- Fast(BM25 키워드) / Best(MiniLM 시맨틱) 두 가지 인덱스 타입
- **에이전트별 격리** — 각 에이전트가 독립된 지식 베이스 보유
- 에이전트 설정의 `resources`로 자동 동기화 가능

> 다른 에이전트와의 차이: 대부분의 에이전트는 현재 세션 컨텍스트에만 의존. Kiro는 로컬 임베딩 기반 영구 지식 저장소를 제공

---

## 8. MCP (Model Context Protocol) 네이티브 통합

```json
{
  "mcpServers": {
    "github": { "command": "mcp-server-github", "args": ["--stdio"] },
    "slack": { "url": "https://mcp.slack.com/mcp", "forceAuth": true },
    "jira": { "type": "registry", "oauth": { "oauthScopes": ["read:jira-work"] } }
  }
}
```

- **Stdio(로컬), HTTP(리모트), Registry(중앙 관리)** 세 가지 MCP 서버 유형 지원
- OAuth 인증, 커스텀 헤더, 도구별 비활성화 등 세밀한 제어
- **Tool Search**: MCP 도구가 많을 때 BM25로 온디맨드 검색 → 컨텍스트 윈도우 절약
- 에이전트별로 다른 MCP 서버 조합 설정 가능

> 다른 에이전트와의 차이: MCP 지원은 Claude Code도 하지만, Kiro는 레지스트리 서버, OAuth 강제, 도구별 비활성화, Tool Search 등 엔터프라이즈급 MCP 관리 기능 제공

---

## 9. ACP (Agent Client Protocol) 지원

```bash
kiro-cli acp  # JSON-RPC over stdio로 프로그래밍적 통합
```

- **ACP v2025-01-01** 준수 — 표준화된 에이전트 통신 프로토콜
- TUI, 커스텀 클라이언트, 다른 도구에서 Kiro를 백엔드 에이전트로 활용 가능
- 세션 관리, 스트리밍, MCP 서버 주입 등 완전한 프로토콜 지원

> 다른 에이전트와의 차이: 대부분의 코딩 에이전트는 폐쇄적 인터페이스. Kiro는 개방형 프로토콜로 외부 통합 가능

---

## 10. Rich TUI (터미널 UI 경험)

| 기능 | 설명 |
|------|------|
| `/theme` | 다크/라이트/커스텀 테마 |
| `Ctrl+G` | Sub-agent 실시간 모니터 |
| `Ctrl+X` | Activity Tray (태스크 진행률) |
| `Ctrl+R` | 역방향 히스토리 검색 |
| Paste Chips | 10줄 이상 붙여넣기 시 자동 접기 |
| `/spawn` | 병렬 에이전트 세션 실행 |
| `/transcript` | 전체 대화를 $PAGER로 열기 |
| `/stats` | 요청 ID, 레이턴시, 토큰 사용량 디버깅 |

---

## 요약 비교표

| 기능 | Kiro CLI | Claude Code | Cursor | GitHub Copilot |
|------|----------|-------------|--------|----------------|
| Steering Files (프로젝트 규칙) | ✅ 2계층+조건부 | ✅ CLAUDE.md | ✅ .cursorrules | ❌ |
| 복수 에이전트 정의/전환 | ✅ | ❌ | ❌ | ❌ |
| 도구 라이프사이클 Hooks | ✅ 5종 트리거 | ❌ | ❌ | ❌ |
| 전용 Planning Agent | ✅ 읽기전용 분리 | ❌ | ❌ | ❌ |
| Multi-Agent DAG Pipeline | ✅ 병렬+의존성 | ❌ | ❌ | ❌ |
| 자율 Goal Loop | ✅ | ✅ (유사) | ❌ | ❌ |
| 영구 Knowledge Base | ✅ 시맨틱+BM25 | ❌ | ❌ | ❌ |
| MCP 네이티브 | ✅ Registry+OAuth | ✅ | ✅ | ❌ |
| ACP 프로토콜 | ✅ | ❌ | ❌ | ❌ |
| AWS 도구 내장 (`use_aws`) | ✅ | ❌ | ❌ | ❌ |

---

## 결론

Kiro CLI의 핵심 강점은 **"구조화된 에이전트 개발 환경"**입니다:

1. **Spec-Driven**: Planning Agent로 먼저 합의 → 그 다음 구현
2. **Multi-Agent**: 역할별 전문 에이전트 정의 + DAG 파이프라인 오케스트레이션
3. **Programmable**: Hooks로 도구 실행 전후에 커스텀 로직 삽입
4. **Persistent**: Knowledge Base로 세션을 넘어선 지식 축적
5. **Enterprise-Ready**: 세분화된 도구 권한, MCP 레지스트리, ACP 통합

단순히 "코드를 생성하는 AI"를 넘어, **재현 가능하고 제어 가능한 AI 개발 워크플로우**를 구축할 수 있는 플랫폼입니다.
