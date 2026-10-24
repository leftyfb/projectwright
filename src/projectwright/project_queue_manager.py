#!/usr/bin/env python3
"""Project queue manager and planner entry point.

--status reports project state. --once invokes plan_once and may run the
configured planner and persist queue/planning state. For --once, stdout is
exactly one JSON object; diagnostics belong on stderr.
Exit codes: 0 queued, 2 busy/blocked, 3 no_op/disabled/awaiting_acceptance,
4 quota_blocked/planner_failed/unknown refusal; 1 is an execution error.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROW = re.compile(r'^\s*- \[(?P<state>[ x!])\]\s+\*\*(?P<id>[A-Z]+\d+)\s+[—-]\s+(?P<kind>[A-Z]+)\*\*\s*(?P<description>.*)$')
VALID_KINDS = {'READ', 'EDIT', 'TEST', 'COMMIT', 'VERIFY', 'DECIDE'}
DEFAULT_TRIGGER = {'pending_below': 3, 'review_every_completed_tasks': 6, 'replan_on_blocker': True}
DEFAULT_QUEUE = {'target_pending': 6, 'max_new_tasks': 5, 'max_pending': 10}
ONCE_EXIT_CODES = {
    'queued': 0, 'busy': 2, 'blocked': 2,
    'no_op': 3, 'disabled': 3, 'awaiting_acceptance': 3,
    'quota_blocked': 4, 'planner_failed': 4,
}


def once_exit_code(decision: object) -> int:
    """Map a machine-readable --once decision to its documented process code."""
    if not isinstance(decision, str):
        return 4
    return ONCE_EXIT_CODES.get(decision, 4)


def provider_argv(cfg: dict, phase: str, *, prompt: str | None = None) -> tuple[list[str], bool]:
    """Return explicit argv and whether to deliver the prompt on stdin.

    Command adapters receive plain text on stdin; planner JSON and worker
    completion artifacts retain their existing schemas and safety checks.
    """
    if phase not in ('planner', 'worker'):
        raise ValueError('Unsupported provider phase')
    provider = cfg.get('provider', {'type': 'hermes'})
    if not isinstance(provider, dict):
        raise ValueError('provider must be an object')
    kind = provider.get('type', 'hermes')
    if kind == 'hermes':
        path = str(Path(cfg['hermes']).expanduser())
        if phase == 'planner':
            if not isinstance(prompt, str):
                raise ValueError('Hermes planner requires a prompt')
            return [path, '--ignore-rules', '-z', prompt], False
        return [path, 'chat', '--oneshot', '--query-file', '-', '--ignore-rules'], True
    if kind == 'command':
        key = phase + '_argv'
        argv = provider.get(key)
        if not isinstance(argv, list) or not argv or not all(
                isinstance(x, str) and x and '\\x00' not in x for x in argv):
            raise ValueError(f'Command provider requires nonempty {key} list')
        if not Path(argv[0]).is_absolute():
            raise ValueError(f'Command provider {key} executable must be absolute')
        return list(argv), True
    raise ValueError(f'Unknown execution provider type: {kind}')


def default_project_root() -> Path:
    """Resolve project storage without changing existing Hermes installations.

    Explicit PROJECTWRIGHT_CONFIG_DIR denotes an XDG-style configuration home,
    with project directories beneath its projects/ child. The legacy environment
    variable remains an explicit direct project-root override.
    """
    direct = os.environ.get('HERMES_PROJECT_CONFIG_DIR')
    selected = os.environ.get('PROJECTWRIGHT_CONFIG_DIR')
    if selected:
        return Path(selected).expanduser() / 'projects'
    if direct:
        return Path(direct).expanduser()
    xdg = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    target = xdg / 'projectwright' / 'projects'
    legacy = Path.home() / '.hermes' / 'projects'
    return legacy if legacy.is_dir() and not target.is_dir() else target


def project_config(project: str, root: Path) -> tuple[Path, dict]:
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', project):
        raise ValueError('Invalid project ID')
    directory = root / project
    cfg = json.loads((directory / 'config.json').read_text(encoding='utf-8'))
    if cfg.get('id') != project:
        raise ValueError('Project config ID mismatch')
    for k in ('queue', 'lock', 'worktree', 'branch', 'cycle_file'):
        if not cfg.get(k):
            raise ValueError(f'Missing configuration key: {k}')
    return directory, cfg


def positive_int(mapping: dict, name: str, default: int, *, minimum: int = 0) -> int:
    v = mapping.get(name, default)
    if type(v) is not int or v < minimum:
        raise ValueError(f'Invalid planning setting {name}: {v!r}')
    return v


def planning_policy(cfg: dict) -> dict:
    p = cfg.get('planning', {})
    if not isinstance(p, dict):
        raise ValueError('planning must be an object')
    t = p.get('trigger', DEFAULT_TRIGGER)
    q = p.get('queue', DEFAULT_QUEUE)
    if not isinstance(t, dict) or not isinstance(q, dict):
        raise ValueError('planning.trigger and planning.queue must be objects')
    low = positive_int(t, 'pending_below', 3, minimum=1)
    review = positive_int(t, 'review_every_completed_tasks', 6, minimum=1)
    target = positive_int(q, 'target_pending', 6, minimum=1)
    batch = positive_int(q, 'max_new_tasks', 5, minimum=1)
    cap = positive_int(q, 'max_pending', 10, minimum=1)
    if not 1 <= low <= target <= cap:
        raise ValueError('Require 1 <= pending_below <= target_pending <= max_pending')
    if batch > cap:
        raise ValueError('max_new_tasks must not exceed max_pending')
    if type(t.get('replan_on_blocker', True)) is not bool:
        raise ValueError('replan_on_blocker must be boolean')
    if type(p.get('enabled', False)) is not bool:
        raise ValueError('planning.enabled must be boolean')
    return {'enabled': p.get('enabled', False), 'low': low, 'review': review,
            'replan_on_blocker': t.get('replan_on_blocker', True),
            'target': target, 'batch': batch, 'cap': cap,
            'requirements_file': p.get('requirements_file')}


def queue_summary(text: str) -> dict:
    ids = set()
    pending = []
    done = 0
    blocked = 0
    invalid = []
    for n, line in enumerate(text.splitlines(), 1):
        if not re.match(r'^\s*- \[[ x!X]\]', line):
            continue
        m = ROW.fullmatch(line)
        if not m or (m['kind'] not in VALID_KINDS and
                     not (m['kind'] == 'LEGACY' and m['state'] in ('x', '!'))):
            invalid.append(n)
            continue
        task_id = m['id']
        if task_id in ids:
            invalid.append(n)
        ids.add(task_id)
        if m['state'] == ' ':
            pending.append({'id': task_id, 'kind': m['kind']})
        elif m['state'] == 'x':
            done += 1
        else:
            blocked += 1
    return {'pending_count': len(pending), 'pending': pending,
            'completed_count': done, 'blocked_count': blocked, 'invalid_lines': invalid}


def read_json_optional(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return value


def inspect(project: str, root: Path, *, mode: str, quota_evaluator=None) -> dict:
    directory, cfg = project_config(project, root)
    policy = planning_policy(cfg)
    lock = Path(cfg['lock']).expanduser()
    lock.parent.mkdir(parents=True, exist_ok=True)
    # Use the same nonblocking lock as the worker; no nested invocation.
    with lock.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'project': project, 'decision': 'busy', 'reason': 'Project lock held; skip planning'}
        queue_path = Path(cfg['queue']).expanduser()
        summary = queue_summary(queue_path.read_text(encoding='utf-8'))
        journal = read_json_optional(directory / 'worker_journal.json')
        state = read_json_optional(directory / 'worker_state.json')
        incidents = read_json_optional(directory / 'recovery_incidents.json')
        repo = Path(cfg['worktree']).expanduser()
        branch = subprocess.check_output(['git', '-C', str(repo), 'branch', '--show-current'], text=True).strip()
        head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = bool(subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True).strip())
        since = state.get('completed_since_strategic_review', 0)
        if type(since) is not int or since < 0:
            raise ValueError('Invalid completed_since_strategic_review')
        incident_block = False
        # Fail conservatively if an incident record exists but its schema isn't recognized.
        if incidents:
            if isinstance(incidents.get('incidents'), list):
                incident_block = any(isinstance(i, dict) and i.get('status') not in ('resolved', 'closed') for i in incidents['incidents'])
            else:
                incident_block = True
        blockers = []
        if journal.get('current_task') is not None:
            blockers.append('unresolved_task_journal')
        if Path(cfg['cycle_file']).expanduser().exists():
            blockers.append('active_git_cycle')
        if incident_block:
            blockers.append('recovery_incident')
        if branch != cfg['branch']:
            blockers.append('wrong_branch')
        if summary['invalid_lines']:
            blockers.append('invalid_queue_entries')
        if dirty:
            blockers.append('dirty_worktree_review')
        reqfile = policy['requirements_file']
        requirements = Path(reqfile).expanduser() if isinstance(reqfile, str) and reqfile else None
        req_exists = bool(requirements and requirements.is_file())
        req_hash = hashlib.sha256(requirements.read_bytes()).hexdigest() if req_exists else None
        # A fully verified set of explicitly named milestones needs no model call.
        # Fail open to a review if requirements contain no explicit milestone headings.
        if req_exists and not blockers:
            from project_milestone_guard import current_receipts, milestone_ids
            milestone_set = milestone_ids(requirements.read_text(encoding='utf-8'))
            receipts = current_receipts(read_json_optional(directory/'planning_state.json'),
                                        requirements.read_bytes(), queue_path.read_text(encoding='utf-8'), head, repo=Path(cfg['worktree']).expanduser(),
                                        strict=cfg.get('planning', {}).get('milestone_sequence') == 'strict',
                                        policy=__import__('project_milestone_guard').policy_for_project(directory), journal=journal)
            fully_verified = bool(milestone_set) and milestone_set <= set(receipts)
        else:
            fully_verified = False
        if not policy['enabled']:
            decision, reason = 'disabled', 'Planning disabled by config'
        elif blockers:
            decision, reason = 'blocked', ', '.join(blockers)
        elif not req_exists:
            decision, reason = 'blocked', 'requirements_file missing or unset'
        elif fully_verified and summary['pending_count'] == 0:
            decision, reason = 'no_op', 'All declared milestones have current verified acceptance receipts'
        else:
            low = summary['pending_count'] < policy['low']
            review = since >= policy['review']
            if low or review:
                decision = 'strategic_review' if review else 'replenish'
                reason = 'Strategic review due' if review else 'Pending queue below threshold'
            else:
                decision, reason = 'no_op', 'Queue healthy and no review due'
        result = {'project': project, 'decision': decision, 'reason': reason,
                  'pending': summary['pending_count'], 'completed': summary['completed_count'],
                  'queue_blocked': summary['blocked_count'], 'invalid_lines': summary['invalid_lines'],
                  'completed_since_strategic_review': since, 'branch': branch,
                  'head': head, 'requirements_sha256': req_hash,
                  'max_add_now': max(0, min(policy['batch'], policy['target']-summary['pending_count'], policy['cap']-summary['pending_count'])),
                  'blockers': blockers, 'planning_enabled': policy['enabled']}
        # Strict milestone sequencing is opt-in and checked before quota / AI.
        if cfg.get('planning', {}).get('milestone_sequence') == 'strict' and not blockers and req_exists:
            from project_milestone_sequence import evaluate
            sequencing = evaluate(requirements.read_text(encoding='utf-8'), queue_path.read_text(encoding='utf-8'), receipts,
                                  __import__('project_milestone_guard').policy_for_project(directory))
            if sequencing['decision'] in ('blocked', 'awaiting_acceptance'):
                result.update(decision=sequencing['decision'], reason=sequencing['reason'],
                              milestone=sequencing.get('milestone'))
                return result
        # Suppress replanning completed COMMIT milestones pending human acceptance.
        if result['decision'] in ('replenish', 'strategic_review') and result['pending'] == 0:
            from project_acceptance_gate import awaiting_acceptance
            _awaiting = awaiting_acceptance(queue_path.read_text(encoding='utf-8'), requirements.read_text(encoding='utf-8'), receipts)
            if _awaiting:
                result.update(decision='awaiting_acceptance', milestones=_awaiting, reason='Completed milestone requires acceptance approval; no model call')
                return result
        # --status never contacts Home Assistant.
        if mode == 'once' and decision in ('replenish', 'strategic_review'):
            if quota_evaluator is None:
                from project_quota import evaluate
                quota_evaluator = evaluate
            quota = quota_evaluator(cfg.get('quota', {}))
            result['quota'] = quota
            if not quota.get('allowed', False):
                result.update(decision='quota_blocked', reason='Quota gate blocked planning')
            else:
                result.update(decision='ready_for_planner', planning_mode=decision,
                              reason='Stage A only: no model calls or queue mutations')
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--config-root', type=Path, default=None)
    parser.add_argument('--config-dir', type=Path, default=None, help='Projectwright configuration home')
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument('--status', action='store_true')
    commands.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.config_dir is not None:
        if not args.config_dir.is_absolute(): parser.error('--config-dir must be absolute')
        if args.config_root is not None: parser.error('--config-dir and --config-root are mutually exclusive')
    args.config_root = (args.config_dir / 'projects' if args.config_dir is not None
                        else args.config_root if args.config_root is not None
                        else default_project_root())
    try:
        # Config-free invocation is intentionally inert: never infer a worktree,
        # provider credentials or authorization policy from the user's HOME.
        if not (args.config_root / args.project / 'config.json').is_file():
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', args.project):
                raise ValueError('Invalid project ID')
            print(json.dumps({'project': args.project, 'decision': 'disabled'}))
            return once_exit_code('disabled') if args.once else 0
        mode = 'once' if args.once else 'status'
        if mode == 'once':
            from project_queue_planner import plan_once
            result = plan_once(args.project, args.config_root)
        else:
            result = inspect(args.project, args.config_root, mode=mode)
        print(json.dumps(result, indent=2, sort_keys=True))
        if mode == 'once':
            return once_exit_code(result.get('decision'))
        return 0 if result['decision'] not in ('blocked', 'busy', 'quota_blocked') else 2
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
