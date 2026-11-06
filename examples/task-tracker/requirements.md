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
