# Current module naming and compatibility map

This document describes the **development branch** `test/review-followups` on
2026-10-24. Historical audit files such as `component-inventory.md` and
`architecture-current.md` describe the original snapshot, not the current
canonical module names.

## Naming policy

- Primary command: `pw`; additional installed commands include `pw-manager`,
  `pw-worker`, `pw-dispatch`, `pw-notify`, and `pw-timer`.
- Canonical flat-source Python modules use `pw_*.py`.
- The `project_*.py` files remain **packaged compatibility imports/entrypoints**
  for existing scripts. Do not delete them before a documented deprecation
  release and installed-upgrade validation.
- The worker compatibility module aliases the **same** `pw_task_worker`
  module object in `sys.modules`. This is necessary because existing
  integration tests and consumers patch mutable module state.
- Do not alter the immutable original installed-source manifest to disguise
  development differences. Development validation explicitly accounts for
  added canonical modules.

## Canonical and legacy modules

| Canonical implementation | Retained legacy import |
|---|---|
| `pw_task_worker.py` | `project_task_worker.py` |
| `pw_queue_manager.py` | `project_queue_manager.py` |
| `pw_queue_planner.py` | `project_queue_planner.py` |
| `pw_milestone_guard.py` | `project_milestone_guard.py` |
| `pw_milestone_sequence.py` | `project_milestone_sequence.py` |
| `pw_acceptance_gate.py` | `project_acceptance_gate.py` |
| `pw_telegram_approval.py` | `project_telegram_approval.py` |
| `pw_notes_sync.py` | `project_notes_sync.py` |
| `pw_notes_publisher.py` | `project_notes_publisher.py` |
| `pw_quota.py` | `project_quota.py` |
| `pw_recovery.py` | `project_recovery.py` |
| `pw_worker_journal.py` | `project_worker_journal.py` |
| `pw_worker_progress.py` | `project_worker_progress.py` |

Canonical-only runtime/CLI helpers: `pw_buttons.py`, `pw_config.py`,
`pw_defaults.py`, `pw_dispatch.py`, `pw_init.py`, `pw_notify.py`,
`pw_plugin.py`, and `pw_project_timer.py`.

## Execution and migration constraints

The dispatcher calls the canonical manager and worker; the manager calls the
canonical planner. The planner uses the canonical milestone guard. Historical
imports are still accepted. Approval notifier/button code retains some legacy
imports deliberately until cross-module patching and callback behavior are
verified using both names.

A missing `config.json` is supported for **manually invoked prepared
projects**, not implicit unattended authorization. Read
`configuration-home.md` for default project paths and Git preflight rules,
`workflow.md` for the task lifecycle, and
`release-checklist.md` for remaining acceptance gates.

## Outstanding work

1. Audit remaining `project_*` references in unit files, Debian lifecycle,
   documentation and test fixtures; distinguish intentional compatibility
   references from stale production dispatch names.
2. Verify fresh wheel and Debian installations, all CLI entrypoints, and a
   disposable legacy-layout upgrade with neither real Hermes state nor live
   Telegram credentials.
3. Decide and publish a compatibility/deprecation policy before removing shims.
4. Complete live isolated Hermes, Telegram approval, and per-user systemd
   installation tests. A green development CI run does **not** sign these off.
