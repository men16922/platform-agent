"""Deployable agent for Vertex AI Agent Engine — the GCP ④ Host role target.

A minimal custom-template agent (a class with ``set_up`` + ``query``) that the
Agent Engine runtime pickles, uploads to the staging bucket, installs, and
serves. Kept small like the AgentCore entrypoint: it proves the hosting path
end-to-end — a real reasoning engine answering real queries via Gemini — without
the full deployer's toolchain.
"""

from __future__ import annotations


class PlatformDeployerAgent:
    def __init__(self, model: str = "gemini-2.5-flash", project: str | None = None, location: str = "us-central1"):
        self.model = model
        self.project = project
        self.location = location

    def set_up(self) -> None:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=self.project, location=self.location)
        self._model = GenerativeModel(self.model)

    def query(self, prompt: str = "Who are you and where are you running?") -> dict:
        resp = self._model.generate_content(prompt)
        return {"result": resp.text, "model": self.model, "hosted_on": "vertex-agent-engine"}
