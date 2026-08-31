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

> 🔴 **정정 (2026-08-30, 측정) — 이 문단의 전건이 거짓이었다.** AMP 프리티어는 12개월
> 한정이 **아니라 `freeTierType: "Always Free"`**다(월 40M 샘플 · 10GB 보관 · 200B 쿼리).
> 켜고 물으니 계정에 AMP 행 셋이 전부 "Always Free"로 나타났다. ⇒ **아래 표의 금액은
> 전부 청구되지 않는다** — 설계 정상부하 15.8M은 한도의 **39.5%**다. **실제 청구액 $0.00**
> (2026-08 계량 798,331 샘플). ⚠️**허용목록이 불필요해진 게 아니라 절벽이 옮겨 앉았다**:
> 필터 없음 5,131M은 40M 한도를 **128배** 넘고 그때부터 정가가 그대로 붙는다.
> 권위는 **§10**과 `docs/evidence/amp-actual-bill-is-zero-and-the-free-tier-reason-was-inverted.log`.
> ⚠️ 이 문단은 **틀린 기록이 아니라 자기가 지목한 측정을 기다리던 예측**이었다(*"확정은
> AMP를 켠 뒤 첫 청구서가 답한다"*) — 지웠으면 그 규율이 지워진다. 그래서 남긴다.

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

---

## 8. 착수 실측 (2026-08-16) — 승인 후 진행분

**승인**: 메트릭 4종 · 간격 60초 · 리전 비용중립 (§7 셋 다).

**한 것**
- 워크스페이스 생성 — `ws-929b8da9-b0db-49f8-aadb-2ed1a70f699f` (**ap-northeast-2**,
  `Project=platform-agent` 태그). 보유 자체는 무과금이고 **아직 아무것도 흘리지 않는다.**
  리전은 레포 기본값(`AWS_REGION` 폴백)과 맞췄다.
- 시계열 실측 — 계획서의 **308과 정확히 일치**. 전체 샘플률 1,982/s → 월 5.14B(§3의 5.13B 확인).

**⚠️ §5의 "60초"를 그대로 쓰면 안 된다 — 더 좁은 손잡이가 있다.**
308 중 **287(93%)이 `kube-state-metrics` ServiceMonitor 하나**에서 온다(나머지 21은 각 job의
`up`). 그리고 현재 간격은 **전역 30초 · kubelet만 10초**다(실측). 따라서:

| 방식 | 월 샘플 | 비용 | 로컬 영향 |
|---|---|---|---|
| 전역 `scrapeInterval: 60s` | 13.3M | $1.20 | ⚠️**랩 전체 해상도 저하** |
| **`kube-state-metrics`만 60초** | **15.8M** | **$1.42** | 그 ServiceMonitor만 |
| 변경 없음(현행) | 28.2M | $2.54 | 없음 |

**중간 행을 택한다**: 승인 목표($1.20)에 $0.22 차이로 닿으면서 부작용이 훨씬 작다.
객체 상태 메트릭은 느리게 변하고, 데모 알람 룰은 `[5m]` 창이라 60초에서도 5샘플이다.
⇒ §5의 `scrapeInterval` 문구는 **전역이 아니라 `kube-state-metrics.prometheus.monitor.interval`**
로 읽어야 한다.

**⛔ 막힌 곳 — 계획서가 다루지 않은 것: sigv4 자격증명**

§5의 `sigv4:` 블록은 Prometheus 파드에 AWS 자격증명이 있다고 전제한다. **kind에는 IRSA가
없고**, `monitoring` 네임스페이스에 자격증명 시크릿도 없다(실측). 계정의 IAM 사용자 다섯 중
AMP 전용은 없고, 현재 신원 `q-user`는 **EC2 종료·워크스페이스 생성까지 되는 광범위한 키**다.

**그걸 클러스터에 넣지 않았다.** 이 레포의 원칙이 *자격증명이 경계*(D38·D39, Risk 3·10)인데,
월 $1.42짜리 메트릭 파이프를 위해 계정 전체 권한을 랩 클러스터에 두는 건 그 원칙을 정면으로
뒤집는다. 선택지는 셋이고 **전부 보안 결정이라 승인 사안**이다:

1. **전용 IAM 신원 + 해당 워크스페이스에 `aps:RemoteWrite`만** — blast radius 최소.
   대신 **장기 액세스 키가 하나 늘어난다**.
2. **호스트 측 sigv4 프록시** — 자격증명이 클러스터에 안 들어간다. 대신 프록시가 떠 있어야만
   동작해 **랩 데모 전용**이고, 실제 배포로 이어지지 않는다.
3. **보류** — 워크스페이스는 무과금이라 그대로 둬도 되고, 필요 없으면 지우면 된다.

⇒ **4a는 여기서 멈춰 있다.** DoD(*"로컬에서 remote_write 성공"*)는 이 결정 없이는 못 넘는다.

## 9. 착수 완료 (2026-08-17) — DoD 달성

§8의 막힌 곳을 **선택지 1(전용 IAM 신원)**으로 풀었다.

**자격증명** — IAM 사용자 `amp-remote-write-4a`. 인라인 정책이 **전부**다:

    Action:   aps:RemoteWrite        (하나)
    Resource: …workspace/ws-929b8da9-…  (하나)

키는 k8s Secret `monitoring/amp-remote-write`로만 존재한다 — **git에 없고 로컬 파일에도
안 썼다**. 차트는 값이 아니라 **Secret 이름을 참조**한다(`sigv4.accessKey.name`).
⚠️**장기 액세스 키가 하나 늘었다**는 대가는 그대로다. 4a를 접으면 **사용자·키·워크스페이스
셋 다 지울 것**.

**적용** — `helm upgrade monitoring … -f values` (릴리스 revision 5). 적용 전에
`helm template`으로 **두 키가 실제로 읽히는지 확인**했다(Risk 8: values는 에러가 아니라
*안 읽히는 방식*으로 실패한다):

    Prometheus CR      remoteWrite[0].url + sigv4.secretKey + writeRelabelConfigs  ✅
    ServiceMonitor     monitoring-kube-state-metrics  interval=60s                 ✅

그리고 `helm get values`로 **릴리스가 이 파일 밖의 값으로 설치되지 않았음**을 먼저 확인했다
(밖의 값이 있었다면 `-f`만으로 업그레이드하면 조용히 떨어진다).

**측정 — 파이프**

    samples_total    319       실제 전송
    samples_failed     0       ← sigv4 인증 성공
    samples_retried    0
    samples_dropped 69,076     ← 허용목록이 걸러낸 것 (99.5%)

**측정 — AMP 쪽 조회(진짜 DoD)**. SigV4로 서명해 워크스페이스에 직접 물었다:

    up                                           22   (§2의 22)
    kube_pod_container_status_restarts_total     50   (§2의 50)
    kube_pod_status_phase                       220   (§2의 220)
    kube_deployment_status_replicas_unavailable  16   (§2의 16)
                                          합계  308

**§2의 표와 네 칸 모두 일치한다.** 파이프가 살아 있고, 허용목록이 정확히 의도한 것만
통과시킨다. ⚠️`{__name__=~".+"}` 형태의 전체 매칭 질의는 AMP가 **403**으로 거부한다 —
같은 자격증명으로 위 넷은 통과하므로 인증이 아니라 질의 형태의 문제다.

**⛔ 아직 안 잰 것 — 실제 청구액.** 위 금액은 전부 산수다. CE는 **이틀 이상 지연**되므로
(Risk 4) **2026-08-19 이후** `make spend-check`와 `aws ce get-cost-and-usage`(⚠️크레딧
제외 필터 필수)로 **AMP 라인 아이템이 예상($1.42/월 = 일 ~$0.047)과 맞는지** 대조해야
4a가 닫힌다. 그 전까지 이 문서의 비용은 **가정이지 측정이 아니다**.

> ✅ **닫혔다 (2026-08-30) — §10이 그 대조다.** 결과는 **$0.00**이고, 어긋난 쪽은 AWS가
> 아니라 **§3이 프리티어를 배제한 근거**였다.

## 10. 실제 청구액 대조 (2026-08-30) — DoD 마지막 칸

권위 증거: `docs/evidence/amp-actual-bill-is-zero-and-the-free-tier-reason-was-inverted.log`.

**측정값 (CE, 크레딧/환불 제외 필터 적용 · `RECORD_TYPE`으로 분해)**

    APN2-AMP:MetricSampleCount       798,331 Metric Datapoints    $0.00
    APN2-AMP:MetricStorageByteHrs    0.00050128 GB-Month          $0.00
    AMP:QuerySamplesProcessed        920 Metric Datapoints        $0.00

`Credit` 행은 **없다** — 크레딧 상쇄가 아니라 **Usage 행 자체가 $0**이다. 그리고 AMP 그룹은
08-17부터 **13일 전부 CE에 존재한다**(계량은 되고 값이 0). ⚠️"목록에 없어서 0"과 "계량하고
0"은 다른 사실이고, 여기선 **후자**다.

**사유 — §3의 전건이 거짓**

    $ aws freetier get-free-tier-usage --region us-east-1
      APN2-AMP:MetricSampleCount    actual 798,331   limit 40,000,000   "Always Free"

AMP 프리티어는 **12개월 한정이 아니다.** §3은 *"12개월 한정이면 이 계정엔 안 붙는다"*는
**조건문**을 세우고 전건이 참이라고 가정했다 — 그리고 **무엇이 확정할지를 정확히 지목했다**
(*"AMP를 켠 뒤 첫 청구서"*). 오늘 한 건 그 측정의 실행이다.

**교차 확인 (2.4%)**: AMP에 직접 물어 잰 실가동 **41.3 수집-시간** × 설계 부하 19,800 샘플/시간
= **817,740** vs AWS 계량 **798,331**. 파이프 모델과 청구 계량이 서로를 확인한다.

**허용목록 유출 0**: 전체 창에서 workspace가 아는 메트릭 이름은 **정확히 4개**이고, 시계열은
**08-17T08:00Z와 08-27T12:00Z 두 시점 모두 308**(22/50/220/16 — §2의 네 칸 그대로).

**⚠️ 비용 절벽의 위치가 바뀌었다 (요율 → 한도)**

| | 월 샘플 | 40M 한도 대비 | 청구 |
|---|---|---|---|
| 설계 정상부하 (4종 @ 60s) | 15.8 M | **39.5%** | **$0.00** |
| 실측 예측치 (간헐 운영) | 0.825 M | 2.1% | $0.00 |
| KSM 전체 (4,188 시계열) | 181 M | 452% | 과금 |
| **필터 없음 (52,438 시계열)** | **5,131 M** | **12,828%** | **≈$180/월** |

⇒ **"AMP는 어차피 공짜"는 틀린 요약이다.** `test_amp_cost_handles.py`의 계약(네 이름 ·
`keep` · 목적지 하나 · KSM 60s)은 **하중이 줄지 않았다** — 그게 40M을 128배 넘지 않게 하는
유일한 물건이다.

**⚠️ 두 번째 발견 — 파이프는 연속이 아니고 지금 죽어 있다**

13일 중 **4일만**(08-17 11.1h · 08-19 10.0h · 08-23 3.6h · 08-27 16.7h), 마지막 샘플
**08-27T19:55Z**. 스택이 로컬 **kind** 위에 있고 Docker가 떠 있을 때만 살기 때문이다
(오늘 `docker info` 실패). duty cycle **13%**. ⇒ **$1.42/월은 720시간 연속 가동을 가정한
수이고, 이 환경에서는 원리상 발생하지 않는다.** 프리티어가 없었더라도 실제 청구는 $1.42가
아니라 **$0.07**이었다. **가정이 지배하는 추정은 추정이 아니라 그 가정이다** — 08-15엔
시계열 수에서, 오늘은 **가동 시간**에서 같은 문장이 성립했다.

**접을 때 (D50 유지)**: IAM 사용자 `amp-remote-write-4a` · 액세스 키 · 워크스페이스
`ws-929b8da9-…` 셋 다 삭제. ⚠️**청구액이 $0이라고 지울 이유가 줄지 않는다** — 대가는 돈이
아니라 **장기 액세스 키 하나**였고 프리티어는 그걸 깎아 주지 않는다.


## 11. 접었다 (2026-09-01) — 사용자 결정

D50이 *"접으면 워크스페이스·IAM 사용자·키 셋 다 지울 것"*이라 적었고, 08-30 실측에서 **셋 다
그대로**였다. 사용자 결정을 받아 지웠다.

    삭제 전   워크스페이스 ACTIVE (ap-northeast-2, 8리전 스윕에서 유일)
              IAM 사용자 · 관리형 정책 0 · 인라인 1건 = aps:RemoteWrite × 워크스페이스 1
              키 AKIA…62VN Active, 마지막 사용 2026-08-30T14:25Z aps
    삭제 후   8리전 전부 0 · describe-workspace → ResourceNotFoundException
              get-user → NoSuchEntity · list-users|amp → []

⚠️ `get-access-key-last-used`는 `AccessDenied`를 답했다 — **그건 부재의 증거가 아니다**
(q-user에 권한이 없어서 나온 답이고, 키가 살아 있어도 같은 답이다). 키가 사라졌다는 증거는
**소유 사용자가 없다는 것**이다.

⚠️ **접은 것은 파이프이지 결론이 아니다.** §9의 DoD 넷과 §10의 실제 청구 $0.00은 그대로
유효하다. 다시 붙일 때 이 문서의 §4(허용목록)·§8(간격)이 여전히 승인 대상이고, **다음
워크스페이스 id는 여기서 정해진다** — 그래서 가드가 id를 더는 박지 않는다.

⚠️ 값 파일의 `remoteWrite:` 블록도 같이 지웠다. 안 지우면 **삭제된 워크스페이스를 가리키는
설정**이 git에 남는다. 로컬 kind는 도커가 꺼져 있어 이미 멈춰 있었고, 다음에 띄우면 고아가 될
`monitoring/amp-remote-write` Secret을 지울 것.

증거: `docs/evidence/folding-4a-the-price-was-a-long-lived-key.log`
