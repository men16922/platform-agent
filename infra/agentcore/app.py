"""AgentCore runtime entrypoint — hosts a minimal Claude-backed platform agent.

Implements the Bedrock AgentCore runtime contract (POST /invocations, GET /ping
on :8080) via the bedrock-agentcore SDK. Kept intentionally small: it proves the
hosting path (the ④ Host role) end-to-end — a real container on a real managed
runtime answering real invocations — without dragging the full deployer's kubectl
/docker toolchain into the image.
"""

from __future__ import annotations

import os

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

_MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
_REGION = os.getenv("AWS_REGION", "us-east-1")

_SYSTEM = (
    "You are the platform-agent deployment assistant, hosted on Amazon Bedrock "
    "AgentCore. Answer concisely."
)

_bedrock = boto3.client("bedrock-runtime", region_name=_REGION)


@app.entrypoint
def invoke(payload: dict) -> dict:
    prompt = (payload or {}).get("prompt", "Who are you and where are you running?")
    resp = _bedrock.converse(
        modelId=_MODEL_ID,
        system=[{"text": _SYSTEM}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 256, "temperature": 0.2},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    return {"result": text, "model": _MODEL_ID, "hosted_on": "bedrock-agentcore"}


if __name__ == "__main__":
    app.run()
