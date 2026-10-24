#!/usr/bin/env python3
"""Validate Projectwright source baseline and run the offline unittest suite.

Usage from the repository root:
  python3 -B scripts/validate-baseline.py --mode baseline
  python3 -B scripts/validate-baseline.py --mode development

Baseline mode requires the 18 expected source files to match the immutable
installed-source-manifest.json hashes and byte counts. Development mode reports
source drift but does not reject intentional edits merely for differing from
that manifest.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

EXPECTED_SOURCE_FILES = {
    "project_acceptance_gate.py",
    "project_milestone_guard.py",
    "project_milestone_sequence.py",
    "project_notes_publisher.py",
    "project_notes_sync.py",
    "project_queue_manager.py",
    "project_queue_planner.py",
    "project_quota.py",
    "project_recovery.py",
    "project_task_worker.py",
    "project_telegram_approval.py",
    "project_worker_journal.py",
    "project_worker_progress.py",
    "pw_buttons.py",
    "pw_dispatch.py",
    "pw_notify.py",
    "pw_plugin.py",
    "pw_project_timer.py",
}
DEVELOPMENT_ADDED_SOURCE_FILES = {'pw_worker_progress.py', 'pw_milestone_sequence.py', 'pw_acceptance_gate.py', 'pw_quota.py'}
ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "src" / "projectwright"
MANIFEST_PATH = ROOT / "installed-source-manifest.json"
TEST_DIR = ROOT / "tests"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"MANIFEST: FAIL ({exc})")
        return {}
    if not isinstance(value, dict):
        print("MANIFEST: FAIL (top-level JSON value must be an object)")
        return {}
    files = value.get("files")
    if not isinstance(files, dict):
        print("MANIFEST: FAIL (missing files object)")
        return {}
    print(f"Manifest: {MANIFEST_PATH.relative_to(ROOT)} ({len(files)} entries; read-only)")
    return files


def inspect_source(mode: str, manifest: dict) -> tuple[bool, bool, bool, bool]:
    actual_paths = sorted(SOURCE_DIR.glob("*.py")) if SOURCE_DIR.is_dir() else []
    actual_names = {path.name for path in actual_paths}
    manifest_names = set(manifest)
    missing = sorted(EXPECTED_SOURCE_FILES - actual_names)
    extra = sorted(actual_names - EXPECTED_SOURCE_FILES)
    manifest_mismatch = sorted(manifest_names ^ EXPECTED_SOURCE_FILES)
    invalid_manifest_records = []
    for name in sorted(EXPECTED_SOURCE_FILES):
        record = manifest.get(name)
        digest = record.get("sha256") if isinstance(record, dict) else None
        size = record.get("bytes") if isinstance(record, dict) else None
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            invalid_manifest_records.append(f"{name}: invalid sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            invalid_manifest_records.append(f"{name}: invalid bytes")
    print(f"Expected source files: {len(EXPECTED_SOURCE_FILES)}; present: {len(actual_names)}")
    permitted_extra = DEVELOPMENT_ADDED_SOURCE_FILES if mode == 'development' else set()
    print(f"Source file set: {'PASS' if not missing and not (set(extra) - permitted_extra) else 'FAIL'}")
    if missing:
        print("  missing: " + ", ".join(missing))
    if extra:
        print("  added/unexpected: " + ", ".join(extra))
    if manifest_mismatch:
        print("  manifest file-set mismatch: " + ", ".join(manifest_mismatch))
    if invalid_manifest_records:
        print("Invalid manifest records: " + "; ".join(invalid_manifest_records))

    changed: list[str] = []
    size_mismatch: list[str] = []
    unrecorded: list[str] = []
    for path in actual_paths:
        record = manifest.get(path.name)
        if record is None:
            unrecorded.append(path.name)
            continue
        expected_hash = record.get("sha256") if isinstance(record, dict) else None
        expected_size = record.get("bytes") if isinstance(record, dict) else None
        if not expected_hash:
            unrecorded.append(path.name)
        elif sha256(path) != expected_hash:
            changed.append(path.name)
        if (
            isinstance(expected_size, int)
            and not isinstance(expected_size, bool)
            and path.stat().st_size != expected_size
        ):
            size_mismatch.append(path.name)
    removed_from_manifest = sorted(manifest_names - actual_names)
    drift = bool(changed or size_mismatch or unrecorded or removed_from_manifest or extra)
    print(f"Source drift vs manifest: {'YES' if drift else 'NONE'}")
    if changed:
        print("  changed hashes: " + ", ".join(changed))
    if size_mismatch:
        print("  byte-count mismatch: " + ", ".join(size_mismatch))
    if unrecorded:
        print("  files without manifest hash: " + ", ".join(unrecorded))
    if removed_from_manifest:
        print("  manifest files absent from source: " + ", ".join(removed_from_manifest))
    if mode == "development" and drift:
        print("  development mode: drift is reported, not treated as baseline corruption")
    baseline_ok = (
        not missing
        and not extra
        and not manifest_mismatch
        and not invalid_manifest_records
        and not drift
    )
    source_set_ok = not missing and not (set(extra) - permitted_extra)
    if mode == "baseline":
        print(f"Original snapshot hash check: {'PASS' if baseline_ok else 'FAIL'}")
    else:
        print("Original snapshot hash check: informational in development mode")

    syntax_ok = True
    for path in actual_paths:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            syntax_ok = False
            print(f"SYNTAX FAIL {path.relative_to(ROOT)}: {exc}")
    print(f"Python syntax: {'PASS' if syntax_ok else 'FAIL'} ({len(actual_paths)} files checked)")

    import_ok = True
    missing_dependencies: set[str] = set()
    sys.path.insert(0, str(SOURCE_DIR))
    for path in actual_paths:
        module_name = path.stem
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            import_ok = False
            missing_dependencies.add(exc.name or "unknown")
            print(f"IMPORT FAIL {module_name}: missing module {exc.name!r}")
        except Exception as exc:  # report import-time failures without hiding them
            import_ok = False
            print(f"IMPORT FAIL {module_name}: {type(exc).__name__}: {exc}")
    print(f"Python imports: {'PASS' if import_ok else 'FAIL'} ({len(actual_paths)} modules attempted)")
    if missing_dependencies:
        print("Missing dependencies: " + ", ".join(sorted(missing_dependencies)))
    elif import_ok:
        print("Missing dependencies: none observed during module imports")
    manifest_ok = not manifest_mismatch and not invalid_manifest_records and set(manifest) == EXPECTED_SOURCE_FILES
    return source_set_ok, syntax_ok and import_ok, baseline_ok, manifest_ok


def run_unittest_suite() -> tuple[bool, dict[str, int]]:
    if not TEST_DIR.is_dir():
        print("UNITTEST: FAIL (tests/ directory is missing)")
        return False, {"pass": 0, "fail": 0, "skip": 0, "xfail": 0, "total": 0}
    command = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        str(TEST_DIR),
        "-p",
        "test_*.py",
        "-v",
    ]
    print("\nRunning offline suite: " + " ".join(command))
    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    total_match = re.search(r"Ran (\d+) tests?", result.stdout)
    total = int(total_match.group(1)) if total_match else 0
    summary_match = re.search(r"(?:FAILED|OK) \(([^)]*)\)", result.stdout)
    counts = {"failures": 0, "errors": 0, "skipped": 0, "expected failures": 0, "unexpected successes": 0}
    if summary_match:
        for key, value in re.findall(r"([a-z ]+)=(\d+)", summary_match.group(1)):
            if key in counts:
                counts[key] = int(value)
    failed = counts["failures"] + counts["errors"] + counts["unexpected successes"]
    skipped = counts["skipped"]
    xfailed = counts["expected failures"]
    passed = max(0, total - failed - skipped - xfailed)
    report = {"pass": passed, "fail": failed, "skip": skipped, "xfail": xfailed, "total": total}
    print(
        "Suite totals: "
        f"PASS={passed} FAIL={failed} SKIP={skipped} XFAIL={xfailed} TOTAL={total}"
    )
    ok = result.returncode == 0 and total_match is not None
    if not total:
        print("Suite warning: unittest discovered zero tests")
        ok = False
    print(f"UNITTEST: {'PASS' if ok else 'FAIL'} (exit {result.returncode})")
    print("Live integration checks: SKIP (not part of ordinary offline discovery)")
    return ok, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("baseline", "development"), required=True)
    args = parser.parse_args()
    print(f"Projectwright validation mode: {args.mode}")
    print(f"Repository: {ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    manifest = load_manifest()
    source_set_ok, syntax_import_ok, original_snapshot_ok, manifest_ok = inspect_source(args.mode, manifest)
    suite_ok, _ = run_unittest_suite()
    baseline_mode_ok = args.mode != "baseline" or original_snapshot_ok
    overall = source_set_ok and syntax_import_ok and manifest_ok and suite_ok and baseline_mode_ok
    print(f"\nOVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
