"""Cross-account STS AssumeRole with graceful in-account fallback.

Reference: AWSome AI Gateway Tier 2 #4. When the platform operates across AWS
accounts, an adapter assumes a role in the *target* account and builds a boto3
``Session`` from the temporary credentials. If the AssumeRole call fails
(AccessDenied, throttling, a broken trust policy) — or the shared circuit breaker
is already OPEN after repeated failures — the helper degrades gracefully to
in-account credentials instead of failing the whole operation. This mirrors the
region-failover precedent in the executor Lambda and reuses the Tier 1
``CircuitBreaker`` rather than re-implementing resilience.

The boto3/STS client is created behind a module-level ``_sts_client`` seam so
tests inject a fake without moto, matching the adapter test idiom
(``monkeypatch.setattr(mod, "_sts_client", ...)``).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from src.agents.ai.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_DEFAULT_SESSION_NAME = "platform-agent"

# One shared breaker so repeated AssumeRole failures fast-fail to in-account
# credentials across calls, instead of every call re-hitting a broken STS or
# trust path. Callers may pass their own breaker (tests do, for isolation).
_BREAKER = CircuitBreaker(name="sts-assume-role", failure_threshold=3, reset_timeout=60.0)


@dataclass
class SessionResult:
    """A boto3 ``Session`` plus how it was obtained, for traces / observability."""

    session: Any
    role_arn: str
    assumed: bool  # cross-account AssumeRole succeeded
    fell_back: bool  # degraded to in-account credentials


def _sts_client(region: str | None):
    import boto3

    return boto3.client("sts", region_name=region)


def _in_account_session(region: str | None):
    import boto3

    return boto3.Session(region_name=region)


def _assume(role_arn: str, region: str | None, session_name: str, external_id: str | None):
    import boto3

    sts = _sts_client(region)
    kwargs: dict[str, Any] = {"RoleArn": role_arn, "RoleSessionName": session_name}
    if external_id:
        kwargs["ExternalId"] = external_id
    creds = sts.assume_role(**kwargs)["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=region,
    )


def assume_role_session(
    role_arn: str = "",
    *,
    region: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    external_id: str | None = None,
    fallback: bool = True,
    breaker: CircuitBreaker | None = None,
) -> SessionResult:
    """Return a boto3 ``Session`` for ``role_arn``, degrading to in-account on failure.

    An empty ``role_arn`` (no cross-account requested) returns an in-account
    session unchanged, so this is a safe drop-in for existing single-account
    callers. With ``fallback=False`` an AssumeRole failure (or an OPEN circuit)
    is raised instead of degrading — for callers that must not silently run in
    the wrong account.
    """
    if not role_arn:
        return SessionResult(_in_account_session(region), "", assumed=False, fell_back=False)

    br = breaker if breaker is not None else _BREAKER
    try:
        # breaker.call fast-fails (raises) when OPEN and records failures so the
        # circuit opens after the threshold; we catch below to degrade.
        session = br.call(_assume, role_arn, region, session_name, external_id)
        return SessionResult(session, role_arn, assumed=True, fell_back=False)
    except Exception as exc:
        if not fallback:
            raise
        logger.warning(
            "STS assume_role failed for %s (%s); falling back to in-account credentials",
            role_arn,
            type(exc).__name__,
        )
        return SessionResult(_in_account_session(region), role_arn, assumed=False, fell_back=True)


def assume_role_arn_from_env() -> str:
    """Operator-configured cross-account role to assume, if any (empty = disabled)."""
    return os.getenv("AWS_ASSUME_ROLE_ARN", "")


__all__ = [
    "SessionResult",
    "assume_role_arn_from_env",
    "assume_role_session",
]
