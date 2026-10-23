# End-to-end test coverage and gaps

Source baseline: `7fe441c9cf46ea3c67ce6cd03fa82eaa4f6124fd`. The original audit was read-only: no fixture was modified and no Projectwright worker was launched then. Host and external-fixture observations below are a snapshot from 2026-10-23, not current-state guarantees; recheck before relying on them. The current branch adds an isolated `unittest` suite; it still does not run live Hermes, Telegram, Home Assistant, or systemd integration.

## Existing evidence

- At the original source baseline, the repository had 18 Python scripts and no `tests/` directory, runner, CI workflow, or dependency manifest. The offline `tests/` suite and `scripts/validate-baseline.py` were introduced on `test/reproducible-baseline` and are present in this checkout; CI and dependency metadata remain absent.
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

Covered offline contracts include source-manifest validation, strict manager/dispatcher parsing and exit-code consistency, queue/dispatch decisions, quota and progress handling, milestone sequence and receipt-chain behavior, Telegram authorization/notifier state with mocked transport, recovery/journal checks, and durable task completion when notification delivery fails. The quota XFAIL has been replaced by passing configuration/default/null regression coverage. Coverage is not proof that live Hermes, Telegram, HA, systemd, or the user's fixtures work end to end.

## Prioritized residual gaps before refactoring

### P0 — establish the safety contract

1. **Dispatcher → manager → worker end-to-end.** Focused offline tests now reject malformed/ambiguous manager stdout and inconsistent exit codes before worker routing, and preserve valid `busy`/`no_op` behavior. Still run the full chain against a disposable project with fake Hermes: manager schema across every real decision, lock contention, one-task execution, and post-worker re-entry. Assert stdout/stderr remain machine-readable and no real Hermes provider is called.
2. **Human acceptance: allow and deny callbacks.** Exercise notifier scan, message/callback payload creation, plugin handler, approval/rejection, receipt creation/removal, and next-run gate behavior. Cover wrong project, duplicate callback, malformed request ID, missing bot configuration, and a declined request. Assert no receipt exists after rejection.
3. **Stale approval and tamper cases.** Change HEAD, queue task list, requirements, policy, or allowed scope after a request is pinned; verify every stale request is refused without writing a valid receipt.
4. **Current queue/config safety.** Test missing queue/requirements/config ID mismatch, disabled planning, invalid milestone policy, and unavailable required HA quota entity. The inspected `projectwright` config currently references a nonexistent `queue.md`; verify the dispatcher returns a clear fail-closed result rather than an unstructured traceback.
5. **Git-cycle authorization and data preservation.** Offline tests cover stale/wrong HEAD, branch/phase, previous task/kind, active journal, untracked changes, and a permitted TEST→COMMIT continuation in disposable repositories. Still cover the full EDIT→COMMIT path with allowed-path enforcement, dirty pre-existing worktree stash/restore, missing/invalid COMMIT, acceptance-command failure, and recovery after each interruption point. Never target real repos.

### P1 — recovery and state integrity

6. **Worker journal crash matrix.** Offline tests cover interrupted edit/commit review-only behavior, missing/corrupt journals, active Git-cycle review, and idempotent incident recording. Still inject process interruption at every persisted phase and cover concurrent worker, lock timeout, and manual clear/review paths. Ambiguous evidence must remain review-only, never auto-reconciled.
7. **Atomic state writes.** Recovery-incident replacement now has a regression test that forces `os.replace` to fail and verifies the last valid file remains byte-for-byte intact with temporary-file cleanup. Still inject interruption/disk failures across queue, planning, journal, progress, approval, and note-manifest replacement, and verify locks release.
8. **Planner response and concurrency.** Offline unit tests cover strict milestone ordering, acceptance-receipt scope invalidation, and fail-closed quota behavior; the held-lock test confirms planner contention returns `busy`. Still test planner/worker races, concurrent queue edits, duplicate proposals, planner timeout/nonzero exit, malformed task schemas, and receipt/quota changes across a complete dispatcher→planner run.
9. **Worker outcome/notification.** An offline integration test verifies a task result remains persisted when notification delivery fails. Still cover explicit blockers, malformed task JSON, command timeout, signal termination, detached execution, progress updates, and ambiguous retries without duplicating or losing task state.

### P2 — integration and maintenance

10. **Notes integrations.** Test status/init/publish, unchanged mirrors, local edits on either side, multiple mirrors, preflight failure before any write, and retry/idempotence. Ensure notes failures do not cause duplicate task execution.
11. **Notifier behavior.** Offline tests cover parsed multi-recipient allow-lists, callback/private-chat authorization, per-recipient deduplication, retry after partial fake-transport failure, and the duplicate window when a send is accepted but marker persistence fails. Delivery is at-least-once across that window, not exactly-once. Still test zero/one/many projects, repeat scans, expired/stale approvals, Telegram HTTP failure/rate limit, missing/invalid token configuration, and credential redaction. Never call live Telegram during default discovery.
12. **Timer utility without host mutation.** A regression test installs disabled unit files in a temporary HOME with a fake `systemctl` that records only `daemon-reload`; text generation and validation are also checked. Still cover overwrite refusal and check/enable/disable/status actions against fake executables only. Never invoke the host `systemctl` from tests.
13. **Standalone environment matrix.** Run import/CLI smoke tests with Hermes absent, HA unreachable, Telegram library absent, and a non-default project config/scripts root. These should prove the core queue engine can be isolated from optional integrations.
14. **Repeatability and release checks.** Add a deterministic test command, fixture setup/teardown in temporary worktrees, CI, supported Python/dependency declarations, and a test proving installed manifest parity. Keep external fixture directories read-only.

## Test design constraints

Use disposable temporary directories and fake executables/HTTP servers; never point destructive Git-cycle tests at the production repository, Vancouver, or the real fixture worktrees. Mock the Hermes, HA, Telegram and systemd boundaries. Tests should assert filesystem state, Git HEAD/status, receipt fingerprints, exit code, JSON stdout, and exact subprocess calls—not just user-facing summary text.
