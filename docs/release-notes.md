# Projectwright 0.2.5

Maintenance and distribution release since 0.2.4.

## Changes

- validation: register completion notifier as intentional development source module
- test: include completion notifier in audited wheel module inventory
- docs: final project completion Telegram summary, eligibility and retry semantics
- build: include final project notification module in wheel and Debian package
- test: add real newline in additional unapproved milestone fixture
- test: announce only fully accepted final milestones and deduplicate recipients
- feat: retry final project completion notices through existing pw notify timer
- feat: send final completion Telegram after successful last acceptance callback
- feat: detect accepted final milestone and send deduplicated project completion summary
- feat: reusable authorized Telegram plain-text delivery for completion notice
- test: explicit notifier no-op on already verified milestone
- fix: preserve requested milestone ID and report already-current approvals as no-op

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
