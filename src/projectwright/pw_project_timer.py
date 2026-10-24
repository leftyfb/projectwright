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

def approval_notify_units(notifier: Path, *, minutes: int = 10) -> tuple[str, str]:
    if not notifier.is_absolute() or not 5 <= minutes <= 1440:
        raise ValueError('Invalid notifier path or timer interval')
    service = ('[Unit]\nDescription=Projectwright approval notification scan\n'
               '[Service]\nType=oneshot\nExecStart=/usr/bin/python3 -B '
               + str(notifier) + ' --send\n')
    timer = ('[Unit]\nDescription=Projectwright approval notification timer\n'
             '[Timer]\nOnBootSec=3min\nOnUnitInactiveSec=' + str(minutes)
             + 'min\nPersistent=false\n[Install]\nWantedBy=timers.target\n')
    return service, timer


def setup_user_approvals(*, minutes=10, enable_plugin=False, runner=subprocess.run) -> None:
    """Per-user setup; never called automatically from root-owned dpkg postinst."""
    if os.geteuid() == 0:
        raise ValueError('Run setup-user as the intended non-root user')
    from pw_notify import config_values, parse_allowed_users
    values = config_values(Path.home() / '.hermes/.env')
    if not values.get('TELEGRAM_BOT_TOKEN'):
        raise ValueError('Configure Telegram bot token before enabling notifications')
    if not parse_allowed_users(values.get('TELEGRAM_ALLOWED_USERS', '')):
        raise ValueError('Configure at least one authorized Telegram user')
    notifier = Path(__file__).resolve().parent / 'pw_notify.py'
    if not notifier.is_file():
        raise ValueError('Notification script is missing from installation')
    service, timer = approval_notify_units(notifier, minutes=minutes)
    dest = Path.home() / '.config/systemd/user'
    targets = {
        dest / 'projectwright-approval-notify.service': service,
        dest / 'projectwright-approval-notify.timer': timer,
    }
    for path, contents in targets.items():
        if path.exists() and path.read_text() != contents:
            raise ValueError(f'Refusing to overwrite custom user unit: {path}')
    if enable_plugin:
        runner(['hermes', 'plugins', 'enable', 'projectwright-approvals'], check=True)
    dest.mkdir(parents=True, exist_ok=True)
    for path, contents in targets.items():
        if not path.exists():
            path.write_text(contents)
    runner(['systemctl', '--user', 'daemon-reload'], check=True)
    runner(['systemctl', '--user', 'enable', '--now',
            'projectwright-approval-notify.timer'], check=True)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == 'setup-user':
        p = argparse.ArgumentParser(description='Configure approvals for the current user')
        p.add_argument('action', choices=['setup-user'])
        p.add_argument('--minutes', type=int, default=10)
        p.add_argument('--enable-hermes-plugin', action='store_true')
        a = p.parse_args()
        setup_user_approvals(minutes=a.minutes, enable_plugin=a.enable_hermes_plugin)
        print('User approval timer enabled')
        return 0
    p=argparse.ArgumentParser();p.add_argument('action',choices=['check','install-disabled','enable','disable','status']);p.add_argument('project');p.add_argument('--minutes',type=int,default=20);p.add_argument('--root',type=Path,default=Path.home()/'.hermes/projects')
    a=p.parse_args()
    if not ID.fullmatch(a.project):p.error('Invalid project ID')
    unit='projectwright-worker-'+a.project
    # Query systemd even if the project config or dispatcher script is gone.
    if a.action=='status':
        return subprocess.run(['systemctl','--user','status',unit+'.timer','--no-pager'],check=False).returncode
    directory=a.root/a.project
    cfg=json.loads((directory/'config.json').read_text())
    if cfg.get('id')!=a.project: raise ValueError('Project config mismatch')
    script=Path(__file__).resolve().parent/'pw_dispatch.py'
    if not script.is_file(): raise ValueError('Dispatcher script missing')
    service,timer=unit_strings(a.project,a.minutes,script)
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
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e: print(f'REFUSED: {e}',file=sys.stderr);raise SystemExit(2)
