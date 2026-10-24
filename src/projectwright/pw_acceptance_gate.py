"""Read-only milestone acceptance barrier shared by manager and planner.

This only detects completed COMMIT-bearing milestones not covered by a CURRENT
acceptance receipt. It does not infer approval, mutate state, or call Hermes.
"""
from __future__ import annotations
import re
from pw_milestone_guard import milestone_ids, scoped_tasks


def awaiting_acceptance(queue: str, requirements: str, current: dict) -> list[str]:
    """Return completed, unverified milestones with a COMMIT task.

    The caller must gate only after checking for zero pending queue tasks and
    ensuring recovery/cycle/worktree blockers are clear.
    """
    if not isinstance(current, dict):
        raise ValueError('Invalid verified milestone map')
    pending = []
    for milestone in sorted(milestone_ids(requirements)):
        if milestone in current:
            continue
        req = re.match(r'^(.*)-M\d+(?:-|$)', milestone)
        if not req:
            continue
        tasks = scoped_tasks(queue, req.group(1), milestone)
        if tasks and any(t['kind'] == 'COMMIT' for t in tasks) and all(t['state'] == 'x' for t in tasks):
            pending.append(milestone)
    return pending
