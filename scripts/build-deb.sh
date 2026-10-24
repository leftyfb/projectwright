#!/usr/bin/env bash
# Build an uninstalled Debian preview from an already verified pure-Python wheel.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 path/to/projectwright.whl output-directory" >&2
  exit 2
fi
wheel=$(realpath "$1")
output=$(realpath -m "$2")
[[ -f "$wheel" ]] || { echo "wheel does not exist: $wheel" >&2; exit 2; }
command -v dpkg-deb >/dev/null || { echo "dpkg-deb required" >&2; exit 2; }

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/DEBIAN" "$stage/usr/lib/python3/dist-packages" "$stage/usr/bin" "$output"
python3 -m pip install --no-deps --no-compile --target "$stage/usr/lib/python3/dist-packages" "$wheel"
# Pip may generate Python-version-specific command launchers and a bin folder.
# Debian executables must instead use the distribution's /usr/bin/python3.
rm -rf "$stage/usr/lib/python3/dist-packages/bin"
# Ship reference integration assets in /usr/share, never activate user services
# from the privileged Debian installation context.
mkdir -p "$stage/usr/share/projectwright/hermes"
install -m 0644 "$(dirname "$0")/../src/projectwright/pw_plugin.py" \
  "$stage/usr/share/projectwright/hermes/projectwright-approvals.py"
mkdir -p "$stage/usr/share/projectwright/systemd/user"
cat > "$stage/usr/share/projectwright/systemd/user/projectwright-approval-notify.service" <<'EOF'
[Unit]
Description=Projectwright approval notification scan
[Service]
Type=oneshot
ExecStart=/usr/bin/pw-notify --send
EOF
cat > "$stage/usr/share/projectwright/systemd/user/projectwright-approval-notify.timer" <<'EOF'
[Unit]
Description=Projectwright approval notification timer
[Timer]
OnBootSec=3min
OnUnitInactiveSec=10min
Persistent=false
[Install]
WantedBy=timers.target
EOF

for name in dispatch manager worker notify timer; do
  case "$name" in
    dispatch) module=pw_dispatch ;;
    manager) module=project_queue_manager ;;
    worker) module=project_task_worker ;;
    notify) module=pw_notify ;;
    timer) module=pw_project_timer ;;
  esac
  printf '#!/bin/sh\nexec /usr/bin/python3 -m %s "$@"\n' "$module" > "$stage/usr/bin/pw-$name"
  chmod 0755 "$stage/usr/bin/pw-$name"
done
cat > "$stage/usr/bin/pw" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 -c 'import pw_dispatch; raise SystemExit(pw_dispatch.cli())' "$@"
EOF
chmod 0755 "$stage/usr/bin/pw"
cat > "$stage/DEBIAN/control" <<'EOF'
Package: projectwright
Version: 0.1.0~dev0-1
Section: utils
Priority: optional
Architecture: all
Maintainer: Projectwright Contributors <noreply@github.com>
Depends: python3 (>= 3.10), git
Description: Development preview of project task orchestration
 A pre-release packaging checkpoint for Projectwright. External agent
 services and project configuration are not provisioned by this package.
EOF
chmod 0644 "$stage/DEBIAN/control"
dpkg-deb --build --root-owner-group "$stage" "$output/projectwright_0.1.0~dev0-1_all.deb"
dpkg-deb --field "$output/projectwright_0.1.0~dev0-1_all.deb"
