#!/usr/bin/env bash
# SessionStart hook: advisory hook with two responsibilities:
# (a) Surface pending proposed-skill-patches found under <brain_dir>/skills/.
# (b) Clean up stale per-target lockfiles (older than 1 hour) left by pm-meta.pm-evolve.

set -euo pipefail
# Advisory hook — never deny. On any internal error, exit 0 silently.
trap 'exit 0' ERR

config_file="$HOME/.pm-second-brain/config.yaml"

# --- Read config; exit silently if unavailable ---
vault_root=$(yq -r '.vault.root' "$config_file" 2>/dev/null || true)
brain_folder=$(yq -r '.folders.brain // "_brain"' "$config_file" 2>/dev/null || true)

if [[ -z "$vault_root" || "$vault_root" == "null" ]]; then
  exit 0
fi

# Normalise: strip trailing slash
vault_root="${vault_root%/}"
brain_dir="${vault_root}/${brain_folder:-_brain}"

# --- (b) Cleanup stale lockfiles (>60 min old) ---
find "$brain_dir/locks" -name '*.lock' -mmin +60 -delete 2>/dev/null || true

# --- (a) Count pending proposed-skill-patches ---
pending=$(find "$brain_dir/skills" -name 'proposed-patch-*.md' 2>/dev/null | wc -l | tr -d ' ')

if [[ "$pending" -gt 0 ]]; then
  jq -nc --arg n "$pending" '{"message": ("\($n) pending skill patches. Run /pm-list-patches to review.")}'
fi

exit 0
