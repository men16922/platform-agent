"""One-variable intervention: replace mlx_lm's compiled categorical_sampling with an
uncompiled call that uses the calling (generation) thread's RNG state. Everything else is the
stock mlx_lm 0.31.3 server with the same CLI arguments."""
import mlx.core as mx
import mlx_lm.sample_utils as su

def categorical_sampling(logits, temp):
    return mx.random.categorical(logits * (1 / temp))

su.categorical_sampling = categorical_sampling  # make_sampler resolves this global at call time

from mlx_lm import server
if __name__ == "__main__":
    server.main()
