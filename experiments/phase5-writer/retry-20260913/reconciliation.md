# M83/M84 진단 증거의 오프라인 조정

`writer_reconciliation.reconcile_ref_read`는 고정 review bytes, 실행/민팅 receipt/operation 기록, 운영자 PR 관측과 이후 App 봇 계정 관측을 받는다. 비교 대상은 요청·신원·권한·시도/응답 ID·시각·Git snapshot·파일·폐기 기록이다. 자료가 없거나 다른 실행/시점/신원의 관측이 섞이면 inconclusive, 실제 형제 쓰기/변경 기록이면 boundary_failure를 반환한다.

결과 consistent_partial은 부분 기록의 일관성이다. 원래 STOPPED/TypeError·Issue App null·설치 신원 파일 조회 부재를 보존한다. 기록의 출처나 과거 POST 자격증명을 인증하지 않으며 live_verified/writer_success_verified/retry_authorized=false다. 재호출은 읽기 전용 동일 계산이고 기존 시도를 재전송할 권한을 주지 않는다. 기존 세 권한 workflow와 production CLAIMED 상태는 변경하지 않는다.

CLI는 JSON 중복 키/비표준 숫자를 거부하고 bundle 256 KiB·review 16 KiB까지만 읽는다. `--as-of`와 `--max-age-seconds`는 필수다. 마지막 재조회만 유효 기간을 검사하고 과거 실행의 시도 순서와 민팅 만료 시각을 별도로 검사한다. 과거 관측 시각을 지정한 아래 실행은 역사적 재평가이며 현재 GitHub 상태 확인이 아니다. exit 0도 부분 일관성을 뜻한다.

```sh
/opt/anaconda3/bin/python scripts/reconcile_registry_writer.py \
  experiments/phase5-writer/retry-20260913/ref-read-observations.json \
  --review experiments/phase5-writer/retry-20260913/ref-read-review.json \
  --review-sha256 a47f64681fcdab183691545f11d4d0260fa92dd76347d15feecc9c839c7b5825 \
  --as-of 2026-09-13T11:15:21.698927+00:00 --max-age-seconds 300
```

보존 기록 두 번의 결과는 동일했고 원래 입력 SHA는 유지됐다. 결과는 docs/evidence/writer-reconciliation-result-2026-09-13.json, 검증은 writer-reconciliation-verification-2026-09-13.json과 writer-reconciliation-mutations-2026-09-13.json에 있다.
