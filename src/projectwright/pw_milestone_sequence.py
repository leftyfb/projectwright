"""Pure, opt-in milestone ordering policy. No state mutations."""
from __future__ import annotations
import re
from project_milestone_guard import HEADER, scoped_tasks, acceptance_policy_fingerprint


def order(requirements: str) -> list[str]:
    items = [m.group(1) for m in HEADER.finditer(requirements) if re.search(r'-M\d+(?:-|$)', m.group(1))]
    if len(set(items)) != len(items):
        raise ValueError('Duplicate milestone headings; correct requirements before scheduling')
    return items


def evaluate(requirements: str, queue: str, receipts: dict, policy: dict | None = None) -> dict:
    """Return the first unaccepted milestone, or a fail-closed decision.

    Assumes caller has independently verified CURRENT receipts and absence of
    journal/cycle/Git blockers. Pending tasks from a later milestone are unsafe.
    """
    milestones = order(requirements)
    if not milestones:
        return {'decision':'blocked', 'reason':'Sequencing requires explicit milestone headings'}
    if not isinstance(receipts, dict):
        return {'decision':'blocked', 'reason':'Invalid receipt map'}
    if (not isinstance(policy, dict) or policy.get('version') != 1
            or not isinstance(policy.get('milestones'), dict)):
        return {'decision':'blocked', 'reason':'Missing or invalid strict acceptance policy'}
    for milestone in milestones:
        spec = policy['milestones'].get(milestone)
        match = re.match(r'^(.*)-M\d+(?:-|$)', milestone)
        if (acceptance_policy_fingerprint(spec) is None or match is None
                or spec['requirement'] != match.group(1)):
            return {'decision':'blocked', 'milestone':milestone,
                    'reason':f'Missing or invalid acceptance policy for {milestone}'}
    current = next((m for m in milestones if m not in receipts), None)
    if current is None:
        return {'decision':'complete', 'milestone':None}
    # Checked/blocked work in a future milestone is also a state error; it
    # indicates previously unauthorized cross-milestone execution.
    for later in milestones[milestones.index(current)+1:]:
        req = re.match(r'^(.*)-M\d+(?:-|$)', later)
        tasks = scoped_tasks(queue, req.group(1), later) if req else []
        if tasks:
            return {'decision':'blocked','milestone':current,'reason':f'Future milestone {later} already has tasks; manual review required'}
    req = re.match(r'^(.*)-M\d+(?:-|$)', current)
    tasks = scoped_tasks(queue, req.group(1), current) if req else []
    if any(t['state'] == '!' for t in tasks):
        return {'decision':'blocked', 'milestone':current,'reason':'Milestone contains blocked tasks'}
    if tasks and any(t['state'] == 'x' and t['kind'] == 'COMMIT' for t in tasks) and all(t['state']=='x' for t in tasks):
        return {'decision':'awaiting_acceptance', 'milestone':current, 'reason':'Completed milestone awaits verified acceptance receipt'}
    return {'decision':'active', 'milestone':current}
