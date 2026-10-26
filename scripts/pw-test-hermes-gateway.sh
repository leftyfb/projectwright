#!/usr/bin/env bash
# Disposable pw-test gateway integration. Leaves prior Hermes credentials untouched.
set -euo pipefail
fail() { echo "REFUSED: $*" >&2; exit 2; }
[[ "$(hostname -s)" == pw-test && "$(id -un)" == ubuntu ]] || fail "wrong account or host"
[[ "$(systemd-detect-virt --container)" == lxc ]] || fail "not LXC"
[[ "${RUNNER_NAME-}" == pw-test-projectwright ]] || fail "wrong runner"
[[ "$HOME" == /home/ubuntu ]] || fail "wrong HOME"
dest="$HOME/.hermes/plugins/projectwright-approvals"
cli="$HOME/.local/bin/hermes"
[[ ! -e "$dest" && ! -L "$dest" ]] || fail "pre-existing plugin"
[[ -x "$cli" && -f /usr/share/projectwright/hermes/projectwright-approvals/plugin.yaml ]] || fail "missing Hermes or Debian plugin assets"
systemctl --user is-active --quiet hermes-gateway.service || fail "gateway must already be running"
created=0
cleanup() {
  code=$?
  trap - EXIT
  if [[ "$created" == 1 ]]; then
    "$cli" plugins disable projectwright-approvals >/dev/null 2>&1 || code=1
    if [[ -d "$dest" && ! -L "$dest" ]]; then rm -rf -- "$dest" || code=1; fi
    # Reload the test gateway back to its original plugin configuration.
    systemctl --user restart hermes-gateway.service || code=1
    systemctl --user is-active --quiet hermes-gateway.service || code=1
  fi
  exit "$code"
}
trap cleanup EXIT
mkdir -p "$dest"
created=1
cp /usr/share/projectwright/hermes/projectwright-approvals/plugin.yaml "$dest/plugin.yaml"
cp /usr/share/projectwright/hermes/projectwright-approvals/__init__.py "$dest/__init__.py"
"$cli" plugins enable projectwright-approvals
"$cli" plugins doctor projectwright-approvals
systemctl --user restart hermes-gateway.service
systemctl --user is-active --quiet hermes-gateway.service
# Inspect only plugin-specific status lines; never log credentials or gateway environment.
journalctl --user -u hermes-gateway.service -n 300 --no-pager --output=cat |
  grep -iE 'projectwright.approvals|projectwright.*plugin' | tail -15 || true
echo "PASS: gateway restarted and remained active with Projectwright enabled; reverting"
