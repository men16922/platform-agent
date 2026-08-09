#!/usr/bin/env python3
"""What is this account actually spending, and what is running that explains it?

Written because the same check was done by hand twice on 2026-08-09 and reported
"$0" both times while $8.81 had accrued. Two defaults did it, and both of them
answer a *reassuring* question instead of the one being asked:

1. **Cost Explorer includes credits by default.** `get-cost-and-usage` with no
   filter returns spend *net of credits*, so a credited account reads as $0 no
   matter how much it is consuming. AWS Budgets excludes credits and refunds, which
   is why the budget alert fired while the hand query said nothing was happening.
   The two are answers to different questions — "what will be charged" versus
   "what am I consuming" — and only the second finds a forgotten resource.

2. **`describe-instances` is one region.** The forgotten instance was in
   `us-east-1` while the configured default region was `us-west-2`.

So this probe hard-codes the credit-excluding filter and sweeps every region, and
`tests/test_cloud_spend_probe.py` fails if either is removed. Read-only by
construction: it never stops, terminates or deletes anything — that stays a human
decision, and the guard asserts no mutating verb appears here.

    python scripts/probe_cloud_spend.py            # month to date
    python scripts/probe_cloud_spend.py --days 30  # trailing window

Exit codes:
  0 = measured (spend may be zero — that is a result, not a failure)
  2 = could not measure (no credentials, API disabled). NOT reported as $0.

The exit-2 case matters: "I could not look" must never render as "nothing is
running", which is the whole failure this probe exists to prevent.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys

#: Budgets exclude these record types; Cost Explorer includes them unless told not
#: to. Keeping the literal here (rather than inline) so the guard can assert on it.
CREDIT_EXCLUDING_FILTER = {
    "Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}}
}


def _aws(*args: str) -> tuple[int, str]:
    proc = subprocess.run(["aws", *args], capture_output=True, text=True)
    return proc.returncode, (proc.stdout if proc.returncode == 0 else proc.stderr)


def _window(days: int | None) -> tuple[str, str]:
    """[start, end) — Cost Explorer's end is exclusive, so end = tomorrow."""
    today = _dt.date.today()
    end = today + _dt.timedelta(days=1)
    start = (today - _dt.timedelta(days=days)) if days else today.replace(day=1)
    return start.isoformat(), end.isoformat()


def spend_by_service(start: str, end: str) -> tuple[float, list[tuple[str, float]]] | None:
    """Real consumption, credits excluded. Returns None when it cannot be measured."""
    code, out = _aws(
        "ce", "get-cost-and-usage",
        "--time-period", f"Start={start},End={end}",
        "--granularity", "MONTHLY",
        "--metrics", "UnblendedCost",
        "--filter", json.dumps(CREDIT_EXCLUDING_FILTER),
        "--group-by", "Type=DIMENSION,Key=SERVICE",
    )
    if code != 0:
        print(f"  ! Cost Explorer 조회 실패: {out.strip().splitlines()[-1:]}", file=sys.stderr)
        return None
    rows: dict[str, float] = {}
    for period in json.loads(out).get("ResultsByTime", []):
        for group in period.get("Groups", []):
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            rows[group["Keys"][0]] = rows.get(group["Keys"][0], 0.0) + amount
    ranked = sorted(((k, v) for k, v in rows.items() if v > 0.005), key=lambda kv: -kv[1])
    return sum(v for _, v in ranked), ranked


def running_instances() -> list[tuple[str, str, str, str]] | None:
    """Every running instance in every region — not just the configured one."""
    code, out = _aws("ec2", "describe-regions", "--query", "Regions[].RegionName",
                     "--output", "text")
    if code != 0:
        print(f"  ! 리전 목록 조회 실패: {out.strip().splitlines()[-1:]}", file=sys.stderr)
        return None
    found: list[tuple[str, str, str, str]] = []
    for region in out.split():
        code, out2 = _aws(
            "ec2", "describe-instances", "--region", region,
            "--filters", "Name=instance-state-name,Values=running",
            "--query",
            "Reservations[].Instances[].[InstanceId,InstanceType,LaunchTime,"
            "Tags[?Key=='Name']|[0].Value]",
            "--output", "text",
        )
        if code != 0:
            continue          # a region the account cannot see is not a finding
        for line in out2.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                found.append((region, parts[0], parts[1], f"{parts[3] if len(parts) > 3 else '-'} "
                                                          f"(since {parts[2][:10]})"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=None,
                        help="trailing window instead of month-to-date")
    args = parser.parse_args()

    start, end = _window(args.days)
    print(f"AWS 실사용 (크레딧·환불 제외)  {start} ~ {end} (end exclusive)")

    measured = spend_by_service(start, end)
    if measured is None:
        print("\n측정하지 못했다. 이것은 '$0'이 아니다.", file=sys.stderr)
        return 2
    total, ranked = measured
    print(f"  총 ${total:.2f}")
    for service, amount in ranked:
        print(f"    {service:<46} ${amount:.2f}")
    if not ranked:
        print("    (해당 창에 실사용 없음)")

    print("\n도는 EC2 인스턴스 (전 리전)")
    instances = running_instances()
    if instances is None:
        print("\n측정하지 못했다. 이것은 '0대'가 아니다.", file=sys.stderr)
        return 2
    for region, iid, itype, label in instances:
        print(f"    {region:<16} {iid:<21} {itype:<12} {label}")
    if not instances:
        print("    (없음)")

    print("\n주의: 이 프로브는 아무것도 중지·종료하지 않는다. 조치는 사람이 정한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
