"""Decision 4 / Task 27 retrofit: proposed-patch lifecycle with auto_apply flag.

A *proposed patch* is a Markdown file with YAML frontmatter followed by a
fenced ``diff`` block.  :func:`load_patch` parses it into a :class:`ProposedPatch`;
:func:`decide` classifies it as :attr:`PatchDecision.AUTO_APPLY` or
:attr:`PatchDecision.ESCALATE`; :func:`apply` runs the decision and writes an
audit event via :func:`~pm_second_brain.audit.audit_append`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import yaml

from pm_second_brain.audit import audit_append
from pm_second_brain.history import revert_latest, snapshot

# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class PatchError(Exception):
    """Raised when a proposed-patch file is malformed or missing required fields."""


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PatchDecision(str, Enum):
    """Outcome of :func:`decide`."""

    AUTO_APPLY = "auto_apply"
    ESCALATE = "escalate"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedPatch:
    """Parsed content of a proposed-patch Markdown file."""

    target: str
    action: str
    auto_apply: Optional[str]
    reason: str
    diff: str


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_MAX_DIFF_LINES = 100

# Matches a +/- line that looks like a YAML frontmatter key (arm b of the
# two-arm frontmatter detection).
_FRONTMATTER_KEY_LINE_RE = re.compile(r"^[+-]\s*[a-zA-Z_][\w\-]*\s*:")

# Matches changes to protected section headings (## Procedure, ## Verification)
_RE_PROTECTED_SECTION = re.compile(
    r"^[+-]\s*##\s*(Procedure|Verification)\b", re.MULTILINE
)

# Matches a fenced diff block: ```diff … ```
_RE_DIFF_BLOCK = re.compile(r"```diff\s*\n(.*?)```", re.DOTALL)

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def load_patch(path: Path) -> ProposedPatch:
    """Parse a proposed-patch Markdown file into a :class:`ProposedPatch`.

    Args:
        path: Path to the ``.md`` file.

    Returns:
        A :class:`ProposedPatch` instance.

    Raises:
        PatchError: When the file is missing frontmatter, required fields, or
            a ``diff`` code block.
    """
    text = path.read_text(encoding="utf-8")

    # Split frontmatter (must start with ``---``)
    if not text.startswith("---"):
        raise PatchError(f"Missing YAML frontmatter in {path}")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise PatchError(f"Malformed frontmatter in {path}")

    raw_fm = parts[1]
    body = parts[2]

    try:
        fm = yaml.safe_load(raw_fm) or {}
    except yaml.YAMLError as exc:
        raise PatchError(f"Invalid YAML frontmatter in {path}: {exc}") from exc

    if not isinstance(fm, dict):
        raise PatchError(f"Frontmatter must be a YAML mapping in {path}")

    target = fm.get("target")
    if not target:
        raise PatchError(f"Missing required frontmatter field 'target' in {path}")

    action = fm.get("action")
    if not action:
        raise PatchError(f"Missing required frontmatter field 'action' in {path}")

    reason = fm.get("reason", "")
    auto_apply = fm.get("auto_apply")
    if auto_apply is not None:
        auto_apply = str(auto_apply)

    # Extract diff block
    match = _RE_DIFF_BLOCK.search(body)
    if not match:
        raise PatchError(f"No ```diff … ``` block found in {path}")

    diff = match.group(1)

    return ProposedPatch(
        target=str(target),
        action=str(action),
        auto_apply=auto_apply,
        reason=str(reason),
        diff=diff,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _diff_touches_frontmatter(diff: str) -> bool:
    """Return True if the diff modifies YAML frontmatter content.

    Uses a two-arm approach:
    - Arm (a): tracks inside-frontmatter state by toggling on lines that strip
      to literal ``---``; if inside and the line has +/- with content, returns True.
    - Arm (b): any +/- line matching the frontmatter-key-line pattern returns True,
      catching mutations that don't include the delimiter as context.
    """
    in_fm = False
    for line in diff.splitlines():
        stripped = line.lstrip("+-").lstrip()
        if stripped == "---":
            in_fm = not in_fm
            continue
        if in_fm and line.startswith(("+", "-")) and line[1:].strip():
            return True
        if line.startswith(("+", "-")) and _FRONTMATTER_KEY_LINE_RE.match(line):
            return True
    return False


def _diff_touches_protected_sections(diff: str) -> bool:
    """Return True if the diff modifies a ## Procedure or ## Verification heading."""
    return bool(_RE_PROTECTED_SECTION.search(diff))


def _diff_changed_line_count(diff: str) -> int:
    """Count lines that start with ``+`` or ``-`` (the actual change lines).

    Lines starting with ``---`` or ``+++`` (file headers) are excluded.
    """
    count = 0
    for line in diff.splitlines():
        if (line.startswith("+") or line.startswith("-")) and not line.startswith(
            ("+++", "---")
        ):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def decide(patch: ProposedPatch, target_root: Path) -> PatchDecision:  # noqa: ARG001
    """Classify a :class:`ProposedPatch` as AUTO_APPLY or ESCALATE.

    Rules (first match wins):
    1. ``auto_apply`` flag is not exactly ``"trivial"`` → ESCALATE.
    2. Diff touches YAML frontmatter markers → ESCALATE.
    3. Diff touches protected sections (Procedure, Verification) → ESCALATE.
    4. Changed-line count >= :data:`_MAX_DIFF_LINES` → ESCALATE.
    Otherwise → AUTO_APPLY.

    Args:
        patch: The parsed patch.
        target_root: Root directory where the target file lives (not used for
            the classification logic itself; reserved for future file reads).

    Returns:
        :attr:`PatchDecision.AUTO_APPLY` or :attr:`PatchDecision.ESCALATE`.
    """
    if patch.auto_apply != "trivial":
        return PatchDecision.ESCALATE

    if _diff_touches_frontmatter(patch.diff):
        return PatchDecision.ESCALATE

    if _diff_touches_protected_sections(patch.diff):
        return PatchDecision.ESCALATE

    if _diff_changed_line_count(patch.diff) >= _MAX_DIFF_LINES:
        return PatchDecision.ESCALATE

    return PatchDecision.AUTO_APPLY


# ---------------------------------------------------------------------------
# Apply (decision + audit)
# ---------------------------------------------------------------------------


def apply(patch: ProposedPatch, target_root: Path, brain_dir: Path) -> PatchDecision:
    """Run :func:`decide` and emit an audit event.

    Args:
        patch: The parsed patch to evaluate.
        target_root: Root directory for the target file.
        brain_dir: Brain directory where the audit log is written.

    Returns:
        The :class:`PatchDecision` result.
    """
    decision = decide(patch, target_root)
    audit_append(
        brain_dir,
        {
            "event": (
                "patch-trivial-applied"
                if decision is PatchDecision.AUTO_APPLY
                else "patch-escalated"
            ),
            "target": patch.target,
            "reason": patch.reason,
            "diff_lines": _diff_changed_line_count(patch.diff),
            "auto_apply_flag": patch.auto_apply,
        },
    )
    return decision


# ---------------------------------------------------------------------------
# Revert workflow helpers
# ---------------------------------------------------------------------------

_RE_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def apply_patch(target_file: Path, unified_diff: str, history_root: Path) -> None:
    """Apply a unified diff to ``target_file``, snapshotting it first.

    Minimal single-hunk applier using only stdlib. Diff lines that do not match
    a hunk header or a recognized hunk-body prefix are skipped silently.

    Args:
        target_file: Path to the file to modify.
        unified_diff: Unified-diff string.
        history_root: Directory root for history snapshots.
    """
    snapshot(target_file, history_root)

    old_lines = target_file.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines: list[str] = []
    old_pos = 0  # 0-indexed cursor into old_lines

    diff_lines = unified_diff.splitlines(keepends=True)
    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]
        # Skip file header lines
        if line.startswith("--- ") or line.startswith("+++ "):
            i += 1
            continue

        m = _RE_HUNK_HEADER.match(line)
        if m:
            hunk_old_start = int(m.group(1)) - 1  # convert to 0-indexed
            hunk_old_count = int(m.group(2)) if m.group(2) is not None else 1
            hunk_new_count = int(m.group(4)) if m.group(4) is not None else 1
            i += 1
            # Copy lines before this hunk unchanged
            new_lines.extend(old_lines[old_pos:hunk_old_start])
            old_pos = hunk_old_start
            old_consumed = 0
            new_emitted = 0
            # Process hunk body until expected counts are satisfied
            while i < len(diff_lines):
                hunk_line = diff_lines[i]
                # Stop at next hunk header
                if hunk_line.startswith("@@"):
                    break
                if hunk_line.startswith("-"):
                    # Remove: advance past this old line
                    old_pos += 1
                    old_consumed += 1
                elif hunk_line.startswith("+"):
                    # Add: emit stripped prefix to new
                    new_lines.append(hunk_line[1:])
                    new_emitted += 1
                else:
                    # Context: emit from old unchanged
                    new_lines.append(old_lines[old_pos])
                    old_pos += 1
                    old_consumed += 1
                    new_emitted += 1
                i += 1
                # Stop when both counts are satisfied
                if old_consumed >= hunk_old_count and new_emitted >= hunk_new_count:
                    break
            continue
        i += 1

    # Append any remaining lines after the last hunk
    new_lines.extend(old_lines[old_pos:])
    target_file.write_text("".join(new_lines), encoding="utf-8")


def apply_with_smoke_guard(
    target_file: Path,
    unified_diff: str,
    history_root: Path,
    smoke: Callable[[Path], bool],
) -> bool:
    """Apply a unified diff and revert if the smoke check fails.

    Args:
        target_file: Path to the file to modify.
        unified_diff: Unified-diff string.
        history_root: Directory root for history snapshots.
        smoke: Callable that receives the patched file path and returns True if
            the patch is acceptable.

    Returns:
        True when the smoke check passed; False when the patch was reverted.
    """
    apply_patch(target_file, unified_diff, history_root)
    if smoke(target_file):
        return True
    revert_latest(target_file, history_root)
    return False
