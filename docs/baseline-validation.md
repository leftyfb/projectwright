# Baseline and development validation

## Scope

The source baseline is commit `7fe441c9cf46ea3c67ce6cd03fa82eaa4f6124fd`.
`installed-source-manifest.json` records SHA-256 digests and byte counts for the
18 expected Python modules in `src/projectwright/`. Validation checks both
values against checked-out files. The manifest is read-only to the validator;
it is not regenerated automatically when source changes.

## Commands

Run from the repository root with Python 3:

```sh
python3 -B scripts/validate-baseline.py --mode baseline
python3 -B scripts/validate-baseline.py --mode development
```

The mode is required. Both modes:

- verify the exact expected module set, manifest record shape, hashes, and byte
  counts;
- parse every checked-out module with `ast.parse`;
- attempt imports from the checked-out source directory, reporting missing
  dependencies and import-time errors;
- run `unittest discover -s tests -p 'test_*.py' -v` in a child process;
- print PASS/FAIL/SKIP/XFAIL/TOTAL counts and a final `OVERALL` result.

The validator does not rewrite the manifest, install packages, touch installed
Hermes scripts, call live APIs, or operate systemd units. An import can execute
module-level initialization, so source imports should remain side-effect-free;
run the validator only against this checked-out test tree.

## `project_queue_manager.py --once` output contract

The command writes exactly one UTF-8 JSON object to stdout. It must not emit
progress or diagnostics there; errors/diagnostics belong on stderr. The object
must contain the requested `project` ID and a recognized `decision`.
The `pw_dispatch.py` consumer rejects duplicate JSON keys, non-standard JSON
constants, empty/non-JSON output, extra stdout lines, fields not allowed for the
decision, missing required fields, wrong field types, project mismatch, or an
exit code that disagrees with the decision; refusal must not launch a worker.

| Decision | Exit | Required response fields / dispatcher behavior |
|---|---:|---|
| `queued` | 0 | Nonnegative `pending`; positive `added`; unique uppercase task IDs matching `[A-Z]+[0-9]+` with length equal to `added`; `planning_mode` is `tactical` or `strategic`; `notes_sync` is `not_configured`, `ok`, or `failed: ...`; dispatch worker. |
| `busy` | 2 | Exact recognized reason `Project lock held; skip planning`; defer without worker. |
| `blocked` | 2 | String reason; refuse without worker except the separately validated active Git-cycle continuation when reason is exactly `branch_or_worktree, active_git_cycle`. |
| `no_op` | 3 | Nonnegative `pending`; zero means safe idle, positive means process existing queued work. |
| `disabled` | 3 | No decision-specific fields; safe idle. |
| `awaiting_acceptance` | 3 | Nonnegative `pending`, string reason, and exactly one `milestone` or `milestones` field; safe idle. |
| `quota_blocked` | 4 | Nonnegative `pending` and valid quota object with boolean `allowed: false`; refuse without worker. |
| `planner_failed` | 4 | Nonnegative `pending` and string `reason`; refuse without worker. |
| execution exception | 1 | JSON may be absent; diagnostic on stderr; dispatcher refuses. |

Unknown decisions map to 4 at the manager boundary but remain invalid to the
dispatcher. The contract is enforced independently in the manager and consumer;
`tests/integration/test_dispatch_contracts.py` checks mapping consistency and
malformed-output refusals. The authorized active Git-cycle continuation remains
a separate validated route and does not authorize a worker from malformed
manager output.

## Quota and Telegram configuration contracts

The required remaining quota sensor remains fail-closed. The optional
`rate_limited_entity` uses a project-level value when present; if omitted, it
uses `PROJECTWRIGHT_RATE_LIMITED_ENTITY` when set. If neither is configured, the
optional gate is skipped, avoiding a hard-coded Home Assistant entity. Explicit
JSON `null` disables that optional check even if the environment default is set.
A malformed configured value or an unavailable explicitly configured sensor
fails closed.

`TELEGRAM_ALLOWED_USERS` is a comma-separated list of unique positive decimal
IDs; surrounding whitespace is accepted, but empty entries, duplicates, zero,
signs, and non-decimal values are rejected. Callback authorization also
requires the expected private chat. Outbound approval delivery targets only
those parsed IDs, persists per-recipient success markers, and skips recipients
whose success marker was written. Telegram acceptance and marker persistence are
not atomic: if Telegram accepts a message but the local marker write fails, a
later retry may send it again. Delivery is at-least-once across that failure
window, not exactly-once. Offline tests inject the transport and never call
Telegram.

## Mode semantics

- `baseline`: source file set, hashes, and byte counts must exactly match the
  recorded snapshot. Intentional source drift fails the baseline check.
- `development`: source drift is reported as information; intentional hash
  differences do not by themselves fail validation. Missing or unexpected
  source files, malformed manifest records, syntax/import failures, or test
  failures still fail validation.

The manifest describes the original 18-module source snapshot, not test or
script files. Do not update it to make a source-changing development branch look
like the original baseline. A new baseline requires an explicitly reviewed
provenance change.

## Test isolation

Ordinary discovery runs offline tests only. They use synthetic project trees,
temporary Git repositories, mocked subprocess/HTTP boundaries, and temporary
state files. There is no default live integration runner. Historical live-test
claims are not re-executed or treated as current validation; see
`docs/test-source-inventory.md` and `docs/e2e-test-gaps.md`.

## Interpreting outcomes

`XFAIL` is an expected failure for a documented unresolved behavior, not a
passing assertion or a test skip. `SKIP` is reported separately. Preserve the
full command output when recording results; distinguish current runs from
historical artifacts. The validator exits nonzero for an overall failure.

## Recorded validation runs

Initial baseline on 2026-10-23: ordinary discovery ran 75 tests: 74 passed,
0 failed, 0 skipped, and 1 expected failure; unittest exited 0. The initial
development validator exited 0 and reported `PASS=74 FAIL=0 SKIP=0 XFAIL=1
TOTAL=75`, `UNITTEST: PASS`, no live integration checks, and `OVERALL: PASS`.

Post-fix development validation on 2026-10-23: ordinary discovery ran 86 tests:
86 passed, 0 failed, 0 skipped, and 0 expected failures; unittest exited 0. The
development validator reported intentional source drift in
`project_queue_manager.py`, `project_quota.py`, `pw_dispatch.py`, `pw_notify.py`,
and `pw_plugin.py`; it passed source-file-set, syntax, imports, and the offline
suite with `PASS=86 FAIL=0 SKIP=0 XFAIL=0 TOTAL=86`, `UNITTEST: PASS`, no live
integration checks, and `OVERALL: PASS`. The manifest remained unchanged.

Post-fix baseline-mode validation on 2026-10-23 intentionally exited 1: source-file
set, syntax, imports, and all 86 offline tests passed, while the original-snapshot
hash check failed because the same five source modules were changed. This is the
expected manifest drift; `installed-source-manifest.json` was not rewritten.

A separate temporary focused verification script on 2026-10-23 ran 31 targeted
quota, Telegram, dispatcher, atomic-write, and fake-systemctl tests; all 31
passed. The script used a `hermes-verify-` tempfile in the scratch directory and
was removed after execution. This is supplemental ad-hoc verification, not a
substitute for the full discovery or validator runs. No live integrations were
exercised.

Strict-contract follow-up on 2026-10-23: ordinary discovery ran 88 tests; all 88
passed with no failures, skips, or expected failures. The development validator
exited 0. A separate OS-generated `hermes-verify-` script in the scratch directory
ran 5 focused dispatcher-contract tests; all 5 passed and the script was removed.
It exercised the real planner-to-dispatcher queued response plus malformed,
unsupported, and missing-field refusal cases. This ad-hoc result is supplemental;
it is not represented as suite green by itself. No live integration, real
systemd, or cron operation was performed.

Post-review validation on 2026-10-23: ordinary discovery ran 89 tests; all 89
passed with no failures, skips, or expected failures. The development validator
exited 0 and reported expected source drift in development mode; the manifest
was unchanged. A fresh OS-generated `hermes-verify-` script ran 5 targeted tests,
including the Telegram accepted-send/marker-write failure window and dispatcher
contract cases; all 5 passed and the script was removed. No live integrations,
real systemd, or cron operation was performed.

Planner/manager/dispatcher branch-matrix follow-up on 2026-10-23: ordinary
discovery ran 91 tests; all 91 passed with no failures, skips, or expected
failures. The development validator exited 0. A fresh OS-generated
`hermes-verify-` script ran 4 focused tests covering supported manager decisions,
tactical and strategic queued modes, rejection of status-only
`ready_for_planner`, and the real `plan_once()` queued-response round-trip; all 4
passed and the script was removed. No live integrations or real systemd/cron
operations were performed.
