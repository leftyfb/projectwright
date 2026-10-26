#!/usr/bin/env python3
"""Prepare a disposable live approval fixture in pw-test."""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path('/home/ubuntu/projectwright-live-test')
ROOT = BASE / 'projects'
PROJECT = ROOT / 'pwtelecheck'
REPO = BASE / 'repo'

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], text=True).strip()

def prepare():
    if BASE.exists() or BASE.is_symlink():
        raise RuntimeError('fixture already exists; refusing overwrite')
    PROJECT.mkdir(parents=True)
    REPO.mkdir()
    git('init', '-q')
    git('config', 'user.name', 'Projectwright Test')
    git('config', 'user.email', 'test@example.invalid')
    (REPO / 'probe.py').write_text('VALUE = 1\n')
    git('add', 'probe.py')
    git('commit', '-qm', 'fixture')
    (PROJECT / 'requirements.md').write_text('## DEMO-1 — Requirement\n\n### DEMO-1-M1 — Test milestone\n')
    (PROJECT / 'queue.md').write_text('- [x] **P1 — READ** DEMO-1 / DEMO-1-M1: Inspect\n- [x] **P2 — COMMIT** DEMO-1 / DEMO-1-M1: Commit\n')
    cfg = {'id': PROJECT.name, 'worktree': str(REPO), 'branch': git('branch', '--show-current'), 'lock': str(PROJECT / 'lock'), 'queue': str(PROJECT / 'queue.md'), 'cycle_file': str(PROJECT / 'cycle.json'), 'planning': {'enabled': True, 'requirements_file': str(PROJECT / 'requirements.md')}}
    (PROJECT / 'config.json').write_text(json.dumps(cfg))
    policy = {'version': 1, 'milestones': {'DEMO-1-M1': {'requirement': 'DEMO-1', 'command': [sys.executable, '-B', '-c', 'import sys; sys.exit(0)'], 'scope_paths': ['probe.py']}}}
    (PROJECT / 'telegram_acceptance.json').write_text(json.dumps(policy))
    from pw_telegram_approval import scan
    assert len(scan(ROOT)) == 1
    print('READY: disposable pending milestone')

def status():
    state = PROJECT / 'planning_state.json'
    if state.exists():
        print('APPROVED' if 'DEMO-1-M1' in json.loads(state.read_text()).get('verified_milestones', {}) else 'UNVERIFIED')
    elif (PROJECT / 'telegram_approval_rejected.json').exists():
        print('REJECTED')
    elif (PROJECT / 'telegram_approval_pending.json').exists():
        print('PENDING')
    else:
        print('NO REQUEST')

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('prepare', 'status'):
        raise SystemExit('usage: prepare|status')
    (prepare if sys.argv[1] == 'prepare' else status)()
