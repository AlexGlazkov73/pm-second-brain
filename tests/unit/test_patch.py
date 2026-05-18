"""Decision 4 / Task 27 retrofit: proposed-patch lifecycle with auto_apply flag."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from pm_second_brain.patch import (
    PatchDecision,
    PatchError,
    apply,
    decide,
    load_patch,
)


def _write(p: Path, body: str) -> Path:
    p.write_text(dedent(body).lstrip(), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Test 1: trivial body-only patch → AUTO_APPLY
# ---------------------------------------------------------------------------

def test_trivial_body_only_patch_auto_applies(tmp_path: Path) -> None:
    patch_file = _write(
        tmp_path / "proposed-patch-1.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: trivial
        reason: add quick reference entry
        ---

        ```diff
        ## Quick Reference
        - old entry
        + new entry
        ```
        """,
    )
    patch = load_patch(patch_file)
    decision = decide(patch, target_root=tmp_path)
    assert decision is PatchDecision.AUTO_APPLY


# ---------------------------------------------------------------------------
# Test 2: diff adds a frontmatter key → ESCALATE
# ---------------------------------------------------------------------------

def test_frontmatter_change_escalates(tmp_path: Path) -> None:
    patch_file = _write(
        tmp_path / "proposed-patch-2.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: trivial
        reason: bump version
        ---

        ```diff
        ---
        + version: 0.2.0
        ---
        ```
        """,
    )
    patch = load_patch(patch_file)
    decision = decide(patch, target_root=tmp_path)
    assert decision is PatchDecision.ESCALATE


# ---------------------------------------------------------------------------
# Test 3: diff modifies ## Procedure heading → ESCALATE
# ---------------------------------------------------------------------------

def test_procedure_section_change_escalates(tmp_path: Path) -> None:
    patch_file = _write(
        tmp_path / "proposed-patch-3.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: trivial
        reason: update procedure
        ---

        ```diff
        -## Procedure
        +## Procedure (updated)
        ```
        """,
    )
    patch = load_patch(patch_file)
    decision = decide(patch, target_root=tmp_path)
    assert decision is PatchDecision.ESCALATE


# ---------------------------------------------------------------------------
# Test 4: diff modifies ## Verification heading → ESCALATE
# ---------------------------------------------------------------------------

def test_verification_section_change_escalates(tmp_path: Path) -> None:
    patch_file = _write(
        tmp_path / "proposed-patch-4.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: trivial
        reason: update verification
        ---

        ```diff
        -## Verification
        +## Verification (updated)
        ```
        """,
    )
    patch = load_patch(patch_file)
    decision = decide(patch, target_root=tmp_path)
    assert decision is PatchDecision.ESCALATE


# ---------------------------------------------------------------------------
# Test 5: diff has 150 added lines → ESCALATE
# ---------------------------------------------------------------------------

def test_large_diff_escalates(tmp_path: Path) -> None:
    added_lines = "\n".join(f"+ line {i}" for i in range(150))
    body = f"""\
---
target: SKILL.md
action: patch
auto_apply: trivial
reason: large change
---

```diff
{added_lines}
```
"""
    patch_file = tmp_path / "proposed-patch-5.md"
    patch_file.write_text(body, encoding="utf-8")
    patch = load_patch(patch_file)
    decision = decide(patch, target_root=tmp_path)
    assert decision is PatchDecision.ESCALATE


# ---------------------------------------------------------------------------
# Test 6: no auto_apply field → ESCALATE
# ---------------------------------------------------------------------------

def test_missing_auto_apply_defaults_to_escalate(tmp_path: Path) -> None:
    patch_file = _write(
        tmp_path / "proposed-patch-6.md",
        """
        ---
        target: SKILL.md
        action: patch
        reason: no auto_apply field
        ---

        ```diff
        - old line
        + new line
        ```
        """,
    )
    patch = load_patch(patch_file)
    decision = decide(patch, target_root=tmp_path)
    assert decision is PatchDecision.ESCALATE


# ---------------------------------------------------------------------------
# Test 7: auto_apply: requires_approval → ESCALATE
# ---------------------------------------------------------------------------

def test_requires_approval_explicit_escalates(tmp_path: Path) -> None:
    patch_file = _write(
        tmp_path / "proposed-patch-7.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: requires_approval
        reason: needs review
        ---

        ```diff
        - old line
        + new line
        ```
        """,
    )
    patch = load_patch(patch_file)
    decision = decide(patch, target_root=tmp_path)
    assert decision is PatchDecision.ESCALATE


# ---------------------------------------------------------------------------
# Test 8: no action field → load_patch raises PatchError
# ---------------------------------------------------------------------------

def test_missing_action_field_raises(tmp_path: Path) -> None:
    patch_file = _write(
        tmp_path / "proposed-patch-8.md",
        """
        ---
        target: SKILL.md
        auto_apply: trivial
        reason: missing action
        ---

        ```diff
        - old line
        + new line
        ```
        """,
    )
    with pytest.raises(PatchError):
        load_patch(patch_file)


# ---------------------------------------------------------------------------
# Test 9: apply() emits audit event
# ---------------------------------------------------------------------------

def test_apply_emits_audit_event(tmp_path: Path) -> None:
    """apply() must call audit.audit_append() exactly once with a patch-* event."""
    brain_dir = tmp_path / "_brain"
    brain_dir.mkdir()
    patch_file = _write(
        tmp_path / "proposed-patch-9.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: trivial
        reason: typo
        ---

        ```diff
        - old typo
        + fixed typo
        ```
        """,
    )
    patch = load_patch(patch_file)
    decision = apply(patch, target_root=tmp_path, brain_dir=brain_dir)
    assert decision is PatchDecision.AUTO_APPLY

    # audit log should have exactly one line with event=patch-trivial-applied
    audit_files = list((brain_dir / "audit").glob("*.jsonl"))
    assert len(audit_files) == 1
    lines = audit_files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "patch-trivial-applied"
    assert event["target"] == "SKILL.md"
    assert event["reason"] == "typo"
    assert event["auto_apply_flag"] == "trivial"
    assert isinstance(event["diff_lines"], int)
    assert event["diff_lines"] >= 2


# ---------------------------------------------------------------------------
# Test 10: body-only diff with a markdown horizontal rule does NOT escalate
# ---------------------------------------------------------------------------

def test_body_only_diff_with_markdown_hrule_does_not_escalate(tmp_path: Path) -> None:
    """A ``---`` markdown horizontal rule in body context must not be confused with frontmatter."""
    patch_file = _write(
        tmp_path / "proposed-patch-10.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: trivial
        reason: clarify section
        ---

        ```diff
         ## Quick Reference
        - call A then call B
        + call A, then call B

         ---

         ## Procedure body continues
        ```
        """,
    )
    assert decide(load_patch(patch_file), target_root=tmp_path) is PatchDecision.AUTO_APPLY


# ---------------------------------------------------------------------------
# Test 11: frontmatter keys changed without delimiter still escalates
# ---------------------------------------------------------------------------

def test_frontmatter_keys_changed_without_delimiter_still_escalates(tmp_path: Path) -> None:
    """If a diff modifies frontmatter keys without including the ``---`` delimiter, key-line arm catches it."""
    patch_file = _write(
        tmp_path / "proposed-patch-11.md",
        """
        ---
        target: SKILL.md
        action: patch
        auto_apply: trivial
        reason: rename key
        ---

        ```diff
        - old_key: x
        + new_key: y
        ```
        """,
    )
    assert decide(load_patch(patch_file), target_root=tmp_path) is PatchDecision.ESCALATE
