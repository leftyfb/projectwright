#!/usr/bin/env python3
"""One bounded automation tick: plan if safe, then execute at most one task."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

def default_project_root():
    """Select project-root path without loading potentially injected modules."""
    custom = os.environ.get('PROJECTWRIGHT_CONFIG_DIR')
    if custom:
        return Path(custom).expanduser() / 'projects'
    legacy_override = os.environ.get('HERMES_PROJECT_CONFIG_DIR')
    if legacy_override:
        return Path(legacy_override).expanduser()
    xdg = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    root = xdg / 'projectwright' / 'projects'
    legacy = Path.home() / '.hermes' / 'projects'
    return legacy if legacy.is_dir() and not root.is_dir() else root


SAFE_IDLE = {'awaiting_acceptance', 'disabled', 'no_op'}
CYCLE_BLOCKERS = {'branch_or_worktree', 'active_git_cycle'}
MANAGER_EXIT_CODES = {
    'queued': 0,
    'busy': 2,
    'blocked': 2,
    'no_op': 3,
    'disabled': 3,
    'awaiting_acceptance': 3,
    'quota_blocked': 4,
    'planner_failed': 4,
}
DECISION_FIELDS = {
    'queued': {'project', 'decision', 'pending', 'added', 'task_ids', 'planning_mode', 'notes_sync'},
    'busy': {'project', 'decision', 'reason'},
    'blocked': {'project', 'decision', 'reason', 'pending', 'milestone'},
    'no_op': {'project', 'decision', 'pending', 'reason'},
    'disabled': {'project', 'decision'},
    'awaiting_acceptance': {'project', 'decision', 'pending', 'reason', 'milestone', 'milestones'},
    'quota_blocked': {'project', 'decision', 'pending', 'quota'},
    'planner_failed': {'project', 'decision', 'pending', 'reason'},
}
REQUIRED_FIELDS = {
    'queued': {'pending', 'added', 'task_ids', 'planning_mode', 'notes_sync'},
    'busy': {'reason'},
    'blocked': {'reason'},
    'no_op': {'pending'},
    'disabled': set(),
    'awaiting_acceptance': {'pending', 'reason'},
    'quota_blocked': {'pending', 'quota'},
    'planner_failed': {'pending', 'reason'},
}
QUOTA_FIELDS = {
    'enabled', 'allowed', 'reason', 'remaining_percent',
    'minimum_remaining_percent', 'rate_limited', 'detail',
}


def manager_exit_code(decision):
    """Return the documented queue-manager exit code; unknown means refusal."""
    return MANAGER_EXIT_CODES.get(decision, 4)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ValueError(f'invalid JSON constant: {value}')


def parse_manager_response(stdout, project, returncode):
    """Parse and validate the single-object manager stdout/exit-code contract."""
    if type(returncode) is not int:
        raise ValueError('manager exit code is not an integer')
    if not isinstance(stdout, str) or not stdout.strip():
        raise ValueError('manager stdout is empty')
    try:
        report = json.loads(stdout, object_pairs_hook=_unique_object,
                            parse_constant=_reject_json_constant)
    except (ValueError, TypeError) as exc:
        raise ValueError('manager stdout is not one valid JSON object') from exc
    if not isinstance(report, dict):
        raise ValueError('manager response has invalid shape')
    if report.get('project') != project or not isinstance(report.get('project'), str):
        raise ValueError('manager project identity mismatch')
    decision = report.get('decision')
    if not isinstance(decision, str) or decision not in MANAGER_EXIT_CODES:
        raise ValueError('manager decision is unsupported')
    if set(report) - DECISION_FIELDS[decision]:
        raise ValueError('manager response has invalid fields for decision')
    if not REQUIRED_FIELDS[decision] <= set(report):
        raise ValueError('manager response is missing required fields')
    if returncode != manager_exit_code(decision):
        raise ValueError('manager exit code does not match decision')
    if 'reason' in report and not isinstance(report['reason'], str):
        raise ValueError('manager reason must be a string')
    if 'pending' in report and (type(report['pending']) is not int or report['pending'] < 0):
        raise ValueError('manager pending count must be a non-negative integer')
    if 'milestone' in report and report['milestone'] is not None and not isinstance(report['milestone'], str):
        raise ValueError('manager milestone must be a string or null')
    if 'milestones' in report and (
        not isinstance(report['milestones'], list) or
        any(not isinstance(item, str) for item in report['milestones'])
    ):
        raise ValueError('manager milestones must be a string list')
    if decision == 'awaiting_acceptance' and ('milestone' in report) == ('milestones' in report):
        raise ValueError('manager awaiting_acceptance requires one milestone field')
    if decision == 'busy' and report['reason'] != 'Project lock held; skip planning':
        raise ValueError('manager busy reason is not recognized')
    if decision == 'queued':
        added, task_ids = report['added'], report['task_ids']
        if type(added) is not int or added < 1 or not isinstance(task_ids, list):
            raise ValueError('manager queued response has invalid task count')
        if len(task_ids) != added or any(
            not isinstance(item, str) or not re.fullmatch(r'[A-Z]+[0-9]+', item)
            for item in task_ids
        ):
            raise ValueError('manager queued task IDs do not match added count')
        if len(set(task_ids)) != len(task_ids):
            raise ValueError('manager queued task IDs are duplicated')
        if report['planning_mode'] not in ('tactical', 'strategic'):
            raise ValueError('manager queued response has invalid planning mode')
        notes_sync = report['notes_sync']
        if (not isinstance(notes_sync, str) or
                notes_sync not in ('not_configured', 'ok') and not notes_sync.startswith('failed: ')):
            raise ValueError('manager queued response has invalid notes_sync status')
    if decision == 'quota_blocked':
        quota = report['quota']
        if not isinstance(quota, dict) or set(quota) - QUOTA_FIELDS or type(quota.get('allowed')) is not bool or quota['allowed']:
            raise ValueError('manager quota_blocked response has invalid quota result')
    if 'quota' in report and isinstance(report['quota'], dict):
        quota = report['quota']
        if 'enabled' in quota and type(quota['enabled']) is not bool:
            raise ValueError('quota enabled must be boolean')
        if 'reason' in quota and not isinstance(quota['reason'], str):
            raise ValueError('quota reason must be a string')
        if 'rate_limited' in quota and type(quota['rate_limited']) is not bool:
            raise ValueError('quota rate_limited must be boolean')
        for key in ('remaining_percent', 'minimum_remaining_percent'):
            value = quota.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ValueError(f'quota {key} must be numeric or null')
        if 'detail' in quota and not isinstance(quota['detail'], str):
            raise ValueError('quota detail must be a string')
    return report


def authorized_cycle_task(project, scripts, report):
    """Fail-closed read-only gate for a blocked manager during EDIT/TEST/COMMIT.

    This only routes to the original worker. The worker independently enforces
    project locks, journal/recovery, quotas, Git snapshots, and task scopes.
    """
    if report.get('decision') != 'blocked':
        return False
    reason = report.get('reason')
    if not isinstance(reason, str) or set(reason.split(', ')) != CYCLE_BLOCKERS:
        return False
    try:
        import importlib.util
        root = default_project_root()
        cfg = json.loads((root / project / 'config.json').read_text())
        if cfg.get('id') != project or not cfg.get('cycle_file'):
            return False
        cycle = json.loads(Path(cfg['cycle_file']).expanduser().read_text())
        if not isinstance(cycle, dict) or cycle.get('version') != 1 or cycle.get('phase') != 'active':
            return False
        spec = importlib.util.spec_from_file_location('pw_cycle_worker_gate', scripts/'project_task_worker.py')
        if spec is None or spec.loader is None:
            return False
        # Import the authoritative worker implementation, not a duplicated Git validator.
        import sys as _sys
        module = importlib.util.module_from_spec(spec)
        _sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.load_project(project)
        if module.CYCLE_FILE.resolve() != Path(cfg['cycle_file']).expanduser().resolve():
            return False
        queue = module.QUEUE.read_text(encoding='utf-8')
        # Load the manager helpers from the selected scripts tree, not sys.modules.
        # This read-only gate must not trust an unrelated pre-imported manager.
        import runpy
        manager_helpers = runpy.run_path(str(scripts / 'project_queue_manager.py'))
        summary = manager_helpers['queue_summary'](queue)
        if summary['invalid_lines'] or summary['blocked_count'] or not summary['pending']:
            return False
        task = module.pick_task(queue)
        if task is None or task.kind not in ('TEST', 'COMMIT'):
            return False
        if summary['pending'][0] != {'id': task.task_id, 'kind': task.kind}:
            return False
        # No detached/unrelated completed task may be used as cycle authorization.
        if not isinstance(cycle.get('last_task'), str) or not cycle['last_task']:
            return False
        lines = [m for m in module.ROW.finditer(queue)]
        previous = next((i for i, m in enumerate(lines) if m['id'] == task.task_id), None)
        if previous is None or previous == 0:
            return False
        prior = lines[previous - 1]
        if prior['id'] != cycle['last_task'] or prior['state'] != 'x':
            return False
        if prior['kind'] not in ('EDIT', 'TEST'):
            return False
        if task.kind == 'COMMIT' and prior['kind'] not in ('EDIT', 'TEST'):
            return False
        before = module.repo_state()
        if before[0] != cycle.get('head') or before[1] != cycle.get('branch') or before[1] != cfg.get('branch'):
            return False
        if before[3] != cycle.get('snapshot'):
            return False
        allowed = cycle.get('allowed')
        if not isinstance(allowed, list) or not allowed or any(not isinstance(p, str) or not p for p in allowed):
            return False
        dirty = {p for p in before[3] if not p.startswith('!')}
        if not dirty or not dirty <= set(allowed):
            return False
        # A current journal or recovery incident cannot authorize dispatch.
        journal = manager_helpers['read_json_optional'](root / project / 'worker_journal.json')
        incidents = manager_helpers['read_json_optional'](root / project / 'recovery_incidents.json')
        if journal.get('current_task') is not None or incidents and (
            not isinstance(incidents.get('incidents'), list) or
            any(not isinstance(i, dict) or i.get('status') not in ('resolved', 'closed') for i in incidents['incidents'])
        ):
            return False
        return True
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.CalledProcessError, ImportError):
        return False


def run_tick(project, scripts, *, runner=subprocess.run):
    manager = [sys.executable, '-B', str(scripts/'project_queue_manager.py'), '--project', project, '--once']
    m = runner(manager, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}, timeout=650)
    try:
        report = parse_manager_response(m.stdout, project, m.returncode)
    except (ValueError, TypeError) as exc:
        print(f'FAIL manager contract: {exc}', file=sys.stderr)
        return 21
    decision = report['decision']
    # A held project lock is a deferred tick, never permission to run a worker.
    if decision == 'busy':
        print('MANAGER decision=busy; DEFERRED: project lock held, no worker launched', flush=True)
        return 0
    cycle_route = decision == 'blocked' and authorized_cycle_task(project, scripts, report)
    if m.returncode == 4:
        print('FAIL manager refused decision='+decision, file=sys.stderr)
        return 20
    if decision == 'blocked' and not cycle_route:
        print('FAIL manager blocked; no authorized active Git cycle', file=sys.stderr)
        return 20
    print('MANAGER decision='+decision, flush=True)
    if cycle_route:
        print('Active Git cycle: dispatching authorized next task to worker; planner remains blocked', flush=True)
    elif decision in SAFE_IDLE:
        if decision != 'no_op' or report['pending'] == 0:
            return 0
    elif decision != 'queued':
        print('FAIL unexpected planning decision='+decision, file=sys.stderr)
        return 20
    worker = [sys.executable, '-B', str(scripts/'project_task_worker.py'), '--project', project, '--once']
    w = runner(worker, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PROJECTWRIGHT_DISPATCHED':'1'}, timeout=2700)
    print('WORKER rc='+str(w.returncode))
    if w.stdout: print(w.stdout[-4000:])
    if w.stderr: print(w.stderr[-4000:], file=sys.stderr)
    if w.returncode == 0:
        # Read-only observability: journal and queue are written by the worker.
        # Missing/inconsistent data is reported, not inferred as successful work.
        try:
            root = Path(os.environ.get('HERMES_PROJECT_CONFIG_DIR', str(Path.home()/'.hermes/projects'))) / project
            journal = json.loads((root/'worker_journal.json').read_text())
            queue = (root/'queue.md').read_text(encoding='utf-8')
            import importlib.util
            spec = importlib.util.spec_from_file_location('pw_dispatch_manager_summary', scripts/'project_queue_manager.py')
            manager_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(manager_module)
            summary = manager_module.queue_summary(queue)
            completed = journal.get('last_completed_task') or {}
            if journal.get('current_task') is None and isinstance(completed.get('id'), str) and isinstance(completed.get('kind'), str):
                print(f"TASK SUMMARY last_completed={completed['id']} kind={completed['kind']} pending={len(summary['pending'])} blocked={summary['blocked_count']} invalid={len(summary['invalid_lines'])}", flush=True)
            else:
                print('TASK SUMMARY unavailable: no trustworthy completed journal entry', flush=True)
        except (OSError, ValueError, KeyError, TypeError, ImportError, AttributeError) as exc:
            print(f'TASK SUMMARY unavailable: {type(exc).__name__}', flush=True)
    return 0 if w.returncode == 0 else 23


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--project',required=True)
    p.add_argument('--scripts',type=Path,default=Path(__file__).resolve().parent)
    a=p.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',a.project):p.error('Invalid project ID')
    return run_tick(a.project,a.scripts)
if __name__=='__main__':raise SystemExit(main())
