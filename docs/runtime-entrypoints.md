> **Historical baseline audit only.** This page inventories the original 18 flat modules and historical installed Hermes state. It is **not** the current development branch manual. Read [manual.md](manual.md), [file-reference.md](file-reference.md) and [release-checklist.md](release-checklist.md) for current names, workflows and verified live test status.

# Runtime entry points and integrations

Audit baseline: `7fe441c9cf46ea3c67ce6cd03fa82eaa4f6124fd`. Commands below describe source/runtime wiring; credentials and token values are deliberately omitted.

## Python CLI entry points

| Entry point | Interface | Role and caller |
|---|---|---|
| `pw_dispatch.py` | `--project ID [--scripts PATH]` | Outer dispatcher. Called by a manual CLI or the per-project systemd service. Invokes queue manager and, if permitted, worker as separate processes. |
| `project_queue_manager.py` | `--project ID [--status|--once]` | Queue/policy decision CLI. `pw_dispatch.py` calls `--once`; can invoke planner in-process. |
| `project_task_worker.py` | `--project ID`; `--once`; `--dry-run`; `--quota-check`; `--no-telegram`; `--journal-status`; `--authorize-retry TASK_ID`; hidden `--detached` | Executes a permitted task; dispatcher is the observed caller. `--once`/`--detached` process once, then invoke queue management when safe; detached mode re-enters the same script as a child. |
| `project_recovery.py` | `--project ID [--record]` | Read-only inspection by default; worker uses `--record` to durably record a detected interrupted journal. |
| `project_telegram_approval.py` | `scan`, `pending`, or `approve-single`; optional `--root PATH` | Approval-state scanner/operator CLI; notifier uses `scan`; callback path uses approval helpers. |
| `project_milestone_guard.py` | `--project ID --requirement ID --milestone NAME --approve [--scope-path PATH ...] COMMAND` | Acceptance CLI that accepts a requirement identifier (not a path), runs the specified verification command and records a receipt after validating Git/milestone evidence. |
| `project_notes_publisher.py` | `--project ID [--dry-run]` | Optional progress-note publisher; worker calls it when notes are enabled. |
| `project_notes_sync.py` | `--project ID [--config-root PATH]` and exactly one of `--status`, `--init`, `--publish` | Optional mirror status/baseline/publish utility; planner/worker can call publish. |
| `pw_notify.py` | `[--root PATH] [--send]` | Approval scan/notification. Without `--send` it is dry-run; systemd invokes `--send`. Actual sends require a bot token and exactly one decimal ID in `TELEGRAM_ALLOWED_USERS`; the callback plugin accepts a list. |
| `pw_project_timer.py` | `ACTION PROJECT [--minutes N] [--root PATH]`; actions `check`, `install-disabled`, `enable`, `disable`, `status` | Manual systemd-user-timer management. `install-disabled` refuses to overwrite existing unit files; no normal runtime call observed. |

`project_queue_planner.py`, `project_quota.py`, `project_acceptance_gate.py`, `project_milestone_sequence.py`, `project_worker_journal.py`, and `project_worker_progress.py` are library modules without their own CLI entry point.

## systemd and Hermes wiring

Read-only systemd-user inspection and the source/installed manifest showed:

- `projectwright-approval-notify.timer`: enabled and active. Its static service executes `/usr/bin/python3 -B /home/leftyfb/.hermes/scripts/pw_notify.py --send`. The latest inspected service run exited status 0; the oneshot service is inactive after completion.
- `projectwright-worker-pw-sequence-test.timer`: disabled/inactive. Its static service's effective `ExecStart` is `/usr/bin/python3 -B /home/leftyfb/.hermes/scripts/pw_dispatch.py --project pw-sequence-test`; service is inactive and has no recorded run in the inspected snapshot.
- No active Projectwright worker cron job was identified. The worker timer is not an active execution source in the inspected state.
- The installed-source manifest contains 18 entries and the read-only runtime snapshot reported all 18 installed scripts match repository source. This validates source parity, not execution of every script.
- `hermes plugins list --plain --no-bundled` reported the user plugin `projectwright-approvals` v0.1.0 enabled. `pw_plugin.py` registers Telegram callback handlers using `telegram.ext.CallbackQueryHandler` and sibling `pw_buttons` handlers.
- The separate `pw_project_timer.py` generator defaults to a 20-minute interval and creates disabled-by-default user units. It is a utility, not the active notification timer.

The current project config at `/home/leftyfb/.hermes/projects/projectwright/config.json` points to this repo and a `queue.md` that does not exist. That config is therefore not a usable queue-runner target as inspected. It is not evidence of a currently running job; the worker timer is disabled and no active worker cron job was identified.

## Subprocess and dynamic-import boundaries

| Caller | Child process / external command | Purpose |
|---|---|---|
| `pw_dispatch.py` | Python child for `project_queue_manager.py --once`; then Python child for `project_task_worker.py` | Isolates decision and task execution; parses manager JSON and uses return status to decide whether to start worker. The runner can be injected for tests. |
| `project_queue_planner.py` | Configured Hermes executable via `subprocess.Popen` with timeout | Obtain one structured planning proposal. Planner validates before queue/state mutation. Also runs optional notes sync after releasing the project lock. |
| `project_task_worker.py` | Configured Hermes CLI as `hermes chat --oneshot --query-file - --ignore-rules`; separate `hermes send --to telegram --quiet`; Python children for recovery record, queue manager, notes sync, and detached worker; Git commands | Executes the task, captures/reconciles state, records recovery when required, re-runs queue management after a safe completion, best-effort publishes notes, and sends a separate task notification. Queue manager invocation has a 900-second timeout; detached worker is started with `Popen`. |
| `project_queue_manager.py` | Git branch/HEAD/dirty-state probes; in-function imports of gate/planner modules; `__import__` of milestone guard at gate points | Collects evidence and computes the dispatch decision. Git probes are read-only. |
| `project_milestone_guard.py` | Git `rev-parse`, `rev-list`, `diff-tree`, additional Git probes; configured acceptance command | Validates milestone acceptance and records a receipt. The configured command is an argument vector, not a shell command string. |
| `project_recovery.py` | Git evidence probes through `subprocess.check_output` | Classifies recovery state; record mode writes only incident state. |
| `project_telegram_approval.py` | Git HEAD/status evidence probes | Pins approval evidence and rejects stale requests. |
| `pw_project_timer.py` | `systemctl --user daemon-reload`, `enable --now`, `disable --now`, `status` | Unit lifecycle operations, only when an operator invokes the utility. |

Dynamic loading is used in `pw_dispatch.py` (`importlib.util.spec_from_file_location`, `module_from_spec`, and `__import__`). The manager/planner use `__import__` for milestone-guard checks; the worker uses regular local imports and invokes helper scripts as subprocesses. The notes/approval modules that need sibling resolution modify `sys.path` in the installed flat-script layout.

## External integrations and credentials

- **Hermes CLI/runtime:** configured executable for planning and task execution; separate `hermes send` path for worker notifications. Provider/model selection remains owned by Hermes configuration.
- **Home Assistant:** `project_quota.py` reads configured entity state from the HA REST API; no write service is invoked.
- **Telegram:** `pw_notify.py` sends approval messages using the Bot API and requires exactly one valid decimal `TELEGRAM_ALLOWED_USERS` ID for outbound sends; the enabled callback plugin accepts a comma-separated list of such IDs and requires a private chat. Incoming callbacks arrive through the enabled Hermes plugin and python-telegram-bot. Secret values were not inspected into documentation.
- **Git:** worktree state, branch, HEAD, commits, diffs, stash and cycle checks. Recovery and approval checks use Git evidence; task execution can intentionally mutate the configured worktree.
- **systemd user manager:** notification and worker timers/services; the timer utility can manage units if manually invoked.
- **Filesystem/locking:** per-project configuration, queue, journal, progress, planning, recovery, acceptance and Telegram state files, guarded with `fcntl` locks and atomic replace patterns.
- **Notes mirrors:** optional local file mirror integration with hash/manifest conflict checks.
