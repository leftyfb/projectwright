# Task Tracker CLI — guided build-it-yourself walkthrough

This is a **build-it-yourself walkthrough**, not the separate [preconfigured runnable demo](../ready_demo/README.md). The Task Tracker repository is intentionally a starter, not a finished application. It contains this walkthrough only; Projectwright and Hermes should implement the Python CLI in the milestones below. The project uses Python's standard library and a local JSON file. It needs no Telegram, cloud service, network access, credentials, or extra package.

## Before you begin

Install Projectwright and configure Hermes with your normal AI provider as described in the [signed APT installation guide](https://github.com/leftyfb/projectwright/blob/main/docs/apt-repository.md). Projectwright's supported Ubuntu releases are 24.04 LTS and 26.04 LTS; the hosted package-install matrix covers both, while manual APT-repository installation was verified on 26.04 only and remains deferred on 24.04. This example does not ask you to configure Telegram. M1 can be planned, executed, tested, and reviewed without Telegram, but completing M1 acceptance and advancing to M2 require a real Telegram approval callback. The example is therefore not an offline-testable end-to-end M1-to-M2 lifecycle.

Commands below assume the Projectwright CLI is `pw`, Python 3 is `python3`, and the example repository is `~/projects/task-tracker`. The Debian package includes the starter file at `/usr/share/doc/projectwright/examples/task_tracker/starter/README.md`; you do **not** need to clone the Projectwright source. If you are running from a source checkout instead of the Debian package, set `PROJECTWRIGHT_CHECKOUT` to your checkout path and use the fallback copy command below. Run commands in the example repository unless indicated otherwise. Avoid using a real project directory: this walkthrough creates a disposable Git repository and its own Projectwright state.

## 1. Create a disposable starter Git repository

```sh
mkdir -p ~/projects/task-tracker
cd ~/projects/task-tracker
git init -b main
```

Copy the starter README **once**, using the method that matches your installation.

**APT package (recommended):**

```sh
cp /usr/share/doc/projectwright/examples/task_tracker/starter/README.md README.md
```

**Source checkout only (alternative, not an additional step):**

```sh
cp "$HOME/repos/projectwright/examples/task_tracker/starter/README.md" README.md
```

If your source checkout is elsewhere, replace `$HOME/repos/projectwright` with its actual path. **Do not run both copy commands.** The installed starter README contains only the project introduction; it is not the requirements document.

Confirm that `README.md` exists, then commit it:

```sh
git add README.md
git -c user.name='Example User' -c user.email='example@example.invalid' commit -m 'docs: start task tracker example'
```

The source and tests do not exist yet. That is intentional: the planner is being asked to develop a scaffold, not rubber-stamp a prebuilt application. If this directory already contains files or work you care about, stop and choose a new empty directory.

## 2. Initialize a separate Projectwright project and add requirements

Use the **same project ID**, `task-tracker-example`, in **every** `pw` command. The directory `~/projects/task-tracker` is the *application Git repository*, not the Projectwright project ID.

```sh
pw init --project task-tracker-example --repo ~/projects/task-tracker
```

Read the JSON returned by `pw init`: its `project_directory` field is the **actual** Projectwright state directory. With the corrected default it is `~/projects/task-tracker-example`. Older installed packages might still select legacy directories; consult the path printed by your actual installed version and do not automatically move existing state.

Now open the requirements editor:

```sh
pw requirements --project task-tracker-example --edit
```

**Important: the editor starts with a blank file.** Copy **the entire Markdown requirements block directly below**, from `# Task Tracker CLI requirements` through the final `README.md` Scope line, **into the editor**, then save and exit. Running `pw requirements --edit` alone does *not* populate requirements, and the starter repository's `README.md` is not a substitute. If no editor opens, set `EDITOR=nano` (or another installed editor) and rerun the command.

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

**Verify the file was actually saved before planning.** Run the following using the `project_directory` path reported by `pw init` (replace the example path if your initialization printed something different):

```sh
PROJECT_STATE="$HOME/.hermes/projects/task-tracker-example" # replace with pw init's project_directory
test -s "$PROJECT_STATE/requirements.md" && echo "Requirements file is nonempty"
sed -n '1,18p' "$PROJECT_STATE/requirements.md"
```

The first line should be `# Task Tracker CLI requirements` and the document should contain both `TRACK-1-M1` and `TRACK-1-M2`. If the file is empty or missing, rerun the editor and save the full requirements block. These checks read only the Projectwright state; they do not execute tasks.

## 3. Plan, then inspect before authorizing work

```sh
pw plan --project task-tracker-example
pw status --project task-tracker-example
```

Read `queue.md` in the **actual `project_directory` printed by `pw init`**, normally `~/projects/task-tracker-example/`. If `pw plan` is blocked, do not execute tasks; use the troubleshooting section below and inspect `pw status --project task-tracker-example --json`. Check that the queue has small tasks for M1 first, the requested paths are the only project files in scope, and no task introduces a dependency or external service. Planning is not execution authorization. Fix requirements and re-plan if the proposal is unsafe or out of scope.

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

A passing test, completed queue, or commit is not milestone approval. Projectwright records human acceptance through its configured Telegram approval callback. If Telegram is not configured, review is still useful, but the acceptance gate is intentionally blocked: do not edit receipts, check queue boxes, or otherwise bypass it. Set up Telegram only if you want to exercise the real approval callback, following [Projectwright's Telegram approval setup](https://github.com/leftyfb/projectwright/blob/main/docs/user-approval-setup.md) and authorized-user safeguards.

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

- **`pw status --project task-tracker` says the project is not initialized:** you initialized `task-tracker-example`, not `task-tracker`. Use `pw status --project task-tracker-example` consistently. **Do not rerun `pw init`** on an already initialized project.
- **`pw plan: Planning was blocked`:** first confirm the complete requirements were saved (Step 2). Then run `pw status --project task-tracker-example --json` to inspect `reason`, `blockers`, and `diagnostics`. A blank requirements file, Git worktree problem, or provider problem requires different fixes. Do not infer which one from this generic message alone.
- **`pw init` returned a `~/.hermes/projects/...` path rather than `~/.config/projects/...`:** Projectwright retains a backwards-compatible legacy project root. Use the `project_directory` reported by initialization. It is separate from your application Git repository; no migration or reinitialization is required.
- **I ran both `cp` commands:** they are alternatives, not sequential steps. If the file was copied before your initial Git commit, no harm; only one command is necessary.
- `pw: command not found`: install Projectwright and verify `pw --help` works.
- Hermes/provider errors during `pw plan` or `pw start`: configure the normal Hermes provider and retry; this example does not supply credentials or an alternate provider.
- Planning reports invalid requirements: preserve the exact heading IDs, `#### Acceptance` heading, one literal executable command and one or more repository-relative scope entries per milestone. Keep other criteria outside the acceptance block.
- An acceptance command cannot find a test before implementation: expected for a greenfield milestone; do not treat the proposal as verified. Ask Projectwright to implement the milestone first, then inspect and run the command.
- Acceptance is pending without Telegram: expected. Do not claim approval or manually create acceptance evidence. Follow `docs/user-approval-setup.md` if you choose to enable the supported callback.
- Git reports unexpected changed paths: stop, inspect `git status` and the full diff, and do not authorize more work until the scope is understood.
- JSON database corruption: preserve a copy for inspection; do not delete or overwrite it automatically.
