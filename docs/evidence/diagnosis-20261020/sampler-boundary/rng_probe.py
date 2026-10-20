"""RNG/sampler boundary probe without a model: same logits, distinct seeds."""
import json
import threading
import mlx.core as mx
from mlx_lm.sample_utils import make_sampler, categorical_sampling

SEEDS = [42, 31415, 27182]
mx.random.seed(0)
z = mx.random.normal((1, 32000)) * 2.0; logits = z - mx.logsumexp(z, axis=-1, keepdims=True)
mx.eval(logits)

def draw(fn, n=24):
    out = []
    for _ in range(n):
        t = fn(logits); mx.eval(t); out.append(int(t.item()))
    return out

res = {}
# 1) raw mx.random.categorical (uncompiled)
res["raw_categorical"] = {s: (mx.random.seed(s), draw(lambda x: mx.random.categorical(x / 0.7)))[1] for s in SEEDS}
# 2) compiled categorical_sampling used by mlx_lm
res["compiled_categorical_sampling"] = {s: (mx.random.seed(s), draw(lambda x: categorical_sampling(x, 0.7)))[1] for s in SEEDS}
# 3) make_sampler(temp=0.7, top_p=1, top_k=0) as the server builds it
sampler = make_sampler(0.7, top_p=1.0, min_p=0.0, top_k=0)
res["make_sampler_reused"] = {s: (mx.random.seed(s), draw(sampler))[1] for s in SEEDS}
# 4) same, but seed set on a worker thread like the server's generation thread
def on_thread(s):
    box = {}
    def run():
        mx.random.seed(s); box["v"] = draw(make_sampler(0.7, top_p=1.0, top_k=0))
    th = threading.Thread(target=run); th.start(); th.join(); return box["v"]
res["worker_thread"] = {s: on_thread(s) for s in SEEDS}
# 5) same seed twice -> reproducibility control
res["same_seed_repeat"] = {f"42#{i}": (mx.random.seed(42), draw(sampler))[1] for i in (1, 2)}

summary = {k: {"distinct_sequences": len({tuple(v) for v in d.values()}), "n": len(d)} for k, d in res.items()}
print(json.dumps({"mlx": mx.__version__, "summary": summary, "first8": {k: {s: v[:8] for s, v in d.items()} for k, d in res.items()}}, indent=1))
