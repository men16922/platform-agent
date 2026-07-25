"""
Guards for the orphan cluster sweeper.

The contract is "make an over-budget cluster impossible to miss, and never delete
on its own". Every rule here fails toward *reporting* — a sweeper that silently
skips a cluster is worse than no sweeper, because it reads as an all-clear.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.agents.operations.orphan_sweeper import (
    ClusterRecord,
    delete_commands,
    find_orphans,
    format_report,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def _cluster(**overrides) -> ClusterRecord:
    base = {
        "provider": "gcp",
        "name": "pa-gke-live",
        "location": "us-central1",
        "created_at": NOW - timedelta(minutes=10),
        "labels": {},
        "project": "proj-1",
    }
    base.update(overrides)
    return ClusterRecord(**base)


class TestAgeBudget:
    def test_fresh_cluster_is_not_an_orphan(self):
        assert find_orphans([_cluster()], now=NOW, max_age_min=60) == []

    def test_over_budget_cluster_is_reported(self):
        old = _cluster(created_at=NOW - timedelta(hours=9))
        (finding,) = find_orphans([old], now=NOW, max_age_min=60)
        assert finding.age_min == 540
        assert "exceeds" in finding.reason

    def test_the_actual_incident_shape_is_caught(self):
        """2026-06-24: a live test cluster left up ~9h with the laptop asleep."""
        nine_hours = _cluster(created_at=NOW - timedelta(hours=9))
        assert find_orphans([nine_hours], now=NOW, max_age_min=1440) == [], (
            "the default day-long budget intentionally does not flag 9h…"
        )
        findings = find_orphans([nine_hours], now=NOW, max_age_min=30)
        assert findings, "…but the watchdog-equivalent 30min budget does"

    def test_exactly_at_budget_is_not_yet_an_orphan(self):
        borderline = _cluster(created_at=NOW - timedelta(minutes=60))
        assert find_orphans([borderline], now=NOW, max_age_min=60) == []

    def test_naive_timestamps_are_treated_as_utc(self):
        """Provider APIs are inconsistent about tz; a crash here would skip a cluster."""
        naive = _cluster(created_at=datetime(2026, 7, 25, 2, 0))  # no tzinfo
        (finding,) = find_orphans([naive], now=NOW, max_age_min=60)
        assert finding.age_min == 600


class TestFailsTowardReporting:
    def test_unknown_creation_time_is_reported_not_skipped(self):
        unknown = _cluster(created_at=None)
        (finding,) = find_orphans([unknown], now=NOW, max_age_min=60)
        assert finding.age_min is None
        assert "unknown" in finding.reason

    def test_unknown_age_sorts_first(self):
        findings = find_orphans(
            [
                _cluster(name="old", created_at=NOW - timedelta(hours=9)),
                _cluster(name="unknown", created_at=None),
            ],
            now=NOW,
            max_age_min=60,
        )
        assert [f.cluster.name for f in findings] == ["unknown", "old"]

    def test_oldest_first_among_known_ages(self):
        findings = find_orphans(
            [
                _cluster(name="a", created_at=NOW - timedelta(hours=2)),
                _cluster(name="b", created_at=NOW - timedelta(hours=9)),
            ],
            now=NOW,
            max_age_min=60,
        )
        assert [f.cluster.name for f in findings] == ["b", "a"]


class TestProtectionAndOverrides:
    def test_protected_name_is_skipped(self):
        old = _cluster(name="keeper", created_at=NOW - timedelta(days=30))
        assert find_orphans([old], now=NOW, max_age_min=60, protected=["keeper"]) == []

    def test_protection_requires_an_exact_name_match(self):
        """Prefix matching would let `pa-gke-live-2` inherit protection."""
        old = _cluster(name="pa-gke-live-2", created_at=NOW - timedelta(hours=9))
        assert find_orphans([old], now=NOW, max_age_min=60, protected=["pa-gke-live"])

    def test_label_ttl_extends_the_budget(self):
        labelled = _cluster(created_at=NOW - timedelta(hours=2), labels={"ttl-min": "180"})
        assert find_orphans([labelled], now=NOW, max_age_min=60) == []

    def test_label_ttl_can_also_tighten_the_budget(self):
        labelled = _cluster(created_at=NOW - timedelta(minutes=45), labels={"ttl-min": "30"})
        assert find_orphans([labelled], now=NOW, max_age_min=1440)

    def test_malformed_label_falls_back_to_the_global_budget(self):
        """A typo'd label must not silently grant an infinite lifetime."""
        labelled = _cluster(created_at=NOW - timedelta(hours=9), labels={"ttl-min": "forever"})
        assert find_orphans([labelled], now=NOW, max_age_min=60)

    def test_nonpositive_label_ttl_is_ignored(self):
        labelled = _cluster(created_at=NOW - timedelta(minutes=10), labels={"ttl-min": "0"})
        assert find_orphans([labelled], now=NOW, max_age_min=60) == []


class TestReporting:
    def test_clean_sweep_says_so(self):
        assert "no clusters over budget" in format_report([], now=NOW)

    def test_report_names_the_cluster_and_reason(self):
        findings = find_orphans(
            [_cluster(created_at=NOW - timedelta(hours=9))], now=NOW, max_age_min=60
        )
        report = format_report(findings, now=NOW)
        assert "pa-gke-live" in report
        assert "gcp/us-central1" in report and "proj-1" in report

    def test_report_states_that_deletion_is_not_automatic(self):
        """D5: destructive actions are approval-gated — the report must not imply otherwise."""
        findings = find_orphans(
            [_cluster(created_at=NOW - timedelta(hours=9))], now=NOW, max_age_min=60
        )
        assert "NOT automatic" in format_report(findings, now=NOW)


class TestDeleteCommands:
    def test_per_provider_commands(self):
        findings = find_orphans(
            [
                _cluster(provider="gcp", created_at=None),
                _cluster(provider="aws", name="eks-1", location="ap-northeast-2", created_at=None),
                _cluster(provider="azure", name="aks-1", location="rg-1", created_at=None),
            ],
            now=NOW,
            max_age_min=60,
        )
        commands = delete_commands(findings)
        joined = "\n".join(commands)
        assert "gcloud container clusters delete pa-gke-live --project proj-1" in joined
        assert "aws eks delete-cluster --name eks-1 --region ap-northeast-2" in joined
        assert "az aks delete --name aks-1 --resource-group rg-1 --yes" in joined

    def test_unknown_provider_yields_a_comment_not_a_wrong_command(self):
        findings = find_orphans(
            [_cluster(provider="ibm", created_at=None)], now=NOW, max_age_min=60
        )
        (command,) = delete_commands(findings)
        assert command.startswith("#"), "must not guess a delete command for an unknown provider"


# --- CLI collection boundary: "could not look" != "nothing there" -----------
#
# The core rules above already fail toward reporting. The dangerous gap was one
# level up, at the shell-out: a provider whose CLI is missing or unauthenticated
# used to yield zero clusters, which reads identically to a healthy empty cloud.
# Run that as a CronJob in a container without `gcloud` and it reports a green
# all-clear forever while the clusters keep billing.


def _script():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "sweep_orphan_clusters.py"
    spec = importlib.util.spec_from_file_location("sweep_orphan_clusters", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSweepCoverage:
    def test_unreachable_provider_does_not_report_clean(self, monkeypatch, capsys):
        sweep = _script()

        def boom():
            raise sweep.ProviderUnavailable("gcloud: not authenticated")

        monkeypatch.setattr(sweep, "_COLLECTORS", {"gcp": boom})
        monkeypatch.setattr("sys.argv", ["sweep", "--provider", "gcp"])
        assert sweep.main() == 2, "no coverage must not exit 0"
        assert "COVERAGE INCOMPLETE" in capsys.readouterr().out

    def test_full_coverage_with_nothing_found_is_a_real_green(self, monkeypatch, capsys):
        sweep = _script()
        monkeypatch.setattr(sweep, "_COLLECTORS", {"gcp": lambda: []})
        monkeypatch.setattr("sys.argv", ["sweep", "--provider", "gcp"])
        assert sweep.main() == 0
        assert "COVERAGE INCOMPLETE" not in capsys.readouterr().out

    def test_findings_outrank_a_coverage_gap(self, monkeypatch):
        """Both problems at once: the actionable one owns the exit code."""
        sweep = _script()

        def boom():
            raise sweep.ProviderUnavailable("az: not logged in")

        monkeypatch.setattr(
            sweep,
            "_COLLECTORS",
            {"azure": boom, "gcp": lambda: [_cluster(created_at=None)]},
        )
        monkeypatch.setattr("sys.argv", ["sweep", "--provider", "gcp", "--provider", "azure"])
        assert sweep.main() == 1

    def test_json_output_names_what_was_not_swept(self, monkeypatch, capsys):
        import json as _json

        sweep = _script()

        def boom():
            raise sweep.ProviderUnavailable("aws: no credentials")

        monkeypatch.setattr(sweep, "_COLLECTORS", {"aws": boom, "gcp": lambda: []})
        monkeypatch.setattr("sys.argv", ["sweep", "--provider", "gcp", "--provider", "aws", "--json"])
        sweep.main()
        payload = _json.loads(capsys.readouterr().out)
        assert payload["swept"] == ["gcp"]
        assert "aws" in payload["unswept"], "a consumer must be able to see the hole in the data"

    def test_run_json_raises_instead_of_swallowing(self, monkeypatch):
        sweep = _script()

        class _Proc:
            returncode = 1
            stdout = ""
            stderr = "ERROR: (gcloud) not authenticated"

        monkeypatch.setattr(sweep.subprocess, "run", lambda *a, **k: _Proc())
        try:
            sweep._run_json(["gcloud", "container", "clusters", "list"])
        except sweep.ProviderUnavailable as exc:
            assert "not authenticated" in str(exc), "the reason must survive to the report"
        else:
            raise AssertionError("a failed CLI call must not look like an empty result")
