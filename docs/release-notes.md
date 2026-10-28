# Projectwright 0.1.2

Maintenance and distribution release since 0.1.1.

## Changes

- make release.py executable
- Document one-command public release helper and manual fallback
- Test release version preparation and guarded dispatch without side effects
- Add guarded one-command maintainer release orchestrator
- Recommend live signed APT installation and link maintainer release guide
- Guard trusted release-to-APT trigger with regression test
- Document safe development-to-signed-APT release procedure
- Correct packaging guide for live signed APT upgrades
- Document live APT feed and guarded automatic refresh
- Republish signed APT feed after verified release workflow succeeds
- Regression test readable setup prompt and opt-out safety
- Give interactive Hermes and Telegram setup a readable layout
- Ship release checksum file with compatibility artifact
- Publish release-specific notes from exact tested source

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
