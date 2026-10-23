# Offline test coverage matrix

This matrix describes the checked-out `src/projectwright/` tests. All fixtures are temporary; service boundaries are mocked. It is not evidence of live Hermes, Telegram, Home Assistant, systemd, or installed-script behavior.

| Area | Maintained tests | Contract exercised | Boundary / gap |
|---|---|---|---|
| Baseline and source drift | `tests/unit/test_baseline_validator.py::BaselineValidatorTests` | Loads JSON manifest records; checks the exact source file set, hashes, and byte counts; malformed manifest digests fail validation; development drift is reported without rewriting the manifest. | Synthetic source tree and manifest. The original manifest remains pinned to the audited 18-module snapshot. |
| Quota and progress | `tests/unit/test_quota_progress.py::QuotaPolicyTests`, `WorkerProgressTests` | Disabled quota avoids HTTP; unavailable sensor fails closed; progress completion is idempotent. The optional rate-limit entity mismatch is retained as an expected failure. | Mocked HTTP and temporary state. No live HA request. |
| Milestone sequencing | `tests/unit/test_milestone_sequence.py::MilestoneSequenceTests` | Duplicate headings, active/current work, completed commit awaiting acceptance, future-milestone blocking, missing-policy blocking. | Pure selector fixtures; not an end-to-end Git/acceptance run. |
| Dispatch, manager/planner, timer and Git cycles | `tests/integration/test_dispatch_contracts.py` (`TestTick`, `DispatcherHardening`, `NoOpContract`, `BusyContract`, `TimerTests`, `CycleTests`) | Worker routing, no-op pending count, refusal/defer decisions, busy-lock contract, task summary safety, generated unit text, and authorized versus stale/malformed Git-cycle state. | Fake runner, temporary Git/project trees, generated text only; no systemd operation or Hermes invocation. |
| Recovery and worker journal | `tests/recovery/test_recovery_contracts.py::RecoveryContracts` | Missing/interrupted/corrupt journal outcomes, no automatic mutation, active-cycle/untracked-change review, incident idempotency, lock-aware CLI, journal inspection, timer generation. | Temporary repository and files; no live recovery or unit activation. |
| Acceptance receipts and Telegram approval | `tests/acceptance/test_acceptance_and_telegram.py::ReceiptChainTests`, `TelegramApprovalAndButtonTests` | Receipt continuity/scope, pinned button payloads, stale/replayed callbacks, approve/reject state, notification deduplication and retry after transport failure, recipient-contract mismatch. | Fake projects/Git and injected transport; no Telegram API or plugin runtime. |
| Worker delivery persistence | `tests/integration/test_worker_delivery_contract.py::WorkerDeliveryPersistenceTests` | A completed task remains checked and recorded in progress/journal when notification delivery returns failure. | Disposable Git/project fixture and mocked Hermes/delivery; no live worker. |

## Recorded validation

Run date: 2026-10-23.

- `python3 -B -m unittest discover -s tests -p 'test_*.py' -v`: 75 tests; 74 PASS, 0 FAIL, 0 SKIP, 1 XFAIL; process exit 0 (`OK (expected failures=1)`).
- `python3 -B scripts/validate-baseline.py --mode baseline`: exit 0; suite totals PASS=74, FAIL=0, SKIP=0, XFAIL=1, TOTAL=75; `UNITTEST: PASS`, live integration checks excluded, `OVERALL: PASS`.
- `python3 -B scripts/validate-baseline.py --mode development`: same totals and `OVERALL: PASS`.
- `git diff --check`: exit 0.

The XFAIL is `QuotaPolicyTests.test_optional_rate_limit_entity_uses_audit_documented_entity_name`. It records the known difference between the source's optional entity default and the entity observed in the audit; it does not change source behavior. Expected fail-closed diagnostic messages printed by negative-path tests do not count as test failures.

## Explicitly not covered

Ordinary discovery does not validate real Telegram delivery/callback authorization, live HA entities or credentials, Hermes provider execution, user systemd scheduling, live project queues/journals, or the user's external fixtures. No CI workflow, packaging metadata, or live integration runner is added. Historical test artifacts and outcomes are inventoried separately in `docs/test-source-inventory.md`; historical claims are not current results.
