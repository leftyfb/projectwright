"""Explicit, non-destructive migration from legacy external Projectwright state.

Dry-run by default. No automatic package-upgrade migrations or service changes.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from pw_dispatch import default_project_root
from pw_embedded import ID, initialize, register, _git_root

FILES = ("requirements.md", "queue.md", "work_log.md")
ROOT_PATHS = {
    "base": ".", "queue": "queue.md", "work_log": "work_log.md",
    "worktree": "..", "lock": "state/worker.lock",
    "run_log": "logs/worker.log", "result_dir": "results",
    "cycle_file": "state/git_cycle.json",
    "worker_journal_file": "state/worker_journal.json",
}
PRIVATE_NAMES = ("worker.lock", ".worker.lock", ".telegram_notify.lock")
SENSITIVE = ("password", "secret", "token", "api_key", "credential", "private_key")


def _no_secrets(value, location="config"):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Invalid legacy configuration key")
            if any(word in key.lower() for word in SENSITIVE):
                raise ValueError(f"Potential credential field in legacy {location}.{key}")
            _no_secrets(item, location + "." + key)
    elif isinstance(value, list):
        for item in value:
            _no_secrets(item, location)


def inspect(project: str, root: Path, repo: Path) -> dict:
    """Validate before any changes. Never migrate active/uncertain state."""
    if not ID.fullmatch(project) or repo.name != project:
        raise ValueError("Project and repository basenames must match")
    legacy = root / project
    if legacy.is_symlink() or not legacy.is_dir():
        raise ValueError("Legacy state directory missing or symlinked")
    config_path = legacy / "config.json"
    if not config_path.is_file() or config_path.is_symlink():
        raise ValueError("Legacy config.json is missing or symlinked")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or cfg.get("id") != project or cfg.get("layout") == "embedded":
        raise ValueError("Not a matching legacy project")
    _no_secrets(cfg)
    if not repo.is_dir() or repo.is_symlink() or _git_root(repo) != repo:
        raise ValueError("Target must be an existing Git repository root")
    if (repo / ".pw").exists() or (repo / ".pw").is_symlink():
        raise ValueError("Target already has Projectwright state")
    configured_worktree = Path(cfg.get("worktree", legacy / "worktree")).expanduser().resolve()
    if configured_worktree != repo.resolve():
        raise ValueError("Legacy worktree does not match requested repository")
    branch = subprocess.check_output(
        ["git", "-C", str(repo), "branch", "--show-current"], text=True).strip()
    if not branch or branch != cfg.get("branch", "main"):
        raise ValueError("Target Git branch is not the configured branch")
    subprocess.check_output(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"])
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"]).strip():
        raise ValueError("Target repository must be clean")
    # An active Git transaction or unfinished worker cannot be copied safely.
    cycle = Path(cfg.get("cycle_file", legacy / "git_cycle.json")).expanduser()
    if cycle.exists() or (legacy / "git_cycle.json").exists():
        raise ValueError("Active or unresolved Git cycle; recover before migration")
    journal = Path(cfg.get("worker_journal_file", legacy / "worker_journal.json")).expanduser()
    if journal.exists():
        state = json.loads(journal.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("current_task") is not None:
            raise ValueError("Unresolved worker journal")
    if (legacy / "telegram_approval_pending.json").exists():
        raise ValueError("Pending Telegram approval must be resolved before migration")
    for key, name in ROOT_PATHS.items():
        if key in cfg:
            existing = Path(cfg[key]).expanduser()
            if key == "worktree":
                continue
            # Custom external paths need manual review; refuse to guess mappings.
            expected = legacy if key == "base" else legacy / {
                "lock": "worker.lock", "run_log": "worker.log",
                "result_dir": "results", "cycle_file": "git_cycle.json",
                "worker_journal_file": "worker_journal.json",
            }.get(key, name)
            if existing.resolve() != expected.resolve():
                raise ValueError(f"Custom {key} path requires manual migration review")
    requirements = cfg.get("planning", {}).get("requirements_file")
    if requirements is not None and Path(requirements).expanduser().resolve() != (legacy / "requirements.md").resolve():
        raise ValueError("Custom requirements path requires manual review")
    # Reject symlinks/special files anywhere: do not follow them into the target.
    files = []
    for item in legacy.rglob("*"):
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            raise ValueError(f"Unsupported legacy entry: {item.relative_to(legacy)}")
        if item.is_file() and item.name not in PRIVATE_NAMES and item.name != "config.json":
            if item.name.startswith(".env") or "secret" in item.name.lower():
                raise ValueError("Sensitive legacy file requires manual review")
            files.append(item.relative_to(legacy).as_posix())
    return {"project": project, "source": str(legacy), "repository": str(repo),
            "files": sorted(files), "execution_enabled_after": False,
            "requires_manual_timer_reconfiguration": True}


def migrate(project: str, root: Path, repo: Path, *, apply=False) -> dict:
    report = inspect(project, root, repo)
    if not apply:
        return {"decision": "dry_run", **report}
    legacy = root / project
    original = json.loads((legacy / "config.json").read_text(encoding="utf-8"))
    # Initialization first installs a Git ignore policy, before any state moves.
    config_file = initialize(repo, shared=False)
    marker = config_file.parent
    for name in report["files"]:
        source = legacy / name
        if name in FILES:
            target = marker / name
        elif name == "worker.log":
            target = marker / "logs" / "worker.log"
        elif name == "worker_journal.json":
            target = marker / "state" / "worker_journal.json"
        elif name.startswith("results/"):
            target = marker / name
        else:
            target = marker / name
        if target.exists() and name not in FILES:
            raise ValueError(f"Migration destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
        target.chmod(0o600)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    for key, value in original.items():
        if key not in ROOT_PATHS and key not in ("id", "layout", "projectwright_initialized",
                                                "planning", "execution"):
            config[key] = value
    config["planning"] = {**original.get("planning", {}), "enabled": False,
                          "requirements_file": "requirements.md"}
    config["execution"] = {**original.get("execution", {}), "enabled": False}
    # Old project remains the rollback copy and old schedules are NOT changed.
    config_file.write_text(json.dumps(config, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    config_file.chmod(0o600)
    register(repo)
    return {"decision": "copied_disabled", **report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--legacy-root", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="Explicitly copy into a previously uninitialized repo")
    args = parser.parse_args()
    root = (args.legacy_root or default_project_root()).expanduser().resolve()
    repo = args.repo.expanduser().resolve()
    try:
        report = migrate(args.project, root, repo, apply=args.apply)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
