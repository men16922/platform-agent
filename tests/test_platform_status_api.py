"""
Guards for the hub half of the push collector (local_deploy_api).

The endpoint is small; what it must never do is large. An ingest endpoint for
operational status is an attractive write target — status is what humans act on,
so writing it is a way to steer them — and its failure modes are quiet by nature:
accepting an unsigned report, or serving data it can no longer vouch for.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

import src.agents.ai.local_deploy_api as api
from src.agents.ai.local_deploy_api import app
from src.agents.platform.collector import StatusStore, build_report, sign
from src.agents.platform.registry import load_registry

KEY = "test-key"
KEYS = json.dumps({"acme/dev": KEY, "globex/dev": "other-key"})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PLATFORM_PUSH_KEYS", KEYS)
    # Fresh store per test: the module-level one would leak state between tests
    # and make a rejected push look accepted because an earlier test's push is
    # still there.
    monkeypatch.setattr(api, "_status_store", StatusStore())
    return TestClient(app)


def _payload(sync: str = "Synced", health: str = "Healthy") -> dict:
    tenant = load_registry().tenant("acme")
    application = {
        "metadata": {"labels": {"platform-agent.io/capability": "observability"}},
        "spec": {"source": {"targetRevision": "87.17.0"}},
        "status": {"sync": {"status": sync}, "health": {"status": health}},
    }
    return build_report(tenant, "dev", [application], now=time.time()).to_dict()


class TestIngest:
    def test_signed_report_is_accepted(self, client):
        payload = _payload()
        response = client.post(
            "/api/platform/status", json=payload,
            headers={"X-Platform-Signature": sign(payload, KEY)},
        )
        assert response.status_code == 200
        assert response.json()["accepted"] == "acme/dev"

    def test_unsigned_report_is_rejected(self, client):
        assert client.post("/api/platform/status", json=_payload()).status_code == 401

    def test_report_signed_with_another_tenants_key_is_rejected(self, client):
        payload = _payload()
        response = client.post(
            "/api/platform/status", json=payload,
            headers={"X-Platform-Signature": sign(payload, "other-key")},
        )
        assert response.status_code == 401

    def test_hub_with_no_keys_accepts_nothing(self, client, monkeypatch):
        """An unconfigured hub must be closed, not open.

        The tempting default — "no keys configured, so skip the check" — turns
        every deployment that forgets the env var into an open write endpoint.
        """
        monkeypatch.delenv("PLATFORM_PUSH_KEYS")
        payload = _payload()
        response = client.post(
            "/api/platform/status", json=payload,
            headers={"X-Platform-Signature": sign(payload, KEY)},
        )
        assert response.status_code == 503

    def test_signer_cannot_write_another_tenants_rows(self, client):
        payload = _payload()
        payload["statuses"][0]["tenant"] = "globex"
        response = client.post(
            "/api/platform/status", json=payload,
            headers={"X-Platform-Signature": sign(payload, KEY)},
        )
        assert response.status_code == 401


class TestRead:
    def test_pushed_status_reads_back_on_both_axes(self, client):
        payload = _payload(sync="OutOfSync", health="Healthy")
        client.post("/api/platform/status", json=payload,
                    headers={"X-Platform-Signature": sign(payload, KEY)})

        body = client.get("/api/platform/status").json()
        row = next(r for r in body["statuses"] if r["capability"] == "observability")
        assert row["sync_state"] == "drifted"
        assert row["health_state"] == "healthy"

    def test_empty_hub_reports_who_it_has_never_heard_from(self, client):
        """The silent failure this endpoint exists to break: a drift view that lists
        only what it received is emptiest exactly when everything is dark."""
        body = client.get("/api/platform/status").json()
        assert body["statuses"] == []
        assert "acme/dev" in body["missing"]

    def test_freshness_is_exposed_so_staleness_is_visible(self, client):
        payload = _payload()
        client.post("/api/platform/status", json=payload,
                    headers={"X-Platform-Signature": sign(payload, KEY)})
        body = client.get("/api/platform/status").json()
        assert body["freshness"][0]["identity"] == "acme/dev"
        assert body["freshness"][0]["stale"] is False
        assert body["stale_after_sec"] > 0

    def test_the_hub_never_reads_a_spoke(self):
        """Structural, not behavioural: the invariant is 'no outbound path exists'.

        A test that merely observes no call was made would pass a hub that calls out
        only on the branch the test did not take.
        """
        source = api.__file__
        with open(source, encoding="utf-8") as handle:
            body = handle.read()
        marker = '@app.post("/api/local-deploy"'
        section = body.split("# --- platform status")[1].split(marker)[0]
        assert len(section) < len(body) / 2, "section markers stopped matching the source"
        for outbound in ("requests.get", "urlopen", "kubectl", "httpx"):
            assert outbound not in section, (
                f"the hub's status section must not reach out ({outbound} found)"
            )
