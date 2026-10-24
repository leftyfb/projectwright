"""Read-only Projectwright configuration defaults; never initialize a project."""
from __future__ import annotations

import argparse
import json
import re
from pw_dispatch import default_project_root
from pw_config import load as load_config, ready_for_config_free_worker

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def defaults(project: str | None = None) -> dict:
    """Describe effective locations and fail-closed behavior without side effects."""
    if project is not None and not _PROJECT_ID.fullmatch(project):
        raise ValueError("Invalid project ID")
    root = default_project_root()
    result = {
        "schema_version": 1,
        "project_root": str(root),
        "defaults": {
            "planning_enabled": False,
            "worker_execution_enabled": False,
            "telegram_delivery_enabled": False,
            "automatic_approval_enabled": False,
            "user_timer_enabled": False,
            "provider": None,
        },
    }
    if project is not None:
        result["project"] = project
        result["project_config"] = str(root / project / "config.json")
        result["configured"] = (root / project / "config.json").is_file()
        result["effective_config"] = load_config(project, root)[1]
        result["config_free_worktree_ready"] = (not result["configured"] and
            ready_for_config_free_worker(result["effective_config"]))
        result["missing_config_decision"] = "disabled"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect inert Projectwright defaults")
    parser.add_argument("--project", help="Optional project ID (read-only)")
    parser.add_argument("--config-dir", help="Override Projectwright configuration home")
    args = parser.parse_args()
    if args.config_dir:
        from pathlib import Path
        import os
        path = Path(args.config_dir).expanduser()
        if not path.is_absolute():
            parser.error("--config-dir must be absolute")
        os.environ["PROJECTWRIGHT_CONFIG_DIR"] = str(path)
    try:
        print(json.dumps(defaults(args.project), indent=2, sort_keys=True))
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
