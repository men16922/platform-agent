"""Prove the SOFT TIER's data-plane isolation actually behaves as claimed.

`verify_netpol_enforcement.py` answers a narrower question — does this CNI enforce
NetworkPolicy at all — using two throwaway namespaces and a bare default-deny. That
is a prerequisite, not the claim. The claim the platform makes is specific:

    a pod in tenant A's namespace can reach tenant A's other namespaces,
    a pod in tenant B cannot reach tenant A at all,
    and nothing else about the workloads breaks as a side effect.

The last clause is why this probe exists rather than a pair of curl commands. A
default-deny ingress has two well-known ways of "working" while breaking the
cluster, and both are invisible from `kubectl get netpol`:

  * **Kubelet probes.** readiness/liveness probes originate from the NODE, not from
    a pod, so no `namespaceSelector` can ever match them. If the CNI treats them as
    ordinary ingress, every policied pod goes NotReady and the cause looks like an
    application regression, days later.
  * **DNS.** These policies set `policyTypes: [Ingress]` only, so egress — which is
    what DNS is — should be untouched. "Should be" is exactly the kind of claim
    this repo has been wrong about before, so it is measured here instead.

Both are asserted, not assumed: a green run means isolation holds AND the two
things a default-deny usually breaks did not break.

The policies under test are the ones `render_tenancy` emits from the registry —
this probe renders nothing of its own, so it cannot pass against a policy shape the
platform does not actually ship.

Usage:
  python scripts/verify_tenant_isolation.py --tenant acme --env dev \
      --peer-tenant globex --peer-env dev [--keep]

Exit codes: 0 = isolation holds, 1 = a claim was violated, 2 = inconclusive/error.

EVERY LINE GOES TO STDOUT, INCLUDING THE FAILURES — see the same note in
`verify_netpol_enforcement.py`. A four-claim report is the worst possible thing to
split across two streams: through a pipe the reader would get `[1/4] ✓` and
`[2/4] ✓` and then silence, because the INCONCLUSIVE that ended the run went to
the stream they were not holding. Two ✓ and no verdict reads as a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.platform.registry import load_registry  # noqa: E402
from src.agents.platform.tenancy import (  # noqa: E402
    TENANT_LABEL,
    namespaces_for,
    network_policies_apply_to,
)

_IMAGE = "registry.k8s.io/e2e-test-images/agnhost:2.47"
_SERVER = "isolation-probe-server"
_PORT = 8080

#: Pod Security Standards `restricted` is enforced on every tenant namespace, so
#: the probe's own pods must comply. This is not incidental: if the probe needed a
#: privileged pod to run, it could only ever test a namespace the platform does not
#: create, and a green result would be about the wrong cluster.
_SECURITY_CONTEXT = {
    "runAsNonRoot": True,
    "runAsUser": 10001,
    "allowPrivilegeEscalation": False,
    "capabilities": {"drop": ["ALL"]},
    "seccompProfile": {"type": "RuntimeDefault"},
}


def _kubectl(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Never raises for a missing binary — see the note in verify_netpol_enforcement."""
    try:
        return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                              timeout=timeout)
    except OSError as exc:
        return subprocess.CompletedProcess(args, 127, "", f"kubectl 실행 실패: {exc}")


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


def _server_pod(namespace: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": _SERVER,
            "namespace": namespace,
            "labels": {"app": _SERVER},
        },
        "spec": {
            "securityContext": {
                "runAsNonRoot": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [{
                "name": "server",
                "image": _IMAGE,
                "args": ["netexec", f"--http-port={_PORT}"],
                "ports": [{"containerPort": _PORT}],
                "securityContext": _SECURITY_CONTEXT,
                "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}},
                # The probe-survival claim: this is an HTTP GET from the node into
                # a namespace whose every pod is under default-deny ingress.
                "readinessProbe": {
                    "httpGet": {"path": "/healthz", "port": _PORT},
                    "initialDelaySeconds": 2,
                    "periodSeconds": 3,
                },
            }],
        },
    }


def _service(namespace: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": _SERVER, "namespace": namespace},
        "spec": {
            "selector": {"app": _SERVER},
            "ports": [{"port": _PORT, "targetPort": _PORT}],
        },
    }


def _wait_ready(namespace: str, timeout_sec: int = 120) -> bool:
    proc = _kubectl(
        "wait", "-n", namespace, "--for=condition=Ready", "pod", "-l", f"app={_SERVER}",
        f"--timeout={timeout_sec}s", timeout=timeout_sec + 30,
    )
    return proc.returncode == 0


def _run_probe(namespace: str, command: list[str], timeout_sec: int) -> subprocess.CompletedProcess:
    """One throwaway client pod in `namespace`, PSS-restricted like its neighbours."""
    overrides = {
        "spec": {
            "securityContext": {
                "runAsNonRoot": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [{
                "name": "probe",
                "image": _IMAGE,
                "command": command,
                "securityContext": _SECURITY_CONTEXT,
                "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}},
            }],
        }
    }
    return _kubectl(
        "run", f"probe-{int(time.time() * 1000)}",
        "-n", namespace, "--image", _IMAGE,
        "--restart=Never", "--rm", "-i", "--quiet",
        "--overrides", json.dumps(overrides),
        timeout=timeout_sec + 120,
    )


def _connect(from_namespace: str, to_namespace: str, *, attempts: int) -> bool:
    """True if ANY attempt establishes a TCP connection.

    "Any success = reachable" is the safe polarity in both directions: one leaked
    connection disproves isolation, and retrying only makes the BLOCKED verdict
    harder to earn. Retries also absorb the unrelated race where a pod is Ready
    before its port is bound (observed on kind: attempt 1 REFUSED, attempt 2 fine).
    """
    target = f"{_SERVER}.{to_namespace}.svc.cluster.local:{_PORT}"
    for attempt in range(attempts):
        proc = _run_probe(
            from_namespace,
            ["/agnhost", "connect", "--timeout=8s", "--protocol=tcp", target],
            timeout_sec=8,
        )
        if proc.returncode == 0:
            return True
        if attempt < attempts - 1:
            time.sleep(3)
    return False


def _resolves_dns(namespace: str) -> bool:
    """DNS is EGRESS. An ingress-only policy must not touch it — measured, not assumed.

    Deliberately NOT `agnhost dns-suffix`, which was the first thing tried here: it
    prints the search domains out of /etc/resolv.conf without ever sending a query,
    so it returns 0 on a cluster whose DNS is completely dead. A probe that cannot
    fail is not evidence.

    Connecting to `kubernetes.default` by NAME requires a real lookup to succeed
    first, and it doubles as the honest statement of what "ingress-only" means: a
    policied pod can still open connections outward, including to services outside
    its own tenant.
    """
    proc = _run_probe(
        namespace,
        ["/agnhost", "connect", "--timeout=8s", "--protocol=tcp",
         "kubernetes.default.svc.cluster.local:443"],
        timeout_sec=20,
    )
    return proc.returncode == 0


def _policied_namespaces(tenant, env: str) -> list[str]:
    return [ns for _capability, ns in namespaces_for(tenant, env)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True, help="tenant whose namespaces are the target")
    parser.add_argument("--env", required=True)
    parser.add_argument("--peer-tenant", required=True, help="a DIFFERENT tenant, the attacker")
    parser.add_argument("--peer-env", required=True)
    parser.add_argument("--keep", action="store_true", help="leave the probe workload behind")
    args = parser.parse_args()

    if args.tenant == args.peer_tenant:
        print("ERROR: peer must be a different tenant, or 'cross-tenant' means nothing")
        return 2

    registry = load_registry()
    try:
        tenant = registry.tenant(args.tenant)
        peer = registry.tenant(args.peer_tenant)
    except KeyError as exc:
        print(f"ERROR: {exc}")
        return 2

    targets = _policied_namespaces(tenant, args.env)
    peers = _policied_namespaces(peer, args.peer_env)
    if len(targets) < 2:
        print(
            f"ERROR: {args.tenant}/{args.env} has {len(targets)} namespace(s); the "
            "same-tenant leg needs two"
        )
        return 2
    if not peers:
        print(f"ERROR: {args.peer_tenant}/{args.peer_env} has no namespaces")
        return 2

    if not network_policies_apply_to(tenant, args.env):
        print(
            f"ERROR: no NetworkPolicy is rendered for {args.tenant}/{args.env} "
            "(unproven substrate) — there is nothing to verify here"
        )
        return 2

    server_ns, same_tenant_ns = targets[0], targets[1]
    cross_tenant_ns = peers[0]
    print(f"server:        {server_ns}")
    print(f"same-tenant:   {same_tenant_ns}   (expect ALLOWED)")
    print(f"cross-tenant:  {cross_tenant_ns}   (expect BLOCKED)")

    # The policy is what makes the verdict meaningful; without it this is a
    # connectivity test wearing a security test's name.
    policy = _kubectl("get", "networkpolicy", "-n", server_ns, "deny-cross-tenant", "-o", "json")
    if policy.returncode != 0:
        print(f"ERROR: no deny-cross-tenant policy in {server_ns} — apply tenancy first")
        return 2
    spec = json.loads(policy.stdout)["spec"]
    print(f"policy in place: policyTypes={spec.get('policyTypes')} "
          f"peers={json.dumps(spec.get('ingress'))}")

    failures: list[str] = []
    try:
        _apply(_server_pod(server_ns))
        _apply(_service(server_ns))

        # CLAIM 1 — kubelet probes survive default-deny (they come from the node).
        if not _wait_ready(server_ns):
            describe = _kubectl("describe", "pod", "-n", server_ns, _SERVER)
            print(
                "\nVIOLATION: the server pod never became Ready under default-deny ingress.\n"
                "  If the readinessProbe is what failed, this CNI treats kubelet probes as\n"
                "  ordinary ingress and these policies will silently NotReady every tenant\n"
                "  workload. Do not ship them on this substrate.\n"
                f"{describe.stdout[-1500:]}"
            )
            return 1
        print("\n[1/4] kubelet readinessProbe reached the pod under default-deny ✓")

        # CLAIM 2 — same tenant, different namespace: ALLOWED.
        if _connect(same_tenant_ns, server_ns, attempts=4):
            print(f"[2/4] {same_tenant_ns} -> {server_ns}: ALLOWED ✓ (same tenant)")
        else:
            failures.append(
                f"same-tenant traffic {same_tenant_ns} -> {server_ns} was BLOCKED; the "
                "policy is isolating the tenant from itself"
            )
            print(f"[2/4] {same_tenant_ns} -> {server_ns}: BLOCKED ✗")

        # CLAIM 3 — different tenant: BLOCKED. The claim the whole tier rests on.
        if _connect(cross_tenant_ns, server_ns, attempts=3):
            failures.append(
                f"cross-tenant traffic {cross_tenant_ns} -> {server_ns} SUCCEEDED; the soft "
                "tier's data-plane isolation does not exist on this cluster"
            )
            print(f"[3/4] {cross_tenant_ns} -> {server_ns}: ALLOWED ✗")
        else:
            print(f"[3/4] {cross_tenant_ns} -> {server_ns}: BLOCKED ✓ (cross tenant)")

        # CLAIM 4 — DNS (egress) unaffected by an ingress-only policy.
        #
        # This also serves as the CONTROL for claim 3, which is why it runs from the
        # cross-tenant namespace rather than anywhere convenient. "Cross-tenant was
        # blocked" is only evidence of isolation if that client could reach anything
        # at all; a pod with broken networking produces the same green. Claim 4
        # succeeding from the same namespace that failed claim 3 is what separates
        # "the policy blocked it" from "that pod cannot talk to anyone".
        if _resolves_dns(cross_tenant_ns):
            print("[4/4] DNS still resolves inside a policied namespace ✓")
        else:
            failures.append(
                f"DNS failed inside policied namespace {cross_tenant_ns}; an ingress-only "
                "policy should not affect egress, and applications will read this as a bug "
                "in themselves"
            )
            print("[4/4] DNS resolution FAILED ✗")

    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"INCONCLUSIVE: {exc}")
        return 2
    finally:
        if args.keep:
            print(f"--keep: leaving {_SERVER} in {server_ns}")
        else:
            _kubectl("delete", "pod", "-n", server_ns, _SERVER, "--ignore-not-found",
                     "--wait=false")
            _kubectl("delete", "svc", "-n", server_ns, _SERVER, "--ignore-not-found",
                     "--wait=false")

    if failures:
        print("\nISOLATION NOT PROVEN:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        f"\nISOLATION HOLDS for {args.tenant}/{args.env} "
        f"(label {TENANT_LABEL}={tenant.name}): same-tenant reachable, cross-tenant blocked, "
        "kubelet probes and DNS unaffected."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
