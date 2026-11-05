# Task Tracker CLI — Projectwright guided walkthrough

This is the **build-it-yourself** example for Projectwright's repository-local `.pw/` layout, not a prebuilt application. Projectwright plans the work and Hermes implements the tracker. For a separate runnable demo, see the [ready demo](../ready_demo/README.md).

The **project ID, Git repository directory, and all examples use one name**: `task-tracker-example`. The default home is `~/projects`, but you can initialize a repository in any directory you choose.

## Prerequisites

Install the development Projectwright Debian package or an equivalent source version with embedded `.pw/` support. Hermes must be configured with your chosen provider. Python 3 and Git are required. The tracker itself uses only the Python standard library, local JSON storage, and no cloud services or extra packages.

The installed walkthrough is at `/usr/share/doc/projectwright/examples/task_tracker/README.md`, and its starter README is at `/usr/share/doc/projectwright/examples/task_tracker/starter/README.md`. These commands assume `pw` is on `PATH`. Do not use an existing repository or project containing work you want to keep.

## 1. Initialize one repository-local project

Run this from any directory:

```sh
pw init ~/projects/task-tracker-example
cd ~/projects/task-tracker-example
```

This creates the Git repository, `.pw/` state directory, `.pw/README.md`, `.pw/config.json`, requirements and queue files, and the default `/.pw/` Git ignore rule. It does **not** enable unattended execution, configure a timer, or run an agent.

If you prefer another parent directory, substitute your path in the `pw init` command. To initialize an existing repository, go to its root and use `pw init .` instead. Its directory basename must match the Projectwright project ID.

Copy the starter application README **once**, based on your installation.

**Debian installation:**

```sh
cp /usr/share/doc/projectwright/examples/task_tracker/starter/README.md README.md
```

**Source checkout alternative:**

```sh
cp ~/repos/projectwright/examples/task_tracker/starter/README.md README.md
```

Do not run both commands. The starter is only an introduction; it is not the full requirements specification. If your source checkout is elsewhere, change the source path.

Create the first Git commit before planning:

```sh
git add .gitignore README.md
git -c user.name='Example User' -c user.email='example@example.invalid' commit -m 'docs: initialize task-tracker-example'
git status --short
```

If you have your normal Git identity configured, you may omit the temporary `-c` options. The Git status should be clean. Do not force-add `.pw/` or commit operational files.

## 2. Save the requirements inside `.pw/`

From the repository root, run:

```sh
pw requirements --project task-tracker-example --edit
```

The editor opens `~/projects/task-tracker-example/.pw/requirements.md`. The file starts blank. Paste **the entire requirements block below**, save, and exit. Set `EDITOR=nano` if your editor does not open.

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

Those acceptance commands describe future deliverables, **not files or tests that already exist**. They should be verified after Hermes implements them.

Check that the requirements actually saved:

```sh
test -s .pw/requirements.md && echo "Requirements saved"
sed -n '1,18p' .pw/requirements.md
grep '^### TRACK-1-M' .pw/requirements.md
```

You should see both `TRACK-1-M1` and `TRACK-1-M2`. If the file is empty, reopen the editor. Do not begin planning with missing requirements.

## 3. Plan and review the queue

```sh
pw plan --project task-tracker-example
pw status --project task-tracker-example
cat .pw/queue.md
```

Explicit `pw plan` authorizes planning, but not execution. Review M1's proposed task descriptions and file scopes. Projectwright should not begin M2 until M1 has passed its tests and the human approval gate. If planning is blocked, inspect:

```sh
pw status --project task-tracker-example --json
cat .pw/config.json
```

The default Home Assistant quota integration is disabled; this walkthrough requires no HA token or quota sensor. Never add secrets to `.pw/config.json`, and do not enable `execution.enabled` to work around blockers.

## 4. Execute and inspect one task at a time

```sh
pw start --project task-tracker-example
```

Confirm the prompt to authorize **one** dispatcher cycle. A one-shot start does not enable persistent execution or recurring timers. After each task:

```sh
pw status --project task-tracker-example
git status --short
git diff --check
git diff
cat .pw/work_log.md
```

Review and repeat `pw start --project task-tracker-example` as appropriate for the remaining M1 tasks. Projectwright/Hermes should create `task_tracker.py` and `tests/` during this work. Do not add or edit `.pw` approval records, operational state, or locks.

After M1 is implemented, independently run its proposed acceptance test:

```sh
python3 -B -m unittest discover -s tests -p test_task_tracker_m1.py
```

An absent test before M1 is implemented is expected. A passing test is **not** human milestone acceptance.

## 5. Approve the milestone through Telegram

Projectwright's configured Telegram integration is the supported human acceptance path. Once all M1 tasks, Git commits, and tests are verified, Projectwright should present an approval request through Telegram. Approve or reject the pinned milestone using its real callback buttons.

If you have not configured authorized Telegram recipients, Projectwright must remain at `awaiting_acceptance`. Do not manually create an approval receipt or mark tasks complete to bypass this gate. See the [Telegram approval setup](https://github.com/leftyfb/projectwright/blob/main/docs/user-approval-setup.md).

After approval, verify the next milestone is available:

```sh
pw status --project task-tracker-example
pw plan --project task-tracker-example
cat .pw/queue.md
```

Use repeated `pw start --project task-tracker-example` one-shot runs to work through M2, then run:

```sh
python3 -B -m unittest discover -s tests -p test_task_tracker_m2.py
```

Review and approve M2 in Telegram. The task tracker is finished only after verified work and the required human milestone acceptance.

## Expected outcomes

- One Git repository named `task-tracker-example` contains both application deliverables and ignored Projectwright state under `.pw/`.
- `.pw/config.json` uses portable relative paths; moving the repository does not require rewriting them.
- Planning creates `.pw/queue.md`; it does not run Hermes tasks.
- Each confirmed `pw start` runs no more than one task and does not install a timer.
- The tracker source and tests are generated during development, not provided in the starter.
- Approval requires a genuine authorized Telegram callback. Without it, M2 remains blocked.
- Git operations never stage runtime `.pw` logs, approvals, journals, results, or credentials.

## Troubleshooting

- **Wrong project name:** Use `task-tracker-example` in the repository directory and every explicit `--project` option. Do not use `task-tracker`.
- **Already initialized:** `pw init` refuses to overwrite an existing `.pw/`. Do not rerun initialization for a project you already started.
- **Planning blocked:** Confirm `.pw/requirements.md` is nonempty, the requirements parse correctly, the Git repository has an initial commit on its configured branch, and the Hermes provider is available. Inspect `pw status --project task-tracker-example --json`.
- **Missing tests before implementation:** Expected for a greenfield project. Run the milestone tests after its code is created.
- **Approval pending:** Configure the supported Telegram integration and authorized users, or stop at the approval gate.
- **Unexpected Git changes:** Stop and inspect `git status` and `git diff` before executing further tasks.
- **Invalid requirements:** Preserve exact milestone IDs, each `#### Acceptance` heading, one literal executable acceptance command, and one or more repository-relative scope paths.
- **Database corruption:** Preserve a copy for inspection; do not delete or overwrite user data automatically.

## Automated test coverage

The repository has disposable end-to-end tests using a fake Hermes provider and separate tests for embedded `.pw/` project execution and Telegram approval callbacks. These are not claims that your real Hermes provider or live Telegram delivery was exercised by CI. This walkthrough is intended to validate those integrations on your test installation.
