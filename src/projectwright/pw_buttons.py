"""Projectwright Telegram approval core. No Telegram SDK dependency or network access.

Use from the Hermes plugin callback. No app expiration on pending records.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sys

PROJECT_RE = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')
CALLBACK_RE = re.compile(r'^pwa:([ar]):([a-z][a-z0-9_-]{0,63}):([0-9a-f]{20})$')


def request_id(record: dict) -> str:
    """Stable content identifier, bound to full pinned approval evidence."""
    raw = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def callback_data(action: str, record: dict) -> str:
    if action not in ('a', 'r') or not PROJECT_RE.fullmatch(record['project']):
        raise ValueError('Invalid callback action or project')
    result = f'pwa:{action}:{record["project"]}:{request_id(record)}'
    if len(result.encode()) > 64:
        raise ValueError('Telegram callback limit exceeded')
    return result


def resolve(root: Path, data: str):
    match = CALLBACK_RE.fullmatch(data)
    if match is None:
        raise ValueError('Unknown callback')
    action, project, rid = match.groups()
    p = root / project / 'telegram_approval_pending.json'
    # Avoid path traversal; regular file checks and exact project binding.
    if not p.is_file() or p.is_symlink():
        raise ValueError('Approval no longer pending')
    record = json.loads(p.read_text(encoding='utf-8'))
    if record.get('project') != project or request_id(record) != rid:
        raise ValueError('Stale or mismatched approval request')
    return action, root / project, record


def approve(root: Path, data: str) -> str:
    action, directory, pinned = resolve(root, data)
    if action != 'a':
        raise ValueError('Not an approval callback')
    scripts = Path.home() / '.hermes/scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import project_telegram_approval as bridge
    import project_milestone_guard as guard
    cfg, policy = bridge.project_data(directory)
    milestone = pinned['milestone']
    spec = policy['milestones'].get(milestone) if policy else None
    if spec is None:
        raise ValueError('Approval policy missing')
    # Guard checks the CURRENT pending file, all pinned state, policy, Git & tests
    # while holding the same project lock as the worker.
    receipt = guard.approve(cfg, directory, pinned['requirement'], milestone,
                            pinned['command'], pinned['scope_paths'], expected=pinned)
    if receipt['git_head'] != pinned['head']:
        raise RuntimeError('Unexpected verified receipt HEAD')
    # Race-tolerant cleanup: if a later request somehow exists do not remove it.
    path = directory / 'telegram_approval_pending.json'
    if path.exists():
        current = json.loads(path.read_text())
        if current == pinned:
            path.unlink()
    return f'APPROVED {directory.name} / {milestone} at {receipt["git_head"][:12]}'


def reject(root: Path, data: str) -> str:
    """Keep the request, but record rejection. A human must review it.

    Do not mutate the queue, approve a receipt or automatically replan.
    """
    import fcntl
    action, directory, pinned = resolve(root, data)
    if action != 'r':
        raise ValueError('Not a rejection callback')
    cfg = json.loads((directory / 'config.json').read_text())
    lock = Path(cfg['lock']).expanduser()
    with lock.open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _, _, current = resolve(root, data)
        # Persist with the same atomic write utility as the existing bridge.
        scripts = Path.home() / '.hermes/scripts'
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import project_telegram_approval as bridge
        bridge.atomic_json(directory / 'telegram_approval_rejected.json', current)
    return f'REJECTED {directory.name} / {pinned["milestone"]}. Manual review required.'


def message_text(record: dict) -> str:
    return ('Projectwright — milestone approval\n'
            f'Project: {record["project"]}\n'
            f'Milestone: {record["milestone"]}\n'
            f'Commit: {record["head"][:12]}\n'
            f'Tasks: {", ".join(record["task_ids"])}\n'
            'Review the changes before approving. The original Git state and acceptance tests are rechecked on approval.')
