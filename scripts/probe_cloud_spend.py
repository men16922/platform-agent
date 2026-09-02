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
import time
import unicodedata

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

#: The 429 body says "Please retry" and nothing else; the *headers* say how long, and
#: `az rest` does not show headers — which is why the transport here is `curl -D -`
#: with an `az`-minted token, and not the obvious one. Measured 2026-09-01: the exhausted bucket was
#: `clienttype-requests: DefaultQuota:0` while entity (2), tenant (18) and QPU (58/h)
#: all had room, and `clienttype-retry-after` asked for 5s, then 40s on the next try.
#: Waiting the 40 returned 200. So the previous record — "retrying was not the answer
#: this time", written after three tries 20s apart — had the conclusion backwards:
#: retrying *was* the answer, at an interval the server had already named and nobody
#: read. A fixed interval below what is asked for looks exactly like a permanent
#: failure, and a 13-hour-later retry (also 429, on the first try) looks like one too.
AZURE_429_HINT = (
    "429는 스로틀이고 서버가 대기 시간을 헤더로 말한다. 프로브는 이제 "
    "clienttype-retry-after 를 읽어 그만큼 기다렸다 다시 묻는다(최대 3회). "
    "여기까지 왔다면 그보다 오래 걸린다는 뜻이니 직접 볼 것: "
    "curl -D- ... | grep clienttype-retry-after  (09-01 실측 5s→40s, 40 기다리니 200). "
    "고정 간격 재시도 금지 — 영구 실패와 구분되지 않는다."
)

#: Read in this order. `clienttype-retry-after` is the one that was actually
#: exhausted on 2026-09-01 (`clienttype-requests: DefaultQuota:0` while entity,
#: tenant and QPU all had room) and the one that named 5s then 40s; `retry-after` is
#: the standard spelling and a reasonable fallback if this API ever sends it.
AZURE_RETRY_AFTER_HEADERS = ("clienttype-retry-after", "retry-after")

#: Bounded twice: at most this many retries, and each wait clamped below. A probe
#: being throttled must still end — the worst case here is ~3 minutes of waiting for
#: one subscription, and that only when the server keeps asking for the maximum.
AZURE_MAX_RETRIES = 3
AZURE_MAX_WAIT_SECONDS = 60.0


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


def _curl(*args: str, config: str = "") -> tuple[int, str]:
    """A read of an HTTPS endpoint whose *response headers* survive.

    Separate from :func:`_run` for one reason: `--config -` reads options from stdin,
    and that is the only place a bearer token can go without appearing in `ps` for
    every other process on this machine. The URL stays in argv on purpose — it is not
    a secret and it is the thing the guard pins.
    """
    try:
        proc = subprocess.run(["curl", *args, "--config", "-"], input=config,
                              capture_output=True, text=True)
    except OSError as exc:
        return 127, f"curl 실행 실패: {exc}"
    return proc.returncode, (proc.stdout if proc.returncode == 0 else proc.stderr)


def _sleep(seconds: float) -> None:
    """Indirection so a guard can watch what was waited without waiting it."""
    time.sleep(seconds)


def _split_http(raw: str) -> tuple[int, str, dict[str, str]]:
    """`curl -D -` output → (status, body, lower-cased headers).

    Loops because an interim block (`100 Continue`) is a header block too, and the
    last one is the answer. A non-HTTP payload — curl's own error text — reads back
    as status 0 with the text intact, so the caller never mistakes it for a response.
    """
    text = raw.replace("\r\n", "\n")
    status, headers = 0, {}
    while text.startswith("HTTP/"):
        head, separator, rest = text.partition("\n\n")
        if not separator:
            head, rest = text, ""
        lines = head.splitlines()
        fields = lines[0].split()
        status = int(fields[1]) if len(fields) > 1 and fields[1].isdigit() else 0
        headers = {}
        for line in lines[1:]:
            name, colon, value = line.partition(":")
            if colon:
                headers[name.strip().lower()] = value.strip()
        text = rest
    if status == 0:
        return 0, raw, {}
    return status, text, headers


def _retry_after(headers: dict[str, str]) -> float | None:
    """How long the server asked for, or None when it did not say.

    None is a real answer and must stay distinguishable from 0: a 429 carrying no
    interval gets no retry, because inventing one is exactly the mistake that made a
    throttle look permanent (three tries 20s apart against a server asking for 40).
    """
    for name in AZURE_RETRY_AFTER_HEADERS:
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            wait = float(raw.strip())
        except ValueError:
            continue
        if wait < 0:
            continue
        return min(wait, AZURE_MAX_WAIT_SECONDS)
    return None


def _azure_token() -> str | None:
    """A bearer token for management.azure.com, or None when the login has none.

    The transport moved off `az rest` to see response headers, so the auth `az rest`
    was doing implicitly has to happen here. `az` is still the only source of the
    token — this is not a second way to log in.
    """
    code, out = _run("az", "account", "get-access-token",
                     "--resource", "https://management.azure.com",
                     "--output", "json")
    if code != 0:
        return None
    try:
        return json.loads(out)["accessToken"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _post_cost_query(url: str, body: str, token: str) -> tuple[int, str, dict[str, str]]:
    """One Cost Management query, with the response headers kept.

    `az rest` is the obvious transport and it discards the headers, which is the
    whole reason a 429 read as a permanent failure for a day: the server had already
    named its own interval and nothing in the pipeline could see it.
    """
    code, out = _curl(
        "-sS", "-D", "-", "-X", "POST", "--url", url,
        "-H", "Content-Type: application/json", "--data", body,
        config=f'header = "Authorization: Bearer {token}"\n',
    )
    if code != 0:
        return 0, out, {}
    return _split_http(out)


def _cost_query_with_retry(url: str, body: str, token: str) -> tuple[int, str]:
    """The query, retried on 429 at the interval the server named. Returns (status, body).

    Not a fixed interval and not a guessed one: only what a header said, at most
    AZURE_MAX_RETRIES times, each wait clamped to AZURE_MAX_WAIT_SECONDS. The waiting
    is announced because a probe that goes silent for 40 seconds looks hung, and a
    reader who kills it learns the wrong thing about the throttle.
    """
    status, payload, headers = _post_cost_query(url, body, token)
    for _ in range(AZURE_MAX_RETRIES):
        if status != 429:
            return status, payload
        wait = _retry_after(headers)
        if wait is None:
            return status, payload
        print(f"      429 — 서버가 {wait:g}초를 요구했다. 기다렸다 다시 묻는다.")
        _sleep(wait)
        status, payload, headers = _post_cost_query(url, body, token)
    return status, payload


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


def _export_row_count(table_id: str) -> int | None:
    """Rows in `project:dataset.table`, or None when the count cannot be read.

    A table is not an answer. The export toggle materialises the table within the
    hour and then loads into it separately, so between those two moments the table
    exists and holds nothing — measured live 2026-09-01: created 01:53Z, still
    touched at 14:08Z, `numRows` 0. Keying "잴 수 있다" on existence alone means the
    probe says it can measure and then a reader who asks gets no rows back, which is
    the empty-section-reads-as-zero failure this file exists to prevent, one level up.

    Metadata, not a query: `bq show` costs nothing and scans nothing, so asking does
    not repeat the AWS mistake where the measurement became 84% of the bill.
    """
    meta = _table_meta(table_id)
    if meta is None:
        return None
    try:
        return int(meta.get("numRows", 0))
    except (TypeError, ValueError):
        return None


def _table_meta(table_id: str) -> dict | None:
    """`bq show` metadata for `project:dataset.table`, or None when unreadable.

    One definition because two callers want different fields off the same free
    call: the row count decides MEASURABLE, and `numBytes` is what the amount query
    will scan — the only honest way to state that query's price before running it.
    """
    code, out = _run("bq", "--format=json", "show", table_id)
    if code != 0:
        return None
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _export_bytes(table_id: str) -> int | None:
    """Bytes a full scan of the export table reads, or None."""
    meta = _table_meta(table_id)
    if meta is None:
        return None
    try:
        return int(meta.get("numBytes", 0))
    except (TypeError, ValueError):
        return None


def _sql_ref(table_id: str) -> str:
    """`project:dataset.table` → `project.dataset.table`.

    Standard SQL rejects the colon form outright ("Project name needs to be
    separated by dot from dataset name"), so the command this probe printed for as
    long as the branch existed could never have run. It was never run: the branch
    needs a live export, and there was none until 2026-09-01. A printed instruction
    is a claim like any other, and this one was false for a month.
    """
    return table_id.replace(":", ".", 1)


def _project_of(table_id: str) -> str:
    """The project half of `project:dataset.table`.

    Without `--project_id` the query bills and runs in whatever `bq` defaults to,
    which on this machine was a *different* project of the same billing account
    (`claude-study-501117`, measured 2026-09-01). It would have answered — from the
    wrong place — for anyone whose default happened to hold a table of that name.
    """
    return table_id.split(":", 1)[0]


def _classify_export(table_id: str) -> tuple[str, str] | None:
    """MEASURABLE only when the table has rows; EXPORTED_EMPTY when it has none.

    None means "keep sweeping" — an empty table in one dataset must not stop the
    search, because a filled one elsewhere is the better answer and the sweep exists
    precisely because the configured place is not where things turned out to be.
    """
    rows = _export_row_count(table_id)
    if rows is None or rows > 0:
        # Unreadable metadata is not evidence of emptiness: the same rule as
        # `AccessDenied` is not evidence of absence. Report it as measurable and let
        # the query be the thing that fails, loudly, in front of the reader.
        return "MEASURABLE", table_id
    return None


def gcp_actual_spend() -> tuple[str, str]:
    """Is GCP spend readable — MEASURABLE / EXPORTED_EMPTY / NOT_EXPORTED / NO_TOOLING.

    Never returns a number, because none is available: Cloud Billing v1 has no
    method that reads spend and the Budgets API returns the configured amount. The
    only true answer is whether the BigQuery export exists **and has loaded**, so
    that is what this returns. The dataset is swept for rather than assumed, for the
    same reason the AWS half sweeps every region: the configured place is not where
    it turned out to be.

    Four states, not three, and the fourth is the one the live account was in for
    thirteen hours on 2026-09-01: exported, and still empty. Folding it into
    MEASURABLE made the probe promise an answer it could not produce; folding it
    into NOT_EXPORTED would have sent a reader back to a console toggle that was
    already correctly set. They are different problems with different next actions.
    """
    empty: str | None = None

    pinned = os.environ.get(GCP_EXPORT_ENV)
    if pinned:
        table = _export_table_in(pinned)
        if table:
            return _classify_export(table) or ("EXPORTED_EMPTY", table)
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
            if not table:
                continue
            classified = _classify_export(table)
            if classified:
                return classified
            empty = empty or table
    if empty:
        return "EXPORTED_EMPTY", empty
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

    token = _azure_token()
    if token is None:
        print("    액세스 토큰을 못 받았다 — 로그인 상태를 확인할 것 (az account show)")
        return None

    body = dict(AZURE_COST_QUERY)
    body["timeframe"] = "Custom"
    body["timePeriod"] = {"from": f"{start}T00:00:00Z", "to": f"{end}T00:00:00Z"}

    found: list[tuple[str, str, list[tuple[str, float]]]] = []
    for sub_id, name in subscriptions:
        status, out = _cost_query_with_retry(
            AZURE_COST_URL.format(sub=sub_id), json.dumps(body), token
        )
        if status != 200:
            print(f"    {name}: 비용 조회 실패 — {_why(out)}")
            if status == 429 or "429" in out:
                print(f"      {AZURE_429_HINT}")
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


def _export_query(table_id: str) -> str:
    """The command a reader can paste. Run against the live export 2026-09-01.

    Three things were wrong with the one printed before, and none could be caught by
    reading it: the colon form is invalid standard SQL, the missing `--project_id`
    ran it in whatever project `bq` defaulted to, and summing `cost` alone reports
    pre-credit usage — the exact trap `GCP_BILLING_EXPORT_SETUP.md` §4 warns about,
    printed by the tool that points at that document. `credits` is negative, so the
    two columns are what you owe and what was taken off, side by side.
    """
    ref = _sql_ref(table_id)
    return (
        f"bq query --use_legacy_sql=false --project_id={_project_of(table_id)} "
        f"'SELECT service.description AS service, ROUND(SUM(cost),2) AS cost,"
        f" ROUND(SUM((SELECT IFNULL(SUM(c.amount),0) FROM UNNEST(credits) c)),2) AS credits"
        f" FROM `{ref}` GROUP BY 1 ORDER BY 2 DESC'"
    )


def _export_sql(table_id: str) -> str:
    """The amount query. Splits `PROMOTION` off from every other credit.

    `GCP_BILLING_EXPORT_SETUP.md` §4 warned that summing `cost` alone reports
    pre-credit usage, and that warning fired the first time anyone looked: measured
    2026-09-02, gross **₩67.87** against a bill of **≈₩0**, and **99.4%** of the
    offset was a single `FreeTrialUpgrade` credit of type `PROMOTION`.

    So subtracting all credits and printing one number would have been the same
    false zero this file exists to prevent, one layer along: a promotion is a
    *balance that runs out*, while `DISCOUNT`/`FREE_TIER` are properties of the
    rate. Collapsed into one column they read identically and the reader concludes
    "GCP is free" — which is true only until the balance is gone. They are reported
    in separate columns for that reason, and the row count and day range come back
    with them because the window was **three days** when this was written: multiply
    it by thirty and the assumption dominates the estimate rather than the measurement.

    Grouped by project because the billing account is not this repo: five projects
    are attached, three carry cost, and platform-agent's own share was **₩6.55 of
    ₩67.87**. A single total would overstate this repo's spend tenfold.
    """
    return (
        "SELECT project.id AS project, currency,"
        " ROUND(SUM(cost), 2) AS gross,"
        " ROUND(SUM((SELECT IFNULL(SUM(c.amount), 0) FROM UNNEST(credits) c"
        " WHERE c.type = 'PROMOTION')), 2) AS promo,"
        " ROUND(SUM((SELECT IFNULL(SUM(c.amount), 0) FROM UNNEST(credits) c"
        " WHERE IFNULL(c.type, '') != 'PROMOTION')), 2) AS other_credits,"
        " MIN(DATE(usage_start_time)) AS first_day,"
        " MAX(DATE(usage_start_time)) AS last_day, COUNT(*) AS rows_"
        f" FROM `{_sql_ref(table_id)}`"
        " GROUP BY project, currency ORDER BY gross DESC"
    )


def _export_spend(table_id: str) -> list[dict] | None:
    """Rows of the amount query, or None when it could not be run.

    None rather than an empty list, and never a zero: a query that fails is the
    `AccessDenied`-is-not-absence rule again, and the caller falls back to printing
    the command so a person can run it themselves.

    `--project_id` is passed because without it the query runs in — and bills —
    whatever project `bq` happens to default to, which on this machine was a
    *different* project of the same billing account (measured 2026-09-01).
    """
    code, out = _run("bq", "--project_id", _project_of(table_id), "--format=json",
                     "query", "--use_legacy_sql=false", _export_sql(table_id))
    if code != 0:
        return None
    try:
        rows = json.loads(out)
    except json.JSONDecodeError:
        return None
    return rows if isinstance(rows, list) else None


def _num(row: dict, key: str) -> float:
    """A numeric column of a `bq` JSON row. `bq` returns every value as a string."""
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _width(text: str) -> int:
    """Display columns of `text`. Hangul and CJK occupy two of them.

    `str.ljust` counts code points, so a column padded with it goes crooked the
    moment a project name or a label is not ASCII — which every label in this
    report is. A misaligned money table is not cosmetic: it is where a number gets
    read against the wrong heading.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    """`text` padded to `width` display columns."""
    return text + " " * max(0, width - _width(text))


def _zero_is_zero(value: float) -> float:
    """-0.00 is a rounding artefact, and it reads as a refund. Fold it to 0."""
    return 0.0 if abs(value) < 0.005 else value


def _usage_window(rows: list[dict]) -> tuple[str, str, int] | None:
    """First day, last day and row count of the rows that carry actual usage.

    Account-level rows (`project` is NULL — the invoice adjustment) are excluded,
    and that exclusion is the whole point. Measured 2026-09-02: the export held
    three days of usage (08-30 ~ 09-02) plus **one** invoice row dated 2026-08-01,
    and spanning every row put "2026-08-01 ~ 2026-09-02" on the screen — a month.
    The same single row made the per-`invoice.month` rollup look like August had
    been backfilled when nothing before 08-30 had. Printing that window would have
    reproduced, in the tool, the exact misreading this report warns the reader against.
    """
    usage = [r for r in rows if r.get("project")] or rows
    days = sorted(d for r in usage for d in (r.get("first_day"), r.get("last_day")) if d)
    if not days:
        return None
    return days[0], days[-1], sum(int(_num(r, "rows_")) for r in usage)


COLUMNS = (("총사용액", 13), ("PROMOTION", 15), ("기타크레딧", 15), ("청구", 14))


def _print_gcp_amounts(rows: list[dict], scanned: int | None) -> None:
    """Print the amount table, and the three things a reader would otherwise misread."""
    currency = next((r.get("currency") for r in rows if r.get("currency")), "")
    window = _usage_window(rows)
    if window:
        first, last, counted = window
        extra = len(rows) - len([r for r in rows if r.get("project")])
        note = f", 계정 수준 {extra}행 제외" if extra else ""
        print(f"    창 {first} ~ {last} ({counted}행{note}) — 이 창 밖은 실리지 않았다."
              " 곱해서 월액으로 읽지 말 것.")

    head = _pad(f"    프로젝트별 ({currency})".rstrip(), 36)
    print(head + "".join(label.rjust(w - _width(label) + len(label)) for label, w in COLUMNS))
    gross = promo = other = 0.0
    for row in rows:
        g, pr, ot = _num(row, "gross"), _num(row, "promo"), _num(row, "other_credits")
        gross, promo, other = gross + g, promo + pr, other + ot
        print(_pad("      " + (row.get("project") or "(계정 수준)"), 36)
              + f"{g:>13,.2f}{pr:>15,.2f}{ot:>15,.2f}{_zero_is_zero(g + pr + ot):>14,.2f}")
    print(_pad("      (합계)", 36)
          + f"{gross:>13,.2f}{promo:>15,.2f}{other:>15,.2f}"
            f"{_zero_is_zero(gross + promo + other):>14,.2f}")

    offset = promo + other
    if promo:
        share = abs(promo) / abs(offset) * 100 if offset else 100.0
        print(f"    주의: 청구액이 낮은 것은 요율이 아니다 — 상쇄의 {share:.1f}%가 PROMOTION"
              " 크레딧이고, 잔액이 마르면 총사용액이 그대로 청구된다.")
        print("    소진 시점은 이 내보내기가 말해 주지 않는다.")
    if len([r for r in rows if r.get("project")]) > 1:
        print("    주의: 이 결제 계정에는 다른 프로젝트도 붙어 있다 — 합계를 이 레포의"
              " 비용으로 읽지 말 것.")
    if scanned is not None:
        print(f"    이 질의는 테이블 전체 {scanned:,}바이트를 스캔한다"
              " (BigQuery 최소 과금 10MB · 무료 티어 1TB/월).")


def report_gcp() -> None:
    """GCP's answer is a state, not a number — printing nothing would read as ₩0."""
    print("GCP 실사용")
    status, detail = gcp_actual_spend()
    if status == "MEASURABLE":
        print(f"    잴 수 있다 — 결제 내보내기 테이블 {detail}")
        rows = _export_spend(detail)
        if rows is None:
            # A failed query is not ₩0. Hand the reader the command and say why
            # the number is missing, rather than printing one that is not there.
            print("    금액 질의가 실패했다 — 이것은 '₩0'이 아니다. 직접 물어볼 것:")
            print(f"    {_export_query(detail)}")
            return
        if not rows:
            print("    테이블에 행은 있는데 질의가 아무것도 돌려주지 않았다 —"
                  " 이것도 '₩0'이 아니다.")
            return
        _print_gcp_amounts(rows, _export_bytes(detail))
        return
    if status == "EXPORTED_EMPTY":
        print(f"    아직 답이 없다 — 내보내기 테이블 {detail} 는 있고 행이 0개다")
        print("    이것은 '₩0'이 아니다. 켠 것과 실린 것은 다르다 — 테이블은 토글 직후")
        print("    수십 분 안에 생기고 적재는 그 뒤에 따로 온다(09-01 실측: 01:53Z 생성,")
        print("    14:08Z에도 0행). 하루가 지나도 0행이면 그때부터가 문제다.")
        print(f"    {_export_query(detail)}")
        print("      docs/GCP_BILLING_EXPORT_SETUP.md §3   (판정 시점과 좁히는 순서)")
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
