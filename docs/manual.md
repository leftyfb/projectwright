# Projectwright user and operator manual

> **Development branch:** `test/review-followups`. This describes the current implementation, not a supported production release. The Debian artifact is `0.1.0~dev0-1`; no stable upgrade or unattended deployment contract is promised. Commands that execute tasks can modify a configured Git worktree. First practice with a disposable project and account.

## 1. What Projectwright does

Projectwright turns a project's requirements and Markdown task queue into bounded agent work, with policy checks before planning, before running a task, during Git changes, and at milestone acceptance. It is an orchestrator, **not** the model or coding agent itself. The supported 0.1.0 installation requires a locally configured Hermes CLI. An experimental command adapter exists but is not a supported replacement for Hermes in this release. Git is the authoritative evidence for worktree state and scoped commits. Optional Home Assistant telemetry can block work when a configured quota threshold is reached. Telegram and a Hermes gateway plugin provide optional human **milestone** approval; ordinary worker-progress messaging is a separate integration.

The primary command is `pw`. The installed `pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify`, and `pw-timer` entrypoints remain available. Python source modules are currently flat `pw_*.py` modules; `project_*.py` imports are compatibility shims, not independent implementations.

## 2. Read this before running

- Never point a new test at a real project worktree, approval root, bot, or gateway by accident. Inspect `pw defaults` and `pw status` first.
- No `apt install` step should silently select a human account or turn on timers/plugins. Non-root approval onboarding is deliberately explicit.
- A configured worker/provider can change files and make Git commits. A completed queue checkbox is **not** an accepted milestone.
- `pw notify` without `--send` previews; `--send` contacts Telegram. A timer that was explicitly enabled may send autonomously.
- Missing credentials, invalid queue/state, wrong branch, dirty worktree, active journal, unresolved recovery incident, stale callback, or acceptance failure should block progress. Do not delete evidence files merely to clear a block.
- `pw-test` is a disposable LXD environment, not the production host. Its runner is intentionally left offline between test sessions; do not run its workflows without authorization.

## 3. Install and inspect the preview

The source tree requires Python 3.10+ and Git. It defines a setuptools wheel in `pyproject.toml` and constructs an all-architecture Debian development package via `scripts/build-deb.sh`. The Debian package places Python modules under `/usr/lib/python3/dist-packages`, executable wrappers under `/usr/bin`, and *inactive* Hermes and systemd assets under `/usr/share/projectwright`. See [packaging and lifecycle](packaging-and-operations.md) for the precise supported test status and cleanup boundaries.

In a disposable source checkout, offline verification is:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B scripts/validate-baseline.py --mode development
```

Inspect a verified installed preview with:

```sh
pw --help
pw defaults --project demo
pw status --project demo
pw-timer --help
```

Do not install this development preview onto production Hermes just to follow this guide. Hermes is a hard requirement for the supported release, but is typically installed/configured independently of Debian; Telegram activation remains optional and explicitly confirmed during `pw setup`.

## 4. Project layout and configuration selection

With no explicit override, the selected projects directory is `$XDG_CONFIG_HOME/projectwright/projects` (normally `~/.config/projectwright/projects`). If that XDG tree does not exist but `~/.hermes/projects` does, the legacy directory may be used. Selection precedence is:

1. `--config-dir /absolute/path` where supported; its `projects/` child is used.
2. `PROJECTWRIGHT_CONFIG_DIR` (configuration home; append `projects/`).
3. `HERMES_PROJECT_CONFIG_DIR` (legacy **projects directory** itself).
4. XDG root, with legacy fallback as above.

This is a partial migration: the notifier, plugin, account setup and some notes utilities still have Hermes-specific defaults. Never assume every entrypoint honors `--config-dir`. See [configuration-home.md](configuration-home.md) and [CLI](cli.md).

A typical project directory contains:

| Path | Purpose / ownership |
|---|---|
| `config.json` | Optional project-specific settings and explicit enablement; `pw init` creates an inert one |
| `requirements.md` | Human-authored project intent and planning input |
| `queue.md` | Ordered Markdown tasks and completion checkboxes, written by planner/worker |
| `work_log.md` | Human/agent project work record |
| `worktree/` | Default Git repository for config-free projects, must already exist with a HEAD commit |
| `worker.lock` | Serializes project-changing operations |
| `worker_journal.json` | Durable in-flight and last-completed task evidence |
| `worker_state.json` | Progress summary |
| `git_cycle.json` | EDIT/TEST/COMMIT scope, phase and Git snapshot |
| `recovery_incidents.json` | Interrupted/unsafe work requiring review |
| `planning_state.json` | Planner state and milestone acceptance evidence |
| `results/` | Structured task result artifacts |
| `telegram_approval_pending.json` | Pinned pending approval evidence |
| `telegram_approval_notified.json` | Outbound notification/deduplication record |
| `telegram_approval_rejected.json` | Durable rejection record |

Several paths can be overridden in JSON; this table is the conventional/default layout, not a promise that every configured project uses these exact names. Do not hand-edit in-flight state.

## 5. Starting safely

### Option A: initialize a disabled, configured project

```sh
pw init --project demo
pw defaults --project demo
pw status --project demo
```

`pw init` refuses an existing project directory, creates private permissions and writes a `config.json` with execution/planning/notes disabled. It does **not** create a Git repository, queue, model credentials or timers. Enabling execution requires a deliberate config/policy review; there is no general-purpose one-command production bootstrap.

### Option B: a manually prepared, config-free project

```sh
pw init --project demo --no-config
```

This creates empty `queue.md` and `work_log.md`, but **no** `config.json`, Git worktree or execution grant. Prepare a Git repository in `<selected projects directory>/demo/worktree` on branch `main`, with an initial commit. Populate `queue.md` with valid task rows (use the project's tested queue grammar; see [workflow](workflow.md) and tests rather than guessing IDs). Then inspect:

```sh
pw defaults --project demo
pw worker --project demo --dry-run
pw status --project demo
```

For an intentional, manually invoked execution, `pw worker --project demo --once` or `pw tick --project demo --no-telegram` can run when preflight passes. A `requirements.md` permits an explicit `pw plan --project demo` using a configured/available provider. The default Git branch is `main`; `PROJECTWRIGHT_WORKTREE` and `PROJECTWRIGHT_BRANCH` can override the config-free defaults. Config-free does **not** authorize unattended scheduling or approval. If prerequisites are missing, expect `disabled` rather than automatic creation.

For a non-default config home, add `--config-dir /absolute/config/home` consistently to supported commands. Do not mix roots between `status`, `plan`, and `worker`.

### Concrete disposable queue example

For a newly prepared `demo` repository, you can use a single read-only task in `queue.md` to inspect behavior before trying any EDIT/TEST/COMMIT cycle:

```markdown
- [ ] **T101 — READ** Summarize the repository layout and existing tests without changing files.
```

The queue parser requires lines beginning `- [ ]`, `- [x]` or `- [!]`, an uppercase-letter-plus-digit task ID, an em dash or hyphen separator, and one of `READ`, `EDIT`, `TEST`, `COMMIT`, `VERIFY`, `DECIDE`. The example describes a **provider-executed** READ; it is not performed by `pw` itself. The provider must return the requested structured result artifact, and Projectwright will reject Git mutation by a READ task.

For a first config-free Git worktree, the safe sequence is: create a disposable `worktree/` repository on `main` with a HEAD commit, put the row above in `queue.md`, leave `work_log.md` in place, run `pw worker --project demo --dry-run`, then execute `pw tick --project demo --no-telegram` **only** after verifying the selected root and local provider. You need not enable any systemd timer for this test.

### Example of an inert `config.json`

`pw init --project demo` writes a disabled configuration resembling:

```json
{
  "id": "demo",
  "projectwright_initialized": 1,
  "execution": {"enabled": false},
  "planning": {"enabled": false},
  "notes": {"enabled": false}
}
```

The effective config also contains `base`, `queue`, `work_log`, `worktree`, `branch`, `lock`, `result_dir`, `cycle_file`, `worker_journal_file`, `timeout_seconds` (900) and `hermes` (`hermes` on PATH). `pw defaults --project demo` prints merged values. Existing JSON can override these, and configured projects retain legacy quota defaults; do **not** turn `execution.enabled` on without reviewing the provider, Git target, queue, policy and any external integrations.

## 6. Daily command guide

| Intent | Command | Side effects |
|---|---|---|
| Inspect routing | `pw --help` | None |
| Inspect effective defaults/paths | `pw defaults --project demo` | Read-only |
| Inspect blockers | `pw status --project demo` | No task execution |
| Request one planning decision | `pw plan --project demo` | May invoke provider and append queue tasks |
| Plan if needed, run at most one task | `pw tick --project demo --no-telegram` | Can run provider and mutate Git, queue and state |
| Directly run at most one task | `pw worker --project demo --once --no-telegram` | Can mutate worktree and state |
| Preview worker selection | `pw worker --project demo --dry-run` | Preflight/preview only |
| Inspect worker journal | `pw worker --project demo --journal-status` | Read-only |
| Check quota | `pw worker --project demo --quota-check` | May query configured HA sensor |
| Preview approval sends | `pw notify` | Does not send |
| Send pending approval | `pw notify --send` | **Network message and delivery marker** |
| Per-project timer | `pw timer status demo` | Calls user systemd manager |

`pw init` and `pw defaults` are also primary subcommands. **`pw setup` is the new first-run command:** it requires installed/configured Hermes and a successful read-only `hermes plugins list --plain --no-bundled` check, detects existing Hermes Telegram credentials and numeric authorized users, then explains and requests confirmation before enabling the approval plugin and user notifier. `pw setup --no-telegram` skips optional Telegram integration; `--yes` explicitly opts into activation without a prompt. `pw setup-user` and `pw-timer setup-user` remain older direct onboarding commands. Consult each command's `--help` before applying flags, especially while the CLI is evolving. Exit codes and manager JSON decisions are documented in [baseline-validation.md](baseline-validation.md).

## 7. Exact orchestration workflow

```text
requirements.md -> planner proposal -> validated queue.md
                                           |
manual pw tick / user timer -> dispatcher -> manager policy/locks/queue/Git checks
                                           |
                         blocked / idle / awaiting approval  OR  authorized worker
                                                                    |
                                 READ / EDIT -> TEST -> COMMIT / VERIFY / DECIDE
                                                                    |
                               result envelope + journal + Git evidence checked
                                                                    |
                                  queue/progress update OR recovery hold
                                                                    |
                     completed milestone -> pinned Telegram request (optional)
                                                                    |
                     Reject -> review hold; Approve -> acceptance command/receipt
                                                                    |
                               next manager tick may plan the next milestone
```

**Dispatch:** `pw_dispatch.py` runs a canonical manager subprocess, validates a single JSON response and its exit code, then starts one worker subprocess only on an allowed decision. An active Git cycle has its own narrow continuation gate for TEST/COMMIT, not a bypass of policy.

**Manager:** `pw_queue_manager.py` takes the project lock, parses queue, checks project/config identity, unresolved journal and recovery, Git branch/worktree, milestone ordering and acceptance, requirements/planning policy and optional quota. It emits `queued`, `no_op`, `disabled`, `busy`, `blocked`, `awaiting_acceptance`, `quota_blocked`, or `planner_failed`. Unknown or inconsistent manager output is refused.

**Planner:** `pw_queue_planner.py` makes a bounded provider call for structured proposal JSON, validates it and rechecks concurrent state before atomically appending work. Planner failure does not authorize executing guessed tasks.

**Worker:** `pw_task_worker.py` locks the project, checks selected task identity and phase, persists journal evidence, invokes the provider, then verifies the exact completion report and resulting files/Git scope before completing a checkbox. READ is non-mutating by contract. EDIT/TEST/COMMIT track an allowed-path Git snapshot and cycle journal; an unexpected path or unauthorized commit blocks continuation. A dangerous commit may already exist in Git: Projectwright deliberately does not silently rewrite history.

**Recovery:** Timeouts, invalid/missing reports, wrong task IDs, interrupted journals, queue tampering and stale cycle evidence leave work pending/for review. `pw_recovery.py` records incidents without resetting Git. Inspect the journal, Git diff, queue and incidents before any explicit retry authorization (`pw worker --project demo --authorize-retry TASK_ID`).

**Milestone acceptance:** A completed milestone is not accepted merely because tasks are checked. The guard validates pinned requirement/queue/Git evidence, path scope and an explicit acceptance-command argv, then records a receipt only on successful validation. An old HEAD, changed queue/policy, failed command, replayed token or revoked user cannot create a valid approval receipt.

**Telegram:** `pw_notify.py` scans and sends the inline button; `pw_plugin.py` installs handler hooks in the Hermes gateway; `pw_buttons.py` routes the callback to `pw_telegram_approval.py` and `pw_milestone_guard.py`. Approval consumes the pending request after a verified receipt; Reject records rejection and preserves pending evidence for review. The live Approve path was verified in a disposable LXD project on 2026-10-25; that does not prove all reject/authorization edge cases live.

## 8. Provider, quota, notes, approval

- **Hermes (default):** Projectwright invokes the locally configured Hermes CLI for planning and worker tasks. Hermes controls its model/provider configuration. Worker progress messages may use separate `hermes send`; `--no-telegram` suppresses those, not milestone approval policy.
- **Command adapter (experimental):** JSON `provider.type=command` with absolute `planner_argv` and `worker_argv`. Processes read prompts on stdin. Planner emits one valid JSON proposal on stdout; worker writes the exact structured result file requested in the prompt. No shell interpolation is used. See [provider-adapters.md](provider-adapters.md).
- **Home Assistant quota:** Optional read-only sensor check. A configured, required-but-unavailable quota fails closed rather than inventing capacity.
- **Notes:** Optional publisher and mirror synchronizer. Mirror conflicts are intentional blockers, not permission to overwrite independent notes.
- **Approvals:** Require explicit acceptance policy. A user-level approval scan timer and Hermes callback plugin are separate components. See [approval setup](user-approval-setup.md).

## 9. Timers and human account setup

Per-project `pw timer check|install-disabled|enable|disable|status PROJECT` generates/manages user services for dispatch; installation is disabled by default. The separate approval notification timer uses:

```sh
pw setup
```

Run that **as the intended unprivileged user**, after reviewing `~/.hermes/.env` (bot token and valid allowed-user IDs), plugin state and any existing unit files. It refuses root, symlinked or modified unit targets and does not silently overwrite an existing plugin. The action may enable a timer and plugin; it is not a read-only preview. The timer sends actual approval notifications. Stop it with:

```sh
systemctl --user disable --now projectwright-approval-notify.timer
```

A Hermes gateway may need an explicit reload/restart for new callback registration. Never share the same bot token between simultaneously polling test and production gateways. Never point callback project-root variables at production when running disposable tests.

## 10. Troubleshooting and release boundaries

| Symptom | Inspect first | Safe response |
|---|---|---|
| `disabled` | selected root, missing config, prepared worktree/queue and enablement | Correct the target/config deliberately |
| `busy` | project lock and running worker | Defer; do not remove a live lock |
| `blocked` | Git branch/dirty paths, queue syntax, journal, incidents | Preserve evidence and investigate |
| `awaiting_acceptance` | milestone receipt, pending/rejected request, acceptance policy | Seek reviewed approval; never forge a receipt |
| `quota_blocked` | quota config, HA connectivity/value | Restore legitimate telemetry or approved policy |
| `planner_failed` | provider command/exit, proposal JSON, timeout | Fix provider; don't append tasks by guess |
| Telegram request absent | dry-run, token, single outbound recipient, plugin/gateway, scoped root | Validate in isolation; don't casually send to real users |
| Callback ignored | private chat, authorized numeric user, pending ID, gateway handler | Inspect sanitized logs, never print token |
| Crash or failed task | `--journal-status`, incidents, results, Git diff | Human-reviewed recovery; do not erase journals |

For verified test evidence and remaining Debian release gates see [release-checklist.md](release-checklist.md); for tests see [test-coverage-matrix.md](test-coverage-matrix.md) and [e2e-test-gaps.md](e2e-test-gaps.md). The historical original-file audit pages remain useful but should not override current canonical names or later test evidence.
