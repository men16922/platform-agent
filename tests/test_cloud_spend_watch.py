"""The half a spend probe cannot cover: nobody runs it.

`probe_cloud_spend.py` is right every time it runs, and on 2026-08-09 what caught
the forgotten `slackops-devops-agent` was not a run of it — it was a budget alert,
eighteen days and ~$35 later. Budgets answer "how much, eventually". The other half
is "what started charging", which is the shape every incident in this repo has had,
and which is answerable on day one because a new charge is a *new line*, not a
bigger number.

So these guards are about the comparison, not the measurement (that one is guarded
in `test_cloud_spend_probe.py` and is imported here rather than rebuilt — a second
source of truth for "what are we spending" is how two numbers start disagreeing).

What must hold:
  * a first run establishes a baseline and reports nothing (or it cries wolf once
    per new machine, and people stop reading it);
  * an unmeasured provider must not overwrite the baseline, or one bad night
    silently resets what "new" means;
  * a service that *disappears* is not a finding — something was turned off;
  * no threshold is invented, because a rule you cannot satisfy is the ₩20 budget.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WATCHER = REPO / "scripts" / "watch_cloud_spend.py"


@pytest.fixture(scope="module")
def source() -> str:
    assert WATCHER.is_file(), "the watcher this file guards does not exist"
    return WATCHER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def watch():
    spec = importlib.util.spec_from_file_location("watch_cloud_spend", WATCHER)
    assert spec and spec.loader, "the watcher is not importable"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def wired(watch, monkeypatch, tmp_path):
    """Point the watcher at fake clouds and a scratch snapshot."""
    state = {"aws": [("Amazon Elastic Compute Cloud - Compute", 7.54)],
             "azure": [("one", "KRW", [("Container Registry", 1989.33)])],
             "gcp": ("NOT_EXPORTED", "no export table")}

    monkeypatch.setattr(watch, "spend_by_service",
                        lambda *_: None if state["aws"] is None else (0.0, state["aws"]))
    monkeypatch.setattr(watch, "azure_spend", lambda *_: state["azure"])
    monkeypatch.setattr(watch, "gcp_actual_spend", lambda: state["gcp"])

    def run(*argv):
        monkeypatch.setattr("sys.argv", ["watch", "--state", str(tmp_path / "snap.json"), *argv])
        return watch.main()

    return state, run, tmp_path / "snap.json"


class TestTheFirstRunDoesNotCryWolf:
    def test_a_baseline_is_recorded_and_nothing_is_reported(self, wired, capsys):
        _, run, snap = wired
        assert run() == 0
        assert "기준선을 잡았다" in capsys.readouterr().out
        assert snap.is_file()

    def test_the_second_run_with_no_change_is_quiet(self, wired, capsys):
        _, run, _ = wired
        run()
        assert run() == 0
        assert "없다" in capsys.readouterr().out

    def test_baseline_can_be_retaken_on_purpose(self, wired):
        state, run, _ = wired
        run()
        state["aws"] = [("Amazon Elastic Compute Cloud - Compute", 7.54), ("Something New", 1.0)]
        assert run("--baseline") == 0, "an explicit baseline must not also report"
        assert run() == 0, "and it must be the thing compared against next time"


class TestSomethingNewIsTheSignal:
    def test_a_newly_charged_service_exits_one_and_names_it(self, wired, capsys):
        state, run, _ = wired
        run()
        state["aws"].append(("Amazon Relational Database Service", 0.01))
        assert run() == 1
        out = capsys.readouterr().out
        assert "Amazon Relational Database Service" in out

    def test_a_new_azure_service_is_seen_too(self, wired, capsys):
        state, run, _ = wired
        run()
        state["azure"] = [("one", "KRW", [("Container Registry", 1989.33), ("Virtual Machines", 12.0)])]
        assert run() == 1
        assert "Virtual Machines" in capsys.readouterr().out

    def test_a_service_that_stops_charging_is_not_a_finding(self, wired):
        """Something was switched off. Waking someone for that is how a signal turns
        into noise — and the ₩20 budget already showed what noise costs."""
        state, run, _ = wired
        run()
        state["aws"] = []
        assert run() == 0

    def test_no_threshold_is_invented(self, source):
        """Budgets already answer "how much" and the AWS one worked. A second,
        hand-picked number here would be a rule nobody agreed to."""
        assert "budgets  → 얼마나" in source, (
            "the watcher stopped saying why it does not threshold"
        )


class TestAnUnmeasuredRunIsNotAQuietRun:
    def test_it_exits_two_rather_than_reporting_nothing_new(self, wired, capsys):
        state, run, _ = wired
        run()
        state["aws"] = None
        assert run() == 2
        assert "'새 과금 없음'이 아니다" in capsys.readouterr().err

    def test_a_failed_run_does_not_overwrite_the_baseline(self, wired):
        """Otherwise one unreadable night resets what "new" means, and the next real
        change compares against nothing."""
        state, run, snap = wired
        run()
        before = snap.read_text(encoding="utf-8")
        state["aws"] = None
        run()
        assert snap.read_text(encoding="utf-8") == before

    def test_a_corrupt_snapshot_is_treated_as_no_snapshot(self, wired, capsys):
        _, run, snap = wired
        run()
        snap.write_text("{ this is not json", encoding="utf-8")
        assert run() == 0, "a broken file must not read as 'everything is new'"
        assert "기준선" in capsys.readouterr().out


class TestGcpBecomingReadableIsWorthSaying:
    def test_a_change_in_gcp_status_is_reported(self, wired, capsys):
        """The one open cost gap is a console toggle. When someone flips it, the
        thing that already runs should be what notices."""
        state, run, _ = wired
        run()
        state["gcp"] = ("MEASURABLE", "proj:ds.gcp_billing_export_v1_x")
        run()
        out = capsys.readouterr().out
        assert "NOT_EXPORTED" in out and "MEASURABLE" in out


class TestTheUnattendedWrapperIsQuietOnPurpose:
    """The daily job is where "an alert that is usually wrong" gets made.

    Cost Management answers 429 when asked a few times in a row — hit for real while
    building this, and a notification for every one of those is the ₩20 budget wearing
    a new hat. So the wrapper retries once before speaking. That branch is exercised
    here rather than trusted, because the live run that would have covered it happened
    to succeed on the first try, and an unexercised branch carries no weight.
    """

    WRAPPER = REPO / "scripts" / "spend_watch_launchd.sh"

    def _fake_repo(self, tmp_path: Path, codes: list[int]) -> tuple[Path, Path]:
        """A repo whose watcher exits with `codes` on successive runs."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "watch_cloud_spend.py").write_text(
            "import sys, pathlib\n"
            f"codes = {codes!r}\n"
            "n = pathlib.Path('.state/calls')\n"
            "n.parent.mkdir(exist_ok=True)\n"
            "i = int(n.read_text()) if n.is_file() else 0\n"
            "n.write_text(str(i + 1))\n"
            "print('call', i)\n"
            "sys.exit(codes[min(i, len(codes) - 1)])\n",
            encoding="utf-8",
        )
        notified = tmp_path / "notified.txt"
        notifier = tmp_path / "notifier.sh"
        notifier.write_text(f'#!/bin/sh\necho "$1" >> "{notified}"\n', encoding="utf-8")
        notifier.chmod(0o755)
        return notifier, notified

    def _run(self, tmp_path, codes):
        notifier, notified = self._fake_repo(tmp_path, codes)
        proc = subprocess.run(
            ["/bin/zsh", str(self.WRAPPER)],
            capture_output=True, text=True,
            env={**os.environ,
                 "SPEND_WATCH_REPO": str(tmp_path),
                 "SPEND_WATCH_RETRY_SLEEP": "0",
                 "SPEND_WATCH_NOTIFY_CMD": str(notifier)},
        )
        calls = int((tmp_path / ".state" / "calls").read_text())
        said = notified.read_text(encoding="utf-8") if notified.is_file() else ""
        return proc.returncode, calls, said

    def test_a_transient_failure_is_retried_and_never_mentioned(self, tmp_path):
        code, calls, said = self._run(tmp_path, [2, 0])
        assert (code, calls) == (0, 2), "the retry did not happen, or its result was ignored"
        assert said == "", "a 429 that cleared on retry is not something to wake anyone for"

    def test_a_failure_that_persists_is_reported(self, tmp_path):
        code, calls, said = self._run(tmp_path, [2, 2])
        assert (code, calls) == (2, 2)
        assert "측정하지 못했다" in said, "'could not look' must not be silent either"

    def test_a_finding_is_reported_without_a_retry(self, tmp_path):
        """Exit 1 is an answer, not a failure — retrying it would just delay the news."""
        code, calls, said = self._run(tmp_path, [1, 0])
        assert (code, calls) == (1, 1)
        assert "새로 과금" in said

    def test_a_quiet_run_says_nothing_at_all(self, tmp_path):
        code, calls, said = self._run(tmp_path, [0])
        assert (code, calls) == (0, 1)
        assert said == "", "a daily 'all fine' notification is one people turn off"


class TestTheMeasurementIsNotRebuilt:
    def test_the_watcher_does_not_shell_out_on_its_own(self, source):
        """Two places asking the cloud "what are we spending" is how two answers
        start disagreeing — 431aeab deleted one of those already."""
        assert "subprocess" not in source, "the watcher grew its own process call"
        assert "_run(" not in source, (
            "the watcher reached for the probe's CLI layer instead of its answers"
        )

    def test_it_makes_no_cloud_call_of_its_own(self, watch, wired):
        """Behavioural, because the source check above cannot tell a dict key named
        "aws" from an `aws` command line — and it already got that wrong once."""
        _, run, _ = wired
        assert run() == 0          # every provider is faked; a real call would hang or fail
        assert not hasattr(watch, "_run")

    def test_it_imports_the_probe_rather_than_copying_it(self, source):
        assert "from probe_cloud_spend import" in source
