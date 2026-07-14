# Bedrock AgentCore requires linux/arm64 container images.
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# AgentCore runtime contract: HTTP server on :8080 (POST /invocations, GET /ping).
EXPOSE 8080
CMD ["python", "app.py"]
