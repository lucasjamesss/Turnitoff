#!/usr/bin/env python3
"""Build dist/turnitoff-skill.zip for claude.ai (Customize > Skills). Standard library only.

Everything is generated from turnitoff/data/ and turnitoff/scanner.py, so rerun this
after editing either. The zip has the skill folder as its top level, as Anthropic's
docs require: turnitoff/SKILL.md, turnitoff/references/, turnitoff/scripts/.
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "turnitoff"
DESCRIPTION = ("Use when writing prose the user will send or submit as themselves (emails, essays, reports, "
               "posts) so it reads like one person, not a template. Not for code or short chat replies.")
assert len(DESCRIPTION) <= 200, len(DESCRIPTION)

SCAN_PY = '''"""Scan a draft for AI-writing tells.

Usage: python3 scan.py FILE [--formal]     (use - for stdin)
Exit 0 if the draft is fine, 1 if it reads as AI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scanner import analyze, report  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "-":
        text = sys.stdin.read()
    else:
        with open(args[0], encoding="utf-8") as f:
            text = f.read()
    score, findings, words = analyze(text, "--formal" in sys.argv)
    print(report(score, findings, words))
    if words < 80:
        print("  (under 80 words: stats unreliable)")
    return 0 if score < 6 else 1


sys.exit(main())
'''

BODY = """# Turnitoff

Apply this to prose the user will send or submit as themselves: emails, essays, reports, posts. Skip it for code and for short chat replies.

{rule}

## Check the draft

If you can run code, save the draft to a file and scan it before you send it. Run this from the skill folder:

    python3 scripts/scan.py draft.txt

- `clean`: send it.
- `minor-tells`: fix what is cheap to fix.
- `reads-AI`: rewrite the flagged sentences from the underlying facts, then scan again. After three passes, send it and tell the user it still flags.

If you can't run code, apply the rule by hand. The full version is in `references/RULES.md`.

Don't mention the scan to the user unless they ask.

## Limits

No tool guarantees a pass in any detector. Formal prose and non-native English get flagged even when a human wrote every word. The user should follow their school or workplace rules on AI use.
"""


def rules_reference():
    text = (ROOT / "turnitoff" / "data" / "RULES.md").read_text(encoding="utf-8")
    # The Tools section describes the MCP server, which a skill does not have.
    return re.sub(r"\n## Tools.*?(?=\n## )", "", text, flags=re.S)


def files():
    """Map of path inside the zip -> bytes."""
    rule = (ROOT / "turnitoff" / "data" / "PASTE.md").read_text(encoding="utf-8").strip()
    skill_md = "---\nname: %s\ndescription: %s\n---\n\n%s" % (NAME, DESCRIPTION, BODY.format(rule=rule))
    return {
        "%s/SKILL.md" % NAME: skill_md.encode("utf-8"),
        "%s/references/RULES.md" % NAME: rules_reference().encode("utf-8"),
        "%s/scripts/scan.py" % NAME: SCAN_PY.encode("utf-8"),
        "%s/scripts/scanner.py" % NAME: (ROOT / "turnitoff" / "scanner.py").read_bytes(),
    }


def build(out=None):
    out = Path(out) if out else ROOT / "dist" / ("%s-skill.zip" % NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files().items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return out


if __name__ == "__main__":
    print("built", build())
    sys.exit(0)
