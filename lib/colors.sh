#!/usr/bin/env bash
# shellcheck shell=bash
# Colored output helpers for the interactive installer.
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

say()  { printf "%s\n" "$*"; }
ok()   { printf "${GREEN}✓ %s${NC}\n" "$*"; }
warn() { printf "${YELLOW}! %s${NC}\n" "$*"; }
fail() { printf "${RED}✗ %s${NC}\n" "$*" >&2; }
info() { printf "${BLUE}→ %s${NC}\n" "$*"; }
