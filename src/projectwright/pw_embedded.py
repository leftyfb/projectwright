"""Embedded Projectwright repositories: inert initialization and safe discovery.

Legacy external project state is intentionally not migrated here.
"""
from __future__ import annotations

import fcntl
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
    "!/.pw/queue.md\n", "!/.pw/config.json\n",
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
            if not (parent / ".git").exists():
                raise ValueError("Embedded .pw exists outside a repository root")
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
    requested = path.expanduser()
    if requested.is_symlink():
        raise ValueError("Refusing symlinked repository path")
    target = requested.resolve()
    project = target.name
    if not ID.fullmatch(project):
        raise ValueError("Repository basename must be a valid project ID")
    if target.is_symlink():
        raise ValueError("Refusing symlinked repository path")
    if target.exists() and not target.is_dir():
        raise ValueError("Project destination is not a directory")
    if target.exists() and (target / ".pw").exists():
        raise FileExistsError("Projectwright project already exists")
    existing_parent = next((parent for parent in (target, *target.parents)
                            if parent.exists() and parent.is_dir()), None)
    top = _git_root(existing_parent) if existing_parent else None
    if top is not None and top != target:
        raise ValueError("Must initialize at a Git repository root, not inside another repository")
    if not target.exists():
        target.mkdir(parents=True)
    if top is None:
        subprocess.run(["git", "-C", str(target), "init", "-b", "main"],
                       check=True, capture_output=True, text=True)
    marker = target / ".pw"
    marker.mkdir(mode=0o700)
    try:
        branch = subprocess.run(
            ["git", "-C", str(target), "branch", "--show-current"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        if not branch:
            raise ValueError("Detached Git HEAD is not supported")
        for name in ("state", "logs", "results"):
            (marker / name).mkdir(mode=0o700)
        config = {
            "id": project, "layout": "embedded", "projectwright_initialized": 1,
            "branch": branch,
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
        if shared and "/.pw/" in previous.splitlines():
            raise ValueError("Existing /.pw/ ignore rule conflicts with shared mode")
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

def directory(project: str, root: Path) -> Path:
    """Return selected project state directory; preserve legacy root semantics."""
    selected = os.environ.get("PROJECTWRIGHT_PROJECT_DIR")
    if selected:
        repo = Path(selected).expanduser()
        if not repo.is_absolute() or repo.name != project:
            raise ValueError("Explicit embedded repository must be absolute and match project ID")
        state = repo / ".pw"
        if state.is_symlink() or not (state / "config.json").is_file():
            raise ValueError("Embedded project state missing or symlinked")
        return state
    found = discover(Path.cwd()) if root == (Path.home() / "projects") else None
    if found is not None:
        if found.parent.name != project:
            raise ValueError("Project ID does not match current repository")
        return found
    return root / project


def registry_path() -> Path:
    return Path.home() / ".config" / "projectwright" / "registry.json"


def registered_projects(path: Path | None = None) -> list[Path]:
    """Read registered .pw directories; reject forged/corrupt registry entries."""
    path = path or registry_path()
    if path.is_symlink():
        raise ValueError("Refusing symlinked project registry")
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("repositories"), list):
        raise ValueError("Invalid Projectwright registry")
    result = []
    for raw in data["repositories"]:
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise ValueError("Invalid registry repository path")
        repo = Path(raw)
        if repo.is_symlink():
            raise ValueError("Symlinked registered repository")
        marker = repo / ".pw"
        if marker.is_symlink():
            raise ValueError("Symlinked registered .pw")
        if marker.is_dir():
            data_file = marker / "config.json"
            if not data_file.is_file() or data_file.is_symlink():
                raise ValueError("Invalid registered project")
            config = json.loads(data_file.read_text(encoding="utf-8"))
            if config.get("layout") != "embedded" or config.get("id") != repo.name:
                raise ValueError("Registered project identity mismatch")
            result.append(marker)
        # Missing/moved repositories are inert until explicitly registered again.
    if len(set(result)) != len(result):
        raise ValueError("Duplicate registry paths")
    return result


def register(repo: Path, path: Path | None = None) -> None:
    """Record arbitrary repository location outside Git; idempotent and locked."""
    repo = repo.expanduser().resolve()
    marker = repo / ".pw"
    if marker not in registered_projects_for_registration(repo):
        raise ValueError("Not an initialized embedded repository")
    path = path or registry_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Refusing symlinked project registry")
    lock = path.with_suffix(".lock")
    if lock.is_symlink():
        raise ValueError("Refusing symlinked registry lock")
    with lock.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        existing = registered_projects(path)
        locations = sorted({str(m.parent) for m in existing} | {str(repo)})
        temp = path.with_name(path.name + ".tmp")
        if temp.is_symlink():
            raise ValueError("Refusing symlinked registry temporary file")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump({"version": 1, "repositories": locations}, out, indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def registered_projects_for_registration(repo: Path) -> list[Path]:
    marker = repo / ".pw"
    if marker.is_symlink() or not (marker / "config.json").is_file():
        return []
    cfg = json.loads((marker / "config.json").read_text(encoding="utf-8"))
    if cfg.get("id") != repo.name or cfg.get("layout") != "embedded":
        return []
    if _git_root(repo) != repo:
        return []
    return [marker]


def projects_for_name(project: str, root: Path) -> list[Path]:
    """Return all matching legacy and registered projects; fail on ambiguity."""
    if not ID.fullmatch(project):
        raise ValueError("Invalid project ID")
    selected = [m for m in registered_projects() if m.parent.name == project]
    legacy = root / project
    if (legacy / "config.json").is_file():
        selected.append(legacy)
    return selected


def callback_project(root: Path, project: str, request: str) -> Path:
    """Resolve a callback by pinned record hash; refuse ambiguous matches."""
    import hashlib
    matches = []
    for marker in projects_for_name(project, root):
        pending = marker / "telegram_approval_pending.json"
        if pending.is_file() and not pending.is_symlink():
            raw = json.loads(pending.read_text(encoding="utf-8"))
            canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            if hashlib.sha256(canonical).hexdigest()[:20] == request:
                matches.append(marker)
    if len(matches) != 1:
        raise ValueError("Stale or ambiguous Projectwright callback")
    return matches[0]

def project_id(directory: Path) -> str:
    return directory.parent.name if directory.name == ".pw" else directory.name


def state_directories(root: Path) -> list[Path]:
    legacy = ([p for p in root.iterdir()
               if p.is_dir() and ID.fullmatch(p.name) and (p / "config.json").is_file()]
              if root.is_dir() else [])
    return sorted(legacy + registered_projects(), key=lambda p: str(p))
