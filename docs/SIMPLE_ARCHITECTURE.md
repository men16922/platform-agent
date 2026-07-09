# Platform Agent — Simple Architecture

> 자연어 명령 하나 + ServiceSpec YAML 하나 = 멀티클라우드 K8s 배포

---

## 흐름

```
"orders-api를 v1.4.2로 4개 환경에 배포해줘"

    ↓ 자연어 명령

┌─────────────────────────────────┐
│         AI Agent (Kiro)         │
│   자연어 파싱 → 배포 실행 위임    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│     ServiceSpec (YAML 1개)      │
│  name, image, version, replicas │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│      공통 배포 파이프라인         │
│  Build → Push → Deploy → Validate│
└──┬───────┬───────┬───────┬──────┘
   │       │       │       │
   ▼       ▼       ▼       ▼
 ┌───┐  ┌───┐  ┌───┐  ┌────────┐
 │EKS│  │GKE│  │AKS│  │On-Prem │
 │   │  │   │  │   │  │  K8s   │
 └───┘  └───┘  └───┘  └────────┘
```

---

## 입력

```yaml
# orders-api.yaml
name: orders-api
image: orders-api
version: v1.4.2
replicas: 3
ports: [8080]
health: /healthz
```

---

## Provider별 매핑

| 단계 | AWS | GCP | Azure | On-Prem |
|------|-----|-----|-------|---------|
| Build | CodeBuild | Cloud Build | ACR Tasks | docker build |
| Push | ECR | Artifact Registry | ACR | Private Registry |
| Deploy | kubectl → EKS | kubectl → GKE | kubectl → AKS | kubectl → K8s |
| Validate | Health check | Health check | Health check | Health check |

---

## 핵심

- **YAML은 1개.** Provider만 바꾸면 어디든 배포.
- **AI Agent가 실행.** 사람은 자연어로 요청만.
- **동일 파이프라인.** Build→Push→Deploy→Validate 구조는 클라우드 무관.
