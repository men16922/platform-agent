"""Prove — empirically — that this cluster's CNI actually ENFORCES NetworkPolicy.

Why this exists: applying a NetworkPolicy to a CNI that ignores it is worse than
applying nothing. The objects exist, `kubectl get netpol` looks healthy, any audit
or dashboard reads "isolated", and traffic flows anyway. That is a false green on
a security control, and the only honest way to rule it out is an experiment.

Support is substrate-dependent and moves over time (kind's kindnet historically
did not enforce policies; newer kindnetd does; k3s ships flannel), so this probe
answers the question for *the cluster in front of you* rather than trusting a
version table.

Method (all in a throwaway namespace pair, cleaned up on exit):
  1. Create ns A (server) and ns B (client), unlabelled.
  2. Confirm B -> A works with NO policy    -> baseline connectivity exists.
  3. Apply a default-deny-ingress policy in A.
  4. Confirm B -> A now FAILS               -> the CNI enforces.
If step 2 fails the probe is inconclusive (cluster/image problem), not a pass —
never report ENFORCED from an experiment whose control did not work.

Usage: python scripts/verify_netpol_enforcement.py [--keep]
Exit codes: 0 = ENFORCED, 1 = NOT ENFORCED, 2 = inconclusive/error.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

_SERVER_NS = "netpol-probe-server"
_CLIENT_NS = "netpol-probe-client"
_IMAGE = "registry.k8s.io/e2e-test-images/agnhost:2.47"


def _kubectl(*args: str, check: bool = False, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["kubectl", *args], capture_output=True, text=True, check=check, timeout=timeout
    )


def _apply(manifest: dict) -> None:
    proc = subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=json.dumps(manifest),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"apply failed: {proc.stderr.strip()}")


def _namespace(name: str) -> dict:
    return {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": name}}


def _server_pod() -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "server", "namespace": _SERVER_NS, "labels": {"app": "server"}},
        "spec": {
            "containers": [
                {
                    "name": "server",
                    "image": _IMAGE,
                    "args": ["netexec", "--http-port=8080"],
                    "ports": [{"containerPort": 8080}],
                    "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}},
                }
            ]
        },
    }


def _service() -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "server", "namespace": _SERVER_NS},
        "spec": {
            "selector": {"app": "server"},
            "ports": [{"port": 8080, "targetPort": 8080}],
        },
    }


def _deny_all_ingress() -> dict:
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "default-deny-ingress", "namespace": _SERVER_NS},
        # No `ingress` rules at all = deny every inbound connection.
        "spec": {"podSelector": {}, "policyTypes": ["Ingress"]},
    }


def _wait_ready(namespace: str, selector: str, timeout_sec: int = 180) -> bool:
    proc = _kubectl(
        "wait", "-n", namespace, "--for=condition=Ready", "pod", "-l", selector,
        f"--timeout={timeout_sec}s", timeout=timeout_sec + 30,
    )
    return proc.returncode == 0


def _can_reach(timeout_sec: int = 8) -> bool:
    """Run a one-shot client pod that curls the server Service across namespaces."""
    target = f"http://server.{_SERVER_NS}.svc.cluster.local:8080/hostname"
    proc = _kubectl(
        "run", f"probe-{int(time.time())}",
        "-n", _CLIENT_NS,
        "--image", _IMAGE,
        "--restart=Never", "--rm", "-i", "--quiet",
        "--command", "--",
        "/agnhost", "connect", f"--timeout={timeout_sec}s", "--protocol=http", target,
        timeout=timeout_sec + 120,
    )
    # agnhost `connect` exits non-zero when the connection cannot be established.
    return proc.returncode == 0


def _cleanup() -> None:
    for namespace in (_CLIENT_NS, _SERVER_NS):
        _kubectl("delete", "namespace", namespace, "--ignore-not-found", "--wait=false")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="leave the probe namespaces behind")
    args = parser.parse_args()

    context = _kubectl("config", "current-context")
    if context.returncode != 0:
        print("ERROR: no kubectl context — is a cluster running?", file=sys.stderr)
        return 2
    print(f"probing context: {context.stdout.strip()}")

    try:
        _apply(_namespace(_SERVER_NS))
        _apply(_namespace(_CLIENT_NS))
        _apply(_server_pod())
        _apply(_service())

        if not _wait_ready(_SERVER_NS, "app=server"):
            print("INCONCLUSIVE: server pod never became Ready", file=sys.stderr)
            return 2

        # Control: without any policy the two namespaces must be able to talk.
        if not _can_reach():
            print(
                "INCONCLUSIVE: baseline cross-namespace connectivity failed, so a later "
                "failure would prove nothing about NetworkPolicy",
                file=sys.stderr,
            )
            return 2
        print("baseline: B -> A reachable (no policy) ✓")

        _apply(_deny_all_ingress())
        # Give the CNI a moment to program the policy before re-testing.
        time.sleep(5)

        if _can_reach():
            print(
                "\nNOT ENFORCED: traffic still flows with a default-deny-ingress policy applied.\n"
                "  This CNI ignores NetworkPolicy. Do NOT enable tenancy-netpol here — it would\n"
                "  report isolation that does not exist. Use a policy-enforcing CNI\n"
                "  (e.g. kind with disableDefaultCNI + Calico) or rely on a stronger tier\n"
                "  (vcluster/dedicated) for data-plane isolation."
            )
            return 1

        print(
            "\nENFORCED: default-deny blocked the cross-namespace connection.\n"
            "  Safe to set tenancy-netpol `enabled: true` on this substrate.\n"
            "  Reminder: namespaces still need the platform-agent.io/tenant label for the\n"
            "  same-tenant allowance to match (Capsule sets it in Phase 2)."
        )
        return 0
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"INCONCLUSIVE: {exc}", file=sys.stderr)
        return 2
    finally:
        if args.keep:
            print(f"--keep: leaving {_SERVER_NS} / {_CLIENT_NS} in place")
        else:
            _cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
