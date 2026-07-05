"""Shared DynamoDB helpers used across Lambda handlers."""

from __future__ import annotations

from typing import Any


def paginated_scan(table: Any, **scan_kwargs: Any) -> list[dict[str, Any]]:
    """Scan an entire DynamoDB table, following LastEvaluatedKey pagination.

    Any keyword arguments (FilterExpression, ProjectionExpression, etc.)
    are forwarded to every scan call so filters are applied server-side.
    """
    response = table.scan(**scan_kwargs)
    items: list[dict[str, Any]] = list(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"], **scan_kwargs)
        items.extend(response.get("Items", []))
    return items
