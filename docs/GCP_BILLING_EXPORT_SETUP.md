# GCP 결제 내보내기 켜기 (콘솔 수동 5분)

> **왜 손으로 하나:** GCP엔 이 토글을 켜는 API도 gcloud 명령도 **없다**. Cloud Billing v1
> discovery 19개 메서드 중 `export`/`bigquery` 관련 **0건**이고 `gcloud billing`의 그룹은
> accounts/budgets/projects뿐이다(2026-08-09 실측 → `docs/evidence/gcp-actual-spend-has-no-api.log`).
>
> **왜 필요한가:** 이걸 켜기 전까지 **GCP 실지출은 어떤 방법으로도 못 읽는다.** 예산 경보는
> "넘었다"만 말하고 **얼마인지는 말하지 않는다**(Budgets API는 설정액만 돌려준다). 07월 GKE
> 방치 비용을 끝내 확정하지 못한 게 이 때문이다 → `STATUS` Risk 4.
>
> **비용:** $0. 내보내기 자체는 무료이고, 적재량은 BigQuery 무료 티어(스토리지 10GB/월,
> 쿼리 1TB/월) 안에 한참 못 미친다.

## 0. 먼저 알아야 할 것 — 소급 적용이 안 된다

**내보내기는 켠 시점부터 쌓인다. 과거는 채워지지 않는다.** 그래서:

- 켜는 게 빠를수록 좋다. 미루면 그만큼의 지출이 **영구적으로 조회 불가**로 남는다.
- **07월 GKE 방치 비용은 이 작업으로도 복구되지 않는다.** 이미 지나간 창이다.
- Phase 4를 켜기 **전에** 켜 두는 게 요점이다 — 켜고 나서 "얼마 나왔지?"를 물을 수 있어야 한다.

## 1. 준비 (전부 확인됨, 2026-08-09)

| 항목 | 값 | 상태 |
|---|---|---|
| 결제 계정 | `010556-A2B7AE-292490` | 예산 2건(₩14,000 · ₩28,000)이 걸려 있음 |
| 대상 프로젝트 | `project-ec7809f7-0fb5-45d4-b6d` ("My First Project") | BigQuery API **활성** |
| 대상 데이터셋 | `billing_export` (asia-northeast3) | **이미 존재**(2026-07-21 생성), 테이블 0개 |
| 로그인 계정 | `yeongsigchoe7@gmail.com` | 데이터셋 OWNER · 이 결제 계정이 열려 있는 유일한 로그인 |

⚠️ **콘솔에 어느 계정으로 로그인했는지 먼저 확인할 것.** 이 결제 계정은
`yeongsigchoe7@gmail.com` 쪽이다 — 다른 계정으로 들어가면 결제 계정 자체가 보이지 않는다.
필요 권한은 **결제 계정 관리자**(`billing.accounts.update`)와 대상 데이터셋 쓰기 권한이고,
둘 다 위 계정이 이미 갖고 있다.

**데이터셋을 새로 만들 필요는 없다.** 이미 있다.

## 2. 절차

1. <https://console.cloud.google.com/billing> → 결제 계정 **`010556-A2B7AE-292490`** 선택.
2. 왼쪽 메뉴 **결제 내보내기**(Billing export) → **BigQuery 내보내기** 탭.
3. **표준 사용량 비용**(Standard usage cost) 행의 **설정 수정**(Edit settings).
4. 프로젝트 = **`project-ec7809f7-0fb5-45d4-b6d`**, 데이터셋 = **`billing_export`** 선택 → **저장**.
5. (선택) **가격 책정**(Pricing) 내보내기도 같은 데이터셋으로 켜 두면 SKU 단가를 붙일 수 있다.

세 종류가 나란히 보인다 — 무엇을 켜는지 헷갈리기 쉽다:

| 내보내기 | 테이블 | 이번에 켜는 것 |
|---|---|---|
| **표준 사용량 비용** | `gcp_billing_export_v1_010556_A2B7AE_292490` | ✅ **이것** — SKU별 지출 |
| 상세 사용량 비용 | `gcp_billing_export_resource_v1_...` | 선택(리소스 단위까지, 행 수가 훨씬 많다) |
| 가격 책정 | `cloud_pricing_export` | 선택 |

`make spend-check`는 `gcp_billing_export`로 시작하는 테이블을 찾으므로 **표준·상세 어느 쪽이든
인식한다**.

## 3. 켜졌는지 확인 — 추측하지 말고 물어볼 것

**저장했다는 것과 집행된다는 것은 다르다**(₩20 예산 때 이미 밟았다). 레포에 확인 수단이 있다:

    make spend-check

GCP 절이 이렇게 바뀌면 성공이다:

    GCP 실사용
        잴 수 있다 — 결제 내보내기 테이블 project-...:billing_export.gcp_billing_export_v1_...

바뀌지 않았다면 아래 순서로 좁힌다:

- **첫 테이블이 생기기까지 통상 수 시간 걸린다.** 저장 직후엔 정상적으로 "아직 못 잰다"가
  나온다 — 실패로 읽지 말 것. 하루 지나도 그대로면 그때부터가 문제다.
- 다른 데이터셋을 골랐다면 `PLATFORM_GCP_BILLING_EXPORT=프로젝트:데이터셋`으로 고정해 확인할
  수 있다(프로브는 기본적으로 **모든 프로젝트의 모든 데이터셋을 훑는다**).
- 콘솔 로그인 계정이 §1과 다른지 다시 볼 것.

## 4. 켜진 뒤

이번 달 SKU별 지출:

    bq query --use_legacy_sql=false --project_id=project-ec7809f7-0fb5-45d4-b6d '
      SELECT service.description AS service, ROUND(SUM(cost), 2) AS cost
      FROM `project-ec7809f7-0fb5-45d4-b6d.billing_export.gcp_billing_export_v1_010556_A2B7AE_292490`
      WHERE invoice.month = FORMAT_DATE("%Y%m", CURRENT_DATE())
      GROUP BY 1 HAVING cost > 0 ORDER BY 2 DESC'

⚠️ `cost`만 더하면 **크레딧이 반영되지 않은 총사용액**이다. 청구 예정액을 보려면
`credits`를 펼쳐 더해야 한다 — AWS에서 크레딧 때문에 "$0"을 두 번 보고했던 것과 **정확히
반대 방향의 같은 함정**이다(둘은 다른 질문의 답이다 → `STATUS` Risk 4).

`make spend-check`의 `MEASURABLE` 분기는 **아직 이 질의를 대신 돌려 주지 않는다** — 태워 볼
데이터가 없어 검증할 수 없었고, 검증 안 된 분기를 늘리지 않는 게 이 레포의 규칙이다. 데이터가
생기면 그때 붙인다.

## 관련

- `docs/evidence/gcp-actual-spend-has-no-api.log` — API가 없다는 것의 실측 근거
- `docs/evidence/gcp-budget-always-firing-fixed.log` — ₩20 → ₩28,000 예산 재보정
- `STATUS` Risk 4 · `NEXT_PLAN` Phase 4
