"""Has anything started costing money since the last look?

`probe_cloud_spend.py` answers "what is this spending **right now**", and it is
right every time it runs. The gap it does not close is that **nobody runs it**:
the forgotten `slackops-devops-agent` burned for 18 days and what finally caught
it was a budget alert at $8.50, not a check. So this is the same measurement,
made *comparable* — it keeps the last answer and reports what is new.

Deliberately **not** a second threshold alarm. Budgets already answer "how much",
they are cheap, and on 2026-08-09 the AWS one **worked**. What they cannot answer
is "how much of this is new", because a budget crossing tells you the total moved,
eighteen days late and with no name attached. This answers the other half:

    budgets  → 얼마나 (how much, eventually)
    this     → 무엇이 새로 (what started, on day one)

So the signal here is **a charged service that was not charged before**, which is
exactly the shape of every incident this repo has had. No invented threshold: a
rule you cannot satisfy teaches people to route around it, which is the lesson the
₩20 budget cost us.

The measurement itself is imported, never re-implemented — a second source of truth
for "what are we spending" is how the numbers drift apart (431aeab deleted one of
those already).

    make spend-watch          # compare against the last snapshot
    make spend-watch-baseline # accept current state as the new baseline

Exit codes:
  0 = nothing newly charged (or first run, which only records a baseline)
  1 = something is charging that was not before (usable as a cron signal)
  2 = could not measure, so "nothing new" cannot be read as "nothing there"
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from probe_cloud_spend import (  # noqa: E402
    _window,
    azure_spend,
    gcp_actual_spend,
    spend_by_service,
)

#: Kept out of git: it is machine state, not a repo fact, and a daily job that
#: dirties the working tree is a daily job people turn off.
DEFAULT_STATE = Path(__file__).resolve().parents[1] / ".state" / "spend-snapshot.json"


def observe() -> dict | None:
    """Today's charged services per provider. None when a provider could not be read."""
    start, end = _window(None)
    snapshot: dict = {"window": [start, end]}

    aws = spend_by_service(start, end)
    if aws is None:
        return None
    _, ranked = aws
    snapshot["aws"] = {service: round(amount, 2) for service, amount in ranked}

    azure = azure_spend(start, end)
    if azure is None:
        return None
    snapshot["azure"] = {
        f"{name} / {service}": round(amount, 2)
        for name, _currency, ranked in azure
        for service, amount in ranked
    }

    status, detail = gcp_actual_spend()
    snapshot["gcp"] = {"status": status, "detail": detail}
    return snapshot


def newly_charged(previous: dict, current: dict) -> dict[str, list[str]]:
    """Services charging now that were not charging in the previous snapshot.

    Only additions. A line that disappears means something was switched off, which
    is not a thing to wake anyone for.
    """
    added: dict[str, list[str]] = {}
    for provider in ("aws", "azure"):
        before = set(previous.get(provider, {}))
        now = set(current.get(provider, {}))
        if fresh := sorted(now - before):
            added[provider] = fresh
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE,
                        help="where the previous answer is kept")
    parser.add_argument("--baseline", action="store_true",
                        help="record the current state and report nothing")
    args = parser.parse_args()

    current = observe()
    if current is None:
        print("측정하지 못했다. 이것은 '새 과금 없음'이 아니다.", file=sys.stderr)
        return 2
    current["observed_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    previous = None
    if args.state.is_file():
        try:
            previous = json.loads(args.state.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None          # a corrupt snapshot is no snapshot, not a finding

    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.baseline or previous is None:
        why = "요청대로 기준선을 잡았다" if args.baseline else "이전 스냅샷이 없다 — 기준선을 잡았다"
        print(f"{why}: {args.state}")
        print(f"  AWS {len(current['aws'])}종 · Azure {len(current['azure'])}종 · GCP {current['gcp']['status']}")
        return 0

    if previous.get("gcp", {}).get("status") != current["gcp"]["status"]:
        print(f"GCP 관측 상태가 바뀌었다: {previous.get('gcp', {}).get('status')}"
              f" → {current['gcp']['status']}  ({current['gcp']['detail']})")

    added = newly_charged(previous, current)
    if not added:
        print(f"새로 과금되기 시작한 것은 없다 (기준 {previous.get('observed_at', '?')})")
        return 0

    print(f"새로 과금되기 시작한 것이 있다 (기준 {previous.get('observed_at', '?')})")
    for provider, services in added.items():
        for service in services:
            amount = current[provider][service]
            print(f"  {provider.upper():<6} {service:<48} {amount}")
    print("\n무엇이 켰는지 확인할 것. 이 스크립트는 아무것도 끄지 않는다 — 조치는 사람이 정한다.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
