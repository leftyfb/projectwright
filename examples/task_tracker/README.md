# Task Tracker example

This is a **build-it-yourself** example. Projectwright and Hermes will create the task tracker; it is not prebuilt. Everything lives in **one Git repository**, with Projectwright state in `.pw/`.

The repository name and Projectwright project ID are both **`task-tracker-example`**. These instructions use the Debian installation; no Projectwright source checkout is needed.

## 1. Create the project

Run as your normal user (not with `sudo`):

```sh
pw init ~/projects/task-tracker-example
cd ~/projects/task-tracker-example
```

This initializes Git and creates `.pw/`. Planning, execution, and timers remain disabled until explicitly authorized.

## 2. Copy the starter and requirements

The Debian package ships both files. Copy them into the new repository:

```sh
cp /usr/share/doc/projectwright/examples/task_tracker/starter/README.md README.md
cp /usr/share/doc/projectwright/examples/task_tracker/requirements.md .pw/requirements.md
```

That's it—**no manual copying and pasting requirements into an editor**.

If running from source instead, copy the same two files from `examples/task_tracker/starter/README.md` and `examples/task_tracker/requirements.md` in your checkout.

Verify the requirements contain both milestones:

```sh
grep '^### TRACK-1-M' .pw/requirements.md
```

## 3. Commit the starter

```sh
git add README.md .gitignore
git commit -m "Initialize task-tracker-example"
```

You need an initial Git commit for Projectwright's worker. `.pw/` is ignored by default; do **not** force-add it to Git.

## 4. Plan the work

```sh
pw plan --project task-tracker-example
pw status --project task-tracker-example
cat .pw/queue.md
```

Review the proposed tasks before executing anything. Planning does not authorize execution. The first milestone (`TRACK-1-M1`) builds the task tracker and its initial tests; `TRACK-1-M2` adds validation and documentation.

## 5. Run one task at a time

```sh
pw start --project task-tracker-example
```

Confirm the prompt. Each `pw start` authorizes only one task and does **not** enable recurring execution. After each task, check:

```sh
pw status --project task-tracker-example
git status --short
git diff
cat .pw/work_log.md
```

Repeat `pw start --project task-tracker-example` to work through the current milestone. Hermes should create `task_tracker.py` and the `tests/` directory—those files are intentionally absent from the starter.

After milestone M1 is implemented, run its acceptance test:

```sh
python3 -B -m unittest discover -s tests -p test_task_tracker_m1.py
```

A passing test **is not milestone approval**.

## 6. Approve M1, then complete M2

Projectwright uses an authorized Telegram approval callback for milestone acceptance. Review the files, Git commits, and tests, then approve M1 with the Telegram buttons. Without configured Telegram approvals, Projectwright correctly stops at the acceptance gate. Do not create approval records manually.

After approval:

```sh
pw plan --project task-tracker-example
pw status --project task-tracker-example
pw start --project task-tracker-example
```

Repeat one-task runs and reviews until M2 is implemented, then run:

```sh
python3 -B -m unittest discover -s tests -p test_task_tracker_m2.py
```

Review and approve M2 through Telegram. See the [Telegram setup instructions](https://github.com/leftyfb/projectwright/blob/main/docs/user-approval-setup.md) if approval delivery is not configured.

## Expected outcomes

- One project at `~/projects/task-tracker-example/`, containing the application, Git history, and `.pw/` state.
- Requirements at `.pw/requirements.md`, queue at `.pw/queue.md`, and progress at `.pw/work_log.md`.
- No extra cloud services or network access needed by the *task tracker*; Hermes uses your configured provider.
- No unattended execution enabled by this walkthrough.
- Human acceptance, not test success alone, is required before the next milestone.

## Troubleshooting

- **Already initialized?** Don't rerun `pw init` inside an existing `.pw/`.
- **Planning blocked?** Run `pw status --project task-tracker-example --json`, confirm the copied requirements are nonempty, Git has a commit, and Hermes is configured.
- **Tests not found?** Expected before Hermes implements that milestone.
- **Approval pending?** Configure Telegram and authorized users, or stop at the approval gate.
- **Unexpected Git changes?** Review them before authorizing more work. Do not commit `.pw/` operational state.
