"""One-shot live GKE provision with a HARD TTL teardown guard.

Provisions a small, short-lived GKE cluster through the same adapter path the
tests cover, then *guarantees* teardown so a cluster can never linger and rack
up cost. This exists because on 2026-06-24 a live test cluster was left up ~9h
(and 06-07 / 07-06 / 07-14 added more) — every one billed GKE mgmt + nodes +
a PSC/LB endpoint. The failure mode was twofold: the caller was trusted to run
teardown, and `clusters create` itself can *hang* (a GCE_STOCKOUT retried node
creation for 35min+ on 07-14) with the control plane already billing.

Three independent layers, so no single failure leaves a cluster running:

  1. try/finally     — normal completion, exceptions, and Ctrl-C all tear down.
  2. signal handlers — SIGTERM/SIGINT (e.g. the overnight loop killing us) tear
     down before exit.
  3. detached watchdog — a background `gcloud clusters delete` scheduled at now
     + TTL, ARMED BEFORE the (possibly hanging) create, in its own session so
     it survives even SIGKILL of this process. Canceled on clean teardown.

Escape hatch: --keep (or KEEP_CLUSTER=1) provisions and skips auto-teardown for
manual inspection — you then own the delete AND the cost (no watchdog).

Usage:
  GCP_PROJECT=<proj> python scripts/provision_gke_live.py [--ttl-min 30] [--keep]
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")

from pathlib import Path

# `python scripts/provision_gke_live.py` — the invocation this file's own docstring gives —
# died with ModuleNotFoundError until 2026-08-11: running a script puts
# `scripts/` on sys.path, not the repo root, so `from src...` never resolved.
# Every sibling that is actually exercised does this; these five were not.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.adapters.provisioning import ProvisionSpec, get_provisioning_adapter

_DEFAULT_TTL_MIN = int(os.getenv("GKE_LIVE_TTL_MIN", "30"))
_WATCHDOG_LOG = os.path.join(
    os.getenv("TMPDIR", "/tmp"), "gke-live-watchdog.log"
)


def _region(spec: ProvisionSpec) -> str:
    return spec.region or os.getenv("GCP_REGION", "asia-northeast3")


def _arm_watchdog(spec: ProvisionSpec, project: str, ttl_min: int) -> subprocess.Popen | None:
    """Detached backstop: force-delete the cluster at now+TTL, surviving even a
    SIGKILL of this process. Returns the handle so a clean teardown can cancel
    it. `start_new_session=True` puts it in its own process group (own session),
    so it is not killed when this script dies."""
    ttl_sec = max(60, ttl_min * 60)
    region = _region(spec)
    delete = (
        f"gcloud container clusters delete {spec.cluster_name} "
        f"--project {project} --region {region} --quiet"
    )
    # sleep then delete; log so a fired watchdog leaves a trace.
    script = (
        f'echo "[watchdog armed] {spec.cluster_name} will be force-deleted in '
        f'{ttl_min}min ($(date))" >> "{_WATCHDOG_LOG}"; '
        f"sleep {ttl_sec}; "
        f'echo "[watchdog FIRED] deleting {spec.cluster_name} ($(date))" >> "{_WATCHDOG_LOG}"; '
        f'{delete} >> "{_WATCHDOG_LOG}" 2>&1'
    )
    try:
        proc = subprocess.Popen(
            ["/bin/sh", "-c", script],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:  # pragma: no cover - defensive
        print(f"WARN: could not arm watchdog: {exc}", flush=True)
        return None
    print(
        f"watchdog armed (pid={proc.pid}, TTL={ttl_min}min) -> {_WATCHDOG_LOG}",
        flush=True,
    )
    return proc


def _cancel_watchdog(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            proc.terminate()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ttl-min", type=int, default=_DEFAULT_TTL_MIN,
                        help="hard TTL in minutes before the watchdog force-deletes")
    parser.add_argument("--keep", action="store_true",
                        default=os.getenv("KEEP_CLUSTER") == "1",
                        help="skip auto-teardown (you own the delete AND the cost)")
    args = parser.parse_args()

    project = os.getenv("GCP_PROJECT")
    if not project:
        print("ERROR: GCP_PROJECT not set", flush=True)
        return 2

    spec = ProvisionSpec(
        cluster_name="pa-gke-live",
        provider="gcp",
        region="us-central1",
        approved=True,
        node_count=1,
        node_size="e2-small",
    )
    adapter = get_provisioning_adapter("gcp")
    region = _region(spec)
    manual_delete = (
        f"gcloud container clusters delete {spec.cluster_name} "
        f"--project {project} --region {region} --quiet"
    )

    torn_down = {"done": False}

    def teardown(reason: str) -> None:
        if torn_down["done"] or args.keep:
            return
        torn_down["done"] = True
        print(f"\n[teardown: {reason}] deleting {spec.cluster_name}...", flush=True)
        tr = adapter.teardown_cluster(spec)
        print("TEARDOWN", tr.success, tr.error or "")
        if not tr.success:
            print(f"!! teardown failed — run manually:\n   {manual_delete}", flush=True)

    def _on_signal(signum, *_):
        teardown(f"signal {signal.Signals(signum).name}")
        _cancel_watchdog(watchdog)
        sys.exit(128 + signum)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    # Layer 3: arm the watchdog BEFORE create, so even a hanging/stuck create
    # (e.g. GCE_STOCKOUT) is reaped at TTL rather than billing indefinitely.
    watchdog = None if args.keep else _arm_watchdog(spec, project, args.ttl_min)

    try:
        print(f"provisioning GKE in project={project} (~5min)...", flush=True)
        r = adapter.provision_cluster(spec)
        print("SUCCESS", r.success)
        print("CONTEXT", r.context)
        print("ERROR", r.error)
        print("OUT:", (r.output or "")[-400:])
        return 0 if r.success else 1
    finally:
        # Layer 1: always tear down on any exit path (unless --keep).
        teardown("finally")
        _cancel_watchdog(watchdog)
        if args.keep:
            print(
                f"\n[--keep] cluster left running, NO watchdog. Delete when done:\n"
                f"   {manual_delete}",
                flush=True,
            )


if __name__ == "__main__":
    raise SystemExit(main())
