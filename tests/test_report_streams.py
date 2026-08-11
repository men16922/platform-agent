"""Every CLI in `scripts/` must reach the reader on the stream the reader holds.

WHERE THIS CAME FROM. On 2026-08-10 `probe_cloud_spend.py` was found printing its
report body to stdout and its "could not measure" verdicts to stderr. On a TTY the
two interleave and it reads correctly, which is how it was written and why nobody
saw it; through a pipe stdout is block-buffered, so the reader got three headings
with nothing under them. An empty section is read as zero. The probe was fixed and
guarded — and then the guard's own blind spot turned out to be the bigger finding:

    the test asked `capsys.readouterr().err`, and `capsys` hands back `.out` and
    `.err` as two separate strings, so a test written that way **cannot see that
    the reader's copy came apart**. It was structurally incapable of failing.

That was recorded as the fourth face of STATUS Risk 12 (①time ②environment ③load
④observation point), with the note that only one instance had been checked. This
file is the sweep of the rest, and the rule it encodes:

    ASK ABOUT THE THING THE READER ACTUALLY READS.

WHAT THE SWEEP FOUND. Eight more CLIs had the same split; four had it on paths that
mattered:

  * `verify_netpol_enforcement.py` — run log to stdout, INCONCLUSIVE to stderr. The
    piped copy ended `baseline: B -> A reachable ✓` and then stopped. A report that
    stops after a ✓ reads as a report that finished, and this script's verdict is
    what decides whether a substrate joins PROVEN_ENFORCING_SUBSTRATES. A lost
    "NOT ENFORCED" is how a CNI that ignores policy gets promoted.
  * `verify_tenant_isolation.py` — same shape over four claims: `[1/4] ✓ [2/4] ✓`
    and silence where the verdict was.
  * `verify_image_signature.py` — the stream depended on *which* failure it was, so
    `2>/dev/null` printed nothing at all on exactly the two paths where nothing had
    been checked.
  * `attach_addon.py` — the `--commit` refusal arrives after the plan is already on
    stdout, so the reader's only evidence of failure was a line that did not appear.

WHY `capsys` IS STILL THE RIGHT TOOL HERE. The blind spot was never the fixture; it
was asserting on `.err` for something the reader needed on `.out`. Asserting
`.err == ""` uses the same fixture to ask the reader's question, because a stream
nothing is written to cannot be a stream anything is lost on — no buffering, TTY
or pipe, changes that.

TWO KINDS OF STDOUT. The rule is not "never use stderr"; it is "the reader's stream
must carry what the reader needs", and for some of these the reader is a program:

    REPORT    stdout is prose a person reads. Nothing they need may be on stderr.
    DOCUMENT  stdout is a document a parser reads (YAML manifests, JSON). The
              inverse duty — diagnostics must stay OFF stdout or the document is
              corrupt.
    DUAL      `--json` switches between the two; each mode owes its own rule.

`render_tenancy.py` had this right all along and is worth copying: manifests on
stdout, every diagnostic on stderr and prefixed `#`, so even a careless `2>&1 |
kubectl apply -f -` still parses.
"""

from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

# ---------------------------------------------------------------------------
# The classification. Every script declares which kind of stdout it has, and a
# new one cannot be added without saying — that is the anti-drift half of this
# file, and it is why the lists below are exhaustive rather than a sample.
# ---------------------------------------------------------------------------

REPORT = {
    "attach_addon.py",
    "find_unconsumed_fields.py",
    "find_unwritten_keys.py",
    "live_model_sweep.py",
    "live_net_demo.py",
    "live_tier2_demo.py",
    "probe_cloud_spend.py",
    "probe_incident_roundtrip.py",
    "probe_scope_reachability.py",
    "provision_gke_live.py",
    "push_addon_status.py",
    "slack_live_approval.py",
    "verify_image_signature.py",
    "verify_netpol_enforcement.py",
    "verify_tenancy_adoption.py",
    "verify_tenant_isolation.py",
    "watch_cloud_spend.py",
}

DOCUMENT = {
    "render_addons.py",       # ArgoCD/Flux manifests, piped to kubectl
    "render_deploy_identity.py",
    "render_tenancy.py",      # Namespace/Role/NetworkPolicy/Tenant manifests
}

DUAL = {
    "preflight_gitops_handoff.py",   # --json
    "sweep_orphan_clusters.py",      # --json
}


def _load(name: str):
    """Import a script by path, the way tests/test_image_signature.py does."""
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class TestEveryScriptDeclaresItsReader:
    def test_no_script_is_unclassified(self):
        """A new CLI must say which kind of stdout it has before it can ship.

        Without this the sweep is a snapshot: the next script lands unclassified,
        splits its report, and nothing here notices — which is exactly how the
        first four got in.
        """
        on_disk = {p.name for p in SCRIPTS.glob("*.py") if not p.name.startswith("_")}
        classified = REPORT | DOCUMENT | DUAL
        unclassified = sorted(on_disk - classified)
        assert not unclassified, (
            f"{unclassified} is not declared REPORT, DOCUMENT or DUAL in "
            "tests/test_report_streams.py. Decide what its stdout is for: prose a "
            "person reads (REPORT — then nothing they need may go to stderr), or a "
            "document a parser reads (DOCUMENT — then diagnostics must stay off it)."
        )

    def test_the_classification_names_no_ghosts(self):
        on_disk = {p.name for p in SCRIPTS.glob("*.py")}
        missing = sorted((REPORT | DOCUMENT | DUAL) - on_disk)
        assert not missing, f"classified but gone from scripts/: {missing}"

    @pytest.mark.parametrize("bucket_a,bucket_b,names", [
        ("REPORT", "DOCUMENT", REPORT & DOCUMENT),
        ("REPORT", "DUAL", REPORT & DUAL),
        ("DOCUMENT", "DUAL", DOCUMENT & DUAL),
    ])
    def test_the_buckets_do_not_overlap(self, bucket_a, bucket_b, names):
        assert not names, f"{sorted(names)} is in both {bucket_a} and {bucket_b}"


# ---------------------------------------------------------------------------
# REPORT: run main() down a failure path and read what the reader receives.
#
# Failure paths on purpose. A green run puts its verdict on stdout in every one
# of these scripts and always did; the split only ever showed on the paths where
# something went wrong, which is where a lost verdict costs the most.
# ---------------------------------------------------------------------------


class TestTheVerdictIsOnTheReadersStream:
    def _assert_reader_gets_a_verdict(self, captured, marker: str, script: str):
        assert marker in captured.out, (
            f"{script}: a reader who pipes stdout never sees {marker!r}. "
            f"They got: {captured.out!r}"
        )
        assert captured.err == "", (
            f"{script}: the report is split across two streams — {captured.err!r} "
            "went where the reader is not looking"
        )

    def test_netpol_enforcement_says_it_could_not_look(self, monkeypatch, capsys):
        mod = _load("verify_netpol_enforcement.py")
        monkeypatch.setattr(mod, "_kubectl", lambda *a, **k: _completed(returncode=1))
        monkeypatch.setattr("sys.argv", ["verify_netpol_enforcement.py"])
        assert mod.main() == 2
        self._assert_reader_gets_a_verdict(
            capsys.readouterr(), "ERROR", "verify_netpol_enforcement.py"
        )

    def test_netpol_enforcement_does_not_end_on_a_tick(self, monkeypatch, capsys):
        """The one that actually bit: a ✓ printed, then the run dies.

        Before the fix stdout ended at `baseline: ... ✓` and the INCONCLUSIVE went
        to stderr, so the reader's last line was a tick.
        """
        mod = _load("verify_netpol_enforcement.py")
        monkeypatch.setattr(mod, "_kubectl", lambda *a, **k: _completed(stdout="kind-kind"))
        monkeypatch.setattr(mod, "_apply", lambda manifest: None)
        monkeypatch.setattr(mod, "_wait_ready", lambda *a, **k: True)
        monkeypatch.setattr(mod, "_can_reach", lambda *a, **k: True)
        monkeypatch.setattr(mod, "_deny_all_ingress", lambda: (_ for _ in ()).throw(
            RuntimeError("apply failed: the cluster went away")
        ))
        monkeypatch.setattr("sys.argv", ["verify_netpol_enforcement.py"])
        assert mod.main() == 2

        captured = capsys.readouterr()
        assert "baseline: B -> A reachable (no policy) ✓" in captured.out
        self._assert_reader_gets_a_verdict(
            captured, "INCONCLUSIVE", "verify_netpol_enforcement.py"
        )
        assert not captured.out.strip().endswith("✓"), (
            "the reader's copy ends on a tick, which reads as a finished run"
        )

    def test_tenant_isolation_refuses_on_the_readers_stream(self, monkeypatch, capsys):
        mod = _load("verify_tenant_isolation.py")
        monkeypatch.setattr("sys.argv", [
            "verify_tenant_isolation.py", "--tenant", "acme", "--env", "dev",
            "--peer-tenant", "acme", "--peer-env", "dev",
        ])
        assert mod.main() == 2
        self._assert_reader_gets_a_verdict(
            capsys.readouterr(), "ERROR", "verify_tenant_isolation.py"
        )

    def test_tenancy_adoption_says_it_did_not_look(self, monkeypatch, capsys):
        """`not looking is not a finding` — the script's own thesis, applied to it."""
        mod = _load("verify_tenancy_adoption.py")
        monkeypatch.setattr(
            mod, "subprocess",
            types.SimpleNamespace(run=lambda *a, **k: _completed(stdout="some-other-cluster")),
        )
        monkeypatch.setattr("sys.argv", ["verify_tenancy_adoption.py"])
        assert mod.main() == 2

        captured = capsys.readouterr()
        self._assert_reader_gets_a_verdict(
            captured, "nothing to check", "verify_tenancy_adoption.py"
        )
        assert "lives on" in captured.out, (
            "the reader is told nothing was checked but not which clusters the "
            "envs are on, which is the whole actionable half"
        )

    @pytest.mark.parametrize("argv,setup", [
        (["verify_image_signature.py", "img"], None),
        (["verify_image_signature.py", "img", "--key", "k.pub"], "no-cosign"),
    ])
    def test_image_signature_never_goes_silent(self, monkeypatch, capsys, argv, setup):
        """Both pre-cosign exits used to print to stderr only.

        `2>/dev/null` then produced empty output and exit 2 — nothing checked, and
        nothing said about it, from the script whose docstring calls that outcome
        worse than having no step at all.
        """
        mod = _load("verify_image_signature.py")
        if setup == "no-cosign":
            monkeypatch.setattr(mod.shutil, "which", lambda name: None)
        monkeypatch.setattr("sys.argv", argv)
        assert mod.main() == mod.COSIGN_MISSING
        self._assert_reader_gets_a_verdict(
            capsys.readouterr(), "CANNOT EVALUATE", "verify_image_signature.py"
        )

    def test_image_signature_keeps_cosigns_reason_with_the_verdict(
        self, monkeypatch, capsys
    ):
        mod = _load("verify_image_signature.py")
        monkeypatch.setattr(mod.shutil, "which", lambda name: "/usr/bin/cosign")
        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _completed(
            returncode=1, stderr="Error: no signatures found for image"
        ))
        monkeypatch.setattr("sys.argv", ["verify_image_signature.py", "img", "--key", "k"])
        assert mod.main() == mod.NOT_SIGNED

        captured = capsys.readouterr()
        self._assert_reader_gets_a_verdict(
            captured, "NOT SIGNED", "verify_image_signature.py"
        )
        assert "no signatures found" in captured.out, (
            "the verdict reached the reader and the reason for it did not"
        )

    def test_attach_addon_refusal_lands_beside_the_plan(self, monkeypatch, capsys):
        """The refusal that arrives after the diff is already printed.

        Absence of the `committed <sha>` line is not a verdict, and it was the only
        signal a piped reader had.
        """
        mod = _load("attach_addon.py")
        monkeypatch.setattr(mod, "commit_attachment", lambda plan: (_ for _ in ()).throw(
            mod.RegistryWriteError("working tree is dirty")
        ))
        monkeypatch.setattr("sys.argv", [
            "attach_addon.py", "acme", "prod", "tracing", "1.24.4", "--commit",
        ])
        assert mod.main() == 1

        captured = capsys.readouterr()
        assert "tracing" in captured.out, "the plan itself vanished"
        self._assert_reader_gets_a_verdict(captured, "REFUSED", "attach_addon.py")

    def test_attach_addon_refuses_an_unknown_tenant_out_loud(self, monkeypatch, capsys):
        mod = _load("attach_addon.py")
        monkeypatch.setattr("sys.argv", [
            "attach_addon.py", "nosuch", "dev", "tracing", "1.24.4",
        ])
        assert mod.main() == 1
        self._assert_reader_gets_a_verdict(
            capsys.readouterr(), "REFUSED", "attach_addon.py"
        )

    def test_spend_watch_does_not_go_quiet_when_it_could_not_measure(
        self, monkeypatch, capsys, tmp_path
    ):
        """Left on stderr when the probe was fixed, on the grounds that one line
        cannot interleave with itself. True, and beside the point: piped, exit 2
        leaves stdout empty, and an empty spend report reads the way an empty
        section did."""
        mod = _load("watch_cloud_spend.py")
        monkeypatch.setattr(mod, "observe", lambda: None)
        monkeypatch.setattr("sys.argv", [
            "watch_cloud_spend.py", "--state", str(tmp_path / "snap.json"),
        ])
        assert mod.main() == 2
        self._assert_reader_gets_a_verdict(
            capsys.readouterr(), "'새 과금 없음'이 아니다", "watch_cloud_spend.py"
        )

    def test_push_agent_reports_a_missing_key_on_one_stream(self, monkeypatch, capsys):
        mod = _load("push_addon_status.py")
        monkeypatch.delenv(mod.PUSH_KEY_ENV, raising=False)
        monkeypatch.setattr("sys.argv", [
            "push_addon_status.py", "--tenant", "acme", "--env", "dev",
        ])
        assert mod.main() == 2
        self._assert_reader_gets_a_verdict(
            capsys.readouterr(), "ERROR", "push_addon_status.py"
        )

    def test_preflight_reports_a_missing_release_to_a_person(self, monkeypatch, capsys):
        mod = _load("preflight_gitops_handoff.py")
        monkeypatch.setattr(mod, "_helm_revision", lambda release, namespace: None)
        monkeypatch.setattr("sys.argv", [
            "preflight_gitops_handoff.py", "pa", "-n", "ns",
        ])
        assert mod.main() == 2
        self._assert_reader_gets_a_verdict(
            capsys.readouterr(), "ERROR", "preflight_gitops_handoff.py"
        )


class TestTheLoopLogIsFlushed:
    """One stream is not enough when the reader is `tail -f`.

    `make dev-up` sends both streams of the push agent into one file. Picking the
    stream by outcome put successes on a block-buffered stream and failures on an
    unbuffered one, into the same file — so the failures arrived promptly, the
    successes arrived later in bursts, and the order in the log was not the order
    things happened. For a loop whose entire output is a timeline, that is the
    timeline being wrong. Asked by watching for the flush rather than by reading
    the source, because the source says `flush=True` in a place a reader cannot
    check and a formatter can move.
    """

    def test_each_line_is_pushed_out_when_it_is_written(self, monkeypatch, capsys):
        mod = _load("push_addon_status.py")
        flushes: list[str] = []

        class _WatchedStream:
            def __init__(self):
                self.buffer: list[str] = []

            def write(self, text: str) -> int:
                self.buffer.append(text)
                return len(text)

            def flush(self) -> None:
                flushes.append("".join(self.buffer))

        monkeypatch.setenv(mod.PUSH_KEY_ENV, "k")
        monkeypatch.setattr(mod, "push_once", lambda *a, **k: (0, "pushed 4 row(s)"))
        monkeypatch.setattr("sys.argv", [
            "push_addon_status.py", "--tenant", "acme", "--env", "dev", "--once",
        ])
        monkeypatch.setattr("sys.stdout", _WatchedStream())
        assert mod.main() == 0

        assert any("pushed 4 row(s)" in text for text in flushes), (
            "the line was written but never flushed — in a redirected log it sits "
            "in an 8KB buffer while lines written after it appear first"
        )


# ---------------------------------------------------------------------------
# DOCUMENT: the mirror duty. Here stdout is not prose and the danger runs the
# other way — a diagnostic that lands on it corrupts what the parser receives.
# ---------------------------------------------------------------------------


class TestTheDocumentStreamStaysParseable:
    def test_render_tenancy_emits_only_manifests_while_warning(self, monkeypatch, capsys):
        """acme/prod is on k3s, an unproven substrate, so this run warns loudly
        about missing data-plane isolation *and* prints manifests. The warning
        must not be inside the thing kubectl is about to apply."""
        mod = _load("render_tenancy.py")
        monkeypatch.setattr("sys.argv", ["render_tenancy.py", "acme", "--env", "prod"])
        mod.main()

        captured = capsys.readouterr()
        documents = [d for d in yaml.safe_load_all(captured.out) if d]
        assert documents, "the manifest stream is empty"
        assert all(isinstance(d, dict) and "kind" in d for d in documents)
        assert "NO DATA-PLANE ISOLATION" in captured.err, (
            "the substrate warning went missing entirely"
        )
        assert "NO DATA-PLANE ISOLATION" not in captured.out, (
            "prose landed in the manifest stream — `| kubectl apply -f -` now "
            "receives a document with commentary in it"
        )

    def test_render_addons_keeps_its_refusals_off_the_manifest_stream(
        self, monkeypatch, capsys
    ):
        """Cluster-scoped capabilities are refused per tenant and named on stderr;
        the namespace-scoped ones still render."""
        mod = _load("render_addons.py")
        monkeypatch.setattr("sys.argv", ["render_addons.py", "acme", "-e", "dev"])
        mod.main()

        captured = capsys.readouterr()
        documents = [d for d in yaml.safe_load_all(captured.out) if d]
        assert documents, "the manifest stream is empty"
        assert all(isinstance(d, dict) and "kind" in d for d in documents)


class TestDualModeObeysTheModeItIsIn:
    def test_sweeper_json_is_json_even_when_a_provider_was_not_swept(
        self, monkeypatch, capsys
    ):
        mod = _load("sweep_orphan_clusters.py")
        monkeypatch.setitem(mod._COLLECTORS, "aws", lambda: (_ for _ in ()).throw(
            mod.ProviderUnavailable("no credentials")
        ))
        monkeypatch.setattr("sys.argv", [
            "sweep_orphan_clusters.py", "--provider", "aws", "--json",
        ])
        mod.main()

        captured = capsys.readouterr()
        payload = json.loads(captured.out)   # red the moment a warning lands here
        assert payload["unswept"] == {"aws": "no credentials"}, (
            "the document must carry what was not looked at, or a consumer reads "
            "'no findings' as 'nothing there'"
        )

    def test_sweeper_report_carries_the_gap_to_a_person(self, monkeypatch, capsys):
        mod = _load("sweep_orphan_clusters.py")
        monkeypatch.setitem(mod._COLLECTORS, "aws", lambda: (_ for _ in ()).throw(
            mod.ProviderUnavailable("no credentials")
        ))
        monkeypatch.setattr("sys.argv", ["sweep_orphan_clusters.py", "--provider", "aws"])
        mod.main()

        captured = capsys.readouterr()
        assert "COVERAGE INCOMPLETE" in captured.out
        assert "no credentials" in captured.out, (
            "the reason the sweep was incomplete is only on stderr"
        )

    def test_preflight_json_stays_a_document(self, monkeypatch, capsys):
        """The mode where the fix above must NOT apply: prose on stdout here is a
        parse error for whoever asked for --json."""
        mod = _load("preflight_gitops_handoff.py")
        monkeypatch.setattr(mod, "_helm_revision", lambda release, namespace: None)
        monkeypatch.setattr("sys.argv", [
            "preflight_gitops_handoff.py", "pa", "-n", "ns", "--json",
        ])
        assert mod.main() == 2

        captured = capsys.readouterr()
        assert captured.out == "", (
            "an error string was printed where a JSON document was promised"
        )
        assert "ERROR" in captured.err
