"""
Signal normalization adapters.
"""

from src.agents.adapters.signals.aws import AwsCloudWatchSignalAdapter
from src.agents.adapters.signals.azure import AzureMonitorSignalAdapter
from src.agents.adapters.signals.gcp import GcpMonitoringSignalAdapter
from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter

__all__ = [
    "AwsCloudWatchSignalAdapter",
    "AzureMonitorSignalAdapter",
    "GcpMonitoringSignalAdapter",
    "OnPremAlertmanagerSignalAdapter",
]
