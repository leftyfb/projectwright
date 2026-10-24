"""Durable, per-project successful-task counters; caller must hold project lock."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path


def state_path(config: dict, config_path: Path) -> Path:
    return Path(config.get('worker_state_file', str(config_path.parent / 'worker_state.json'))).expanduser()


def read_state(path: Path) -> dict:
    if not path.exists():
        return {'schema_version': 1, 'completed_tasks_total': 0,
                'completed_since_strategic_review': 0,
                'completed_task_ids': [], 'last_strategic_review_at': None,
                'last_planning_at': None, 'last_planning_result': None}
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('schema_version') != 1 or not isinstance(state.get('completed_task_ids'), list):
        raise ValueError(f'Unsupported or invalid worker progress state: {path}')
    return state


def record_completed(path: Path, task_id: str) -> bool:
    """Idempotent per task ID; call after the verified checkbox is persisted.

    The queue manager must assign unique task IDs over a project's lifetime.
    """
    state = read_state(path)
    if task_id in state['completed_task_ids']:
        return False
    state['completed_task_ids'].append(task_id)
    state['completed_tasks_total'] += 1
    state['completed_since_strategic_review'] += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(dir_fd)
        finally: os.close(dir_fd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return True
