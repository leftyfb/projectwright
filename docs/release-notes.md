# Projectwright 0.2.0

Maintenance and distribution release since 0.1.9.

## Changes

- test: explicitly enable quota for environment-default sensor case
- test: opt into quota explicitly in HA failure and sensor policy cases
- test: quota disabled by default and explicit opt-in remains fail-closed
- docs: explain opt-in quota and empty-plan troubleshooting
- docs: explain opt-in quota and empty-plan troubleshooting
- fix: permit greenfield planning and avoid permanently suppressing empty initial queues
- fix: default HA quota checks to disabled unless explicitly enabled
- fix: default HA quota checks to disabled unless explicitly enabled
- fix: default HA quota checks to disabled unless explicitly enabled
- fix: default HA quota checks to disabled unless explicitly enabled

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
