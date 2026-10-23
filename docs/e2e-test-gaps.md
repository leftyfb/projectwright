# End-to-end test coverage and gaps

Source baseline: `7fe441c9cf46ea3c67ce6cd03fa82eaa4f6124fd`. The original audit was read-only: no fixture was modified and no Projectwright worker was launched then. The current branch adds an isolated `unittest` suite; it still does not run live Hermes, Telegram, Home Assistant, or systemd integration.

## Existing evidence

- At the original source baseline, the repository had 18 Python scripts and no `tests/` directory, runner, CI workflow, or dependency manifest. The `test/reproducible-baseline` branch now contains an offline `tests/` suite and `scripts/validate-baseline.py`; CI and dependency metadata remain absent.
- External fixture projects exist under `~/.hermes/projects/`: `pw-sequence-test`, `pw-e2e-allow`, and `pw-e2e-deny`. Their queues were fully checked at inspection: 12, 4, and 3 checked task rows respectively. The allow fixture has historical completed result records for P101–P104; the deny fixture has completed result records for P101–P103. Those records do not by themselves establish that Telegram callback, stale-approval, or denial behavior was executed end to end.
- The `pw-sequence-test` systemd worker timer is disabled, and there is no active worker cron job identified. The enabled approval-notification timer is not a worker test harness.
- The original read-only AST inventory parsed all 18 source files. It was not behavioral coverage. Current syntax/import and offline-suite results are recorded in `docs/test-coverage-matrix.md`; historical claims remain separate in `docs/test-source-inventory.md`.

## Current checked-out tests

The repository's `tests/unit`, `tests/integration`, `tests/recovery`, and
`tests/acceptance` modules use standard-library `unittest`. Ordinary discovery
is offline and does not contact live services, change host units, or use the
external Projectwright fixtures. The worker-delivery integration contract uses
a disposable Git repository and temporary project files. Run the suite and
baseline checks using the commands in `README.md` and `docs/baseline-validation.md`.

Covered offline contracts include source-manifest validation, queue/dispatch
decisions, quota and progress handling, milestone sequence and receipt-chain
behavior, Telegram button/approval/notifier state with mocked transport,
recovery/journal checks, and durable task completion when notification delivery
fails. The optional quota entity default remains an expected failure; see the
coverage matrix and technical-debt record. Coverage is not proof that live
Hermes, Telegram, HA, systemd, or the user's fixtures work end to end.

## Prioritized residual gaps before refactoring

### P0 — establish the safety contract

1. **Dispatcher → manager → worker end-to-end.** Use a disposable temporary project root and fake Hermes executable. Verify manager JSON/exit-code combinations, allow/hold/refuse decisions, lock contention, worker not started on a held/invalid decision, one-task execution, and post-worker re-entry. Assert stdout/stderr remain machine-readable and no real Hermes provider is called.
2. **Human acceptance: allow and deny callbacks.** Exercise notifier scan, message/callback payload creation, plugin handler, approval/rejection, receipt creation/removal, and next-run gate behavior. Cover wrong project, duplicate callback, malformed request ID, missing bot configuration, and a declined request. Assert no receipt exists after rejection.
3. **Stale approval and tamper cases.** Change HEAD, queue task list, requirements, policy, or allowed scope after a request is pinned; verify every stale request is refused without writing a valid receipt.
4. **Current queue/config safety.** Test missing queue/requirements/config ID mismatch, disabled planning, invalid milestone policy, and unavailable required HA quota entity. The inspected `projectwright` config currently references a nonexistent `queue.md`; verify the dispatcher returns a clear fail-closed result rather than an unstructured traceback.
5. **Git-cycle authorization and data preservation.** Verify EDIT→COMMIT sequencing, allowed-path enforcement, dirty pre-existing worktree stash/restore, untracked-file behavior, missing/invalid COMMIT, acceptance command failure, interrupted cycles, and preservation of user changes. Run only in disposable repos.

### P1 — recovery and state integrity

6. **Worker journal crash matrix.** Interrupt at every persisted phase; restart; verify `project_recovery.py` records deduplicated incidents and refuses automatic reconciliation where evidence is ambiguous. Cover malformed/partial journal, concurrent worker, lock timeout, and manual clear/review paths.
7. **Atomic state writes.** Inject process interruption and disk/write failures during queue, planning, journal, progress, recovery, approval and note-manifest replacement. Assert the previous complete file remains readable and locks are released.
8. **Planner response and concurrency.** Test timeout, nonzero Hermes exit, malformed/extra JSON, invalid task schema/IDs/kinds, concurrent queue edits, duplicate proposals, blocked prerequisites, strict sequencing, receipt fingerprint changes, and quota below threshold/unknown/offline.
9. **Worker outcome/notification.** Cover successful result, explicit blocker, malformed task JSON, command timeout, task failure, signal termination, detached execution, progress update, and Hermes notification failure without duplicating or losing task state.

### P2 — integration and maintenance

10. **Notes integrations.** Test status/init/publish, unchanged mirrors, local edits on either side, multiple mirrors, preflight failure before any write, and retry/idempotence. Ensure notes failures do not cause duplicate task execution.
11. **Notifier behavior.** Test zero/one/many projects, repeat scans, notification deduplication, expired/stale approvals, Telegram HTTP failure/rate limit, missing/invalid token/chat configuration, and redaction of credentials from logs/errors.
12. **Timer utility without host mutation.** Unit-test generated service/timer text and validation in temporary directories; test refusal to overwrite and every action using a fake `systemctl`. Do not enable or alter real user units in tests.
13. **Standalone environment matrix.** Run import/CLI smoke tests with Hermes absent, HA unreachable, Telegram library absent, and a non-default project config/scripts root. These should prove the core queue engine can be isolated from optional integrations.
14. **Repeatability and release checks.** Add a deterministic test command, fixture setup/teardown in temporary worktrees, CI, supported Python/dependency declarations, and a test proving installed manifest parity. Keep external fixture directories read-only.

## Test design constraints

Use disposable temporary directories and fake executables/HTTP servers; never point destructive Git-cycle tests at the production repository, Vancouver, or the real fixture worktrees. Mock the Hermes, HA, Telegram and systemd boundaries. Tests should assert filesystem state, Git HEAD/status, receipt fingerprints, exit code, JSON stdout, and exact subprocess calls—not just user-facing summary text.
