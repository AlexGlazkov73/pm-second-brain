#!/usr/bin/env bash
# shellcheck shell=bash
# Symlink each skill namespace (pm-*) into a runtime's skills/ dir.

link_skills() {
  local src_root="$1" target_root="$2"
  mkdir -p "$target_root"
  local ns
  for ns in "$src_root"/skills/pm-*; do
    [[ -d "$ns" ]] || continue
    ln -sfn "$ns" "$target_root/$(basename "$ns")"
  done
}

unlink_skills() {
  local target_root="$1"
  local link
  for link in "$target_root"/pm-*; do
    [[ -L "$link" ]] && rm -f "$link"
  done
}
