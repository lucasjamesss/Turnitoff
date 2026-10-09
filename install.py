#!/usr/bin/env python3
"""Turnitoff installer. Standard library only. Safe to run twice.

    python3 install.py              install
    python3 install.py --strict     also check long chat replies (Claude Code Stop hook)
    python3 install.py --dry-run    show what would change, change nothing
    python3 install.py --uninstall  remove everything this installer added

It only touches Claude's own settings for the current user. Each config file it
edits is copied once to <file>.turnitoff-backup before the first change.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = "turnitoff"
HERE = Path(__file__).resolve().parent

# Packed with tells on purpose. Used only by the self-test.
SAMPLE_AI = ("Moreover, it is worth noting that this tapestry underscores the pivotal role of seamless "
             "innovation, highlighting how leveraging robust frameworks fosters a vibrant landscape. ") * 4


def home():
    return Path.home()


def dest():
    return home() / ".turnitoff"


def rules_path():
    return home() / ".claude" / "rules" / "turnitoff.md"


def settings_path():
    return home() / ".claude" / "settings.json"


def desktop_config():
    if sys.platform == "darwin":
        return home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        return (Path(base) if base else home() / "AppData" / "Roaming") / "Claude" / "claude_desktop_config.json"
    return home() / ".config" / "Claude" / "claude_desktop_config.json"


def tilde(p):
    p = Path(p)
    try:
        return "~/" + p.relative_to(home()).as_posix()
    except ValueError:
        return str(p)


def say(tag, msg):
    print("  %-5s %s" % (tag, msg))


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def first_line(r):
    text = (r.stderr or r.stdout or "").strip()
    return text.splitlines()[0] if text else "no output"


def has_claude_code():
    return bool(shutil.which("claude")) or (home() / ".claude").is_dir()


def has_desktop():
    return desktop_config().parent.is_dir()


# ---- JSON config helpers -------------------------------------------------

def load_json(path):
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else {}


def backup_once(path):
    b = path.with_name(path.name + ".turnitoff-backup")
    if path.exists() and not b.exists():
        shutil.copy2(str(path), str(b))
        return b
    return None


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".turnitoff-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def server_def():
    return {"command": sys.executable, "args": [str(dest() / "run.py"), "mcp"]}


def hook_command():
    return '"%s" "%s" hook' % (Path(sys.executable).as_posix(), (dest() / "run.py").as_posix())


def is_ours(cmd):
    return isinstance(cmd, str) and "/.turnitoff/run.py" in cmd.replace("\\", "/")


def strip_ours(settings):
    """Remove our hook entries from a settings dict. Returns True if anything changed."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    changed = False
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        keep = []
        for g in groups:
            inner = g.get("hooks") if isinstance(g, dict) else None
            if isinstance(inner, list):
                new = [h for h in inner if not (isinstance(h, dict) and is_ours(h.get("command")))]
                if len(new) != len(inner):
                    changed = True
                    if not new:
                        continue
                    g = dict(g, hooks=new)
            keep.append(g)
        if keep:
            hooks[event] = keep
        elif groups:
            del hooks[event]
    if not hooks:
        del settings["hooks"]
    return changed


# ---- install steps -------------------------------------------------------

def install_files(dry):
    d = dest()
    if dry:
        say("dry", "copy the program to %s" % tilde(d))
        return True
    try:
        d.mkdir(parents=True, exist_ok=True)
        if d.resolve() != HERE:
            pkg = d / "turnitoff"
            if pkg.exists():
                shutil.rmtree(str(pkg))
            shutil.copytree(str(HERE / "turnitoff"), str(pkg), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for f in ("run.py", "install.py"):
                shutil.copy2(str(HERE / f), str(d / f))
        say("ok", "program copied to %s" % tilde(d))
        return True
    except OSError as e:
        say("FAIL", "could not copy the program to %s (%s)" % (tilde(d), e))
        return False


def write_rules(dry):
    p = rules_path()
    if dry:
        say("dry", "save the writing rule to %s" % tilde(p))
        return True
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text((HERE / "turnitoff" / "data" / "RULES.md").read_text(encoding="utf-8"), encoding="utf-8")
        say("ok", "writing rule saved to %s (Claude Code loads it every session)" % tilde(p))
        return True
    except OSError as e:
        say("FAIL", "could not save the writing rule (%s)" % e)
        return False


def patch_hooks(strict, dry):
    p = settings_path()
    what = "file checker" + (" + reply checker" if strict else "")
    if dry:
        say("dry", "add the %s to %s" % (what, tilde(p)))
        return True
    try:
        data = load_json(p)
        if not isinstance(data, dict):
            raise ValueError("top level is not an object")
        strip_ours(data)
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("'hooks' is not an object")
        cmd = hook_command()
        entry = {"type": "command", "command": cmd, "timeout": 10}
        post = hooks.setdefault("PostToolUse", [])
        if not isinstance(post, list):
            raise ValueError("'PostToolUse' is not a list")
        post.append({"matcher": "Write|Edit|MultiEdit", "hooks": [dict(entry)]})
        if strict:
            stop = hooks.setdefault("Stop", [])
            if not isinstance(stop, list):
                raise ValueError("'Stop' is not a list")
            stop.append({"hooks": [dict(entry)]})
        b = backup_once(p)
        save_json(p, data)
        say("ok", "%s added to %s%s" % (what, tilde(p), " (backup: %s)" % tilde(b) if b else ""))
        return True
    except (OSError, ValueError) as e:
        say("WARN", "left %s untouched, could not read it (%s)" % (tilde(p), e))
        return False


def register_cli(dry):
    claude = shutil.which("claude")
    if dry:
        say("dry", "register the Turnitoff tool with Claude Code")
        return True
    run([claude, "mcp", "remove", NAME, "--scope", "user"])  # fine if it was not there
    r = run([claude, "mcp", "add", "--scope", "user", NAME, "--", sys.executable, str(dest() / "run.py"), "mcp"])
    if r.returncode == 0:
        say("ok", "Claude Code: Turnitoff tool registered")
        return True
    say("FAIL", "Claude Code: could not register the tool (%s)" % first_line(r))
    return False


def patch_desktop(dry):
    p = desktop_config()
    if dry:
        say("dry", "register the Turnitoff tool in %s" % tilde(p))
        return True
    try:
        data = load_json(p)
        if not isinstance(data, dict):
            raise ValueError("top level is not an object")
        servers = data.setdefault("mcpServers", {})
        if not isinstance(servers, dict):
            raise ValueError("'mcpServers' is not an object")
        servers[NAME] = server_def()
        b = backup_once(p)
        save_json(p, data)
        say("ok", "Claude Desktop: Turnitoff tool registered%s" % (" (backup: %s)" % tilde(b) if b else ""))
        return True
    except (OSError, ValueError) as e:
        say("WARN", "Claude Desktop: left its config untouched (%s)" % e)
        return False


def self_test():
    run_py = dest() / "run.py"
    tmp = tempfile.mkdtemp(prefix="turnitoff-test-")
    env = dict(os.environ, TMPDIR=tmp, TEMP=tmp, TMP=tmp)
    env.pop("TURNITOFF", None)
    problems = []
    try:
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "selftest", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "scan_text", "arguments": {"text": SAMPLE_AI}}},
        ]
        try:
            r = subprocess.run([sys.executable, str(run_py), "mcp"], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                               capture_output=True, text=True, timeout=30, env=env)
            out = {}
            for line in r.stdout.splitlines():
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if isinstance(m, dict):
                    out[m.get("id")] = m
            names = [t["name"] for t in out.get(2, {}).get("result", {}).get("tools", [])]
            if "scan_text" not in names:
                problems.append("tool server did not list its tools")
            text = (out.get(3, {}).get("result", {}).get("content") or [{}])[0].get("text", "")
            if "reads-AI" not in text:
                problems.append("tool server did not flag the test text")
        except (OSError, subprocess.TimeoutExpired) as e:
            problems.append("tool server did not start (%s)" % e)

        sample = os.path.join(tmp, "selftest.md")
        with open(sample, "w", encoding="utf-8") as f:
            f.write(SAMPLE_AI)
        payload = json.dumps({"hook_event_name": "PostToolUse", "tool_input": {"file_path": sample}})
        try:
            r = subprocess.run([sys.executable, str(run_py), "hook"], input=payload, capture_output=True, text=True,
                               timeout=30, env=env)
            if r.returncode != 2 or "turnitoff" not in r.stderr:
                problems.append("file checker did not flag the test text (exit %s)" % r.returncode)
        except (OSError, subprocess.TimeoutExpired) as e:
            problems.append("file checker did not run (%s)" % e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if problems:
        for pr in problems:
            say("FAIL", "self-test: " + pr)
        return False
    say("ok", "self-test passed (tool server and file checker both respond)")
    return True


def install(strict, dry):
    print("Turnitoff installer" + (" (dry run, nothing changes)" if dry else ""))
    code, desktop = has_claude_code(), has_desktop()
    if not (code or desktop):
        say("FAIL", "no Claude Code or Claude Desktop found on this computer")
        print("Use the copy-paste method instead (INSTALL.md, Path C).")
        return 3
    results = [install_files(dry)]
    if code:
        results.append(write_rules(dry))
        results.append(patch_hooks(strict, dry))
        if shutil.which("claude"):
            results.append(register_cli(dry))
        else:
            say("skip", "Claude Code tool registration: the 'claude' command was not found (rule and checker still work)")
    else:
        say("skip", "Claude Code: not found")
    if desktop:
        results.append(patch_desktop(dry))
    else:
        say("skip", "Claude Desktop: not found")
    if not dry:
        results.append(self_test())
    if all(results):
        if not dry:
            print("turnitoff: install OK. Quit and reopen Claude so it loads the changes.")
        return 0
    print("turnitoff: install incomplete. See the FAIL and WARN lines above. The copy-paste method still works (INSTALL.md, Path C).")
    return 1


def uninstall(dry):
    print("Turnitoff uninstaller" + (" (dry run, nothing changes)" if dry else ""))
    claude = shutil.which("claude")
    if claude:
        if dry:
            say("dry", "remove the Claude Code tool")
        else:
            r = run([claude, "mcp", "remove", NAME, "--scope", "user"])
            say("ok" if r.returncode == 0 else "skip", "Claude Code tool " + ("removed" if r.returncode == 0 else "was not registered"))
    cfg = desktop_config()
    if cfg.exists():
        try:
            data = load_json(cfg)
            servers = data.get("mcpServers") if isinstance(data, dict) else None
            if isinstance(servers, dict) and NAME in servers:
                if dry:
                    say("dry", "remove the tool from %s" % tilde(cfg))
                else:
                    del servers[NAME]
                    save_json(cfg, data)
                    say("ok", "Claude Desktop tool removed")
        except (OSError, ValueError) as e:
            say("WARN", "could not edit %s (%s)" % (tilde(cfg), e))
    sp = settings_path()
    if sp.exists():
        try:
            data = load_json(sp)
            if isinstance(data, dict) and strip_ours(data):
                if dry:
                    say("dry", "remove the checker from %s" % tilde(sp))
                else:
                    save_json(sp, data)
                    say("ok", "checker removed from %s" % tilde(sp))
        except (OSError, ValueError) as e:
            say("WARN", "could not edit %s (%s)" % (tilde(sp), e))
    rp = rules_path()
    if rp.exists():
        if dry:
            say("dry", "delete %s" % tilde(rp))
        else:
            rp.unlink()
            say("ok", "writing rule deleted")
    if dest().exists():
        if dry:
            say("dry", "delete %s" % tilde(dest()))
        else:
            shutil.rmtree(str(dest()), ignore_errors=True)
            say("ok", "program deleted")
    if not dry:
        print("turnitoff: removed. Config backups (*.turnitoff-backup) were left in place.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="install.py", description="Install or remove Turnitoff.")
    ap.add_argument("--strict", action="store_true", help="also check long chat replies (Claude Code Stop hook)")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    ap.add_argument("--uninstall", action="store_true", help="remove everything this installer added")
    a = ap.parse_args(argv)
    if sys.version_info < (3, 8):
        say("FAIL", "needs Python 3.8 or newer (this is %d.%d)" % sys.version_info[:2])
        return 3
    return uninstall(a.dry_run) if a.uninstall else install(a.strict, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
