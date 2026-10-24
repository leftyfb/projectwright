# Offline test coverage matrix

This matrix describes the checked-out `src/projectwright/` tests. All fixtures are temporary; service boundaries are mocked. It is not evidence of live Hermes, Telegram, Home Assistant, systemd, or installed-script behavior.

| Area | Maintained tests | Contract exercised | Boundary / gap |
|---|---|---|---|
| Baseline and source drift | `tests/unit/test_baseline_validator.py::BaselineValidatorTests` | Loads JSON manifest records; checks the exact source file set, hashes, and byte counts; malformed manifest digests fail validation; development drift is reported without rewriting the manifest. | Synthetic source tree and manifest. The original manifest remains pinned to the audited 18-module snapshot. |
| Real approval guard and callback | `tests/test_guard_pinned_evidence.py`, `tests/test_telegram_callback_replay.py` | Disposable Git repo acceptance execution, scope-bounded receipt, callback-to-guard handoff, stale/rejected policy, callback replay refusal, failed acceptance command, and concurrent queue mutation refusal. | Real Git and Python acceptance subprocess, but no Telegram network, production Hermes configuration, or live project. |
| Callback user authorization and send revocation | `tests/test_pw_plugin_authorization.py`, `tests/test_pw_notify_revocation.py` | Dynamic `.env` allowlist reload/revocation, private-only callbacks, refusal of invalid users, successful callback routing, revoke-during-send stopping subsequent recipients and preventing stale markers. | Fake Telegram SDK/transport and temporary HOME; no network calls. |
| Timer status CLI | `tests/test_timer_status_exit.py` | Propagates status exit code from mocked systemctl without enabling or disabling services. | No real systemd interaction. |
| Quota and progress | `tests/unit/test_quota_progress.py::QuotaPolicyTests`, `WorkerProgressTests` | Disabled quota avoids HTTP; required and explicitly configured optional sensor failures fail closed; project setting/env default precedence; explicit `null` disables only the optional gate; progress completion is idempotent. | Mocked HTTP and temporary state. No live HA request. |
| Milestone sequencing | `tests/unit/test_milestone_sequence.py::MilestoneSequenceTests` | Duplicate headings, active/current work, completed commit awaiting acceptance, future-milestone blocking, missing-policy blocking. | Pure selector fixtures; not an end-to-end Git/acceptance run. |
| Dispatch, manager/planner, timer and Git cycles | `tests/integration/test_dispatch_contracts.py` (`TestTick`, `DispatcherHardening`, `NoOpContract`, `BusyContract`, `TimerTests`, `CycleTests`); `tests/recovery/test_recovery_contracts.py::RecoveryContracts` | Strict single-object JSON parsing (duplicate keys/non-standard constants/extra stdout rejected); per-decision response fields and required values; project and exit-code match; task-ID/status validation; tactical and strategic queued modes; status-only `ready_for_planner` rejection on the `--once` path; a real `plan_once()` queued report round-trips through dispatcher parsing; no-op/busy semantics, worker routing, task-summary safety, generated unit text, fake-`systemctl` disabled installation, and authorized versus stale/malformed Git-cycle state. | Fake runner/systemctl, temporary Git/project trees; no real systemd operation or Hermes invocation. |
| Recovery and worker journal | `tests/recovery/test_recovery_contracts.py::RecoveryContracts` | Missing/interrupted/corrupt journal outcomes, no automatic mutation, active-cycle/untracked-change review, incident idempotency, atomic replacement failure preserves the last valid file and cleans temporary files, lock-aware CLI, journal inspection, timer generation. | Temporary repository/files and injected `os.replace` failure; no live recovery or unit activation. |
| Acceptance receipts and Telegram approval | `tests/acceptance/test_acceptance_and_telegram.py::ReceiptChainTests`, `TelegramApprovalAndButtonTests` | Receipt continuity/scope, pinned button payloads, stale/replayed callbacks, approve/reject state, shared strict multi-recipient authorization, recipient-specific deduplication and retry after partial transport failure; marker-write failure after an accepted send is covered as an at-least-once duplicate window. | Fake projects/Git and injected transport; no Telegram API or plugin runtime. |
| Worker delivery persistence | `tests/integration/test_worker_delivery_contract.py::WorkerDeliveryPersistenceTests` | A completed task remains checked and recorded in progress/journal when notification delivery returns failure. | Disposable Git/project fixture and mocked Hermes/delivery; no live worker. |

## Recorded validation

Run date: 2026-10-23.

- Starting baseline: 75 tests; 74 PASS, 0 FAIL, 0 SKIP, 1 XFAIL; unittest exit 0.
- Initial development validator: exit 0; PASS=74, FAIL=0, SKIP=0, XFAIL=1, TOTAL=75; `UNITTEST: PASS`, live integration checks excluded, `OVERALL: PASS`.
- Post-fix ordinary discovery before the strict-contract follow-up: 86 tests; 86 PASS, 0 FAIL, 0 SKIP, 0 XFAIL; unittest exit 0.
- Strict-contract follow-up development validation: 88 tests; 88 PASS, 0 FAIL, 0 SKIP, 0 XFAIL; source-file-set, syntax, imports, and offline tests passed; manifest remains unchanged.
- Post-review marker-write failure regression: 89 tests; 89 PASS, 0 FAIL, 0 SKIP, 0 XFAIL; development validator exit 0; source drift was reported in development mode, manifest remained unchanged.
- Planner/manager/dispatcher branch-matrix follow-up: 91 tests; 91 PASS, 0 FAIL, 0 SKIP, 0 XFAIL; development validator exit 0; tactical/strategic queued modes and status-only decision refusal are covered.
- The source manifest was not regenerated.
- `git diff --check`: exit 0.

The original XFAIL was the optional quota-entity default mismatch and has been replaced with passing configuration/default/null regression coverage. The supplemental temporary focused verification (31 tests passed) is recorded in `docs/baseline-validation.md`; it is not a substitute for full discovery. Expected fail-closed diagnostic messages printed by negative-path tests do not count as test failures.

## Explicitly not covered

Ordinary discovery does not validate real Telegram delivery/callback authorization, live HA entities or credentials, Hermes provider execution, user systemd scheduling, live project queues/journals, or the user's external fixtures. No CI workflow, packaging metadata, or live integration runner is added. Historical test artifacts and outcomes are inventoried separately in `docs/test-source-inventory.md`; historical claims are not current results.
