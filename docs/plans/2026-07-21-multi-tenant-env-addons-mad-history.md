# 기록 — 멀티테넌트/멀티-클라우드 플랫폼 설계: 의사결정 & MAD 히스토리

작성: 2026-07-21 · 대상 설계: `docs/plans/2026-07-21-multi-tenant-env-addons.md` (v5, 최종 등급 **S 93.5/100**)

> 이 파일은 설계가 **어떻게·왜** 지금 형태가 됐는지의 이력이다(설계 본문은 위 문서). 의사결정 로그 +
> Advocate/Critic MAD + 평가 파이프라인 + 버전 계보를 남긴다. 재론·회고·온보딩용.

---

## Part A. 의사결정 로그 (사용자와의 협업 결정, 시간순)

| # | 질문 | 결정 | 이유 |
|---|---|---|---|
| D1 | on-prem이 곧 단일 클러스터인가? | **아니다 — 여러 env에 동시 배포, env마다 add-on 상이** | kind·k3s 양기판 이미 실증. 사용자 통찰. |
| D2 | 다중 타깃을 뭘로 모델링? | **tenant / env** 2계층 | 사용자 제안. |
| D3 | tenant 경계 강도? | **하이브리드** (초기) → 이후 **격리 티어 정책**으로 진화(D9) | env=클러스터 경계(하드), tenant=묶는 라벨(소프트). |
| D4 | 대시보드 구조? | **단일 컨트롤플레인**(env 스위처로 스코프) | single pane of glass. |
| D5 | 1차 범위? | **설계 문서 먼저**(코드 착수 전) | 사용자 지정. |
| D6 | 이건 특정 클라우드 얘기인가? | **아니다 — 어느 클라우드든 동일**(cloud-agnostic) | env.substrate ∈ kind\|k3s\|eks\|gke\|aks. |
| D7 | Terraform과 ArgoCD 같이 쓰면 문제? | **아니다 — 상호보완 레이어**(TF=부트스트랩, GitOps=워크로드) | 최초 "문제"라 한 건 과장. **유일한 안티패턴 = 같은 리소스 이중소유**. |
| D8 | ArgoCD가 필수? | **아니다 — GitOps 엔진 pluggable**(ArgoCD/Flux 어댑터) | 다른 스택 검토(Flux·Crossplane·Capsule·vCluster) 후. |
| D9 | 멀티테넌시 격리를 하나로 고정? | **아니다 — per-tenant 정책**(soft\|vcluster\|dedicated) | "제약/요건에 따라 모두 가능"(사용자). Capsule/vCluster/전용클러스터. |
| D10 | on-prem CNCF만? 클라우드는? | **능력마다 {self-hosted \| managed} 백엔드**, substrate로 결정 | 클라우드는 관리형 제공(사용자). Config Sync/AMP/Azure Monitor 등. 비교표 추가. |
| D11 | 설계 확정 방식? | **rubric 수립 → MAD(Advocate/Critic) → Fable 5 최종 + 평가 에이전트 재리뷰** | 사용자 goal. 목표 등급 A+~S. |

**결과 아키텍처 (D1~D10 수렴):** *capability, implementation-pluggable* — 프로젝트의 cloud-neutral DNA를
플랫폼 레이어로 확장. `capability × {self-hosted|managed} × substrate` 3차원. SSOT = per-tenant git 레지스트리.

---

## Part B. 평가 파이프라인 & 등급 진행

### 채점 기준 (rubric) — 원칙-아키텍트 에이전트, 8기준·100점

| 가중 | 기준 |
|---|---|
| 16 | **Security & blast-radius containment** (최대 가중) |
| 15 | Multi-tenancy & isolation model |
| 14 | Architecture soundness & conceptual coherence |
| 13 | GitOps / delivery correctness |
| 12 | Observability & normalized read-model |
| 12 | Day-2 operations (upgrades / drift / promotion / DR) |
| 10 | Extensibility vs over-engineering (adapter contracts) |
| 8 | Phasing, feasibility & honesty-of-scope |

등급 밴드: **S ≥93** (top ~2% reference) · **A+ ≥87** · A ≥80 · B ≥68 · C ≥50.

### 진행 (등급 추이)

```
① MAD 디베이트 (Critic → Advocate개정 → Judge, 1라운드)      → A+ (92/100)
      · Critic 9건(critical 2), Advocate가 실제 코드에 근거해 v3로 심화
② 평가 에이전트 ground-truth 재리뷰                           → 코드 주장 2건 오류 적발
      · NormalizedIncident엔 namespace 필드 없음(FALSE)
      · resolve_action은 decision 단계지 실행 seam 아님(WRONG SEAM)
③ v4 정정 → Fable 5 최종 평가 (권위)                          → A+ (91/100)
      · 정정 4건 전부 코드로 검증됨(첫 오디트 통과). S-델타 3건 지목
④ S-델타 3건 소진(v5) → Fable 5 재평가                        → ⭐ S (93.5/100)
```

### MAD가 잡은 주요 결함 (라운드 0, Critic)
- **인가가 엉뚱한 대상 보호**: 특권 주체는 viewer가 아니라 remediation **에이전트** → 실행 자격증명을 tenant 스코프.
- **Flux 스텁으로는 어댑터 계약 검증 불가** → Phase 1에서 Flux 실제 구현.
- **NormalizedAddonStatus 단일 enum이 drift 신호 죽임** → sync·health **2축** + applicable.
- 그 외 major: read model=신규 서브시스템(추정 2배 과소)·TF↔ArgoCD 소유권 핸드오프·Day-2 all-env blast·레지스트리 god-object.

### 평가 에이전트 재리뷰의 결정타 (ground-truth)
MAD엔 코드 대조 패스가 없어 **advocate의 citation을 검증 없이 fact로 채점**했다. 재리뷰가 실제 파일
(`onprem_runner.py`·`aws/executor.py`·`models.py`)을 읽어 2건 오류를 잡음 → 이게 A+↔S를 가른 핵심.

### S를 만든 3건 (v5, 전부 Security 16축)
1. **실행 위치 = in-cluster 러너 결정**(Lambda-egress 아님) — 자격증명이 대상 클러스터를 안 벗어남.
2. **token broker = incident provenance 바인딩** — attested 승인 레코드 검증, 호출자 문자열 불신.
3. **read-model = push 모델** — in-cluster agent가 push, 허브 스포크 자격증명 0개.

### Fable 5가 인정한 2차 잔여 (v5에 명시)
agent→hub push 인증 · 승인레코드 one-time nonce(replay) · push heartbeat(staleness) · soft티어 agent의
per-cluster mint 집중(blast=1클러스터). hub=spoke 로컬 단계에선 inert, Phase 1a 진입 시 닫는다.

---

## Part C. 버전 계보

| 버전 | 계기 | 핵심 변화 | 등급 |
|---|---|---|---|
| v1 | 초안 | 레지스트리 + Terraform workspace-per-env | — |
| v2 | 평가 에이전트 1차 critique | 인가=blast radius · Flux 실제 · 2축 read model · TF↔Argo 핸드오프 · 레지스트리 파티션 · 비교표 정정 | — |
| v3 | MAD advocate | 자격증명 seam을 코드에 근거해 심화 · 티어별 cardinality · DR 런북 · 핸드오프 안전화 | A+ (92, MAD Judge) |
| v4 | 평가 에이전트 ground-truth 재리뷰 | 코드 주장 2건 정정(namespace·seam) · 토큰 custody · Phase 1a/1b 분할 | A+ (91, Fable 5) |
| v5 | Fable 5 S-델타 | in-cluster 러너 결정 · broker provenance · read push · 2차 잔여 명시 | **S (93.5, Fable 5)** |

---

## Part D. 메타 학습

- **MAD는 ground-truth 앵커가 없으면 "의도"를 "사실"처럼 채점한다.** 코드 대조 재리뷰가 없었다면 잘못된 seam
  citation이 A+로 통과했을 것 — 별도 평가 에이전트의 파일 오디트가 결정적.
- **좋은 설계 개정은 "결정 + 메커니즘 + 가짜를 잡는 DoD"** 세트다. S-델타 3건은 각각 대안의 실패모드를
  명시하고($0 falsifiable DoD 포함) 닫혔다 — "결정하라"가 아니라 "결정했다"가 S를 만든다.
- **경계를 없앴다고 주장하면, 새 거주자가 생긴다.** in-cluster agent로 자격증명을 가뒀더니 그 agent 자신의
  신원·replay·mint 집중이 새 표면 — 정직하게 명시하는 게 S가 implementer에게 지는 빚.
