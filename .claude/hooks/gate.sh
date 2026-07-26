#!/usr/bin/env bash
# Stop hook — the repo's gate, enforced instead of remembered.
#
# The rule "run `make check` after multi-file changes" lived only in NEXT_PLAN,
# which means it held exactly as often as it was remembered. This runs it.
#
# Two properties make it tolerable rather than infuriating:
#   * It SKIPS when no source changed. Docs-only turns pay nothing.
#   * It is wired async in settings.json, so a passing gate never blocks; only a
#     FAILING one (exit 2) interrupts. The common case is silent.
set -uo pipefail

REPO="/Users/men1692/Desktop/AWS/platform-agent"
cd "$REPO" || exit 0

# Uncommitted source only. A clean tree means the last commit already passed —
# re-running four minutes of tests to learn that again is pure waste.
changed=$(git status --porcelain -- src tests scripts harness platform 2>/dev/null \
  | grep -E '\.(py|ya?ml)$')
if [ -z "$changed" ]; then
  exit 0
fi

if out=$(make check 2>&1); then
  echo "$out" | tail -1
  exit 0
fi

# Exit 2 = blocking error: the model is woken with this text.
echo "GATE FAILED — uncommitted source changes do not pass 'make check'."
echo "Changed:"
echo "$changed" | head -10
echo
# Targeted, not `tail`: pytest ends with a wall of DeprecationWarnings, so the
# last 25 lines are almost never the failure. Pull the summary lines instead.
echo "$out" | grep -E '^(FAILED|ERROR) ' | head -15
echo "$out" | grep -E '^=+ .*(failed|passed|error).* =+$' | tail -1
exit 2
