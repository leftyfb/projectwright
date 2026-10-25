#!/usr/bin/env python3
"""Read-only SSH preflight for a disposable Projectwright LXD container.

Does not install packages, modify files or request sudo. No private keys are
read by Projectwright: the local SSH client owns authentication.
"""
import argparse
import json
import subprocess
import sys

REMOTE = r"""set -eu
printf 'user='; id -un
printf 'hostname='; hostname
printf 'uid='; id -u
printf 'virt='; systemd-detect-virt --container || true
printf 'os='; . /etc/os-release; printf '%s\n' "$ID"
printf 'systemd='; if test -d /run/systemd/system; then echo running; else echo absent; fi
printf 'mounts='; grep -E ' /(home|var/lib|usr|etc) ' /proc/mounts | head -10 || true
"""

def inspect(target="ubuntu@pw-test", *, runner=subprocess.run):
    if target != "ubuntu@pw-test":
        raise ValueError("Only the explicit disposable target ubuntu@pw-test is permitted")
    result = runner(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         "-o", "StrictHostKeyChecking=yes", target, "sh", "-c", REMOTE],
        capture_output=True, text=True, timeout=25, check=True,
    )
    facts = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if facts.get("user") != "ubuntu" or facts.get("uid") == "0":
        raise RuntimeError("Refusing: SSH did not resolve to unprivileged ubuntu")
    if facts.get("virt") not in {"lxc", "lxd"}:
        raise RuntimeError("Refusing: target did not report LXC/LXD container virtualization")
    return facts

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="ubuntu@pw-test", choices=["ubuntu@pw-test"])
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.target), indent=2, sort_keys=True))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("PREFLIGHT REFUSED: " + str(exc), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
