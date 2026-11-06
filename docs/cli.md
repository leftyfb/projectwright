# `pw` command-line reference

The `pw` launcher preserves the existing service commands and adds a small onboarding path. Each command supports `--help`.

## Initialization and basic commands

`pw init PATH` initializes a Git repository at PATH if necessary and creates its local `.pw/` directory. Without a custom path, `pw init --project NAME` uses `~/projects/NAME`. To initialize an existing repository, use `pw init .` at its root. Initialization does not enable planning, execution, or timers.

`pw init PATH --shared` allows selected human-readable `.pw/` definitions to be tracked; default mode ignores all of `.pw/`. Existing legacy installations using `--repo` and `--config-dir` remain compatible.

The primary commands are `pw requirements --project NAME --edit`, `pw plan --project NAME`, `pw status --project NAME`, and `pw start --project NAME`. For a complete runnable walkthrough and packaged requirements, use [the Task Tracker example](../examples/task-tracker/README.md).

`pw requirements --edit` opens the configured requirements file, using `$VISUAL`, then `$EDITOR`, then an available `nano`, `vi`, `vim` or `editor`. Requirements are stored in the Projectwright project directory. Set `VISUAL` or `EDITOR` if no suitable editor is detected.

Invoking `pw plan` explicitly authorizes planning: it enables `planning.enabled` and runs one planning decision. It does not enable execution or run a worker. Review the queue before authorizing execution. Planning requires valid requirements, a usable Git worktree on the configured branch, named milestones where needed, and an available configured Hermes provider.

`pw start` asks for confirmation before launching one manual dispatcher run. It does not modify `execution.enabled`, install a timer, or enable recurring execution. In non-interactive scripts, `pw start --project NAME --yes` is the explicit confirmation. A declined prompt leaves the project unchanged. The worker's Git scope checks, journals, recovery rules, task sequencing and milestone gates remain in effect.

Persistent execution is separately authorized with `pw authorize-execution --project NAME --yes`; this only changes the persistent project setting. To run unattended, install a disabled timer, then enable it:

```sh
pw authorize-execution --project NAME --yes
pw timer install-disabled NAME
pw timer enable NAME
```

Use `pw timer disable NAME` to stop recurring runs and `pw timer status NAME` to inspect the timer. `pw start` never authorizes persistent execution, installs a timer, or enables recurring execution.

`pw status` prints a human-readable summary. Add `--json` for machine-readable JSON. Both formats include the manager decision and reason, queue counts, blockers, project settings, and next action. JSON adds `recurring_execution_configured` and `recurring_execution_enabled`; these are `unknown` when the user timer cannot be inspected reliably, and `recurring_execution` summarizes the result as `enabled`, `disabled`, `not_configured`, or `unknown`.

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
| `pw gateway-restart` | Prompt the current user to restart an active Hermes gateway after an install or upgrade |

Legacy `pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify`, and `pw-timer` entrypoints remain available. `pw init --project NAME --no-config` retains its config-free skeleton behavior; it cannot be combined with `--repo`.

A Projectwright project controls one worktree. A repository can be outside its state directory, but coordinated execution across multiple repositories as one task is not supported. Preserve the worker's existing repository-scope safeguards. See [workflow](workflow.md), [configuration paths](configuration-home.md), and the [operator manual](manual.md) for advanced behavior, recovery and approvals.
