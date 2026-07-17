# Runtime image for the On-Prem control-plane APIs (reference #7 production packaging).
#
# One image, two entrypoints — the Helm chart picks the command per Deployment:
#   webhook: uvicorn src.agents.ai.onprem_webhook_api:app   (Day-2: Alertmanager → pipeline → approval gate)
#   router:  uvicorn src.agents.ai.local_deploy_api:app     (deploy front door + SSE; needs external build tooling)
#
# kubectl is baked in because the Day-2 executor (onprem_runner) shells out to it
# for the four reversible actions (restart / undo / scale / polite drain); in-cluster
# it authenticates via the chart's ServiceAccount, scoped by the least-privilege RBAC.
FROM python:3.11-slim

ARG KUBECTL_VERSION=v1.31.4
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && ARCH=$(dpkg --print-architecture) \
    && curl -fsSL -o /usr/local/bin/kubectl \
        "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/

# Project deps (boto3/structlog/requests/pyyaml/strands) + the ASGI stack the two
# APIs are served with. The MLX/LLM extra is NOT installed — the model brain stays
# an external endpoint (values: llm.endpoint), never in this container.
RUN pip install --no-cache-dir . fastapi "uvicorn[standard]" pydantic-ai-slim[openai]

ENV PYTHONPATH=/app
EXPOSE 8077 8078

# Default to the Day-2 webhook plane; the chart overrides args per component.
CMD ["uvicorn", "src.agents.ai.onprem_webhook_api:app", "--host", "0.0.0.0", "--port", "8078"]
