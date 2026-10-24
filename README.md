# Projectwright source snapshot and tests

This repository contains an audited snapshot of Projectwright's 18 flat Python
modules under `src/projectwright/`, together with an immutable source manifest
and an offline `unittest` suite. Runtime scripts in `~/.hermes/scripts/` are not
modified by this repository's tests.

## Development wheel preview

A preliminary, non-production Python wheel can be built from the repository's
`pyproject.toml`. CI installs the wheel into a disposable target, smoke-tests the
`pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify` and `pw-timer` entrypoints,
and retains a seven-day wheel artifact. See [development wheel notes](docs/development-wheel.md)
for build instructions and remaining Hermes-specific runtime assumptions. The
package does not install/enable systemd timers or modify `~/.hermes/scripts`.

## Run the offline suite

From the repository root:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

The suite uses temporary directories/repositories and mocked service boundaries.
It does not send Telegram messages, call live Home Assistant or Hermes APIs, or
start/enable systemd units. Live checks are intentionally not part of default
discovery; see `docs/e2e-test-gaps.md` before attempting any separate live test.

## Validate source and baseline

```sh
python3 -B scripts/validate-baseline.py --mode baseline
python3 -B scripts/validate-baseline.py --mode development
```

`baseline` requires the checked-out source file set and SHA-256 values to match
`installed-source-manifest.json`. `development` reports source drift while
still enforcing the expected file set and running syntax, import, dependency,
and offline-suite checks. Details: `docs/baseline-validation.md`.

## Decision and configuration contracts

The `project_queue_manager.py --once` JSON and exit-code contract, quota
sensor semantics, and Telegram multi-recipient parsing/delivery rules are
specified in `docs/baseline-validation.md`. Current coverage and explicit
remaining gaps are tracked in `docs/test-coverage-matrix.md` and
`docs/e2e-test-gaps.md`.

## Test documentation

- `docs/test-source-inventory.md` — recovered historical test artifacts and
  provenance.
- `docs/test-coverage-matrix.md` — current offline coverage and known gaps.
- `docs/e2e-test-gaps.md` — residual live/integration work and safety boundaries.
- `docs/technical-debt.md` — source/runtime findings and unresolved contracts.
