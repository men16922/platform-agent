"""The two defaults that reported "$0" while $8.81 was accruing.

On 2026-08-09 an AWS budget alert ($8.50 threshold, $8.81 actual) arrived right
after the same account had been checked by hand twice and reported as spending
nothing. Neither check was careless in an obvious way; both used a default that
answers a *different, reassuring* question:

  1. **Cost Explorer includes credits.** `get-cost-and-usage` with no filter is
     net of credits, so a credited account reads as $0 regardless of consumption.
     Budgets exclude `Credit`/`Refund`, which is why the alert fired and the hand
     query did not. "What will be charged" and "what am I consuming" are different
     questions and only the second finds a forgotten resource.
  2. **`describe-instances` is one region.** The instance was in `us-east-1`; the
     configured default region was `us-west-2`.

`scripts/probe_cloud_spend.py` hard-codes the fix for both. These are the guards
that make removing either one go red, because a probe that quietly loses its filter
is worse than no probe: it carries the authority of a measurement.

The AWS guards are static assertions on purpose — that half talks to a live account,
so exercising it for real would need credentials and would make the gate
non-deterministic. What is falsifiable there is that the *right question* is baked
in, which is exactly what was wrong when it was asked by hand. The GCP guards below
are behavioural instead, with the CLI layer replaced: they still never touch the
network, but they can execute a branch (`MEASURABLE`) that no live run reaches today.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "scripts" / "probe_cloud_spend.py"


@pytest.fixture(scope="module")
def source() -> str:
    assert PROBE.is_file(), "the probe this file guards does not exist"
    return PROBE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def module(source):
    """The probe's constants, without importing it (import must not shell out)."""
    tree = ast.parse(source)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return consts


class TestCreditsAreExcluded:
    """Failure 1: the query answered "net of credits" and read as $0."""

    def test_the_filter_constant_excludes_credits_and_refunds(self, module):
        f = module.get("CREDIT_EXCLUDING_FILTER")
        assert f, "the probe no longer declares a credit-excluding filter"
        dims = f["Not"]["Dimensions"]
        assert dims["Key"] == "RECORD_TYPE"
        assert set(dims["Values"]) == {"Credit", "Refund"}, (
            "Budgets exclude exactly these two; dropping either re-opens the gap"
        )

    def test_the_cost_call_actually_passes_it(self, source):
        """Declaring the constant is not using it — that gap is how this returns."""
        assert "--filter" in source
        assert "json.dumps(CREDIT_EXCLUDING_FILTER)" in source, (
            "the filter must reach the CLI call, not just sit in a constant"
        )

    def test_the_filter_is_valid_json_for_the_cli(self, module):
        json.loads(json.dumps(module["CREDIT_EXCLUDING_FILTER"]))


class TestEveryRegionIsSwept:
    """Failure 2: one region was checked and the instance was in another."""

    def test_regions_are_enumerated_rather_than_assumed(self, source):
        assert "describe-regions" in source, (
            "a hard-coded region list goes stale; ask the account which regions exist"
        )

    def test_the_instance_query_is_run_per_region(self, source):
        assert '"--region", region' in source, (
            "describe-instances without --region uses one configured region — the bug"
        )

    def test_only_running_instances_are_reported(self, source):
        assert "Name=instance-state-name,Values=running" in source


class TestTheProbeCannotChangeAnything:
    """A cost probe that can also stop things turns a report into an action."""

    FORBIDDEN = (
        "stop-instances", "terminate-instances", "delete-", "modify-",
        "create-", "put-", "stop_instances", "terminate_instances",
    )

    def test_no_mutating_verb_appears(self, source):
        body = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        # The module docstring names what it must NOT do; strip it before scanning.
        body = body.split('"""', 2)[-1]
        hits = [v for v in self.FORBIDDEN if v in body]
        assert not hits, f"the probe gained a mutating call: {hits}"

    def test_it_says_so_to_whoever_runs_it(self, source):
        assert "중지·종료하지 않는다" in source, (
            "the output must state that acting is a human decision"
        )


class TestTheCostOfMeasuringIsWrittenDown:
    """Read-only is not free, and this repo found that out by looking.

    Cost Explorer bills $0.01 per request. Measured 2026-08-10: 24 calls put $0.24
    on the bill under `APS$USE`, and `spend-watch` once a day comes to ~$0.30/month
    — a recurring charge created by the tool whose subject is forgotten recurring
    charges. It was in no document.

    These are source assertions and can only prove the sentence is still there,
    not that the number is still right; the number is a live measurement and
    nothing in a gate can re-take it. What they do prevent is the specific way this
    fact would disappear — someone tidying a long docstring.
    """

    def test_the_probe_states_the_per_request_price(self, source):
        assert "$0.01 per request" in source, (
            "the probe stopped saying that calling it costs money"
        )

    def test_the_probe_warns_that_today_is_reported_late(self, source):
        """Both halves: the claim, and what to do about it.

        The first draft of this guard asked only for the claim, and a mutation that
        deleted the instruction survived — a warning that says a number is wrong
        without saying which number to read instead is half a warning, and the half
        it drops is the one a reader acts on.
        """
        flat = " ".join(source.split())
        assert "not a measured zero" in flat, (
            "a 0 on today's row is an unfilled row, not a measurement — the probe "
            "stopped warning about the one way its own output misleads"
        )
        assert "Read the trailing days, not the last one" in flat, (
            "the warning kept the claim and lost the instruction"
        )

    def test_the_daily_watcher_states_its_monthly_cost(self):
        watcher = (REPO / "scripts" / "watch_cloud_spend.py").read_text(encoding="utf-8")
        assert "$0.30/month" in watcher, (
            "the thing that actually runs daily stopped naming what daily costs"
        )


class TestUnmeasuredIsNotZero:
    """The failure being guarded is a false zero, so silence must not read as zero."""

    def test_a_failed_lookup_returns_none_not_zero(self, source):
        assert "return None" in source

    @pytest.mark.parametrize("subject", ["'$0'이", "'0대'가"])
    def test_the_words_it_says_instead_of_a_number(self, probe, capsys, subject):
        """Asserted on the rendered line rather than on the source text: the wording
        is now assembled, and grepping the file would pass on a string that no run
        ever prints."""
        probe._unmeasured(subject)
        assert f"이것은 {subject} 아니다" in capsys.readouterr().out

    def test_it_exits_nonzero_when_it_could_not_look(self, source):
        assert "return 2" in source, (
            "exit 0 on an unmeasured account is the same false reassurance"
        )

    def test_zero_spend_is_still_exit_zero(self, source):
        """Measured-and-zero is a result; conflating it with 'could not look' would
        make the probe cry wolf on a genuinely idle account."""
        assert "spend may be zero — that is a result, not a failure" in source


class TestTheWindowIsRight:
    def test_end_is_exclusive_and_covers_today(self, source):
        """Cost Explorer's End is exclusive; end=today silently drops today."""
        assert "timedelta(days=1)" in source
        assert "end exclusive" in source or "exclusive" in source


# ---------------------------------------------------------------------------
# GCP: the same false zero, one provider over.
#
# The AWS half above was written after "$0" was reported twice for an account that
# was spending. GCP was then left out of this probe entirely — and on a four-provider
# platform an omitted provider reads exactly like a measured zero. It is worse here,
# because GCP genuinely cannot be measured today: Cloud Billing v1 has no method
# that reads spend (19 methods, checked against the live discovery document on
# 2026-08-09) and the Budgets API returns the amount you configured. So the probe
# cannot print a number and must print the *state* instead.
#
# These are behavioural rather than static: the branch that says "not measurable"
# is the one running today, so the branch that says "measurable" would otherwise
# never be executed by anything, and an unexercised branch carries no weight.
# `_run` is replaced, so nothing here shells out.
# ---------------------------------------------------------------------------

EXPORT_TABLE = "gcp_billing_export_v1_010556_A2B7AE_292490"


@pytest.fixture(scope="module")
def probe():
    spec = importlib.util.spec_from_file_location("probe_cloud_spend", PROBE)
    assert spec and spec.loader, "the probe this file guards is not importable"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # import alone must not shell out
    return mod


def fake_run(datasets=(), tables=(), projects=("p1",), gcloud_ok=True, rows=None):
    """A stand-in for every CLI the GCP half calls; returns (runner, calls-it-made).

    `rows` is the row count `bq show` reports, per fully-qualified table id, or a
    single int for every table. `None` means the metadata call fails — which is not
    the same as reporting zero, and the probe must not read it as such.
    """
    calls: list[tuple[str, ...]] = []

    def _run(*args: str) -> tuple[int, str]:
        calls.append(args)
        if args[0] == "gcloud":
            return (0, "\n".join(projects)) if gcloud_ok else (1, "API not enabled")
        if "show" in args:                # table metadata for `project:dataset.table`
            if rows is None:
                return 1, "Not found"
            count = rows if isinstance(rows, int) else rows.get(args[-1])
            if count is None:
                return 1, "Not found"
            return 0, json.dumps({"numRows": str(count)})
        if args[-1] == "ls":              # dataset listing for a project
            return 0, json.dumps(
                [{"datasetReference": {"datasetId": d}} for d in datasets]
            )
        # table listing for `project:dataset` — an empty dataset prints nothing,
        # not `[]`, which is the shape the live account is actually in.
        if not tables:
            return 0, ""
        return 0, json.dumps([{"tableReference": {"tableId": t}} for t in tables])

    return _run, calls


class TestGcpIsNotSilentlyOmitted:
    def test_the_probe_reports_gcp_at_all(self, source):
        assert "GCP 실사용" in source, (
            "a provider missing from the report is indistinguishable from a zero"
        )

    def test_gcp_is_reached_even_when_aws_could_not_be_measured(self, source):
        """The early `return 2` used to sit above everything else, so a broken AWS
        lookup deleted GCP from the output entirely."""
        body = source.split("def main(")[-1]
        assert body.index("report_gcp()") < body.index("return 2"), (
            "report_gcp must run before main can bail out on an AWS failure"
        )


class TestUnmeasurableIsSaidOutLoud:
    def test_a_missing_export_names_itself_and_refuses_to_imply_zero(self, probe, monkeypatch, capsys):
        runner, _ = fake_run(datasets=["billing_export"])
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        status, _ = probe.gcp_actual_spend()
        assert status == "NOT_EXPORTED"
        probe.report_gcp()
        out = capsys.readouterr().out
        assert "아직 못 잰다" in out
        assert "'₩0'이 아니다" in out, "the whole point is that absence is not zero"
        assert "결제 내보내기" in out, "say which console toggle would fix it"

    def test_an_empty_dataset_is_not_an_export(self, probe, monkeypatch):
        """`bq ls` on an empty dataset prints nothing at all rather than `[]` — parsing
        that as JSON raises, and treating the raise as 'found' would be a false green."""
        runner, _ = fake_run(datasets=["billing_export"], tables=())
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        assert probe.gcp_actual_spend()[0] == "NOT_EXPORTED"

    def test_missing_tooling_is_not_the_same_answer_as_missing_export(self, probe, monkeypatch):
        """"gcloud cannot look" and "the export is off" need different fixes."""
        runner, _ = fake_run(gcloud_ok=False)
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        assert probe.gcp_actual_spend()[0] == "NO_TOOLING"

    def test_the_procedure_it_points_at_exists(self, probe, monkeypatch, capsys):
        """The probe tells the reader where the console steps are. A pointer to a
        renamed or deleted file is worse than no pointer: it reads as authoritative
        while sending someone nowhere, and nothing else in the repo would catch it."""
        runner, _ = fake_run(datasets=["billing_export"])
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        probe.report_gcp()
        referenced = [
            word.strip(".,()")
            for word in capsys.readouterr().out.split()
            if word.strip(".,()").startswith("docs/") and word.endswith(".md")
        ]
        assert referenced, "the probe stopped naming where the procedure is"
        for path in referenced:
            assert (REPO / path).is_file(), f"the probe points at a file that is gone: {path}"

    def test_a_missing_export_does_not_turn_the_probe_red(self, probe, source, monkeypatch):
        """A known gap is not a failed lookup. A probe that exits nonzero on every
        run trains people to skip it — the same way the ₩20 budget that fired every
        month trained everyone to ignore it."""
        runner, _ = fake_run(datasets=["billing_export"])
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        assert probe.report_gcp() is None
        assert "unmeasured = True" not in source.split("report_gcp()")[-1]


# ---------------------------------------------------------------------------
# Azure: the same false zero a third time, and this one is the cleanest sample.
#
# Azure *does* expose actual spend — unlike GCP — so the failure here is not
# "unmeasurable", it is "measured with the wrong call". On 2026-08-09
# `az consumption usage list` returned 28 rows for 08-01~08-09 with `pretaxCost`
# null in every single one; summing them gives exactly 0.0. Cost Management,
# asked about the identical window, said ₩1,989.33. Anyone reaching for the
# obviously-named command gets a confident zero for a subscription that spent
# ₩22,630 the month before.
# ---------------------------------------------------------------------------

WINDOW = ("2026-08-01", "2026-08-10")


TOKEN = "tok-do-not-leak"


class FakeAzure:
    """Both halves of the Azure transport: the `az` CLI and the `curl` that queries.

    They are two functions in the probe because the token has to be minted by `az`
    and the query has to keep its response headers, which `az rest` discards. Faking
    them together keeps one object answering "what did the probe actually do".

    `fail` is "account", "token" or "cost". `throttles` is how many 429s arrive before
    the real answer, each carrying `retry_after` — and `retry_after=None` is the case
    where the server throttled without saying how long, which the probe must not fill
    in with a guess.
    """

    def __init__(self, subs, rows, fail, error, throttles, retry_after, standard_retry_after):
        self.subs, self.rows, self.fail, self.error = subs, rows, fail, error
        self.throttles, self.retry_after = throttles, retry_after
        self.standard_retry_after = standard_retry_after
        self.calls: list[tuple[str, ...]] = []
        self.configs: list[str] = []
        self.waited: list[float] = []

    def run(self, *args: str) -> tuple[int, str]:
        self.calls.append(args)
        if args[:3] == ("az", "account", "list"):
            if self.fail == "account":
                return 1, self.error
            return 0, json.dumps([{"id": i, "name": n} for i, n in self.subs])
        if args[:3] == ("az", "account", "get-access-token"):
            if self.fail == "token":
                return 1, self.error
            return 0, json.dumps({"accessToken": TOKEN})
        return 127, f"unexpected call: {args}"

    def curl(self, *args: str, config: str = "") -> tuple[int, str]:
        # argv0 is added back because the probe's `_curl` prepends it, and the guards
        # below tell an az call from a curl one by looking at the whole command line.
        self.calls.append(("curl", *args))
        self.configs.append(config)
        if self.fail == "cost":
            return 0, _http(500, {}, self.error)
        if self.throttles > 0:
            self.throttles -= 1
            headers = {}
            if self.retry_after is not None:
                headers["clienttype-retry-after"] = self.retry_after
            if self.standard_retry_after is not None:
                headers["retry-after"] = self.standard_retry_after
            return 0, _http(429, headers, '{"error":{"code":"429","message":"Please retry."}}')
        payload = json.dumps(
            {"properties": {"rows": [[amt, svc, "KRW"] for svc, amt in self.rows]}}
        )
        return 0, _http(200, {}, payload)

    def sleep(self, seconds: float) -> None:
        self.waited.append(seconds)

    @property
    def posts(self) -> list[tuple[str, ...]]:
        return [c for c in self.calls if c and c[0] == "curl"]


def _http(status: int, headers: dict, body: str) -> str:
    """What `curl -D -` hands back: header block, blank line, body."""
    reason = {200: "OK", 429: "Too Many Requests", 500: "Internal Server Error"}[status]
    lines = [f"HTTP/1.1 {status} {reason}", "content-type: application/json"]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    return "\r\n".join(lines) + "\r\n\r\n" + body


def fake_az(probe, monkeypatch, subs=(("sub-1", "one"),),
            rows=(("Container Registry", 1989.33),), fail: str | None = None,
            error: str = "boom", throttles: int = 0,
            retry_after: str | None = "40", standard_retry_after: str | None = None):
    """Wires the fake transport into the probe and hands back the recorder.

    `_sleep` is replaced too: the point of this feature is *how long* it waits, and a
    guard that proves that by waiting 40 seconds is a guard people delete.
    """
    az = FakeAzure(subs, rows, fail, error, throttles, retry_after, standard_retry_after)
    monkeypatch.setattr(probe, "_run", az.run)
    monkeypatch.setattr(probe, "_curl", az.curl)
    monkeypatch.setattr(probe, "_sleep", az.sleep)
    return az


class TestAzureAsksTheRightCall:
    def test_the_command_that_returns_a_false_zero_is_never_used(self, probe, monkeypatch):
        """`az consumption usage list` succeeds, returns rows, and has no cost in
        them. Using it would be indistinguishable from a working probe."""
        az = fake_az(probe, monkeypatch)
        probe.azure_spend(*WINDOW)
        assert not any("consumption" in part for c in az.calls for part in c), (
            "the probe reached for the CLI whose pretaxCost is null on every row"
        )

    def test_it_asks_for_actual_cost(self, module):
        q = module.get("AZURE_COST_QUERY")
        assert q, "the probe no longer declares what it asks Cost Management"
        assert q["type"] == "ActualCost"
        assert q["dataset"]["aggregation"]["totalCost"]["function"] == "Sum"
        assert q["dataset"]["grouping"][0]["name"] == "ServiceName"

    def test_the_window_is_sent_explicitly(self, probe, monkeypatch):
        """`TheLastMonth` is rejected by this API ("currently not supported"), so a
        named timeframe would fail at exactly the moment someone asked for history."""
        az = fake_az(probe, monkeypatch)
        probe.azure_spend(*WINDOW)
        bodies = [json.loads(c[c.index("--data") + 1]) for c in az.posts if "--data" in c]
        assert bodies, "no query was sent"
        assert bodies[0]["timeframe"] == "Custom"
        assert bodies[0]["timePeriod"]["from"].startswith(WINDOW[0])
        assert bodies[0]["timePeriod"]["to"].startswith(WINDOW[1])

    def test_only_the_cost_query_endpoint_is_posted_to(self, probe, monkeypatch):
        """This probe promises to change nothing, and it issues a POST. That is fine
        for a query endpoint and not fine for anything else, so pin the URL.

        Moved onto the curl transport with the retry work: the assertion used to read
        `az rest --url`, which no longer exists, and a guard that matches nothing
        passes forever. Hence the count check — vacuous is the failure mode here.
        """
        az = fake_az(probe, monkeypatch)
        probe.azure_spend(*WINDOW)
        posted = [c for c in az.posts if "POST" in c]
        assert posted, "no POST was seen at all — this guard was watching nothing"
        for call in posted:
            url = call[call.index("--url") + 1]
            assert "/Microsoft.CostManagement/query?" in url, f"unexpected POST: {url}"

    def test_the_transport_keeps_the_response_headers(self, probe, monkeypatch):
        """Without the header dump there is no interval to wait, and the retry below
        silently degrades into the fixed-interval guess it exists to replace."""
        az = fake_az(probe, monkeypatch)
        probe.azure_spend(*WINDOW)
        assert all("-D" in c and c[c.index("-D") + 1] == "-" for c in az.posts)

    def test_the_bearer_token_never_lands_in_argv(self, probe, monkeypatch):
        """`ps` is readable by every process on the machine. The token goes to curl
        on stdin (`--config -`); the URL stays in argv because the guard above pins it."""
        az = fake_az(probe, monkeypatch)
        probe.azure_spend(*WINDOW)
        assert not any(TOKEN in part for c in az.calls for part in c), (
            "the access token was passed as a command-line argument"
        )
        assert any(TOKEN in cfg for cfg in az.configs), "the token never reached curl"


class TestAzureSweepsAndFailsLoudly:
    def test_every_subscription_is_swept(self, probe, monkeypatch):
        az = fake_az(probe, monkeypatch, subs=(("sub-1", "one"), ("sub-2", "two")))
        result = probe.azure_spend(*WINDOW)
        assert [name for name, _, _ in result] == ["one", "two"]
        queried = {c[c.index("--url") + 1] for c in az.posts if "--url" in c}
        assert len(queried) == 2, "a subscription never queried cannot be ruled out"

    @pytest.mark.parametrize("broken", ["account", "token", "cost"])
    def test_a_failed_lookup_is_none_not_an_empty_report(self, probe, monkeypatch, broken):
        """Returning [] here would print a clean, totally empty Azure section — the
        false zero wearing a different hat. "token" is new with the curl transport:
        minting the token is a step that can fail on its own now."""
        fake_az(probe, monkeypatch, fail=broken)
        assert probe.azure_spend(*WINDOW) is None

    def test_an_unmeasured_azure_makes_the_probe_exit_nonzero(self, probe, source, monkeypatch):
        """Unlike GCP, Azure spend *is* knowable — so failing to read it is a failed
        lookup, not a known gap, and must be treated like the AWS failure."""
        fake_az(probe, monkeypatch, fail="account")
        assert probe.report_azure(*WINDOW) is False
        assert "if not report_azure(start, end):\n        unmeasured = True" in source

    def test_the_reason_for_a_failure_reaches_the_reader(self, probe, monkeypatch, capsys):
        """Cost Management answers 429 "Too many requests" when asked a few times in
        a row — hit live on 2026-08-09. That is transient and the fix is to wait a
        minute, but a bare "could not measure" makes it look like a broken credential
        and sends someone off checking logins instead."""
        fake_az(probe, monkeypatch, fail="cost")
        probe.report_azure(*WINDOW)
        captured = capsys.readouterr()
        assert "boom" in captured.out, (
            "the failure was reported without saying what went wrong — and it has to "
            "land in the report itself, not beside it (see TestTheReportIsOneStream)"
        )

    def test_currency_is_carried_not_assumed(self, probe, monkeypatch, capsys):
        """The AWS half prints dollars; this subscription bills in KRW. Printing a
        bare number, or a $, would silently mix two units in one report."""
        fake_az(probe, monkeypatch)
        probe.report_azure(*WINDOW)
        out = capsys.readouterr().out
        assert "KRW" in out and "$" not in out


class TestTheExportIsFoundWhereverItIs:
    def test_it_is_identified_by_table_name_not_dataset_name(self, probe, monkeypatch):
        """The console lets you point the export at any dataset, so keying off the
        dataset name would miss a real export that happens to be called something else."""
        runner, _ = fake_run(datasets=["anything_at_all"], tables=[EXPORT_TABLE])
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        status, detail = probe.gcp_actual_spend()
        assert status == "MEASURABLE"
        assert detail == f"p1:anything_at_all.{EXPORT_TABLE}"

    def test_every_project_is_swept_rather_than_the_configured_one(self, probe, monkeypatch):
        """Same failure as the single-region EC2 query: the thing was not where the
        active configuration pointed."""
        runner, calls = fake_run(datasets=["d"], tables=(), projects=("p1", "p2"))
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        assert probe.gcp_actual_spend()[0] == "NOT_EXPORTED"
        assert any(c[0] == "gcloud" and "projects" in c for c in calls), (
            "the project list must be asked for, not assumed from gcloud config"
        )
        looked_at = {c[2] for c in calls if c[0] == "bq" and c[1] == "--project_id"}
        assert looked_at == {"p1", "p2"}, (
            "a project that was never listed cannot be ruled out — reporting "
            f"'no export anywhere' after looking at {looked_at} is the false zero again"
        )

    def test_a_pinned_location_skips_the_sweep(self, probe, monkeypatch):
        runner, calls = fake_run(tables=[EXPORT_TABLE])
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.setenv(probe.GCP_EXPORT_ENV, "proj:ds")
        assert probe.gcp_actual_spend() == ("MEASURABLE", f"proj:ds.{EXPORT_TABLE}")
        assert not any(c[0] == "gcloud" for c in calls)


# ---------------------------------------------------------------------------
# The reporter made the report's own mistake.
#
# Every guard above checks that the probe *says* the right thing. None of them
# checked what a reader *receives*, and those came apart on 2026-08-10: the
# "could not measure" lines went to stderr while the headings went to stdout. On a
# terminal that reads correctly, because stdout is line-buffered — which is how it
# was written and why nobody saw it. Through a pipe stdout is block-buffered, so
# every warning is flushed first and the reader gets three warnings at the top
# followed by `AWS 실사용`, `도는 EC2 인스턴스` and `Azure 실사용` **all empty**.
# An empty section under a heading reads as zero. That is the single failure this
# whole file exists to prevent, committed by the thing preventing it.
#
# It survived because `capsys` hands back `.out` and `.err` as separate strings, so
# a test that asserts on `.err` cannot see that the reader's copy came apart. These
# guards assert on the stream the reader actually reads.
# ---------------------------------------------------------------------------

SECTION_HEADINGS = ("AWS 실사용", "도는 EC2 인스턴스", "Azure 실사용", "GCP 실사용")


def _sections(out: str) -> dict[str, list[str]]:
    """Split the report at its headings, keeping each section's non-blank body."""
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in out.splitlines():
        heading = next((h for h in SECTION_HEADINGS if line.startswith(h)), None)
        if heading:
            current = heading
            found[heading] = []
        elif current and line.strip() and not line.startswith("주의:"):
            found[current].append(line.strip())
    return found


class TestTheReportIsOneStream:
    @pytest.fixture
    def blind_run(self, probe, monkeypatch, capsys):
        """Every CLI fails — the state in which an empty section is most dangerous."""
        monkeypatch.setattr(probe, "_aws", lambda *a: (1, "boom: aws unavailable"))
        monkeypatch.setattr(probe, "_run", lambda *a: (1, "boom: cli unavailable"))
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        monkeypatch.setattr("sys.argv", ["probe_cloud_spend.py"])
        code = probe.main()
        return code, capsys.readouterr()

    def test_no_section_is_empty_when_nothing_could_be_measured(self, blind_run):
        _, captured = blind_run
        sections = _sections(captured.out)
        assert set(sections) == set(SECTION_HEADINGS), (
            f"a heading vanished from the report: {sorted(sections)}"
        )
        empty = [h for h, body in sections.items() if not body]
        assert not empty, (
            f"{empty} printed a heading and then nothing. A blank section under "
            "'Azure 실사용' is read as ₩0 — the exact false zero this probe exists "
            "to stop."
        )

    def test_every_section_says_it_could_not_look(self, blind_run):
        _, captured = blind_run
        sections = _sections(captured.out)
        for heading in ("AWS 실사용", "도는 EC2 인스턴스", "Azure 실사용"):
            body = " ".join(sections[heading])
            assert "측정하지 못했다" in body, (
                f"{heading} did not say it failed, in its own section"
            )
            assert "boom" in body, f"{heading} did not say *why* it failed"
        # GCP is a known gap rather than a failed lookup (D44), so it says so
        # differently — but it must still not be blank.
        assert "이것은 '₩0'이 아니다" in " ".join(sections["GCP 실사용"])

    def test_the_reader_needs_nothing_from_the_other_stream(self, blind_run):
        """Whoever reads this pipes it, tees it, or captures it into an evidence log.
        Anything only on stderr is out of order at best and dropped at worst."""
        _, captured = blind_run
        assert captured.err == "", (
            f"the report is split across two streams again: {captured.err!r}"
        )

    def test_it_still_exits_two(self, blind_run):
        """Saying it on stdout does not make it a success."""
        code, _ = blind_run
        assert code == 2


class TestTheTableIsNotTheAnswer:
    """A materialised export table and a loaded one are different states.

    Measured live on 2026-09-01: the console toggle was saved at 01:11Z, BigQuery
    created the table at 01:53Z, and at 14:08Z — thirteen hours later, with the
    table still being touched — it held zero rows. The probe said "잴 수 있다" the
    whole time. That is this file's own thesis (an empty section reads as a zero)
    reappearing one level up: an empty *table* was reading as a measurement.
    """

    def test_an_empty_export_is_not_measurable(self, probe, monkeypatch):
        runner, _ = fake_run(
            datasets=["billing_export"],
            tables=["gcp_billing_export_v1_010556_A2B7AE_292490"],
            rows=0,
        )
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        status, detail = probe.gcp_actual_spend()
        assert status == "EXPORTED_EMPTY", (
            "a table with no rows cannot answer 'how much', so it is not MEASURABLE"
        )
        assert detail.endswith("gcp_billing_export_v1_010556_A2B7AE_292490"), (
            "name the table anyway — the next check is against that exact one"
        )

    def test_a_loaded_export_is_measurable(self, probe, monkeypatch):
        runner, _ = fake_run(
            datasets=["billing_export"],
            tables=["gcp_billing_export_v1_010556_A2B7AE_292490"],
            rows=42,
        )
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        assert probe.gcp_actual_spend()[0] == "MEASURABLE"

    def test_empty_is_neither_of_the_two_states_it_would_have_been_folded_into(self, probe):
        """The two wrong homes for this state send a reader to the wrong place:
        MEASURABLE promises an answer that is not there, NOT_EXPORTED sends them
        back to a console toggle that is already set correctly."""
        assert "EXPORTED_EMPTY" not in ("MEASURABLE", "NOT_EXPORTED")
        source = PROBE.read_text(encoding="utf-8")
        branch = source.split('if status == "EXPORTED_EMPTY":')[-1].split("return")[0]
        assert "'₩0'이 아니다" in branch, "an empty table must not read as zero spend"
        assert "§3" in branch, "point at the section that says when 0 rows becomes a problem"

    def test_unreadable_metadata_is_not_read_as_empty(self, probe, monkeypatch):
        """`bq show` failing is the same shape as `AccessDenied` and a region-scoped
        `[]`: it is a failure to look, not evidence of absence. Reading it as zero
        rows would demote a working export on nothing more than a permissions error."""
        runner, _ = fake_run(
            datasets=["billing_export"],
            tables=["gcp_billing_export_v1_010556_A2B7AE_292490"],
            rows=None,
        )
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        assert probe.gcp_actual_spend()[0] == "MEASURABLE"

    def test_an_empty_table_does_not_stop_the_sweep(self, probe, monkeypatch):
        """The sweep exists because the export is not where it was configured to be.
        Returning the first *empty* table it trips over would reintroduce exactly the
        single-place assumption the sweep was written to remove."""
        table = "gcp_billing_export_v1_010556_A2B7AE_292490"
        runner, _ = fake_run(
            datasets=["empty_ds", "real_ds"],
            tables=[table],
            projects=["p1"],
            rows={f"p1:empty_ds.{table}": 0, f"p1:real_ds.{table}": 7},
        )
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        status, detail = probe.gcp_actual_spend()
        assert (status, detail) == ("MEASURABLE", f"p1:real_ds.{table}"), (
            "a loaded table further along the sweep is the better answer"
        )

    def test_counting_rows_costs_nothing(self, probe, monkeypatch):
        """This account learned the hard way that observation becomes the bill —
        Cost Explorer is 84% of AWS spend here. `bq show` reads metadata and scans no
        bytes; `bq query` would scan the table on every single run of the probe."""
        runner, calls = fake_run(
            datasets=["billing_export"],
            tables=["gcp_billing_export_v1_010556_A2B7AE_292490"],
            rows=5,
        )
        monkeypatch.setattr(probe, "_run", runner)
        monkeypatch.delenv(probe.GCP_EXPORT_ENV, raising=False)
        probe.gcp_actual_spend()
        assert not any("query" in call for call in calls), (
            "the probe must never run a billable query to decide whether it can measure"
        )
        assert any("show" in call for call in calls), "row count must actually be asked for"


class TestThePrintedCommandRuns:
    """The MEASURABLE branch printed a command that could not have worked.

    It went unnoticed because the branch needs a live export and there was none
    until 2026-09-01 — a printed instruction is a claim, and this one was never
    executed until the day it first could be. All three faults were invisible to
    reading and obvious to running; the corrected form was run against the live
    export before being written here (exit 0).
    """

    @pytest.fixture
    def printed(self, probe):
        return probe._export_query(
            "project-ec7809f7-0fb5-45d4-b6d:billing_export."
            "gcp_billing_export_v1_010556_A2B7AE_292490"
        )

    def test_the_table_is_dotted_not_coloned(self, printed):
        """Standard SQL: "Project name needs to be separated by dot from dataset
        name, not by colon" — the command failed before touching a row."""
        table_ref = printed.split("FROM `")[1].split("`")[0]
        assert ":" not in table_ref, "the colon form is rejected by standard SQL"
        assert table_ref.count(".") >= 2, "project.dataset.table"

    def test_the_query_names_the_project_it_must_run_in(self, printed):
        """Without it the job runs and bills in whatever `bq` defaults to — on this
        machine a *different* project of the same billing account."""
        assert "--project_id=project-ec7809f7-0fb5-45d4-b6d" in printed

    def test_credits_are_not_silently_dropped(self, printed):
        """Summing `cost` alone is pre-credit usage, which is the trap
        GCP_BILLING_EXPORT_SETUP.md §4 spells out — printed by the very tool that
        points the reader at that document. It is the AWS credit trap mirrored."""
        assert "credits" in printed, "the reader must see what was taken off, not just gross"
        assert "UNNEST(credits)" in printed, "credits is a repeated field; it has to be flattened"

    def test_both_states_that_name_a_table_print_the_same_runnable_command(self, probe):
        """Two copies of a command is how one of them stays broken."""
        source = PROBE.read_text(encoding="utf-8")
        report = source.split("def report_gcp(")[1]
        assert report.count("bq query") == 0, (
            "the command must come from _export_query, not be spelled out again"
        )
        assert report.count("_export_query(") == 2, (
            "MEASURABLE and EXPORTED_EMPTY both name a table, so both print how to ask it"
        )


class TestAzure429SaysHowLongToWait:
    """The recorded conclusion was backwards, and measurement turned it over.

    2026-08-30 recorded "retrying was the answer"; 2026-09-01 recorded "retrying was
    not the answer this time" after three tries 20 seconds apart. Asking with the
    headers visible showed why: the exhausted bucket was `clienttype-requests`
    (DefaultQuota:0) while entity, tenant and QPU all had room, and the server named
    its own interval — 5s, then 40s. Waiting the 40 returned 200. Retrying was the
    answer both times; the interval was never read because `az rest` hides headers.
    """

    def test_a_429_tells_the_reader_the_wait_is_knowable(self, probe, monkeypatch, capsys):
        fake_az(probe, monkeypatch, throttles=99)
        probe.report_azure("2026-09-01", "2026-09-02")
        out = capsys.readouterr().out
        assert "clienttype-retry-after" in out, (
            "name the header that carries the number, since az rest will not show it"
        )
        assert "측정하지 못했다" in out, "a throttled read is still not a zero"

    def test_a_non_throttle_failure_does_not_get_the_throttle_advice(self, probe, monkeypatch, capsys):
        """Advice printed under every failure teaches readers to skip it, and would
        send someone chasing a rate limit when the credential is what broke."""
        fake_az(probe, monkeypatch, fail="cost",
                error="ERROR: AADSTS700082: refresh token has expired")
        probe.report_azure("2026-09-01", "2026-09-02")
        out = capsys.readouterr().out
        assert "clienttype-retry-after" not in out

    def test_the_hint_forbids_the_interval_that_failed(self, probe):
        """A fixed short interval is indistinguishable from a permanent failure, and
        that is exactly how it was misread."""
        assert "고정 간격" in probe.AZURE_429_HINT


class TestAzure429IsWaitedOutNotGuessed:
    """The interval comes from the server or the probe does not retry at all.

    Naming the header in a hint left the waiting to whoever read the report, and the
    report is read the next morning. These drive the probe doing it itself — the only
    part that stays a human's is the case where the server never named an interval,
    because that is where a number would have to be invented.
    """

    def test_it_waits_exactly_what_the_server_asked_and_then_succeeds(self, probe, monkeypatch):
        az = fake_az(probe, monkeypatch, throttles=1, retry_after="40")
        result = probe.azure_spend(*WINDOW)
        assert result is not None, "a throttle the server told us to wait out is not a failure"
        assert az.waited == [40.0], f"waited {az.waited} instead of the 40s asked for"
        assert len(az.posts) == 2

    def test_the_bucket_specific_header_wins_over_the_standard_one(self, probe, monkeypatch):
        """Measured 2026-09-01: `clienttype-requests` was the exhausted bucket
        (DefaultQuota:0) while entity, tenant and QPU had room. Taking the shorter,
        standard header would retry early and read back as a permanent failure."""
        az = fake_az(probe, monkeypatch, throttles=1, retry_after="40",
                     standard_retry_after="5")
        probe.azure_spend(*WINDOW)
        assert az.waited == [40.0]

    def test_a_429_with_no_interval_is_not_retried_on_a_guessed_one(self, probe, monkeypatch):
        """The whole correction: a fixed interval below what the server wants is
        indistinguishable from a permanent failure. No header, no retry."""
        az = fake_az(probe, monkeypatch, throttles=99, retry_after=None)
        assert probe.azure_spend(*WINDOW) is None
        assert az.waited == []
        assert len(az.posts) == 1, "retried on an interval nobody asked for"

    def test_it_gives_up_after_the_declared_number_of_retries(self, probe, monkeypatch):
        """Bounded, because an unattended probe that waits forever is a probe nobody
        runs. The count is the constant, not a literal, so the two cannot drift."""
        az = fake_az(probe, monkeypatch, throttles=99, retry_after="40")
        assert probe.azure_spend(*WINDOW) is None
        assert len(az.posts) == probe.AZURE_MAX_RETRIES + 1
        assert az.waited == [40.0] * probe.AZURE_MAX_RETRIES

    def test_an_absurd_interval_is_clamped(self, probe, monkeypatch):
        """A header is input. `retry-after: 86400` would hang the probe for a day."""
        az = fake_az(probe, monkeypatch, throttles=1, retry_after="86400")
        probe.azure_spend(*WINDOW)
        assert az.waited == [probe.AZURE_MAX_WAIT_SECONDS]

    def test_an_unparseable_interval_is_not_a_zero_second_wait(self, probe, monkeypatch):
        """HTTP allows `Retry-After` as a date. Reading that as 0 would turn this into
        a tight retry loop against a server that is already throttling."""
        az = fake_az(probe, monkeypatch, throttles=99, retry_after="Wed, 01 Sep 2026 00:00:00 GMT")
        assert probe.azure_spend(*WINDOW) is None
        assert az.waited == []
        assert len(az.posts) == 1

    def test_the_waiting_is_announced_to_whoever_is_watching(self, probe, monkeypatch, capsys):
        """40 silent seconds looks hung, and someone who kills it concludes the
        throttle is permanent — which is the misreading this whole item is about."""
        fake_az(probe, monkeypatch, throttles=1, retry_after="40")
        probe.report_azure(*WINDOW)
        assert "40초" in capsys.readouterr().out

    def test_a_curl_level_failure_is_not_mistaken_for_a_response(self, probe):
        """curl's own error text has no status line. Parsing it as one would invent a
        status, and status 0 is the one thing that must never look like 200."""
        status, body, headers = probe._split_http("curl: (6) Could not resolve host")
        assert (status, headers) == (0, {})
        assert "Could not resolve host" in body
