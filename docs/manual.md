# Projectwright operator manual

The [README](../README.md) is the self-contained starting point for new projects and the Task Tracker example. This document describes operation and recovery once a project has been initialized.

## Safety model

Projectwright orchestrates Hermes; it is not an AI model itself. Its Git worktree and task journal are authoritative evidence. The manager checks requirements, queue validity, worktree/branch state, lock and journal, optional quotas, and milestone policy. Planner results are proposals. Workers must produce structured task reports, and edited files and commits must remain inside approved scope.

- `pw plan` authorizes planning only.
- `pw start` asks for confirmation before one manual dispatcher cycle.
- `pw authorize-execution --yes --minutes N` authorizes persistent execution and **creates a disabled** per-project systemd user timer. It prints the exact activation command.
- `pw timer enable PROJECT` starts recurring execution; `pw timer disable PROJECT` stops the schedule.
- `pw approve MILESTONE-ID` accepts a completed milestone locally **without Telegram**, after running the configured acceptance guard and an explicit human confirmation.
- Telegram approval buttons are optional. They use the same guard; enabling notifications is a separately consented action.
- `pw notify` previews without sending; `pw notify --send` contacts configured Telegram recipients.

## Repository and state

`pw init ~/projects/NAME` creates a Git repository when necessary and a private `.pw/` state directory within it. Run `pw init .` to add Projectwright to an existing Git repository. Projectwright does not enable tasks, timers, or Telegram merely because it was initialized.

| Location | Purpose |
|---|---|
| `.pw/config.json` | Project configuration |
| `.pw/requirements.md` | Reviewed milestone requirements and acceptance policy |
| `.pw/queue.md` | Planner queue and completed task checks |
| `.pw/work_log.md` | Worker summaries |
| `.pw/state/` | Lock and live task/cycle journal |
| `.pw/logs/` | Operational logs |
| `.pw/results/` | Result artifacts |

`.pw/` is ignored by Git by default. Never add credentials to the repository. For the optional shared-definitions mode, use `pw init PATH --shared`; its runtime files remain excluded.

## Typical supervised operation

```sh
pw requirements --edit
pw config set planning.milestone_sequence strict
git status --short
pw plan
pw status
cat .pw/queue.md
pw start
pw status
git status --short
cat .pw/work_log.md
```

Repeat the reviewed single-task run until the current milestone finishes. Once all tasks are committed, inspect the changes and evidence, then:

```sh
pw approve APP-1-M1
pw plan
pw status
```

The ID is the identifier from a `###` milestone heading in `.pw/requirements.md` (e.g. `APP-1-M1`), not a task ID. The milestone must have a valid `#### Acceptance` block in requirements with one command and one or more literal tracked scope paths. The command is executed as argv (not in a shell) under the project lock. The guard requires completed milestone tasks including a COMMIT, a clean worktree on the expected branch, valid scoped paths and a passing acceptance command. A test run alone is not approval. The guard refuses stale or rejected pending Telegram evidence rather than allowing local approval to override it.

## Unattended task execution

```sh
pw authorize-execution --yes --minutes 5
```

Expected message:

```text
Timer created for NAME (5-minute interval) and LEFT DISABLED.
No recurring tasks will run until you explicitly enable the timer.
When ready, run: pw timer enable NAME
To check status: pw timer status NAME
```

Then explicitly start and inspect the schedule:

```sh
pw timer enable NAME
pw timer status NAME
pw status
```

Intervals are 1–1440 minutes; the default is 20 minutes. A new activation is scheduled after the previous worker service ends, and the per-project lock prevents concurrent execution. Each activation attempts at most one worker task. A schedule never automatically accepts a milestone.

If the timer already exists with the same configuration and is disabled, authorization may reuse it. Unexpected, incomplete, or already enabled systemd units cause authorization to refuse the change, rather than overwriting custom units.

## Telegram approvals (optional)

Run `pw setup` as the ordinary Hermes user. It validates Hermes and, when Telegram credentials and authorized users are present, asks before enabling the approval plugin and user notification timer. An active gateway may need a reviewed restart with `pw gateway-restart`. Telegram transport is not needed for `pw approve MILESTONE-ID`. See [Telegram setup](user-approval-setup.md).

## Status and recovery

```sh
pw status
pw status --json
git status --short
cat .pw/queue.md
cat .pw/work_log.md
```

Status can report missing/invalid acceptance policy, wrong Git branch, uncommitted changes, a busy worker, incomplete tasks, quota failures, and unresolved journal/recovery incidents. A busy lock while a worker is active is not itself grounds for deleting lock files. Resolve reported issues, inspect logs and Git evidence, and avoid manually modifying a queue, receipt or journal during execution. Never forge milestone receipts to bypass an approval failure.

Use [baseline diagnostics](baseline-validation.md), [workflow mechanics](workflow.md), [CLI reference](cli.md), and [provider adapters](provider-adapters.md) for detailed contracts.

## Development and releases

Use the repository's tests and CI to validate modifications before publishing. The release tooling and APT signing workflow are documented in [release-process.md](release-process.md) and [apt-repository.md](apt-repository.md). Do not treat source-tree execution as equivalent to an installed-package test.
