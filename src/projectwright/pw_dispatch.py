#!/usr/bin/env python3
"""One bounded automation tick: plan if safe, then execute at most one task."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SAFE_IDLE = {'awaiting_acceptance', 'disabled'}
CYCLE_BLOCKERS = {'branch_or_worktree', 'active_git_cycle'}


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
        root = Path(os.environ.get('HERMES_PROJECT_CONFIG_DIR', str(Path.home()/'.hermes/projects')))
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
        from_queue = __import__('project_queue_manager') if str(scripts) in sys.path else None
        if from_queue is None:
            sys.path.insert(0, str(scripts))
            from_queue = __import__('project_queue_manager')
        summary = from_queue.queue_summary(queue)
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
        journal = from_queue.read_json_optional(root / project / 'worker_journal.json')
        incidents = from_queue.read_json_optional(root / project / 'recovery_incidents.json')
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
        report = json.loads(m.stdout)
        decision = report['decision']
    except (ValueError, KeyError, TypeError):
        print('FAIL manager returned invalid JSON', m.stdout[-1600:], file=sys.stderr)
        return 21
    # A held project lock is a deferred tick, never permission to run a worker.
    # Reject malformed/error responses rather than treating them as contention.
    if (m.returncode == 2 and decision == 'busy' and
            report.get('project') == project and
            report.get('reason') == 'Project lock held; skip planning'):
        print('MANAGER decision=busy; DEFERRED: project lock held, no worker launched', flush=True)
        return 0
    cycle_route = m.returncode == 2 and authorized_cycle_task(project, scripts, report)
    if m.returncode and not cycle_route:
        print('FAIL manager:', m.stderr.strip(), m.stdout[-1600:], file=sys.stderr)
        return 20
    print('MANAGER decision='+str(decision), flush=True)
    if cycle_route:
        print('Active Git cycle: dispatching authorized next task to worker; planner remains blocked', flush=True)
    elif decision in SAFE_IDLE:
        return 0
    elif decision == 'no_op':
        pending = report.get('pending')
        if not isinstance(pending, int) or isinstance(pending, bool) or pending < 0:
            print('FAIL no_op missing trustworthy pending count', file=sys.stderr)
            return 24
        if pending == 0:
            return 0
    elif decision != 'queued':
        print('FAIL unexpected planning decision: '+str(decision), file=sys.stderr)
        return 22
    worker = [sys.executable, '-B', str(scripts/'project_task_worker.py'), '--project', project, '--once']
    w = runner(worker, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}, timeout=2700)
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
    p.add_argument('--scripts',type=Path,default=Path.home()/'.hermes/scripts')
    a=p.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',a.project):p.error('Invalid project ID')
    return run_tick(a.project,a.scripts)
if __name__=='__main__':raise SystemExit(main())
