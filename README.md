# Projectwright

Projectwright turns your requirements into a reviewable queue of small development tasks, then coordinates Hermes to work through that queue in a Git repository. It tracks progress and Git changes, checks worker reports, and can pause for human milestone approval.

Hermes is the AI developer: it plans and edits using your configured model and tools. Projectwright manages the requirements, queue, safety checks, progress and approval gates. Planning proposes work; it does not authorize execution. Execution is a separate, explicit action.

## Install and set up

Configure the [signed APT repository](docs/apt-repository.md), including verifying its signing-key fingerprint, then run as your normal user:

```sh
sudo apt update
sudo apt install projectwright
pw setup
```

Do not run `pw setup` with sudo. Hermes CLI must already be installed and configured. Telegram setup is optional.

## Quick start

Use a disposable, initialized Git repository for a first run. Projectwright creates its own state directory and connects to the repository; it does not clone, initialize, or duplicate it. Replace the example path with the path to your existing repository.

```sh
pw init --project myproject --repo ~/repos/myproject
pw requirements --project myproject --edit
pw plan --project myproject
pw status --project myproject
```

Write the requirements as goals and explicitly named milestones. Save and close the editor. `pw plan` is your explicit authorization to plan: it enables planning and asks Hermes to prepare or review the queue. Execution remains disabled. Review `queue.md` and the proposed tasks before proceeding. Planning requires a working Hermes CLI/provider and requirements with named milestones.

When you are ready for a real code change, start a manually confirmed worker run:

```sh
pw start --project myproject
```

Confirm at the prompt. `pw start` persistently enables execution in this project's config, then runs one worker task once. The command does not install or enable a timer; an already-enabled timer may use the stored authorization, so disable recurring automation separately if you do not want it. The authorization remains enabled even if that worker run fails. The worker still applies Projectwright's Git-scope, journal, recovery and task-sequencing checks. Run `pw status --project myproject` to check progress, then review the work log, results, and `git diff` in your repository. Run `pw start` again to manually process another task. To decline the confirmation, answer no; execution remains disabled.

Projects normally live at `$XDG_CONFIG_HOME/projects/myproject` (usually `~/.config/projects/myproject`). An existing repository can be elsewhere, such as `~/repos/myproject`. To use another Projectwright config home, pass `--config-dir /absolute/config/home` to each command; its projects are stored below `projects/`. The default selector retains compatibility with older `~/.config/projectwright/projects` and `~/.hermes/projects` locations without moving or deleting them. See [configuration paths](docs/configuration-home.md).

`pw status` summarizes planning and execution state, queue progress, current decision, blockers and the next action. Use `pw status --project myproject --json` for machine-readable output.

## Reviewing work and approvals

A successful test, completed queue checkbox, worker report or Git commit is not milestone acceptance. Projectwright never infers acceptance from those signals. Milestone approval/acceptance gates remain separate; the existing Telegram approval integration is optional and documented in [Telegram approval setup](docs/user-approval-setup.md).

Recurring automation is also optional and is not enabled by these steps. See `pw timer --help` and the [operator manual](docs/manual.md) before separately configuring a project timer.

## Limits and advanced documentation

A Projectwright project controls one Git worktree. An application repository may be located outside the Projectwright state directory, but coordinated execution that modifies multiple repositories as one task is not supported. Use separate Projectwright projects and review them independently; do not weaken repository scope checks.

- [CLI reference](docs/cli.md)
- [Workflow and milestone gates](docs/workflow.md)
- [Configuration and default paths](docs/configuration-home.md)
- [User and operator manual](docs/manual.md) — safety, recovery and operations
- [Provider adapters](docs/provider-adapters.md)
- [Telegram approval setup](docs/user-approval-setup.md)
- [Coverage boundaries](docs/test-coverage-matrix.md)
- [APT installation](docs/apt-repository.md)
