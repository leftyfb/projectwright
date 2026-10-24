"""Projectwright Hermes user plugin: scoped, no-LLM Telegram callback handler."""
import asyncio
import logging
import os
from pathlib import Path
import sys

LOG = logging.getLogger('projectwright.telegram')
SCRIPTS = Path.home() / '.hermes' / 'scripts'
if str(SCRIPTS) not in sys.path:
    # Prefer installed package modules; retain legacy scripts as a fallback only.
    sys.path.append(str(SCRIPTS))


def _authorized_ids():
    from pw_notify import config_values, parse_allowed_users
    try:
        vals = config_values(Path.home() / '.hermes' / '.env')
        return frozenset(parse_allowed_users(vals.get('TELEGRAM_ALLOWED_USERS', '')))
    except (OSError, ValueError):
        # Invalid authorization configuration must deny every callback.
        return frozenset()


def _factory(app, adapter):
    from telegram.ext import CallbackQueryHandler
    from pw_buttons import approve, reject
    from project_queue_manager import default_project_root
    root = default_project_root()

    async def on_press(update, context):
        q = update.callback_query
        if q is None:
            return
        uid = str(getattr(q.from_user, 'id', ''))
        chat = getattr(getattr(q.message, 'chat', None), 'type', None)
        # Re-read on each callback so revoked users lose access immediately.
        if uid not in _authorized_ids() or chat != 'private':
            await q.answer('Not authorized', show_alert=True)
            return
        try:
            action = q.data.split(':', 2)[1]
            result = await asyncio.to_thread(approve if action == 'a' else reject, root, q.data)
        except Exception as exc:
            LOG.exception('Milestone action refused')
            await q.answer('Request stale or approval refused. See gateway logs.', show_alert=True)
            return
        await q.answer('Recorded')
        await q.edit_message_text(result)
    # Filter excludes all Hermes core buttons. Hermes reorders plugin callback handlers ahead of catch-all.
    app.add_handler(CallbackQueryHandler(on_press, pattern=r'^pwa:[ar]:[a-z][a-z0-9_-]{0,63}:[0-9a-f]{20}$'))


def register(ctx):
    ctx.register_telegram_handler(_factory)
