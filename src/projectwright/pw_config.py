"""Built-in Projectwright project defaults; config.json is optional."""
from __future__ import annotations

import json
import re
from pathlib import Path
from pw_dispatch import default_project_root

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def load(project: str, root: Path | None = None) -> tuple[Path, dict]:
    if not _ID.fullmatch(project):
        raise ValueError("Invalid project ID")
    root = Path(root) if root is not None else default_project_root()
    directory = root / project
    path = directory / "config.json"
    overrides = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(overrides, dict):
        raise ValueError("Project configuration must be an object")
    if overrides.get("id", project) != project:
        raise ValueError("Project configuration ID mismatch")
    defaults = {
        "id": project,
        "base": str(directory),
        "queue": str(directory / "queue.md"),
        "work_log": str(directory / "work_log.md"),
        "lock": str(directory / "worker.lock"),
        "run_log": str(directory / "worker.log"),
        "result_dir": str(directory / "results"),
        "cycle_file": str(directory / "git_cycle.json"),
        "worker_journal_file": str(directory / "worker_journal.json"),
        "timeout_seconds": 900,
        "hermes": "hermes",
        "planning": {"enabled": False},
        "notes": {"enabled": False},
        "execution": {"enabled": False},
    }
    result = {**defaults, **overrides}
    for section in ("planning", "notes", "execution"):
        if isinstance(overrides.get(section), dict):
            result[section] = {**defaults[section], **overrides[section]}
    return path, result
