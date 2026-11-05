# Projectwright 0.2.3

Maintenance and distribution release since 0.2.2.

## Changes

- fix: validate notifier project ID without depending on mocked bridge constant
- test: notifier target project and skip non-Projectwright directories
- test compatibility: preserve unscoped notifier calls
- feat: allow pw notify --project to isolate approval scans
- fix: scope approval scans and skip directories with no Projectwright config
- fix: show milestone approval next step instead of misleading completion
- fix: show milestone approval next step instead of misleading completion

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
