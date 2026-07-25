"""
Guards for the incident → trace deep link (dashboard).

There is no JS test runner in this repo (TS is guarded by `tsc --noEmit`), so
these assert the source contract the way the add-on guards assert Terraform/YAML.

The contract that matters is prod-safety, and it is the same lesson
`stack-links.ts` already learned: a localhost link rendered in production is a
dead link, and a dead link is worse than no link — it reads as "the trace is
missing" when the truth is "tracing was off".
"""

from __future__ import annotations

from pathlib import Path

import pytest

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard" / "src"
TRACE_LINKS = DASHBOARD / "lib" / "trace-links.ts"
INCIDENT_DETAIL = DASHBOARD / "app" / "incidents" / "[id]" / "page.tsx"
INCIDENT_DATA = DASHBOARD / "lib" / "incident-data.ts"
MOCK_DATA = DASHBOARD / "lib" / "mock-data.ts"


def _source(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


class TestProdSafety:
    def test_localhost_fallback_is_dev_only(self):
        """Same rule as stack-links: prod shows a link only when configured."""
        source = _source(TRACE_LINKS)
        assert 'process.env.NODE_ENV !== "production"' in source
        assert "localhost" in source, "dev fallback keeps the demo working out of the box"
        # The dev flag must actually gate the fallback, not just exist.
        assert "dev ?" in source

    def test_env_var_is_referenced_literally(self):
        """NEXT_PUBLIC_* are inlined at build time; a dynamic lookup silently yields undefined."""
        assert "process.env.NEXT_PUBLIC_GRAFANA_URL" in _source(TRACE_LINKS)

    def test_missing_trace_or_grafana_yields_no_link(self):
        source = _source(TRACE_LINKS)
        # Two explicit null returns: no trace id, and no configured base URL.
        assert source.count("return null") >= 2

    def test_url_targets_the_tempo_datasource(self):
        source = _source(TRACE_LINKS)
        assert "tempo" in source
        assert "/explore?left=" in source, "Grafana Explore takes its state in `left`"

    def test_query_value_is_encoded(self):
        """The pane is JSON in a query param; unencoded braces break the link."""
        assert "encodeURIComponent" in _source(TRACE_LINKS)


class TestRendering:
    def test_detail_page_renders_the_link_conditionally(self):
        source = _source(INCIDENT_DETAIL)
        assert "getTraceUrl" in source
        assert "{traceUrl && (" in source, "must not render an anchor when there is no URL"

    def test_link_opens_safely_in_a_new_tab(self):
        source = _source(INCIDENT_DETAIL)
        assert 'target="_blank"' in source
        assert 'rel="noreferrer"' in source

    def test_short_id_is_used_for_display(self):
        """A 32-char hex id would blow out the layout."""
        assert "shortTraceId" in _source(INCIDENT_DETAIL)


class TestTypeAndFeed:
    def test_incident_type_carries_trace_id_optionally(self):
        source = _source(MOCK_DATA)
        assert "trace_id?: string;" in source, "optional: tracing is opt-in, so absence is normal"

    def test_feed_maps_trace_id_and_drops_empties(self):
        source = _source(INCIDENT_DATA)
        assert "trace_id" in source
        # An empty string must become undefined, or the UI would try to link to "".
        assert 'typeof item.trace_id === "string" && item.trace_id' in source


class TestBackendPersistsTraceId:
    def test_record_incident_accepts_and_stores_it(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(tmp_path / "incidents.jsonl"))
        monkeypatch.delenv("PLATFORM_STATE_DSN", raising=False)
        from src.agents.ai import onprem_incidents

        record = onprem_incidents.record_incident(
            severity="P2", alarm_name="api", root_cause="oom", runbook_id="eks-pod-oom",
            remediation_mode="APPROVE", resolved=False, trace_id="3c9da1037da6a04a73ad194c085a2405",
        )
        assert record["trace_id"] == "3c9da1037da6a04a73ad194c085a2405"

    def test_absent_trace_id_is_none_not_empty_string(self, tmp_path, monkeypatch):
        """None distinguishes "tracing was off" from "there is a trace, id unknown"."""
        monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(tmp_path / "incidents.jsonl"))
        monkeypatch.delenv("PLATFORM_STATE_DSN", raising=False)
        from src.agents.ai import onprem_incidents

        record = onprem_incidents.record_incident(
            severity="P2", alarm_name="api", root_cause="oom", runbook_id="rb",
            remediation_mode="APPROVE", resolved=False,
        )
        assert record["trace_id"] is None


@pytest.mark.parametrize("path", [TRACE_LINKS, INCIDENT_DETAIL, INCIDENT_DATA, MOCK_DATA])
def test_sources_exist(path):
    assert path.is_file()
