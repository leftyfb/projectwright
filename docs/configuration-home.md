# Configuration home: initial XDG migration

Projectwright currently has an **initial XDG project-root selector**, not yet
complete configuration-free execution. New user configuration should live under
`$XDG_CONFIG_HOME/projectwright` (default `~/.config/projectwright`).
Project-specific state and config are currently discovered in its
`projects/<project-id>/` subdirectory.

The CLI accepts an explicit Projectwright config home with:

```bash
pw tick --project demo --config-dir /absolute/config/projectwright
pw status --project demo --config-dir /absolute/config/projectwright
pw worker --project demo --config-dir /absolute/config/projectwright --once
```

For `pw tick`, its dispatcher forwards the chosen root to manager and worker
subprocesses as `PROJECTWRIGHT_CONFIG_DIR`, so each sees the same project
directory. On a direct manager/worker invocation, `--config-dir` is also
supported.

Project directory resolution, when no explicit CLI root is supplied:

1. `PROJECTWRIGHT_CONFIG_DIR/projects` if set.
2. `HERMES_PROJECT_CONFIG_DIR` if set (backwards-compatible project-root override).
3. `$XDG_CONFIG_HOME/projectwright/projects`, or
   `~/.config/projectwright/projects` when `XDG_CONFIG_HOME` is unset.
4. If the XDG project root does not exist and the legacy
   `~/.hermes/projects` exists, use the legacy directory.

The selector never moves or rewrites an existing project. For the first
transition, retaining legacy data takes priority over silently changing live
behavior. Use an explicit `--config-dir` to select a new location.

**Missing configuration behavior:** `pw status` or `pw plan` for a
project without `config.json` returns a `disabled` decision and does not
create project data, run a provider, or send a message. The remaining config-free runtime defaults are not yet implemented. The worker
now also returns a non-executing `disabled` JSON decision (exit code 3) when the
project has no `config.json`, rather than reading an implicit Hermes config.
Actual worker execution still requires a validated project configuration. A missing configuration is never
interpreted as permission to start a task.

Current migration gaps: individual utilities (notifier, approval helpers,
notes sync, timer setup) still have legacy `~/.hermes` assumptions. The release
checklist tracks consolidating these behind one shared configuration API,
separating XDG data/state/cache directories, and adding first-run setup.

## Inspect defaults without initializing a project

`pw defaults --project demo` prints the selected project root, optional
configuration-file location and an explicit fail-closed set of defaults.
`pw defaults --project demo --config-dir /absolute/config/projectwright`
inspects another configuration home. Neither command creates files, starts a
provider, sends Telegram messages, enables systemd services, or approves tasks.

The `configured` field reports only whether `config.json` exists; it is not
an authorization decision or validation of its contents. The reported defaults
describe behavior **when no project configuration exists**, not effective
settings in an existing project. Actual config-free *execution* remains
intentionally disabled until safe project initialization and policy validation
are designed and tested.

## Initialize a safe, disabled project

`pw init --project demo` creates a new, private
`<project-root>/demo/config.json` with execution, planning, and notes disabled.
Use `--config-dir /absolute/config/projectwright` to select an XDG-style
configuration home. Initialization refuses existing project directories
(including symbolic links); it will not overwrite an existing configuration.
The created directory is mode 0700 and configuration is mode 0600.

`pw status --project demo` reports `disabled`; `pw worker --project demo
--once` also refuses execution. Initialization deliberately does **not**
invent a Git worktree, credentials, provider, queue, approval policy, systemd
unit or Telegram recipient. Enabling real execution remains an explicit
separate configuration and authorization process.

## Hardcoded runtime defaults (optional config file)

`pw_config.load(project, root)` now constructs ordinary project paths and
runtime settings from built-in defaults, whether or not `config.json` exists.
A present JSON file overrides those defaults, including partial settings for
planning, notes and execution. `pw defaults --project demo` also exposes
`effective_config` so users can inspect the resulting values.

The basic filesystem defaults are local to
`<project-root>/<project-id>/`: `queue.md`, `work_log.md`,
`worker.lock`, `worker.log`, `results/`, `git_cycle.json`, and
`worker_journal.json`. Runtime timeout defaults to 900 seconds and the
Hermes executable name defaults to `hermes`, which uses its own selected model.

**Current integration:** the manager's project-config loader and worker's
load_project now consume the shared hardcoded defaults and optional overrides.
**Still pending:** remove the CLI-level absent-file execution guard only after
selecting and validating a Git worktree and the execution authorization policy,
and distinguish ordinary task execution from approval-sensitive operations.
The installed worker currently retains its fail-closed absent-file guard, so
this is not yet an end-to-end config-free execution claim.
