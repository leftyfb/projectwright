#!/usr/bin/env bash
# Explicitly invoked inside disposable pw-test LXD ONLY. Never run on tux.
# Usage: sudo bash scripts/pw-test-deb-lifecycle.sh /absolute/path/projectwright_*.deb
set -euo pipefail
die() { echo "REFUSED: $*" >&2; exit 2; }
[[ ${EUID} -eq 0 ]] || die "requires explicit root invocation inside pw-test; runner must not have sudo"
[[ "$(hostname -s)" == "pw-test" ]] || die "wrong hostname"
[[ "$(systemd-detect-virt --container 2>/dev/null)" == "lxc" ]] || die "not an LXC container"
[[ "${1-}" == /* && -f "${1-}" && ! -L "${1-}" ]] || die "provide an absolute regular Debian package path"
deb=$1
[[ "$(dpkg-deb --field "$deb" Package)" == "projectwright" ]] || die "package is not projectwright"
[[ "$(dpkg-deb --field "$deb" Version)" == "0.1.0~dev0-1" ]] || die "unexpected development package version"
if dpkg-query -W -f='${Status}' projectwright 2>/dev/null | grep -Eq '(installed|unpacked|half-installed|half-configured|config-files)'; then
  die "projectwright is already installed; never overwrite an existing installation"
fi
[[ ! -e /usr/bin/pw && ! -L /usr/bin/pw && ! -e /usr/share/projectwright && ! -L /usr/share/projectwright ]] || die "Projectwright paths already exist"
# Require a non-privileged runner and no obvious host bind-mounted paths.
[[ -f /run/systemd/container ]] || die "missing systemd container marker"
if grep -Eq ' /(home|etc|usr|var/lib/dpkg) (none|ext4|btrfs|zfs|overlay) .*bind' /proc/mounts; then
  die "suspicious bind mount: review isolation first"
fi
cleanup() {
  rc=$?
  trap - EXIT
  if dpkg-query -W -f='${Status}' projectwright 2>/dev/null | grep -Eq '(installed|unpacked|half-installed|half-configured|config-files)'; then
    dpkg --purge projectwright || rc=1
  fi
  if [[ -e /usr/bin/pw || -L /usr/bin/pw || -e /usr/share/projectwright || -L /usr/share/projectwright ]]; then
    echo "REFUSED cleanup incomplete: package-owned paths still present" >&2
    rc=1
  fi
  exit "$rc"
}
trap cleanup EXIT
dpkg --install "$deb"
dpkg-query -W -f='${Status}\n' projectwright | grep -qx 'install ok installed'
for name in pw pw-dispatch pw-manager pw-worker pw-notify pw-timer; do
  command -v "$name" >/dev/null
  "$name" --help >/dev/null
done
# Reinstall the *identical* preview to test repeat installation semantics;
# true upgrade requires a separately versioned package.
dpkg --install "$deb"
dpkg-query -W -f='${Status}\n' projectwright | grep -qx 'install ok installed'
echo "PASS: install, reinstall and CLI smoke. Purge runs via EXIT trap."
