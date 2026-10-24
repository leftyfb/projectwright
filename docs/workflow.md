# Projectwright workflow: from requirements to accepted milestones

This document describes the current **development** implementation. It covers
existing functional boundaries without implying that Hermes integrations and
filenames have already been fully replaced.

## 1. Define the project

A project has an identifier, Git worktree/branch, queue, requirements file,
optional acceptance policy and optional planning/agent provider settings.
Existing projects use a JSON configuration under the selected project root.
See [configuration-home.md](configuration-home.md) for XDG paths, overrides
and the backwards-compatible Hermes-project fallback.

A missing `config.json` is recognized as `disabled` by the manager. Nothing
is automatically executed or initialized in that case; config-free execution
remains incomplete. The worker always validates the configuration and may
not infer a Git repository or executable from an absent setting.

## 2. Inspect, plan and dispatch

`pw status --project NAME` asks the queue manager to inspect the current
state without planning. The manager checks queue syntax, project lock, worker
journal, pending recovery incidents, Git branch and cleanliness, current
acceptance receipts, requirements and optional quota gates. Its response has
a documented JSON/exit-code contract (see `baseline-validation.md`).

`pw tick --project NAME` runs the dispatcher, which starts one manager
subprocess. If safe planning is due, the manager invokes the planner, which
proposes bounded tasks and validates the proposal before updating the queue.
The dispatcher accepts only the documented response shape, then runs at
most one worker task when authorized. An active EDIT/TEST/COMMIT cycle has
additional evidence and scope checks; it is not a general bypass for a
blocked manager result.

## 3. Execute one task

The worker reads the selected task from the queue and validates all required
preconditions. Tasks include READ, EDIT, TEST, COMMIT, VERIFY and DECIDE.
The agent prompt includes the task and a unique result file path. The worker
expects a structured report with the correct task identity and outcome; a
message on stdout alone is not sufficient to mark work complete.

Hermes remains the default runner. An explicit `provider.type=command`
can instead execute a configured absolute-path argv list, delivering the
prompt on stdin. The planner expects proposal JSON on stdout; the worker
expects a report written to its specified file. See
[provider-adapters.md](provider-adapters.md). This is an experimental adapter,
not yet an SDK-stable backend API.

## 4. Persist completion and recover

Worker journal state, task progress, Git HEAD and worktree scope are checked
before queue completion. A failed, timed-out or malformed agent response does
not advance the task. An unresolved journal blocks an automatic retry until
review. Recovery helpers create durable incidents but do not quietly reset
Git or approve work.

EDIT/TEST/COMMIT form an authorized cycle. An unexpected worktree path or
stale cycle snapshot prevents continuation. A COMMIT that includes an
unapproved file is rejected even if Git itself succeeded; that commit is
not automatically undone. A successful cycle verifies the scoped commit,
updates the task queue, and removes the cycle journal.

## 5. Milestone verification and human acceptance

Completed task checkboxes do not constitute milestone acceptance. A current
milestone receipt requires an explicitly configured acceptance command,
pinned requirement/queue/HEAD evidence, validated path scope and a clean
Git worktree under the project lock. A failing command, stale evidence,
rejected request or concurrent state change prevents a receipt.

For Telegram approvals, the notifier scans pending requests and posts
inline **Approve** and **Reject** buttons to authorized recipients. Callback
data identifies the project and pinned evidence. The Hermes gateway plugin
restricts callbacks to allow-listed users in private chats, rereads the
allow-list on every callback and refuses revoked, stale or replayed requests.
Approval invokes the acceptance guard; rejection is durable and requires
manual review. See [user-approval-setup.md](user-approval-setup.md).

The current notification transport for worker progress can still use
`hermes send`. With an alternate command provider, use explicit
`pw tick --no-telegram` until provider-independent progress delivery exists.
The Telegram approval channel is a distinct function; suppressing worker
progress does not replace or satisfy milestone approval.

## 6. Scheduling and installation

The timer utility can install disabled-by-default per-project systemd user
units. `pw setup-user` performs explicit non-root setup for the separate
approval notification timer, only after validating Telegram configuration.
The Debian preview does **not** silently choose an operating-system user
from its root-run installation script. Package-triggered per-user onboarding,
plugin provisioning, release upgrades and uninstall lifecycle are pending
requirements, tracked in [release-checklist.md](release-checklist.md).

## 7. Files and tests

The 18 current Python source files and their purposes, callers, and external
effects are enumerated in [component-inventory.md](component-inventory.md).
The [test coverage matrix](test-coverage-matrix.md) identifies maintained
tests by subsystem; [end-to-end gaps](e2e-test-gaps.md) distinguishes source
tests on `tux` from live model, Telegram and systemd operations. CI builds
both a development wheel and a Debian preview without installing either into
the existing Hermes environment.
