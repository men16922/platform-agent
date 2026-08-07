"""The push model bounds what a spoke WRITES, not what it READS. Say which.

`collector` opens by claiming the hub holds zero spoke credentials — true, and the
reason the direction was chosen. It then used to add that "a spoke agent's blast
radius is one tenant/env on the read path too", which is the part that was not
true and is what this file pins.

Measured 2026-08-02 (`docs/evidence/push-identity-ambient.log`):

  write side, live against the real hub route — enforced
      valid signature                        -> 200
      no signature                           -> 401
      wrong key                              -> 401
      globex's key claiming acme             -> 401
      acme's key carrying a globex row       -> 401 "carries rows for ['globex/dev']"

  read side — not enforced by a credential
      `_kubectl` shells out to a bare `kubectl`: no --kubeconfig, no --context
      it reads `applications.argoproj.io -n argocd`, a SHARED namespace holding
      every tenant's Applications, and confines to one tenant afterwards in Python
      there is no in-cluster manifest for the spoke at all (infra/helm has router,
      webhook, orphan-sweeper — no status pusher), so it runs from the Makefile
      against the operator's ambient context, which on kind is cluster-admin

That is the same shape D38 found on the deploy path. It is left as a warning rather
than a refusal for the same reason D38 did: fail-closed here breaks `make dev-up`
and the two-line demo, and a boundary nobody can run is the failure this repo has
already documented once. What is NOT acceptable is the silence — hence
`warn_if_ambient_read`, and hence these tests.

The plan's `2차 잔여` listed "agent→hub push 인증" as open. It has been done since
2026-07-26 and is re-measured above; what is actually open is the spoke's own
identity, which is a different item and now says so.
"""

from __future__ import annotations

import pytest

from src.agents.platform import collector


class _Recorder:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, *args, **kwargs) -> None:
        self.warnings.append(message)


@pytest.fixture(autouse=True)
def _reset_warned(monkeypatch):
    """Module-level latch, so each test starts from 'has not spoken yet'."""
    monkeypatch.setattr(collector, "_warned_ambient", False)


def test_the_spoke_says_out_loud_that_its_read_is_ambient():
    log = _Recorder()

    assert collector.warn_if_ambient_read(log) is True
    assert len(log.warnings) == 1
    message = log.warnings[0]
    assert "ambient" in message
    assert "boundary is not the credential" in message, (
        "the warning must name what is NOT enforced; 'reading with default config' "
        "would read as a configuration note rather than a boundary statement"
    )


def test_it_says_it_once_not_once_a_minute():
    """`push_addon_status.py --interval 60` loops forever; a per-read warning would
    turn a real statement into log noise nobody reads."""
    log = _Recorder()

    assert collector.warn_if_ambient_read(log) is True
    assert collector.warn_if_ambient_read(log) is False
    assert collector.warn_if_ambient_read(log) is False
    assert len(log.warnings) == 1


def test_the_cluster_read_actually_goes_through_the_warning():
    """Asserted behaviourally: the warning is worthless if `_kubectl` bypasses it.

    This is the trap the D38/D40 family kept springing — a correct mechanism with
    nothing calling it. Here the caller is the one thing that must not be missed,
    so it is exercised rather than read.
    """
    log = _Recorder()
    calls: list[tuple[str, ...]] = []

    class _Proc:
        returncode = 1
        stdout = ""

    def fake_run(cmd, **kwargs):
        calls.append(tuple(cmd))
        return _Proc()

    import src.agents.platform.collector as mod

    original_logger = mod.logging.getLogger
    mod.logging.getLogger = lambda *a, **k: log  # noqa: E731
    original_run = mod.subprocess.run
    mod.subprocess.run = fake_run
    try:
        mod._kubectl("get", "pods")
    finally:
        mod.subprocess.run = original_run
        mod.logging.getLogger = original_logger

    assert calls and calls[0][0] == "kubectl"
    assert "--kubeconfig" not in calls[0], (
        "the read is now pinned to a credential — good, but then the warning and "
        "the collector docstring are both stale and must move with it"
    )
    assert len(log.warnings) == 1, "the cluster read did not announce its identity"
