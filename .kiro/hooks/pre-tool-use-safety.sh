#!/usr/bin/env bash
# .kiro/hooks/pre-tool-use-safety.sh
# preToolUse hook — blocks destructive commands before execution.
# Exit codes: 0 = allow, 2 = block (tool use denied)
set -euo pipefail

# Read the tool use JSON from stdin
INPUT=$(cat)

# Extract the command being executed
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
# Handle different possible JSON structures
if 'input' in data:
    inp = data['input']
    if isinstance(inp, dict):
        print(inp.get('command', inp.get('content', '')))
    else:
        print(inp)
elif 'command' in data:
    print(data['command'])
else:
    print('')
" 2>/dev/null || echo "")

# If we couldn't extract a command, allow (fail-open for non-shell tools)
if [ -z "$COMMAND" ]; then
  exit 0
fi

# --- Destructive patterns (case-insensitive check) ---
DESTRUCTIVE_PATTERNS=(
  "rm -rf /"
  "aws .* delete-"
  "aws .* terminate-"
  "aws .* drop-"
  "aws .* destroy"
  "kubectl delete namespace"
  "kubectl delete --all"
  "docker system prune -a"
  "git push.*--force"
  "git reset --hard"
  "git clean -fd"
  "DROP TABLE"
  "DROP DATABASE"
  "TRUNCATE"
)

COMMAND_LOWER=$(echo "$COMMAND" | tr '[:upper:]' '[:lower:]')

for pattern in "${DESTRUCTIVE_PATTERNS[@]}"; do
  pattern_lower=$(echo "$pattern" | tr '[:upper:]' '[:lower:]')
  if echo "$COMMAND_LOWER" | grep -qE "$pattern_lower"; then
    echo "BLOCKED by pre-tool-use-safety hook: destructive command detected" >&2
    echo "Pattern: $pattern" >&2
    echo "Command: $COMMAND" >&2
    exit 2
  fi
done

# Allow the command
exit 0
