#!/usr/bin/env python3
"""Conservative project task recovery inspector.

Read-only by default. --record writes only recovery_incidents.json under
~/.hermes/projects/<id>. No Git, queue, or journal mutation.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone

ID_RE = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
TASK_RE = re.compile(r'^\s*- \[(?P<state>[ x!])\] \*\*(?P<id>[A-Z]+\d+)\s+[—-]\s+(?P<kind>[A-Z]+)\*\*')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_of(value: str) -> Path:
    return Path(value).expanduser()


def project_config(project: str, root: Path) -> tuple[Path, dict]:
    if not ID_RE.fullmatch(project):
        raise ValueError('Invalid project ID')
    directory = root / project
    cfg = json.loads((directory / 'config.json').read_text())
    if cfg.get('id') != project:
        raise ValueError('Project configuration ID mismatch')
    for k in ('queue', 'worktree', 'cycle_file', 'lock'):
        if not isinstance(cfg.get(k), str):
            raise ValueError(f'Missing config key: {k}')
    return directory, cfg


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, timeout=15).strip()


def evidence(directory: Path, cfg: dict) -> dict:
    journal_path = directory / 'worker_journal.json'
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else {'current_task': None}
    task = journal.get('current_task')
    if not task:
        return {'status': 'clear', 'reason': 'No active task journal', 'task_id': None}
    tid = task.get('id')
    if not isinstance(tid, str) or not re.fullmatch(r'[A-Z]+\d+', tid):
        return {'status': 'needs_review', 'reason': 'Invalid journal task ID', 'task_id': tid}
    queue_path = path_of(cfg['queue'])
    queue = queue_path.read_bytes()
    matches = []
    for line in queue.decode('utf-8').splitlines():
        match = TASK_RE.match(line)
        if match and match['id'] == tid:
            matches.append({'state': match['state'], 'kind': match['kind'], 'line': line})
    repo = path_of(cfg['worktree'])
    head = git(repo, 'rev-parse', 'HEAD')
    status = git(repo, 'status', '--porcelain=v1', '--untracked-files=all')
    cycle_present = path_of(cfg['cycle_file']).exists()
    original_head = task.get('git_head_before')
    unchanged_head = head == original_head
    original_queue_hash = task.get('queue_sha256_before')
    queue_unchanged = digest(queue) == original_queue_hash
    result = {
        'status': 'needs_review', 'task_id': tid, 'phase': task.get('phase'),
        'queue_entries': len(matches), 'queue_states': [x['state'] for x in matches],
        'head_unchanged': unchanged_head, 'working_tree_clean': not bool(status),
        'active_git_cycle': cycle_present, 'queue_unchanged': queue_unchanged,
        'result_prefix': task.get('result_prefix'),
    }
    if len(matches) != 1:
        result['reason'] = 'Queue has missing or duplicate task ID; manual review required'
    elif cycle_present:
        result['reason'] = 'Active EDIT/TEST/COMMIT cycle requires manual review'
    elif not unchanged_head or status:
        result['reason'] = 'Repository changed relative to journal; manual review required'
    elif task.get('phase') in ('running', 'selected'):
        result['reason'] = 'Interrupted task; result must be independently verified before retry'
    elif task.get('phase') == 'verified' and matches[0]['state'] == 'x':
        # Safe candidate only; journal reconciliation belongs to established worker journal module.
        result['status'] = 'reconciliation_candidate'
        result['reason'] = 'Checked task and verified journal; validate result report before reconciliation'
    else:
        result['reason'] = 'Journal/queue phase mismatch; manual review required'
    return result


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def record_incident(directory: Path, result: dict) -> dict:
    path = directory / 'recovery_incidents.json'
    doc = json.loads(path.read_text()) if path.exists() else {'schema_version': 1, 'incidents': []}
    if result['status'] == 'clear':
        return {'recorded': False, 'reason': 'No active incident'}
    # Avoid a new incident / counter bump from identical repeated cron checks.
    signature = digest(json.dumps(result, sort_keys=True).encode())
    for incident in doc['incidents']:
        if incident.get('signature') == signature and incident.get('status') == 'open':
            return {'recorded': False, 'reason': 'Identical incident already open', 'incident_id': incident['id']}
    item = {'id': 'INC-' + signature[:12], 'signature': signature, 'status': 'open',
            'first_seen': datetime.now(timezone.utc).isoformat(), 'ai_attempts': 0,
            'evidence': result}
    doc['incidents'].append(item)
    atomic_json(path, doc)
    return {'recorded': True, 'incident_id': item['id']}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--config-root', type=Path, default=Path.home() / '.hermes/projects')
    parser.add_argument('--record', action='store_true', help='Record incident if needed; never change worker state')
    args = parser.parse_args()
    directory, cfg = project_config(args.project, args.config_root.expanduser())
    if args.record:
        lock_path = path_of(cfg['lock'])
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('a+') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(json.dumps({'status': 'busy', 'reason': 'Worker holds project lock'}))
                return 2
            result = evidence(directory, cfg)
            result['incident_record'] = record_incident(directory, result)
    else:
        result = evidence(directory, cfg)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['status'] == 'clear' else 3


if __name__ == '__main__':
    raise SystemExit(main())
