# `pw` command-line reference

The `pw` launcher preserves the existing service commands and adds a small onboarding path. Each command supports `--help`.

## Initialization and basic commands

`pw init PATH` initializes a Git repository at PATH if necessary and creates its local `.pw/` directory. Without a custom path, `pw init --project NAME` uses `~/projects/NAME`. To initialize an existing repository, use `pw init .` at its root. Initialization does not enable planning, execution, or timers.

`pw init PATH --shared` allows selected human-readable `.pw/` definitions to be tracked; default mode ignores all of `.pw/`. Existing legacy installations using `--repo` and `--config-dir` remain compatible.

The primary commands are `pw requirements --project NAME --edit`, `pw plan --project NAME`, `pw status --project NAME`, and `pw start --project NAME`. For a complete runnable walkthrough and packaged requirements, use [the Task Tracker example](../examples/task-tracker/README.md).

`pw requirements --edit` opens the configured requirements file, using `$VISUAL`, then `$EDITOR`, then an available `nano`, `vi`, `vim` or `editor`. Requirements are stored in the Projectwright project directory. Set `VISUAL` or `EDITOR` if no suitable editor is detected.

Invoking `pw plan` explicitly authorizes planning: it enables `planning.enabled` and runs one planning decision. It does not enable execution or run a worker. Review the queue before authorizing execution. Planning requires valid requirements, a usable Git worktree on the configured branch, named milestones where needed, and an available configured Hermes provider.

`pw start` asks for confirmation before launching one manual dispatcher run. It does not modify `execution.enabled`, install a timer, or enable recurring execution. In non-interactive scripts, `pw start --project NAME --yes` is the explicit confirmation. A declined prompt leaves the project unchanged. The worker's Git scope checks, journals, recovery rules, task sequencing and milestone gates remain in effect.

Persistent execution is separately authorized with `pw authorize-execution --project NAME --yes`; this only changes the persistent project setting. To run unattended, install a timer definition **without starting it**, then explicitly enable it:

```sh
pw authorize-execution --project NAME --yes
pw timer install NAME --minutes 5
pw timer enable NAME
```

The `install` command only writes user systemd service/timer units; it does not schedule work until `enable`. Worker intervals are 1–1440 minutes (default 20); `OnUnitInactiveSec` schedules the next activation relative to the **end** of the preceding run, rather than overlapping active tasks. The dispatcher and project lock also prevent concurrent work. Approval notification timers are separate and retain their own configuration and constraints.

Use `pw timer disable NAME` to stop recurring runs and `pw timer status NAME` to inspect the timer. `pw start` never authorizes persistent execution, installs a timer, or enables recurring execution.

`pw status` prints a human-readable summary. While a worker holds the lock, status reads the live task journal and a read-only queue snapshot; a busy lock is not an approval blocker and the displayed counts may change as the task finishes. Add `--json` for machine-readable JSON. Both formats include the manager decision and reason, queue counts, blockers, project settings, and next action. JSON adds `recurring_execution_configured` and `recurring_execution_enabled`; these are `unknown` when the user timer cannot be inspected reliably, and `recurring_execution` summarizes the result as `enabled`, `disabled`, `not_configured`, or `unknown`.

## Configure a project with `pw config`

All examples operate on the **selected project**; for an embedded repository
the file is `~/projects/NAME/.pw/config.json`. The commands also accept
`--config-dir /absolute/config/home` for a legacy external project.

```sh
pw config list --project task-tracker
pw config get planning.milestone_sequence --project task-tracker
pw config set planning.milestone_sequence strict --project task-tracker
pw config reset planning.milestone_sequence --project task-tracker
```

- `list` prints each supported dotted setting with its effective value (including built-in defaults).
- `get KEY` prints the effective value as JSON. Missing optional settings appear as `null`.
- `set KEY VALUE` writes a validated setting; booleans use `true` or `false`, numbers are unquoted, and arrays use JSON syntax. String values are unquoted command arguments.
- `reset KEY` removes an override to restore the program default. For `planning.milestone_sequence`, `off` is the effective default, and `set ... off` also removes the strict-mode override.
- Unknown setting names are refused. Changes are atomic and preserve other settings.
- Sensitive paths, provider definitions and network-related settings require `--yes`; this is explicit consent, not a bypass of normal worker/approval checks.
- The command refuses to change configuration while the worker holds the project lock, an EDIT/TEST/COMMIT Git cycle is active, or a worker journal has an unresolved task. Embedded paths must remain within `.pw/` (the worktree must remain the owning repository). Identity and layout markers are immutable.
- **Authorization is separate:** `execution.enabled` cannot be enabled with `pw config`; use `pw authorize-execution --project NAME --yes`. Enabling planning uses `pw plan --project NAME`. Changing JSON never installs or enables systemd timers and never approves a milestone.
- Secrets such as Home Assistant bearer tokens belong in their existing environment/secret files, never in embedded `config.json`.

### Supported settings

These are the keys supported by `pw config`, their effective defaults and their constraints. Not all defaults are materialized in the file. Path values for the embedded layout are **relative to `.pw/`**, not the current shell directory.

| Setting | Effective default | Usage / constraint |
|---|---|---|
| `planning.milestone_sequence` | `off` | `strict` requires accepted milestones in order; `off` removes the override. Recommended for automatic milestone-by-milestone workflows |
| `planning.enabled` | `false` | Planning authorization through `pw plan`; can set `false` to turn it off |
| `planning.requirements_file` | `requirements.md` (embedded) | Relative requirements path inside `.pw/` |
| `planning.trigger.pending_below` | `3` | Replenish when fewer than this many tasks remain; positive integer |
| `planning.trigger.review_every_completed_tasks` | `6` | Strategic-review trigger after completed-task count; positive integer |
| `planning.trigger.replan_on_blocker` | `true` | Trigger preference; does not override safety blockers |
| `planning.queue.target_pending` | `6` | Target pending task count |
| `planning.queue.max_new_tasks` | `5` | Maximum tasks added by one planning pass |
| `planning.queue.max_pending` | `10` | Hard queue ceiling; requires `1 <= pending_below <= target_pending <= max_pending` and `max_new_tasks <= max_pending` |
| `execution.enabled` | `false` | Persistent authorization; enable only via `pw authorize-execution`; `pw config` never bypasses it |
| `timeout_seconds` | `900` | Worker time limit, integer from 1 through 3600 |
| `hermes` | `hermes` | Hermes executable path/name (sensitive setting) |
| `provider.type` | `hermes` | `hermes` or `command` |
| `provider.planner_argv` | `null` | For command provider, JSON array of argv tokens; first must be absolute executable |
| `provider.worker_argv` | `null` | As above, for worker; both arrays required before selecting command provider |
| `test_file_patterns` | `["scripts/test_*.py", "tests/test_*.py"]` | Relative Python test patterns, JSON array |
| `quota.enabled` | `false` | Enable optional Home Assistant quota gating; unavailable telemetry blocks planning/worker |
| `quota.minimum_remaining_percent` | `10` | Numeric threshold 0–100; quota allowed only above this threshold |
| `quota.timeout_seconds` | `10` | Network request timeout, greater than 0 and at most 30 seconds |
| `quota.remaining_entity` | `sensor.codex_usage_weekly_remaining` | Home Assistant entity ID holding remaining percent |
| `quota.rate_limited_entity` | `null` | Optional HA binary_sensor; `null` disables it |
| `quota.ha_env_file` | `~/.hermes/secrets/ha.env` | File containing `HA_URL` and `HA_TOKEN`; **do not store the token in JSON** |
| `quota.allow_local_http` | `false` | Explicitly permit only the guarded `homeassistant.local` HTTP exception |
| `notes.enabled` | `false` | Enable read-only generated progress publishing |
| `notes.progress_file` | `null` | Generated progress destination; required for enabled publishing |
| `notes.mirrors.queue` | `null` | Optional existing notes mirror for `queue.md` |
| `notes.mirrors.work_log` | `null` | Optional existing notes mirror for `work_log.md` |
| `display_name` | Project ID | Display title in progress notes |
| `branch` | `main` | Git branch checked by worker/manager |
| `base`, `queue`, `work_log` | Project-local paths | Base, queue and worker log paths; these are structural and usually shouldn't be changed |
| `worktree` | Owning repository (embedded) | Immutable target relationship for embedded projects; legacy external state may reference a different repo |
| `lock`, `run_log`, `result_dir` | Project-local paths | Worker synchronization, activity logging and artifacts |
| `cycle_file`, `worker_journal_file` | Project-local paths | Git-cycle and worker recovery records; don't change with active state |
| `id`, `layout`, `projectwright_initialized` | Set by `pw init` | Readable but **not editable** via `pw config` |

The default worker interval and approval-notifier interval are **not**
`config.json` settings: use `pw timer install NAME --minutes N`
for the worker (default 20 minutes), and `pw setup --minutes N` for the
approval notifier (default 10 minutes). Those are separate systemd user timers.
The `provider` command arrays are an advanced integration; the `hermes`
provider remains the default and lets Hermes choose its own model.

Examples:

```sh
# Strict, human-approved milestones before automatic execution
pw config set planning.milestone_sequence strict --project task-tracker

# Replenish the queue when fewer than 2 tasks remain; target 4 pending
pw config set planning.trigger.pending_below 2 --project task-tracker
pw config set planning.queue.target_pending 4 --project task-tracker

# Turn off optional quota checks; does not change approval or execution
pw config set quota.enabled false --project task-tracker

# Restore default queue target and inspect it
pw config reset planning.queue.target_pending --project task-tracker
pw config get planning.queue.target_pending --project task-tracker
```


## Optional quota integration

Home Assistant-backed quota checks are **off by default** for every project. To opt in, set `"quota": {"enabled": true}` in the project's `config.json` and configure the relevant HA token and sensor. An enabled quota gate fails closed if the quota reading is unavailable; plain HTTP to arbitrary LAN addresses is not permitted for bearer tokens. Existing projects with explicit `quota.enabled: true` retain that setting.

## Project paths

The default deliverable repository is `~/projects/NAME/`, with Projectwright state under `~/projects/NAME/.pw/`. You may choose any other directory using `pw init /other/parent/NAME`. Internal embedded configuration paths are relative to `.pw/`, independent of the shell's working directory.

The CLI discovers `.pw/` by walking upward inside the current repository. Background callbacks and timers use an external registry; run `pw register .` after moving or cloning an initialized repository. If multiple repositories have the same name, run the command from the intended repository rather than relying on an ambiguous name.

Existing installations with external state remain supported. `--config-dir /absolute/config/home` selects the legacy `config-home/projects/NAME` layout, and `HERMES_PROJECT_CONFIG_DIR` is a legacy direct-root override.

## Existing commands

| Command | Purpose |
|---|---|
| `pw tick --project NAME` | One dispatcher cycle: planning when permitted and at most one worker task |
| `pw worker --project NAME --once` | Run at most one worker task |
| `pw defaults --project NAME` | Read-only selected paths and defaults |
| `pw notify` | Preview approval notifications; `--send` explicitly sends |
| `pw timer ACTION NAME` | Inspect or explicitly manage a project timer |
| `pw setup` | Check Hermes and optionally configure Telegram onboarding |
| `pw setup-user` | Explicit non-root Telegram approval integration onboarding |
| `pw config` | List, get, set and reset validated project configuration |
| `pw gateway-restart` | Prompt the current user to restart an active Hermes gateway after an install or upgrade |

Legacy `pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify`, and `pw-timer` entrypoints remain available. `pw init --project NAME --no-config` retains its config-free skeleton behavior; it cannot be combined with `--repo`.

A Projectwright project controls one worktree. A repository can be outside its state directory, but coordinated execution across multiple repositories as one task is not supported. Preserve the worker's existing repository-scope safeguards. See [workflow](workflow.md), [configuration paths](configuration-home.md), and the [operator manual](manual.md) for advanced behavior, recovery and approvals.
