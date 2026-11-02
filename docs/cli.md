# `pw` command-line reference

The `pw` launcher preserves the existing service commands and adds a small onboarding path. Each command supports `--help`.

## First project

```sh
pw init --project NAME --repo /path/to/existing/git-worktree
pw requirements --project NAME --edit
pw plan --project NAME
pw status --project NAME
pw start --project NAME
```

`pw init --repo` verifies that PATH is the root of an initialized Git worktree with a HEAD commit and a named current branch, then stores that path and branch in a new Projectwright config. It does not initialize, clone, checkout, clean, or otherwise modify the repository. Initialization refuses an existing Projectwright project directory. The new project has planning and execution disabled.

`pw requirements --edit` opens the configured requirements file, using `$VISUAL`, then `$EDITOR`, then an available `nano`, `vi`, `vim` or `editor`. Requirements are stored in the Projectwright project directory. Set `VISUAL` or `EDITOR` if no suitable editor is detected.

Invoking `pw plan` explicitly authorizes planning: it enables `planning.enabled` and runs one planning decision. It does not enable execution or run a worker. Review the queue before authorizing execution. Planning requires valid requirements, a usable Git worktree on the configured branch, named milestones where needed, and an available configured Hermes provider.

`pw start` asks for confirmation before persistently setting `execution.enabled` and launching one worker task with `--once`. In non-interactive scripts, `pw start --project NAME --yes` is the explicit confirmation. A declined prompt leaves execution disabled. Start itself is a manual one-task run and never enables timers; an already-enabled timer may use the stored authorization. The authorization remains enabled if the worker fails. The worker's Git scope checks, journals, recovery rules, task sequencing and milestone gates remain in effect.

`pw status` prints a human-readable summary. Add `--json` for machine-readable JSON. Status includes planning/execution configuration, queue counts, manager decision, blockers and a suggested next action.

## Project paths

The default project root is `$XDG_CONFIG_HOME/projects` (normally `~/.config/projects`). The selector recognizes older `$XDG_CONFIG_HOME/projectwright/projects` and `~/.hermes/projects` roots without moving, overwriting or deleting their projects. Existing roots are preferred when the new root has not yet been created. Use `--config-dir /absolute/config/home` consistently to select a config home; the project directory is `config-home/projects/NAME`. `PROJECTWRIGHT_CONFIG_DIR` has the same config-home meaning. The legacy `HERMES_PROJECT_CONFIG_DIR` remains a direct project-root override.

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

Legacy `pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify`, and `pw-timer` entrypoints remain available. `pw init --project NAME --no-config` retains its config-free skeleton behavior; it cannot be combined with `--repo`.

A Projectwright project controls one worktree. A repository can be outside its state directory, but coordinated execution across multiple repositories as one task is not supported. Preserve the worker's existing repository-scope safeguards. See [workflow](workflow.md), [configuration paths](configuration-home.md), and the [operator manual](manual.md) for advanced behavior, recovery and approvals.
