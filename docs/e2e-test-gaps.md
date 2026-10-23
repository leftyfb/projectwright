# End-to-end test coverage and gaps

Baseline: `7fe441c9cf46ea3c67ce6cd03fa82eaa4f6124fd`. This is a coverage inventory only. No fixture was modified and no Projectwright worker was launched during the audit.

## Existing evidence

- The repository has 18 Python scripts but no `tests/` directory, test runner, CI workflow, or dependency manifest in the inspected tree.
- External fixture projects exist under `~/.hermes/projects/`: `pw-sequence-test`, `pw-e2e-allow`, and `pw-e2e-deny`. Their queues were fully checked at inspection: 12, 4, and 3 checked task rows respectively. The allow fixture has historical completed result records for P101–P104; the deny fixture has completed result records for P101–P103. Those records do not by themselves establish that Telegram callback, stale-approval, or denial behavior was executed end to end.
- The `pw-sequence-test` systemd worker timer is disabled, and there is no active worker cron job identified. The enabled approval-notification timer is not a worker test harness.
- A read-only AST inventory parsed all 18 source files without a syntax-parse error. This is not behavioral test coverage. No automated test suite was run because none is present in the repository.

## Prioritized gaps before refactoring

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
