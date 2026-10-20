"""Read-only observer for this approved experiment, not a deployment tool."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument("label")
p.add_argument("tag")
p.add_argument("--replicas", type=int, default=2)
p.add_argument("--timeout", type=int, default=180)
a = p.parse_args()
assert a.label.replace("-", "").isalnum() and a.tag.replace("-", "").isalnum()
out = Path(__file__).resolve().parent
out.mkdir(exist_ok=True)
prefix = ["kubectl", "--context", "kind-platform-agent", "--request-timeout=10s", "-n", "acme-dev-observability"]
started = time.monotonic()
observations = []
healthy_since = None
image = "localhost:5001/orders-api-dogfood:" + a.tag

def read(*args):
    return subprocess.check_output(prefix + list(args), text=True, timeout=15, stderr=subprocess.PIPE)

while time.monotonic() - started < a.timeout:
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        deployment = json.loads(read("get", "deployment", "orders-api-dogfood", "-o", "json"))
        pods = json.loads(read("get", "pods", "-l", "app=orders-api-dogfood", "-o", "json"))["items"]
        current = [pod for pod in pods if not pod["metadata"].get("deletionTimestamp")
                   and pod["spec"]["containers"][0]["image"] == image]
        status = deployment["status"]
        ready = (deployment["spec"]["template"]["spec"]["containers"][0]["image"] == image
                 and deployment["spec"]["replicas"] == a.replicas
                 and status.get("observedGeneration") == deployment["metadata"]["generation"]
                 and status.get("updatedReplicas") == status.get("readyReplicas") == status.get("replicas") == a.replicas
                 and len(current) == a.replicas
                 and all(all(c.get("ready") for c in pod["status"].get("containerStatuses", []))
                         and pod["status"].get("containerStatuses") for pod in current))
        observation = {"at": stamp, "revision": deployment["metadata"]["annotations"]["deployment.kubernetes.io/revision"],
                       "generation": deployment["metadata"]["generation"], "ready": ready,
                       "image": deployment["spec"]["template"]["spec"]["containers"][0]["image"]}
        logs = {}
        if ready:
            healthy_since = healthy_since or stamp
            logs = {pod["metadata"]["name"]: read("logs", pod["metadata"]["name"], "--since-time=" + healthy_since) for pod in current}
        else:
            healthy_since = None
        healthy = ready and all('"GET /healthz HTTP/1.1" 200' in log for log in logs.values())
        observation["health_observed"] = healthy
        observations.append(observation)
        if healthy:
            observed_at = dt.datetime.now(dt.timezone.utc).isoformat()
            (out / (a.label + "-deployment.json")).write_text(json.dumps(deployment, indent=2) + "\n")
            (out / (a.label + "-pods.json")).write_text(json.dumps(pods, indent=2) + "\n")
            (out / (a.label + "-health.json")).write_text(json.dumps(logs, indent=2) + "\n")
            result = {"label": a.label, "healthy_observed_at": observed_at, "revision": observation["revision"],
                      "uid": deployment["metadata"]["uid"], "replicas": a.replicas, "image": image,
                      "observations": observations, "method": "Read-only 1s polling and actual kubelet health-200 log from each current Pod; not browser HTTP."}
            (out / (a.label + "-observation.json")).write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps({k:v for k,v in result.items() if k != "observations"}), flush=True)
            break
    except (subprocess.SubprocessError, ValueError, KeyError) as exc:
        observations.append({"at": stamp, "error_type": type(exc).__name__})
    time.sleep(1)
else:
    (out / (a.label + "-observation.json")).write_text(json.dumps({"label":a.label,"timeout":True,"observations":observations},indent=2)+"\n")
    raise SystemExit("Observer timed out; this does not prove the workload stopped.")
