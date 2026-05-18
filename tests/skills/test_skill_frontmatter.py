"""Contract test: every SKILL.md listed in the agentskills.io v1 allow-list
obeys agentskills.io v1 frontmatter + project extensions.

Required frontmatter keys: name, description, version, author, license,
allowed_tools, model_preference. Required body sections in order:
When to Use, Quick Reference, Procedure, Pitfalls, Verification.

The allow-list is hard-coded to the 11 SKILL.md files in scope for the
2026-05-18 research-integration retrofit. Three Phase 3 placeholder skills
(pm-rebuild-moc, pm-self-review, pm-verify-output) are excluded.

See docs/decisions/0007-agentskills-io-format.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"

ALLOW_LIST = (
    "pm-workflow/SKILL.md",
    "pm-knowledge/SKILL.md",
    "pm-quality/SKILL.md",
    "pm-meta/SKILL.md",
    "pm-workflow/pm-daily-brief/SKILL.md",
    "pm-workflow/pm-decision/SKILL.md",
    "pm-workflow/pm-meeting-recap/SKILL.md",
    "pm-workflow/pm-research/SKILL.md",
    "pm-knowledge/pm-add-decision/SKILL.md",
    "pm-knowledge/pm-add-meeting/SKILL.md",
    "pm-knowledge/pm-link-notes/SKILL.md",
)

REQUIRED_FIELDS = (
    "name",
    "description",
    "version",
    "author",
    "license",
    "allowed_tools",
    "model_preference",
)

REQUIRED_SECTIONS = (
    "When to Use",
    "Quick Reference",
    "Procedure",
    "Pitfalls",
    "Verification",
)

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _allowed_skill_files() -> list[Path]:
    return [SKILLS_ROOT / rel for rel in ALLOW_LIST]


def _parse_frontmatter(text: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    assert match, "SKILL.md must start with a YAML frontmatter block delimited by ---"
    return yaml.safe_load(match.group(1)) or {}


def _section_order(text: str) -> list[str]:
    return [m.group(1).strip() for m in HEADING_RE.finditer(text)]


@pytest.mark.parametrize("path", _allowed_skill_files(), ids=lambda p: str(p.relative_to(SKILLS_ROOT)))
def test_required_frontmatter_fields(path: Path) -> None:
    fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
    missing = [f for f in REQUIRED_FIELDS if f not in fm]
    assert not missing, f"{path}: missing frontmatter fields {missing}"


@pytest.mark.parametrize("path", _allowed_skill_files(), ids=lambda p: str(p.relative_to(SKILLS_ROOT)))
def test_model_preference_is_primary_or_fallback(path: Path) -> None:
    fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm["model_preference"] in {"primary", "fallback"}, (
        f"{path}: model_preference must be 'primary' or 'fallback', "
        f"got {fm['model_preference']!r}"
    )


@pytest.mark.parametrize("path", _allowed_skill_files(), ids=lambda p: str(p.relative_to(SKILLS_ROOT)))
def test_body_sections_present_and_ordered(path: Path) -> None:
    sections = _section_order(path.read_text(encoding="utf-8"))
    filtered = [s for s in sections if s in REQUIRED_SECTIONS]
    assert filtered == list(REQUIRED_SECTIONS), (
        f"{path}: section order is {filtered}, expected {list(REQUIRED_SECTIONS)}"
    )


def test_allow_list_has_exactly_eleven_skill_files() -> None:
    found = _allowed_skill_files()
    assert len(found) == 11, f"expected exactly 11 SKILL.md files in allow-list, found {len(found)}"
    for path in found:
        assert path.is_file(), f"allow-list entry missing on disk: {path}"
