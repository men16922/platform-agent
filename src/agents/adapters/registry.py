"""
Provider adapter registry for portability scaffolding.
"""

from __future__ import annotations

from src.agents.adapters.base import ExecutionAdapter, SignalAdapter
from src.agents.adapters.execution.aws import AwsSsmExecutionAdapter
from src.agents.adapters.execution.azure import AzureExecutionAdapter
from src.agents.adapters.execution.gcp import GcpExecutionAdapter
from src.agents.adapters.execution.onprem import OnPremExecutionAdapter
from src.agents.adapters.signals.aws import AwsCloudWatchSignalAdapter
from src.agents.adapters.signals.azure import AzureMonitorSignalAdapter
from src.agents.adapters.signals.gcp import GcpMonitoringSignalAdapter
from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter

_SIGNAL_ADAPTERS: dict[str, SignalAdapter] = {
    "aws": AwsCloudWatchSignalAdapter(),
    "gcp": GcpMonitoringSignalAdapter(),
    "azure": AzureMonitorSignalAdapter(),
    "onprem": OnPremAlertmanagerSignalAdapter(),
}

_EXECUTION_ADAPTERS: dict[str, ExecutionAdapter] = {
    "aws": AwsSsmExecutionAdapter(),
    "gcp": GcpExecutionAdapter(),
    "azure": AzureExecutionAdapter(),
    "onprem": OnPremExecutionAdapter(),
}


def get_signal_adapter(provider: str) -> SignalAdapter:
    try:
        return _SIGNAL_ADAPTERS[provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported signal adapter provider: {provider}") from exc


def get_execution_adapter(provider: str) -> ExecutionAdapter:
    try:
        return _EXECUTION_ADAPTERS[provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported execution adapter provider: {provider}") from exc


def supported_providers() -> list[str]:
    return sorted(set(_SIGNAL_ADAPTERS) & set(_EXECUTION_ADAPTERS))
