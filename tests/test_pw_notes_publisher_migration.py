"""Canonical notes publishing preserves legacy API and safe default."""
import importlib
import sys
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/"src"/"projectwright"
if str(SRC) not in sys.path:sys.path.insert(0,str(SRC))

class NotesPublisherMigration(unittest.TestCase):
    def test_legacy_aliases_are_canonical(self):
        old=importlib.import_module("project_notes_publisher")
        new=importlib.import_module("pw_notes_publisher")
        for name in ("publish","render","atomic_write","main"):
            self.assertIs(getattr(old,name),getattr(new,name))
    def test_unconfigured_publishing_is_disabled(self):
        new=importlib.import_module("pw_notes_publisher")
        self.assertIsNone(new.publish({"notes":{"enabled":False}},Path("/nonexistent/config.json")))

if __name__=="__main__":unittest.main()
