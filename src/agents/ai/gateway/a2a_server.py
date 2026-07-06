"""
A2A Server — FastAPI-based Agent-to-Agent protocol server.

Implements the A2A protocol (v1.0) HTTP+JSON binding, exposing the platform
deployer agents as an A2A-compliant service that other agents can discover
and communicate with.

Usage:
    from src.agents.ai.gateway.a2a_server import A2AServer, create_a2a_app

    app = create_a2a_app()
    # Run with: uvicorn src.agents.ai.gateway.a2a_server:app --port 8000
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    """A2A Task states."""

    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELED = "TASK_STATE_CANCELED"
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"


@dataclass
class Message:
    """A2A Message."""

    role: str  # "ROLE_USER" or "ROLE_AGENT"
    parts: list[dict[str, Any]]
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str | None = None
    task_id: str | None = None


@dataclass
class Task:
    """A2A Task."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: dict[str, Any] = field(default_factory=lambda: {
        "state": TaskState.SUBMITTED.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)


class A2AServer:
    """In-memory A2A Server implementing the core protocol operations."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._card = self._load_agent_card()

    def _load_agent_card(self) -> dict:
        """Load the agent card from JSON file."""
        card_path = os.path.join(
            os.path.dirname(__file__), "..", "a2a_card.json"
        )
        try:
            with open(card_path) as f:
                return json.load(f)
        except FileNotFoundError:
            return {"name": "Platform Deployer Agent", "version": "1.0.0"}

    @property
    def agent_card(self) -> dict:
        """Get the agent card."""
        return self._card

    def send_message(self, message: dict[str, Any], configuration: dict | None = None) -> dict:
        """Process an incoming message and create/update a task.

        Args:
            message: A2A Message object (role, parts, messageId, etc.)
            configuration: Optional send configuration.

        Returns:
            A2A response containing either a Task or Message.
        """
        task = Task()

        # Store the user message in history
        task.history.append(message)

        # Extract the text content from parts
        text_parts = [p.get("text", "") for p in message.get("parts", []) if "text" in p]
        user_text = " ".join(text_parts)

        # Process the request (dispatch to appropriate handler)
        response_text = self._process_request(user_text, task)

        # Update task status
        task.status = {
            "state": TaskState.COMPLETED.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Add artifact with response
        task.artifacts = [{
            "artifactId": str(uuid.uuid4()),
            "name": "response",
            "parts": [{"text": response_text}],
        }]

        # Store task
        self._tasks[task.id] = task

        return {
            "task": {
                "id": task.id,
                "contextId": task.context_id,
                "status": task.status,
                "artifacts": task.artifacts,
            }
        }

    def get_task(self, task_id: str) -> dict | None:
        """Get a task by ID.

        Returns:
            Task dict or None if not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id,
            "contextId": task.context_id,
            "status": task.status,
            "artifacts": task.artifacts,
            "history": task.history,
        }

    def list_tasks(self, context_id: str | None = None, status: str | None = None) -> dict:
        """List tasks with optional filtering.

        Returns:
            List of tasks matching criteria.
        """
        tasks = list(self._tasks.values())

        if context_id:
            tasks = [t for t in tasks if t.context_id == context_id]
        if status:
            tasks = [t for t in tasks if t.status.get("state") == status]

        return {
            "tasks": [
                {"id": t.id, "contextId": t.context_id, "status": t.status}
                for t in tasks
            ],
            "nextPageToken": "",
            "pageSize": len(tasks),
            "totalSize": len(tasks),
        }

    def cancel_task(self, task_id: str) -> dict | None:
        """Cancel a task.

        Returns:
            Updated task dict or None if not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            return None

        terminal_states = {TaskState.COMPLETED.value, TaskState.FAILED.value, TaskState.CANCELED.value}
        if task.status.get("state") in terminal_states:
            return None  # Cannot cancel terminal tasks

        task.status = {
            "state": TaskState.CANCELED.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return {"id": task.id, "contextId": task.context_id, "status": task.status}

    def _process_request(self, text: str, task: Task) -> str:
        """Process a user request text and return a response.

        This is a simplified dispatcher — in production, this would
        route to the actual deployer agents.
        """
        text_lower = text.lower()

        if "deploy" in text_lower:
            return f"Deployment request received. Task {task.id} created. Use the deployer agent for execution."
        elif "validate" in text_lower:
            return f"Validation request received. Task {task.id} will check deployment health."
        elif "rollback" in text_lower:
            return f"Rollback request received. Task {task.id} will revert the deployment."
        elif "policy" in text_lower or "guard" in text_lower:
            return f"Policy evaluation request. Task {task.id} will check against deployment rules."
        else:
            return f"Request acknowledged. Task {task.id} created for processing."


def create_a2a_app():
    """Create a FastAPI app implementing the A2A HTTP+JSON protocol binding.

    Returns:
        FastAPI app instance (requires fastapi to be installed).
    """
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError("fastapi is required: pip install fastapi")

    app = FastAPI(title="Platform Agent A2A Server", version="1.0.0")
    server = A2AServer()

    @app.get("/.well-known/agent-card.json")
    async def get_agent_card():
        return JSONResponse(content=server.agent_card)

    @app.post("/message:send")
    async def send_message(body: dict):
        message = body.get("message")
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        configuration = body.get("configuration")
        result = server.send_message(message, configuration)
        return JSONResponse(content=result)

    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str):
        task = server.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return JSONResponse(content={"task": task})

    @app.get("/tasks")
    async def list_tasks(contextId: str | None = None, status: str | None = None):
        result = server.list_tasks(context_id=contextId, status=status)
        return JSONResponse(content=result)

    @app.post("/tasks/{task_id}:cancel")
    async def cancel_task(task_id: str):
        result = server.cancel_task(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found or not cancelable")
        return JSONResponse(content={"task": result})

    return app


# Module-level app for uvicorn
app = create_a2a_app() if os.environ.get("A2A_SERVER_ENABLED") else None
