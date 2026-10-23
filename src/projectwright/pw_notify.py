"""Scan configured project milestones and deliver durable Telegram approval messages.

Runs once and exits; call with a recurring cron/systemd timer. Does not poll Telegram.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.request import Request, urlopen
from pw_buttons import request_id, callback_data, message_text


def config_values(path: Path):
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        if key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_ALLOWED_USERS'):
            result[key] = val.strip().strip('"\'')
    return result


def send(root: Path, record: dict, transport=None):
    vals = config_values(Path.home() / '.hermes' / '.env')
    token = vals.get('TELEGRAM_BOT_TOKEN')
    users = [i.strip() for i in vals.get('TELEGRAM_ALLOWED_USERS','').split(',') if i.strip()]
    if not token or len(users) != 1 or not users[0].isdecimal():
        raise ValueError('Expected a bot token and exactly one authorized Telegram user')
    data = {'chat_id': users[0], 'text': message_text(record), 'reply_markup': {
        'inline_keyboard': [[{'text':'Approve','callback_data':callback_data('a',record)},
                             {'text':'Reject','callback_data':callback_data('r',record)}]]}}
    if transport:
        return transport(data)
    req=Request('https://api.telegram.org/bot'+token+'/sendMessage', data=json.dumps(data).encode(),
                headers={'Content-Type':'application/json'}, method='POST')
    with urlopen(req, timeout=15) as response:
        body=json.load(response)
    if body.get('ok') is not True:
        raise RuntimeError('Telegram sendMessage failed')
    return body['result']['message_id']


def notify_pending(root: Path, *, dry_run=False, transport=None):
    import project_telegram_approval as bridge
    out=[]
    for directory, pinned in bridge.load_pending(root):
        marker=directory/'telegram_approval_notified.json'
        current_id=request_id(pinned)
        if marker.exists() and json.loads(marker.read_text()).get('request_id')==current_id:
            continue
        rejected=directory/'telegram_approval_rejected.json'
        if rejected.exists() and json.loads(rejected.read_text())==pinned:
            continue
        if dry_run:
            out.append(f'PREVIEW {directory.name} / {pinned["milestone"]}')
            continue
        lock=Path(json.loads((directory/'config.json').read_text())['lock']).expanduser()
        # Serialize notifier instances; do not hold worker project lock over network.
        notify_lock=directory/'.telegram_notify.lock'
        with notify_lock.open('a+') as f:
            fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
            if marker.exists() and json.loads(marker.read_text()).get('request_id')==current_id:
                continue
            if json.loads((directory/'telegram_approval_pending.json').read_text()) != pinned:
                continue
            msgid=send(root,pinned,transport=transport)
            bridge.atomic_json(marker,{'request_id':current_id,'message_id':msgid})
            out.append(f'NOTIFIED {directory.name} / {pinned["milestone"]}')
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.home()/'.hermes/projects')
    parser.add_argument('--send', action='store_true')
    a=parser.parse_args()
    # Scan first, under per-project locks. A failed scan is reported, never silently bypassed.
    from project_telegram_approval import scan
    scan(a.root)
    rows=notify_pending(a.root,dry_run=not a.send)
    print('\n'.join(rows) if rows else 'No new notifications')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f'REFUSED: {type(exc).__name__}: {exc}',file=sys.stderr)
        raise SystemExit(2)
