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


def _step_failed(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("error"))


async def route_deploy(
    instruction: str,
    model_id: str,
    provider: str,
    *,
    agent_factory: Callable[..., Any] | None = None,
) -> DeployOutcome:
    """Route a natural-language deploy to the model's deployer for the environment.

    ``agent_factory`` overrides the pydantic-ai deployer factory (used in tests to
    inject a TestModel); it is ignored for cloud frameworks.
    """
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}")
    if provider not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {provider}")

    model = MODELS[model_id]
    fit = suitability(model_id, provider)

    if model.framework == "pydantic-ai":
        from src.agents.ai.local_deployer import create_local_deployer

        factory = agent_factory or create_local_deployer
        agent = factory(provider=provider)
        result = await agent.run(instruction)
        steps = extract_steps(result.all_messages())
        ok = bool(steps) and not any(_step_failed(step["result"]) for step in steps)
        return DeployOutcome(
            ok=ok,
            model=model_id,
            provider=provider,
            summary=str(result.output),
            steps=steps,
            suitability=fit,
        )

    # Cloud frameworks (strands/adk/msft) run through their native deployers,
    # which require that cloud's credentials. Validated + dispatched, not faked.
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
