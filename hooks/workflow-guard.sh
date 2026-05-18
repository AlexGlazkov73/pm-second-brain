#!/usr/bin/env bash
# PreToolUse hook: denies Write operations targeting paths outside the configured vault root

set -euo pipefail
trap 'echo "{\"action\":\"deny\",\"reason\":\"hook internal error\"}"; exit 2' ERR

normalize_path() {
  python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$1" 2>/dev/null || echo "$1"
}

payload=$(cat)

tool_name=$(echo "$payload" | jq -r '.tool_name // ""')

if [[ "$tool_name" != "Write" ]]; then
  exit 0
fi

target_path=$(echo "$payload" | jq -r '.tool_input.file_path // .tool_input.path // ""')

config_file="$HOME/.pm-second-brain/config.yaml"

if [[ ! -f "$config_file" ]]; then
  echo '{"action":"deny","reason":"vault config missing at ~/.pm-second-brain/config.yaml — cannot verify write target"}'
  exit 2
fi

vault_root=$(yq -r '.vault.root' "$config_file")

if [[ -z "$vault_root" || "$vault_root" == "null" ]]; then
  echo '{"action":"deny","reason":"vault.root not set in ~/.pm-second-brain/config.yaml"}'
  exit 2
fi

# Resolve to absolute path for reliable prefix matching
resolved_target=$(normalize_path "$target_path")
resolved_vault=$(normalize_path "$vault_root")

# Allow writes to system temp directories (macOS /tmp is a symlink to /private/tmp)
if [[ "$resolved_target" == /tmp/* || "$resolved_target" == /private/tmp/* ]]; then
  exit 0
fi

# Prevent prefix bypass: /Users/u/Vault-evil must NOT match vault /Users/u/Vault
vault_prefix="${resolved_vault%/}/"
if [[ "$resolved_target" == "$vault_prefix"* || "$resolved_target" == "${resolved_vault%/}" ]]; then
  exit 0
fi

jq -nc --arg p "$target_path" '{"action":"deny","reason": ("write outside vault: " + $p)}'
exit 2
