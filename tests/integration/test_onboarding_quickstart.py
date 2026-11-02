"""Disposable end-to-end test for the README onboarding commands."""
from __future__ import annotations
import json
import os
import pty
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"


class QuotaHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"entity_id": "sensor.codex_usage_weekly_remaining", "state": "90"}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, format, *args):
        pass


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True).stdout.strip()


class ReadmeQuickstartTests(unittest.TestCase):
    def test_documented_init_requirements_plan_status_and_manual_start(self):
        with tempfile.TemporaryDirectory(prefix="pw-onboarding-") as td:
            base = Path(td); home = base / "home"; home.mkdir()
            cfg_home = base / "xdg"; repo = base / "repos/myproject"; repo.mkdir(parents=True)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.name", "Fixture")
            git(repo, "config", "user.email", "fixture@example.invalid")
            (repo / "README.md").write_text("Disposable project fixture.\n")
            git(repo, "add", "README.md"); git(repo, "commit", "-qm", "fixture")

            fake_editor = base / "editor"
            fake_editor.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\nPath(sys.argv[-1]).write_text('## DEMO-1 — Disposable project\\n\\n### DEMO-1-M1 — Inspect the disposable project\\n')\n")
            fake_editor.chmod(0o700)
            fake_hermes = base / "hermes"
            fake_hermes.write_text('''#!/usr/bin/env python3
import json, pathlib, re, sys
if "send" in sys.argv:
 raise SystemExit(0)
if "-z" in sys.argv:
 print(json.dumps({"tasks":[{"id":"P101","kind":"READ","description":"Read the disposable project source and summarize its current structure","requirement_id":"DEMO-1","milestone_id":"DEMO-1-M1"}]})); raise SystemExit(0)
prompt = sys.stdin.read()
report = next(line.strip() for line in prompt.splitlines() if line.strip().startswith("/") and line.strip().endswith(".json"))
pathlib.Path(report).write_text(json.dumps({"task_id":"P101","status":"completed","summary":"Reviewed disposable project","verification":"Fixture review completed","blocker":""}))
''')
            fake_hermes.chmod(0o700)
            bin_dir = base / "bin"; bin_dir.mkdir()
            (bin_dir / "hermes").symlink_to(fake_hermes)
            pw = bin_dir / "pw"
            pw.write_text(f'#!/bin/sh\nPYTHONPATH="{SRC}" exec "{sys.executable}" -B -c \'import sys; sys.path.insert(0, "{SRC}"); import pw_dispatch; sys.exit(pw_dispatch.cli())\' "$@"\n')
            pw.chmod(0o700)

            quota_server = HTTPServer(("127.0.0.1", 0), QuotaHandler)
            thread = threading.Thread(target=quota_server.serve_forever, daemon=True); thread.start()
            self.addCleanup(quota_server.server_close)
            self.addCleanup(quota_server.shutdown)
            secret = home / ".hermes/secrets/ha.env"; secret.parent.mkdir(parents=True)
            secret.write_text(f"HA_URL=http://127.0.0.1:{quota_server.server_port}\nHA_TOKEN=fixture\n")
            env = {**os.environ, "HOME": str(home), "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""), "EDITOR": str(fake_editor), "VISUAL": "", "XDG_CONFIG_HOME": str(base / "xdg"), "PYTHONPATH": str(SRC)}
            def run(*args, input_text=None, expect=0):
                command = [str(pw), *args]
                if input_text is not None:
                    master, slave = pty.openpty()
                    try:
                        proc = subprocess.Popen(command, cwd=base, env=env, stdin=slave, stdout=slave, stderr=slave)
                        os.close(slave)
                        transcript = b""
                        while b"[y/N]" not in transcript and proc.poll() is None:
                            transcript += os.read(master, 4096)
                        os.write(master, input_text.encode())
                        returncode = proc.wait(timeout=30)
                        while True:
                            try:
                                chunk = os.read(master, 4096)
                            except OSError:
                                break
                            if not chunk:
                                break
                            transcript += chunk
                        result = subprocess.CompletedProcess(command, returncode, transcript.decode(errors="replace"), "")
                    finally:
                        os.close(master)
                else:
                    result = subprocess.run(command, cwd=base, env=env, text=True, capture_output=True)
                diagnostics = "\\n".join(f"{item}: {item.read_text(errors='replace')[-1600:]}" for item in (cfg_home / "projects/myproject").glob("**/*") if item.is_file()) if (cfg_home / "projects/myproject").exists() else ""
                self.assertEqual(result.returncode, expect, f"command: {args}\\nstdout: {result.stdout}\\nstderr: {result.stderr}\\nstate: {diagnostics}")
                return result

            # These are the commands shown by README, substituting a disposable repo.
            run("init", "--project", "myproject", "--repo", str(repo))
            run("requirements", "--project", "myproject", "--edit")
            planned = run("plan", "--project", "myproject")
            self.assertIn("P101", (cfg_home / "projects/myproject/queue.md").read_text())
            status = run("status", "--project", "myproject")
            self.assertIn("Planning: enabled", status.stdout)
            self.assertIn("Execution: disabled", status.stdout)
            machine = run("status", "--project", "myproject", "--json")
            self.assertEqual(json.loads(machine.stdout)["pending"], 1)
            started = run("start", "--project", "myproject", input_text="yes\n")
            config = json.loads((cfg_home / "projects/myproject/config.json").read_text())
            self.assertTrue(config["planning"]["enabled"])
            self.assertTrue(config["execution"]["enabled"])
            completed_status = run("status", "--project", "myproject")
            self.assertIn("Execution: enabled", completed_status.stdout)
            self.assertIn("Queue completed: 1", completed_status.stdout)
            self.assertIn("Next action:", completed_status.stdout)
            self.assertIn("completed", (cfg_home / "projects/myproject/work_log.md").read_text().lower())
            self.assertEqual(git(repo, "rev-parse", "--show-toplevel"), str(repo))
            self.assertFalse((cfg_home / "projects/myproject/worktree/.git").exists())

if __name__ == "__main__":
    unittest.main()
