# Task Tracker CLI — Projectwright example

This repository is intentionally a starter, not a finished application. It contains this walkthrough only; Projectwright and Hermes should implement the Python CLI in the milestones below. The project uses Python's standard library and a local JSON file. It needs no Telegram, cloud service, network access, credentials, or extra package.

## Before you begin

Install Projectwright and configure Hermes with your normal AI provider as described in the [signed APT installation guide](../../docs/apt-repository.md). Projectwright's supported Ubuntu releases are 24.04 LTS and 26.04 LTS; the hosted package-install matrix covers both, while manual APT-repository installation was verified on 26.04 only and remains deferred on 24.04. This example does not ask you to configure Telegram. M1 can be planned, executed, tested, and reviewed without Telegram, but completing M1 acceptance and advancing to M2 require a real Telegram approval callback. The example is therefore not an offline-testable end-to-end M1-to-M2 lifecycle.

Commands below assume the Projectwright CLI is `pw`, Python 3 is `python3`, and the example repository is `~/projects/task-tracker`. Set `PROJECTWRIGHT_CHECKOUT` to the path of your Projectwright source checkout before copying the starter file. Run commands in the example repository unless indicated otherwise. Avoid using a real project directory: this walkthrough creates a disposable Git repository and its own Projectwright state.

## 1. Create a disposable starter Git repository

```sh
PROJECTWRIGHT_CHECKOUT="$HOME/repos/projectwright" # change if your checkout is elsewhere
mkdir -p ~/projects/task-tracker
cd ~/projects/task-tracker
git init -b main
```

Copy the intentionally minimal starter README from the Projectwright checkout, then commit it:

```sh
cp "$PROJECTWRIGHT_CHECKOUT/examples/task_tracker/starter/README.md" README.md
```

```sh
git add README.md
git -c user.name='Example User' -c user.email='example@example.invalid' commit -m 'docs: start task tracker example'
```

The source and tests do not exist yet. That is intentional: the planner is being asked to develop a scaffold, not rubber-stamp a prebuilt application. If this directory already contains files or work you care about, stop and choose a new empty directory.

## 2. Initialize a separate Projectwright project and add requirements

```sh
pw init --project task-tracker-example --repo ~/projects/task-tracker
pw requirements --project task-tracker-example --edit
```

In the editor, replace the blank draft with the complete requirements below. Save and exit. The requirements file is stored with Projectwright state, separately from the Git repository.

```markdown
# Task Tracker CLI requirements

## TRACK-1 — Manage a local task list

Build a small, maintainable Python command-line task tracker. Use Python 3 standard library only. Persist tasks in a JSON file selected with `--db PATH`; default to `tasks.json` in the current working directory. Do not read or write outside the selected database path and repository scope. Never execute shell commands from task data.

Non-goals: synchronization, accounts, network access, GUI, due dates, priorities, plugins, third-party dependencies, and automatic deletion of user data. Do not modify files outside the scopes listed for the active milestone. Keep tests isolated with temporary directories.

### TRACK-1-M1 — Scaffold and core task lifecycle
- Provide `task_tracker.py` as an executable module with `add`, `list`, and `done` subcommands.
- `add` stores a non-empty task and prints its stable integer ID; `list` displays IDs, completion state, and task text; `done ID` marks the matching task complete.
- Store JSON atomically enough to avoid exposing partially serialized data (write a temporary sibling then replace); create the database only when a mutating command is used.
- Provide standard-library `unittest` coverage in `tests/test_task_tracker_m1.py`, using temporary database paths.
- PROPOSED — NOT IMPLEMENTED/VERIFIED until the task is built: acceptance command and scope below.

#### Acceptance
- **Command:** `python3 -B -m unittest discover -s tests -p test_task_tracker_m1.py`
- **Scope:** `task_tracker.py`
- **Scope:** `tests/test_task_tracker_m1.py`

### TRACK-1-M2 — Safe validation and user-facing errors
- Reject blank task text, malformed database JSON, unknown task IDs, and invalid IDs with a concise error and non-zero exit status; do not silently overwrite malformed data.
- Ensure listing an absent database reports an empty list without creating a file.
- Document all subcommands, database behavior, examples, and recovery guidance in `README.md`.
- Provide standard-library `unittest` coverage in `tests/test_task_tracker_m2.py`; tests must not use the real working directory database.
- PROPOSED — NOT IMPLEMENTED/VERIFIED until the task is built: acceptance command and scope below.

#### Acceptance
- **Command:** `python3 -B -m unittest discover -s tests -p test_task_tracker_m2.py`
- **Scope:** `task_tracker.py`
- **Scope:** `tests/test_task_tracker_m2.py`
- **Scope:** `README.md`
```

The commands and future source/test paths above are proposed deliverables, not claims that the files or tests already exist. After each milestone is implemented, inspect its exact command, paths, test safety, and Git tracking before requesting acceptance. Do not broaden scope just to make a command pass.

## 3. Plan, then inspect before authorizing work

```sh
pw plan --project task-tracker-example
pw status --project task-tracker-example
```

Read `queue.md` in the Projectwright state directory (normally `~/.config/projects/task-tracker-example/queue.md`). Check that the queue has small tasks for M1 first, the requested paths are the only project files in scope, and no task introduces a dependency or external service. Planning is not execution authorization. Fix requirements and re-plan if the proposal is unsafe or out of scope.

## 4. Run one task at a time

When the plan is acceptable, authorize one manual dispatcher cycle:

```sh
pw start --project task-tracker-example
```

Confirm the prompt. This is a one-shot run, not a recurring timer. Then review status and the repository diff:

```sh
pw status --project task-tracker-example
git -C ~/projects/task-tracker status --short
git -C ~/projects/task-tracker diff --check
git -C ~/projects/task-tracker diff
```

Repeat planning/review and one-shot starts only as appropriate for the remaining queue. Do not use `pw authorize-execution` or enable timers for this tutorial. Run the milestone's exact acceptance command yourself as a test, and inspect every changed file.

## 5. Human acceptance and next milestone

A passing test, completed queue, or commit is not milestone approval. Projectwright records human acceptance through its configured Telegram approval callback. If Telegram is not configured, review is still useful, but the acceptance gate is intentionally blocked: do not edit receipts, check queue boxes, or otherwise bypass it. Set up Telegram only if you want to exercise the real approval callback, following Projectwright's Telegram approval setup and authorized-user safeguards.

After M1's work has been reviewed and accepted through the supported Telegram callback, refresh the plan and status, verify that M2 is now the active milestone, then use `pw start --project task-tracker-example` for one task at a time. Repeat review, validation, and human acceptance. Without Telegram acceptance, stop at the gate rather than claiming progression; M2 execution is not available through this offline walkthrough.

## What automated and live testing cover

The repository's automated `tests/integration/test_task_tracker_projectwright_e2e.py` uses a disposable Git repository, isolated Projectwright state, the installed-style `pw` entrypoint, and a controlled fake Hermes provider. It covers initialization, requirements, planning/queue creation, a one-shot run, the separate execution-authorization state, a manually driven task cycle, and the M1 acceptance block without Telegram. It does not test a real Hermes provider, Telegram delivery/callbacks, or M2 progression.

A separate live-Hermes smoke test performed initialization, planning, and one one-shot task, then stopped at the genuine M1 human-acceptance gate. It did not record approval, test Telegram, or advance to M2. The automated fake-provider test and that limited live smoke test are distinct evidence; neither claims the full lifecycle was completed.

## Expected outcomes

- Initialization creates Projectwright state separately from the disposable Git repository.
- Planning produces a reviewable queue; it does not run code.
- Each confirmed `pw start` authorizes only one manual dispatcher cycle; execution remains non-recurring.
- The starter repository contains no completed tracker. Its source and tests appear only as Projectwright executes approved tasks.
- When built, `python3 -B -m unittest discover -s tests -p test_task_tracker_m1.py` and the corresponding M2 command should pass. Initially they are expected to fail because the example is deliberately unimplemented.
- With Telegram approval unavailable, the workflow is verified only through task completion/review, not through milestone acceptance or progression.
- Reaching M2 requires a real human acceptance through Telegram; do not treat the fake-provider integration test as evidence of Telegram or M2 behavior.

## Troubleshooting

- `pw: command not found`: install Projectwright and verify `pw --help` works.
- Hermes/provider errors during `pw plan` or `pw start`: configure the normal Hermes provider and retry; this example does not supply credentials or an alternate provider.
- Planning reports invalid requirements: preserve the exact heading IDs, `#### Acceptance` heading, one literal executable command and one or more repository-relative scope entries per milestone. Keep other criteria outside the acceptance block.
- An acceptance command cannot find a test before implementation: expected for a greenfield milestone; do not treat the proposal as verified. Ask Projectwright to implement the milestone first, then inspect and run the command.
- Acceptance is pending without Telegram: expected. Do not claim approval or manually create acceptance evidence. Follow `docs/user-approval-setup.md` if you choose to enable the supported callback.
- Git reports unexpected changed paths: stop, inspect `git status` and the full diff, and do not authorize more work until the scope is understood.
- JSON database corruption: preserve a copy for inspection; do not delete or overwrite it automatically.
