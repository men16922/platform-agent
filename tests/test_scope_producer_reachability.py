"""A mechanism whose only producer is the test suite is green forever.

`guard_scoped_action` refuses without an `IncidentScope`. Seventeen tests exercise
that gate, and every one of them mints its own scope with `sign_approval`. So the
suite proves the gate works and says nothing about whether anything can open it.

Measured 2026-07-30: nothing can. No signal adapter writes
`source_metadata["attested_approval"]`, `sign_approval` has no caller in `src/`, and
neither broker environment variable is set by any stack, script or Makefile. Every
real incident therefore resolves to `None` and every live remediation is refused —
fail-closed, which is safe, but it means the repo's headline invariant
("blast radius = 1 tenant/env, enforced") describes a closed door.

This is the M13 lesson at the level of a whole subsystem rather than a field:
**assert the consumer, not the producer** — and when the producer is the test
fixture, the absence of a real producer never shows up.

So this file asserts the *reachability state itself*, and it is load-bearing in both
directions:

  * while the mechanism is closed, the seam must SAY so — a reader who finds
    `guard_scoped_action` and the live isolation evidence would otherwise
    reasonably conclude scoping is operational;
  * the moment someone adds a real producer, the broker's credentials must be
    provisioned too, or they will have wired a path that fails closed in production
    while passing here.

Deliberately NOT asserted: that a producer must exist. Which side to close first is
결정 5 — `docs/plans/2026-07-30-deploy-request-tenant-scoping.md`. Re-measure with
`scripts/probe_scope_reachability.py`.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
SCOPE_PY = REPO / "src" / "agents" / "platform" / "scope.py"
SIGNAL_DIR = REPO / "src" / "agents" / "adapters" / "signals"

BROKER_ENV_VARS = ("PLATFORM_CREDENTIAL_DIR", "PLATFORM_APPROVAL_SIGNING_KEY")

#: Where a production setter could legitimately live. Derived over the trees rather
#: than a file list, so a new stack or entrypoint is covered without editing this.
PRODUCTION_TREES = ("src", "scripts")
SKIP_DIR_PARTS = {"cdk.out", "__pycache__", "node_modules", ".git"}


def _production_files():
    for tree in PRODUCTION_TREES:
        root = REPO / tree
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and not SKIP_DIR_PARTS & set(path.parts):
                if path.suffix in {".py", ".ts", ".sh", ".json", ".yaml", ".yml", ""}:
                    yield path
    for name in ("Makefile",):
        candidate = REPO / name
        if candidate.exists():
            yield candidate


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def _code_lines(path):
    """Lines that are code, not comments. Cheap, and enough for this question."""
    for n, raw in enumerate(_read(path).splitlines(), 1):
        stripped = raw.lstrip()
        if stripped and not stripped.startswith(("#", "*", "//", '"""', "'''")):
            yield n, raw


#: Every way production code can cause an attestation to be minted. `sign_approval`
#: is the primitive; `attest_decision` is the seam that calls it and attaches the
#: record to an incident. Both count, because "is the mechanism reachable" is a
#: question about the *chain*, not about one function name.
#:
#: This list started as `{"sign_approval"}` and was wrong within the hour: the
#: producer was added as `attest_decision` inside `scope.py` — which this sweep skips
#: as the definition site — so the guard reported "no producer" while production
#: could plainly mint one. Detecting a mechanism by a single symbol name is the same
#: brittleness as enumerating boundaries instead of deriving them.
PRODUCER_ENTRYPOINTS = ("sign_approval", "attest_decision")


def _scope_producers():
    """Production **call sites** that can mint an attestation.

    A call, not a mention: `scripts/probe_scope_reachability.py` names these symbols
    inside grep arguments to *measure* this, and a tool that reports the absence of a
    producer must not be counted as one. (It was, on the first run.)
    """
    pattern = re.compile(r"\b(" + "|".join(PRODUCER_ENTRYPOINTS) + r")\s*\(")
    hits = []
    for path in _production_files():
        if path == SCOPE_PY:
            continue  # its own definition
        for n, line in _code_lines(path):
            if pattern.search(line):
                hits.append(f"{path.relative_to(REPO)}:{n}")
    return hits


def _attested_writers():
    """Production code that **puts** the key onto an incident (scope.py only reads it).

    A write, again not a mention — `"attested_approval":` in a dict literal or
    `[...] =` assignment. The probe's grep argument is neither.
    """
    hits = []
    for path in _production_files():
        if path == SCOPE_PY:
            continue
        for n, line in _code_lines(path):
            if re.search(r"""["']attested_approval["']\s*(:|\]\s*=)""", line):
                hits.append(f"{path.relative_to(REPO)}:{n}")
    return hits


def _env_setters(var):
    """Anything that assigns the variable, as opposed to reading its name."""
    hits = []
    for path in _production_files():
        if path == SCOPE_PY:
            continue
        for n, line in enumerate(_read(path).splitlines(), 1):
            if var not in line:
                continue
            # An assignment, an export, an env-block entry — not a getenv lookup.
            if re.search(rf"""(export\s+)?{var}\s*[:=]|["']{var}["']\s*:""", line):
                hits.append(f"{path.relative_to(REPO)}:{n}")
    return hits


class TestTheClosedDoorIsDocumentedAtTheSeam:
    """While no producer exists, `scope.py` must say so where it is read."""

    def test_the_module_states_that_no_production_caller_mints_a_scope(self):
        if _scope_producers():
            return  # a producer exists; the caveat is allowed to be gone
        src = _read(SCOPE_PY)
        assert re.search(r"NO PRODUCTION CALLER MINTS A SCOPE", src), (
            "no production code can mint an IncidentScope, and scope.py does not say so. "
            "A reader who finds guard_scoped_action plus the live isolation evidence will "
            "conclude scoping is operational — it is a closed door."
        )

    def test_the_caveat_points_at_a_way_to_re_measure(self):
        if _scope_producers():
            return
        src = _read(SCOPE_PY)
        assert "probe_scope_reachability" in src, (
            "the caveat is prose with no way to check it — the state it describes will "
            "drift exactly like the read model in M13 ⑪ did"
        )
        assert (REPO / "scripts" / "probe_scope_reachability.py").is_file()

    def test_no_signal_adapter_silently_started_attesting(self):
        """If one begins writing the key, the caveat above is stale and must be revisited."""
        writers = [h for h in _attested_writers() if "adapters/signals" in h]
        if not writers:
            return
        assert not re.search(r"NO PRODUCTION CALLER MINTS A SCOPE", _read(SCOPE_PY)), (
            f"{writers} now attests incidents, but scope.py still says nothing can. "
            "Update the caveat — and check the broker credentials are provisioned."
        )


class TestAProducerWithoutCredentialsWouldFailClosedInProduction:
    """The trap waiting for whoever closes this: attest the incident, ship it, and
    discover the broker still refuses because `from_env` has nothing to read.

    `TokenBroker.from_env` raises when either variable is unset, and
    `resolve_incident_scope` swallows that into `None`. So the failure is a log line
    on a path that already logs one — the least visible place for it to land.
    """

    def test_if_something_attests_then_the_broker_credentials_are_provisioned(self):
        producers = _scope_producers()
        if not producers:
            return  # nothing attests yet — 결정 5
        missing = [var for var in BROKER_ENV_VARS if not _env_setters(var)]
        assert not missing, (
            f"{producers} mints attested approvals, but {missing} is not set by any "
            "stack, script or Makefile. TokenBroker.from_env fails closed and "
            "resolve_incident_scope swallows it into None, so every live remediation "
            "would still be refused — and the only signal is one more log line on a "
            "path that already logs one."
        )

    def test_the_gate_still_refuses_a_none_scope(self):
        """The one behaviour this whole file depends on. Cheap to assert, and it is
        what makes an unreachable producer safe rather than catastrophic."""
        from src.agents.platform.scope import ScopeError, guard_scoped_action

        class _Log:
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        try:
            guard_scoped_action(action="restart_workload", namespace="acme-dev-logging",
                                scope=None, log=_Log(), log_prefix="onprem_runner")
        except ScopeError:
            return
        raise AssertionError(
            "guard_scoped_action permitted an action with no scope — with no producer "
            "in production that would make every remediation run on ambient credentials"
        )


class TestARealIncidentIsTheFixture:
    """The suite's scopes are hand-built; this one comes from the real adapter.

    M13's second lesson — fixtures from real input, not from what the code expects —
    is why this is here rather than a hand-made NormalizedIncident.
    """

    def test_a_real_alertmanager_incident_carries_no_attestation(self):
        from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter

        incident = OnPremAlertmanagerSignalAdapter().normalise({
            "status": "firing",
            "alerts": [{
                "labels": {"alertname": "PodCrashLooping", "namespace": "acme-dev-logging",
                           "pod": "loki-gateway-0", "tenant": "acme", "env": "dev"},
                "annotations": {"summary": "pod restarting"},
                "startsAt": "2026-07-30T00:00:00Z",
            }],
        })
        metadata = incident.source_metadata or {}
        # The tenant IS known — which is what makes the gap subtle. Attribution is
        # present; the *credential* the gate needs is not.
        assert incident.tenant == "acme"
        if "attested_approval" in metadata:
            assert _scope_producers(), (
                "an incident carries an attestation that no production code produces"
            )

    def test_the_resolver_returns_none_for_it_unless_a_producer_exists(self):
        from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter
        from src.agents.platform.scope import resolve_incident_scope

        class _Log:
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        incident = OnPremAlertmanagerSignalAdapter().normalise({
            "status": "firing",
            "alerts": [{"labels": {"alertname": "X", "tenant": "acme", "env": "dev"},
                        "annotations": {}, "startsAt": "2026-07-30T00:00:00Z"}],
        })
        scope = resolve_incident_scope(incident, _Log())
        if scope is None:
            return
        assert _scope_producers(), (
            "a scope was minted from a real incident, but nothing in production attests "
            "one — the caveat in scope.py is now wrong"
        )
