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

## Recorded run

On 2026-10-23, ordinary discovery ran 75 tests: 74 passed, 0 failed, 0 skipped,
and 1 expected failure; unittest exited 0. Both validator modes exited 0 and
reported `PASS=74 FAIL=0 SKIP=0 XFAIL=1 TOTAL=75`, `UNITTEST: PASS`, live
integration checks excluded, and `OVERALL: PASS`. The XFAIL records the known
optional quota-entity default mismatch; details and coverage are in
`docs/test-coverage-matrix.md`. These results are a snapshot of that run, not a
claim that live integrations were exercised.
