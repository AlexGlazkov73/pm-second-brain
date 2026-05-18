#!/usr/bin/env bash
# UserPromptSubmit hook: denies prompts containing secret-shaped strings (API keys, tokens)

set -euo pipefail
trap 'echo "{\"action\":\"deny\",\"reason\":\"hook internal error\"}"; exit 2' ERR

payload=$(cat)

prompt=$(echo "$payload" | jq -r '.prompt // ""')

if echo "$prompt" | grep -qE '(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})'; then
  echo '{"action":"deny","reason":"secret-shaped string detected in prompt; refusing to send"}'
  exit 2
fi

exit 0
