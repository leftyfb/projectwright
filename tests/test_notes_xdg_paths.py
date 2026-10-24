"""Projectwright notes utilities must use XDG root rather than a live Hermes home."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"src"/"projectwright"

class NotesRootTests(unittest.TestCase):
    def test_sync_default_xdg_root(self):
        with tempfile.TemporaryDirectory() as td:
            env={**os.environ,"HOME":td,"XDG_CONFIG_HOME":str(Path(td)/"xdg")}
            env.pop("HERMES_PROJECT_CONFIG_DIR",None)
            env.pop("PROJECTWRIGHT_CONFIG_DIR",None)
            proc=subprocess.run([sys.executable,"-B",str(SOURCE/"project_notes_sync.py"),"--project","fixture","--status"],env=env,capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn(str(Path(td)/"xdg/projectwright/projects/fixture/config.json"),proc.stderr)

    def test_sync_explicit_config_dir(self):
        with tempfile.TemporaryDirectory() as td:
            proc=subprocess.run([sys.executable,"-B",str(SOURCE/"project_notes_sync.py"),"--project","fixture","--status","--config-dir",td],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn(str(Path(td)/"projects/fixture/config.json"),proc.stderr)

    def test_sync_rejects_conflicting_root_flags(self):
        with tempfile.TemporaryDirectory() as td:
            proc=subprocess.run([sys.executable,"-B",str(SOURCE/"project_notes_sync.py"),"--project","fixture","--status","--config-dir",td,"--config-root",td],capture_output=True,text=True)
            self.assertEqual(proc.returncode,2)
            self.assertIn("mutually exclusive",proc.stderr)

    def test_publisher_uses_shared_resolver_and_canonical_imports(self):
        src=(SOURCE/"project_notes_publisher.py").read_text()
        self.assertIn("root=default_project_root()",src)
        self.assertIn("from pw_worker_journal import",src)
        self.assertIn("from pw_worker_progress import",src)

if __name__=="__main__":
    unittest.main()
