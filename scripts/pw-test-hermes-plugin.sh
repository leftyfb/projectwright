#!/usr/bin/env bash
# Run only as ubuntu in the dedicated pw-test LXC runner.
set -euo pipefail
fail() { echo "REFUSED: $*" >&2; exit 2; }
[[ "$(hostname -s)" == pw-test ]] || fail "wrong host"
[[ "$(id -un)" == ubuntu && "$(id -u)" != 0 ]] || fail "wrong user"
[[ "$(systemd-detect-virt --container)" == lxc ]] || fail "not LXC"
[[ "$HOME" == /home/ubuntu ]] || fail "unexpected HOME"
[[ "${RUNNER_NAME-}" == pw-test-projectwright ]] || fail "wrong runner"
cli="$HOME/.local/bin/hermes"
[[ -x "$cli" ]] || fail "Hermes CLI not found"
[[ -f /usr/share/projectwright/hermes/projectwright-approvals/plugin.yaml ]] || fail "packaged plugin missing"
dest="$HOME/.hermes/plugins/projectwright-approvals"
# Recover only harmless generated cache left by our earlier failed cleanup.
# Refuse any plugin manifest or other content that could belong to the user.
if [[ -d "$dest" && ! -L "$dest" && ! -e "$dest/plugin.yaml" && ! -e "$dest/__init__.py" ]]; then
  if [[ -d "$dest/__pycache__" && ! -L "$dest/__pycache__" ]] &&
     [[ "$(find "$dest" -mindepth 1 -maxdepth 1 ! -name __pycache__ | wc -l)" -eq 0 ]]; then
    rm -rf -- "$dest/__pycache__"
    rmdir -- "$dest"
  fi
fi
[[ ! -e "$dest" && ! -L "$dest" ]] || fail "plugin already exists; preserving it"
cleanup() {
  rc=$?
  trap - EXIT
  "$cli" plugins disable projectwright-approvals >/dev/null 2>&1 || true
  if [[ -d "$dest" && ! -L "$dest" ]]; then
    # This directory was absent before the test and created by this script.
    # Hermes may generate __pycache__ or plugin metadata while loading it.
    rm -rf -- "$dest" || rc=1
  fi
  exit "$rc"
}
trap cleanup EXIT
mkdir -p -- "$dest"
cp -- /usr/share/projectwright/hermes/projectwright-approvals/plugin.yaml "$dest/plugin.yaml"
cp -- /usr/share/projectwright/hermes/projectwright-approvals/__init__.py "$dest/__init__.py"
"$cli" plugins enable projectwright-approvals
"$cli" plugins show projectwright-approvals
"$cli" plugins doctor projectwright-approvals
# Use the same Python runtime that launches Hermes to materialize the
# callback handler with a dummy application. No gateway or Telegram connection.
interpreter="$(head -n 1 "$cli")"
interpreter="${interpreter#\#!}"
interpreter="${interpreter%% *}"
[[ -x "$interpreter" ]] || fail "cannot identify Hermes Python interpreter"
"$interpreter" scripts/pw-test-hermes-callback.py
"$cli" plugins list
echo 'PASS: Projectwright native plugin enabled and discovered by real test Hermes CLI; cleanup follows'
