"""Current-record authorization for registry previews, independent of transport.

The caller authenticates the session and supplies its username as ``subject``.
Neither a browser-supplied identity nor a session's cached role is authoritative.
Production adapters must read the current user record without demo fallback or
cross-request caching. This module does not implement login or storage I/O.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Protocol

from src.agents.platform.registry_planner import (
    PlanEnvelope,
    PlannerError,
    SnapshotReader,
    plan_snapshot,
    validate_attachment_request,
)


class CurrentUserReader(Protocol):
    """Fetch by canonical username; None means absent, exceptions mean outage.

    Return an application record with username, role and registry_write_tenants
    (a list of exact tenant names). Ignore read-side tenants for this decision.
    Implementations must not return cached/demo users after a failed lookup.
    """

    def get_current_user(self, username: str) -> Mapping[str, object] | None: ...


def plan_authorized_snapshot(
    request: Mapping[str, object], *, subject: str | None,
    users: CurrentUserReader, reader: SnapshotReader,
    request_id: str, now: datetime,
) -> PlanEnvelope:
    """Authorize the exact copied request, then call the existing offline planner.

    Username lowercasing matches the dashboard's persisted user keys. Every
    invocation rereads the user, including repeated requests from the same
    subject. Admins require an explicit write grant, just like operators.
    Grant revocation during/after a preview still requires reauthorization at
    submission; this function cannot make a multi-store operation atomic.
    """
    username, values = authorize_attachment_request(request, subject=subject, users=users)

    return plan_snapshot(
        values, subject=username, reader=reader, request_id=request_id, now=now,
    )


def authorize_attachment_request(
    request: Mapping[str, object], *, subject: str | None, users: CurrentUserReader,
) -> tuple[str, dict[str, str]]:
    """Recheck the current record for preview and stored-plan consumption."""
    if (not isinstance(subject, str) or not subject or len(subject) > 256
            or subject != subject.strip() or any(ord(char) < 32 or ord(char) == 127 for char in subject)):
        raise PlannerError("session_required", 401)
    username = subject.lower()
    values = validate_attachment_request(request)
    try:
        record = users.get_current_user(username)
    except Exception:
        raise PlannerError("user_store_unavailable", 503) from None

    if not isinstance(record, Mapping) or record.get("username") != username:
        raise PlannerError("registry_write_forbidden", 403)
    role = record.get("role")
    grants = record.get("registry_write_tenants")
    if (not isinstance(role, str) or role not in ("operator", "admin")
            or not isinstance(grants, list)
            or not all(isinstance(tenant, str) for tenant in grants)
            or values["tenant"] not in grants):
        raise PlannerError("registry_write_forbidden", 403)

    return username, values
