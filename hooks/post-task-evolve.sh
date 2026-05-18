#!/usr/bin/env bash
# PostToolUse hook: counts tool calls per session; when the count crosses
# evolution.evolve_after_tool_calls, spawns a background subagent to run
# pm-meta.pm-evolve for the targeted skill.

set -euo pipefail
trap 'echo "{\"action\":\"deny\",\"reason\":\"hook internal error\"}"; exit 2' ERR

payload=$(cat)

session_id=$(echo "$payload" | jq -r '.session_id // ""' 2>/dev/null)
target_skill=$(echo "$payload" | jq -r '.tool_input.skill_name // ""' 2>/dev/null)

# Cannot count without a session ID
if [[ -z "$session_id" ]]; then
  exit 0
fi

# Nothing to evolve without a target skill
if [[ -z "$target_skill" ]]; then
  exit 0
fi

# --- Counter management ---
counter_dir="${TMPDIR:-/tmp}/pm-second-brain-counters"
mkdir -p "$counter_dir"
counter_file="$counter_dir/${session_id}.count"

prev_count=$(cat "$counter_file" 2>/dev/null || echo 0)
count=$(( prev_count + 1 ))
echo "$count" > "$counter_file"

# --- Threshold from config (fallback: 5) ---
config_file="$HOME/.pm-second-brain/config.yaml"
threshold=$(yq -r '.evolution.evolve_after_tool_calls // 5' "$config_file" 2>/dev/null || echo 5)

# Guard: ensure threshold is a positive integer
if ! [[ "$threshold" =~ ^[0-9]+$ ]] || [[ "$threshold" -lt 1 ]]; then
  threshold=5
fi

# Fire ONCE at the exact threshold boundary (not >=) to avoid repeat spawns
if [[ "$count" -eq "$threshold" ]]; then
  # Replace dots with slashes to build the SKILL.md path (e.g. pm-workflow.pm-decision → pm-workflow/pm-decision)
  skill_path="${target_skill//.//}"
  (
    opencode run --skill pm-meta.pm-evolve \
      --arg target="_brain/skills/${skill_path}/SKILL.md" \
      --arg trigger="POST-TASK" \
      --headless >/dev/null 2>&1 &
  )
fi

exit 0
