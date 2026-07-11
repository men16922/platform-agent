"""
Shared data models for the incident response pipeline.

Each agent receives an IncidentEvent and passes an enriched version downstream.
Step Functions serialises / deserialises these as JSON at each state boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import json


class Severity(str, Enum):
    P1 = "P1"   # Critical — auto-execute remediation
    P2 = "P2"   # High     — auto-execute with Slack approval gate
    P3 = "P3"   # Medium   — human approval required


class RemediationMode(str, Enum):
    AUTO   = "AUTO"    # execute without human approval
    APPROVE = "APPROVE" # send Slack approval request first
    MANUAL = "MANUAL"  # create ticket only


@dataclass
class AlarmContext:
    alarm_name: str
    alarm_arn:  str
    state:      str          # ALARM | OK | INSUFFICIENT_DATA
    reason:     str
    metric_name: str
    namespace:  str
    dimensions: dict[str, str] = field(default_factory=dict)
    triggered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class NormalizedIncident:
    """
    Cloud-neutral incident envelope for portability across AWS, GCP, Azure,
    and on-prem adapters.
    """

    provider: str
    service: str
    resource_type: str
    resource_id: str
    signal_type: str
    severity_hint: str | None = None
    observations: dict[str, Any] = field(default_factory=dict)
    recommended_capabilities: list[str] = field(default_factory=list)
    source_metadata: dict[str, Any] = field(default_factory=dict)
    triggered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DetectorOutput:
    alarm: AlarmContext
    log_insights_results: list[dict[str, Any]] = field(default_factory=list)
    xray_trace_ids:       list[str]            = field(default_factory=list)
    related_metrics:      dict[str, float]     = field(default_factory=dict)
    normalized_incident:  NormalizedIncident | None = None


@dataclass
class AnalyzerOutput:
    detector: DetectorOutput
    root_cause:    str
    severity:      Severity
    confidence:    float         # 0.0 – 1.0
    similar_incidents: list[str] = field(default_factory=list)  # past incident IDs


@dataclass
class DecisionOutput:
    analyzer: AnalyzerOutput
    runbook_id:        str
    remediation_mode:  RemediationMode
    actions:           list[str]     = field(default_factory=list)  # SSM doc names / kubectl cmds
    estimated_rto_sec: Optional[int] = None


@dataclass
class ExecutorOutput:
    decision:     DecisionOutput
    executed_actions: list[str] = field(default_factory=list)
    skipped_actions:  list[str] = field(default_factory=list)
    slack_ts:         Optional[str] = None   # Slack message timestamp
    incident_id:      str = ""
    resolved:         bool = False


# ------------------------------------------------------------------
# Serialisation helpers (Step Functions ↔ Python)
# ------------------------------------------------------------------

def to_json(obj: Any) -> str:
    """Recursively serialise dataclasses to JSON-serialisable dict."""
    return json.dumps(_to_dict(obj))


def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


# ------------------------------------------------------------------
# Deployment models (re-exported from adapters.deployment.base)
# ------------------------------------------------------------------

# Intentional re-export surface: `from src.agents.models import ServiceSpec`.
# noqa: F401 keeps ruff --fix from pruning these as "unused" (usage is the
# public re-export, not a local reference); E402 allows the mid-file import.
from src.agents.adapters.deployment.base import (  # noqa: E402, F401
    BuildResult,
    DeployResult,
    DeployStatus,
    PushResult,
    RollbackResult,
    ServiceSpec,
    ValidationResult,
)

__all_deployment__ = [
    "ServiceSpec",
    "BuildResult",
    "PushResult",
    "DeployResult",
    "DeployStatus",
    "ValidationResult",
    "RollbackResult",
]
