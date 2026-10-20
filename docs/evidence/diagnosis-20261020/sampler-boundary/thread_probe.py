"""Server-shaped probe: one long-lived worker thread serves sequential seeded requests."""
import json
import threading
import queue
import mlx.core as mx
from mlx_lm.sample_utils import categorical_sampling

SEEDS = [42, 31415, 27182]
mx.random.seed(0)
z = mx.random.normal((1, 32000)) * 2.0
logits = z - mx.logsumexp(z, axis=-1, keepdims=True); mx.eval(logits)

def key():  # current RNG key as seen from the calling thread
    k = mx.random.state[0]; mx.eval(k); return [int(v) for v in k.tolist()]

def draw(fn, n=12):
    out = []
    for _ in range(n):
        t = fn(logits); mx.eval(t); out.append(int(t.item()))
    return out

uncompiled = lambda x: mx.random.categorical(x * (1 / 0.7))
compiled = lambda x: categorical_sampling(x, 0.7)
main_key_before = key()
results = {}

def worker(jobs, out):
    while (job := jobs.get()) is not None:
        name, seed, fn = job
        mx.random.seed(seed)
        k0 = key(); toks = draw(fn); k1 = key()
        out.put((name, seed, {"tokens": toks, "key_after_seed": k0, "key_after_draws": k1}))

jobs, out = queue.Queue(), queue.Queue()
th = threading.Thread(target=worker, args=(jobs, out)); th.start()
for name, fn in (("worker_uncompiled", uncompiled), ("worker_compiled", compiled)):
    for s in SEEDS: jobs.put((name, s, fn))
jobs.put(None); th.join()
while not out.empty():
    name, seed, r = out.get(); results.setdefault(name, {})[seed] = r
main_key_after = key()

summ = {}
for name, d in results.items():
    seqs = {s: tuple(r["tokens"]) for s, r in d.items()}
    summ[name] = {"distinct_across_seeds": len(set(seqs.values())),
                  "per_seed_unique_tokens": {s: len(set(t)) for s, t in seqs.items()},
                  "thread_key_advanced": {s: r["key_after_seed"] != r["key_after_draws"] for s, r in d.items()}}
print(json.dumps({"mlx": mx.__version__, "main_key_before": main_key_before, "main_key_after": main_key_after,
                  "main_key_changed_by_worker": main_key_before != main_key_after, "summary": summ,
                  "tokens": {n: {s: r["tokens"] for s, r in d.items()} for n, d in results.items()}}, indent=1))
