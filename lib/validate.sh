#!/usr/bin/env bash
# shellcheck shell=bash
# Prerequisite validation helpers.

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "missing required command: $1"
    return 1
  fi
}

# require_version <cmd> <min_version>  (returns 0 if cur >= min)
require_version() {
  local cmd="$1" min="$2"
  local cur
  cur=$("$cmd" --version 2>/dev/null | head -1 | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)
  if [[ -z "$cur" ]]; then
    fail "cannot read version from $cmd"
    return 1
  fi
  if ! printf '%s\n%s\n' "$min" "$cur" | sort -V -C; then
    fail "$cmd version $cur is older than required $min"
    return 1
  fi
}

# is_absolute_path <path>  (rejects relative paths and ~ unexpanded)
is_absolute_path() {
  [[ "$1" == /* ]]
}
