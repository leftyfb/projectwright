#!/usr/bin/env python3
"""Publish a read-only, generated SilverBullet progress snapshot for any project."""
from __future__ import annotations
import argparse, fcntl, json, os, re, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

MARKER='<!-- generated-by: project_notes_publisher; manual edits will be overwritten -->'
ROW=re.compile(r'^\s*- \[([ x!])\]\s+\*\*([A-Z]+\d+)\s+[—-]\s+([A-Z]+)\*\*\s*(.*)$')

def render(config, config_path):
    from pw_worker_journal import journal_path, read as read_journal
    from pw_worker_progress import read_state, state_path
    q=Path(config['queue']).expanduser(); log=Path(config['work_log']).expanduser()
    rows=[m.groups() for line in q.read_text(encoding='utf-8').splitlines() if (m:=ROW.match(line))]
    count=lambda st:sum(1 for row in rows if row[0]==st)
    journal=read_journal(journal_path(config,config_path))
    state=read_state(state_path(config,config_path))
    active=journal.get('current_task')
    last=journal.get('last_completed_task')
    pending=[f'- `{tid}` — {kind}: {desc}' for st,tid,kind,desc in rows if st==' ']
    title=config.get('display_name', config['id'])
    out=[MARKER,f'# {title} — Automation Status','',
         f'_Updated: {datetime.now(timezone.utc).isoformat()}_','',
         '## Task queue',
         f'- Completed checkboxes: **{count("x")}**',
         f'- Pending: **{count(" ")}**',
         f'- Marked blocked/attention: **{count("!")}**',
         f'- Completions recorded since tracking began: **{state["completed_tasks_total"]}**',
         f'- Since strategic review: **{state["completed_since_strategic_review"]}**','',
         '## Execution journal',
         f'- Current: **{active["id"]} ({active["phase"]})**' if active else '- Current: none',
         f'- Last completed: **{last["id"]}**' if last else '- Last completed: not recorded','',
         '## Upcoming tasks',*(pending[:12] or ['- No pending tasks']),
         *(['- … additional tasks omitted from snapshot'] if len(pending)>12 else []),'',
         '## Project files',f'- Queue: `{q}`',f'- Work log: `{log}`','',
         '> This page is generated from automation state; edit requirements, not this page.','']
    if active and active.get('phase') in ('needs_review','running','selected'):
        out.insert(out.index('## Upcoming tasks'),'> **Attention:** Previous task may need recovery review before further execution.\n')
    return '\n'.join(out)

def atomic_write(target, content):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and not target.read_text(encoding='utf-8').startswith(MARKER):
        raise RuntimeError(f'Refusing to overwrite manually maintained note: {target}')
    fd,tmp=tempfile.mkstemp(prefix='.'+target.name+'.',dir=target.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            f.write(content); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def publish(config,config_path):
    notes=config.get('notes',{})
    if not notes.get('enabled',False): return None
    if not notes.get('progress_file'): raise ValueError('notes.progress_file missing')
    target=Path(notes['progress_file']).expanduser()
    atomic_write(target,render(config,config_path))
    return target

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--dry-run',action='store_true');p.add_argument('--config-dir',type=Path,default=None,help='Projectwright config home');a=p.parse_args()
    from pw_dispatch import default_project_root
    if a.config_dir is not None and not a.config_dir.is_absolute(): p.error('--config-dir must be absolute')
    root=a.config_dir / 'projects' if a.config_dir is not None else default_project_root()
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',a.project):p.error('Invalid project ID')
    path=root/a.project/'config.json'; cfg=json.loads(path.read_text())
    if cfg.get('id')!=a.project: raise ValueError('Project config ID mismatch')
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    if a.dry_run: print(render(cfg,path));return
    lock=Path(cfg['lock']).expanduser();lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        target=publish(cfg,path)
    print('Published:',target if target else 'notes disabled')

if __name__=='__main__':main()
