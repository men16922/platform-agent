"""Server boundary probe: seeds x path (upstream/proxy) x cache (shared/nonce) x seeded/unseeded.

Short neutral prompt, temperature 0.7, top_p 1, top_k 0, 48 tokens. Records raw text hash and
whether any sampled token was not the top-1 logprob (i.e. sampling actually departed from argmax).
"""
import hashlib
import json
import sys
import time
import uuid
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
URLS = {"upstream": "http://127.0.0.1:18190/v1/chat/completions",
        "proxy": "http://127.0.0.1:18191/v1/chat/completions"}
BASE = "Write one short sentence about a Kubernetes pod that keeps restarting."

def call(path, seed, prompt, logprobs):
    body = {"model": "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 48, "temperature": 0.7, "top_p": 1.0, "top_k": 0,
            "repetition_penalty": 0, "stream": False}
    if seed is not None: body["seed"] = seed
    if logprobs: body.update(logprobs=True, top_logprobs=3)
    req = urllib.request.Request(URLS[path], json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time(); raw = urllib.request.urlopen(req, timeout=600).read(); dt = time.time() - t
    r = json.loads(raw); ch = r["choices"][0]; text = ch["message"].get("content") or ""
    non_top1 = None
    lp = (ch.get("logprobs") or {}).get("content")
    if lp:
        non_top1 = sum(1 for e in lp if e.get("top_logprobs") and e["top_logprobs"][0]["token"] != e["token"])
    return {"path": path, "seed": seed, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()[:16],
            "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "finish_reason": ch.get("finish_reason"), "non_top1_tokens": non_top1,
            "logprobs_tokens": len(lp) if lp else None, "seconds": round(dt, 2), "request": body}

rows = []
plan = []
for path in ("upstream", "proxy"):
    for s in (42, 31415, 27182, 42):                       # shared prompt: warm cache after first
        plan.append(("shared", path, s, BASE, path == "upstream"))
    for s in (42, 31415, 27182):                           # nonce prompt: always cold cache
        plan.append(("nonce", path, s, f"[{uuid.uuid4().hex[:8]}] {BASE}", False))
for i in range(3):                                         # unseeded -> batch path control
    plan.append(("unseeded", "upstream", None, BASE, False))
for arm, path, s, prompt, lp in plan:
    row = {"arm": arm, **call(path, s, prompt, lp)}
    rows.append(row); print(json.dumps({k: row[k] for k in ("arm", "path", "seed", "text_sha256", "non_top1_tokens", "finish_reason", "seconds")}))
    (OUT / f"{len(rows):02d}-{arm}-{path}-{s}.json").write_text(json.dumps(row, ensure_ascii=False, indent=1) + "\n")

def distinct(f): return len({r["text_sha256"] for r in rows if f(r)})
summary = {
 "upstream_shared_distinct_over_3_seeds": distinct(lambda r: r["arm"] == "shared" and r["path"] == "upstream" and r is not rows[3]),
 "proxy_shared_distinct_over_3_seeds": distinct(lambda r: r["arm"] == "shared" and r["path"] == "proxy" and r is not rows[10]),
 "upstream_vs_proxy_same_for_same_seed": {s: len({r["text_sha256"] for r in rows if r["arm"] == "shared" and r["seed"] == s}) == 1 for s in (42, 31415, 27182)},
 "unseeded_distinct_over_3": distinct(lambda r: r["arm"] == "unseeded"),
 "upstream_logprob_non_top1": [r["non_top1_tokens"] for r in rows if r["non_top1_tokens"] is not None],
}
(OUT / "summary.json").write_text(json.dumps({"rows": [{k: v for k, v in r.items() if k != "request"} for r in rows], "summary": summary}, ensure_ascii=False, indent=1) + "\n")
print(json.dumps(summary, indent=1))
