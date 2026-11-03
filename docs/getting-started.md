# Getting started: create your own Projectwright project

This is a **guided tutorial** for building your own project, not a prepared
demo. If you want to immediately inspect an already-configured project with
a ready queue, start with the [runnable demo](../examples/ready_demo/README.md).

## 1. Set up the tools

Install Projectwright from the [signed APT repository](apt-repository.md).
Configure your chosen Hermes provider and run `pw setup` as your regular
user. Telegram approvals are optional at setup but required for the currently
supported human milestone approval callback.

## 2. Decide what to build and where

Use an *existing initialized* Git repository for the application's files.
Projectwright does not create or modify that repository during `pw init`.
Choose a short identifier, for example `myproject`, and keep the Projectwright
state separate from the application source.

```sh
pw init --project myproject --repo "$HOME/repos/myproject"
```

The default state directory is normally
`$XDG_CONFIG_HOME/projects/myproject` (or `~/.config/projects/myproject`
when XDG_CONFIG_HOME is unset). The application remains in the repository you
selected.

## 3. Write and review requirements

You can describe the project to Hermes or another LLM, using
[the requirements drafting prompt](llm-requirements-onboarding.md) to work
through unknowns before writing `requirements.md`.

```sh
pw requirements --project myproject --edit
```

Review the requirements, split work into milestones, and specify verified
acceptance commands and exact allowed repository-relative paths. Do not
assert that tests exist if building them is part of the proposed work.

## 4. Plan only when ready

```sh
pw plan --project myproject
pw status --project myproject
```

Read the generated `queue.md` in the Projectwright state directory.
Planning proposes work but never authorizes execution. Check scope and
dependencies; revise and replan if needed.

## 5. Manually run and inspect a single task

```sh
pw start --project myproject
pw status --project myproject
git -C "$HOME/repos/myproject" status --short
git -C "$HOME/repos/myproject" diff
```

Review and confirm the one-task prompt. Repeat only after reviewing the
previous task's result. A test passing or a task being checked does not
constitute milestone acceptance.

## 6. Approvals, repeating and recovery

Human milestone acceptance currently uses the configured Telegram callback.
Without it the milestone boundary is intentionally blocked. Scheduled
execution is a separate, opt-in operation; `pw start` alone does not
enable a timer. Review [the workflow](workflow.md),
[Telegram approval setup](user-approval-setup.md) and
[the operator manual](manual.md) before production use.

For a detailed task-by-task build-it-yourself example, see the
[Task Tracker walkthrough](../examples/task_tracker/README.md). Unlike the
[runnable demo](../examples/ready_demo/README.md), the Task Tracker tutorial
starts before requirements and planning are completed.
