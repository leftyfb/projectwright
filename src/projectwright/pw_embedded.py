"""Embedded Projectwright repositories: inert initialization and safe discovery.

Legacy external project state is intentionally not migrated here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
README = """# Projectwright project metadata

This directory is managed by [Projectwright](https://github.com/leftyfb/projectwright).

Human-editable project definitions: `requirements.md`, `queue.md`, and
`config.json` (do not add secrets). `work_log.md` records task progress
and is generally maintained by Projectwright.

Machine-managed: `state/`, `logs/`, and `results/`. Do not edit
these during execution. They must never be committed.

Common commands: `pw status --project PROJECT`,
`pw requirements --project PROJECT --edit`, `pw plan --project PROJECT`,
and `pw start --project PROJECT`. Planning and execution are disabled
until explicitly authorized.
"""
EXCLUDE = ("/.pw/\n",)
SHARED_EXCLUDE = (
    "/.pw/*\n", "!/.pw/README.md\n", "!/.pw/requirements.md\n",
    "!/.pw/queue.md\n", "!/.pw/config.json\n", "!/.pw/work_log.md\n",
    "/.pw/state/\n", "/.pw/logs/\n", "/.pw/results/\n",
)


def discover(start: Path) -> Path | None:
    """Find an embedded project, stopping at its repository boundary."""
    here = start.expanduser().resolve()
    if here.is_file():
        here = here.parent
    for parent in (here, *here.parents):
        marker = parent / ".pw"
        if marker.is_symlink():
            raise ValueError("Refusing symlinked .pw directory")
        if (marker / "config.json").is_file():
            return marker
        # An enclosing repository is authoritative: do not discover another
        # repository's parent project.
        if (parent / ".git").exists():
            return None
    return None


def _git_root(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        text=True, capture_output=True, check=False,
    )
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve()


def initialize(path: Path, *, shared: bool = False) -> Path:
    """Initialize .pw in an existing worktree or a newly created repository.

    Never modify an existing .pw, never authorize execution, and never
    overwrite an existing .gitignore.
    """
    target = path.expanduser().resolve()
    project = target.name
    if not ID.fullmatch(project):
        raise ValueError("Repository basename must be a valid project ID")
    if target.is_symlink():
        raise ValueError("Refusing symlinked repository path")
    if target.exists() and not target.is_dir():
        raise ValueError("Project destination is not a directory")
    if target.exists() and (target / ".pw").exists():
        raise FileExistsError("Projectwright project already exists")
    if target.exists():
        top = _git_root(target)
        if top is not None and top != target:
            raise ValueError("Must initialize at a Git repository root")
    else:
        target.mkdir(parents=True)
    if _git_root(target) is None:
        subprocess.run(["git", "-C", str(target), "init", "-b", "main"],
                       check=True, capture_output=True, text=True)
    marker = target / ".pw"
    marker.mkdir(mode=0o700)
    try:
        for name in ("state", "logs", "results"):
            (marker / name).mkdir(mode=0o700)
        config = {
            "id": project, "layout": "embedded", "projectwright_initialized": 1,
            "base": ".", "queue": "queue.md", "work_log": "work_log.md",
            "worktree": "..", "lock": "state/worker.lock",
            "run_log": "logs/worker.log", "result_dir": "results",
            "cycle_file": "state/git_cycle.json",
            "worker_journal_file": "state/worker_journal.json",
            "planning": {"enabled": False, "requirements_file": "requirements.md"},
            "execution": {"enabled": False}, "notes": {"enabled": False},
            "quota": {"enabled": False},
        }
        for name, contents in {
            "README.md": README, "config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            "requirements.md": "", "queue.md": "", "work_log.md": "",
        }.items():
            file = marker / name
            fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(contents)
        ignore = target / ".gitignore"
        if ignore.is_symlink():
            raise ValueError("Refusing symlinked .gitignore")
        previous = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
        entries = SHARED_EXCLUDE if shared else EXCLUDE
        # Only append the requested policy, avoiding duplicate identical rules.
        with ignore.open("a", encoding="utf-8") as handle:
            if previous and not previous.endswith("\n"):
                handle.write("\n")
            for line in entries:
                if line.strip() not in previous.splitlines():
                    handle.write(line)
    except BaseException:
        # Do not remove a user's repository or pre-existing .gitignore.
        # Leave the initialized .pw for investigation rather than risk deleting
        # unexpected files created by concurrent operations.
        raise
    return marker / "config.json"
