"""AI Model Router — decouple the LLM *brain* from the deployment *environment*.

The deploy tools (build/push/deploy/validate) are provider-neutral, and every
deployer takes a ``provider`` (target environment). That means any model can, in
principle, drive a deploy to any environment. This module is the router that
makes that explicit:

    (model, environment) -> suitability verdict + the deployer that runs it

Models
    local-qwen      Local LLM (Qwen2.5/3-Coder via MLX)   framework: pydantic-ai
    bedrock-claude  Bedrock Claude                        framework: strands
    vertex-gemini   Vertex AI Gemini 3.5 Flash            framework: adk
    azure-gpt       Azure OpenAI GPT-5.4                  framework: msft

Environments
    aws  gcp  azure  onprem

Suitability lets the UI offer every model for every environment while flagging
which pairing is native/recommended vs. merely allowed — e.g. on-prem lists
Bedrock Claude, Gemini, Azure GPT and Local Qwen, with Local Qwen recommended
for fully offline operation.

Only the local (pydantic-ai + MLX) path executes fully offline here. Cloud
models validate + dispatch through their native deployers, which require that
cloud's credentials to run live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    llm: str
    framework: str
    home: str  # the environment this model is native to


MODELS: dict[str, ModelInfo] = {
    "local-qwen": ModelInfo("local-qwen", "Local LLM (Qwen)", "Qwen2.5/3-Coder (MLX)", "pydantic-ai", "onprem"),
    "bedrock-claude": ModelInfo("bedrock-claude", "Bedrock Claude", "Claude (Bedrock)", "strands", "aws"),
    "vertex-gemini": ModelInfo("vertex-gemini", "Vertex Gemini", "Gemini 3.5 Flash", "adk", "gcp"),
    "azure-gpt": ModelInfo("azure-gpt", "Azure OpenAI GPT", "GPT-5.4", "msft", "azure"),
}

ENVIRONMENTS: list[str] = ["aws", "gcp", "azure", "onprem"]

NATIVE_MODEL: dict[str, str] = {
    "aws": "bedrock-claude",
    "gcp": "vertex-gemini",
    "azure": "azure-gpt",
    "onprem": "local-qwen",
}

_ENV_LABEL = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure", "onprem": "On-Prem"}
_VERDICT_RANK = {"recommended": 0, "allowed": 1, "discouraged": 2}


@dataclass
class DeployOutcome:
    ok: bool
    model: str
    provider: str
    summary: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    suitability: dict[str, str] = field(default_factory=dict)
    # Ordered mixed trace: {"kind": "reasoning", "text"} | {"kind": "tool", "tool", "args", "result"}
    trace: list[dict[str, Any]] = field(default_factory=list)


def suitability(model_id: str, provider: str) -> dict[str, str]:
    """Return {verdict, reason} for running ``model_id`` against ``provider``."""
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}")
    if provider not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {provider}")

    model = MODELS[model_id]
    native = MODELS[NATIVE_MODEL[provider]]
    env_label = _ENV_LABEL[provider]

    if model.home == provider:
        return {"verdict": "recommended", "reason": f"Native pairing — {model.label} is the {env_label}-native brain."}

    if provider == "onprem":
        return {
            "verdict": "allowed",
            "reason": (
                f"{model.label} can drive on-prem deploys, but the cloud brain breaks air-gapped "
                f"operation; {native.label} is recommended for fully offline on-prem."
            ),
        }

    if model_id == "local-qwen":
        return {
            "verdict": "allowed",
            "reason": (
                f"Local Qwen can drive {env_label} deploys (offline brain, cloud hands); "
                f"{native.label} is the {env_label}-native choice."
            ),
        }

    return {
        "verdict": "allowed",
        "reason": f"Non-native pairing — works, but {native.label} is recommended for {env_label}.",
    }


def models_for_environment(provider: str) -> list[dict[str, str]]:
    """All models offered for ``provider``, recommended-first — drives the UI selector."""
    if provider not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {provider}")
    rows = []
    for model in MODELS.values():
        fit = suitability(model.id, provider)
        rows.append(
            {
                "id": model.id,
                "label": model.label,
                "llm": model.llm,
                "framework": model.framework,
                "verdict": fit["verdict"],
                "reason": fit["reason"],
            }
        )
    rows.sort(key=lambda r: (_VERDICT_RANK[r["verdict"]], r["label"]))
    return rows


def router_matrix() -> list[dict[str, Any]]:
    """Full model x environment suitability matrix (for docs / diagnostics)."""
    return [
        {"provider": provider, "models": models_for_environment(provider)}
        for provider in ENVIRONMENTS
    ]


# --- Execution -----------------------------------------------------------


def _args_as_dict(part: Any) -> dict[str, Any]:
    try:
        args = part.args_as_dict()
    except Exception:
        args = part.args if isinstance(getattr(part, "args", None), dict) else {}
    return args or {}


def extract_steps(messages: list[Any]) -> list[dict[str, Any]]:
    """Pair each pydantic-ai tool call with its return value, preserving order."""
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    order: list[str] = []
    calls: dict[str, dict[str, Any]] = {}
    for message in messages:
        for part in getattr(message, "parts", []):
            if isinstance(part, ToolCallPart):
                if part.tool_call_id not in calls:
                    order.append(part.tool_call_id)
                calls.setdefault(part.tool_call_id, {})["call"] = part
            elif isinstance(part, ToolReturnPart):
                calls.setdefault(part.tool_call_id, {})["return"] = part

    steps: list[dict[str, Any]] = []
    for call_id in order:
        entry = calls[call_id]
        call = entry.get("call")
        if call is None:
            continue
        ret = entry.get("return")
        steps.append(
            {
                "tool": call.tool_name,
                "args": _args_as_dict(call),
                "result": ret.content if ret is not None else None,
            }
        )
    return steps


def build_trace(messages: list[Any]) -> list[dict[str, Any]]:
    """Ordered mixed trace of reasoning text and tool calls from a pydantic-ai run.

    Preserves the sequence the model produced: reasoning/explanation text
    (TextPart/ThinkingPart) interleaved with tool calls + their results.
    """
    from pydantic_ai.messages import TextPart, ThinkingPart, ToolCallPart, ToolReturnPart

    trace: list[dict[str, Any]] = []
    by_call_id: dict[str, dict[str, Any]] = {}
    for message in messages:
        for part in getattr(message, "parts", []):
            if isinstance(part, (TextPart, ThinkingPart)):
                text = (part.content or "").strip()
                if text:
                    trace.append({"kind": "reasoning", "text": text})
            elif isinstance(part, ToolCallPart):
                item = {"kind": "tool", "tool": part.tool_name, "args": _args_as_dict(part), "result": None}
                trace.append(item)
                by_call_id[part.tool_call_id] = item
            elif isinstance(part, ToolReturnPart):
                item = by_call_id.get(part.tool_call_id)
                if item is not None:
                    item["result"] = part.content
    return trace


def _strip_trailing_summary(trace: list[dict[str, Any]], summary: str) -> list[dict[str, Any]]:
    """Drop the final reasoning item when it just repeats the summary (shown separately)."""
    if trace and trace[-1].get("kind") == "reasoning" and trace[-1].get("text", "").strip() == (summary or "").strip():
        return trace[:-1]
    return trace


def _tool_steps(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"tool": item["tool"], "args": item.get("args", {}), "result": item.get("result")}
        for item in trace
        if item.get("kind") == "tool"
    ]


def _step_failed(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("error"))


def _cloud_outcome(model_id: str, provider: str, fit: dict[str, str]) -> DeployOutcome:
    """Structured outcome for a cloud model routed without live execution."""
    model = MODELS[model_id]
    return DeployOutcome(
        ok=False,
        model=model_id,
        provider=provider,
        summary=(
            f"{model.label} runs via the {model.framework} deployer and requires "
            f"{_ENV_LABEL[model.home]} credentials for a live run. "
            f"Suitability for {_ENV_LABEL[provider]}: {fit['verdict']} — {fit['reason']}"
        ),
        steps=[],
        suitability=fit,
    )


async def route_deploy(
    instruction: str,
    model_id: str,
    provider: str,
    *,
    agent_factory: Callable[..., Any] | None = None,
    memory: Any | None = None,
) -> DeployOutcome:
    """Route a natural-language deploy to the model's deployer for the environment.

    ``agent_factory`` overrides the pydantic-ai deployer factory (used in tests to
    inject a TestModel); it is ignored for cloud frameworks. ``memory`` is an
    opt-in :class:`~src.agents.ai.memory_tier.MemoryStore`; when given, a
    non-binding advisory of this service's past failures is prepended to the
    instruction (default ``None`` = untouched).
    """
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}")
    if provider not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {provider}")

    model = MODELS[model_id]
    fit = suitability(model_id, provider)

    if model.framework == "pydantic-ai":
        from src.agents.ai.local_deployer import create_local_deployer
        from src.agents.ai.memory_tier import augment_instruction

        factory = agent_factory or create_local_deployer
        agent = factory(provider=provider)
        result = await agent.run(augment_instruction(instruction, memory, provider))
        summary = str(result.output)
        trace = _strip_trailing_summary(build_trace(result.all_messages()), summary)
        steps = _tool_steps(trace)
        ok = bool(steps) and not any(_step_failed(step["result"]) for step in steps)
        return DeployOutcome(
            ok=ok,
            model=model_id,
            provider=provider,
            summary=summary,
            steps=steps,
            suitability=fit,
            trace=trace,
        )

    # Cloud frameworks (strands/adk/msft) run through their native deployers,
    # which require that cloud's credentials. Validated + dispatched, not faked.
    return _cloud_outcome(model_id, provider, fit)


async def route_deploy_stream(
    instruction: str,
    model_id: str,
    provider: str,
    *,
    agent_factory: Callable[..., Any] | None = None,
    memory: Any | None = None,
):
    """Async generator of deploy events for live UIs (tool-calling progress).

    Yields dicts:
      {"type": "tool_call",   "tool": name, "args": {...}}   # tool about to run
      {"type": "tool_result", "tool": name, "ok": bool}      # tool returned
      {"type": "result",      "outcome": DeployOutcome}      # final (last event)

    Only the local pydantic-ai path streams; cloud models yield a single result.
    """
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}")
    if provider not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {provider}")

    model = MODELS[model_id]
    fit = suitability(model_id, provider)

    if model.framework != "pydantic-ai":
        yield {"type": "result", "outcome": _cloud_outcome(model_id, provider, fit)}
        return

    from pydantic_ai import Agent as PydAgent
    from pydantic_ai.messages import (
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartStartEvent,
        TextPart,
        TextPartDelta,
        ThinkingPart,
        ThinkingPartDelta,
    )

    from src.agents.ai.local_deployer import create_local_deployer
    from src.agents.ai.memory_tier import augment_instruction

    factory = agent_factory or create_local_deployer
    agent = factory(provider=provider)

    async with agent.iter(augment_instruction(instruction, memory, provider)) as run:
        async for node in run:
            if PydAgent.is_model_request_node(node):
                # Stream the model's reasoning / intermediate text as it forms.
                async with node.stream(run.ctx) as req_stream:
                    async for event in req_stream:
                        if isinstance(event, PartStartEvent) and isinstance(event.part, (TextPart, ThinkingPart)):
                            if event.part.content:
                                yield {"type": "reasoning", "text": event.part.content}
                        elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, (TextPartDelta, ThinkingPartDelta)):
                            if event.delta.content_delta:
                                yield {"type": "reasoning", "text": event.delta.content_delta}
            elif PydAgent.is_call_tools_node(node):
                async with node.stream(run.ctx) as tool_stream:
                    async for event in tool_stream:
                        if isinstance(event, FunctionToolCallEvent):
                            part = event.part
                            yield {"type": "tool_call", "tool": part.tool_name, "args": _args_as_dict(part)}
                        elif isinstance(event, FunctionToolResultEvent):
                            result_part = event.part
                            content = getattr(result_part, "content", None)
                            yield {
                                "type": "tool_result",
                                "tool": getattr(result_part, "tool_name", ""),
                                "ok": not _step_failed(content),
                                "result": content,
                            }
        result = run.result

    summary = str(result.output)
    trace = _strip_trailing_summary(build_trace(result.all_messages()), summary)
    steps = _tool_steps(trace)
    ok = bool(steps) and not any(_step_failed(step["result"]) for step in steps)
    yield {
        "type": "result",
        "outcome": DeployOutcome(
            ok=ok,
            model=model_id,
            provider=provider,
            summary=summary,
            steps=steps,
            suitability=fit,
            trace=trace,
        ),
    }
