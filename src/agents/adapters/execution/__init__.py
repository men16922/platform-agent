"""
Execution adapters.
"""

from src.agents.adapters.execution.aws import AwsSsmExecutionAdapter
from src.agents.adapters.execution.azure import AzureExecutionAdapter
from src.agents.adapters.execution.gcp import GcpExecutionAdapter
from src.agents.adapters.execution.onprem import OnPremExecutionAdapter

__all__ = [
    "AwsSsmExecutionAdapter",
    "AzureExecutionAdapter",
    "GcpExecutionAdapter",
    "OnPremExecutionAdapter",
]
