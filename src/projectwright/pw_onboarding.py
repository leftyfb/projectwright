"""Small, fail-closed interactive onboarding actions for the pw CLI."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from pw_dispatch import default_project_root

PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
RESERVED_REQUIREMENTS_NAMES = {
    "config.json", "config.json.tmp", "queue.md", "work_log.md", "worker_state.json",
    "worker_journal.json", "worker.lock", "git_cycle.json", "recovery_incidents.json",
    "planning_state.json", "telegram_approval_pending.json",
}


def _project_dir(project: str) -> Path:
    if not PROJECT_ID.fullmatch(project):
        raise ValueError("Invalid project ID")
    return default_project_root() / project


def _config(project: str) -> tuple[Path, dict]:
    directory = _project_dir(project)
    path = directory / "config.json"
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("Refusing symlink project state")
    if not path.is_file():
        raise ValueError(f"Project {project!r} is not initialized. Run: pw init --project {project}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid project configuration {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("id") != project:
        raise ValueError(f"Malformed or mismatched project configuration: {path}")
    for section in ("planning", "execution"):
        if section in data and not isinstance(data[section], dict):
            raise ValueError(f"Malformed configuration: {section} must be an object")
    return path, data


def _requirements_path(project: str, config: dict) -> Path:
    base = _project_dir(project).resolve()
    raw = config.get("planning", {}).get("requirements_file") or "requirements.md"
    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = base / target
    target = target.resolve()
    if target.parent != base:
        raise ValueError("Requirements file must be within this Projectwright project directory")
    if target.name in RESERVED_REQUIREMENTS_NAMES:
        raise ValueError(f"Requirements file cannot replace reserved Projectwright state file: {target.name}")
    return target


def _write(path: Path, config: dict) -> None:
    # Preserve file permissions and avoid truncating a config on serialization failure.
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.chmod(path.stat().st_mode & 0o777)
    os.replace(temp, path)


def requirements(project: str) -> int:
    path, config = _config(project)
    target = _requirements_path(project, config)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(mode=0o600, exist_ok=True)
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        command = shlex.split(editor)
        if not command:
            raise ValueError("VISUAL/EDITOR is empty")
    else:
        selected = next((x for x in ("nano", "vi", "vim", "editor") if shutil.which(x)), None)
        if selected is None:
            raise ValueError("No editor found. Set VISUAL or EDITOR, for example: export EDITOR=nano")
        command = [selected]
    try:
        return subprocess.run([*command, str(target)], check=False).returncode
    except FileNotFoundError as exc:
        raise ValueError(f"Editor not found: {command[0]}. Set VISUAL or EDITOR") from exc


def authorize_planning(project: str) -> int:
    config_path, config = _config(project)
    requirements = _requirements_path(project, config)
    if not requirements.is_file():
        print("Requirements are missing. Create them with: pw requirements --project " + project + " --edit", file=sys.stderr)
        return 2
    planning = config.setdefault("planning", {})
    planning["enabled"] = True  # invoking pw plan is explicit planning authorization only
    _write(config_path, config)
    cmd = [sys.executable, "-B", "-m", "pw_queue_manager", "--project", project, "--once"]
    return subprocess.run(cmd, check=False).returncode


def start(project: str, confirmed: bool) -> int:
    path, config = _config(project)
    if not confirmed:
        if not sys.stdin.isatty():
            print("Execution authorization required. Review the queue, then rerun: pw start --project " + project + " --yes", file=sys.stderr)
            return 2
        answer = input(f"Persistently enable execution for {project!r} and run one manual worker task? Existing timers may use this authorization. [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Execution remains disabled.")
            return 1
    execution = config.setdefault("execution", {})
    execution["enabled"] = True
    _write(path, config)
    cmd = [sys.executable, "-B", "-m", "pw_task_worker", "--project", project, "--once"]
    return subprocess.run(cmd, check=False, env={**os.environ, "PROJECTWRIGHT_DISPATCHED": "1"}).returncode


def status(project: str, as_json: bool) -> int:
    project_dir = _project_dir(project)
    cmd = [sys.executable, "-B", "-m", "pw_queue_manager", "--project", project, "--status"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(result.stdout, end="")
        return result.returncode
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return result.returncode
    config_path = project_dir / "config.json"
    if project_dir.is_symlink() or config_path.is_symlink():
        raise ValueError("Refusing symlink project state")
    if config_path.exists() and not config_path.is_file():
        raise ValueError(f"Malformed project configuration: {config_path}")
    initialized = config_path.is_file()
    cfg = _config(project)[1] if initialized else {}
    print(f"Project: {project}")
    print(f"Planning: {'enabled' if cfg.get('planning', {}).get('enabled') else 'disabled'}")
    print(f"Execution: {'enabled' if cfg.get('execution', {}).get('enabled') else 'disabled'}")
    for key, label in (("pending", "Queue pending"), ("completed", "Queue completed"), ("queue_blocked", "Queue blocked")):
        if key in report:
            print(f"{label}: {report[key]}")
    print(f"Current activity: {report.get('decision', 'unknown')} — {report.get('reason', 'no further detail')}")
    blockers = report.get("blockers", [])
    print("Blockers: " + (", ".join(blockers) if blockers else "none reported"))
    if not initialized:
        next_action = f"Initialize managed onboarding against an existing Git repository: pw init --project {project} --repo /path/to/repository"
    elif not cfg.get("planning", {}).get("enabled"):
        next_action = f"Review requirements, then authorize planning with: pw plan --project {project}"
    elif not cfg.get("execution", {}).get("enabled"):
        next_action = f"Review the approved queue, then authorize a manual worker run with: pw start --project {project}"
    else:
        next_action = f"Review results and Git changes; run another manual step with: pw start --project {project}"
    print("Next action: " + next_action)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "requirements", "start", "status"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--config-dir", type=Path, help="Configuration home (contains projects/)")
    parser.add_argument("--edit", action="store_true", help="Open requirements in an editor")
    parser.add_argument("--yes", action="store_true", help="Explicitly confirm execution authorization and one manual task")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON status")
    args = parser.parse_args()
    if args.config_dir:
        if not args.config_dir.is_absolute():
            parser.error("--config-dir must be absolute")
        os.environ["PROJECTWRIGHT_CONFIG_DIR"] = str(args.config_dir)
    try:
        if args.action == "plan":
            return authorize_planning(args.project)
        if args.action == "requirements":
            if not args.edit:
                parser.error("use --edit to open the requirements file")
            return requirements(args.project)
        if args.action == "start":
            return start(args.project, args.yes)
        return status(args.project, args.json)
    except (ValueError, OSError) as exc:
        print(f"pw {args.action}: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
