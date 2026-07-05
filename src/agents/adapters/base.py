"""
Common adapter contracts for provider-specific integrations.
"""

from __future__ import annotations

from typing import Any

from src.agents.models import NormalizedIncident


class SignalAdapter:
    provider = "unknown"

    def normalise(self, event: dict[str, Any]) -> NormalizedIncident:
        raise NotImplementedError

    def collect_observations(self, incident: NormalizedIncident) -> dict[str, Any]:
        return incident.observations


class ExecutionAdapter:
    provider = "unknown"

    def resolve_action(self, capability: str, incident: NormalizedIncident) -> dict[str, Any]:
        raise NotImplementedError
