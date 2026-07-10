# DASHBOARD_DESIGN.md — Platform Agent Dashboard

## 목적

멀티클라우드(AWS/GCP/Azure/On-Prem) Operations 대시보드.
AI Agent가 자율적으로 배포/장애복구를 수행하는 것을 **시각적으로 증명**하기 위한 포트폴리오 UI.

---

## 대상 사용자

- LinkedIn / dev.to 방문자 (스크린샷/데모 영상으로 첫인상)
- 채용 담당자 / CTO (기술 역량 빠르게 파악)
- 본인 (배포/인시던트 현황 한눈에)

---

## 디자인 레퍼런스

| 서비스 | 참고할 점 | URL |
|--------|----------|-----|
| **Datadog** | 다크 배경 + 보라/녹색 accent, 메트릭 카드 레이아웃, 타임라인 | app.datadoghq.com |
| **Grafana** | 완전 다크 + 네온 차트 색상, 패널 그리드, 알림 배너 | grafana.com |
| **AWS CloudWatch** | 위젯 기반 대시보드, 알람 상태 색상 체계 (OK/ALARM/INSUFFICIENT) | console.aws.amazon.com/cloudwatch |
| **GCP Monitoring** | 밝은 톤 + Material 카드, 시계열 차트, 인시던트 타임라인 | console.cloud.google.com/monitoring |
| **Azure Monitor** | 타일 그리드 + 블루 그라디언트, 리소스 헬스 맵 | portal.azure.com |
| **Linear** | 미니멀 다크 + 보라 accent, 깔끔한 타이포, 애니메이션 | linear.app |
| **Vercel Dashboard** | 검정 배경 + 흰 텍스트, 배포 상태 타임라인, 심플 | vercel.com/dashboard |

---

## 디자인 방향 (결정 필요)

### Option A: Datadog/Grafana 스타일 (모니터링 중심)
- 완전 다크 배경 (#0b0e11)
- 네온 계열 accent (보라 #7c3aed, 녹색 #10b981, 주황 #f59e0b)
- 그래프/차트 중심 레이아웃
- 프로 모니터링 도구 느낌
- **장점:** DevOps/SRE 역량 어필에 적합
- **단점:** 차트 라이브러리 필요 (recharts 등)

### Option B: Linear/Vercel 스타일 (미니멀 모던)
- 깔끔한 다크 (#09090b)
- 모노톤 + 단일 accent (보라 or 블루)
- 타이포 중심, 여백 활용
- 부드러운 hover/transition 애니메이션
- **장점:** 세련된 느낌, 구현 가볍
- **단점:** 데이터 밀도 낮음

### Option C: 클라우드 콘솔 하이브리드
- 사이드바: 다크
- 메인 영역: 약간 밝은 다크 (#111827)
- 각 Provider 카드에 해당 클라우드 브랜드 색상 활용
- AWS 주황 / GCP 블루 / Azure 스카이 / On-Prem 그린
- **장점:** 멀티클라우드 아이덴티티 강조
- **단점:** 색상 밸런스 잡기 어려움

---

## 현재 구현 상태

```
dashboard/
├── src/app/
│   ├── page.tsx          # Overview (4-cloud health + stats + recent)
│   ├── incidents/        # 인시던트 타임라인
│   ├── deployments/      # 배포 이력 + pipeline DAG
│   └── agents/           # AI Agent 활동 로그
├── src/components/
│   ├── sidebar.tsx       # 네비게이션
│   ├── status-card.tsx   # 클라우드 상태 카드
│   └── incident-row.tsx  # 인시던트 행
└── src/lib/
    └── mock-data.ts      # DynamoDB/Firestore/Cosmos 시뮬레이션
```

- **Stack:** Next.js 16 + Tailwind 4 + TypeScript
- **현재 스타일:** 다크 배경 + 블루 accent (Linear 비슷)
- **데이터:** Mock (추후 실 Cloud SDK 연동)

---

## 추가 고려사항

### 차트/시각화
- [ ] recharts or Chart.js (메트릭 시계열)
- [ ] 인시던트 타임라인 시각화 (vertical timeline)
- [ ] 배포 파이프라인 DAG 시각화 (node-edge diagram)

### 인터랙션
- [ ] Provider별 필터
- [ ] Severity 필터 (P1/P2/P3)
- [ ] 실시간 polling (30s) or WebSocket
- [ ] P2 승인 버튼 (Slack 대체)

### 배포
- [ ] Vercel 배포 (무료 tier)
- [ ] 커스텀 도메인 연결
- [ ] Open Graph 메타 (LinkedIn 공유 시 프리뷰)

---

## 결정 대기

1. **스타일 방향:** Option A / B / C 중 선택
2. **차트 라이브러리:** recharts vs lightweight (없이 숫자만)
3. **브랜딩:** 로고/타이틀 커스텀 여부
