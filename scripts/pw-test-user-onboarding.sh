#!/usr/bin/env bash
# Disposable pw-test account only. Never reuse production Hermes credentials.
set -euo pipefail
fail() { echo "REFUSED: $*" >&2; exit 2; }
[[ "$(hostname -s)" == pw-test ]] || fail "wrong host"
[[ "$(id -un)" == ubuntu && "$(id -u)" != 0 ]] || fail "requires ubuntu nonroot user"
[[ "$(systemd-detect-virt --container)" == lxc ]] || fail "not LXC"
[[ "$HOME" == /home/ubuntu ]] || fail "unexpected home"
[[ -n "${XDG_RUNTIME_DIR-}" && -S "${XDG_RUNTIME_DIR}/bus" ]] || fail "user bus unavailable"
[[ ! -e "$HOME/.hermes/.env" && ! -L "$HOME/.hermes/.env" ]] || fail "existing Hermes env"
[[ ! -e "$HOME/.config/systemd/user/projectwright-approval-notify.timer" ]] || fail "existing timer"
[[ ! -e "$HOME/.config/systemd/user/projectwright-approval-notify.service" ]] || fail "existing service"
[[ ! -e "$HOME/.hermes/plugins/projectwright-approvals" ]] || fail "existing Hermes plugin"
[[ -x /usr/bin/pw ]] || fail "installed package missing"
mkdir -p "$HOME/.hermes"
env_file="$HOME/.hermes/.env"
timer_file="$HOME/.config/systemd/user/projectwright-approval-notify.timer"
service_file="$HOME/.config/systemd/user/projectwright-approval-notify.service"
cleanup() {
  status=$?
  trap - EXIT
  systemctl --user disable --now projectwright-approval-notify.timer >/dev/null 2>&1 || true
  rm -f -- "$timer_file" "$service_file" "$env_file"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT
(umask 077; printf 'TELEGRAM_BOT_TOKEN=123456:pw-test-fake-token-NO-NETWORK\nTELEGRAM_ALLOWED_USERS=123456789\n' > "$env_file")
/usr/bin/pw setup-user --minutes 1440
systemctl --user is-enabled projectwright-approval-notify.timer | grep -Fxq enabled
systemctl --user is-active projectwright-approval-notify.timer | grep -Fxq active
test -f "$timer_file"
test -f "$service_file"
grep -Fq 'OnUnitInactiveSec=1440min' "$timer_file"
# Immediately disable the timer before checking repeat onboarding.
systemctl --user disable --now projectwright-approval-notify.timer
/usr/bin/pw setup-user --minutes 1440
systemctl --user disable --now projectwright-approval-notify.timer
echo 'PASS: live per-user timer setup, enable, disable and idempotent setup'
