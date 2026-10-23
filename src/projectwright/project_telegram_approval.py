#!/usr/bin/env python3
"""Conservative local approval bridge. Does not contact Telegram itself.

Policy is administrator-defined in <project>/telegram_acceptance.json.
Only previously scanned and pinned, clean milestones can be approved.
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
import sys
import tempfile

PROJECT_RE = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

def atomic_json(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.approval-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, sort_keys=True, indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def project_data(directory):
    cfg = json.loads((directory / 'config.json').read_text())
    if cfg.get('id') != directory.name or not PROJECT_RE.fullmatch(directory.name):
        raise ValueError('Project ID mismatch')
    policy_path = directory / 'telegram_acceptance.json'
    if not policy_path.exists():
        return cfg, None
    policy = json.loads(policy_path.read_text())
    if not isinstance(policy, dict) or policy.get('version') != 1 or not isinstance(policy.get('milestones'), dict):
        raise ValueError('Invalid telegram_acceptance.json')
    return cfg, policy

def evidence(directory, cfg, milestone, spec):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import project_milestone_guard as guard
    if not isinstance(spec, dict): raise ValueError('Invalid acceptance spec')
    requirement = spec.get('requirement')
    command, paths = spec.get('command'), spec.get('scope_paths')
    if (not isinstance(requirement, str) or not re.fullmatch(r'[A-Z][A-Z0-9]*-\d+', requirement)
        or not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command)
        or not isinstance(paths, list) or not paths or not all(guard._valid_scope_path(x) for x in paths)
        or len(set(paths)) != len(paths)):
        raise ValueError('Acceptance requires explicit requirement, argv command and nonempty literal scope_paths')
    req = Path(cfg['planning']['requirements_file']).expanduser()
    queue = Path(cfg['queue']).expanduser()
    repo = Path(cfg['worktree']).expanduser()
    if milestone not in guard.milestone_ids(req.read_text()) or not milestone.startswith(requirement+'-'):
        return None
    tasks = guard.scoped_tasks(queue.read_text(), requirement, milestone)
    if not tasks or any(t['state'] != 'x' for t in tasks) or not any(t['kind'] == 'COMMIT' for t in tasks):
        return None
    if Path(cfg['cycle_file']).expanduser().exists():
        return None
    journal = directory / 'worker_journal.json'
    if journal.exists() and json.loads(journal.read_text()).get('current_task') is not None:
        return None
    if git(repo, 'branch','--show-current') != cfg['branch'] or git(repo,'status','--porcelain'):
        return None
    head = git(repo, 'rev-parse', 'HEAD')
    state_path = directory / 'planning_state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    receipts = guard.current_receipts(state, req.read_bytes(), queue.read_text(), head, repo=repo, strict=cfg.get('planning', {}).get('milestone_sequence') == 'strict',
                                      policy=guard.policy_for_project(directory), journal=json.loads(journal.read_text()) if journal.exists() else {})
    if milestone in receipts: return None
    strict = cfg.get('planning', {}).get('milestone_sequence') == 'strict'
    fingerprints = {}
    if strict:
        milestone_hash = guard.milestone_fingerprint(req.read_bytes(), milestone)
        policy_hash = guard.acceptance_policy_fingerprint(spec)
        if not milestone_hash or not policy_hash:
            return None
        fingerprints = {'milestone_requirements_sha256': milestone_hash,
                        'acceptance_policy_sha256': policy_hash}
    return dict(**fingerprints, project=directory.name, requirement=requirement, milestone=milestone,
                head=head, requirements_sha256=digest(req), queue_sha256=digest(queue),
                task_ids=[t['id'] for t in tasks], scope_paths=paths, command=command)

def load_pending(root):
    records=[]
    for directory in sorted(root.iterdir()) if root.is_dir() else []:
        if not directory.is_dir() or not PROJECT_RE.fullmatch(directory.name): continue
        record_path=directory/'telegram_approval_pending.json'
        if not record_path.exists(): continue
        data=json.loads(record_path.read_text())
        if data.get('project') != directory.name: raise ValueError('Pending record project mismatch')
        records.append((directory,data))
    return records

def scan(root):
    found=[]
    for directory in sorted(root.iterdir()) if root.is_dir() else []:
        if not directory.is_dir() or not PROJECT_RE.fullmatch(directory.name): continue
        cfg, policy=project_data(directory)
        if policy is None: continue
        # Do not scan when the project itself is disabled.
        if not cfg.get('planning',{}).get('enabled',False): continue
        lock=Path(cfg['lock']).expanduser()
        with lock.open('a+') as f:
            try: fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: continue
            options=[]
            if cfg.get('planning', {}).get('milestone_sequence') == 'strict':
                from project_milestone_sequence import evaluate
                from project_milestone_guard import current_receipts
                reqdata = Path(cfg['planning']['requirements_file']).expanduser().read_bytes()
                queuedata = Path(cfg['queue']).expanduser().read_text()
                repo = Path(cfg['worktree']).expanduser()
                statepath = directory / 'planning_state.json'
                state = json.loads(statepath.read_text()) if statepath.exists() else {}
                head = git(repo, 'rev-parse', 'HEAD')
                receipts = current_receipts(state, reqdata, queuedata, head, repo=repo, strict=True, policy=policy, journal=json.loads((directory / 'worker_journal.json').read_text()) if (directory / 'worker_journal.json').exists() else {})
                selection = evaluate(reqdata.decode('utf-8'), queuedata, receipts, policy)
                if selection['decision'] != 'awaiting_acceptance':
                    continue
                allowed = {selection['milestone']}
            else:
                allowed = set(policy['milestones'])
            for milestone,spec in policy['milestones'].items():
                if milestone not in allowed:
                    continue
                record=evidence(directory,cfg,milestone,spec)
                if record: options.append(record)
            if len(options)==1:
                pending_path = directory / 'telegram_approval_pending.json'
                previous = json.loads(pending_path.read_text()) if pending_path.exists() else None
                if previous != options[0]:
                    atomic_json(pending_path, options[0])
                    found.append(options[0])
            elif len(options)>1:
                print(f'{directory.name}: multiple completed milestones; not creating an ambiguous request')
    return found

def approve_single(root):
    pending=load_pending(root)
    if len(pending)!=1:
        raise ValueError(f'Expected exactly one pending approval across all projects; found {len(pending)}')
    directory, pinned=pending[0]
    cfg,policy=project_data(directory)
    milestone=pinned['milestone']
    spec=policy['milestones'].get(milestone) if policy else None
    if spec is None: raise ValueError('Acceptance policy missing; refusing')
    # Guard verifies ALL pinned fields and policy inside its own project lock.
    # Never release a lock between stale-request validation and receipt writing.
    import project_milestone_guard as guard
    receipt=guard.approve(cfg,directory,pinned['requirement'],milestone,
                          pinned['command'],pinned['scope_paths'],expected=pinned)
    # Do not remove request if receipt wasn't actually written.
    if receipt['git_head'] != pinned['head']: raise RuntimeError('Unexpected receipt HEAD')
    (directory/'telegram_approval_pending.json').unlink()
    return f'APPROVED {directory.name} / {milestone} at {receipt["git_head"][:12]}. Next scheduled run may plan.'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('scan','pending','approve-single'))
    p.add_argument('--root',type=Path,default=Path.home()/'.hermes/projects')
    a=p.parse_args()
    try:
        if a.action=='scan':
            recs=scan(a.root)
            print('\n'.join(f'REQUESTED {r["project"]} / {r["milestone"]} HEAD {r["head"][:12]}' for r in recs) or 'No new approvals')
        elif a.action=='pending':
            pending=load_pending(a.root)
            print('\n'.join(f'{r["project"]} / {r["milestone"]}: HEAD {r["head"][:12]} tasks {",".join(r["task_ids"])}' for _,r in pending) or 'No pending approvals')
        else: print(approve_single(a.root))
    except (Exception,) as exc:
        print(f'REFUSED: {type(exc).__name__}: {exc}',file=sys.stderr)
        return 2
    return 0
if __name__=='__main__': raise SystemExit(main())
