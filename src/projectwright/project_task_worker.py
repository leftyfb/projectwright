#!/usr/bin/env python3
"""Deterministic single-task dispatcher with on-disk JSON reports."""
from __future__ import annotations

import argparse
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HOME = Path.home()
HERMES_HOME = HOME / '.hermes'
BASE = QUEUE = WORK_LOG = LOCK = RUN_LOG = RESULT_DIR = CYCLE_FILE = WORKTREE = None
HERMES = MODEL = None
CURRENT_TASK_KIND = None
LOCK_CONTENDED = False  # Specific signal for a failed nonblocking project-lock acquisition.
TIMEOUT = None
PROJECT = None
PROJECT_ID = None
PROJECT_CONFIG = None

def load_project(project_id: str) -> None:
    global BASE, QUEUE, WORK_LOG, LOCK, RUN_LOG, RESULT_DIR, CYCLE_FILE, WORKTREE
    global HERMES, MODEL, TIMEOUT, PROJECT, PROJECT_ID, PROJECT_CONFIG
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', project_id):
        raise ValueError('Invalid project ID')
    from pw_config import load as load_config
    cfg_path, cfg = load_config(project_id)
    required = ('queue','work_log','lock','run_log','result_dir','cycle_file','worktree','hermes','timeout_seconds')
    if isinstance(cfg.get('provider'), dict) and cfg['provider'].get('type') == 'command':
        required = tuple(k for k in required if k != 'hermes')
    missing = [k for k in required if not cfg.get(k)]
    if missing: raise ValueError(f'Missing project config: {missing}')
    PROJECT = cfg
    PROJECT_CONFIG = cfg_path
    PROJECT_ID = project_id
    BASE = Path(cfg.get('base', str(Path(cfg['queue']).parent))).expanduser()
    QUEUE = Path(cfg['queue']).expanduser()
    WORK_LOG = Path(cfg['work_log']).expanduser()
    LOCK = Path(cfg['lock']).expanduser()
    RUN_LOG = Path(cfg['run_log']).expanduser()
    RESULT_DIR = Path(cfg['result_dir']).expanduser()
    CYCLE_FILE = Path(cfg['cycle_file']).expanduser()
    WORKTREE = Path(cfg['worktree']).expanduser()
    HERMES = str(Path(cfg.get('hermes', '')).expanduser())
    MODEL = None  # Hermes selects its configured model/provider.
    TIMEOUT = int(cfg['timeout_seconds'])
    if not 1 <= TIMEOUT <= 3600: raise ValueError('Invalid timeout')

ROW = re.compile(r'^(?P<prefix>\s*- \[)(?P<state>[ x!])(?P<suffix>\]\s+\*\*(?P<id>[A-Z]+\d+)\s+[—-]\s+(?P<kind>[A-Z]+)\*\*\s*(?P<desc>.*))$', re.M)

@dataclass(frozen=True)
class Task:
    task_id: str
    kind: str
    description: str
    line_no: int
    raw_line: str


def pick_task(content: str) -> Task | None:
    found = set()
    for no, line in enumerate(content.splitlines(), 1):
        match = ROW.match(line)
        if not match:
            continue
        task_id = match['id']
        if task_id in found:
            raise ValueError(f'Duplicate task ID: {task_id}')
        found.add(task_id)
        if match['kind'] == 'LEGACY' and match['state'] == ' ':
            raise ValueError('Unchecked historical LEGACY task is not executable')
        if match['state'] == ' ':
            return Task(task_id, match['kind'], match['desc'].strip(), no, line)
    return None


def update_selected_only(original: str, task: Task, new_state: str) -> str:
    assert new_state in {'x', '!'}
    lines = original.splitlines(keepends=True)
    idx = task.line_no - 1
    if idx >= len(lines) or lines[idx].rstrip('\r\n') != task.raw_line:
        raise ValueError('Selected line changed during execution')
    match = ROW.match(lines[idx].rstrip('\r\n'))
    if match is None or match['state'] != ' ' or match['id'] != task.task_id:
        raise ValueError('Selected task is no longer unchecked')
    state_pos = match.start('state')
    lines[idx] = lines[idx][:state_pos] + new_state + lines[idx][state_pos + 1:]
    return ''.join(lines)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(['git', '-C', str(WORKTREE), *args], text=True).rstrip('\n')


def tracked_state() -> dict[str, str]:
    """Content-and-index-sensitive snapshot, including untracked (not ignored) files."""
    status = git('status', '--porcelain=v1', '--untracked-files=all')
    paths = [line[3:] for line in status.splitlines()]
    # Digest the index and worktree differences from HEAD (including staged edits).
    diff = subprocess.check_output(['git', '-C', str(WORKTREE),
                                    'diff', '--binary', 'HEAD', '--'])
    result = {'!git-diff': sha(diff), '!status': sha(status.encode())}
    for name in paths:
        f = WORKTREE / name
        if f.is_symlink():
            result[name] = 'link:' + sha(os.readlink(f).encode())
        elif f.is_file():
            result[name] = 'file:' + sha(f.read_bytes())
        elif f.exists():
            result[name] = 'other'
        else:
            result[name] = 'deleted'
    return result


def repo_state() -> tuple:
    return (git('rev-parse', 'HEAD'), git('branch', '--show-current'),
            tuple(line[3:] for line in git('status', '--short', '--untracked-files=all').splitlines()),
            tracked_state())


def changed_files(before: tuple, after: tuple) -> set[str]:
    a, b = before[3], after[3]
    files = {p for p in set(a) | set(b) if not p.startswith('!') and a.get(p) != b.get(p)}
    if before[0] != after[0]:
        files.update(git('diff', '--name-only', f'{before[0]}..{after[0]}').splitlines())
    return files


def cycle_read() -> dict | None:
    if not CYCLE_FILE.exists():
        return None
    value = json.loads(CYCLE_FILE.read_text())
    if not isinstance(value, dict) or value.get('version') != 1:
        raise RuntimeError(f'Invalid cycle state: {CYCLE_FILE}')
    return value


def cycle_write(value: dict) -> None:
    CYCLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f'.{PROJECT_ID}-cycle-', dir=CYCLE_FILE.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, CYCLE_FILE)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def stash_ref(oid: str) -> str:
    rows = git('stash', 'list', '--format=%gd %H').splitlines()
    refs = [row.split(' ', 1)[0] for row in rows if row.split(' ', 1)[-1] == oid]
    if len(refs) != 1:
        raise RuntimeError(f'Saved stash {oid} not found uniquely; recovery required')
    return refs[0]


def cycle_begin(task: Task) -> None:
    state = cycle_read()
    if state:
        if state['phase'] != 'active':
            raise RuntimeError(f'Cycle recovery required, phase={state["phase"]}: {CYCLE_FILE}')
        if git('branch', '--show-current') != state['branch']:
            raise RuntimeError('Cycle branch changed; refusing to continue')
        if git('rev-parse', 'HEAD') != state['head']:
            raise RuntimeError('Unexpected commit during active cycle')
        if tracked_state() != state['snapshot']:
            raise RuntimeError('Repository changed outside prior completed task; refusing to continue')
        return
    if task.kind != 'EDIT':
        # READ/VERIFY before the first EDIT is okay, but TEST/COMMIT without an
        # established EDIT cycle is not safe to recover automatically.
        if task.kind == 'COMMIT':
            raise RuntimeError('COMMIT without an active EDIT cycle; manual review required')
        # A standalone TEST is permitted, but must leave Git state unchanged.
        return
    branch, head = git('branch', '--show-current'), git('rev-parse', 'HEAD')
    token = uuid.uuid4().hex
    message = f'{PROJECT_ID}-worker-{token}'
    record = dict(version=1, phase='preparing', branch=branch, head=head,
                  token=token, stash_message=message, stash_oid=None,
                  allowed=[], snapshot={}, last_task=None)
    cycle_write(record)   # journal before mutating Git
    try:
        if git('status', '--porcelain=v1', '--untracked-files=all'):
            subprocess.run(['git', '-C', str(WORKTREE), 'stash', 'push', '-u', '-m', message], check=True)
            entries = git('stash', 'list', '--format=%H %s').splitlines()
            candidates = [entry.split(' ', 1)[0] for entry in entries if message in entry]
            if len(candidates) != 1:
                raise RuntimeError('Could not uniquely identify newly-created stash')
            record['stash_oid'] = candidates[0]
        if git('status', '--porcelain=v1', '--untracked-files=all'):
            raise RuntimeError('Repository still dirty after stashing; inspect ignored files and Git state')
        record['phase'] = 'active'
        record['snapshot'] = tracked_state()
        cycle_write(record)
    except Exception:
        # Leave the preparation journal in place, even if stash succeeded:
        # a human must decide whether it can be safely restored.
        raise


def cycle_approved(task: Task, before: tuple, after: tuple) -> None:
    record = cycle_read()
    if not record or record['phase'] != 'active':
        return
    if task.kind in {'EDIT', 'TEST'}:
        record['allowed'] = sorted(set(record['allowed']) | changed_files(before, after))
    record['snapshot'] = after[3]
    record['last_task'] = task.task_id
    cycle_write(record)


def allowed_test_file(name: str) -> bool:
    """Only configured test Python file patterns are permitted for TEST changes."""
    patterns = PROJECT.get('test_file_patterns', ['scripts/test_*.py'])
    if (not isinstance(patterns, list) or not patterns or
        any(not isinstance(p, str) or not p or p.startswith('/') or '..' in Path(p).parts or
            not p.endswith('.py') for p in patterns)):
        raise ValueError('Invalid project test_file_patterns configuration')
    if not name.endswith('.py') or name.startswith('/') or '..' in Path(name).parts:
        return False
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def cycle_record_failed_test(task: Task, before: tuple, after: tuple, original_queue: bytes) -> bool:
    """Journal test-only artifacts after failure; never advance the queue.

    The active-cycle snapshot must still match the initial state. This function
    is called only after the worker has exited and while holding the worker lock.
    Any production edit, new commit, branch change, or unexpected Git metadata
    change leaves the snapshot unchanged and requires manual investigation.
    """
    if task.kind != 'TEST':
        return False
    record = cycle_read()
    if not record or record.get('phase') != 'active':
        return False
    if before[0] != after[0] or before[1] != after[1]:
        return False
    if record['head'] != before[0] or record['branch'] != before[1]:
        return False
    if record['snapshot'] != before[3]:
        return False
    if QUEUE.read_bytes() != original_queue:
        return False
    changed = changed_files(before, after)
    if not changed:
        return False
    if any(not allowed_test_file(name) for name in changed):
        return False
    # Do not journal potentially malicious symlinks or unusual file types.
    if any((WORKTREE / name).is_symlink() or
           ((WORKTREE / name).exists() and not (WORKTREE / name).is_file())
           for name in changed):
        return False
    # Confirm that all per-path snapshot changes are accounted for.
    actual = {name for name in set(before[3]) | set(after[3])
              if not name.startswith('!') and before[3].get(name) != after[3].get(name)}
    if actual != changed:
        return False
    record['allowed'] = sorted(set(record['allowed']) | changed)
    record['snapshot'] = after[3]
    record['last_failed_task'] = task.task_id
    cycle_write(record)
    return True


def cycle_commit_precheck() -> None:
    record = cycle_read()
    if not record or record['phase'] != 'active':
        raise RuntimeError('No active cycle for COMMIT')
    dirty = set(repo_state()[2])
    extra = dirty - set(record['allowed'])
    if extra:
        raise RuntimeError(f'Unapproved dirty paths before COMMIT: {sorted(extra)}')


def cycle_finish_commit(before: tuple, after: tuple) -> None:
    record = cycle_read()
    if not record or record['phase'] != 'active':
        raise RuntimeError('Missing active cycle after commit')
    committed_paths = set(git('diff', '--name-only', f'{before[0]}..{after[0]}').splitlines())
    extra = committed_paths - set(record['allowed'])
    if extra:
        raise RuntimeError(f'Commit includes unapproved paths: {sorted(extra)}')
    if git('status', '--porcelain=v1', '--untracked-files=all'):
        raise RuntimeError('COMMIT left uncommitted changes; original stash not restored')
    record['phase'] = 'restoring'
    record['committed_head'] = after[0]
    cycle_write(record)
    if record['stash_oid']:
        # Fail closed on any conflict. Do not use pop (which obscures recovery).
        subprocess.run(['git', '-C', str(WORKTREE), 'stash', 'apply', '--index', record['stash_oid']], check=True)
        record['phase'] = 'restored'
        cycle_write(record)
        subprocess.run(['git', '-C', str(WORKTREE), 'stash', 'drop', stash_ref(record['stash_oid'])], check=True)
    CYCLE_FILE.unlink()

def prompt_for(task: Task, result_path: Path) -> str:
    cycle = cycle_read()

    if task.kind == 'TEST':
        if cycle is not None and cycle.get('phase') == 'active':
            paths = PROJECT.get('test_file_patterns', ['scripts/test_*.py'])
            if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
                raise ValueError('Invalid test_file_patterns')
            test_instructions = (
                "This TEST task belongs to an ACTIVE EDIT → TEST → COMMIT cycle. "
                f"You may create or modify ONLY Python test files matching {paths!r}; "
                "do not modify production code or commit. "
                "Run the focused tests with /usr/bin/python3 and report the result. "
                "Do not generate __pycache__ or .pyc artifacts."
            )
        else:
            test_instructions = (
                "This is a STANDALONE TEST task. Do not modify repository files "
                "or create commits. Execute existing tests only."
            )
    else:
        test_instructions = ""

    return f'''You are executing a single, self-contained software maintenance assignment.
Repository working directory: {WORKTREE}
Assignment: {task.task_id} — {task.kind}: {task.description}

Perform only this assignment. When finished, stop. Do not choose additional work.
For READ, VERIFY, or DECIDE assignments, do not modify repository files or create commits.
{test_instructions}
For EDIT assignments, do not create commits unless explicitly required by this assignment.
For TEST assignments involving subprocesses, use unittest.mock in a repository-owned test file. Run the test with the normal Python test runner. Never launch the real acquisition process, and do not use inline Python execution. If a security scanner blocks a command, do not bypass it.
For COMMIT assignments, commit only the already-validated intended changes; do not invent new features.
If the assignment is already satisfied, verify it and report it as already_done.
If blocked, report blocked; do not claim success.

Write your completion report as a UTF-8 JSON file using your file-writing tool at this EXACT absolute path:
{result_path}
The JSON file MUST contain one JSON object with these keys:
{{"task_id":"{task.task_id}","status":"completed|already_done|blocked|failed","summary":"one sentence","verification":"what you observed or tested","blocker":"reason or empty string"}}
Use a single actual status value, not the pipe-separated template. All other values must be JSON strings.
Write this file once after completing the assignment (including when already done, blocked, or failed).
Do not merely print the JSON in your final reply: the report FILE is required.
After saving the report, end your response and do not begin another assignment.

For Python tests, use /usr/bin/python3 -B rather than python.
Never generate Python bytecode or __pycache__ directories.
Ubuntu system packages, including Jinja2, are available through this interpreter.

For COMMIT assignments, inspect all uncommitted changes in the repository before deciding the task is already done. Include the validated tests associated with the current assignment. If implementation changes were previously committed but validated test changes remain, commit those tests. Never use git add -A; stage only explicitly reviewed relevant files.
'''


def parse_result(stdout: str, task_id: str) -> dict:
    """Find the last *valid* task-result JSON embedded in Hermes CLI output.

    Hermes prints a banner, tool summaries and a session footer after the final
    response.  Validate each JSON candidate rather than requiring EOF after it,
    and never interpret the JSON template in the echoed assignment as a result.
    """
    decoder = json.JSONDecoder()
    valid = []
    for match in re.finditer(r"\{", stdout):
        try:
            obj, _ = decoder.raw_decode(stdout, match.start())
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get('task_id') != task_id:
            continue
        if obj.get('status') not in {'completed', 'already_done', 'blocked', 'failed'}:
            continue
        if any(not isinstance(obj.get(key), str) for key in ('summary', 'verification', 'blocker')):
            continue
        valid.append(obj)
    if not valid:
        raise ValueError('No valid task-result JSON found in Hermes output')
    return valid[-1]


def verify(task: Task, response: dict, before: tuple, after: tuple) -> tuple[bool, str]:
    if response['status'] not in {'completed', 'already_done'}:
        return False, response['blocker'] or response['status']
    if not response['verification'].strip():
        return False, 'Empty verification'
    files = changed_files(before, after)
    committed = before[0] != after[0]
    if task.kind in {'READ', 'VERIFY', 'DECIDE'} and (files or committed):
        return False, f'{task.kind} scope violation: repository changes/commit: {sorted(files)}'
    if task.kind == 'TEST':
        if committed or any(not allowed_test_file(f) for f in files):
            return False, f'TEST scope violation: commit or non-test-file changes: {sorted(files)}'
    if task.kind == 'EDIT' and committed:
        return False, 'EDIT scope violation: created commit'
    if task.kind == 'COMMIT' and response['status'] == 'completed' and not committed:
        return False, 'COMMIT task reported completed without a new commit'
    if task.kind == 'EDIT' and response['status'] == 'completed' and not files:
        return False, 'EDIT reported completed without any repository change'
    # This checks structural evidence and declared verification, not semantic correctness.
    return True, 'Verification report received and operation scope checks passed'


def atomic_write(path: Path, text: str) -> None:
    fd, name = tempfile.mkstemp(prefix=f'.{PROJECT_ID}-queue-update-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run_agent(prompt: str, log) -> tuple[int, str]:
    from project_queue_manager import provider_argv
    cmd, _ = provider_argv(PROJECT, 'worker')
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    proc = subprocess.Popen(cmd, cwd=WORKTREE, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=log, start_new_session=True, text=True, env=env)
    try:
        output, _ = proc.communicate(input=prompt, timeout=TIMEOUT)
        return proc.returncode, output
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
        raise TimeoutError(f'Worker exceeded {TIMEOUT} seconds')


def deliver(message: str, log) -> bool:
    result = subprocess.run([HERMES, 'send', '--to', 'telegram', '--quiet'],
                            input=message, stdout=log, stderr=subprocess.STDOUT,
                            text=True, timeout=60)
    return result.returncode == 0



def notification_footer() -> str:
    """Append live HA Codex quota and authoritative task queue count."""
    import urllib.request
    import urllib.error

    usage = 'unavailable'
    try:
        env = {}
        for line in (HERMES_HOME / 'secrets/ha.env').read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[7:].strip()
            key, sep, value = line.partition('=')
            if sep and key.strip() in {'HA_URL', 'HA_TOKEN'}:
                env[key.strip()] = value.strip().strip("\\\"'")

        url = env['HA_URL'].rstrip('/') + (
            '/api/states/sensor.codex_usage_weekly_remaining'
        )
        request = urllib.request.Request(
            url,
            headers={'Authorization': 'Bearer ' + env['HA_TOKEN']}
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            remaining = float(json.load(response)['state'])
        usage = f'{remaining:g}%'
    except (OSError, KeyError, TypeError, ValueError,
            urllib.error.URLError):
        pass

    count = sum(
        line.lstrip().startswith('- [ ]')
        for line in QUEUE.read_text(encoding='utf-8').splitlines()
    )
    return (
        f'Codex usage remaining: {usage}\n'
        f'Tasks remaining in queue: {count}'
    )

def process_once(*, dry_run=False, no_telegram=False) -> int:
    global CURRENT_TASK_KIND, LOCK_CONTENDED
    LOCK_CONTENDED = False
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+') as lk, RUN_LOG.open('a', encoding='utf-8') as log:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            LOCK_CONTENDED = True
            print('Another project worker is already running', file=log, flush=True)
            return 1
        from pw_worker_journal import (journal_path, inspect as inspect_journal,
                                           read as read_journal, start as journal_start,
                                           phase as journal_phase, finalize as journal_finalize,
                                           clear_reviewed as journal_clear_reviewed)
        from pw_worker_progress import record_completed, state_path as progress_state_path
        journal_file = journal_path(PROJECT, PROJECT_CONFIG)
        progress_file = progress_state_path(PROJECT, PROJECT_CONFIG)
        # Hand recovery its own project lock before selecting any new task.
        # Avoid a subprocess/AI call on the normal (journal-clear) path.
        if not dry_run:
            journal_path = PROJECT_CONFIG.parent / 'worker_journal.json'
            if journal_path.exists():
                try:
                    journal_doc = json.loads(journal_path.read_text(encoding='utf-8'))
                except (OSError, ValueError) as exc:
                    print(f'RECOVERY BLOCKED: unreadable journal: {exc}', file=sys.stderr)
                    return 2
                if not isinstance(journal_doc, dict):
                    print('RECOVERY BLOCKED: invalid journal document', file=sys.stderr)
                    return 2
                if journal_doc.get('current_task') is not None:
                    recovery_script = Path(__file__).resolve().parent / 'pw_recovery.py'
                    if not recovery_script.is_file():
                        print('RECOVERY BLOCKED: packaged pw_recovery.py missing', file=sys.stderr)
                        return 2
                    fcntl.flock(lk, fcntl.LOCK_UN)
                    try:
                        recovery_result = subprocess.run(
                            [sys.executable, str(recovery_script), '--project', PROJECT_ID, '--record'],
                            capture_output=True, text=True, timeout=45, check=False,
                        )
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        print(f'RECOVERY BLOCKED: recovery invocation error: {exc}', file=sys.stderr)
                        return 2
                    finally:
                        # Own the lock again before reading/relying on project state.
                        fcntl.flock(lk, fcntl.LOCK_EX)
                    try:
                        recovery_report = json.loads(recovery_result.stdout)
                    except ValueError:
                        print('RECOVERY BLOCKED: invalid recovery response; ' + recovery_result.stderr.strip(), file=sys.stderr)
                        return 2
                    # Current recovery implementation inspects and records; it does NOT repair.
                    # Continue only when the journal was actually cleared and recovery said clear.
                    refreshed = json.loads(journal_path.read_text(encoding='utf-8'))
                    if (recovery_result.returncode != 0 or
                            recovery_report.get('status') != 'clear' or
                            refreshed.get('current_task') is not None):
                        print('RECOVERY BLOCKED: ' + json.dumps(recovery_report, sort_keys=True),
                              file=sys.stderr)
                        return 2
        original_bytes = QUEUE.read_bytes()
        original = original_bytes.decode('utf-8')
        # Refuse to run on the old truncated-queue isolation artifact.
        if 'ISOLATED WORKER RUN' in original or QUEUE.with_name(QUEUE.name + '.single-task-original').exists():
            raise RuntimeError('Previous queue isolation not fully restored. Refusing to run.')
        existing = inspect_journal(journal_file, original, ROW,
                                   git('rev-parse', 'HEAD'),
                                   sha(repr(repo_state()).encode()),
                                   cycle_read() is not None)
        if existing['outcome'] == 'reconcile_count':
            record_completed(progress_file, existing['task_id'])
            journal_finalize(journal_file, existing['task_id'])
            print('Reconciled verified previous completion: ' + existing['task_id'], file=log, flush=True)
        elif existing['outcome'] == 'review':
            print('Previous task requires manual review: ' + json.dumps(existing, sort_keys=True), file=sys.stderr)
            return 4
        task = pick_task(original)
        if task is None:
            print('No unchecked tasks', file=log, flush=True)
            return 0
        if dry_run:
            print(f'{task.task_id} — {task.kind}: {task.description}')
            return 0
        from pw_quota import evaluate
        quota = evaluate(PROJECT.get('quota', {}))
        if not quota['allowed']:
            print('Quota gate BLOCKED: ' + json.dumps(quota, sort_keys=True), file=log, flush=True)
            print('Quota gate BLOCKED: ' + json.dumps(quota, sort_keys=True), file=sys.stderr)
            return 3
        cycle_begin(task)
        if task.kind == 'COMMIT':
            cycle_commit_precheck()
        before = repo_state()
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        result_prefix = RESULT_DIR / f'{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}_{task.task_id}'
        journal_start(journal_file, task, original_bytes, before[0],
                      sha(repr(before).encode()), result_prefix)
        journal_phase(journal_file, task.task_id, 'running')
        print(f'{datetime.now().isoformat(timespec="seconds")} START {task.task_id}: {task.description}', file=log, flush=True)
        result = None
        reason = ''
        rc = -1
        output = ''
        try:
            report_path = result_prefix.with_suffix('.json')
            if report_path.exists():
                raise RuntimeError(f'Report path unexpectedly exists: {report_path}')
            CURRENT_TASK_KIND = task.kind
            rc, output = run_agent(prompt_for(task, report_path), log)
            result_prefix.with_suffix('.raw.txt').write_text(output, encoding='utf-8')
            if not report_path.is_file() or report_path.is_symlink():
                raise ValueError(f'Hermes did not write a regular JSON result file: {report_path}')
            if report_path.stat().st_size > 65536:
                raise ValueError('Hermes JSON report exceeds 64 KiB')
            result = json.loads(report_path.read_text(encoding='utf-8'))
            if (not isinstance(result, dict) or result.get('task_id') != task.task_id
                    or result.get('status') not in {'completed', 'already_done', 'blocked', 'failed'}
                    or any(not isinstance(result.get(k), str) for k in ('summary', 'verification', 'blocker'))):
                raise ValueError('Hermes result file is missing required valid fields')
            after = repo_state()
            ok, reason = verify(task, result, before, after)
            if task.kind == 'TEST' and cycle_read() is None and before != after:
                ok = False
                reason = 'Standalone TEST modified repository state; manual review required'
            if rc != 0:
                ok, reason = False, f'Hermes exited {rc}; {reason}'
            if QUEUE.read_bytes() != original_bytes:
                ok, reason = False, 'Task file changed unexpectedly during execution; it was NOT overwritten'
            if ok and task.kind == 'COMMIT' and after[0] == before[0]:
                ok, reason = False, 'COMMIT did not create a new commit; cycle remains active'
            if ok and task.kind == 'COMMIT' and after[0] != before[0]:
                cycle_finish_commit(before, after)
            elif ok and not (task.kind == 'TEST' and cycle_read() is None):
                cycle_approved(task, before, after)
            # Task status is advanced only after the deterministic work log is persisted.
        except Exception as exc:
            ok = False
            reason = f'{type(exc).__name__}: {exc}'
            # Retain the raw response even when parsing fails.
            raw_path = result_prefix.with_suffix('.raw.txt')
            if not raw_path.exists():
                raw_path.write_text(output, encoding='utf-8')
            result_prefix.with_suffix('.error.txt').write_text(reason + '\n', encoding='utf-8')
        # An unsuccessful TEST may have created a valid test file. Preserve it
        # across retries only if ALL changes are confined to approved test paths.
        # Do not change the task checkbox; any other changes remain blocked.
        if not ok and task.kind == 'TEST':
            try:
                failure_after = repo_state()
                if cycle_record_failed_test(task, before, failure_after, original_bytes):
                    print(f'{task.task_id}: journaled test-only changes for safe retry',
                          file=log, flush=True)
            except Exception as recovery_exc:
                print(f'{task.task_id}: failed-test journal error: {recovery_exc}',
                      file=log, flush=True)
        print(f'Worker response files: {result_prefix}.*', file=log, flush=True)
        report_after = locals().get('after', repo_state())
        status = 'COMPLETE' if ok else 'FAILED'
        status_icon = '✅' if ok else '🚨'
        summary = result['summary'] if result else 'No trustworthy completion result.'
        verification = result['verification'] if result else 'No verified result.'
        files = sorted(changed_files(before, report_after))
        following = pick_task(update_selected_only(original, task, 'x') if ok else original)
        next_label = f'{following.task_id} — {following.kind}: {following.description}' if following else 'All tasks complete'
        msg = (f'{status_icon} {PROJECT["display_name"]} worker\n'
               f'Task: {task.task_id} — {task.kind}: {task.description}\n'
               f'Result: {status}: {summary}\n'
               f'Verification: {verification}\n'
               f'Changed: commit {report_after[0][:12] if report_after[0] != before[0] else "none"}; files {", ".join(files) or "none"}\n'
               f'Blocker: {reason if not ok else "None"}\n'
               f'Next: {next_label}\n')
        timestamp = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
        entry = (f'\n## {timestamp} — {task.task_id} {status}\n'
                 f'- Task: {task.task_id} — {task.kind}: {task.description}\n'
                 f'- Result: {status}: {summary}\n'
                 f'- Verification: {verification}\n'
                 f'- Changed: {", ".join(files) or "none"}; commit {after[0][:12] if after[0] != before[0] else "none"}\n'
                 f'- Blocker: {reason if not ok else "None"}\n')
        with WORK_LOG.open('a', encoding='utf-8') as f:
            f.write(entry)
            f.flush()
            os.fsync(f.fileno())
        if ok:
            # Never overwrite concurrent changes or modify any other task.
            if QUEUE.read_bytes() != original_bytes:
                print('Queue changed after verification; checkbox NOT updated', file=log, flush=True)
                return 1
            journal_phase(journal_file, task.task_id, 'verified',
                          git_head_after=report_after[0],
                          verification=verification,
                          report_path=str(result_prefix.with_suffix('.json')))
            atomic_write(QUEUE, update_selected_only(original, task, 'x'))
            # Record only a verified, persisted completion. The project lock is held.
        if ok:
            record_completed(progress_file, task.task_id)
            journal_finalize(journal_file, task.task_id)
        else:
            journal_phase(journal_file, task.task_id, 'needs_review', reason=reason)
        print(f'{timestamp} {task.task_id}: {status}; {reason}', file=log, flush=True)
        # Release the project lock before publishing notes.
        # The standalone sync utility acquires the same lock independently.
        # Publishing failures must never invalidate a completed task.
        fcntl.flock(lk, fcntl.LOCK_UN)
        if PROJECT.get("notes", {}).get("mirrors"):
            try:
                sync_script = Path(__file__).resolve().parent / "project_notes_sync.py"
                sync_result = subprocess.run(
                    [
                        sys.executable,
                        str(sync_script),
                        "--project", PROJECT_ID,
                        "--publish",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if sync_result.returncode:
                    print(
                        "WARNING: Notes synchronization failed: "
                        + (sync_result.stderr or sync_result.stdout).strip(),
                        file=log,
                        flush=True,
                    )
                    print(
                        "WARNING: Notes synchronization failed; "
                        "project task result was preserved.",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "Notes synchronization: "
                        + sync_result.stdout.strip(),
                        file=log,
                        flush=True,
                    )
            except Exception as exc:
                print(
                    f"WARNING: Notes synchronization error: {exc}",
                    file=log,
                    flush=True,
                )

        if not no_telegram:
            if not deliver(msg.rstrip() + '\n\n' + notification_footer() + '\n', log):
                return 1
        return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, help='Project ID in selected projects directory')
    parser.add_argument('--config-dir', type=Path, help='Projectwright configuration home')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--quota-check', action='store_true', help='Check quota without executing tasks')
    parser.add_argument('--no-telegram', action='store_true')
    parser.add_argument('--journal-status', action='store_true')
    parser.add_argument('--authorize-retry', metavar='TASK_ID')
    parser.add_argument('--detached', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.config_dir is not None:
        if not args.config_dir.is_absolute(): parser.error('--config-dir must be absolute')
        os.environ['PROJECTWRIGHT_CONFIG_DIR'] = str(args.config_dir)
    # An unconfigured project is inert. Never infer a worktree, provider or
    # authorization from the surrounding user's Hermes installation.
    from pw_dispatch import default_project_root
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', args.project):
        parser.error('Invalid project ID')
    from pw_config import load as load_config
    config_file, effective = load_config(args.project)
    config_free = not config_file.is_file()
    if config_free:
        from pw_config import ready_for_config_free_worker
        if not (args.once or args.dry_run) or not ready_for_config_free_worker(effective):
            print(json.dumps({'project': args.project, 'decision': 'disabled',
                              'reason': 'project config missing'}))
            return 3
    if effective.get('projectwright_initialized') == 1 and effective['execution']['enabled'] is False:
        print(json.dumps({'project': args.project, 'decision': 'disabled',
                          'reason': 'project not configured for execution'}))
        return 3
    load_project(args.project)
    if config_free:
        args.no_telegram = True  # no implicit external delivery without configuration
    if args.journal_status or args.authorize_retry:
        from pw_worker_journal import (journal_path, read as journal_read,
                                            clear_reviewed as journal_clear_reviewed)
        path = journal_path(PROJECT, PROJECT_CONFIG)
        if args.journal_status:
            print(json.dumps(journal_read(path), indent=2, sort_keys=True))
            return 0
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        with LOCK.open('a+') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
            journal_clear_reviewed(path, args.authorize_retry,
                                   QUEUE.read_text(encoding='utf-8'), ROW,
                                   git('rev-parse', 'HEAD'),
                                   sha(repr(repo_state()).encode()),
                                   cycle_read() is not None)
        print('Retry authorized for ' + args.authorize_retry)
        return 0
    if args.quota_check:
        from pw_quota import evaluate
        result = evaluate(PROJECT.get('quota', {}))
        print(json.dumps(result, sort_keys=True))
        return 0 if result['allowed'] else 3
    if args.dry_run:
        return process_once(dry_run=True)
    if args.once or args.detached:
        rc = process_once(no_telegram=args.no_telegram)
        # No task ran; do not invoke the queue manager or attempt to publish
        # progress while another process holds the project lock.
        if LOCK_CONTENDED:
            return rc
        if rc == 0 and not config_free and os.environ.get('PROJECTWRIGHT_DISPATCHED') != '1':
            # process_once has released its project lock before returning.
            # Never plan inside an active EDIT/TEST/COMMIT Git cycle.
            if CYCLE_FILE.exists():
                print('Queue manager skipped: active Git cycle', file=sys.stderr)
            else:
                manager = Path(__file__).resolve().parent / 'project_queue_manager.py'
                if not manager.is_file():
                    print('Queue manager unavailable: script missing', file=sys.stderr)
                    rc = 5
                else:
                    try:
                        manager_result = subprocess.run(
                            [sys.executable, str(manager), '--project', PROJECT_ID, '--once'],
                            capture_output=True, text=True, timeout=900, check=False,
                        )
                        if manager_result.stdout.strip():
                            print('Queue manager: ' + manager_result.stdout.strip())
                        if manager_result.stderr.strip():
                            print('Queue manager stderr: ' + manager_result.stderr.strip(), file=sys.stderr)
                        if manager_result.returncode:
                            print(f'Queue manager exited {manager_result.returncode}', file=sys.stderr)
                            rc = 5
                        else:
                            try:
                                manager_decision = json.loads(manager_result.stdout)
                                if manager_decision.get('decision') in ('planner_failed', 'blocked', 'busy', 'quota_blocked'):
                                    print('Queue manager did not plan: ' + str(manager_decision.get('reason', manager_decision['decision'])), file=sys.stderr)
                                    if manager_decision['decision'] == 'planner_failed':
                                        rc = 5
                            except (ValueError, TypeError, AttributeError):
                                print('Queue manager returned invalid JSON', file=sys.stderr)
                                rc = 5
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        print(f'Queue manager invocation failed: {exc}', file=sys.stderr)
                        rc = 5
        # Publishing is best-effort and must never change a task's result.
        try:
            from pw_notes_publisher import publish
            import fcntl as _fcntl
            with LOCK.open('a+') as _publication_lock:
                _fcntl.flock(_publication_lock, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                publish(PROJECT, PROJECT_CONFIG)
        except Exception as _publish_error:
            print(f'Progress note publish failed: {_publish_error}', file=sys.stderr)
        return rc
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open('a', encoding='utf-8') as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--project', PROJECT_ID, '--detached'],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
