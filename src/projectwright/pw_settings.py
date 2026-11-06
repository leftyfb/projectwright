"""Inspect and safely update documented Projectwright project settings."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from pw_config import load

# Fields are intentionally explicit: typos and unknown keys must not silently
# create ineffective JSON settings. Values are validated before any write.
STRINGS = {
    "display_name", "branch", "hermes",
    "base", "queue", "work_log", "worktree", "lock", "run_log",
    "result_dir", "cycle_file", "worker_journal_file",
    "planning.requirements_file", "notes.progress_file",
    "notes.mirrors.queue", "notes.mirrors.work_log",
    "quota.ha_env_file", "quota.remaining_entity",
}
BOOLEANS = {
    "planning.enabled", "planning.trigger.replan_on_blocker",
    "execution.enabled", "notes.enabled", "quota.enabled",
    "quota.allow_local_http",
}
INTEGERS = {
    "timeout_seconds", "planning.trigger.pending_below",
    "planning.trigger.review_every_completed_tasks",
    "planning.queue.target_pending", "planning.queue.max_new_tasks",
    "planning.queue.max_pending",
}
NUMBERS = {"quota.minimum_remaining_percent", "quota.timeout_seconds"}
OPTIONAL_STRINGS = {"quota.rate_limited_entity"}
ARRAYS = {"test_file_patterns", "provider.planner_argv", "provider.worker_argv"}
ENUMS = {"planning.milestone_sequence": ("strict", "off"),
         "provider.type": ("hermes", "command")}
READ_ONLY = {"id", "layout", "projectwright_initialized"}
KEYS = STRINGS | BOOLEANS | INTEGERS | NUMBERS | OPTIONAL_STRINGS | ARRAYS | set(ENUMS)
# Executing work requires its separate, existing authorization command.
AUTH_ONLY = {"execution.enabled"}
# Changes to these paths could redirect work to unintended resources.
SENSITIVE = {"branch", "worktree", "hermes", "provider.type",
             "provider.planner_argv", "provider.worker_argv",
             "quota.ha_env_file", "quota.allow_local_http",
             "notes.progress_file", "notes.mirrors.queue",
             "notes.mirrors.work_log"}
DEFAULT_VALUES = {
    "planning.milestone_sequence": "off",
    "planning.trigger.pending_below": 3,
    "planning.trigger.review_every_completed_tasks": 6,
    "planning.trigger.replan_on_blocker": True,
    "planning.queue.target_pending": 6,
    "planning.queue.max_new_tasks": 5,
    "planning.queue.max_pending": 10,
    "provider.type": "hermes",
    "quota.minimum_remaining_percent": 10,
    "quota.timeout_seconds": 10,
    "quota.remaining_entity": "sensor.codex_usage_weekly_remaining",
    "quota.rate_limited_entity": None,
    "quota.allow_local_http": False,
    "test_file_patterns": ["scripts/test_*.py", "tests/test_*.py"],
}


def _effective_value(effective: dict, key: str):
    actual = _nested(effective, key)
    return DEFAULT_VALUES.get(key) if actual is None and key in DEFAULT_VALUES else actual


PATHS = {"base", "queue", "work_log", "worktree", "lock", "run_log",
         "result_dir", "cycle_file", "worker_journal_file",
         "planning.requirements_file", "notes.progress_file",
         "notes.mirrors.queue", "notes.mirrors.work_log",
         "quota.ha_env_file"}


def _nested(data: dict, key: str):
    value = data
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _put(data: dict, key: str, value, *, reset=False):
    parts = key.split(".")
    node = data
    ancestors = []
    for part in parts[:-1]:
        if part not in node:
            if reset:
                return
            node[part] = {}
        if not isinstance(node[part], dict):
            raise ValueError(f"Cannot edit {key}: {part} is not an object")
        ancestors.append((node, part))
        node = node[part]
    if reset:
        node.pop(parts[-1], None)
        for parent, name in reversed(ancestors):
            if not parent[name]:
                parent.pop(name)
    else:
        node[parts[-1]] = value


def _value(key: str, raw: str):
    if key in STRINGS | OPTIONAL_STRINGS | set(ENUMS):
        if key in OPTIONAL_STRINGS and raw == "null":
            return None
        value = raw
    else:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(f"{key} expects a JSON value") from None
    if key in STRINGS and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{key} requires a nonempty string")
    if key in ENUMS and value not in ENUMS[key]:
        raise ValueError(f"{key}: expected one of {', '.join(ENUMS[key])}")
    if key in BOOLEANS and type(value) is not bool:
        raise ValueError(f"{key}: expected true or false")
    if key in INTEGERS and (type(value) is not int or value < 1):
        raise ValueError(f"{key}: expected a positive integer")
    if key in NUMBERS and (type(value) not in (float, int) or
                           not float("-inf") < value < float("inf")):
        raise ValueError(f"{key}: expected a finite number")
    if key in ARRAYS and (not isinstance(value, list) or not value or
                         not all(isinstance(item, str) and item for item in value)):
        raise ValueError(f"{key}: expected a nonempty JSON array of strings")
    if key == "planning.milestone_sequence" and value == "off":
        # Omit strict sequencing to retain the program's built-in default.
        return None
    if key in PATHS and isinstance(value, str) and "\x00" in value:
        raise ValueError("Paths cannot contain NUL bytes")
    if key == "branch" and (not re.fullmatch(r"[A-Za-z0-9_./-]+", value)
                             or ".." in value or value.endswith("/") or value.startswith("-")):
        raise ValueError("Invalid Git branch")
    if key == "timeout_seconds" and value > 3600:
        raise ValueError("timeout_seconds must be between 1 and 3600")
    if key == "planning.trigger.review_every_completed_tasks" and value < 1:
        raise ValueError("Review interval must be positive")
    if key == "quota.minimum_remaining_percent" and not 0 <= value <= 100:
        raise ValueError("Quota percentage must be between 0 and 100")
    if key == "quota.timeout_seconds" and not 0 < value <= 30:
        raise ValueError("Quota timeout must be greater than 0 and at most 30 seconds")
    if key == "test_file_patterns" and any(
            not v.endswith(".py") or v.startswith("/") or ".." in Path(v).parts for v in value):
        raise ValueError("Test patterns must be relative Python file patterns")
    if key in {"provider.planner_argv", "provider.worker_argv"} and not Path(value[0]).is_absolute():
        raise ValueError("Provider command executable must be an absolute path")
    return value


def _check_policy(data: dict):
    planning = data.get("planning", {})
    trigger = planning.get("trigger", {})
    queue = planning.get("queue", {})
    low = trigger.get("pending_below", 3)
    target = queue.get("target_pending", 6)
    cap = queue.get("max_pending", 10)
    batch = queue.get("max_new_tasks", 5)
    if not 1 <= low <= target <= cap or batch > cap:
        raise ValueError("Planning thresholds require 1 <= pending_below <= target_pending <= max_pending; max_new_tasks <= max_pending")
    provider = data.get("provider", {})
    if provider.get("type", "hermes") == "command":
        for field in ("planner_argv", "worker_argv"):
            argv = provider.get(field)
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) and v for v in argv):
                raise ValueError(f"provider.{field} must be configured for command provider")
            if not Path(argv[0]).is_absolute():
                raise ValueError(f"provider.{field} requires an absolute executable")


def _atomic_json(path: Path, data: dict):
    if path.is_symlink():
        raise ValueError("Refusing symlinked config.json")
    fd, tmp = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def operate(action: str, project: str, key: str | None = None,
            raw: str | None = None, *, yes=False):
    path, effective = load(project)
    if not path.is_file():
        raise ValueError("Project is not initialized; use pw init first")
    if path.is_symlink():
        raise ValueError("Refusing symlinked config.json")
    if action == "list":
        for name in sorted(KEYS | READ_ONLY):
            actual = _effective_value(effective, name)
            print(f"{name} = {json.dumps(actual, sort_keys=True)}")
        return
    if key not in KEYS and key not in READ_ONLY:
        raise ValueError(f"Unknown setting: {key}. Use pw config list to see supported options")
    if action == "get":
        actual = _effective_value(effective, key)
        print(json.dumps(actual, sort_keys=True))
        return
    if key in READ_ONLY:
        raise ValueError(f"{key} is managed by initialization and cannot be changed")
    if key in AUTH_ONLY:
        raise ValueError("Use pw authorize-execution --project PROJECT --yes to enable execution; do not edit it through pw config")
    if key == "planning.enabled" and action == "set" and raw == "true":
        raise ValueError("Use pw plan --project PROJECT to authorize planning")
    if action == "set" and raw is None:
        raise ValueError("Missing setting value")
    value = _value(key, raw) if action == "set" else None
    if key in SENSITIVE and not yes:
        raise ValueError(f"{key} is sensitive; review the change and repeat with --yes")
    # Lock the running worker out of configuration mutations and reject changes
    # while a Git cycle or an interrupted task is awaiting recovery.
    lock = Path(effective["lock"])
    if lock.is_symlink():
        raise ValueError("Refusing symlinked worker lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Project worker holds its lock; try again after the task ends") from None
        if Path(effective["cycle_file"]).exists():
            raise ValueError("Active Git cycle; configuration changes require manual review")
        from pw_worker_journal import journal_path
        journal = journal_path(effective, path)
        if journal.exists():
            try:
                data = json.loads(journal.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ValueError("Unreadable worker journal; manual review required") from exc
            if data.get("current_task") is not None:
                raise ValueError("Active or unresolved task journal; configuration changes refused")
        original = json.loads(path.read_text(encoding="utf-8"))
        modified = json.loads(json.dumps(original))
        if action == "reset" or (key == "planning.milestone_sequence" and value is None):
            _put(modified, key, None, reset=True)
        else:
            _put(modified, key, value)
        _check_policy(modified)
        if modified == original:
            print(f"Unchanged: {key}")
            return
        # Validate embedded paths and security constraints with the canonical
        # loader before replacing the actual configuration file.
        # Use the embedded layout's security boundaries even for changes that
        # do not involve a path, rather than trusting arbitrary JSON.
        if original.get("layout") == "embedded":
            from pw_embedded import directory
            state = directory(project, __import__("pw_dispatch").default_project_root())
            for field in ("base", "queue", "work_log", "worktree", "lock", "run_log",
                          "result_dir", "cycle_file", "worker_journal_file",
                          "planning.requirements_file"):
                candidate = _nested(modified, field)
                if candidate is None:
                    continue
                resolved = (state / candidate).resolve()
                expected = state.parent.resolve() if field == "worktree" else state.resolve()
                if field == "worktree":
                    if resolved != expected:
                        raise ValueError("Embedded worktree must be the owning repository")
                elif not resolved.is_relative_to(expected):
                    raise ValueError(f"Embedded {field} cannot escape .pw")
            # Credentials belong in separately managed files, never embedded config.
            def no_secrets(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if any(t in k.lower() for t in ("password", "secret", "token", "api_key", "credential", "private_key")):
                            raise ValueError("Embedded config cannot contain secrets")
                        no_secrets(v)
                elif isinstance(obj, list):
                    for v in obj:
                        no_secrets(v)
            no_secrets(modified)
        _atomic_json(path, modified)
        print(f"{action.title()}: {key} = {json.dumps(_nested(modified, key))}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or update documented Projectwright configuration")
    parser.add_argument("action", choices=["list", "get", "set", "reset"])
    parser.add_argument("key", nargs="?")
    parser.add_argument("value", nargs="?")
    parser.add_argument("--project", required=True)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--yes", action="store_true", help="Explicitly authorize a sensitive setting change")
    args = parser.parse_args()
    if args.config_dir is not None:
        if not args.config_dir.is_absolute():
            parser.error("--config-dir must be absolute")
        os.environ["PROJECTWRIGHT_CONFIG_DIR"] = str(args.config_dir)
    if args.action == "list" and (args.key is not None or args.value is not None):
        parser.error("list takes no key or value")
    if args.action in ("get", "reset") and (args.key is None or args.value is not None):
        parser.error(f"{args.action} requires exactly one setting key")
    if args.action == "set" and (args.key is None or args.value is None):
        parser.error("set requires a setting key and value")
    try:
        operate(args.action, args.project, args.key, args.value, yes=args.yes)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
