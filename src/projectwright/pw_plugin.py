"""Projectwright Hermes user plugin: scoped, no-LLM Telegram callback handler."""
import asyncio
import logging
import os
from pathlib import Path
import subprocess
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


def _plan_after_approval(directory: Path) -> None:
    """Run the normal guarded planner after approval without starting a worker."""
    from pw_embedded import project_id
    from pw_config import load as load_config
    project = project_id(directory)
    # Pass the verified repository location into the subprocess. Do not
    # rediscover by project name (which may be ambiguous across clones).
    env = os.environ.copy()
    if directory.name == '.pw':
        env['PROJECTWRIGHT_PROJECT_DIR'] = str(directory.parent.resolve())
    else:
        env.pop('PROJECTWRIGHT_PROJECT_DIR', None)
        env['HERMES_PROJECT_CONFIG_DIR'] = str(directory.parent.resolve())
    cfg = load_config(project, directory.parent, directory_override=directory)[1]
    if not cfg.get('planning', {}).get('enabled'):
        return
    result = subprocess.run(
        [sys.executable, '-B', '-m', 'pw_queue_manager', '--project', project, '--once'],
        env=env, capture_output=True, text=True, timeout=650, check=False)
    if result.returncode not in (0, 3):
        raise RuntimeError(
            'Post-approval planner returned ' + str(result.returncode) + ': ' +
            (result.stdout or result.stderr)[-1200:])


def _factory(app, adapter):
    from telegram.ext import CallbackQueryHandler
    from pw_buttons import approve, reject
    from project_queue_manager import default_project_root
    root = default_project_root()
    # A gateway can be pinned to a dedicated project tree for isolated tests.
    # Require an absolute, existing, nonsymlink directory; do not silently
    # fall back if an explicit override is malformed.
    scoped = os.environ.get('PROJECTWRIGHT_APPROVAL_ROOT')
    if scoped is not None:
        candidate = Path(scoped)
        if not candidate.is_absolute() or candidate.is_symlink() or not candidate.is_dir():
            raise ValueError('PROJECTWRIGHT_APPROVAL_ROOT must be an existing absolute directory')
        root = candidate

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
            target_dir = None
            if action == 'a':
                approved = await asyncio.to_thread(approve, root, q.data, True)
                if isinstance(approved, tuple):
                    result, target_dir = approved
                else:
                    result = approved
            else:
                result = await asyncio.to_thread(reject, root, q.data)
        except Exception as exc:
            LOG.exception('Milestone action refused')
            await q.answer('Request stale or approval refused. See gateway logs.', show_alert=True)
            return
        await q.answer('Recorded')
        await q.edit_message_text(result)
        if action == 'a' and target_dir is not None:
            # The exact directory was verified by approve under its acceptance
            # guard. Never rediscover by name after the pending record is gone.
            # Completion delivery is separate and cannot undo acceptance.
            try:
                from pw_completion import notify_completion
                await asyncio.to_thread(notify_completion, target_dir)
            except Exception:
                LOG.exception('Project completion notice could not be sent; notifier timer may retry')
            # Approval was already committed by the guarded callback. Replenish
            # immediately using the exact validated repository, rather than
            # waiting for the next dispatcher timer tick. Only queue planning
            # happens here; task execution remains on its authorized schedule.
            try:
                await asyncio.to_thread(_plan_after_approval, target_dir)
            except Exception:
                LOG.exception('Immediate post-approval planning failed; worker timer may retry')
    # Filter excludes all Hermes core buttons. Hermes reorders plugin callback handlers ahead of catch-all.
    app.add_handler(CallbackQueryHandler(on_press, pattern=r'^pwa:[ar]:[a-z][a-z0-9_-]{0,63}:[0-9a-f]{20}$'))


def register(ctx):
    ctx.register_telegram_handler(_factory)
