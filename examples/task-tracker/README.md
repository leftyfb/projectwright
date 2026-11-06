# Task Tracker example

This is a **build-it-yourself** example. Projectwright and Hermes will create the task tracker using Python's standard library; it is not prebuilt. Everything lives in **one Git repository**, with Projectwright state in `.pw/`.

The repository name and Projectwright project ID are both **`task-tracker`**. These instructions use the Debian installation; no Projectwright source checkout is needed.

## 1. Create the project

Run as your normal user (not with `sudo`):

```sh
pw init ~/projects/task-tracker
cd ~/projects/task-tracker
```

This initializes Git and creates `.pw/`. Planning, execution, and timers remain disabled until explicitly authorized.

## 2. Copy the starter and requirements

The Debian package ships both files. Copy them into the new repository:

```sh
cp /usr/share/doc/projectwright/examples/task-tracker/starter/README.md README.md
cp /usr/share/doc/projectwright/examples/task-tracker/requirements.md .pw/requirements.md
```

That's it—**no manual copying and pasting requirements into an editor**.

If running from source instead, copy the same two files from `examples/task-tracker/starter/README.md` and `examples/task-tracker/requirements.md` in your checkout.

Verify the requirements contain both milestones:

```sh
grep '^### TRACK-1-M' .pw/requirements.md
```

## 3. Commit the starter

```sh
git add README.md .gitignore
git commit -m "Initialize task-tracker"
```

You need an initial Git commit for Projectwright's worker. `.pw/` is ignored by default; do **not** force-add it to Git.

## 4. Plan the work

```sh
pw plan --project task-tracker
pw status --project task-tracker
cat .pw/queue.md
```

Review the proposed tasks before executing anything. Planning does not authorize execution. The first milestone (`TRACK-1-M1`) builds the task tracker and its initial tests; `TRACK-1-M2` adds validation and documentation.

## 5. Choose how Projectwright runs tasks

**Option A — automated (recommended to test timers and Telegram approvals):**

```sh
pw config set planning.milestone_sequence strict
pw authorize-execution --project task-tracker --yes --minutes 5
# Timer has been created but left disabled; run the next line when ready.
pw timer enable task-tracker
pw timer status task-tracker
pw status
```

`pw authorize-execution` creates the systemd user timer **disabled by default** and prints the exact `pw timer enable task-tracker` command. Nothing is scheduled until you explicitly enable the timer. This two-step process separates authorization and installation from permission to start recurring work. Run `pw timer disable task-tracker` to stop scheduling; you do not need to reinstall later to enable it again.

Timer intervals range from **1 to 1440 minutes**. The next interval begins **after the previous worker service finishes**: a 15-minute task is not killed or overlapped by a 1-minute timer, and the project lock prevents multiple workers modifying the same project. Each activation attempts at most one task. Milestone M1 must be explicitly approved before strict sequencing allows M2 to be planned. Use local `pw approve TRACK-1-M1` after reviewing the work, or enable optional Telegram approval buttons with `pw setup`. Follow progress using `pw status` and `journalctl --user -u projectwright-worker-task-tracker-*.service -n 30 --no-pager` (replace the wildcard with your service name if your systemd version requires it). When a task is active, `pw status` shows its journal phase and read-only queue counts.

**Option B — manual:** follow the one-task commands in the next sections. **Do not use `pw start` while you are testing unattended execution.** Manual runs are separate explicit authorizations.

## 6. Run one task at a time (manual option)

```sh
pw start --project task-tracker
```

Confirm the prompt. Each `pw start` authorizes only one task and does **not** enable recurring execution. After each task, check:

```sh
pw status --project task-tracker
git status --short
git diff
cat .pw/work_log.md
```

Repeat `pw start --project task-tracker` to work through the current milestone. Hermes should create `task_tracker.py` and the `tests/` directory—those files are intentionally absent from the starter.

After milestone M1 is implemented, run its acceptance test:

```sh
python3 -B -m unittest discover -s tests -p test_task_tracker_m1.py
```

A passing test **is not milestone approval**.

## 7. Approve M1, then complete M2 (manual option)

The milestone ID is taken directly from a `###` heading in `.pw/requirements.md` (for example `### TRACK-1-M1 — ...`); it is not the project name or a task number. To list IDs, run `grep '^### ' .pw/requirements.md`.

Review the files, Git commits, and tests. Then approve M1 locally with `pw approve TRACK-1-M1`. This uses the same guarded acceptance checks as Telegram. If you configured Telegram, you may instead approve using the authorized Telegram buttons. Do not create approval records manually.

Approve M1 locally (skip this command if you already approved through Telegram):

```sh
pw approve TRACK-1-M1
```

After approval:

```sh
pw plan --project task-tracker
pw status --project task-tracker
pw start --project task-tracker
```

Repeat one-task runs and reviews until M2 is implemented, then run:

```sh
python3 -B -m unittest discover -s tests -p test_task_tracker_m2.py
```

Review and approve M2 locally with `pw approve TRACK-1-M2`, or use configured Telegram approval buttons. See the [optional Telegram setup instructions](../../docs/user-approval-setup.md).

## Expected outcomes

- One project at `~/projects/task-tracker/`, containing the application, Git history, and `.pw/` state.
- Requirements at `.pw/requirements.md`, queue at `.pw/queue.md`, and progress at `.pw/work_log.md`.
- No extra cloud services or network access needed by the *task tracker*; Hermes uses your configured provider.
- Unattended execution is optional and must be explicitly enabled with `pw timer enable`.
- Human acceptance, not test success alone, is required before the next milestone.

## Troubleshooting

- **Already initialized?** Don't rerun `pw init` inside an existing `.pw/`.
- **Planning blocked?** Run `pw status --project task-tracker --json`, confirm the copied requirements are nonempty, Git has a commit, and Hermes is configured.
- **Tests not found?** Expected before Hermes implements that milestone.
- **Approval pending?** Review the milestone and run `pw approve TRACK-1-M1` (or the actual pending milestone). Telegram is optional.
- **Unexpected Git changes?** Review them before authorizing more work. Do not commit `.pw/` operational state.
