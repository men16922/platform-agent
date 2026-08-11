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

That is a sufficiency argument, though, not a measurement, and the whole point of
this file is that arguments about what a reader receives have been wrong here
before. So `TestARealPipeAgrees` runs one CLI as an actual subprocess with an
actual pipe on stdout and `stderr` thrown away — the reader's exact situation, the
one `capsys` reasons about rather than reproduces. One case, deliberately: it
exists to check that the reasoning above holds in the real world, not to be
duplicated for all seventeen.

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
import os
import subprocess
import sys
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

    # The sweep was extended past scripts/ on 2026-08-11. `src/` writes to stderr
    # nowhere at all, so it has none of the REPORT defect — but it has exactly one
    # module with a DOCUMENT stdout, and that one was corrupting it. The guard
    # lives here, with the rule, rather than beside the module.
    def test_the_one_document_cli_in_src_does_not_answer_with_prose(self):
        """`python -m …manifest_generator > out.yaml` after a typo used to write
        the usage line into out.yaml and exit 0 — and `yaml.safe_load` returns
        `{'Usage': '…'}` for that, a **valid mapping**. Not a parse error and not
        a failed exit: it fails later, as a manifest with no `kind`."""
        proc = subprocess.run(
            [sys.executable, "-m", "src.agents.provisioning.manifest_generator"],
            cwd=REPO, capture_output=True, text=True,
        )
        assert proc.stdout == "", (
            f"prose landed on the manifest stream: {proc.stdout!r}"
        )
        assert proc.returncode != 0, "a missing argument exited 0"
        assert "Usage" in proc.stderr, "the reader was told nothing at all"

    def test_help_is_still_prose_on_stdout(self):
        """The case that is NOT the same: a reader asking for text gets text.
        Routing `--help` to stderr to satisfy the rule above would be obeying the
        letter of it — nobody redirects `--help` into a manifest."""
        proc = subprocess.run(
            [sys.executable, "-m", "src.agents.provisioning.manifest_generator", "--help"],
            cwd=REPO, capture_output=True, text=True,
        )
        assert proc.returncode == 0
        assert "Usage" in proc.stdout


#: REPORT CLIs whose failure path can be driven with no cluster, no network and no
#: credentials — so they can be run as real subprocesses through a real pipe.
#: (label, argv, env-overrides, expected marker on stdout)
PIPEABLE = [
    ("image-signature/no-identity",
     ["verify_image_signature.py", "some/image:tag"], {}, "CANNOT EVALUATE"),
    ("image-signature/no-cosign",
     ["verify_image_signature.py", "some/image:tag", "--key", "k.pub"],
     {"PATH": "/usr/bin:/bin"}, "CANNOT EVALUATE"),
    ("tenant-isolation/peer-is-self",
     ["verify_tenant_isolation.py", "--tenant", "acme", "--env", "dev",
      "--peer-tenant", "acme", "--peer-env", "dev"], {}, "ERROR"),
    ("attach-addon/unknown-tenant",
     ["attach_addon.py", "nosuch", "dev", "tracing", "1.24.4"], {}, "REFUSED"),
    ("push-status/no-key",
     ["push_addon_status.py", "--tenant", "acme", "--env", "dev"],
     {"PLATFORM_PUSH_KEY": ""}, "ERROR"),
    ("preflight/no-release",
     ["preflight_gitops_handoff.py", "nosuch-release", "-n", "nosuch-ns"],
     {"PATH": "/usr/bin:/bin"}, "ERROR"),
]


class TestARealPipeAgrees:
    """Run them the way the reader runs them: a real pipe, `stderr` discarded.

    Everything above reasons: nothing is written to stderr, therefore nothing can
    be lost on it, therefore buffering cannot matter. The reasoning is sound and
    it is still reasoning — and reasoning about what the reader receives is the
    thing this file exists because of.

    Not every REPORT CLI can be driven here: the rest need a cluster, a network or
    credentials to reach a failure path, and a guard that needs those is a guard
    that will be skipped, which is Risk 12② (skip and pass are the same colour).
    `PIPEABLE` is therefore the subset that can be driven from nothing — and
    `test_the_pipeable_set_is_not_quietly_shrinking` keeps it from being trimmed
    to whatever currently passes.
    """

    def _piped(self, argv: list[str], env: dict) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / argv[0]), *argv[1:]],
            cwd=REPO, capture_output=True, text=True, env={**os.environ, **env},
        )
        return proc.returncode, proc.stdout

    @pytest.mark.parametrize("label,argv,env,marker", PIPEABLE,
                             ids=[row[0] for row in PIPEABLE])
    def test_the_verdict_survives_a_real_pipe(self, label, argv, env, marker):
        code, out = self._piped(argv, env)
        assert code != 0, f"{label}: expected a failure path, got exit 0"
        assert marker in out, (
            f"{label}: through a real pipe with stderr discarded the reader got no "
            f"verdict — the `.err == ''` reasoning does not hold here. "
            f"stdout was: {out!r}"
        )

    def test_the_pipeable_set_is_not_quietly_shrinking(self):
        """6 invocations over 5 CLIs: **4 of the 17 REPORT** plus the report mode
        of one DUAL. Written down so shrinking it is an edit, not a drift.

        The other 13 REPORT CLIs are still covered by the `capsys` guards above.
        What they do not have is a real pipe behind them, and that limit belongs
        in writing rather than in the gap between two test names.
        """
        assert len(PIPEABLE) == 6
        covered = {argv[0] for _, argv, _, _ in PIPEABLE}
        assert len(covered) == 5
        # A DUAL CLI belongs here only via the mode where stdout is prose — hence
        # no `--json` anywhere in PIPEABLE. (Both assertions caught their own
        # author: first filing preflight under REPORT, then counting invocations
        # as if they were scripts.)
        assert covered <= REPORT | DUAL, f"unclassified: {sorted(covered - REPORT - DUAL)}"
        assert not any("--json" in argv for _, argv, _, _ in PIPEABLE), (
            "a --json invocation is a DOCUMENT stream; asserting prose on it would "
            "guard the opposite of the rule"
        )
        assert len(covered & REPORT) == 4 and len(covered & DUAL) == 1


class TestTheLibraryUsesTheSameDoor:
    """A stream is also chosen where no `print` appears.

    Found 2026-08-11, after the sweep above had already been called finished.
    `src/` contains no `sys.stderr` at all — and no logging handler either, which
    is the part that matters: an unhandled record falls through to Python's
    `logging.lastResort`, **which writes WARNING and above to stderr**. So a
    library warning lands on the stream the report is not on, by a route with no
    `print` in it, which is why sweeping `print`/`sys.stderr` could never find it.

    One REPORT CLI demonstrably hits this on its live path: `push_addon_status`
    calls into `collector._kubectl`, whose first invocation fires
    `warn_if_ambient_read` — "the spoke reads this cluster with the ambient kubectl
    context and filters tenants in code". The most security-relevant line the
    process emits, leaving by the wrong door. Today nothing is actually lost,
    because `make dev-up` redirects `2>&1` into one file — but "it happens to be
    captured together" is exactly the reasoning that made the netpol evidence logs
    look fine while the script was broken.
    """

    def test_an_ambient_read_warning_reaches_the_report(self):
        """Driven as a real subprocess so the logging config is the real one.

        In-process this would be meaningless: pytest installs its own handlers, so
        `lastResort` never runs and the bug is invisible — the same shape as the
        `capsys` blind spot, one layer down.
        """
        probe = (
            "import sys; sys.path.insert(0, '.');"
            "import scripts.push_addon_status as m;"          # noqa: E501
            "import src.agents.platform.collector as c;"
            "sys.argv = ['push', '--tenant', 'acme', '--env', 'dev', '--once'];"
            "m.push_once = lambda *a, **k: (c.warn_if_ambient_read(), (0, 'pushed'))[1];"
            "import os; os.environ['PLATFORM_PUSH_KEY'] = 'k';"
            "raise SystemExit(m.main())"
        )
        proc = subprocess.run(
            [sys.executable, "-c", probe], cwd=REPO, capture_output=True, text=True,
        )
        assert "collector.read.ambient" in proc.stdout, (
            "the ambient-read warning did not reach the report's stream. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        assert "collector.read.ambient" not in proc.stderr, (
            "the warning is still going out the logging door onto stderr"
        )


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
