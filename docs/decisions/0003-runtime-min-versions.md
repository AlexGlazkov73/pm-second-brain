# ADR 0003 — Runtime minimum versions

**Status:** Provisional — pin to verified versions during Phase 5
**Spike task:** Task 4 (Phase 0)

## Decision

Minimums for v0:

| Component   | Min version | Reason                                                          |
|-------------|-------------|-----------------------------------------------------------------|
| `opencode`  | **TBD**     | Set during installer test on macOS; record actual version here. |
| `claude`    | **TBD**     | Set during installer test on macOS; record actual version here. |
| `python`    | **3.11**    | `mcp` SDK requires 3.10+; we pick 3.11 for `dataclass` `slots`. |
| `sqlite`    | **3.9**     | FTS5 first stable. macOS 13+ ships ≥ 3.39; Ubuntu 22+ ≥ 3.37.   |
| `bash`      | **5**       | Associative arrays + `${var,,}` lowercase needed in installer.  |
| `uv`        | **0.4**     | `uv python pin`, `uv run --directory` flags required.           |

## Enforcement

`setup-pm-second-brain.sh` runs a `lib/validate.sh::check_versions` function
during the **prerequisites** phase and aborts with a colored error if any
component is missing or below the minimum. The script offers a `--skip-version-check`
escape hatch for power users.

## Verification status

- [x] Python 3.11.13 verified (uv-managed)
- [x] uv 0.8.0 verified
- [ ] **TODO:** Replace `TBD` for `opencode` / `claude` once Phase 5 installer
      runs on a macOS host and prints `--version`.
