#!/usr/bin/env bash
# PM Second Brain — one-line bootstrap installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/zenin7305/pm-second-brain/main/install.sh | bash
#
# What it does:
#   1. Verifies macOS + detects Apple Silicon vs Intel
#   2. Installs Homebrew if missing
#   3. Installs git, uv, sqlite, python@3.12 via brew (skips if present)
#   4. Clones github.com/zenin7305/pm-second-brain into ~/PM-SecondBrain
#      (asks before overwriting an existing dir)
#   5. Hands off to the existing interactive setup-pm-second-brain.sh
#
# Logs are duplicated to /tmp/pm-secondbrain-install-<timestamp>.log

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_OWNER="${PM_SB_REPO_OWNER:-zenin7305}"
REPO_NAME="${PM_SB_REPO_NAME:-pm-second-brain}"
REPO_URL="${PM_SB_REPO_URL:-https://github.com/${REPO_OWNER}/${REPO_NAME}.git}"
REPO_BRANCH="${PM_SB_REPO_BRANCH:-main}"
TARGET_DIR="${PM_SB_TARGET_DIR:-$HOME/PM-SecondBrain}"

TS="$(date +%Y%m%dT%H%M%S)"
LOG_FILE="/tmp/pm-secondbrain-install-${TS}.log"

# Duplicate all output (stdout + stderr) to log file.
exec > >(tee -a "$LOG_FILE") 2>&1

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log()    { printf '[install] %s\n' "$*"; }
warn()   { printf '[install] WARN: %s\n' "$*" >&2; }
fail()   {
  printf '[install] ERROR: %s\n' "$*" >&2
  printf '[install] Full log: %s\n' "$LOG_FILE" >&2
  exit 1
}

trap 'fail "installer aborted on line $LINENO"' ERR

# ---------------------------------------------------------------------------
# 1. Pre-flight
# ---------------------------------------------------------------------------
log "PM Second Brain installer"
log "Log file: $LOG_FILE"

if [[ "$(uname -s)" != "Darwin" ]]; then
  fail "this installer supports macOS only (detected: $(uname -s))"
fi

ARCH="$(uname -m)"
case "$ARCH" in
  arm64)  BREW_PREFIX="/opt/homebrew" ;;
  x86_64) BREW_PREFIX="/usr/local"    ;;
  *)      fail "unsupported architecture: $ARCH" ;;
esac
log "macOS detected (arch=$ARCH, expected brew prefix=$BREW_PREFIX)"

# ---------------------------------------------------------------------------
# 2. Homebrew
# ---------------------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
  log "Homebrew not found — installing (you may be prompted for sudo password)"
  /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  log "Homebrew already installed: $(command -v brew)"
fi

# Make brew available in this shell session even if just installed.
if [[ -x "$BREW_PREFIX/bin/brew" ]]; then
  eval "$("$BREW_PREFIX/bin/brew" shellenv)"
fi

command -v brew >/dev/null 2>&1 || fail "brew still not on PATH after install"

# ---------------------------------------------------------------------------
# 3. Dependencies
# ---------------------------------------------------------------------------
install_if_missing() {
  local cmd="$1" formula="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    log "  $cmd present — skipping"
  else
    log "  installing $formula"
    brew install "$formula"
  fi
}

log "Checking dependencies"
install_if_missing git    git
install_if_missing uv     uv
install_if_missing sqlite3 sqlite
install_if_missing python3 python@3.12

# ---------------------------------------------------------------------------
# 4. Clone / update repo
# ---------------------------------------------------------------------------
choose_existing_dir_action() {
  # Print one of: update | reinstall | cancel
  local choice
  printf '\n' >&2
  printf '[install] Directory %s already exists.\n' "$TARGET_DIR" >&2
  printf '[install]   [u] update (git pull)\n' >&2
  printf '[install]   [r] reinstall (backup current, clone fresh)\n' >&2
  printf '[install]   [c] cancel\n' >&2
  # Read from /dev/tty so this works inside `curl … | bash`.
  if [[ -t 0 ]]; then
    read -r -p "[install] choose [u/r/c]: " choice
  else
    read -r -p "[install] choose [u/r/c]: " choice < /dev/tty
  fi
  case "${choice:-c}" in
    u|U) echo update ;;
    r|R) echo reinstall ;;
    *)   echo cancel ;;
  esac
}

if [[ -d "$TARGET_DIR" ]]; then
  ACTION="$(choose_existing_dir_action)"
  case "$ACTION" in
    update)
      log "Updating existing checkout at $TARGET_DIR"
      if [[ -d "$TARGET_DIR/.git" ]]; then
        git -C "$TARGET_DIR" fetch --quiet origin "$REPO_BRANCH"
        git -C "$TARGET_DIR" checkout --quiet "$REPO_BRANCH"
        git -C "$TARGET_DIR" pull --ff-only --quiet origin "$REPO_BRANCH"
      else
        fail "$TARGET_DIR exists but is not a git checkout — choose reinstall instead"
      fi
      ;;
    reinstall)
      BACKUP="${TARGET_DIR}.backup-${TS}"
      log "Backing up existing dir to $BACKUP"
      mv "$TARGET_DIR" "$BACKUP"
      log "Cloning $REPO_URL (branch=$REPO_BRANCH)"
      git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$TARGET_DIR"
      ;;
    cancel|*)
      log "Cancelled by user. Existing dir kept untouched."
      exit 0
      ;;
  esac
else
  log "Cloning $REPO_URL (branch=$REPO_BRANCH) into $TARGET_DIR"
  git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$TARGET_DIR"
fi

# ---------------------------------------------------------------------------
# 5. Hand off to interactive setup
# ---------------------------------------------------------------------------
SETUP_SCRIPT="$TARGET_DIR/setup-pm-second-brain.sh"
[[ -x "$SETUP_SCRIPT" ]] || chmod +x "$SETUP_SCRIPT" 2>/dev/null || true
[[ -f "$SETUP_SCRIPT" ]] || fail "expected $SETUP_SCRIPT, not found in clone"

log "Bootstrap done. Handing off to interactive setup."
log ""

# Disable ERR trap during interactive setup — its exit code is propagated explicitly.
trap - ERR
set +e
bash "$SETUP_SCRIPT"
SETUP_RC=$?
set -e

if (( SETUP_RC != 0 )); then
  fail "setup-pm-second-brain.sh exited with code $SETUP_RC (see $LOG_FILE)"
fi

log ""
log "All done."
log "  Repo:  $TARGET_DIR"
log "  Log:   $LOG_FILE"
log ""
log "Next: open the vault in Obsidian and try running a skill (see USAGE.md)."
