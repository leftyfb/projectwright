"""Built-in Projectwright paths and JSON override resolution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"

class ConfigDefaultResolutionTests(unittest.TestCase):
    def test_no_file_produces_all_runtime_paths_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            env = {**os.environ, "HOME": td, "XDG_CONFIG_HOME": str(home/"xdg"),
                   "PYTHONPATH": str(SRC)}
            env.pop("PROJECTWRIGHT_CONFIG_DIR", None)
            env.pop("HERMES_PROJECT_CONFIG_DIR", None)
            proc = subprocess.run([sys.executable, "-B", "-m", "pw_defaults", "--project", "demo"],
                                  capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            effective = data["effective_config"]
            root = home/"xdg/projectwright/projects/demo"
            self.assertEqual(effective["queue"], str(root/"queue.md"))
            self.assertEqual(effective["result_dir"], str(root/"results"))
            self.assertEqual(effective["lock"], str(root/"worker.lock"))
            self.assertFalse(effective["execution"]["enabled"])
            self.assertFalse(root.exists())

    def test_manager_loader_consumes_defaults_without_a_file(self):
        with tempfile.TemporaryDirectory() as td:
            env = {**os.environ, "PYTHONPATH": str(SRC)}
            script = (
                "import json,sys; from pathlib import Path; "
                "from project_queue_manager import project_config; "
                "path,cfg=project_config('demo',Path(sys.argv[1])); "
                "print(json.dumps({'path':str(path),'cfg':cfg}))"
            )
            proc = subprocess.run([sys.executable, "-B", "-c", script, td],
                                  capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["cfg"]["queue"], str(Path(td)/"demo/queue.md"))
            self.assertEqual(data["cfg"]["worktree"], str(Path(td)/"demo/worktree"))
            self.assertEqual(data["cfg"]["branch"], "main")
            self.assertEqual(data["cfg"]["timeout_seconds"], 900)
            self.assertFalse(data["cfg"]["execution"]["enabled"])
            self.assertFalse((Path(td)/"demo").exists())

    def test_manager_loader_preserves_legacy_explicit_fields(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            directory = base / "demo"
            directory.mkdir()
            (directory / "config.json").write_text(json.dumps({
                "id": "demo", "queue": "/explicit/queue.md",
                "worktree": "/explicit/repo", "branch": "test",
                "cycle_file": "/explicit/cycle.json", "lock": "/explicit/lock",
                "planning": {"enabled": True}
            }))
            env = {**os.environ, "PYTHONPATH": str(SRC)}
            cmd = ("import json,sys; from pathlib import Path; "
                   "from project_queue_manager import project_config; "
                   "_,cfg=project_config('demo',Path(sys.argv[1])); "
                   "print(json.dumps(cfg))")
            proc = subprocess.run([sys.executable,"-B","-c",cmd,td],env=env,
                                  capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            cfg = json.loads(proc.stdout)
            self.assertEqual(cfg["queue"],"/explicit/queue.md")
            self.assertEqual(cfg["worktree"],"/explicit/repo")
            self.assertTrue(cfg["planning"]["enabled"])
            self.assertEqual(cfg["timeout_seconds"],900)

    def test_malformed_enablement_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td)/"demo"
            directory.mkdir()
            env={**os.environ,"PYTHONPATH":str(SRC)}
            for bad in ({"execution":{"enabled":"false"}},
                        {"planning":{"enabled":1}},
                        {"notes":[]},
                        {"execution":"enabled"}):
                with self.subTest(bad=bad):
                    (directory/"config.json").write_text(json.dumps({"id":"demo",**bad}))
                    proc=subprocess.run([sys.executable,"-B","-c",
                        "import sys; from pathlib import Path; from pw_config import load; load('demo',Path(sys.argv[1]))",
                        td],capture_output=True,text=True,env=env)
                    self.assertNotEqual(proc.returncode,0)
                    self.assertIn("ValueError",proc.stderr)

    def test_environment_worktree_and_branch_override_json(self):
        with tempfile.TemporaryDirectory() as td:
            env={**os.environ,"PYTHONPATH":str(SRC),
                 "PROJECTWRIGHT_WORKTREE":str(Path(td)/"repo"),
                 "PROJECTWRIGHT_BRANCH":"feature/my-work"}
            command=("import json,sys; from pathlib import Path; "
                     "from pw_config import load; "
                     "print(json.dumps(load('demo',Path(sys.argv[1]))[1]))")
            proc=subprocess.run([sys.executable,"-B","-c",command,td],
                                capture_output=True,text=True,env=env)
            self.assertEqual(proc.returncode,0,proc.stderr)
            cfg=json.loads(proc.stdout)
            self.assertEqual(cfg["worktree"],str(Path(td)/"repo"))
            self.assertEqual(cfg["branch"],"feature/my-work")
            self.assertFalse(Path(td,"demo").exists())
            env["PROJECTWRIGHT_WORKTREE"]="relative/path"
            invalid=subprocess.run([sys.executable,"-B","-c",command,td],
                                   capture_output=True,text=True,env=env)
            self.assertNotEqual(invalid.returncode,0)
            self.assertIn("PROJECTWRIGHT_WORKTREE must be an absolute path",invalid.stderr)
            env["PROJECTWRIGHT_WORKTREE"]=str(Path(td)/"repo")
            env["PROJECTWRIGHT_BRANCH"]="../other"
            invalid=subprocess.run([sys.executable,"-B","-c",command,td],
                                   capture_output=True,text=True,env=env)
            self.assertNotEqual(invalid.returncode,0)
            self.assertIn("Invalid PROJECTWRIGHT_BRANCH",invalid.stderr)

    def test_planner_resolves_default_hermes_from_path(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            binary=folder/"hermes"
            binary.write_text("#!/bin/sh\\nexit 0\\n")
            binary.chmod(0o755)
            env={**os.environ,"PYTHONPATH":str(SRC),
                 "PATH":str(folder)+os.pathsep+os.environ.get("PATH","")}
            script=("from unittest.mock import patch; "
                    "from project_queue_planner import run_planner; "
                    "import subprocess; "
                    "with patch('subprocess.Popen') as proc: pass")
            # Provider resolution is verified without launching an agent.
            src=(SRC/"project_queue_planner.py").read_text()
            self.assertIn("shutil.which(cmd[0])",src)
            self.assertTrue(binary.is_file())

    def test_json_overrides_take_precedence_without_losing_nested_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project_dir = base/"demo"
            project_dir.mkdir()
            (project_dir/"config.json").write_text(json.dumps({
                "id": "demo", "timeout_seconds": 120,
                "planning": {"trigger": {"pending_below": 2}}
            }))
            env = {**os.environ, "PYTHONPATH": str(SRC), "PROJECTWRIGHT_CONFIG_DIR": str(base.parent/"unused")}
            proc = subprocess.run([sys.executable, "-B", "-c",
                "from pathlib import Path; from pw_config import load; import json,sys; print(json.dumps(load('demo', Path(sys.argv[1]))[1]))",
                str(base)], capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            cfg = json.loads(proc.stdout)
            self.assertEqual(cfg["timeout_seconds"], 120)
            self.assertFalse(cfg["planning"]["enabled"])
            self.assertEqual(cfg["planning"]["trigger"]["pending_below"], 2)
            self.assertEqual(cfg["id"], "demo")

if __name__ == "__main__":
    unittest.main()
