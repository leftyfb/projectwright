"""Safely initialize an inert Projectwright project without enabling execution."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from pw_dispatch import default_project_root

PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def initialize(project: str, root: Path, *, no_config: bool = False, repo: Path | None = None) -> Path:
    if not PROJECT_ID.fullmatch(project):
        raise ValueError("Invalid project ID")
    root = root.expanduser()
    git_repo = None
    git_branch = None
    if repo is not None:
        repo = repo.expanduser().resolve()
        if not repo.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo}")
        try:
            top = Path(subprocess.check_output(
                ['git', '-C', str(repo), 'rev-parse', '--show-toplevel'], text=True,
                stderr=subprocess.PIPE).strip()).resolve()
            git_branch = subprocess.check_output(
                ['git', '-C', str(repo), 'branch', '--show-current'], text=True,
                stderr=subprocess.PIPE).strip()
            subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--verify', 'HEAD'], stderr=subprocess.PIPE)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError(f"Not an initialized Git worktree with a HEAD commit: {repo}") from exc
        if top != repo or not git_branch:
            raise ValueError(f"Path must be the root of a Git worktree on a named branch: {repo}")
        git_repo = str(repo)
    directory = root / project
    if root.is_symlink() or directory.is_symlink():
        raise ValueError("Refusing symlink project path")
    if directory.exists():
        raise FileExistsError(f"Project directory already exists: {directory}")
    root.mkdir(parents=True, exist_ok=True)
    # Exclusive directory creation prevents reusing an existing project.
    directory.mkdir(mode=0o700)
    if no_config:
        created = []
        try:
            for name in ("queue.md", "work_log.md"):
                target = directory / name
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created.append(target)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write("")
            return directory
        except BaseException:
            for target in created:
                target.unlink(missing_ok=True)
            directory.rmdir()
            raise
    doc = {
        "id": project,
        "projectwright_initialized": 1,
        "execution": {"enabled": False},
        "planning": {"enabled": False},
        "notes": {"enabled": False},
    }
    if git_repo is not None:
        doc["worktree"] = git_repo
        doc["branch"] = git_branch
    target = directory / "config.json"
    created = []
    try:
        for name in ("queue.md", "work_log.md"):
            state_file = directory / name
            fd = os.open(state_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(state_file)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(target, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        for created_file in created:
            created_file.unlink(missing_ok=True)
        if target.exists():
            target.unlink()
        directory.rmdir()
        raise
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--config-dir", type=Path, help="Absolute Projectwright configuration home")
    parser.add_argument("--no-config", action="store_true", help="Create empty queue and work log without config.json")
    parser.add_argument("--repo", type=Path, help="Existing Git worktree to connect (never initialized or modified)")
    args = parser.parse_args()
    if args.config_dir is not None and not args.config_dir.is_absolute():
        parser.error("--config-dir must be absolute")
    if args.no_config and args.repo is not None:
        parser.error("--repo requires a project config; remove --no-config")
    root = args.config_dir / "projects" if args.config_dir is not None else default_project_root()
    try:
        output = initialize(args.project, root, no_config=args.no_config, repo=args.repo)
    except (ValueError, FileExistsError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"project": args.project,
                      "config": None if args.no_config else str(output),
                      "project_directory": str(root / args.project),
                      "decision": "disabled"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
