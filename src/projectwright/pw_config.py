"""Built-in Projectwright project defaults; config.json is optional."""
from __future__ import annotations

import json
import os
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
        "worktree": str(directory / "worktree"),
        "branch": "main",
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
    for section in ("planning", "notes", "execution"):
        supplied = overrides.get(section)
        if supplied is not None and not isinstance(supplied, dict):
            raise ValueError(f"{section} configuration must be an object")
        if isinstance(supplied, dict) and "enabled" in supplied and type(supplied["enabled"]) is not bool:
            raise ValueError(f"{section}.enabled must be boolean")
    result = {**defaults, **overrides}
    for section in ("planning", "notes", "execution"):
        if isinstance(overrides.get(section), dict):
            result[section] = {**defaults[section], **overrides[section]}
    # Explicit process environment overrides are optional. Never resolve a
    # relative repository against an unspecified working directory.
    selected = os.environ.get("PROJECTWRIGHT_WORKTREE")
    if selected is not None:
        if not selected or not Path(selected).expanduser().is_absolute():
            raise ValueError("PROJECTWRIGHT_WORKTREE must be an absolute path")
        result["worktree"] = str(Path(selected).expanduser())
    branch = os.environ.get("PROJECTWRIGHT_BRANCH")
    if branch is not None:
        if not branch or branch.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_./-]+", branch) or ".." in branch or branch.endswith("/"):
            raise ValueError("Invalid PROJECTWRIGHT_BRANCH")
        result["branch"] = branch
    return path, result
