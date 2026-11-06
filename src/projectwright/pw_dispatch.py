#!/usr/bin/env python3
"""One bounded automation tick: plan if safe, then execute at most one task."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from pw_one_shot_auth import HANDOFF_ENV, create as create_handoff, sha256_bytes

def default_project_root():
    """Select project-root path without loading potentially injected modules."""
    custom = os.environ.get('PROJECTWRIGHT_CONFIG_DIR')
    if custom:
        return Path(custom).expanduser() / 'projects'
    legacy_override = os.environ.get('HERMES_PROJECT_CONFIG_DIR')
    if legacy_override:
        return Path(legacy_override).expanduser()
    # Projectwright project state belongs in ~/projects by default. Do not
    # silently create *new* projects under legacy XDG/Hermes directories just
    # because one of those directories happens to exist.
    #
    # Existing installations can select their original state explicitly using
    # HERMES_PROJECT_CONFIG_DIR (direct root) or PROJECTWRIGHT_CONFIG_DIR
    # (configuration home, with /projects appended).
    return Path.home() / 'projects'


SAFE_IDLE = {'awaiting_acceptance', 'disabled', 'no_op'}
CYCLE_BLOCKERS = {'active_git_cycle', 'dirty_worktree_review'}
LEGACY_CYCLE_BLOCKERS = {'branch_or_worktree', 'active_git_cycle'}
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
    'blocked': {'project', 'decision', 'reason', 'pending', 'milestone', 'blockers', 'diagnostics',
                'requirements_file', 'requirements_exists', 'requirements_valid', 'requirements_milestones',
                'planning_enabled'},
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
    if 'blockers' in report and (
        not isinstance(report['blockers'], list) or
        any(not isinstance(item, str) for item in report['blockers'])
    ):
        raise ValueError('manager blockers must be a string list')
    if 'diagnostics' in report:
        diagnostics = report['diagnostics']
        if not isinstance(diagnostics, list):
            raise ValueError('manager diagnostics must be a list')
        for item in diagnostics:
            if (not isinstance(item, dict) or
                    not isinstance(item.get('code'), str) or not item['code'] or
                    not isinstance(item.get('message'), str) or not item['message']):
                raise ValueError('manager diagnostic must include code and message strings')
            if 'line' in item and (type(item['line']) is not int or item['line'] < 1):
                raise ValueError('manager diagnostic line must be a positive integer')
            if any(key in item and not isinstance(item[key], str)
                   for key in ('requirement', 'milestone')):
                raise ValueError('manager diagnostic requirement and milestone must be strings')
    requirements_file = report.get('requirements_file')
    if ('requirements_file' in report and requirements_file is not None and
            not isinstance(requirements_file, str)):
        raise ValueError('manager requirements_file must be a string or null')
    for key in ('requirements_exists', 'requirements_valid'):
        if key in report and type(report[key]) is not bool:
            raise ValueError(f'manager {key} must be a boolean')
    if 'requirements_milestones' in report and (
        not isinstance(report['requirements_milestones'], list) or
        any(not isinstance(item, str) for item in report['requirements_milestones'])
    ):
        raise ValueError('manager requirements_milestones must be a string list')
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
    if not isinstance(reason, str):
        return False
    reason_blockers = set(reason.split(', '))
    # The manager's read-only --status and planning --once pathways use
    # different blocker names. Both must be exact known cycle-only shapes.
    if reason_blockers not in (CYCLE_BLOCKERS, LEGACY_CYCLE_BLOCKERS):
        return False
    blockers = report.get('blockers')
    if blockers is not None and (not isinstance(blockers, list)
                                 or set(blockers) != reason_blockers):
        return False
    if blockers is None and reason_blockers != LEGACY_CYCLE_BLOCKERS:
        return False
    try:
        import importlib.util
        root = default_project_root()
        from pw_config import load as load_config
        config_path, cfg = load_config(project, root)
        if not config_path.is_file() or cfg.get('id') != project:
            return False
        cycle = json.loads(Path(cfg['cycle_file']).expanduser().read_text())
        if not isinstance(cycle, dict) or cycle.get('version') != 1 or cycle.get('phase') != 'active':
            return False
        spec = importlib.util.spec_from_file_location('pw_cycle_worker_gate', scripts/'pw_task_worker.py')
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
        manager_helpers = runpy.run_path(str(scripts / 'pw_queue_manager.py'))
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
        journal_file = manager_helpers['worker_journal_path'](cfg, config_path)
        journal = manager_helpers['read_json_optional'](journal_file)
        incidents = manager_helpers['read_json_optional'](config_path.parent / 'recovery_incidents.json')
        if journal.get('current_task') is not None or incidents and (
            not isinstance(incidents.get('incidents'), list) or
            any(not isinstance(i, dict) or i.get('status') not in ('resolved', 'closed') for i in incidents['incidents'])
        ):
            return False
        return True
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.CalledProcessError, ImportError):
        return False


def parse_manual_status(stdout, project, returncode, *, cycle_authorized=False):
    """Fail closed on the manager's read-only status before a manual worker run."""
    if returncode != 0 and not (returncode == 2 and cycle_authorized):
        raise ValueError(f'manager status exit code {returncode}')
    try:
        report = json.loads(stdout, object_pairs_hook=_unique_object,
                            parse_constant=_reject_json_constant)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'manager status is not JSON: {exc}') from exc
    required = {'project', 'decision', 'pending', 'completed', 'queue_blocked',
                'invalid_lines', 'blockers', 'planning_enabled', 'branch', 'head',
                'queue_sha256', 'requirements_sha256', 'pending_tasks'}
    if not isinstance(report, dict) or not required <= set(report):
        raise ValueError('manager status is missing required safety fields')
    if report['project'] != project:
        raise ValueError('manager status project mismatch')
    allowed_decisions = {'disabled', 'no_op', 'replenish', 'strategic_review'}
    if cycle_authorized:
        allowed_decisions.add('blocked')
    if not isinstance(report['decision'], str) or report['decision'] not in allowed_decisions:
        raise ValueError(f"manager status blocks execution: {report['decision']}")
    if cycle_authorized and (returncode != 2 or report['decision'] != 'blocked'
                             or report.get('reason') is None):
        raise ValueError('invalid authorized cycle status')
    for field in ('pending', 'completed', 'queue_blocked'):
        if type(report[field]) is not int or report[field] < 0:
            raise ValueError(f'manager status has invalid {field} count')
    if (not isinstance(report['queue_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', report['queue_sha256'])
            or not isinstance(report['requirements_sha256'], str)
            or (report['requirements_sha256'] is not None and not re.fullmatch(r'[0-9a-f]{64}', report['requirements_sha256']))
            or not isinstance(report['pending_tasks'], list)
            or len(report['pending_tasks']) != report['pending']):
        raise ValueError('manager status has invalid authorization snapshot')
    if type(report['planning_enabled']) is not bool:
        raise ValueError('manager status has invalid planning state')
    if (not isinstance(report['blockers'], list) or
            (set(report['blockers']) != CYCLE_BLOCKERS if cycle_authorized else bool(report['blockers']))):
        raise ValueError('manager status reports safety blockers')
    if not isinstance(report['invalid_lines'], list) or report['invalid_lines']:
        raise ValueError('manager status reports invalid queue entries')
    if not isinstance(report['branch'], str) or not report['branch'] or not isinstance(report['head'], str) or not report['head']:
        raise ValueError('manager status has invalid Git identity')
    return report


def _manual_handoff(project, report):
    """Mint a capability from the exact live state checked by manager status."""
    root = default_project_root()
    from pw_config import load as load_config
    config_path, config = load_config(project, root)
    config_path = config_path.resolve()
    if config.get('id') != project:
        raise ValueError('project configuration identity mismatch')
    queue_path = Path(config['queue']).expanduser().resolve()
    queue_bytes = queue_path.read_bytes()
    if sha256_bytes(queue_bytes) != report['queue_sha256']:
        raise ValueError('queue changed after manager authorization snapshot')
    pending = report['pending_tasks']
    if (not pending or not isinstance(pending[0], dict)
            or not isinstance(pending[0].get('id'), str)):
        raise ValueError('manager status has no valid selected task')
    requirements_setting = config.get('planning', {}).get('requirements_file')
    requirements_bytes = Path(requirements_setting).expanduser().resolve().read_bytes() if requirements_setting else b''
    if sha256_bytes(requirements_bytes) != (report['requirements_sha256'] or sha256_bytes(b'')):
        raise ValueError('requirements changed after manager authorization snapshot')
    worktree = Path(config['worktree']).expanduser().resolve()
    branch = subprocess.check_output(
        ['git', '-C', str(worktree), 'branch', '--show-current'], text=True
    ).strip()
    head = subprocess.check_output(
        ['git', '-C', str(worktree), 'rev-parse', 'HEAD'], text=True
    ).strip()
    if report.get('branch') != branch or report.get('head') != head:
        raise ValueError('manager Git identity changed before handoff')
    claims = {
        'project': project,
        'config': str(config_path),
        'task_id': pending[0]['id'],
        'queue_sha256': sha256_bytes(queue_bytes),
        'requirements_sha256': sha256_bytes(requirements_bytes),
        'configured_branch': config.get('branch'),
        'git_branch': branch,
        'head': head,
    }
    return create_handoff(config_path.parent, claims)


def run_tick(project, scripts, *, runner=subprocess.run, no_telegram=False, one_shot=False):
    manager_mode = '--status' if one_shot else '--once'
    manager = [sys.executable, '-B', str(scripts/'pw_queue_manager.py'), '--project', project, manager_mode]
    try:
        m = runner(manager, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}, timeout=650)
    except subprocess.TimeoutExpired:
        print('FAIL manager status/planning timed out; worker not launched', file=sys.stderr)
        return 21
    try:
        if one_shot:
            cycle_authorized = False
            if m.returncode == 2:
                candidate = json.loads(m.stdout, object_pairs_hook=_unique_object,
                                       parse_constant=_reject_json_constant)
                cycle_authorized = (isinstance(candidate, dict) and
                                    authorized_cycle_task(project, scripts, candidate))
            report = parse_manual_status(m.stdout, project, m.returncode,
                                         cycle_authorized=cycle_authorized)
        else:
            report = parse_manager_response(m.stdout, project, m.returncode)
    except (ValueError, TypeError) as exc:
        print(f'FAIL manager contract: {exc}', file=sys.stderr)
        return 21
    decision = report['decision']
    if one_shot and report['pending'] == 0:
        print('MANAGER reports no pending task; no worker launched', flush=True)
        return 0
    if one_shot:
        print(f'MANAGER decision={decision}; authorizing one manually requested task', flush=True)
    # A held project lock is a deferred tick, never permission to run a worker.
    elif decision == 'busy':
        print('MANAGER decision=busy; DEFERRED: project lock held, no worker launched', flush=True)
        return 0
    if not one_shot:
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
            config_free_ready = False
            if decision == 'disabled':
                from pw_config import load as load_config, ready_for_config_free_worker
                config_path, effective = load_config(project)
                # A disabled configured project is never treated as config-free.
                config_free_ready = not config_path.exists() and ready_for_config_free_worker(effective)
            if not config_free_ready and (decision != 'no_op' or report['pending'] == 0):
                return 0
        elif decision != 'queued':
            print('FAIL unexpected planning decision='+decision, file=sys.stderr)
            return 20
    worker = [sys.executable, '-B', str(scripts/'pw_task_worker.py'), '--project', project, '--once']
    from pw_config import load as _load_config
    if no_telegram or not _load_config(project)[0].is_file():
        worker.append('--no-telegram')
    worker_env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}
    if one_shot:
        try:
            worker_env[HANDOFF_ENV] = _manual_handoff(project, report)
        except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
            print(f'FAIL one-shot handoff: {exc}', file=sys.stderr)
            return 21
    try:
        w = runner(worker, capture_output=True, text=True, env=worker_env, timeout=2700)
    except subprocess.TimeoutExpired:
        print('WORKER interrupted by timeout; task recovery state was preserved for review', file=sys.stderr)
        return 23
    except OSError as exc:
        print(f'FAIL worker could not start: {exc}', file=sys.stderr)
        return 23
    print('WORKER rc='+str(w.returncode))
    if w.stdout: print(w.stdout[-4000:])
    if w.stderr: print(w.stderr[-4000:], file=sys.stderr)
    if w.returncode == 0:
        # Read-only observability: journal and queue are written by the worker.
        # Missing/inconsistent data is reported, not inferred as successful work.
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location('pw_dispatch_manager_summary', scripts/'pw_queue_manager.py')
            manager_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(manager_module)
            config_path, cfg = __import__('pw_config').load(project, default_project_root())
            journal_file = manager_module.worker_journal_path(cfg, config_path)
            journal = json.loads(journal_file.read_text(encoding='utf-8'))
            queue = Path(cfg['queue']).read_text(encoding='utf-8')
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
    p.add_argument('--no-telegram',action='store_true',help='Do not send worker progress through Hermes Telegram')
    p.add_argument('--one-shot', action='store_true', help='Authorize one manually requested worker task without persistent execution authorization')
    p.add_argument('--config-dir',type=Path,help='Projectwright configuration home (projects are in its projects/ subdirectory)')
    a=p.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',a.project):p.error('Invalid project ID')
    if a.config_dir is not None:
        if not a.config_dir.is_absolute(): p.error('--config-dir must be absolute')
        os.environ['PROJECTWRIGHT_CONFIG_DIR'] = str(a.config_dir)
    return run_tick(a.project,a.scripts,no_telegram=a.no_telegram,one_shot=a.one_shot)
def cli():
    """Preliminary unified command launcher; each service retains its own parser."""
    commands = {
        'tick': ('pw_dispatch', []),
        'status': ('pw_onboarding', ['status']),
        'plan': ('pw_onboarding', ['plan']),
        'worker': ('pw_task_worker', []),
        'notify': ('pw_notify', []),
        'timer': ('pw_project_timer', []),
        'setup': ('pw_project_timer', ['setup']),
        'gateway-restart': ('pw_project_timer', ['gateway-restart']),
        'setup-user': ('pw_project_timer', ['setup-user']),
        'defaults': ('pw_defaults', []),
        'config': ('pw_settings', []),
        'init': ('pw_init', []),
        'register': ('pw_embedded', []),
        'requirements': ('pw_onboarding', ['requirements']),
        'start': ('pw_onboarding', ['start']),
        'authorize-execution': ('pw_onboarding', ['authorize-execution']),
    }
    usage = 'usage: pw {tick|status|plan|start|authorize-execution|requirements|worker|notify|timer|setup|gateway-restart|setup-user|defaults|config|init|register} [options]'
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(usage)
        return 0 if len(sys.argv) > 1 else 2
    command = sys.argv[1]
    if command not in commands:
        print(f'Unknown Projectwright command: {command}\n{usage}', file=sys.stderr)
        return 2
    module, fixed = commands[command]
    # Shared onboarding commands accept --config-dir in the same sense as
    # the existing commands: a configuration home containing projects/.
    config_dir = None
    if '--config-dir' in sys.argv[2:]:
        i = sys.argv.index('--config-dir', 2)
        if i + 1 < len(sys.argv):
            candidate = Path(sys.argv[i + 1]).expanduser()
            if not candidate.is_absolute():
                print('--config-dir must be absolute', file=sys.stderr)
                return 2
            config_dir = str(candidate)
    if config_dir:
        os.environ['PROJECTWRIGHT_CONFIG_DIR'] = config_dir
    env = os.environ.copy()
    if config_dir is not None:
        # An explicit legacy configuration home must not silently inherit a
        # repository location from an unrelated shell or background service.
        env.pop("PROJECTWRIGHT_PROJECT_DIR", None)
    if command != "init" and "--config-dir" not in sys.argv[2:]:
        from pw_embedded import discover
        try:
            found = discover(Path.cwd())
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if found is not None:
            env["PROJECTWRIGHT_PROJECT_DIR"] = str(found.parent)
    arguments = list(sys.argv[2:])
    if (command in {'tick', 'status', 'plan', 'worker', 'notify', 'requirements',
                    'start', 'authorize-execution'} and
            '--project' not in arguments and env.get('PROJECTWRIGHT_PROJECT_DIR')):
        arguments.extend(['--project', Path(env['PROJECTWRIGHT_PROJECT_DIR']).name])
    return subprocess.run([sys.executable, '-B', '-m', module, *fixed, *arguments],
                          check=False, env=env).returncode


if __name__=='__main__':raise SystemExit(main())
