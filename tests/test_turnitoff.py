"""Run with: python3 -m unittest discover -s tests -v"""
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import install  # noqa: E402
from turnitoff import __version__, mcp_server  # noqa: E402
from turnitoff.rules import full_rule, short_rule  # noqa: E402
from turnitoff.scanner import analyze, verdict  # noqa: E402

AI = (ROOT / "tests" / "samples" / "ai.md").read_text(encoding="utf-8")
HUMAN = (ROOT / "tests" / "samples" / "human.md").read_text(encoding="utf-8")


def load_build_skill():
    spec = importlib.util.spec_from_file_location("build_skill", str(ROOT / "scripts" / "build_skill.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ScannerTests(unittest.TestCase):
    def test_ai_sample_is_flagged(self):
        score, findings, _ = analyze(AI)
        self.assertEqual(verdict(score), "reads-AI")
        self.assertTrue(any("vocabulary" in f for f in findings))

    def test_human_sample_is_clean(self):
        score, findings, _ = analyze(HUMAN)
        self.assertEqual(verdict(score), "clean", findings)

    def test_formal_mode_flags_a_single_dash(self):
        # one dash in ~430 words is under the casual limit, but formal mode allows none
        text = HUMAN.replace("Too busy.", "Too busy — no time.", 1) + "\n\n" + HUMAN
        dash = lambda formal: [f for f in analyze(text, formal=formal)[1] if "dash" in f]
        self.assertEqual(dash(False), [])
        self.assertEqual(len(dash(True)), 1)

    def test_code_and_urls_are_ignored(self):
        text = "Plain sentence here.\n```\nleverage seamless tapestry delve\n```\nSee https://example.com/tapestry for more."
        self.assertEqual(analyze(text)[1], [])


class CliTests(unittest.TestCase):
    def cli(self, *args, stdin=None, env=None):
        e = dict(os.environ, PYTHONPATH=str(ROOT))
        e.update(env or {})
        return subprocess.run([sys.executable, "-m", "turnitoff"] + list(args), input=stdin,
                              capture_output=True, text=True, env=e, cwd=str(ROOT))

    def test_scan_exit_codes(self):
        self.assertEqual(self.cli("scan", str(ROOT / "tests/samples/ai.md")).returncode, 1)
        self.assertEqual(self.cli("scan", str(ROOT / "tests/samples/human.md")).returncode, 0)

    def test_scan_stdin_json(self):
        r = self.cli("scan", "-", "--json", stdin=AI)
        data = json.loads(r.stdout)
        self.assertEqual(data["verdict"], "reads-AI")
        self.assertEqual(r.returncode, 1)

    def test_rules_output(self):
        self.assertEqual(self.cli("rules").stdout.strip(), short_rule())
        self.assertEqual(self.cli("rules", "--full").stdout, full_rule())


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="turnitoff-hook-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hook(self, payload, **extra):
        env = dict(os.environ, PYTHONPATH=str(ROOT), TMPDIR=self.tmp, TEMP=self.tmp, TMP=self.tmp)
        env.pop("TURNITOFF", None)
        env.pop("TURNITOFF_BLOCK_AT", None)
        env.update(extra)
        return subprocess.run([sys.executable, "-m", "turnitoff", "hook"], input=json.dumps(payload),
                              capture_output=True, text=True, env=env, cwd=str(ROOT))

    def file_event(self, name, text):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": p}}

    def test_flags_ai_prose_file(self):
        r = self.hook(self.file_event("essay.md", AI))
        self.assertEqual(r.returncode, 2)
        self.assertIn("reads-AI", r.stderr)

    def test_passes_human_prose_file(self):
        self.assertEqual(self.hook(self.file_event("essay.md", HUMAN)).returncode, 0)

    def test_ignores_code_files(self):
        self.assertEqual(self.hook(self.file_event("notes.py", AI)).returncode, 0)

    def test_ignores_instruction_files(self):
        for name in ("CLAUDE.md", "SKILL.md", "AGENTS.md"):
            self.assertEqual(self.hook(self.file_event(name, AI)).returncode, 0, name)

    def test_ignores_claude_config_dir(self):
        d = os.path.join(self.tmp, ".claude", "rules")
        os.makedirs(d)
        ev = self.file_event("x.md", AI)
        p = os.path.join(d, "x.md")
        shutil.move(ev["tool_input"]["file_path"], p)
        ev["tool_input"]["file_path"] = p
        self.assertEqual(self.hook(ev).returncode, 0)

    def test_short_text_is_not_judged(self):
        self.assertEqual(self.hook(self.file_event("short.md", "Moreover, a tapestry.")).returncode, 0)

    def test_missing_file_and_bad_input_do_not_crash(self):
        self.assertEqual(self.hook({"tool_input": {"file_path": "/nope/missing.md"}}).returncode, 0)
        self.assertEqual(self.hook({"tool_input": {}}).returncode, 0)
        self.assertEqual(self.hook(["not", "a", "dict"]).returncode, 0)

    def test_off_switch_and_threshold(self):
        ev = self.file_event("essay.md", AI)
        self.assertEqual(self.hook(ev, TURNITOFF="off").returncode, 0)
        self.assertEqual(self.hook(ev, TURNITOFF_BLOCK_AT="1000").returncode, 0)

    def test_file_loop_guard(self):
        ev = self.file_event("essay.md", AI)
        r1, r2, r3 = self.hook(ev), self.hook(ev), self.hook(ev)
        self.assertEqual([r1.returncode, r2.returncode, r3.returncode], [2, 2, 2])
        self.assertNotIn("Still flagged", r2.stderr)
        self.assertIn("Still flagged", r3.stderr)

    def test_stop_hook_flags_then_lets_go(self):
        ev = {"hook_event_name": "Stop", "session_id": "abc", "last_assistant_message": AI}
        codes = [self.hook(ev).returncode for _ in range(4)]
        self.assertEqual(codes, [2, 2, 0, 2])

    def test_stop_hook_ignores_clean_and_short(self):
        ok = {"hook_event_name": "Stop", "session_id": "s", "last_assistant_message": HUMAN}
        short = {"hook_event_name": "Stop", "session_id": "s", "last_assistant_message": "Done."}
        self.assertEqual(self.hook(ok).returncode, 0)
        self.assertEqual(self.hook(short).returncode, 0)


class McpTests(unittest.TestCase):
    def call(self, name, args, mid=9):
        return mcp_server.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                                  "params": {"name": name, "arguments": args}})

    def test_initialize_echoes_version_and_sends_instructions(self):
        r = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"protocolVersion": "2024-11-05"}})["result"]
        self.assertEqual(r["protocolVersion"], "2024-11-05")
        self.assertEqual(r["serverInfo"], {"name": "turnitoff", "version": __version__})
        self.assertIn("get_rules", r["instructions"])
        self.assertIn("tools", r["capabilities"])

    def test_tools_list(self):
        tools = mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"scan_text", "scan_file", "get_rules"})
        for t in tools:
            self.assertEqual(t["inputSchema"]["type"], "object")

    def test_scan_text(self):
        res = self.call("scan_text", {"text": AI})["result"]
        self.assertFalse(res["isError"])
        self.assertIn("reads-AI", res["content"][0]["text"])
        clean = self.call("scan_text", {"text": HUMAN})["result"]["content"][0]["text"]
        self.assertIn("Send it.", clean)

    def test_scan_file(self):
        res = self.call("scan_file", {"path": str(ROOT / "tests/samples/ai.md")})["result"]
        self.assertIn("reads-AI", res["content"][0]["text"])

    def test_get_rules(self):
        self.assertEqual(self.call("get_rules", {})["result"]["content"][0]["text"], short_rule())

    def test_errors(self):
        self.assertTrue(self.call("scan_text", {"text": "  "})["result"]["isError"])
        self.assertTrue(self.call("scan_file", {"path": "/nope/missing.md"})["result"]["isError"])
        self.assertEqual(self.call("nope", {})["error"]["code"], -32602)
        self.assertEqual(mcp_server.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"], -32601)

    def test_notifications_and_ping(self):
        self.assertIsNone(mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(mcp_server.handle({"jsonrpc": "2.0", "id": 4, "method": "ping"})["result"], {})

    def test_stdio_protocol(self):
        lines = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}),
            "this is not json",
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ]
        r = subprocess.run([sys.executable, str(ROOT / "run.py"), "mcp"], input="\n".join(lines) + "\n",
                           capture_output=True, text=True, timeout=30)
        out = [json.loads(x) for x in r.stdout.splitlines()]
        self.assertEqual([m["id"] for m in out], [1, 2])
        self.assertEqual(r.stderr, "")


class RuleTextTests(unittest.TestCase):
    def test_paste_block_fits_chatgpt_free_limit(self):
        self.assertLessEqual(len(short_rule()), 1400)  # Free and Go plans allow 1,500

    def test_install_runbook_carries_the_paste_block(self):
        self.assertIn(short_rule(), (ROOT / "INSTALL.md").read_text(encoding="utf-8"))

    def test_no_em_dashes_in_rule_files(self):
        for name in ("PASTE.md", "RULES.md"):
            text = (ROOT / "turnitoff" / "data" / name).read_text(encoding="utf-8")
            self.assertNotIn("—", text, name)

    def test_banned_words_in_scanner_cover_paste_list(self):
        # every single-word ban in PASTE should be known to the scanner
        banned = "delve tapestry landscape pivotal crucial underscore showcase foster enhance testament intricate multifaceted holistic robust seamless leverage utilize navigate realm journey vibrant".split()
        for w in banned:
            self.assertTrue(analyze("This is %s." % w)[1] or analyze("This is %s today and %s again." % (w, w))[1], w)


class PackageTests(unittest.TestCase):
    def test_versions_agree(self):
        m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
        self.assertEqual(m.group(1), __version__)

    def test_no_network_imports(self):
        bad = re.compile(r"^\s*(?:import|from)\s+(?:socket|urllib|http|requests|ftplib|smtplib|ssl)\b", re.M)
        for p in list((ROOT / "turnitoff").glob("*.py")) + [ROOT / "install.py", ROOT / "run.py"]:
            self.assertIsNone(bad.search(p.read_text(encoding="utf-8")), p.name)


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.bs = load_build_skill()

    def test_layout_and_frontmatter(self):
        files = self.bs.files()
        self.assertTrue(all(n.startswith("turnitoff/") for n in files))
        self.assertIn("turnitoff/SKILL.md", files)
        head = files["turnitoff/SKILL.md"].decode("utf-8").split("---")[1]
        self.assertRegex(head, r"(?m)^name: turnitoff$")
        desc = re.search(r"(?m)^description: (.+)$", head).group(1)
        self.assertLessEqual(len(desc), 200)
        self.assertNotIn("## Tools", files["turnitoff/references/RULES.md"].decode("utf-8"))

    def test_committed_zip_is_current(self):
        z = zipfile.ZipFile(str(ROOT / "dist" / "turnitoff-skill.zip"))
        built = self.bs.files()
        self.assertEqual(sorted(z.namelist()), sorted(built))
        for name, data in built.items():
            self.assertEqual(z.read(name), data, "%s is stale: run scripts/build_skill.py" % name)

    def test_bundled_scanner_runs_from_skill_folder(self):
        tmp = tempfile.mkdtemp(prefix="turnitoff-skill-")
        try:
            out = Path(tmp) / "x.zip"
            self.bs.build(out)
            zipfile.ZipFile(str(out)).extractall(tmp)
            skill = Path(tmp) / "turnitoff"
            for sample, code in (("ai.md", 1), ("human.md", 0)):
                r = subprocess.run([sys.executable, "scripts/scan.py", str(ROOT / "tests/samples" / sample)],
                                   cwd=str(skill), capture_output=True, text=True)
                self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipIf(os.name == "nt", "installer tests use a shell script as a fake claude command")
class InstallerTests(unittest.TestCase):
    ORIGINAL_SETTINGS = {
        "theme": "dark",
        "hooks": {"PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}]},
    }

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="turnitoff-home-"))
        self.home = self.tmp / "home"
        self.bin = self.tmp / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home),
                                                "PATH": str(self.bin)})
        self.env.start()
        os.environ.pop("APPDATA", None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def fake_claude(self):
        p = self.bin / "claude"
        p.write_text('#!/bin/sh\necho "$@" >> "%s/claude-calls.log"\nexit 0\n' % self.home, encoding="utf-8")
        p.chmod(0o755)

    def seed_settings(self, text=None):
        p = self.home / ".claude" / "settings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if text is not None else json.dumps(self.ORIGINAL_SETTINGS), encoding="utf-8")
        return p

    def seed_desktop(self):
        cfg = install.desktop_config()
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
        return cfg

    def go(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = install.main(list(args))
        return rc, buf.getvalue()

    def ours(self, settings):
        found = []
        for event, groups in settings.get("hooks", {}).items():
            for g in groups:
                for h in g["hooks"]:
                    if install.is_ours(h["command"]):
                        found.append(event)
        return found

    def test_full_install(self):
        self.fake_claude()
        sp = self.seed_settings()
        cfg = self.seed_desktop()
        rc, out = self.go()
        self.assertEqual(rc, 0, out)
        self.assertIn("install OK", out)
        d = self.home / ".turnitoff"
        self.assertTrue((d / "run.py").exists() and (d / "install.py").exists())
        self.assertTrue((d / "turnitoff" / "data" / "PASTE.md").exists())
        self.assertEqual((self.home / ".claude/rules/turnitoff.md").read_text(encoding="utf-8"), full_rule())
        settings = json.loads(sp.read_text(encoding="utf-8"))
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(self.ours(settings), ["PostToolUse"])
        self.assertEqual(settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"], "echo mine")
        backup = sp.with_name("settings.json.turnitoff-backup")
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), self.ORIGINAL_SETTINGS)
        calls = (self.home / "claude-calls.log").read_text(encoding="utf-8")
        self.assertIn("mcp add --scope user turnitoff -- %s" % sys.executable, calls)
        self.assertIn("run.py mcp", calls)
        desktop = json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]
        self.assertEqual(set(desktop), {"other", "turnitoff"})
        self.assertEqual(desktop["turnitoff"]["args"][-1], "mcp")

    def test_twice_is_the_same_as_once(self):
        self.fake_claude()
        sp = self.seed_settings()
        self.go()
        self.go()
        settings = json.loads(sp.read_text(encoding="utf-8"))
        self.assertEqual(self.ours(settings), ["PostToolUse"])
        backup = sp.with_name("settings.json.turnitoff-backup")
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), self.ORIGINAL_SETTINGS)

    def test_strict_adds_stop_hook(self):
        self.fake_claude()
        sp = self.seed_settings()
        self.go("--strict")
        self.assertEqual(sorted(self.ours(json.loads(sp.read_text(encoding="utf-8")))), ["PostToolUse", "Stop"])
        self.go()  # back to default drops the Stop hook
        self.assertEqual(self.ours(json.loads(sp.read_text(encoding="utf-8"))), ["PostToolUse"])

    def test_dry_run_changes_nothing(self):
        self.fake_claude()
        sp = self.seed_settings()
        before = sp.read_text(encoding="utf-8")
        rc, out = self.go("--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("dry", out)
        self.assertEqual(sp.read_text(encoding="utf-8"), before)
        self.assertFalse((self.home / ".turnitoff").exists())
        self.assertFalse((self.home / ".claude/rules").exists())
        self.assertFalse((self.home / "claude-calls.log").exists())

    def test_uninstall_removes_only_ours(self):
        self.fake_claude()
        sp = self.seed_settings()
        cfg = self.seed_desktop()
        self.go("--strict")
        rc, out = self.go("--uninstall")
        self.assertEqual(rc, 0, out)
        self.assertEqual(json.loads(sp.read_text(encoding="utf-8")), self.ORIGINAL_SETTINGS)
        self.assertEqual(set(json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]), {"other"})
        self.assertFalse((self.home / ".claude/rules/turnitoff.md").exists())
        self.assertFalse((self.home / ".turnitoff").exists())
        self.assertIn("mcp remove turnitoff --scope user", (self.home / "claude-calls.log").read_text(encoding="utf-8"))

    def test_nothing_to_attach_to(self):
        rc, out = self.go()
        self.assertEqual(rc, 3)
        self.assertIn("Path C", out)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_broken_settings_file_is_left_alone(self):
        self.fake_claude()
        sp = self.seed_settings("{ this is not json")
        rc, out = self.go()
        self.assertEqual(rc, 1)
        self.assertIn("WARN", out)
        self.assertEqual(sp.read_text(encoding="utf-8"), "{ this is not json")
        self.assertTrue((self.home / ".turnitoff/run.py").exists())  # the rest still installed

    def test_claude_code_without_cli_still_gets_rule_and_checker(self):
        (self.home / ".claude").mkdir()
        rc, out = self.go()
        self.assertEqual(rc, 0, out)
        self.assertIn("skip", out)
        self.assertTrue((self.home / ".claude/rules/turnitoff.md").exists())
        self.assertEqual(self.ours(json.loads((self.home / ".claude/settings.json").read_text(encoding="utf-8"))),
                         ["PostToolUse"])

    def test_desktop_only(self):
        cfg = self.seed_desktop()
        rc, out = self.go()
        self.assertEqual(rc, 0, out)
        self.assertIn("turnitoff", json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"])
        self.assertFalse((self.home / ".claude").exists())


if __name__ == "__main__":
    unittest.main()
