# Multi-Cloud E2E 배포 테스트 결과

**실행일시:** 2026-07-06 22:17~22:35 KST  
**실행자:** Kiro CLI (kiro_default agent)  
**리소스 정리:** 완료 (GKE cluster deleted, AR repo deleted, Azure RG deleted)

---

## 요약

| Cloud | Registry | Cluster | 이미지 Push | Pod 배포 | 상태 |
|-------|----------|---------|------------|---------|------|
| **GCP** | Artifact Registry (asia-northeast3) | GKE Autopilot | ✅ | ✅ 1/1 Running | 정리됨 |
| **Azure** | ACR (koreacentral) | AKS (1 node, B2s_v2) | ✅ | ✅ 1/1 Running | 정리됨 |
| **AWS** | (이전) ECR/kind | (이전) CDK 97 resources | ✅ | ✅ | 정리됨 |

---

## GCP 테스트

### 환경

| 항목 | 값 |
|------|-----|
| Project | project-ec7809f7-0fb5-45d4-b6d |
| Region | asia-northeast3 |
| Account | yeongsigchoe7@gmail.com |
| API 활성화 | Artifact Registry, Cloud Build, Container (새로 활성화) |

### 수행

1. **Artifact Registry repo 생성**
   ```bash
   gcloud artifacts repositories create platform-agent --repository-format=docker --location=asia-northeast3
   ```

2. **Docker push (amd64)**
   ```
   asia-northeast3-docker.pkg.dev/project-ec7809f7-0fb5-45d4-b6d/platform-agent/e2e-test:v1.0.0
   digest: sha256:1d87d0596acc24be3e970c7af6c5eb8ab3e7c159dc7a7dd5d3b99cd9d17e5da1
   ```

3. **GKE Autopilot 클러스터 생성**
   ```
   NAME                    STATUS   NODES   VERSION
   platform-agent-cluster  RUNNING  3       v1.36.0-gke.3712000
   ```

4. **배포 검증**
   ```
   NAME       READY   UP-TO-DATE   AVAILABLE
   e2e-test   1/1     1            1
   ```

### 해결한 이슈

- **Container API 미활성화** → `gcloud services enable container.googleapis.com`
- **Platform mismatch** → macOS (ARM) 빌드 이미지를 GKE (AMD64)에서 pull 불가 → `docker buildx --platform linux/amd64` 재빌드

---

## Azure 테스트

### 환경

| 항목 | 값 |
|------|-----|
| Subscription | Azure subscription 1 |
| Account | men16922@gmail.com |
| Resource Group | platform-agent-rg |
| Location | koreacentral |

### 수행

1. **Resource Group 생성**
   ```bash
   az group create --name platform-agent-rg --location koreacentral
   ```

2. **ACR 생성 + Login**
   ```
   platformagente2e.azurecr.io (Basic SKU)
   ```

3. **Docker push (amd64)**
   ```
   platformagente2e.azurecr.io/e2e-test:v1.0.0
   digest: sha256:4ee9827d5bb0dd432caf5dc21f19f4bff35d59ccf223498ca03f02144f9c277e
   ```

4. **AKS 클러스터 생성**
   ```
   NAME                KUBERNETES   NODE VM         NODES   STATUS
   platform-agent-aks  1.35.5       Standard_B2s_v2 1       Succeeded
   ```

5. **배포 검증**
   ```
   NAME       READY   UP-TO-DATE   AVAILABLE
   e2e-test   1/1     1            1
   ```

### 해결한 이슈

- **ContainerRegistry/ContainerService NotRegistered** → `az provider register` 실행
- **Standard_B2s 미지원** → 구독에서 v1 B-series 비허용, `Standard_B2s_v2` 사용
- **Platform mismatch** → ARM 이미지 → `docker buildx --platform linux/amd64` 재빌드

---

## 리소스 정리

```bash
# GCP
gcloud container clusters delete platform-agent-cluster --region=asia-northeast3 --quiet --async
gcloud artifacts repositories delete platform-agent --location=asia-northeast3 --quiet

# Azure
az group delete --name platform-agent-rg --yes --no-wait
```

모든 리소스 삭제 확인됨.

---

## 검증된 멀티클라우드 경로

```
Local (macOS)
  → docker buildx --platform linux/amd64
  → Push to:
      GCP Artifact Registry (asia-northeast3-docker.pkg.dev/...)
      Azure ACR (platformagente2e.azurecr.io/...)
  → Deploy to:
      GKE Autopilot (kubectl apply → 1/1 Running)
      AKS (kubectl apply → 1/1 Running)
```

## 전체 클라우드 커버리지

| Provider | Registry | Cluster | AI Agent Framework | 상태 |
|----------|----------|---------|-------------------|------|
| AWS | ECR | EKS (CDK) | Strands (Bedrock Claude) | ✅ 코드+CDK+LLM 검증 |
| GCP | Artifact Registry | GKE Autopilot | ADK (Gemini) | ✅ 실배포 검증 |
| Azure | ACR | AKS | MS Agent Framework (GPT-4o) | ✅ 실배포 검증 |
| Local | localhost:5001 | kind | — | ✅ E2E 파이프라인 검증 |
