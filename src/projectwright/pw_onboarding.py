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
import tempfile

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
    from pw_embedded import directory
    return directory(project, default_project_root())


def _config(project: str) -> tuple[Path, dict]:
    directory = _project_dir(project)
    path = directory / "config.json"
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("Refusing symlink project state")
    if not path.is_file():
        raise ValueError(f"Project {project!r} is not initialized. Run: pw init PATH")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid project configuration {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("id") != project:
        raise ValueError(f"Malformed or mismatched project configuration: {path}")
    for section in ("planning", "execution"):
        if section in data and not isinstance(data[section], dict):
            raise ValueError(f"Malformed configuration: {section} must be an object")
    # Read the effective configuration for validation, but return the raw
    # document so relative paths are never rewritten as machine-specific ones.
    from pw_config import load as validate_config
    validate_config(project, directory_override=directory)
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
    # Use an unpredictable private sibling, never a deterministic config.json.tmp.
    # Serialize before opening the temporary file to preserve the original.
    contents = json.dumps(config, indent=2, sort_keys=True) + "\n"
    fd, name = tempfile.mkstemp(prefix=".pw-config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


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
    from pw_milestone_guard import validate_requirements
    diagnostics = validate_requirements(
        requirements.read_text(encoding="utf-8"),
        strict=config.get("planning", {}).get("milestone_sequence") == "strict",
        project_dir=config_path.parent)["issues"]
    if diagnostics:
        print("pw plan: requirements validation failed; planning remains disabled", file=sys.stderr)
        for item in diagnostics:
            if isinstance(item, dict) and item.get("message"):
                location = ""
                if item.get("milestone"):
                    location = f" (requirement {item.get('requirement', 'unknown')}, milestone {item['milestone']})"
                print(f"  -{location} {item['message']}", file=sys.stderr)
        return 2
    planning = config.setdefault("planning", {})
    planning["enabled"] = True  # invoking pw plan is explicit planning authorization only
    _write(config_path, config)
    cmd = [sys.executable, "-B", "-m", "pw_queue_manager", "--project", project, "--once"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode:
        # A normal successful planner run needs no diagnostics. Keep
        # failure/no-op output parsing inside the nonzero return path.
        detail = (result.stdout or "").strip()
        try:
            payload = json.loads(detail)
        except (TypeError, json.JSONDecodeError):
            payload = None
        # The manager intentionally exits 3 for a healthy no-op.
        # Preserve its machine-readable contract while making the
        # interactive pw plan command report success.
        if result.returncode == 3 and isinstance(payload, dict) and (
                payload.get("project") == project and payload.get("decision") == "no_op"):
            reason = payload.get("reason") or "Queue already has enough work"
            print(f"pw plan: No planning needed — {reason}")
            return 0
        if isinstance(payload, dict):
            reason = payload.get("reason") or "Planning was blocked"
            blockers = payload.get("blockers") or []
            suffix = f" ({', '.join(str(x) for x in blockers)})" if blockers else ""
            print(f"pw plan: {reason}{suffix}", file=sys.stderr)
            for item in payload.get("diagnostics") or []:
                if isinstance(item, dict) and item.get("message"):
                    print(f"  - {item['message']}", file=sys.stderr)
        elif result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    return result.returncode


def start(project: str, confirmed: bool) -> int:
    _path, config = _config(project)
    if not confirmed:
        if not sys.stdin.isatty():
            print("One-task execution requires confirmation. Review the queue, then rerun: pw start --project " + project + " --yes", file=sys.stderr)
            return 2
        answer = input(f"Authorize one manual task for {project!r}? Persistent execution settings will not be changed. [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("No task was authorized; project settings are unchanged.")
            return 1
    # run_tick is the supported manager/dispatcher path; it authorizes at most
    # one worker task and preserves locks, quota, sequencing, and recovery gates.
    scripts = Path(__file__).resolve().parent / "pw_dispatch.py"
    cmd = [sys.executable, "-B", str(scripts), "--project", project, "--one-shot"]
    return subprocess.run(cmd, check=False).returncode


def authorize_persistent_execution(project: str, confirmed: bool) -> int:
    path, config = _config(project)
    if not confirmed:
        print("Persistent execution requires explicit confirmation; rerun with --yes", file=sys.stderr)
        return 2
    config.setdefault("execution", {})["enabled"] = True
    _write(path, config)
    print(f"Persistent execution enabled for {project}; configure recurring runs separately with pw timer.")
    return 0


def _recurring_state(project: str) -> tuple[bool | None, bool | None]:
    from pw_project_timer import unit_name
    directory = _project_dir(project)
    repo = directory.parent if directory.name == ".pw" else None
    unit = unit_name(project, repo) + ".timer"
    unit_path = Path.home() / ".config/systemd/user" / unit
    if unit_path.is_symlink():
        return None, None
    if not unit_path.is_file():
        return False, False
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True, None
    state = (result.stdout or "").strip()
    if result.returncode == 0:
        return True, True
    if state == "disabled":
        return True, False
    return True, None


def status(project: str, as_json: bool) -> int:
    project_dir = _project_dir(project)
    cmd = [sys.executable, "-B", "-m", "pw_queue_manager", "--project", project, "--status"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    manager_error = (result.stderr or result.stdout or "").strip()
    try:
        report = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        report = {}
        manager_status_unavailable = True
    else:
        manager_status_unavailable = not isinstance(report, dict) or not report
    if not isinstance(report, dict):
        report = {}
    if not report:
        report = {
            "project": project,
            "decision": "unknown",
            "reason": "Manager status unavailable",
            "pending": None,
            "completed": None,
            "queue_blocked": None,
            "blockers": [manager_error] if manager_error else ["Manager status unavailable"],
        }
    else:
        report.setdefault("project", project)
        report.setdefault("decision", "unknown")
        if not isinstance(report.get("decision"), str) or not report["decision"]:
            report["decision"] = "unknown"
        report.setdefault("reason", "unknown")
        if report["project"] != project:
            report.update(project=project, decision="unknown", reason="Manager project identity mismatch",
                          pending=None, completed=None, queue_blocked=None,
                          blockers=["Manager project identity mismatch"])
        if not isinstance(report.get("reason"), str):
            report["reason"] = "unknown"
        for key in ("pending", "completed", "queue_blocked"):
            value = report.get(key)
            if type(value) is not int or value < 0:
                report[key] = None
        if not isinstance(report.get("blockers"), list) or any(not isinstance(item, str) for item in report["blockers"]):
            report["blockers"] = ["Manager returned invalid blocker data"]
    if project_dir.is_symlink():
        raise ValueError("Refusing symlink project state")
    config_path = project_dir / "config.json"
    if config_path.is_symlink():
        raise ValueError("Refusing symlink project state")
    if config_path.exists() and not config_path.is_file():
        raise ValueError(f"Malformed project configuration: {config_path}")
    initialized = config_path.is_file()
    cfg = _config(project)[1] if initialized else {}
    effective_cfg = None
    effective_path = None
    if initialized:
        from pw_config import load as load_config
        effective_path, effective_cfg = load_config(project, directory_override=project_dir)
    planning_enabled = cfg.get("planning", {}).get("enabled") if initialized else False
    execution_enabled = cfg.get("execution", {}).get("enabled") if initialized else False
    recurring_configured, recurring_enabled = _recurring_state(project)
    display_worktree = cfg.get("worktree") if initialized else None
    if initialized and cfg.get("layout") == "embedded" and isinstance(display_worktree, str):
        display_worktree = str((project_dir / display_worktree).resolve())
    report.update({
        "initialized": initialized,
        "worktree": display_worktree,
        "planning_enabled": planning_enabled if isinstance(planning_enabled, bool) else None,
        "execution_enabled": execution_enabled if isinstance(execution_enabled, bool) else None,
        "recurring_execution_configured": recurring_configured,
        "recurring_execution_enabled": recurring_enabled,
        "recurring_execution": (
            "enabled" if recurring_enabled is True else
            "disabled" if recurring_configured is True and recurring_enabled is False else
            "not_configured" if recurring_configured is False else "unknown"
        ),
    })
    # Read the canonical effective journal path, which for embedded projects
    # is usually .pw/state/worker_journal.json (not .pw/worker_journal.json).
    report["current_task"] = None
    if effective_cfg is not None:
        from pw_worker_journal import journal_path
        try:
            journal = json.loads(journal_path(effective_cfg, effective_path).read_text(encoding="utf-8"))
            current_task = journal.get("current_task")
            if isinstance(current_task, dict):
                report["current_task"] = current_task
        except (OSError, ValueError, RuntimeError):
            # Preserve the manager's real blocked state; do not invent an
            # active task when the journal is unreadable or absent.
            pass

    if report.get("decision") == "busy":
        # The lock is expected when an unattended worker or planner is active.
        # A busy manager returns no queue counts or blockers, so report a
        # read-only queue snapshot rather than calling missing data an error.
        report["blockers"] = []
        if effective_cfg is not None:
            from pw_queue_manager import queue_summary
            try:
                queue_path = Path(effective_cfg["queue"])
                if not queue_path.is_symlink():
                    summary = queue_summary(queue_path.read_text(encoding="utf-8"))
                    report.update(pending=summary["pending_count"],
                                  completed=summary["completed_count"],
                                  queue_blocked=summary["blocked_count"])
                    report["queue_counts_snapshot"] = True
            except (OSError, ValueError, UnicodeError):
                pass
        active = report.get("current_task")
        phase = active.get("phase") if isinstance(active, dict) else None
        report["current_activity"] = (
            "running" if phase in ("selected", "running") else "busy"
        )
        report["reason"] = (
            "Project lock held; task in progress" if phase in ("selected", "running")
            else "Project lock held by another worker or planner"
        )
    else:
        report["current_activity"] = report.get("decision", "unknown")
    if not initialized:
        next_action = f"Initialize a managed project: pw init --project {project} --repo /path/to/repository"
    elif report.get("decision") == "unknown" and report.get("reason") == "Manager project identity mismatch":
        next_action = "Verify the selected project configuration and manager identity, then rerun pw status"
    elif report.get("decision") in {"unknown", None}:
        next_action = "Verify the configured worktree exists and is a Git repository, then rerun pw status"
    elif report.get("blockers") and "requirements_missing" in report["blockers"]:
        next_action = f"Create and complete requirements.md with: pw requirements --project {project} --edit"
    elif report.get("blockers") and "requirements_invalid" in report["blockers"]:
        next_action = f"Correct the listed requirements diagnostics, then rerun: pw status --project {project}"
    elif report.get("decision") == "awaiting_acceptance":
        next_action = ("Milestone acceptance is pending. Approve through the configured "
                       "Telegram callback; Projectwright will attempt to replenish "
                       "the next milestone immediately after approval.")
    elif report.get("decision") == "busy":
        next_action = "A run is in progress; no action required. Check the user service journal for progress."
    elif (report.get("decision") == "blocked" and
          set(report.get("blockers") or []) in (
              {"active_git_cycle", "dirty_worktree_review"},
              {"active_git_cycle", "branch_or_worktree"})):
        # The dispatcher independently validates a recorded EDIT/TEST/COMMIT
        # cycle before allowing the next task. Do not call this a manual blocker.
        pending_tasks = report.get("pending_tasks")
        candidate = (pending_tasks[0] if isinstance(pending_tasks, list)
                     and pending_tasks and isinstance(pending_tasks[0], dict) else {})
        task_id, kind = candidate.get("id"), candidate.get("kind")
        if isinstance(task_id, str) and kind in ("TEST", "COMMIT"):
            next_action = (f"{task_id} — {kind} will be attempted automatically on the "
                           "next timer activation if the Git-cycle checks pass.")
        else:
            next_action = ("An EDIT/TEST/COMMIT cycle is in progress; the next queued "
                           "task will be attempted on the next timer activation "
                           "if the recorded Git-cycle checks pass.")
    elif report.get("decision") in {"blocked", "quota_blocked"}:
        next_action = "Resolve the reported blocker or approval gate, then rerun pw status"
    elif type(report.get("pending")) is not int:
        next_action = "Queue counts are unknown; inspect the project queue and manager blockers, then rerun pw status"
    elif (report.get("decision") in {"replenish", "strategic_review"} and
          report.get("planning_enabled") is True and recurring_enabled is True):
        next_action = "Automatic queue replenishment will be attempted on the next timer activation."
    elif report.get("pending") == 0:
        next_action = f"Review requirements and queue planning with: pw plan --project {project}"
    elif recurring_enabled is True and execution_enabled is True:
        next_action = "Queued work will be attempted automatically on the next timer activation."
    else:
        next_action = f"Review the queued task, then run one manually with: pw start --project {project}"
    report["next_action"] = next_action
    status_returncode = result.returncode or int(manager_status_unavailable)
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return status_returncode
    print(f"Project: {project}")
    print(f"Worktree: {report.get('worktree') or 'unknown'}")
    print(f"Planning: {'enabled' if planning_enabled else 'disabled' if planning_enabled is not None else 'unknown'}")
    print(f"Planning decision: {report.get('decision', 'unknown')}")
    print(f"Execution: {'enabled' if execution_enabled else 'disabled' if execution_enabled is not None else 'unknown'}")
    for key, label in (("pending", "Queue pending"), ("completed", "Queue completed"), ("queue_blocked", "Queue blocked")):
        if key in report:
            value = report[key]
            print(f"{label}: {value if isinstance(value, int) else 'unknown'}")
    if report.get("queue_counts_snapshot"):
        print("Queue counts: read-only snapshot while a run holds the lock")
    print(f"Current activity: {report.get('current_activity', 'unknown')} — {report.get('reason', 'unknown')}")
    task = report.get("current_task")
    if isinstance(task, dict):
        task_id = task.get("id") or task.get("task_id") or "?"
        kind, phase = task.get("kind", "?"), task.get("phase", "?")
        print(f"Current task: {task_id} — {kind} ({phase})")
    else:
        print("Current task: none reported")
    blockers = report.get("blockers")
    print("Blockers: " + (", ".join(blockers) if isinstance(blockers, list) and blockers else "none reported"))
    for item in report.get("diagnostics", []):
        if isinstance(item, dict) and isinstance(item.get("message"), str):
            location = ""
            if item.get("milestone"):
                location = f" (requirement {item.get('requirement', 'unknown')}, milestone {item['milestone']})"
            print(f"Requirement issue{location}: {item['message']}")
    print("Recurring execution: " + report["recurring_execution"])
    print("Next action: " + next_action)
    return status_returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "requirements", "start", "authorize-execution", "status"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--config-dir", type=Path, help="Configuration home (contains projects/)")
    parser.add_argument("--edit", action="store_true", help="Open requirements in an editor")
    parser.add_argument("--yes", action="store_true", help="Confirm one manual task, or explicitly authorize persistent execution")
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
        if args.action == "authorize-execution":
            return authorize_persistent_execution(args.project, args.yes)
        return status(args.project, args.json)
    except (ValueError, OSError) as exc:
        print(f"pw {args.action}: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
