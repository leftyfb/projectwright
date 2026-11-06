"""End-to-end onboarding and acceptance gate using a disposable pw install."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "projectwright"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        text=True, timeout=30,
    ).stdout.strip()


class TaskTrackerProjectwrightE2E(unittest.TestCase):
    def test_one_shot_lifecycle_stops_at_unapproved_milestone(self):
        with tempfile.TemporaryDirectory(prefix="pw-task-tracker-e2e-") as temporary:
            base = Path(temporary)
            home = base / "home"
            home.mkdir()
            state = base / "projectwright-state"
            repo = base / "task-tracker"
            repo.mkdir()
            git(repo, "init", "-q", "-b", "main")
            git(repo, "config", "user.name", "Fixture")
            git(repo, "config", "user.email", "fixture@example.invalid")
            (repo / "README.md").write_text("Disposable task tracker starter.\n", encoding="utf-8")
            (repo / "task_tracker.py").write_text("raise NotImplementedError('starter')\n", encoding="utf-8")
            tests_dir = repo / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_task_tracker_m1.py").write_text(
                "import unittest\nimport task_tracker\n"
                "class TrackerTests(unittest.TestCase):\n"
                "    def test_ready_marker(self): self.assertEqual(task_tracker.STATUS, 'ready')\n",
                encoding="utf-8",
            )
            git(repo, "add", "README.md")
            git(repo, "add", "task_tracker.py", "tests/test_task_tracker_m1.py")
            git(repo, "commit", "-qm", "starter")

            # This mirrors the generated setuptools console-script wrapper for
            # the real pyproject entry point pw_dispatch:cli. It is executable
            # through PATH like an installed pw, not a direct module invocation.
            bindir = base / "bin"
            bindir.mkdir()
            pw = bindir / "pw"
            pw.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "from pw_dispatch import cli\n"
                "if __name__ == '__main__':\n"
                "    sys.exit(cli())\n",
                encoding="utf-8",
            )
            pw.chmod(0o700)

            calls = base / "hermes-calls.jsonl"
            fake_hermes = bindir / "hermes"
            fake_hermes.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, re, subprocess, sys\n"
                "log = pathlib.Path(os.environ['PW_FAKE_HERMES_LOG'])\n"
                "with log.open('a', encoding='utf-8') as stream:\n"
                "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                "if '-z' in sys.argv:\n"
                "    prompt = sys.argv[sys.argv.index('-z') + 1]\n"
                "    if 'TRACK-1-M1' not in prompt or 'TRACK-1-M2' not in prompt:\n"
                "        raise SystemExit('requirements were not loaded into planning prompt')\n"
                "    print(json.dumps({'tasks':[\n"
                "      {'id':'P100','kind':'READ','description':'Inspect the disposable task tracker starter scope and report its safety constraints', 'requirement_id':'TRACK-1','milestone_id':'TRACK-1-M1'},\n"
                "      {'id':'P101','kind':'EDIT','description':'Implement the minimal M1 task tracker ready marker in its existing module', 'requirement_id':'TRACK-1','milestone_id':'TRACK-1-M1'},\n"
                "      {'id':'P102','kind':'TEST','description':'Run the M1 standard-library task tracker acceptance test', 'requirement_id':'TRACK-1','milestone_id':'TRACK-1-M1'},\n"
                "      {'id':'P103','kind':'COMMIT','description':'Commit the reviewed and tested M1 task tracker changes', 'requirement_id':'TRACK-1','milestone_id':'TRACK-1-M1'}\n"
                "    ]}))\n"
                "    raise SystemExit(0)\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'send':\n"
                "    # Capture-only stub: no Telegram or network request is made.\n"
                "    raise SystemExit(0)\n"
                "prompt = sys.stdin.read()\n"
                "match = re.search(r'Assignment: (P[0-9]+) [—-] (READ|EDIT|TEST|COMMIT):', prompt)\n"
                "if not match: raise SystemExit('missing assignment')\n"
                "task_id, kind = match.groups()\n"
                "report_match = re.search(r'at this EXACT absolute path:\\s*\\n([^\\n]+)', prompt)\n"
                "if not report_match: raise SystemExit('missing completion report path')\n"
                "report = pathlib.Path(report_match.group(1).strip())\n"
                "repo = pathlib.Path.cwd()\n"
                "if kind == 'READ' and not (repo / 'README.md').is_file(): raise SystemExit('starter README missing')\n"
                "if kind == 'EDIT': (repo / 'task_tracker.py').write_text(\"STATUS = 'ready'\\n\", encoding='utf-8')\n"
                "if kind == 'TEST':\n"
                "    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_task_tracker_m1.py'], cwd=repo)\n"
                "    if result.returncode: raise SystemExit(result.returncode)\n"
                "if kind == 'COMMIT':\n"
                "    subprocess.run(['git', 'add', 'task_tracker.py'], cwd=repo, check=True)\n"
                "    subprocess.run(['git', 'commit', '-m', 'feat: complete M1 task tracker'], cwd=repo, check=True, stdout=subprocess.DEVNULL)\n"
                "report.write_text(json.dumps({'task_id':task_id,'status':'completed','summary':'Fixture completed '+kind,'verification':'Controlled fake provider executed the requested fixture step','blocker':''}), encoding='utf-8')\n",
                encoding="utf-8",
            )
            fake_hermes.chmod(0o700)

            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                "PYTHONPATH": str(SRC),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PW_FAKE_HERMES_LOG": str(calls),
            }

            def run(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
                result = subprocess.run(
                    [str(pw), *args], cwd=base, env=env, capture_output=True,
                    text=True, timeout=90,
                )
                diagnostic = ""
                if result.returncode != expected:
                    cfg_file = state / "projects" / project / "config.json"
                    cycle = "<missing config>"
                    if cfg_file.exists():
                        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                        cycle_file = Path(cfg.get("cycle_file", "")).expanduser()
                        cycle = f"path={cycle_file}, content={cycle_file.read_text(encoding='utf-8') if cycle_file.is_file() else '<missing>'}"
                    queue_file = state / "projects" / project / "queue.md"
                    queue = queue_file.read_text(encoding="utf-8") if queue_file.exists() else "<missing>"
                    repo_status = subprocess.run(
                        ["git", "-C", str(repo), "status", "--short"],
                        capture_output=True, text=True,
                    ).stdout
                    diagnostic = (
                        f"provider_calls={calls.read_text(encoding='utf-8') if calls.exists() else '<none>'}\n"
                        f"queue={queue}\ncycle={cycle}\nrepo_status={repo_status}"
                    )
                self.assertEqual(
                    result.returncode, expected,
                    f"pw {' '.join(args)} returned {result.returncode};\n"
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
                    f"{diagnostic}",
                )
                return result

            project = "task-tracker-e2e"
            run("init", "--project", project, "--repo", str(repo), "--config-dir", str(state))
            project_dir = state / "projects" / project
            self.assertTrue((project_dir / "config.json").is_file())
            config_path = project_dir / "config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["hermes"] = str(fake_hermes)
            config["cycle_file"] = str(project_dir / "git_cycle.json")
            config["planning"] = {"enabled": False, "requirements_file": str(project_dir / "requirements.md")}
            config["execution"] = {"enabled": False}
            config["quota"] = {"enabled": False}
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            requirements = """# Task tracker requirements

## TRACK-1 — Local task tracker
Use only Python 3 standard library; no external services, credentials, or network access.

### TRACK-1-M1 — Scaffold and core lifecycle
Implement a small source scaffold and isolated test. The controlled test provider supplies the implementation tasks for this lifecycle demonstration.

#### Acceptance
- **Command:** `python3 -B -m unittest discover -s tests -p test_task_tracker_m1.py`
- **Scope:** `task_tracker.py`
- **Scope:** `tests/test_task_tracker_m1.py`

### TRACK-1-M2 — Safe validation
Reject malformed local input and document recovery without destroying user data.

#### Acceptance
- **Command:** `python3 -B -m unittest discover -s tests -p test_task_tracker_m2.py`
- **Scope:** `task_tracker.py`
- **Scope:** `tests/test_task_tracker_m2.py`
"""
            (project_dir / "requirements.md").write_text(requirements, encoding="utf-8")
            run("plan", "--project", project, "--config-dir", str(state))
            queue_path = project_dir / "queue.md"
            queue = queue_path.read_text(encoding="utf-8")
            self.assertEqual(["P100", "P101", "P102", "P103"], re.findall(r"\*\*(P[0-9]+) —", queue))
            self.assertIn("TRACK-1-M1", queue)

            # First prove the one-task `pw start` path with a read-only task.
            # Use the regular planner/dispatcher route for the real Git cycle;
            # it independently authorizes only in-scope continuation tasks.
            result = run("start", "--project", project, "--config-dir", str(state), "--yes")
            self.assertIn("last_completed=P100", result.stdout)
            current_config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIs(current_config["execution"]["enabled"], False)
            unit = home / ".config/systemd/user" / f"projectwright-worker-{project}.timer"
            self.assertFalse(unit.exists(), "manual pw start unexpectedly installed a recurring timer")

            # Persistent dispatch is a separate explicit authorization, not a
            # side effect of the preceding one-shot start. Keep it in this
            # isolated fixture only; no timer is installed.
            run("authorize-execution", "--project", project, "--config-dir", str(state), "--yes")
            for task_id in ("P101", "P102", "P103"):
                result = run("tick", "--project", project, "--config-dir", str(state), "--no-telegram")
                self.assertIn("last_completed=" + task_id, result.stdout)
                current_queue = queue_path.read_text(encoding="utf-8")
                completed_ids = re.findall(r"- \[x\] \*\*(P[0-9]+) —", current_queue)
                self.assertGreaterEqual(len(completed_ids), ("P101", "P102", "P103").index(task_id) + 2)
                current_config = json.loads(config_path.read_text(encoding="utf-8"))
                self.assertIs(current_config["execution"]["enabled"], True)
                self.assertFalse(unit.exists(), "manual pw start unexpectedly installed a recurring timer")

            # No disable subcommand exists; restore the disposable project's
            # config directly after the manually driven cycle for the final
            # no-execution/no-timer assertions.
            current_config = json.loads(config_path.read_text(encoding="utf-8"))
            current_config["execution"]["enabled"] = False
            config_path.write_text(json.dumps(current_config, indent=2) + "\n", encoding="utf-8")

            milestone_status = run("status", "--project", project, "--config-dir", str(state), "--json")
            status = json.loads(milestone_status.stdout)
            self.assertEqual(status["decision"], "awaiting_acceptance")
            self.assertEqual(status.get("milestones"), ["TRACK-1-M1"])
            self.assertIs(status["execution_enabled"], False)
            self.assertEqual(status["recurring_execution"], "not_configured")
            self.assertIs(status["recurring_execution_configured"], False)
            self.assertIs(status["recurring_execution_enabled"], False)
            self.assertFalse((project_dir / "telegram_acceptance.json").exists())
            # The last verified task now pins the approval request immediately,
            # even when Telegram delivery is unavailable in this local fixture.
            pending = json.loads((project_dir / "telegram_approval_pending.json").read_text())
            self.assertEqual(pending["milestone"], "TRACK-1-M1")
            self.assertFalse((project_dir / "telegram_approval_notified.json").exists())

            # Without Telegram, approval is unavailable: replanning is gated
            # locally and the valid fake provider is not called for M2.
            calls_before = calls.read_text(encoding="utf-8").splitlines()
            blocked_plan = run("plan", "--project", project, "--config-dir", str(state), expected=3)
            self.assertEqual(blocked_plan.stdout, "")  # gate blocks before planner output
            blocked_start = run("start", "--project", project, "--config-dir", str(state), "--yes", expected=21)
            self.assertIn("manager contract", blocked_start.stderr)
            self.assertEqual(calls.read_text(encoding="utf-8").splitlines(), calls_before)
            final_queue = queue_path.read_text(encoding="utf-8")
            self.assertNotIn("P104", final_queue)
            self.assertNotIn("TRACK-1-M2", final_queue)
            final_config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIs(final_config["execution"]["enabled"], False)
            self.assertFalse((home / ".config/systemd/user" / f"projectwright-worker-{project}.timer").exists())

            provider_calls = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sum(call and call[0] == "chat" for call in provider_calls), 4)
            self.assertEqual(sum("-z" in call for call in provider_calls), 1)


if __name__ == "__main__":
    unittest.main()
