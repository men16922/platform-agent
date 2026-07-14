"""One-shot live GKE provision via the GcpProvisionAdapter (auditable helper).

Mirrors how AKS was validated live. Provisions a small, short-lived GKE cluster
through the same adapter path the tests cover, prints the result, and leaves
teardown to the caller (the adapter's teardown_cluster / gcloud delete).

Usage: GCP_PROJECT=<proj> python scripts/provision_gke_live.py
"""

from __future__ import annotations

import os
import warnings

warnings.filterwarnings("ignore")

from src.agents.adapters.provisioning import ProvisionSpec, get_provisioning_adapter


def main() -> None:
    spec = ProvisionSpec(
        cluster_name="pa-gke-live",
        provider="gcp",
        region="us-central1",
        approved=True,
        node_count=1,
        node_size="e2-small",
    )
    print(f"provisioning GKE in project={os.getenv('GCP_PROJECT')} (~5min)...", flush=True)
    r = get_provisioning_adapter("gcp").provision_cluster(spec)
    print("SUCCESS", r.success)
    print("CONTEXT", r.context)
    print("ERROR", r.error)
    print("OUT:", (r.output or "")[-400:])


if __name__ == "__main__":
    main()
