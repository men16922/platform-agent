#!/usr/bin/env bash
# PostToolUse hook — typecheck the dashboard the moment a TS file changes.
#
# Reads the edited path from the hook's stdin JSON and exits immediately for
# anything outside dashboard/, so Python edits pay nothing.
#
# Worth being clear about what this does NOT catch: today a page crashed on
# `posture.namespaces.length` and `tsc` was green the whole time, because the
# value came from a network payload written by an older agent. A type checker
# validates the claim, not the data. This catches the cheap half early; the
# expensive half still needs the thing actually running.
set -uo pipefail

f=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)
case "$f" in
  */dashboard/*.ts | */dashboard/*.tsx) ;;
  *) exit 0 ;;
esac

cd /Users/men1692/Desktop/AWS/platform-agent/dashboard || exit 0

if out=$(npx tsc --noEmit 2>&1); then
  exit 0
fi

echo "tsc FAILED after editing ${f#*/dashboard/}:"
echo "$out" | head -20
exit 2
