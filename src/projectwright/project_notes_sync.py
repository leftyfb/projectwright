#!/usr/bin/env python3
"""Publish project-owned queue/work log to existing notes with conflict checks.

Does not move files, change config, or modify existing notes during init.
"""
import argparse
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.tmp-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def paths(root, project):
    if not project or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in project) or not project[0].isalpha():
        raise ValueError('Invalid project ID')
    directory = root / project
    cfg = json.loads((directory / 'config.json').read_text())
    if cfg.get('id') != project:
        raise ValueError('Config ID mismatch')
    notes = cfg.get('notes', {}).get('mirrors')
    if not isinstance(notes, dict) or set(notes) != {'queue', 'work_log'}:
        raise ValueError('Add notes.mirrors.queue and notes.mirrors.work_log to config')
    mapping = {}
    for key in ('queue', 'work_log'):
        source = Path(cfg[key]).expanduser()
        target = Path(notes[key]).expanduser()
        if source.resolve() == target.resolve():
            raise ValueError('Source and destination must be different')
        if source.is_symlink() or target.is_symlink() or not source.is_file() or not target.is_file():
            raise ValueError(f'Missing, symlinked, or non-regular file: {key}')
        mapping[key] = (source, target)
    return directory, cfg, mapping


def perform(root, project, mode):
    directory, cfg, mapping = paths(root, project)
    manifest_path = directory / 'notes_sync_state.json'
    lock_path = Path(cfg['lock']).expanduser()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Project worker currently holds the lock') from exc
        if manifest_path.is_symlink():
            raise RuntimeError('Manifest may not be a symlink')
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
        if mode == 'init' and manifest is not None:
            raise RuntimeError('Already initialized')
        if mode != 'init' and manifest is None:
            raise RuntimeError('Run --init first')
        updates = {}
        next_manifest = {'version': 1, 'paths': {}}
        for key, (source, target) in mapping.items():
            src = source.read_bytes()
            dst = target.read_bytes()
            sh, dh = digest(src), digest(dst)
            if mode == 'init':
                if sh != dh:
                    raise RuntimeError(f'{key}: original and copy differ; refusing baseline')
            else:
                previous = manifest['paths'].get(key)
                if not previous or previous['target'] != str(target) or previous['source'] != str(source):
                    raise RuntimeError(f'{key}: paths changed since baseline')
                old = previous['digest']
                if dh != old and dh != sh:
                    raise RuntimeError(f'{key}: notes file edited independently; refusing overwrite')
                if mode == 'publish' and sh != dh:
                    updates[key] = src
            next_manifest['paths'][key] = {'source': str(source), 'target': str(target), 'digest': sh if mode in ('init', 'publish') else dh}
            print(f'{key}: source={sh[:12]} notes={dh[:12]} {"UPDATE" if key in updates else "OK"}')
        if mode == 'init':
            atomic(manifest_path, (json.dumps(next_manifest, indent=2) + '\n').encode())
            print('Baseline recorded; no queue or notes changed.')
        if mode == 'publish':
            # Preflight both mirrors before writing either. Idempotent on retry.
            for key, data in updates.items():
                atomic(mapping[key][1], data)
            atomic(manifest_path, (json.dumps(next_manifest, indent=2) + '\n').encode())
            print(f'Published {len(updates)} mirror(s).')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--project', required=True)
    p.add_argument('--config-root', type=Path, default=Path.home() / '.hermes/projects')
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--status', action='store_true')
    modes.add_argument('--init', action='store_true')
    modes.add_argument('--publish', action='store_true')
    a = p.parse_args()
    perform(a.config_root, a.project, 'init' if a.init else 'publish' if a.publish else 'status')


if __name__ == '__main__':
    main()
