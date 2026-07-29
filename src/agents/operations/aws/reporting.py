"""
Reporting Agent — Lambda handler.

Triggered by:
  EventBridge scheduled rules (daily/weekly/monthly)

Dispatches to one of three reporting jobs based on event.report_type:
  - daily_slo        → SLO burn rate report across services
  - weekly_oncall    → On-call summary: MTTR, P1/P2/P3 counts, recurring patterns
  - monthly_capacity → Capacity headroom and cost-optimisation recommendations

Data source: DynamoDB incident-history table (QueryMetrics → CloudWatch for SLO data)
"""

from __future__ import annotations

import os
import time
from typing import Any

import boto3
import structlog
from boto3.dynamodb.conditions import Attr

from src.agents.adapters.dynamodb_client import paginated_scan
from src.agents.adapters.slack_client import post_webhook
from src.agents.operations.capacity_planner import (
    analyze_service_capacity,
    build_monthly_capacity_report,
)
from src.agents.operations.oncall_reporter import (
    build_weekly_oncall_report,
)
from src.agents.operations.slo_calculator import (
    build_daily_slo_report,
    calculate_service_slo,
)

logger = structlog.get_logger(__name__)

_REGION         = os.getenv("AWS_REGION", "ap-northeast-2")
_SLACK_WEBHOOK  = os.getenv("SLACK_WEBHOOK_URL", "")
_INCIDENT_TABLE = os.getenv("INCIDENT_TABLE", "incident-history")

_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)
_CW     = boto3.client("cloudwatch", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Entry point.

    EventBridge event shapes:
      { "report_type": "daily_slo" }
      { "report_type": "weekly_oncall" }
      { "report_type": "monthly_capacity" }

    Optional override:
      { "report_type": "daily_slo", "services": [...] }  # inject service metrics directly
    """
    report_type = event.get("report_type", "daily_slo")
    log = logger.bind(report_type=report_type)
    log.info("reporting.start")

    if report_type == "daily_slo":
        report = _run_daily_slo(event, log)
    elif report_type == "weekly_oncall":
        report = _run_weekly_oncall(event, log)
    elif report_type == "monthly_capacity":
        report = _run_monthly_capacity(event, log)
    else:
        raise ValueError(f"Unknown report_type: {report_type}")

    _post_slack_report(report_type, report)

    log.info("reporting.done", report_type=report_type)
    return report


# ------------------------------------------------------------------
# Daily SLO report
# ------------------------------------------------------------------

def _run_daily_slo(event: dict[str, Any], log: Any) -> dict[str, Any]:
    """
    Build a daily SLO report.

    Metric source priority:
      1. event["services"] list (injected by caller / tests)
      2. CloudWatch GetMetricStatistics (one metric per service in event["service_names"])
      3. DynamoDB incident scan (counts errors as failed_requests)
    """
    service_inputs = event["services"] if "services" in event else _fetch_slo_metrics_from_dynamo()

    summaries = [
        calculate_service_slo(
            svc["service_name"],
            total_requests=svc.get("total_requests", 1),
            failed_requests=svc.get("failed_requests", 0),
            slo_target=svc.get("slo_target", 0.999),
        )
        for svc in service_inputs
    ]

    report = build_daily_slo_report(summaries)
    log.info("reporting.slo_done", services=len(summaries))
    return report


#: The retention the incident writer stamps onto `ttl`
#: (``aws/executor._record_incident``: ``time.time() + 90 * 86400``). Only used
#: to place rows that predate `created_at`; the two are kept in step by
#: tests/test_report_windows.py rather than by hope.
_LEGACY_RETENTION_SEC = 90 * 86400


def _created_epoch(item: dict[str, Any]) -> int | None:
    """When the incident row was written, in epoch seconds.

    `created_at` is an ISO-8601 UTC string every writer stamps unconditionally.
    `ttl` is a *retention* field — it is the write time plus 90 days — and using
    it as a timestamp is what broke both windows in this module. It stays here
    only as a fallback for rows written before `created_at` existed, and returns
    None when neither is present, because a row we cannot place in time must be
    left out of a time window rather than guessed into one.
    """
    raw = item.get("created_at")
    if isinstance(raw, str) and raw:
        try:
            return int(
                time.mktime(time.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
            )
        except ValueError:
            pass
    ttl = item.get("ttl")
    if ttl is not None:
        try:
            return int(ttl) - _LEGACY_RETENTION_SEC
        except (TypeError, ValueError):
            return None
    return None


def _fetch_slo_metrics_from_dynamo(hours: int = 24) -> list[dict[str, Any]]:
    """Scan incident-history for the last N hours to produce coarse SLO inputs."""
    try:
        table  = _DYNAMO.Table(_INCIDENT_TABLE)
        cutoff = int(time.time()) - hours * 3600
        # This filtered on `ttl >= cutoff`. `ttl` is the write time plus ninety
        # days, and `cutoff` is in the past, so the comparison was true for every
        # row that had not already expired: the "last 24 hours" of this daily SLO
        # report has always been the entire 90-day retention window, and the
        # failure counts it feeds have been inflated by however many days of
        # history the table happened to hold.
        cutoff_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(cutoff))
        items = paginated_scan(table, FilterExpression=Attr("created_at").gte(cutoff_iso))

        # Aggregate by alarm_name (service proxy)
        service_counts: dict[str, dict[str, int]] = {}
        for item in items:
            created = _created_epoch(item)
            if created is None or created < cutoff:
                continue
            name = item.get("alarm_name", "unknown")
            service_counts.setdefault(name, {"failed": 0})
            if not item.get("resolved", True):
                service_counts[name]["failed"] += 1

        return [
            {
                "service_name":    name,
                "total_requests":  max(100, counts["failed"] * 100),
                "failed_requests": counts["failed"],
            }
            for name, counts in service_counts.items()
        ] or [{"service_name": "platform", "total_requests": 1000, "failed_requests": 0}]

    except Exception as exc:
        logger.warning("reporting.slo.dynamo_error", error=str(exc))
        return [{"service_name": "platform", "total_requests": 1000, "failed_requests": 0}]


# ------------------------------------------------------------------
# Weekly on-call report
# ------------------------------------------------------------------

def _run_weekly_oncall(event: dict[str, Any], log: Any) -> dict[str, Any]:
    # Use "in event" check so that an explicit empty list [] is respected
    # (avoids triggering DynamoDB fetch when caller deliberately passes []).
    current  = event["current_incidents"]  if "current_incidents"  in event else _fetch_incidents_from_dynamo(days=7)
    previous = event["previous_incidents"] if "previous_incidents" in event else _fetch_incidents_from_dynamo(days=14, offset_days=7)

    report = build_weekly_oncall_report(current, previous)
    log.info("reporting.oncall_done", total=report["current"]["total_incidents"])
    return report


def _in_window(item: dict[str, Any], start: int, end: int) -> bool:
    """Whether the row belongs to [start, end]. Undateable rows do not."""
    created = _created_epoch(item)
    return created is not None and start <= created <= end


def _fetch_incidents_from_dynamo(
    days: int = 7,
    offset_days: int = 0,
) -> list[dict[str, Any]]:
    try:
        table    = _DYNAMO.Table(_INCIDENT_TABLE)
        now      = int(time.time())
        window_end   = now - offset_days * 86400
        window_start = window_end - days * 86400

        items = paginated_scan(table)

        filtered = [
            {
                "alarm_name":   item.get("alarm_name", "unknown"),
                "service_name": item.get("alarm_name", "unknown"),
                "severity":     item.get("severity", "P3"),
                "root_cause":   item.get("root_cause", ""),
                "resolved":     item.get("resolved", False),
                # When the incident began. `triggered_at` is the source's own fire
                # time; `created_at` is when we wrote the row, i.e. the earliest
                # moment we can prove we knew. Falling back to the latter
                # understates MTTR but never invents time we cannot account for.
                #
                # This read `resolved_at` — the same key as the line below it — so
                # every incident handed to the reporter began and ended at the
                # same instant and `average_mttr_minutes` has been a structural
                # 0.0 in every weekly report ever sent. The unit tests never saw
                # it because they hand `summarize_incidents` a fixture with two
                # different timestamps, which is a shape this, the only producer,
                # could not emit.
                "started_at":   item.get("triggered_at") or item.get("created_at", ""),
                # Absent on unresolved rows since the executor stopped defaulting
                # it; the reporter drops those from the MTTR sample rather than
                # counting them as instant.
                "resolved_at":  item.get("resolved_at", ""),
                # The runbook, not the alarm. Recurring-pattern grouping prefers
                # `runbook_id`, so copying the alarm name in here collapsed the
                # grouping back to per-alarm and hid exactly what it exists to
                # show: distinct alarms that keep landing on one runbook.
                "runbook_id":   item.get("runbook_id", "unknown"),
            }
            for item in items
            # Placed by when the row was written, not by inverting its retention
            # field. The arithmetic here used to be `ttl - 90 days`, which is
            # right only for as long as nobody changes the writer's retention —
            # and a row with no `ttl` at all defaulted to `now`, landing it 90
            # days in the past and dropping it from every report silently.
            if _in_window(item, window_start, window_end)
        ]
        return filtered
    except Exception as exc:
        logger.warning("reporting.oncall.dynamo_error", error=str(exc))
        return []


# ------------------------------------------------------------------
# Monthly capacity report
# ------------------------------------------------------------------

def _run_monthly_capacity(event: dict[str, Any], log: Any) -> dict[str, Any]:
    service_data = event["services"] if "services" in event else _fetch_capacity_from_cloudwatch()

    analyses = [
        analyze_service_capacity(
            svc["service_name"],
            samples=svc.get("samples", [{"cpu_utilization": 50.0, "memory_utilization": 60.0}]),
            monthly_cost_usd=svc.get("monthly_cost_usd"),
        )
        for svc in service_data
    ]

    report = build_monthly_capacity_report(analyses)
    log.info("reporting.capacity_done", services=len(analyses))
    return report


def _fetch_capacity_from_cloudwatch() -> list[dict[str, Any]]:
    """
    Fetch CPU and memory utilization from CloudWatch for EKS workloads.
    Returns a minimal placeholder when CloudWatch data is unavailable.
    """
    try:
        now   = time.time()
        start = now - 30 * 86400  # 30-day look-back

        resp = _CW.list_metrics(Namespace="AWS/EKS", MetricName="node_cpu_utilization")
        seen_services: dict[str, list[dict[str, float]]] = {}

        for metric in resp.get("Metrics", []):
            dims = {d["Name"]: d["Value"] for d in metric.get("Dimensions", [])}
            cluster = dims.get("ClusterName", "unknown")

            stats = _CW.get_metric_statistics(
                Namespace   = "AWS/EKS",
                MetricName  = "node_cpu_utilization",
                Dimensions  = metric["Dimensions"],
                StartTime   = start,
                EndTime     = now,
                Period      = 86400,
                Statistics  = ["Average", "Maximum"],
            )
            for pt in stats.get("Datapoints", []):
                seen_services.setdefault(cluster, []).append({
                    "cpu_utilization":    pt.get("Average", 0.0),
                    "memory_utilization": 0.0,  # separate query needed
                })

        if seen_services:
            return [
                {"service_name": name, "samples": samples}
                for name, samples in seen_services.items()
            ]

    except Exception as exc:
        logger.warning("reporting.capacity.cw_error", error=str(exc))

    return [{"service_name": "platform", "samples": [{"cpu_utilization": 50.0, "memory_utilization": 60.0}]}]


# ------------------------------------------------------------------
# Slack notification
# ------------------------------------------------------------------

_REPORT_COLOR = {
    "daily_slo":        "#3498DB",
    "weekly_oncall":    "#9B59B6",
    "monthly_capacity": "#1ABC9C",
}

_REPORT_TITLE = {
    "daily_slo":        ":bar_chart: Daily SLO Report",
    "weekly_oncall":    ":pager: Weekly On-Call Summary",
    "monthly_capacity": ":cloud: Monthly Capacity Report",
}


def _post_slack_report(report_type: str, report: dict[str, Any]) -> None:
    if not _SLACK_WEBHOOK:
        logger.warning("reporting.slack.skip", reason="SLACK_WEBHOOK_URL not set")
        return

    color = _REPORT_COLOR.get(report_type, "#95A5A6")
    title = _REPORT_TITLE.get(report_type, f"Report: {report_type}")

    summary_text = _build_summary_text(report_type, report)

    payload = {
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": title},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": summary_text},
                },
            ],
        }]
    }

    try:
        post_webhook(_SLACK_WEBHOOK, payload)
        logger.info("reporting.slack.sent", report_type=report_type)
    except Exception as exc:
        logger.error("reporting.slack.error", error=str(exc))


def _build_summary_text(report_type: str, report: dict[str, Any]) -> str:
    if report_type == "daily_slo":
        counts = report.get("status_counts", {})
        top    = report.get("top_unstable_services", [])
        return (
            f"*Services:* {report.get('service_count', 0)}  "
            f"✅ {counts.get('healthy', 0)} healthy  "
            f"⚠️ {counts.get('warning', 0)} warning  "
            f"🔴 {counts.get('critical', 0)} critical\n"
            f"*Top unstable:* {', '.join(f'`{s}`' for s in top) or 'none'}"
        )

    if report_type == "weekly_oncall":
        curr  = report.get("current", {})
        trend = report.get("trend", {})
        delta = trend.get("incident_delta", 0)
        sign  = "+" if delta > 0 else ""
        top_services = ", ".join(f"`{s['name']}`" for s in curr.get("top_services", []))
        return (
            f"*Incidents this week:* {curr.get('total_incidents', 0)} "
            f"({sign}{delta} vs last week)\n"
            f"*Avg MTTR:* {curr.get('average_mttr_minutes', 0):.0f} min\n"
            f"*Top services:* {top_services}"
        )

    if report_type == "monthly_capacity":
        priority = report.get("priority_services", [])
        return (
            f"*Services analysed:* {report.get('service_count', 0)}\n"
            f"*Priority (scale up / review):* "
            f"{', '.join(f'`{s}`' for s in priority) or 'none'}"
        )

    return f"Report generated: {report_type}"
