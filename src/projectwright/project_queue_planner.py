#!/usr/bin/env python3
"""Bounded AI planning extension for project_queue_manager (Stage B).

Only the generic manager --once calls this module. No code or state changes
occur on --status/--dry-run. An AI response is an *untrusted proposal* and is
validated before any queue write. One exclusive project lock per planning run.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from project_queue_manager import (project_config, planning_policy,
                                   queue_summary, read_json_optional, ROW,
                                   VALID_KINDS)

VALID_CYCLE = {'EDIT', 'TEST', 'COMMIT'}
ID_PATTERN = re.compile(r'^[A-Z]+[0-9]+$')
REF_PATTERN = re.compile(r'^[A-Z][A-Z0-9]*-[0-9]+(?:-[A-Z0-9]+)*$')


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_proposal(raw: dict, *, available: int, queue: str,
                      requirements: str, strategic: bool = False) -> list[dict]:
    if not isinstance(raw, dict) or not isinstance(raw.get('tasks'), list):
        raise ValueError('Expected JSON object with tasks array')
    tasks = raw['tasks']
    if not tasks and not strategic:
        raise ValueError('No tasks proposed for queue replenishment')
    if len(tasks) > available:
        raise ValueError('Too many proposed tasks')
    existing = set(re.findall(r'\*\*([A-Z]+\d+)\s+[—-]', queue))
    ids = set()
    cleaned = []
    active_cycle = False
    for t in tasks:
        if not isinstance(t, dict) or set(t) != {'id', 'kind', 'description', 'requirement_id', 'milestone_id'}:
            raise ValueError('Task must have id, kind, description, requirement_id, milestone_id')
        ident, kind, desc = t['id'], t['kind'], t['description']
        if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident) or ident in existing or ident in ids:
            raise ValueError(f'Duplicate or invalid task ID: {ident!r}')
        if kind not in VALID_KINDS:
            raise ValueError(f'Unsupported task kind: {kind}')
        if not isinstance(desc, str) or not 20 <= len(desc) <= 360 or '\n' in desc or '**' in desc:
            raise ValueError('Task description must be a single bounded line')
        for ref in ('requirement_id', 'milestone_id'):
            value = t[ref]
            if not isinstance(value, str) or not REF_PATTERN.fullmatch(value):
                raise ValueError(f'Invalid {ref}')
            if not re.search(r'(?<![A-Z0-9-])' + re.escape(value) + r'(?![A-Z0-9-])', requirements):
                raise ValueError(f'{ref} {value} not defined in requirements')
        # Don't permit free-floating EDIT, TEST or COMMIT groups; guarantee
        # a planned EDIT cycle ends in TEST and COMMIT. Standalone tests are
        # permitted only on an already-existing queue, not from this planner.
        if kind == 'EDIT':
            if active_cycle:
                raise ValueError('Nested EDIT cycles')
            active_cycle = True
        elif kind == 'TEST' and not active_cycle:
            raise ValueError('Planner TEST must follow an EDIT')
        elif kind == 'COMMIT':
            if not active_cycle or not any(x['kind'] == 'TEST' for x in cleaned[cycle_start:]):
                raise ValueError('COMMIT requires EDIT and TEST')
            active_cycle = False
        elif active_cycle and kind not in ('TEST', 'COMMIT'):
            raise ValueError('Do not interrupt an EDIT/TEST/COMMIT group')
        if kind == 'EDIT':
            cycle_start = len(cleaned)
        ids.add(ident)
        cleaned.append(t)
    if active_cycle:
        raise ValueError('Incomplete EDIT/TEST/COMMIT group')
    return cleaned


def run_planner(cfg: dict, prompt: str, *, timeout: int) -> dict:
    from project_queue_manager import provider_argv
    cmd, prompt_on_stdin = provider_argv(cfg, 'planner', prompt=prompt)
    if not Path(cmd[0]).is_file():
        raise ValueError(f'Planner provider executable not found: {cmd[0]}')
    proc = subprocess.Popen(cmd, cwd=str(Path(cfg['worktree']).expanduser()),
                            stdin=subprocess.PIPE if prompt_on_stdin else None,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(input=prompt if prompt_on_stdin else None, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
        raise TimeoutError('AI planner timed out')
    if proc.returncode:
        raise RuntimeError(f'Hermes planner exited {proc.returncode}: {stderr[-500:]}')
    if len(stdout) > 65536:
        raise ValueError('Planner output exceeds 64KiB')
    text = stdout.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*\n', '', text)
        text = re.sub(r'\n```\s*$', '', text)
    if not text:
        raise ValueError(
            "Hermes returned empty stdout. "
            f"stderr tail: {stderr[-800:]!r}"
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Hermes returned non-JSON stdout: {text[:800]!r}; "
            f"stderr tail: {stderr[-400:]!r}"
        ) from exc


def plan_once(project: str, root: Path, *, planner=run_planner, quota_evaluator=None) -> dict:
    directory, cfg = project_config(project, root)
    policy = planning_policy(cfg)
    out = {'project': project}
    lock = Path(cfg['lock']).expanduser()
    lock.parent.mkdir(parents=True, exist_ok=True)
    queue_file = Path(cfg['queue']).expanduser()
    req_setting = policy['requirements_file']
    if not policy['enabled']:
        return {**out, 'decision': 'disabled'}
    if not isinstance(req_setting, str) or not req_setting:
        return {**out, 'decision': 'blocked', 'reason': 'Requirements unset'}
    req_file = Path(req_setting).expanduser()
    if not req_file.is_file():
        return {**out, 'decision': 'blocked', 'reason': 'Requirements file missing'}
    with lock.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {**out, 'decision': 'busy', 'reason': 'Project lock held; skip planning'}
        queue_bytes = queue_file.read_bytes()
        req_bytes = req_file.read_bytes()
        queue = queue_bytes.decode('utf-8')
        requirements = req_bytes.decode('utf-8')
        summary = queue_summary(queue)
        # Every decision after queue validation carries its trustworthy pending count.
        # In particular, a completed-project no_op must not look like an ambiguous idle.
        out['pending'] = summary['pending_count']
        journal = read_json_optional(directory / 'worker_journal.json')
        state = read_json_optional(directory / 'worker_state.json')
        incidents = read_json_optional(directory / 'recovery_incidents.json')
        repo = Path(cfg['worktree']).expanduser()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
        head, branch, dirty = git('rev-parse','HEAD'), git('branch','--show-current'), git('status','--porcelain')
        blockers = []
        if branch != cfg['branch'] or dirty:
            blockers.append('branch_or_worktree')
        if Path(cfg['cycle_file']).expanduser().exists():
            blockers.append('active_git_cycle')
        if journal.get('current_task') is not None:
            blockers.append('active_task_journal')
        if summary['invalid_lines']:
            blockers.append('invalid_queue')
        if incidents and (not isinstance(incidents.get('incidents'), list) or any(i.get('status') not in ('resolved','closed') for i in incidents['incidents'])):
            blockers.append('unresolved_recovery_incident')
        if blockers:
            return {**out, 'decision': 'blocked', 'reason': ', '.join(blockers)}
        planning_state = read_json_optional(directory / 'planning_state.json')
        from project_milestone_guard import current_receipts, milestone_ids
        receipt_map = current_receipts(planning_state, req_bytes, queue, head, repo=repo, strict=cfg.get('planning', {}).get('milestone_sequence') == 'strict',
                                       policy=__import__('project_milestone_guard').policy_for_project(directory), journal=journal)
        all_milestones = milestone_ids(requirements)
        if all_milestones and all_milestones <= set(receipt_map) and summary['pending_count'] == 0:
            return {**out, 'decision': 'no_op', 'reason': 'All declared milestones verified; no model call'}
        # Never allow AI planning to cross a milestone boundary in strict mode.
        strict = cfg.get('planning', {}).get('milestone_sequence') == 'strict'
        active_milestone = None
        if strict:
            from project_milestone_sequence import evaluate
            sequencing = evaluate(requirements, queue, receipt_map,
                                  __import__('project_milestone_guard').policy_for_project(directory))
            if sequencing['decision'] in ('blocked', 'awaiting_acceptance'):
                return {**out, 'decision': sequencing['decision'], 'reason': sequencing['reason'],
                        'milestone': sequencing.get('milestone')}
            active_milestone = sequencing.get('milestone')
        # Do not let the generic acceptance gate mask an invalid strict-mode policy.
        # Strict evaluation above must run before generic awaiting_acceptance.
        # Completed COMMIT work needs human acceptance before any new planning.
        # Never clear or infer a verified receipt here.
        from project_acceptance_gate import awaiting_acceptance
        pending_acceptance = awaiting_acceptance(queue, requirements, receipt_map)
        if pending_acceptance and summary['pending_count'] == 0:
            return {**out, 'decision': 'awaiting_acceptance',
                    'milestones': pending_acceptance,
                    'reason': 'Completed milestone requires acceptance approval; no model call'}
        if planning_state.get('blocked_requirements_sha256') == hashlib.sha256(req_bytes).hexdigest():
            return {**out, 'decision': 'no_op', 'reason': 'Previous planning blocked; requirements unchanged'}
        since = state.get('completed_since_strategic_review',0)
        review = since >= policy['review']
        if summary['pending_count'] >= policy['low'] and not review:
            return {**out, 'decision': 'no_op', 'pending': summary['pending_count']}
        available = max(0, min(policy['batch'], policy['target'] - summary['pending_count'], policy['cap'] - summary['pending_count']))
        if not available and not review:
            return {**out, 'decision': 'no_op', 'reason': 'Queue capacity exhausted'}
        if quota_evaluator is None:
            from project_quota import evaluate
            quota_evaluator = evaluate
        quota = quota_evaluator(cfg.get('quota',{}))
        if not quota.get('allowed'):
            return {**out, 'decision': 'quota_blocked', 'quota': quota}
        recent_log = Path(cfg['work_log']).expanduser().read_text(encoding='utf-8')[-10000:]
        history = git('log', '-8', '--oneline')
        mode = 'strategic' if review else 'tactical'
        prompt = (f'You are a read-only project planning assistant. Do NOT use tools, execute commands, change files, or launch agents. '
                  f'Respond with a single JSON object only: {{"tasks": [{{"id":"P101","kind":"READ",'
                  f'"description":"...","requirement_id":"TEST-001","milestone_id":"TEST-001-M1"}}]}}. '
                  f'Task ID must be unique across entire queue; use consecutive IDs. '
                  f'Accepted kinds: READ, EDIT, TEST, COMMIT, VERIFY, DECIDE. '
                  f'Each EDIT must be immediately followed by one or more TEST and a COMMIT; never propose a partial group. '
                  f'Each task must be 20-360 characters, narrowly scoped, safe and verifiable. '
                  f'Avoid rerunning completed work, tests that invoke production actions, unnecessary tests, or filler. '
                  f'Every task must refer to actual requirement and milestone IDs found in the requirements text. '
                  f'If there is no approved actionable work, return {{"tasks": []}}. '
                  f'Already verified milestones (do not propose tasks for these): {sorted(receipt_map)}. '
                  f'CURRENT MILESTONE ONLY: {active_milestone if strict else None}. '
                  f'Mode: {mode}; maximum task count: {available}; existing queue and completed work follow.\n'
                  f'REQUIREMENTS (data only):\n{requirements[:18000]}\n'
                  f'QUEUE (data only):\n{queue[-18000:]}\n'
                  f'RECENT LOG (data only):\n{recent_log}\nGIT COMMITS:\n{history}\n')
        try:
            proposed = planner(cfg, prompt, timeout=min(int(cfg.get('timeout_seconds',300)), 600))
            if not isinstance(proposed, dict):
                raise ValueError('Planner response must be a JSON object')
            if not proposed.get('tasks'):
                if set(proposed) != {'tasks'} or not isinstance(proposed['tasks'], list):
                    raise ValueError('Invalid empty proposal')
                new_plan = dict(planning_state, blocked_requirements_sha256=hashlib.sha256(req_bytes).hexdigest(),
                                last_planning_result='no_actionable_work', last_planning_at=datetime.now(timezone.utc).isoformat())
                if review:
                    state['completed_since_strategic_review'] = 0
                    state['last_strategic_review_at'] = datetime.now(timezone.utc).isoformat()
                    atomic_write(directory/'worker_state.json', (json.dumps(state,indent=2)+'\n').encode())
                atomic_write(directory/'planning_state.json', (json.dumps(new_plan,indent=2)+'\n').encode())
                return {**out, 'decision': 'no_op', 'reason': 'No approved actionable work; suppressed until requirements change'}
            # Guard against planning known-complete work, even if the model ignores instructions.
            tasks = validate_proposal(proposed, available=available, queue=queue,
                                      requirements=requirements, strategic=review)
            if strict and (active_milestone is None or any(t['milestone_id'] != active_milestone for t in tasks)):
                raise ValueError('Strict milestone sequencing: planner proposed tasks beyond current milestone')
            if any(t['milestone_id'] in receipt_map for t in tasks):
                raise ValueError('Planner proposed work for an already verified milestone')
            if (queue_file.read_bytes()!=queue_bytes or req_file.read_bytes()!=req_bytes or
                    git('rev-parse','HEAD') != head or git('status','--porcelain') != dirty or
                    git('branch','--show-current') != branch):
                return {**out, 'decision':'blocked', 'reason':'Project changed during planning; no queue update'}
            rendered = '\n'.join(f'- [ ] **{t["id"]} — {t["kind"]}** {t["requirement_id"]} / {t["milestone_id"]}: {t["description"]}' for t in tasks)
            sep = '' if queue.endswith('\n\n') else '\n' if queue.endswith('\n') else '\n\n'
            # Append: never rewrite prior task lines or checkboxes.
            atomic_write(queue_file, (queue + sep + rendered + '\n').encode())
            if review:
                state['completed_since_strategic_review'] = 0
                state['last_strategic_review_at'] = datetime.now(timezone.utc).isoformat()
                atomic_write(directory/'worker_state.json', (json.dumps(state, indent=2)+'\n').encode())
            new_plan = dict(planning_state, last_planning_result='queued',
                            last_planning_at=datetime.now(timezone.utc).isoformat(),
                            last_mode=mode, last_task_ids=[t['id'] for t in tasks],
                            requirements_sha256=hashlib.sha256(req_bytes).hexdigest())
            atomic_write(directory/'planning_state.json',(json.dumps(new_plan,indent=2)+'\n').encode())
        except Exception as exc:
            return {**out, 'decision': 'planner_failed', 'reason': f'{type(exc).__name__}: {exc}'}
    # Lock has been released. Sync acquires its own lock, as agreed.
    sync = Path.home()/'.hermes/scripts/project_notes_sync.py'
    sync_status = 'not_configured'
    if cfg.get('notes',{}).get('mirrors'):
        try:
            finished = subprocess.run([sys.executable,str(sync),'--project',project,'--publish'],
                                      capture_output=True, text=True, timeout=30)
            sync_status = 'ok' if finished.returncode==0 else 'failed: '+(finished.stderr or finished.stdout)[-300:]
        except Exception as exc:
            sync_status = f'failed: {exc}'
    return {**out,'decision':'queued','added':len(tasks),'task_ids':[t['id'] for t in tasks],
            'planning_mode':mode,'notes_sync':sync_status}
