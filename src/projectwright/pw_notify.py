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


def parse_allowed_users(value: str):
    """Parse the shared comma-separated allow-list of positive decimal user IDs."""
    if not isinstance(value, str):
        raise ValueError('TELEGRAM_ALLOWED_USERS must be a comma-separated ID list')
    entries = value.split(',')
    users = []
    for entry in entries:
        user = entry.strip()
        if not re.fullmatch(r'[1-9][0-9]*', user):
            raise ValueError('TELEGRAM_ALLOWED_USERS contains an invalid user ID')
        if user in users:
            raise ValueError('TELEGRAM_ALLOWED_USERS contains a duplicate user ID')
        users.append(user)
    return tuple(users)


def send(root: Path, record: dict, transport=None, *, recipient=None, values=None):
    vals = values if values is not None else config_values(Path.home() / '.hermes' / '.env')
    token = vals.get('TELEGRAM_BOT_TOKEN')
    users = parse_allowed_users(vals.get('TELEGRAM_ALLOWED_USERS', ''))
    if not token:
        raise ValueError('A Telegram bot token is required')
    if recipient is None:
        if len(users) != 1:
            raise ValueError('A recipient must be selected from the authorized Telegram user list')
        recipient = users[0]
    if recipient not in users:
        raise ValueError('Telegram recipient is not authorized')
    data = {'chat_id': recipient, 'text': message_text(record), 'reply_markup': {
        'inline_keyboard': [[{'text':'Approve','callback_data':callback_data('a',record)},
                             {'text':'Reject','callback_data':callback_data('r',record)}]]}}
    if transport:
        return transport(data)
    req=Request('https://api.telegram.org/bot'+token+'/sendMessage', data=json.dumps(data).encode(),
                headers={'Content-Type':'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=15) as response:
            body=json.load(response)
    except Exception as exc:
        # HTTP exceptions can embed the request URL, which contains the bot token.
        raise RuntimeError(f'Telegram sendMessage request failed ({type(exc).__name__})') from None
    if body.get('ok') is not True:
        raise RuntimeError('Telegram sendMessage failed')
    return body['result']['message_id']


def _delivery_state(marker: Path, current_id: str, users):
    if not marker.exists():
        return {}
    data = json.loads(marker.read_text())
    if not isinstance(data, dict):
        raise ValueError('Invalid Telegram delivery marker')
    if data.get('request_id') != current_id:
        return {}
    recipients = data.get('recipients')
    if recipients is None and 'message_id' in data:
        # The former one-recipient marker did not identify its recipient.
        if len(users) != 1:
            raise ValueError('Ambiguous legacy Telegram delivery marker; refusing duplicate sends')
        recipients = {users[0]: data['message_id']}
    if not isinstance(recipients, dict):
        raise ValueError('Invalid Telegram delivery marker')
    for user, message_id in recipients.items():
        if not isinstance(user, str) or not re.fullmatch(r'[1-9][0-9]*', user):
            raise ValueError('Invalid Telegram delivery marker recipient')
        if type(message_id) is not int or message_id <= 0:
            raise ValueError('Invalid Telegram delivery marker message ID')
    return recipients



def _still_pending(directory: Path, pinned: dict) -> bool:
    """A revoked or replaced request must not get a new delivery receipt."""
    pending = directory / 'telegram_approval_pending.json'
    try:
        if json.loads(pending.read_text(encoding='utf-8')) != pinned:
            return False
        rejected = directory / 'telegram_approval_rejected.json'
        return not (rejected.exists() and json.loads(rejected.read_text(encoding='utf-8')) == pinned)
    except FileNotFoundError:
        return False


def notify_pending(root: Path, *, dry_run=False, transport=None):
    import project_telegram_approval as bridge
    out=[]
    values = None
    users: tuple[str, ...] = ()
    for directory, pinned in bridge.load_pending(root):
        marker=directory/'telegram_approval_notified.json'
        current_id=request_id(pinned)
        rejected=directory/'telegram_approval_rejected.json'
        if rejected.exists() and json.loads(rejected.read_text())==pinned:
            continue
        if dry_run:
            out.append(f'PREVIEW {directory.name} / {pinned["milestone"]}')
            continue
        if values is None:
            values = config_values(Path.home() / '.hermes' / '.env')
            if not values.get('TELEGRAM_BOT_TOKEN'):
                raise ValueError('A Telegram bot token is required')
            users = parse_allowed_users(values.get('TELEGRAM_ALLOWED_USERS', ''))
        delivered = _delivery_state(marker, current_id, users)
        if all(user in delivered for user in users):
            continue
        lock=Path(json.loads((directory/'config.json').read_text())['lock']).expanduser()
        # Serialize notifier instances; do not hold worker project lock over network.
        notify_lock=directory/'.telegram_notify.lock'
        with notify_lock.open('a+') as f:
            fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
            delivered = _delivery_state(marker, current_id, users)
            if all(user in delivered for user in users):
                continue
            if not _still_pending(directory, pinned):
                continue
            failures = []
            for user in users:
                if user in delivered:
                    continue
                # Acceptance may have changed since the scan or last recipient.
                if not _still_pending(directory, pinned):
                    break
                try:
                    msgid=send(root,pinned,transport=transport,recipient=user,values=values)
                    if type(msgid) is not int or msgid <= 0:
                        raise ValueError('Telegram returned an invalid message ID')
                except Exception as exc:
                    failures.append(type(exc).__name__)
                    continue
                # Network delivery cannot be undone. If acceptance changed while
                # sending, avoid recording a stale receipt or sending to others.
                if not _still_pending(directory, pinned):
                    break
                delivered[user] = msgid
                # Telegram acceptance and local marker persistence are not atomic;
                # a failure here leaves an at-least-once retry that may duplicate.
                bridge.atomic_json(marker,{'request_id':current_id,'recipients':delivered})
            if failures:
                kinds = ', '.join(sorted(set(failures)))
                raise RuntimeError(f'Telegram delivery failed for {len(failures)} recipient(s) ({kinds})')
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
