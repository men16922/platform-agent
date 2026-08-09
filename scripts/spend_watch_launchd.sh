#!/bin/sh
# Daily wrapper for `watch_cloud_spend.py`, run by launchd.
#
# The probe was already right whenever it ran; what it could not fix is that nobody
# ran it. This is the part that runs and — just as importantly — the part that stays
# quiet. It speaks only when something is new or when it is still failing after a
# retry, because a daily notification that says "all fine" is a notification people
# turn off, and this repo has already paid for that lesson (the ₩20 budget fired
# every single month and therefore told nobody anything).
#
# Notification lives here rather than in the watcher on purpose: the watcher is
# guarded to make no process calls of its own, so it can never grow a second way of
# asking the cloud what we are spending.
#
# Exit codes pass through: 0 = quiet, 1 = something new, 2 = could not measure.
#
# POSIX sh rather than zsh, and that is not a style choice: the guards below run in
# CI, CI is Linux, and Linux has no /bin/zsh. Written as zsh first, it failed there
# — which is the "게이트의 초록에는 환경이 붙는다" trap (Risk 12②) in its plainest form,
# caught by the machine that does not look like mine.
#
# Test seams (used by tests/test_cloud_spend_watch.py, default to the real thing):
#   SPEND_WATCH_REPO         where to run
#   SPEND_WATCH_RETRY_SLEEP  seconds to wait before the one retry
#   SPEND_WATCH_NOTIFY_CMD   called with the message instead of osascript

set -u
REPO="${SPEND_WATCH_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG="$REPO/.state/spend-watch.log"
RETRY_SLEEP="${SPEND_WATCH_RETRY_SLEEP:-90}"
mkdir -p "$REPO/.state"

stamp() { date '+%Y-%m-%d %H:%M:%S%z'; }
look()  { (cd "$REPO" && python3 scripts/watch_cloud_spend.py 2>&1); }

notify() {
  if [ -n "${SPEND_WATCH_NOTIFY_CMD:-}" ]; then
    "$SPEND_WATCH_NOTIFY_CMD" "$1"
    return
  fi
  osascript -e "display notification \"$1\" with title \"platform-agent 비용\"" 2>/dev/null
}

output="$(look)"
code=$?

# A transient failure is not news. Cost Management answers 429 "Too many requests"
# when asked a few times in a row — hit for real while building this — and a daily
# job that notifies on every one of those is the ₩20 budget again: an alert that is
# usually wrong, so eventually nobody reads it. Retry once, quietly, and speak only
# if it is still failing. The interactive `make spend-watch` does NOT do this: there
# a human is waiting and should hear the truth immediately.
if [ "$code" -eq 2 ]; then
  echo "=== $(stamp)  exit=2 (1차) — ${RETRY_SLEEP}초 후 재시도" >> "$LOG"
  sleep "$RETRY_SLEEP"
  output="$(look)"
  code=$?
fi

{
  echo "=== $(stamp)  exit=$code"
  echo "$output"
} >> "$LOG"

# A watcher that fills a disk is a bug.
if [ "$(wc -l < "$LOG" 2>/dev/null || echo 0)" -gt 2000 ]; then
  tail -n 1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

if [ "$code" -eq 1 ]; then
  notify "새로 과금되기 시작한 것이 있다 — make spend-watch"
elif [ "$code" -eq 2 ]; then
  # "Could not look" must not be silent either — that is the whole doctrine here.
  notify "비용을 측정하지 못했다 (이것은 0이 아니다)"
fi

exit "$code"
