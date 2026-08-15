"""
The gate does not reach the network — enforced, not hoped for.

D45 already decided this ("게이트는 라이브 클라우드에 의존하지 않는다") and nothing
enforced it, so it had stopped being true. Measured 2026-08-15:

    tests/test_gcp_day2_operations.py     200.66s
    tests/test_azure_day2_operations.py     0.43s     (same 28 tests)

`gcp/analyzer.py::_analyse` does ``import vertexai`` inside the function. The
package **is** installed, so the ``except ImportError`` fallback never fired and
the call went out for real:

    POST https://us-central1-aiplatform.googleapis.com/v1/projects/<project>/
         .../gemini-2.5-flash:generateContent  ->  200

i.e. every gate run on a credentialed machine billed Vertex AI, once per test.
The same single test:

    with gcloud credentials      16.55s   (live, billable)
    with credentials hidden       0.90s   (fallback)
    ...and it passes identically either way.

Which is the worse half. The assertions never needed the model, so **the gate
exercised a different code path depending on what happened to be authenticated
on the machine running it** — Risk 12② ("환경"), invisible because both paths are
green. Azure looked fine only because no Azure credentials are configured here;
its test has the same hole. AWS's analyzer tests mock properly and were always
fast, which is why this never showed up as a whole-suite number.

So this blocks egress rather than mocking three providers one at a time: the
invariant is "the gate does not depend on live cloud", and that is a property of
the suite, not of whichever SDK a module happens to import today.

Loopback stays open — the on-prem webhook tests bind and call real local ports.
A blocked call names where it tried to go, so a violating test says so instead of
timing out.
"""

from __future__ import annotations

import socket

import pytest

_ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost", "0.0.0.0", ""}

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


class OutboundNetworkBlocked(RuntimeError):
    """A test tried to reach the network. The gate must not."""


def _host_of(address: object) -> str | None:
    """The host from a connect() address, or None when it is not IP-based."""
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None  # AF_UNIX and friends — not our concern


def _check(address: object) -> None:
    host = _host_of(address)
    if host is None or host in _ALLOWED_HOSTS:
        return
    raise OutboundNetworkBlocked(
        f"outbound connection to {host!r} blocked — the gate must not depend on "
        "live cloud (D45). Mock the client, or force the module's documented "
        "offline fallback. See tests/conftest.py."
    )


@pytest.fixture(autouse=True, scope="session")
def _no_outbound_network():
    def guarded_connect(self, address):
        _check(address)
        return _real_connect(self, address)

    def guarded_connect_ex(self, address):
        _check(address)
        return _real_connect_ex(self, address)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    try:
        yield
    finally:
        socket.socket.connect = _real_connect
        socket.socket.connect_ex = _real_connect_ex
