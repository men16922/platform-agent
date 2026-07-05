"""Shared Slack webhook helper used across Lambda handlers."""

from __future__ import annotations

from typing import Any

import requests


def post_webhook(webhook_url: str, payload: dict[str, Any], *, timeout: int = 10) -> None:
    """POST a JSON payload to a Slack incoming-webhook URL.

    Raises requests.HTTPError on non-2xx responses.
    """
    resp = requests.post(webhook_url, json=payload, timeout=timeout)
    resp.raise_for_status()
