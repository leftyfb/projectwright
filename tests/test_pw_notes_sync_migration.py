"""Canonical notes synchronization retains the legacy module API and CLI."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1]/"src"/"projectwright"
if str(SRC) not in sys.path:
    sys.path.insert(0,str(SRC))

class NotesSyncMigrationTests(unittest.TestCase):
    def test_legacy_functions_are_canonical(self):
        legacy=importlib.import_module("project_notes_sync")
        canonical=importlib.import_module("pw_notes_sync")
        for name in ("digest","atomic","paths","perform","main"):
            self.assertIs(getattr(legacy,name),getattr(canonical,name))

    def test_both_entrypoints_resolve_same_config_home(self):
        with tempfile.TemporaryDirectory() as td:
            env={**os.environ,"HOME":td,"XDG_CONFIG_HOME":str(Path(td)/"xdg")}
            env.pop("PROJECTWRIGHT_CONFIG_DIR",None)
            env.pop("HERMES_PROJECT_CONFIG_DIR",None)
            messages=[]
            for module in ("project_notes_sync","pw_notes_sync"):
                proc=subprocess.run([sys.executable,"-B","-m",module,
                                     "--project","fixture","--status"],
                                    env={**env,"PYTHONPATH":str(SRC)},
                                    text=True,capture_output=True)
                self.assertNotEqual(proc.returncode,0)
                messages.append(proc.stderr)
            self.assertIn(str(Path(td)/"xdg/projectwright/projects/fixture/config.json"),messages[0])
            self.assertIn(str(Path(td)/"xdg/projectwright/projects/fixture/config.json"),messages[1])

if __name__=="__main__":
    unittest.main()
