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

GCP is reported too, and the honest report is not a number. Verified against the
live discovery documents on 2026-08-09: Cloud Billing v1 exposes 19 methods and
none of them read spend, and the Budgets API returns the *configured* amount plus
`spendBasis` — never an actual. The only path to actual GCP spend is the BigQuery
billing export, whose toggle exists in the console alone. So a repo that says
nothing about GCP here is making the same mistake in a new place: absence reads as
zero. This prints whether that export exists yet, and names it as unmeasured when
it does not. It deliberately does *not* exit 2 for a missing export — that is a
known, named gap rather than a failed lookup, and a probe that is red every run
teaches people to skip it (the same lesson as the always-firing budget alert).

READ-ONLY IS NOT FREE. Cost Explorer bills **$0.01 per request** (measured
2026-08-10: 3 calls = $0.03, 24 calls = $0.24, MTD $0.27 under `APS$USE` — the
one line in this account's bill that this repo put there itself). A full run makes
several CE calls, and `make spend-watch` once a day comes to roughly $0.30/month.
That is cheap and worth it, but it belonged in writing: a tool whose subject is
forgotten recurring charges should not be a forgotten recurring charge, and this
number appeared in no document until it was looked for.

⚠️ CE ALSO REPORTS THE CURRENT DAY LATE. A 0 on today's row is not a measured
zero — it is a row that has not filled in yet. Read the trailing days, not the
last one, before concluding something was switched off.

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
import os
import subprocess

#: Budgets exclude these record types; Cost Explorer includes them unless told not
#: to. Keeping the literal here (rather than inline) so the guard can assert on it.
CREDIT_EXCLUDING_FILTER = {
    "Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}}
}

#: Billing export tables are named `gcp_billing_export_v1_<ACCOUNT>` (or
#: `..._resource_v1_...`) whatever the dataset is called, so the table name is what
#: identifies an export — not the dataset name, which the console lets you choose.
GCP_EXPORT_TABLE_PREFIX = "gcp_billing_export"

#: Set to `project:dataset` to skip the sweep when the export location is known.
GCP_EXPORT_ENV = "PLATFORM_GCP_BILLING_EXPORT"

#: Azure *does* have a spend API — but the obvious CLI does not reach it. Measured
#: 2026-08-09: `az consumption usage list` returned 28 rows for 08-01~08-09 with
#: `pretaxCost` null in **every one**, so summing them gives exactly 0.0 while Cost
#: Management reports ₩1,989.33 for the same window. Third instance of one shape —
#: a call that succeeds, returns plausible rows, and renders as zero. Keeping the
#: query as a literal so the guard can assert the probe asks the right question.
AZURE_COST_QUERY = {
    "type": "ActualCost",
    "dataset": {
        "granularity": "None",
        "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
        "grouping": [{"type": "Dimension", "name": "ServiceName"}],
    },
}

#: `TheLastMonth` is rejected by this API ("currently not supported"), so windows are
#: always passed explicitly — which also keeps --days meaning the same thing for
#: every provider.
AZURE_COST_URL = (
    "https://management.azure.com/subscriptions/{sub}/providers"
    "/Microsoft.CostManagement/query?api-version=2023-03-01"
)


def _aws(*args: str) -> tuple[int, str]:
    """Like :func:`_run`, and for the same reason it must never raise.

    `_run` has caught a missing binary since it was written; this sibling did not,
    so on a machine without the AWS CLI the probe printed the `AWS 실사용` heading
    and then **died mid-report with a traceback** — heading on stdout, cause on
    stderr, exit 1. That is the empty-section-reads-as-zero failure this file
    exists to prevent, arriving through the one door the fix did not cover, and
    with the wrong exit code on top (1, not the documented 2).
    """
    try:
        proc = subprocess.run(["aws", *args], capture_output=True, text=True)
    except OSError as exc:
        return 127, f"aws 실행 실패: {exc}"
    return proc.returncode, (proc.stdout if proc.returncode == 0 else proc.stderr)


def _why(output: str) -> str:
    """The last meaningful line of a failure, for printing.

    A probe that says only "could not measure" makes every cause look alike. The one
    that actually happens here is transient — Cost Management answers 429 "Too many
    requests" when asked a few times in a row (hit live on 2026-08-09) — and knowing
    that is the difference between retrying in a minute and going to look for a
    broken credential.
    """
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else "(이유 없음)"


def _unmeasured(subject: str) -> None:
    """Says "could not look" *inside* the section it belongs to.

    On stdout, not stderr. On a terminal stdout is line-buffered and the two streams
    interleave in the right order, which is how this read correctly while it was being
    written. Through a pipe — which is how it is actually read: evidence logs,
    `make spend-check | tee`, anything captured — stdout is block-buffered and every
    warning is hoisted above every heading. Measured 2026-08-10 with all three CLIs
    failing: the reader got three warnings at the top and then `AWS 실사용`,
    `도는 EC2 인스턴스`, `Azure 실사용` **all three visibly empty**. An empty section
    under a heading reads as zero, which is the one mistake this probe exists to stop
    — the reporter was making it about itself. Exit 2 stays the machine-readable half.
    """
    print(f"    측정하지 못했다. 이것은 {subject} 아니다.")


def _run(*args: str) -> tuple[int, str]:
    """Any read-only CLI. Returns (code, stdout-or-stderr), never raises."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        return 127, f"{args[0]} 없음"
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
        print(f"    Cost Explorer 조회 실패 — {_why(out)}")
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
        print(f"    리전 목록 조회 실패 — {_why(out)}")
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


def _datasets(payload: str) -> list[str]:
    try:
        rows = json.loads(payload)
    except json.JSONDecodeError:
        return []
    return [r["datasetReference"]["datasetId"] for r in rows if "datasetReference" in r]


def _export_table_in(location: str) -> str | None:
    """The billing export table inside `project:dataset`, if the toggle was ever set.

    An empty dataset prints nothing rather than `[]`, which is exactly the shape the
    live account is in: the dataset was made in 2026-07 and the console toggle that
    fills it never was.
    """
    code, out = _run("bq", "--format=json", "ls", location)
    if code != 0:
        return None
    try:
        rows = json.loads(out)
    except json.JSONDecodeError:
        return None
    for row in rows:
        table = (row.get("tableReference") or {}).get("tableId", "")
        if table.startswith(GCP_EXPORT_TABLE_PREFIX):
            return f"{location}.{table}"
    return None


def gcp_actual_spend() -> tuple[str, str]:
    """Whether GCP spend is readable at all — MEASURABLE / NOT_EXPORTED / NO_TOOLING.

    Never returns a number, because none is available: Cloud Billing v1 has no
    method that reads spend and the Budgets API returns the configured amount. The
    only true answer is whether the BigQuery export exists, so that is what this
    returns. The dataset is swept for rather than assumed, for the same reason the
    AWS half sweeps every region: the configured place is not where it turned out
    to be.
    """
    pinned = os.environ.get(GCP_EXPORT_ENV)
    if pinned:
        table = _export_table_in(pinned)
        if table:
            return "MEASURABLE", table
        return "NOT_EXPORTED", f"{GCP_EXPORT_ENV}={pinned} 에 내보내기 테이블이 없다"

    code, out = _run("gcloud", "projects", "list", "--format=value(projectId)")
    if code != 0:
        return "NO_TOOLING", f"프로젝트 목록을 못 읽었다 — {_why(out)}"
    projects = out.split()
    if not projects:
        return "NO_TOOLING", "이 자격증명에 보이는 프로젝트가 없다"
    for project in projects:
        code, listing = _run("bq", "--project_id", project, "--format=json", "ls")
        if code != 0:
            continue          # a project without BigQuery is not a finding
        for dataset in _datasets(listing):
            table = _export_table_in(f"{project}:{dataset}")
            if table:
                return "MEASURABLE", table
    return "NOT_EXPORTED", f"프로젝트 {len(projects)}개를 훑었지만 내보내기 테이블이 없다"


def azure_spend(start: str, end: str) -> list[tuple[str, str, list[tuple[str, float]]]] | None:
    """Per-subscription actual cost, grouped by service. None when it cannot be read.

    Sweeps every subscription the login can see rather than the default one, for the
    same reason the AWS half sweeps every region: the spend was not where the active
    configuration pointed.

    The Cost Management query is a POST, which is worth saying out loud in a probe
    that promises to change nothing — it is a query endpoint, not a write. The guard
    pins the URL so no other POST can be added quietly.
    """
    code, out = _run("az", "account", "list", "--output", "json")
    if code != 0:
        print(f"    구독 목록 조회 실패 — {_why(out)}")
        return None
    try:
        subscriptions = [(s["id"], s.get("name", s["id"])) for s in json.loads(out)]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    body = dict(AZURE_COST_QUERY)
    body["timeframe"] = "Custom"
    body["timePeriod"] = {"from": f"{start}T00:00:00Z", "to": f"{end}T00:00:00Z"}

    found: list[tuple[str, str, list[tuple[str, float]]]] = []
    for sub_id, name in subscriptions:
        code, out = _run(
            "az", "rest", "--method", "post",
            "--url", AZURE_COST_URL.format(sub=sub_id),
            "--body", json.dumps(body), "--output", "json",
        )
        if code != 0:
            print(f"    {name}: 비용 조회 실패 — {_why(out)}")
            return None
        try:
            rows = json.loads(out)["properties"]["rows"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
        currency = rows[0][-1] if rows else ""
        ranked = sorted(((r[1], float(r[0])) for r in rows if float(r[0]) > 0),
                        key=lambda kv: -kv[1])
        found.append((name, currency, ranked))
    return found


def report_azure(start: str, end: str) -> bool:
    """Prints Azure's answer. Returns False when it could not be measured."""
    print("Azure 실사용 (ActualCost, 전 구독)")
    measured = azure_spend(start, end)
    if measured is None:
        _unmeasured("'0'이")
        return False
    for name, currency, ranked in measured:
        total = sum(amount for _, amount in ranked)
        print(f"    {name} — 총 {total:,.2f} {currency}")
        for service, amount in ranked:
            print(f"      {service:<44} {amount:>12,.2f}")
        if not ranked:
            print("      (해당 창에 실사용 없음)")
    if not measured:
        print("    (이 로그인에 보이는 구독이 없다)")
    return True


def report_gcp() -> None:
    """GCP's answer is a state, not a number — printing nothing would read as ₩0."""
    print("GCP 실사용")
    status, detail = gcp_actual_spend()
    if status == "MEASURABLE":
        print(f"    잴 수 있다 — 결제 내보내기 테이블 {detail}")
        print(f"    bq query --use_legacy_sql=false 'SELECT service.description,"
              f" SUM(cost) FROM `{detail}` GROUP BY 1 ORDER BY 2 DESC'")
        return
    print(f"    아직 못 잰다 — {detail}")
    print("    이것은 '₩0'이 아니다. GCP엔 지출을 읽는 API가 없다 — Cloud Billing v1엔")
    print("    비용 메서드가 없고 Budgets API는 설정액만 준다(2026-08-09 discovery 실측).")
    print("    유일한 길은 콘솔의 결제 내보내기다 — 절차와 확인법:")
    print("      docs/GCP_BILLING_EXPORT_SETUP.md   (켜면 이 줄이 바뀐다)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=None,
                        help="trailing window instead of month-to-date")
    args = parser.parse_args()

    start, end = _window(args.days)
    print(f"AWS 실사용 (크레딧·환불 제외)  {start} ~ {end} (end exclusive)")

    unmeasured = False
    measured = spend_by_service(start, end)
    if measured is None:
        _unmeasured("'$0'이")
        unmeasured = True
    else:
        total, ranked = measured
        print(f"  총 ${total:.2f}")
        for service, amount in ranked:
            print(f"    {service:<46} ${amount:.2f}")
        if not ranked:
            print("    (해당 창에 실사용 없음)")

    print("\n도는 EC2 인스턴스 (전 리전)")
    instances = running_instances()
    if instances is None:
        _unmeasured("'0대'가")
        unmeasured = True
    else:
        for region, iid, itype, label in instances:
            print(f"    {region:<16} {iid:<21} {itype:<12} {label}")
        if not instances:
            print("    (없음)")

    # Reached even when AWS could not be measured: one provider failing must not
    # delete the others from the report, which is the omission this section is about.
    print()
    if not report_azure(start, end):
        unmeasured = True

    print()
    report_gcp()

    print("\n주의: 이 프로브는 아무것도 중지·종료하지 않는다. 조치는 사람이 정한다.")
    if unmeasured:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
