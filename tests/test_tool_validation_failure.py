"""Rejected Pydantic tool arguments must not become a successful deployment."""
import asyncio
import json

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel, DeltaToolCall

from src.agents.ai import model_router as router
from src.agents.ai import local_deployer as deployer


@pytest.mark.parametrize("streaming", [False, True])
def test_rejected_mutation_and_successful_read_are_a_failed_run(streaming):
    mutations = []

    def deploy_to_cluster(ports: list[int]) -> dict:
        mutations.append(ports)
        return {"status": "success"}

    def validate_deployment() -> dict:
        return {"healthy": True}

    def respond(messages, info):
        if len(messages) == 1:
            return ModelResponse(parts=[
                ToolCallPart("deploy_to_cluster", {"ports": "[8080]"}, "bad-args"),
                ToolCallPart("validate_deployment", {}, "read-only"),
            ])
        return ModelResponse(parts=[TextPart("Done")])

    async def respond_stream(messages, info):
        response = respond(messages, info)
        if isinstance(response.parts[0], TextPart):
            yield "Done"
        else:
            yield {i: DeltaToolCall(name=part.tool_name, json_args=json.dumps(part.args), tool_call_id=part.tool_call_id)
                   for i, part in enumerate(response.parts)}

    def factory(**kwargs):
        return Agent(FunctionModel(respond, stream_function=respond_stream), tools=[deploy_to_cluster, validate_deployment])

    async def run():
        if streaming:
            events = [e async for e in router.route_deploy_stream("deploy", "local-qwen", "onprem", agent_factory=factory)]
            tool_result = next(e for e in events if e["type"] == "tool_result" and e["tool"] == "deploy_to_cluster")
            assert tool_result["ok"] is False
            return events[-1]["outcome"]
        return await router.route_deploy("deploy", "local-qwen", "onprem", agent_factory=factory)

    outcome = asyncio.run(run())
    assert mutations == []
    assert outcome.ok is False
    assert outcome.steps[0]["result"]["tool_completed"] is False
    assert outcome.steps[0]["result"]["error"]


def test_omitted_replica_count_never_reaches_the_deployment_adapter(monkeypatch):
    from types import SimpleNamespace
    mutations = []

    def deploy(spec, image_uri):
        mutations.append(spec.replicas)
        return SimpleNamespace(status=SimpleNamespace(value="success"), deployment_id="test/app",
                               namespace="test", replicas_desired=spec.replicas, endpoint="", error="", metadata={})

    monkeypatch.setattr(deployer, "get_deployment_adapters", lambda _: SimpleNamespace(cluster=SimpleNamespace(deploy=deploy)))

    def respond(messages, info):
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart("deploy_to_cluster", {
                "service_name": "app", "image": "app", "version": "v1", "image_uri": "local/app:v1",
                "namespace": "test", "provider": "onprem",
            }, "missing-replicas")])
        return ModelResponse(parts=[TextPart("Stopped")])

    outcome = asyncio.run(router.route_deploy("Deploy with 2 replicas", "local-qwen", "onprem",
                        agent_factory=lambda **kwargs: deployer.create_local_deployer(model=FunctionModel(respond))))
    assert mutations == []
    assert outcome.ok is False
