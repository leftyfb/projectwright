#!/usr/bin/env bash
# Set up a disposable, preplanned Projectwright/Hermes demo; never run on an existing directory.
set -euo pipefail
root="${1:-$HOME/projectwright-demo}"
case "$root" in /*) ;; *) echo "Use an absolute demo directory path" >&2; exit 2 ;; esac
if [[ -e "$root" || -L "$root" ]]; then
  echo "Refusing to overwrite existing path: $root" >&2
  exit 2
fi
command -v pw >/dev/null || { echo "Install Projectwright first (pw missing)" >&2; exit 2; }
command -v git >/dev/null || { echo "git is required" >&2; exit 2; }
mkdir -p "$root/repo/tests" "$root/state"
repo="$root/repo"
git -C "$repo" init -q -b main
cat > "$repo/README.md" <<'EOF'
# Demo counter library
This intentionally incomplete Python library is the **working repository** for
the Projectwright preplanned demo. Its increment function is not implemented.
Projectwright is expected to develop, test, and commit the missing behavior.
The Projectwright requirements and queue live in ../state/projects/demo-counter,
not in this Git repository.
EOF
cat > "$repo/counter.py" <<'EOF'
"""Tiny demo counter. TODO: implement increment."""
def increment(value: int) -> int:
    raise NotImplementedError("Hermes will implement this in the EDIT task")
EOF
cat > "$repo/tests/test_counter.py" <<'EOF'
import unittest
from counter import increment

class CounterTests(unittest.TestCase):
    def test_increments_positive(self):
        self.assertEqual(increment(4), 5)

    def test_increments_negative(self):
        self.assertEqual(increment(-2), -1)

    def test_increments_zero(self):
        self.assertEqual(increment(0), 1)

if __name__ == "__main__":
    unittest.main()
EOF
git -C "$repo" add README.md counter.py tests/test_counter.py
git -C "$repo" -c user.name='Projectwright Demo' -c user.email='demo@example.invalid' commit -qm 'demo: initial incomplete counter library'
pw init --project demo-counter --repo "$repo" --config-dir "$root/state"
state="$root/state/projects/demo-counter"
cat > "$state/requirements.md" <<'EOF'
# Counter library demonstration

## DEMO-1 — Add an integer increment operation

Provide a minimal Python 3 standard-library-only module with an `increment(value)`
function returning the integer increased by one. Work only in the disposable
demo repository; do not access credentials, production directories, or network
services. Keep the existing tests and avoid introducing dependencies.

### DEMO-1-M1 — Implement, test and commit increment

Implement the behavior in `counter.py`, run the isolated test suite, and
commit only the allowed source change. Do not alter `tests/test_counter.py`
to make the tests pass. No other file changes are authorized.

#### Acceptance
- **Command:** `python3 -B -m unittest discover -s tests -p test_counter.py`
- **Scope:** `counter.py`
EOF
cat > "$state/queue.md" <<'EOF'
# Demo counter — preplanned task queue

- [ ] **P100 — READ** DEMO-1 / DEMO-1-M1: Inspect the incomplete counter module and existing tests, and explain the intended single-file implementation scope.
- [ ] **P101 — EDIT** DEMO-1 / DEMO-1-M1: Implement increment in counter.py, returning its integer input plus one without modifying tests or unrelated files.
- [ ] **P102 — TEST** DEMO-1 / DEMO-1-M1: Run python3 -B -m unittest discover -s tests -p test_counter.py and report whether the unchanged tests pass.
- [ ] **P103 — COMMIT** DEMO-1 / DEMO-1-M1: Commit the reviewed counter.py change after successful tests, without adding unrelated files to the commit.
EOF
cat > "$state/work_log.md" <<'EOF'
# Demo work log

No tasks have executed yet. This is a preplanned sample, not a recorded run.
EOF
python3 - "$state/config.json" "$state" <<'PY'
import json
from pathlib import Path
import sys
path = Path(sys.argv[1])
state = Path(sys.argv[2])
cfg = json.loads(path.read_text(encoding="utf-8"))
cfg["planning"] = {"enabled": False, "requirements_file": str(state / "requirements.md")}
cfg["execution"] = {"enabled": False}
cfg["cycle_file"] = str(state / "git_cycle.json")
cfg["quota"] = {"enabled": False}
path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
printf '\nDemo initialized at %s\n' "$root"
printf 'Inspect: PROJECTWRIGHT_CONFIG_DIR=%q pw status --project demo-counter\n' "$root/state"
printf 'Run ONE task: PROJECTWRIGHT_CONFIG_DIR=%q pw start --project demo-counter\n' "$root/state"
printf 'Read the ready_demo README before executing. No work has run yet.\n'
