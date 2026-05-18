#!/usr/bin/env bash
# PostToolUse hook: warns or denies when context window usage exceeds thresholds

set -euo pipefail
trap 'echo "{\"action\":\"deny\",\"reason\":\"hook internal error\"}"; exit 2' ERR

payload=$(cat)

ctx_used_pct=$(jq -r '(.context.usage_pct // 0) | tonumber? // 0' <<<"$payload")

if (( $(echo "$ctx_used_pct > 75" | bc -l) )); then
  echo '{"action":"deny","reason":"context >75% — wrap up this task or split into subagent"}'
  exit 2
elif (( $(echo "$ctx_used_pct > 65" | bc -l) )); then
  echo '{"action":"warn","reason":"context >65% — consider dispatching a subagent for the next step"}'
  exit 0
fi

exit 0
