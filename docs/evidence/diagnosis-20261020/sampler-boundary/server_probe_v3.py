"""v3 (v2 + corrected non-top1: chosen logprob vs max of unsorted top_logprobs; raw entries kept): fixed high-entropy prompts, logprobs on every row, seeds x path x temperature + unseeded.

usage: server_probe_v2.py OUT_DIR BASE_URL_UPSTREAM [BASE_URL_PROXY|-] LABEL
Same prompt across seeds (no nonce) so only the seed differs within a group.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

OUT, UP, PX, LABEL = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
PROMPTS = {"number": "Pick a random integer between 1 and 1000. Reply with only the number.",
           "words": "List eight random unrelated English nouns separated by commas. No other text."}
SEEDS = (42, 31415, 27182, 42)

def call(url, seed, prompt, temp):
    body = {"model": "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
            "messages": [{"role": "user", "content": prompt}], "max_tokens": 32,
            "temperature": temp, "top_p": 1.0, "top_k": 0, "repetition_penalty": 0,
            "stream": False, "logprobs": True, "top_logprobs": 3}
    if seed is not None: body["seed"] = seed
    req = urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    raw = urllib.request.urlopen(req, timeout=600).read(); r = json.loads(raw); ch = r["choices"][0]
    text = ch["message"].get("content") or ""
    lp = (ch.get("logprobs") or {}).get("content") or []
    non_top1 = sum(1 for e in lp if e.get("top_logprobs") and e["logprob"] < max(t["logprob"] for t in e["top_logprobs"]) - 1e-6)
    return {"seed": seed, "temperature": temp, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "finish_reason": ch.get("finish_reason"), "tokens_with_logprobs": len(lp), "non_top1_tokens": non_top1, "logprobs": lp}

paths = {"upstream": UP} | ({"proxy": PX} if PX != "-" else {})
rows = []
for pname, prompt in PROMPTS.items():
    for temp in (0.7, 1.0):
        for path, url in paths.items():
            for s in SEEDS + (None, None, None):
                row = {"label": LABEL, "prompt": pname, "path": path, **call(url, s, prompt, temp)}
                rows.append(row)
                print(json.dumps({k: row[k] for k in ("prompt", "temperature", "path", "seed", "text", "non_top1_tokens")}, ensure_ascii=False))

groups = {}
for r in rows:
    k = f'{r["prompt"]}|t={r["temperature"]}|{r["path"]}'
    g = groups.setdefault(k, {"seeded": {}, "unseeded": []})
    (g["seeded"].setdefault(str(r["seed"]), []) if r["seed"] is not None else g["unseeded"]).append(r["text_sha256"])
summary = {k: {"distinct_over_3_seeds": len({v[0] for s, v in g["seeded"].items()}),
               "seed42_repeat_identical": len(set(g["seeded"]["42"])) == 1,
               "unseeded_distinct_over_3": len(set(g["unseeded"])),
               "non_top1_total": sum(r["non_top1_tokens"] for r in rows if f'{r["prompt"]}|t={r["temperature"]}|{r["path"]}' == k)}
           for k, g in groups.items()}
(OUT / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
(OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
print(json.dumps(summary, indent=1))
