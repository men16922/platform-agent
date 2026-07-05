"""
Provider adapters for signal normalization and execution resolution.
"""

from src.agents.adapters.base import ExecutionAdapter, SignalAdapter
from src.agents.adapters.registry import (
    get_execution_adapter,
    get_signal_adapter,
    supported_providers,
)

__all__ = [
    "ExecutionAdapter",
    "SignalAdapter",
    "get_execution_adapter",
    "get_signal_adapter",
    "supported_providers",
]
