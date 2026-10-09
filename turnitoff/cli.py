"""Command line and Claude Code hook entry point."""
import argparse
import hashlib
import json
import os
import sys
import tempfile

from .rules import full_rule, short_rule
from .scanner import analyze, report, verdict

EXTS = {".md", ".txt", ".tex"}
SKIP_NAMES = {"CLAUDE.md", "SKILL.md", "RULES.md", "PASTE.md", "AGENTS.md", "INSTALL.md"}


def _state(key):
    return os.path.join(tempfile.gettempdir(), "turnitoff-" + hashlib.md5(key.encode()).hexdigest())


def _tries(path):
    try:
        with open(path) as f:
            return int(f.read() or 0)
    except (OSError, ValueError):
        return 0


def _drop(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _limit():
    try:
        return float(os.environ.get("TURNITOFF_BLOCK_AT", "6"))
    except ValueError:
        return 6.0


def _gate(key, text, what, is_stop):
    """Exit 2 sends the findings to Claude. Stop it from looping forever."""
    score, findings, nw = analyze(text)
    if nw < 80:
        return 0
    state = _state(key)
    if score < _limit():
        _drop(state)
        return 0
    tries = _tries(state)
    msg = report(score, findings, nw)
    if tries >= 2:
        _drop(state)
        if is_stop:
            return 0
        sys.stderr.write(msg + "\nStill flagged after 2 rewrites. Send it anyway and tell the user it still reads AI.\n")
        return 2
    try:
        with open(state, "w") as f:
            f.write(str(tries + 1))
    except OSError:
        pass
    sys.stderr.write(msg + "\nRewrite %s from the underlying facts. Do not swap synonyms. Then scan again.\n" % what)
    return 2


def hook():
    if os.environ.get("TURNITOFF", "").lower() == "off":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    if data.get("hook_event_name") == "Stop":
        text = data.get("last_assistant_message") or ""
        if not isinstance(text, str):
            return 0
        return _gate("stop:" + str(data.get("session_id", "")), text, "your last reply", True)
    path = (data.get("tool_input") or {}).get("file_path", "")
    if not isinstance(path, str) or not path:
        return 0
    norm = path.replace("\\", "/")
    if os.path.splitext(path)[1].lower() not in EXTS:
        return 0
    if "/.claude/" in norm or os.path.basename(norm) in SKIP_NAMES:
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        return 0
    return _gate("file:" + path, text, "the flagged sentences", False)


def main(argv=None):
    p = argparse.ArgumentParser(prog="turnitoff", description="Scan prose for AI-writing tells.")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("scan", help="scan a file, or - for stdin")
    s.add_argument("file")
    s.add_argument("--formal", action="store_true", help="zero tolerance for em dashes")
    s.add_argument("--json", action="store_true")
    sub.add_parser("hook", help="Claude Code hook (JSON on stdin)")
    r = sub.add_parser("rules", help="print the writing rule")
    r.add_argument("--full", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "hook":
        sys.exit(hook())
    if a.cmd == "rules":
        sys.stdout.write(full_rule() if a.full else short_rule() + "\n")
        return
    if a.cmd == "scan":
        text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
        score, findings, nw = analyze(text, a.formal)
        if a.json:
            print(json.dumps({"verdict": verdict(score), "score": score, "words": nw, "findings": findings}))
        else:
            print(report(score, findings, nw))
            if nw < 80:
                print("  (under 80 words: stats unreliable)")
        sys.exit(0 if score < 6 else 1)
    p.print_help()
