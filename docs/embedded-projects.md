# Repository-local Projectwright projects

New Projectwright projects keep their definitions and operational files under the
repository's `.pw/` directory. Existing projects using external state directories
continue to work without automatic migration.

## Initialize

The default project/repository parent is `~/projects`:

```sh
pw init --project task-tracker-example
# Creates ~/projects/task-tracker-example (Git repository) and .pw/
```

Specify an arbitrary destination, or initialize in the current repository:

```sh
pw init ~/repos/task-tracker-example
cd ~/projects/task-tracker-example
pw init .
```

The project ID and repository directory basename must agree.
Initialization fails rather than overwriting an existing `.pw/`. Existing Git
history, source files and commits remain untouched. A new empty Git repository
is created only if the destination is not already a repository.

By default, `/.pw/` is added to the repository's `.gitignore`.
Use `pw init PATH --shared` to opt into tracking human-readable `.pw/README.md`,
`.pw/requirements.md`, and `.pw/config.json`. The queue and work log are ignored
in this mode by default because Projectwright updates them operationally.
Advanced users may explicitly track them, but automated Git cycles will refuse
pending metadata changes: review and commit those changes manually.

Runtime state, approval receipts, locks, logs, and execution results are never
eligible for automated Git commits. Do not force-add them, including with
`git add -f`; a repository with tracked operational state is rejected by
the worker.

Configuration paths such as `queue.md`, `state/worker.lock`, and `..`
for the repository worktree are resolved relative to `.pw/`, not to the
process's current working directory. `.pw/config.json` must not contain secrets.
Keep provider and Telegram credentials in external credential stores (e.g.
the existing Hermes environment file).

## Locate projects and register moves

From the repository root or a nested source directory, Projectwright walks
upward to locate `.pw/`; this lookup stops at a Git boundary. For example,
`pw status` selects the current embedded repository without needing its name.

Each embedded repository is registered outside Git in
`~/.config/projectwright/registry.json` so background Telegram notifications
can find repositories outside `~/projects`. The registry does not contain
provider or Telegram credentials. Duplicate directory names are allowed;
ambiguous callbacks fail closed.

After moving a repository, re-register it:

```sh
cd /new/location/task-tracker-example
pw register .
```

No edits to the internal `.pw/config.json` are needed. Systemd timer units
contain a location-specific project binding; after a move, disable/remove the
old timer and explicitly install a new one. Timer installation is disabled by
default; enabling recurring execution requires separate authorization.

## Legacy migration

Nothing is migrated on an APT upgrade. To inspect and explicitly copy legacy
external state into an existing clean repository:

```sh
pw migrate --project task-tracker-example --repo ~/projects/task-tracker-example
pw migrate --project task-tracker-example --repo ~/projects/task-tracker-example --apply
```

Use `--legacy-root /path/to/existing/projects` when the original state is
outside the default project directory. The first command is a read-only dry-run.
The second refuses active Git cycles, unfinished journals, pending Telegram
approvals, dirty repositories, mismatched Git roots/branches, symlinks and
unexpected custom paths. Original state is left intact for rollback, and the
new project's execution and planning are **disabled**. Review the generated
configuration and copied files before authorizing any new tasks.

Migration does **not** deactivate legacy scheduled units or modify Hermes.
Those changes require separate deliberate administrator action to prevent two
instances acting on the same worktree. No release is performed by migration.

## Compatibility and limitations

Existing `pw init --project NAME --config-dir CONFIG_HOME` continues to
initialize the legacy external layout. `--config-dir` selects the old
configuration home explicitly. `PROJECTWRIGHT_PROJECT_DIR` is an internal
absolute path handoff to child processes and timers, not stored in a project.

Shared mode and migration require a clean Git worktree before normal
execution; metadata changes should be reviewed by a human. The worker fails
closed when runtime files appear in the Git index. Automated tasks still
require normal Git verification, guard checks and milestone acceptance.
