# Repository-local project layout

Projectwright keeps application code, Git history, and its own state in one repository. For a new project, the default parent is `~/projects`:

```sh
pw init ~/projects/myproject
cd ~/projects/myproject
```

Or, in an existing Git repository:

```sh
cd /path/to/myproject
pw init .
```

Both forms create `.pw/` at the repository root. The repository directory name is also the Projectwright project ID. Initialization does **not** enable planning, persistent execution, timers, or approvals.

| Repository path | Contents |
|---|---|
| `.pw/README.md` | Guide to Projectwright state |
| `.pw/config.json` | Validated project configuration |
| `.pw/requirements.md` | Requirements and milestone acceptance rules |
| `.pw/queue.md` | Planned and completed tasks |
| `.pw/work_log.md` | Task summaries |
| `.pw/state/` | Lock, journal, and runtime state |
| `.pw/logs/` | Operational logs |
| `.pw/results/` | Worker reports |

By default `pw init` adds `/.pw/` to `.gitignore`; no Projectwright state is tracked. `pw init PATH --shared` instead permits selected human-maintained definitions to be committed, but still excludes runtime files. Keep credentials out of configuration and Git.

## Find and configure a project

Within an initialized repository, commands discover the local `.pw/` automatically. From another directory, use `--project NAME` for a registered project. After relocating or cloning a repository with tracked Projectwright definitions, run `pw register .` at its root to refresh registration.

```sh
pw requirements --edit
pw config list
pw config set planning.milestone_sequence strict
pw plan
pw status
pw start
```

Planning and task execution are separate actions. `pw plan` enables planning and requests a queue; `pw start` prompts before one manual dispatcher run. Neither installs a worker schedule.

To authorize recurring work, use:

```sh
pw authorize-execution --yes --minutes 5
```

This creates the per-project systemd user timer, **left disabled**, and prints `pw timer enable NAME` so you can start it when ready. `pw timer disable NAME` stops future scheduled activations.

## Approval without Telegram

After reviewing completed milestone work and commits, run `pw approve YOUR-MILESTONE-ID`. It shows the configured command and scope, requires explicit confirmation, and invokes the same milestone acceptance guard used by Telegram approvals. It will not accept incomplete tasks, untracked required paths, a dirty worktree, or a failed acceptance command.

See the [README](../README.md) for complete examples and the [CLI reference](cli.md) for commands and settings.
