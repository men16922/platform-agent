# Plan — 4a 착수 조건: `write_relabel_configs` 허용목록 (승인 대기)

작성: 2026-08-15 · 상태: **제안 — 승인 전이며 아무것도 프로비저닝하지 않았다**

> **D48이 지정한 4a의 첫 산출물이다.** 워크스페이스 생성이 아니라 이것이 먼저다:
> 허용목록 없이 remote_write를 붙이면 **≥$180/월**이고 그건 4b(≈$185)와 같아져
> **4a를 고른 이유가 사라진다**(→ `docs/plans/2026-08-08-phase4-scope-and-cost.md` §4 정정 박스,
> 근거 `docs/evidence/4a-cost-assumed-a-hundredth-of-the-cluster.log`).

---

## 1. 허용목록이 섬겨야 할 소비자 — 재서 확인했다

발명을 피하려면 *"무엇이 이 데이터를 읽는가"*가 먼저다. 전수로 물었다:

    $ git grep -rln "promql|/api/v1/query|prometheus_api" -- src platform infra
    (platform-agent에 PromQL로 되읽는 경로 **없음**)

**platform-agent는 AMP를 되읽지 않는다.** `observability` capability는 GitOps 렌더용으로
백엔드를 **선언**할 뿐이다(`platform/catalog.yaml:50`). 따라서 허용목록이 섬길 대상은 둘뿐:

1. **Day-2 루프를 여는 알람 룰** — `values/kube-prometheus-stack.yaml:66`
   `increase(kube_pod_container_status_restarts_total{namespace="default"}[5m]) > 2`
2. **4a의 DoD** — *"로컬에서 remote_write 성공 → read model이 sync 축을 정직하게 n/a로 표기"*
   (`2026-08-08-phase4-scope-and-cost.md` §3). **파이프가 살아 있음을 보일 수단**이 필요하다.

⇒ **4a는 관측 커버리지를 증명하는 단계가 아니라 어댑터 코드 경로를 닫는 단계다.**
그래서 목록이 작아도 DoD가 상한다.

## 2. 제안 — 메트릭 4종

| | 메트릭 | 왜 | 실측 시계열 |
|---|---|---|---|
| **R1** | `kube_pod_container_status_restarts_total` | **데모 알람 룰이 쓰는 바로 그것.** 없으면 루프가 안 열린다 | **50** |
| **R2** | `up` | remote_write **파이프가 살아 있음**을 AMP 쪽에서 확인하는 최소 신호. DoD의 "성공"을 눈으로 볼 수단 | **22** |
| **R3** | `kube_pod_status_phase` | 재시작 알람이 떴을 때 **파드가 어떤 상태인지** — 알람의 맥락 | **220** |
| **R4** | `kube_deployment_status_replicas_unavailable` | 재시작이 **가용성에 닿았는지** — 조치 판단의 근거 | **16** |
| | **합계** | | **308** |

**전체 52,360 중 308 = 0.59%.**

⚠️ **R3·R4는 "있으면 좋다"가 아니라 판단 근거다.** R1만 넣으면 AMP에 **숫자 하나**만
쌓이고, 그걸로는 "조치 후 나아졌나"를 그쪽에서 물을 수 없다. 다만 **더 넣지 않았다** —
§4의 배제 목록이 그 선이다.

## 3. 비용 — 승인액 대비

정가 **$0.90/1천만 샘플**(첫 20억 구간, `aws.amazon.com/prometheus/pricing` 2026-08-15 · AWS
자체 예시 892.8M→$80.93로 교차 확인). 월 샘플 = 시계열 × (2,592,000 ÷ 간격초).

| remote_write 간격 | 월 샘플 | 월 비용 | 승인액 $5 대비 |
|---|---|---|---|
| **60초 (권장)** | **13.3 M** | **≈$1.20** | **여유 4.2배** |
| 30초 (차트 기본값 그대로) | 26.6 M | ≈$2.39 | 여유 2.1배 |
| *(참고)* 필터 없음 | 5,131 M | **≥$180** | **초과 36배** |

보관·쿼리는 랩 규모에서 **<$1**(0.03/GB·월, 쿼리 $0.10/10억 샘플).

⚠️ **프리티어(40M)에 기대지 않은 금액이다.** 계정이 `freetier` API에서 **"12 Month Free" 0건**
이라 첫 12개월 창을 지났다. 붙으면 13.3M은 통째로 무료지만 **그렇게 계획하지 않는다.**

⚠️ **20억 샘플 초과 요율은 미확인**이다(pricing 페이지에 표가 없다). 위 금액은 전부
첫 구간 안이라 **영향받지 않는다** — 필터 없는 경우만 그 구간을 넘는다.

## 4. 배제한 것과 그 대가 — 정직하게

| 배제 | 시계열 | 잃는 것 |
|---|---|---|
| `apiserver` 전부 | 21,038 (40%) | 컨트롤플레인 지연·에러율 대시보드 |
| `kubelet`/cAdvisor 전부 | 13,820 (26%) | **컨테이너 CPU/메모리 사용량** |
| `node-exporter` 전부 | 5,919 | 노드 수준 용량 |
| `kube-state-metrics` 나머지 | ~3,900 | 그 밖의 오브젝트 상태 |
| grafana·prometheus·alertmanager 자기 메트릭 | ~5,600 | 관측 스택 자체 관측 |

**대가는 "AMP에서 용량 분석을 못 한다"이다.** 4a의 DoD에 용량 분석은 없다.
그리고 **로컬 Prometheus는 전부 그대로 갖고 있다**(retention 12h) — 잃는 건 *AMP 쪽에서*의
조회일 뿐이다.

⚠️ **job 단위로 넓히면 왜 안 되는지는 실측이 답했다**: kube-state-metrics **전부**만 통과시켜도
4,188 시계열 → **$16.28/월**(승인액의 3배). **허용목록은 메트릭 단위여야 한다.**

## 5. 적용할 설정 (승인 시)

`infra/onprem/addons/values/kube-prometheus-stack.yaml`의 `prometheus.prometheusSpec`에:

```yaml
    remoteWrite:
      - url: https://aps-workspaces.<region>.amazonaws.com/workspaces/<ws-id>/api/v1/remote_write
        sigv4:
          region: <region>
        # 기본 15~30초가 아니라 60초로 — 간격이 곧 비용이다(§3).
        # 이 값과 아래 목록이 4a 비용을 지배하는 두 손잡이다.
        writeRelabelConfigs:
          - sourceLabels: [__name__]
            regex: 'kube_pod_container_status_restarts_total|kube_pod_status_phase|kube_deployment_status_replicas_unavailable|up'
            action: keep
```

⚠️ **`regex`는 앵커된다**(Prometheus가 `^(?:...)$`로 감싼다) — 접두사 매칭이 아니다.
⚠️ **간격은 `remoteWrite`가 아니라 스크랩이 정한다.** 60초를 원하면 해당 ServiceMonitor의
`interval`을 올리거나 전역 `scrapeInterval`을 조정해야 한다 — **적용 전 실측으로 재확인할 것**
(이 문서의 §3은 시계열 수 × 간격의 산수이고, 간격을 실제로 바꿨는지는 별개다).

## 6. 이 문서가 하지 않은 것

- **워크스페이스를 만들지 않았다.** 전 리전 0개를 확인만 했다(보유 자체는 무과금).
- **설정을 적용하지 않았다.** §5는 제안이다.
- **간격 변경을 실측하지 않았다.** 현재 유효 간격은 **26.4초**(52,438 ÷ 1,981)로 역산했을 뿐,
  60초로 바꾼 뒤의 샘플률은 **안 쟀다** — 바꾸면 재야 한다.
- **AMP 쪽에서 조회되는지 확인하지 않았다.** 그건 DoD이고 프로비저닝 이후다.

## 7. 승인받을 것

1. **메트릭 4종 목록**(§2) — 더/덜 넣을지
2. **remote_write 간격 60초**(§3) — $1.20 대 $2.39
3. **워크스페이스 리전** — 인바운드 전송은 무료라 비용 중립. 지연만 고려하면
   `ap-northeast-2`, 기존 AWS 자원과 묶으려면 `us-east-1`

승인되면 다음 순서: 워크스페이스 생성(무과금) → §5 적용 → remote_write 확인 →
`make spend-check`로 **이틀 뒤 실제 청구액 대조**(⚠️CE 지연 이틀 이상, Risk 4).
