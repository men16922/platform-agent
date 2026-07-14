"""Agent-runtime hosting adapters — managed runtime for built agents (④ Host role)."""

from src.agents.adapters.runtime.base import (
    RuntimeHostingAdapter,
    RuntimeResult,
    RuntimeSpec,
)
from src.agents.adapters.runtime.registry import (
    get_runtime_adapter,
    supported_runtime_providers,
)

__all__ = [
    "RuntimeHostingAdapter",
    "RuntimeResult",
    "RuntimeSpec",
    "get_runtime_adapter",
    "supported_runtime_providers",
]
