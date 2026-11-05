"""Verified, idempotent final-project Telegram notification.

No LLM calls or changes to project planning/approval state. A completion
message is eligible only after all declared milestones have current acceptance
receipts and the repository, cycle, worker and queue are clean.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import re
import subprocess
from pathlib import Path

from pw_config import load as load_config
from pw_notify import config_values, parse_allowed_users, send_text
from pw_telegram_approval import atomic_json
from project_milestone_guard import current_receipts, milestone_ids, policy_for_project
from project_queue_manager import queue_summary


def completion_details(directory: Path) -> dict | None:
    """Read-only gate for a fully accepted project; fail closed on ambiguity."""
    directory = Path(directory)
    from pw_embedded import project_id
    project = project_id(directory)
    config_path, cfg = load_config(project, directory.parent, directory_override=directory)
    if not config_path.is_file() or cfg.get("id") != project:
        return None
    if not cfg.get("planning", {}).get("enabled", False):
        return None
    requirements = Path(cfg["planning"]["requirements_file"]).expanduser().read_bytes()
    queue = Path(cfg["queue"]).expanduser().read_text(encoding="utf-8")
    milestones = milestone_ids(requirements.decode("utf-8"))
    summary = queue_summary(queue)
    if (not milestones or summary["pending_count"] or summary["blocked_count"]
            or summary["invalid_lines"]):
        return None
    if Path(cfg["cycle_file"]).expanduser().exists():
        return None
    from pw_worker_journal import journal_path
    worker_path = journal_path(cfg, config_path)
    journal = json.loads(worker_path.read_text()) if worker_path.exists() else {}
    if journal.get("current_task") is not None:
        return None
    repo = Path(cfg["worktree"]).expanduser()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
    if (git("branch", "--show-current") != cfg["branch"]
            or git("status", "--porcelain=v1", "--untracked-files=all")):
        return None
    head = git("rev-parse", "HEAD")
    state_file = directory / "planning_state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    receipts = current_receipts(
        state, requirements, queue, head, repo=repo,
        strict=cfg.get("planning", {}).get("milestone_sequence") == "strict",
        policy=policy_for_project(directory), journal=journal,
    )
    if not milestones <= set(receipts):
        return None
    headings = []
    for match in re.finditer(r"(?m)^###\s+([A-Z][A-Z0-9]*-\d+-M\d+(?:-[A-Z0-9]+)*)\s+[—-]\s+(.+)$",
                             requirements.decode("utf-8")):
        if match.group(1) in milestones:
            headings.append((match.group(1), match.group(2).strip()))
    if {m for m, _ in headings} != milestones:
        return None
    fingerprint = hashlib.sha256(json.dumps(
        {"head": head, "milestones": sorted(milestones),
         "requirements": hashlib.sha256(requirements).hexdigest()},
        sort_keys=True,
    ).encode("utf-8")).hexdigest()
    milestone_lines = [f"• {key}: {title}" for key, title in headings[:8]]
    if len(headings) > 8:
        milestone_lines.append(f"• …and {len(headings) - 8} more milestones")
    message = (
        "✅ Projectwright — project complete\n"
        f"Project: {project}\n"
        f"Milestones accepted: {len(milestones)}\n"
        f"Tasks completed: {summary['completed_count']}\n\n"
        "Work completed:\n" + "\n".join(milestone_lines) + "\n\n"
        f"Final commit: {head[:12]}\n"
        "All declared milestones have verified acceptance receipts. No further work is queued."
    )
    return {"id": fingerprint, "message": message}


def notify_completion(directory: Path, *, transport=None) -> list[str]:
    """Send at most once per recipient and completed project revision.

    The per-project lock serializes concurrent callbacks and the regular
    notification timer. A crash after Telegram delivery but before receipt
    persistence has the same at-least-once limitation as milestone delivery.
    """
    directory = Path(directory)
    details = completion_details(directory)
    if details is None:
        return []
    notify_lock = directory / ".telegram_completion_notify.lock"
    with notify_lock.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        details = completion_details(directory)
        if details is None:
            return []
        vals = config_values(Path.home() / ".hermes" / ".env")
        if not vals.get("TELEGRAM_BOT_TOKEN"):
            raise ValueError("Telegram bot token is missing")
        users = parse_allowed_users(vals.get("TELEGRAM_ALLOWED_USERS", ""))
        marker = directory / "telegram_completion_notified.json"
        previous = json.loads(marker.read_text()) if marker.exists() else {}
        recipients = dict(previous.get("recipients", {})) if previous.get("completion_id") == details["id"] else {}
        sent = []
        for user in users:
            if user in recipients:
                continue
            message_id = send_text(details["message"], user, values=vals, transport=transport)
            if type(message_id) is not int or message_id <= 0:
                raise ValueError("Telegram returned an invalid completion message ID")
            recipients[user] = message_id
            atomic_json(marker, {"completion_id": details["id"], "recipients": recipients})
            sent.append(user)
        return sent
