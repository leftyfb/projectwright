"""Manage disabled-by-default per-project systemd user schedules."""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

ID = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')

def unit_strings(project: str, minutes: int, script: Path) -> tuple[str,str]:
    if not ID.fullmatch(project) or not 5 <= minutes <= 1440:
        raise ValueError('Invalid project or interval (5..1440 minutes)')
    if not script.is_absolute(): raise ValueError('Dispatcher script path must be absolute')
    service = ('[Unit]\nDescription=Projectwright dispatcher for '+project+'\n'
               '[Service]\nType=oneshot\nExecStart=/usr/bin/python3 -B '+str(script)+' --project '+project+'\n'
               'TimeoutStartSec=45min\n')
    timer = ('[Unit]\nDescription=Schedule project worker for '+project+'\n'
             '[Timer]\nOnBootSec=2min\nOnUnitInactiveSec='+str(minutes)+'min\nPersistent=false\n'
             '[Install]\nWantedBy=timers.target\n')
    return service,timer

def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('action',choices=['check','install-disabled','enable','disable','status']);p.add_argument('project');p.add_argument('--minutes',type=int,default=20);p.add_argument('--root',type=Path,default=Path.home()/'.hermes/projects')
    a=p.parse_args()
    if not ID.fullmatch(a.project):p.error('Invalid project ID')
    directory=a.root/a.project
    cfg=json.loads((directory/'config.json').read_text())
    if cfg.get('id')!=a.project: raise ValueError('Project config mismatch')
    script=Path.home()/'.hermes/scripts/pw_dispatch.py'
    if not script.is_file(): raise ValueError('Dispatcher script missing')
    service,timer=unit_strings(a.project,a.minutes,script)
    unit='projectwright-worker-'+a.project
    dest=Path.home()/'.config/systemd/user'
    service_path=dest/(unit+'.service');timer_path=dest/(unit+'.timer')
    if a.action=='check':print(service);print(timer);return 0
    if a.action=='install-disabled':
        if service_path.exists() or timer_path.exists():raise ValueError('Units already exist; refusing overwrite')
        dest.mkdir(parents=True,exist_ok=True)
        service_path.write_text(service);timer_path.write_text(timer)
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        print('Installed disabled units for',a.project);return 0
    if a.action=='enable':
        if not service_path.exists() or not timer_path.exists():raise ValueError('Units not installed')
        # Explicit user action only. Never silently enable on install.
        subprocess.run(['systemctl','--user','enable','--now',unit+'.timer'],check=True);return 0
    if a.action=='disable':subprocess.run(['systemctl','--user','disable','--now',unit+'.timer'],check=True);return 0
    return subprocess.run(['systemctl','--user','status',unit+'.timer','--no-pager'],check=False).returncode

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e: print(f'REFUSED: {e}',file=sys.stderr);raise SystemExit(2)
