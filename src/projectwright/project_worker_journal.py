"""Conservative single-task execution journal. Caller holds project lock.

This journal is not the Git EDIT/TEST/COMMIT cycle authority.
"""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def journal_path(config: dict, config_path: Path) -> Path:
    return Path(config.get('worker_journal_file', str(config_path.parent / 'worker_journal.json'))).expanduser()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read(path: Path) -> dict:
    if not path.exists():
        return {'schema_version': 1, 'current_task': None, 'last_completed_task': None}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise RuntimeError('Unknown worker journal schema; manual review required')
    if 'current_task' not in data:
        raise RuntimeError('Malformed worker journal; manual review required')
    return data


def start(path: Path, task, queue_bytes: bytes, head: str, state_digest: str, result_prefix: Path) -> None:
    data = read(path)
    if data['current_task'] is not None:
        raise RuntimeError('Unresolved previous task; manual review required')
    data['current_task'] = {
        'id': task.task_id, 'kind': task.kind, 'line': task.raw_line,
        'phase': 'selected', 'started_at': stamp(), 'git_head_before': head,
        'repository_digest_before': state_digest,
        'queue_sha256_before': digest(queue_bytes),
        'result_prefix': str(result_prefix),
    }
    atomic_json(path, data)


def phase(path: Path, task_id: str, value: str, **extra) -> None:
    if value not in {'running', 'verified', 'needs_review'}:
        raise ValueError('Invalid journal phase')
    data = read(path)
    current = data['current_task']
    if current is None or current['id'] != task_id:
        raise RuntimeError('Journal task identity mismatch')
    current.update(extra)
    current['phase'] = value
    current['updated_at'] = stamp()
    atomic_json(path, data)


def _queue_state(queue_text: str, current: dict, row_re) -> str:
    matches = [m for line in queue_text.splitlines() if (m := row_re.match(line)) and m['id'] == current['id']]
    if len(matches) != 1:
        return 'missing_or_duplicate'
    match = matches[0]
    if match['kind'] != current['kind']:
        return 'changed'
    expected = current['line']
    if match['state'] == ' ' and match.group(0) == expected:
        return 'unchecked_original'
    checked = expected.replace('- [ ]', '- [x]', 1)
    if match['state'] == 'x' and match.group(0) == checked:
        return 'checked_original'
    return 'changed'


def inspect(path: Path, queue_text: str, row_re, head: str, repo_digest: str, cycle_present: bool) -> dict:
    data = read(path)
    c = data['current_task']
    if c is None:
        return {'outcome': 'clear'}
    qs = _queue_state(queue_text, c, row_re)
    same_repo = repo_digest == c['repository_digest_before'] and head == c['git_head_before']
    # Finalization recovery requires a previously persisted verified result.
    # A COMMIT intentionally changes HEAD and has its own cycle journal; refuse
    # automatic reconciliation for it until its full evidence is reviewed.
    if (c['phase'] == 'verified' and qs == 'checked_original'
            and c['kind'] != 'COMMIT' and not cycle_present
            and same_repo):
        return {'outcome': 'reconcile_count', 'task_id': c['id']}
    return {'outcome': 'review', 'task_id': c['id'], 'phase': c['phase'],
            'queue_state': qs, 'same_repository_as_start': same_repo,
            'cycle_present': cycle_present}


def finalize(path: Path, task_id: str) -> None:
    data = read(path)
    c = data['current_task']
    if c is None or c['id'] != task_id or c['phase'] != 'verified':
        raise RuntimeError('Cannot finalize unverified journal task')
    data['last_completed_task'] = {'id': task_id, 'kind': c['kind'],
                                   'completed_at': stamp(),
                                   'git_head_before': c['git_head_before'],
                                   'git_head_after': c.get('git_head_after')}
    data['current_task'] = None
    atomic_json(path, data)


def clear_reviewed(path: Path, task_id: str, queue_text: str, row_re,
                   head: str, repo_digest: str, cycle_present: bool) -> None:
    result = inspect(path, queue_text, row_re, head, repo_digest, cycle_present)
    data = read(path)
    c = data['current_task']
    if c is None or c['id'] != task_id or result['outcome'] != 'review':
        raise RuntimeError('No matching unresolved task')
    if c['phase'] == 'verified':
        raise RuntimeError('Verified work requires manual reconciliation')
    # An active Git cycle may be retried only for a failed TEST that did not
    # change the repository or the selected queue entry. All other active-cycle
    # cases (EDIT, COMMIT, interrupted work) still need manual reconciliation.
    if cycle_present and not (c['kind'] == 'TEST' and c['phase'] == 'needs_review'):
        raise RuntimeError('Active Git-cycle work requires manual reconciliation')
    if result['queue_state'] != 'unchecked_original' or not result['same_repository_as_start']:
        raise RuntimeError('Queue or Git differs from task start; manual reconciliation required')
    data['last_reviewed_task'] = {'id': task_id, 'at': stamp(), 'action': 'retry_authorized'}
    data['current_task'] = None
    atomic_json(path, data)
