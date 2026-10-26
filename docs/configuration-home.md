# Configuration home: initial XDG migration

Projectwright currently has an **initial XDG project-root selector**, partially migrated configuration-free execution. New user configuration should live under
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

**Missing configuration behavior:** an ordinary unprepared project without `config.json` is disabled, and no provider, Git repository, queue or credentials are created. An **explicitly prepared** config-free project with a Git worktree, HEAD commit, branch match, queue and work log can be manually inspected and executed, as described later on this page. With `requirements.md` an explicit planning path is supported. Unattended scheduling and human approval are never inferred.

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
settings in an existing project. Config-free *execution* requires an explicitly prepared worktree and preflight; it is not an unattended authorization.

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

A missing worktree setting resolves to the project's `worktree/` directory
and a missing branch setting defaults to `main`; neither default creates or
initializes a Git repository. A worker must still pass its Git-state and
execution checks before acting. The basic filesystem defaults are local to
`<project-root>/<project-id>/`: `queue.md`, `work_log.md`,
`worker.lock`, `worker.log`, `results/`, `git_cycle.json`, and
`worker_journal.json`. Runtime timeout defaults to 900 seconds and the
Hermes executable name defaults to `hermes`, which uses its own selected model.

**Current integration:** the manager's project-config loader and worker's
load_project now consume the shared hardcoded defaults and optional overrides.
**Still pending:** remove the CLI-level absent-file execution guard only after
selecting and validating a Git worktree and the execution authorization policy,
and distinguish ordinary task execution from approval-sensitive operations.
The worker permits the prepared-worktree manual path after Git and queue preflight; it continues to refuse unprepared projects.

## Manually running a prepared project without config.json

A config file is not required for an explicitly invoked worker when the
hardcoded project paths point to an existing, initialized Git worktree, the
current branch matches the configured/default branch, and both `queue.md`
and `work_log.md` already exist. For example, `pw worker --project demo
--dry-run` can inspect the next task from this prepared directory without
creating `config.json`. By default its worktree is
`<project-root>/demo/worktree`, branch `main`. A different repository or
branch can be selected with `PROJECTWRIGHT_WORKTREE` (absolute path) and
`PROJECTWRIGHT_BRANCH`. These environment values override JSON fields.

Explicit `--once` is also eligible after preflight validation, but all normal
worker Git, journal and task-scope checks continue to apply. Projectwright does
not create a Git repository, queue, or notes automatically, and will return
`disabled` when these prerequisites are absent. The normal `pw tick --project demo` dispatcher also accepts this prepared
config-free workspace: it skips automatic planning and dispatches one worker
cycle directly. Config-free automatic planning and scheduled execution remain
disabled until explicitly configured.

### Creating a project with no config.json

`pw init --project demo --no-config` creates private empty `queue.md`
and `work_log.md` files in the default project directory, with **no**
`config.json`. It does not initialize a Git repository, invoke Hermes or
enable automatic execution. Clone or initialize the intended repository into
the default `worktree/` subdirectory (with a real HEAD commit), then use
`pw worker --project demo --dry-run` or `pw tick --project demo`.
The prepared repository must be on the expected branch (default `main`).
Existing projects are never overwritten.

### Default requirements file and planning

The default requirements path is `<project-root>/<id>/requirements.md`.
When that file and the prepared Git worktree, queue, and work log exist,
an explicit `pw plan --project demo` can invoke the planner without
`config.json`. `pw tick --project demo` may then plan and execute the
next task using normal quota, Git, journal and acceptance checks. Planner
invocation still requires a working, locally installed provider (default:
`hermes` on `PATH`). If requirements are absent, planning stays disabled;
nothing invents a requirements document or auto-approves a milestone.

### Defaults for external integrations

For a project with no `config.json`, Home Assistant quota telemetry is
disabled by default, and the worker does not send Telegram progress messages.
This avoids requiring unrelated Hermes/HA credentials for local operation.
Existing configured projects retain their prior quota default (enabled unless
overridden) and notification behavior. Automatic milestone approval is never
inferred from missing configuration.
