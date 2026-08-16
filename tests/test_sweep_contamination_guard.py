"""
A sweep nobody answered must not be persisted as a score.

`scripts/live_model_sweep.py` grades a model over `ROUTING_EVAL_SET`. When a call
fails, `live_router_factory` degrades to the deterministic backstop so a flaky
model never yields a null route — which is right for routing and wrong for
*scoring*: the backstop's answers are not the model's.

The script already refused to persist when a **different model** answered
(`stats["mismatch"]`). It did not refuse when the call never got that far.
`stats["calls"]` is incremented *after* the model-echo check, so an exception in
`urlopen` / JSON / `["content"]` leaves both counters at zero and the guard
passes.

Measured 2026-08-16 against Qwen3.8-27B: it is a reasoning model, so with this
script's `max_tokens: 16` every reply was `{"role": ..., "reasoning": ...}` with
**no `content`** — KeyError on all 40 cases, `calls=0, mismatch=0`, and a
persisted `pass=1.00 (20/20)` that was entirely the backstop. That is a
scoreboard for a model that was never asked.

Both directions are asserted: the contaminated run must refuse *and write
nothing*, and a clean run must still persist (a guard that always fires is not a
guard, Risk 12③).
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/live_model_sweep.py"
MODEL = "test/model-4bit"


def _load():
    spec = importlib.util.spec_from_file_location("live_model_sweep", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Resp(io.BytesIO):
    """`with urlopen(...) as resp: json.load(resp)`."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _reply(message: dict):
    def urlopen(req, timeout=None):  # noqa: ARG001
        return _Resp(json.dumps({
            "model": MODEL,
            "choices": [{"message": message}],
        }).encode())

    return urlopen


def _run(monkeypatch, tmp_path, message: dict):
    module = _load()
    monkeypatch.setattr(module, "available_models", lambda _e: {MODEL})
    monkeypatch.setattr(module.request, "urlopen", _reply(message))
    points = tmp_path / "points.jsonl"
    monkeypatch.setattr(sys, "argv", [
        "live_model_sweep.py", "--model", MODEL, "--points", str(points),
    ])
    return module, points


class TestARunNobodyAnsweredIsRefused:
    def test_reasoning_only_reply_refuses_to_persist(self, monkeypatch, tmp_path):
        """The exact 2026-08-16 shape: `reasoning` present, `content` absent."""
        module, points = _run(monkeypatch, tmp_path, {
            "role": "assistant", "reasoning": "We need to respond to user...",
        })
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert "reached the model" in str(exc.value)
        assert not points.exists(), "a scoreboard nobody answered was written to disk"

    def test_the_error_names_the_likely_cause(self, monkeypatch, tmp_path):
        """A reader hitting this must not have to re-derive it."""
        module, points = _run(monkeypatch, tmp_path, {"role": "assistant"})
        with pytest.raises(SystemExit) as exc:
            module.main()
        text = str(exc.value)
        assert "max_tokens" in text and "reasoning" in text

    def test_it_reports_how_many_reached_the_model(self, monkeypatch, tmp_path):
        module, points = _run(monkeypatch, tmp_path, {"role": "assistant"})
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert "0 of 40" in str(exc.value), "40 = 2 configs x 20 cases x 1 trial"


class TestACleanRunStillPersists:
    """Reverse direction — the guard must not block a real measurement."""

    def test_content_reply_is_scored_and_written(self, monkeypatch, tmp_path):
        module, points = _run(monkeypatch, tmp_path, {
            "role": "assistant", "content": "deployment",
        })
        module.main()
        assert points.exists()
        rows = [json.loads(line) for line in points.read_text().splitlines() if line.strip()]
        assert len(rows) == 2, "one point per effort config"
        assert all(r["total"] == 20 for r in rows)


class TestTheMismatchGuardStillWorks:
    """The older half of the guard must not have been replaced by the new one."""

    def test_wrong_model_answering_still_refuses(self, monkeypatch, tmp_path):
        module, points = _run(monkeypatch, tmp_path, {"role": "assistant", "content": "x"})

        def wrong(req, timeout=None):  # noqa: ARG001
            return _Resp(json.dumps({
                "model": "some/other-model",
                "choices": [{"message": {"role": "assistant", "content": "deployment"}}],
            }).encode())

        monkeypatch.setattr(module.request, "urlopen", wrong)
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert "wrong model" in str(exc.value)
        assert not points.exists()
