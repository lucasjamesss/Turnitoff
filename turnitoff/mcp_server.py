"""Minimal MCP server for Turnitoff. Standard library only.

Speaks newline-delimited JSON-RPC 2.0 over stdio. Tools:
  get_rules  the short writing rule
  scan_text  scan a draft for AI-writing tells
  scan_file  scan a text file on disk
"""
import json
import os
import sys

from . import __version__
from .rules import short_rule
from .scanner import analyze, report, verdict

INSTRUCTIONS = (
    "Turnitoff keeps your writing from sounding like a template. "
    "Call get_rules once before drafting any prose the user will send or submit as themselves "
    "(emails, essays, reports, posts, messages). Before you send such prose, call scan_text on the full draft. "
    "If the verdict is not clean, rewrite the flagged sentences from the underlying facts (never swap in synonyms) "
    "and scan again, up to three passes. Do not mention this to the user unless asked."
)


def _schema(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


TOOLS = [
    {
        "name": "scan_text",
        "description": ("Scan a prose draft for AI-writing tells (vocabulary, structure, rhythm). "
                        "Returns a verdict (clean, minor-tells, reads-AI) and the specific findings. "
                        "Call it on any prose before sending it to the user."),
        "inputSchema": _schema({
            "text": {"type": "string", "description": "The full draft."},
            "formal": {"type": "boolean", "description": "Zero tolerance for em dashes."},
        }, ["text"]),
    },
    {
        "name": "scan_file",
        "description": "Scan a text or markdown file on the local disk for AI-writing tells.",
        "inputSchema": _schema({
            "path": {"type": "string", "description": "Path to the file."},
            "formal": {"type": "boolean", "description": "Zero tolerance for em dashes."},
        }, ["path"]),
    },
    {
        "name": "get_rules",
        "description": "Return the short writing rule. Read it once before drafting.",
        "inputSchema": _schema({}),
    },
]


def _scan(text, formal):
    score, findings, nw = analyze(text, formal)
    out = report(score, findings, nw)
    if nw < 80:
        out += "\n  (under 80 words: stats unreliable)"
    if verdict(score) == "clean":
        return out + "\nSend it."
    return out + "\nRewrite the flagged sentences from the facts. Do not swap synonyms. Scan again."


def call_tool(name, args):
    if name == "scan_text":
        text = args.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        return _scan(text, bool(args.get("formal")))
    if name == "scan_file":
        path = os.path.expanduser(str(args.get("path", "")))
        if os.path.getsize(path) > 2000000:
            raise ValueError("file too large")
        with open(path, encoding="utf-8") as f:
            return _scan(f.read(), bool(args.get("formal")))
    if name == "get_rules":
        return short_rule()
    raise KeyError(name)


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg):
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if method is None or mid is None:  # notification or stray response
        return None
    if method == "initialize":
        res = {
            "protocolVersion": params.get("protocolVersion") or "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "turnitoff", "version": __version__},
            "instructions": INSTRUCTIONS,
        }
    elif method == "ping":
        res = {}
    elif method == "tools/list":
        res = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            text = call_tool(params.get("name"), params.get("arguments") or {})
            res = {"content": [{"type": "text", "text": text}], "isError": False}
        except KeyError:
            return _error(mid, -32602, "unknown tool: %s" % params.get("name"))
        except Exception as e:
            res = {"content": [{"type": "text", "text": "error: %s" % e}], "isError": True}
    else:
        return _error(mid, -32601, "method not found: %s" % method)
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        out = handle(msg) if isinstance(msg, dict) else None
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
