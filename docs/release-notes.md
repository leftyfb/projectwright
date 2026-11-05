# Projectwright 0.2.4

Maintenance and distribution release since 0.2.3.

## Changes

- docs: explain milestone revalidation and safe successor approval carry-forward
- fix: parse Oxford comma in explicit COMMIT file lists
- fix: distinguish stale historical approvals from never-approved milestones in notifier diagnostics
- test: fail before COMMIT when leftover files exceed literal assignment scope
- test: default sequencing preserves only chain-verified predecessor acceptance
- fix: preserve evidenced predecessor acceptance through authorized successor commits in default mode
- fix: correctly parse literal filename lists in COMMIT scope
- fix: preserve dots in filenames when parsing scoped COMMIT instructions
- fix: block scoped COMMIT before agent runs when dirty files exceed assigned paths
- test: explicit milestone selection and ambiguity refusal
- feat: add pw notify --project ID --milestone ID for explicit approval requests
- feat: allow explicitly selected milestone in approval scan, preserving strict sequencing

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
