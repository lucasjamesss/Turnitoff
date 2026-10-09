"""The writing rule text. One source of truth: the markdown files in data/."""
from pathlib import Path

_DATA = Path(__file__).with_name("data")


def short_rule():
    """The paste-anywhere version (fits ChatGPT custom instructions)."""
    return (_DATA / "PASTE.md").read_text(encoding="utf-8").strip()


def full_rule():
    """The full rule for Claude Code (~/.claude/rules/)."""
    return (_DATA / "RULES.md").read_text(encoding="utf-8")
