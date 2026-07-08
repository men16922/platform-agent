"""
Backward compatibility — re-exports from onprem.py.

Use 'onprem' as the canonical provider name. This module exists
so that existing imports from 'deployment.local' continue to work.
"""

from src.agents.adapters.deployment.onprem import (  # noqa: F401
    OnPremBuildAdapter as LocalBuildAdapter,
    OnPremClusterAdapter as LocalClusterAdapter,
    OnPremRegistryAdapter as LocalRegistryAdapter,
)
