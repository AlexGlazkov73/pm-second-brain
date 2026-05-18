#!/usr/bin/env bash
# shellcheck shell=bash
# Interactive prompt helpers.

# ask "label" "default"
# The -e flag enables readline editing so arrow keys, backspace, Home/End
# work. Without -e, arrow keys insert escape sequences like ^[[D.
# Bash 4+ would let us pre-fill with `-i $default`, but macOS ships Bash 3.2,
# so the default is shown in [brackets] and applied if the user just hits Enter.
ask() {
  local label="$1" default="${2:-}"
  local hint=""
  [[ -n "$default" ]] && hint=" [$default]"
  local ans
  # Prompt to stderr explicitly + plain `read` (no -e): macOS bash 3.2 readline
  # misbehaves when stdin is /dev/tty reattached from a pipe (curl|bash mode).
  printf '%s%s: ' "$label" "$hint" >&2
  read -r ans
  echo "${ans:-$default}"
}

# ask_yn "label" "y|n"  (returns 0 on yes, 1 on no)
ask_yn() {
  local label="$1" default="${2:-n}"
  local hint="[y/N]"
  [[ "$default" == "y" ]] && hint="[Y/n]"
  local ans
  printf '%s %s: ' "$label" "$hint" >&2
  read -r ans
  ans="${ans:-$default}"
  [[ "$ans" =~ ^[Yy]([Ee][Ss])?$ ]]
}
