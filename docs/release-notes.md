# Projectwright 0.1.6

Maintenance and distribution release since 0.1.5.

## Changes

- docs: expose packaged task tracker demo (examples/task_tracker/README.md)
- docs: expose packaged task tracker demo (README.md)
- docs: expose packaged task tracker demo (scripts/build-deb.sh)
- test: use isolated release notes fixture for confirmation
- test: stop confirmed release before any git operation
- test: cover default-no release confirmation
- docs: explain y/N release confirmation
- fix: use y/N confirmation for release publishing
- fix: request JSON status in Ubuntu compatibility matrix

## Requirements

- Ubuntu 24.04 and 26.04 LTS. Ubuntu 22.04 is not supported.
- Hermes CLI and per-user configuration are required and installed separately.
- Telegram approvals are optional and require consent during `pw setup`.

## Installation and upgrade

Install the signed APT source using the [repository guide](https://github.com/leftyfb/projectwright/blob/main/docs/apt-repository.md), then run:

```sh
sudo apt update
sudo apt install projectwright
pw setup
```

The release also attaches the versioned Debian package and SHA256SUMS.
Package installation does not modify Hermes credentials or activate plugins or user timers. Refer to the packaging guide for removal and rollback.

## Verification

The exact tagged commit must pass the hosted Ubuntu 24.04/26.04 clean-install and purge matrix. Historical live Telegram callback tests do not guarantee all Hermes installations or configurations.
