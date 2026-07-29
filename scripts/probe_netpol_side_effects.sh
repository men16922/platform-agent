#!/bin/bash
# Does a default-deny ingress break the two things it usually breaks — on k3s?
#
# The kind entry in PROVEN_ENFORCING_SUBSTRATES rests on a live check that
# kubelet probes and DNS survive default-deny. kindnet's behaviour does not
# transfer to k3s (flannel + kube-router netpol controller), so measure it.
#
#   1. readinessProbe under default-deny  -> pod must still reach Ready
#      (probes come from the NODE; no namespaceSelector can match them)
#   2. DNS under default-deny             -> policyTypes is [Ingress] only,
#      so egress, which is what DNS is, should be untouched
set -u
NS=k3s-sideeffect-probe
K="kubectl"

cleanup() { $K delete ns $NS --wait=false >/dev/null 2>&1; }
trap cleanup EXIT

$K delete ns $NS >/dev/null 2>&1
$K create ns $NS >/dev/null || exit 2

# default-deny ingress FIRST, so the pod is born under the policy
cat <<'EOF' | $K apply -n $NS -f - >/dev/null || exit 2
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}
  policyTypes: [Ingress]
EOF

cat <<'EOF' | $K apply -n $NS -f - >/dev/null || exit 2
apiVersion: v1
kind: Pod
metadata:
  name: probed
  labels: {app: probed}
spec:
  containers:
    - name: agnhost
      image: registry.k8s.io/e2e-test-images/agnhost:2.47
      args: ["netexec", "--http-port=8080"]
      readinessProbe:
        httpGet: {path: /healthz, port: 8080}
        initialDelaySeconds: 2
        periodSeconds: 3
        failureThreshold: 5
EOF

echo "--- 1. kubelet readinessProbe under default-deny ---"
if $K wait -n $NS --for=condition=Ready pod/probed --timeout=150s >/dev/null 2>&1; then
  echo "    READY        -> node-sourced probes are NOT blocked"
  PROBE=ok
else
  echo "    NOT READY    -> default-deny blocks kubelet probes on this substrate"
  $K get pod -n $NS probed -o wide
  $K describe pod -n $NS probed | sed -n '/Events:/,$p' | head -12
  PROBE=broken
fi

echo "--- 2. DNS (egress) under default-deny ---"
OUT=$($K exec -n $NS probed -- /agnhost dns-suffix 2>&1; $K exec -n $NS probed -- \
      sh -c 'getent hosts kubernetes.default.svc.cluster.local || nslookup kubernetes.default' 2>&1)
if echo "$OUT" | grep -qE '([0-9]{1,3}\.){3}[0-9]{1,3}|cluster\.local'; then
  echo "    RESOLVED     -> ingress-only policy leaves DNS alone"
  echo "$OUT" | head -3 | sed 's/^/      /'
  DNS=ok
else
  echo "    FAILED       -> DNS broke under the policy"
  echo "$OUT" | head -6 | sed 's/^/      /'
  DNS=broken
fi

echo
echo "RESULT: probe=$PROBE dns=$DNS"
[ "$PROBE" = ok ] && [ "$DNS" = ok ] && exit 0 || exit 1
