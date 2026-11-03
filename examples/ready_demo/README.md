# Ready-to-run demo: preplanned counter library

**This is a demo, not the tutorial for creating your own project.** It starts
with a real Git repository, valid Projectwright state, requirements, a preloaded
four-task queue, and deliberately failing tests. You do **not** need to write
requirements or invoke a planner. The configured Hermes provider executes
the tasks when you explicitly authorize them. Results depend on the live
provider; no expected model response or Git commit is fabricated.

For a guided tutorial on defining a *new* project, use
[Getting started](../../docs/getting-started.md).

## Prerequisites and safety

Install Projectwright, run `pw setup` as your ordinary user, and configure
Hermes separately. Requires `bash`, `git` and `python3`. The demo uses
your actual Hermes configuration, so your provider may incur usage charges.
There is **no automatic execution** or recurring timer. The script refuses
to reuse an existing demo directory and does not modify existing projects.
It creates its own Git repository and state and uses a fake Git author identity
only for the initial repository commit.

This demo tests task execution, but **does not exercise Telegram acceptance**:
finishing the four tasks is not a milestone approval. Do not invent a receipt
or manually bypass the human-approval gate. Use a separate disposable demo.

## 1. Initialize the already-planned example

Installed Debian package:

```sh
bash /usr/share/doc/projectwright/examples/ready_demo/bootstrap.sh
```

From a source checkout:

```sh
bash examples/ready_demo/bootstrap.sh
```

Pass an absolute path as the first argument to choose a different destination.
By default this creates `~/projectwright-demo/`:

```text
projectwright-demo/
├── repo/                         # actual Git repository for Hermes to edit
│   ├── README.md
│   ├── counter.py                 # intentionally raises NotImplementedError
│   └── tests/test_counter.py      # three already-written tests
└── state/
    └── projects/demo-counter/    # Projectwright's separate project state
        ├── config.json
        ├── requirements.md
        ├── queue.md
        └── work_log.md
```

The bootstrap uses `pw init` to create real project state, then provides a
reviewed sample queue and requirements. Paths inside `config.json` are
generated for this machine. This is why the demo is bootstrapped rather than
shipping a nonportable hardcoded `config.json`.

## 2. Inspect everything before running

```sh
export PROJECTWRIGHT_CONFIG_DIR="$HOME/projectwright-demo/state"
pw status --project demo-counter
cat "$PROJECTWRIGHT_CONFIG_DIR/projects/demo-counter/requirements.md"
cat "$PROJECTWRIGHT_CONFIG_DIR/projects/demo-counter/queue.md"
git -C "$HOME/projectwright-demo/repo" status --short
python3 -B -m unittest discover -s "$HOME/projectwright-demo/repo/tests" -p test_counter.py
```

Expected: four unchecked queue tasks (P100–P103), clean Git working tree,
and **three test errors** caused by `NotImplementedError`. The initial
failure is intentional. `pw status` is read-only; its exact fields may
change between versions. Planning is disabled because the queue is already
prepared. Execution is disabled except for one-task manual authorization.

## 3. Run and inspect one task at a time

```sh
pw start --project demo-counter
pw status --project demo-counter
cat "$PROJECTWRIGHT_CONFIG_DIR/projects/demo-counter/queue.md"
git -C "$HOME/projectwright-demo/repo" status --short
git -C "$HOME/projectwright-demo/repo" diff --check
git -C "$HOME/projectwright-demo/repo" diff
```

Confirm the one-shot prompt and review before repeating `pw start`. With a
successful live provider and no safety blockers, expected progression is:

| Run | Task | Expected observable result |
| --- | --- | --- |
| First | P100 READ | P100 checked in queue; no source change |
| Second | P101 EDIT | P101 checked; `counter.py` implements increment; Git shows uncommitted modification |
| Third | P102 TEST | P102 checked after the three tests pass; no test files changed |
| Fourth | P103 COMMIT | P103 checked; Git contains new commit for `counter.py`; clean working tree |

The task summaries, Git commit SHA and precise CLI output are **not fixed**.
If a step fails, do not blindly keep calling `pw start`; inspect status,
queue, work log and provider errors first. Projectwright must not treat a
failed worker report as successful completion.

## 4. Understand the pieces

| File | Why it exists |
| --- | --- |
| `repo/README.md` | Explains the small application Hermes is building |
| `repo/counter.py` | The deliberately incomplete source to modify |
| `repo/tests/test_counter.py` | Fixed behavioral checks, not to be edited |
| `state/projects/demo-counter/config.json` | Connects the Git repo; disables scheduled execution and planning |
| `state/projects/demo-counter/requirements.md` | Requirement, milestone, acceptance test and allowed Git scope |
| `state/projects/demo-counter/queue.md` | Preplanned READ/EDIT/TEST/COMMIT tasks and completion checkboxes |
| `state/projects/demo-counter/work_log.md` | Human-readable work history; starts empty of executions |
| `git_cycle.json` and worker state (if produced) | Runtime safety and progress data; not starter files |

The separation matters: Projectwright state lives **outside** the repository
that Hermes edits. The EDIT/TEST/COMMIT grouping protects the Git cycle. The
acceptance block is evidence for a future human approval—not an automatic pass.

## 5. Verify the finished repository

After successful tasks:

```sh
cd "$HOME/projectwright-demo/repo"
python3 -B -m unittest discover -s tests -p test_counter.py
git log -2 --oneline
git status --short
```

Expected: three passing tests, an initial setup commit followed by an
implementation commit, and no changed files. The queue should show four
checked items. Milestone acceptance may remain pending without Telegram; that
is an accurate safeguard, not a demo failure.

## Cleanup and troubleshooting

Nothing is removed automatically. Review paths before any cleanup. To discard
the isolated default demo (only if you no longer need its contents), remove
`~/projectwright-demo` yourself; do not run removal commands against a
different configured project root.

- `pw` not found: install the Debian package and check `pw --help`.
- Hermes not configured: finish `pw setup` and Hermes provider setup.
- Directory exists: choose a new absolute destination; never overwrite an
  existing project.
- Git reports unexpected paths: stop and inspect the diff and worker journal.
- Tests fail after EDIT: inspect `counter.py` and the worker report; a live
  provider is not guaranteed to generate correct code.
- Completion blocked by human approval: expected after the milestone, not a
  reason to fabricate approval.

This example performs real local changes and can consume provider tokens.
It does not claim a previously recorded or successful live execution.
