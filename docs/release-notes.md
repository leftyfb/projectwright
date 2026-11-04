# Projectwright 0.1.9

Maintenance and distribution release since 0.1.8.

## Changes

- test: remove final implicit-XDG and legacy fallback assertions
- fix: share single project root resolver between manager and CLI
- test: finish updating legacy-root cases to new home default
- test: update project-root expectations for ~/projects default
- test: update project-root expectations for ~/projects default
- test: update project-root expectations for ~/projects default
- test: update project-root expectations for ~/projects default
- test: update project-root expectations for ~/projects default
- test: update project-root expectations for ~/projects default
- test: update project-root expectations for ~/projects default
- test: update project-root expectations for ~/projects default
- docs: align CLI and walkthrough with ~/projects state default
- docs: align CLI and walkthrough with ~/projects state default
- docs: align default project state paths with ~/projects
- test: require ~/projects state default even when legacy roots exist
- docs: specify ~/projects as Projectwright's default state directory
- fix: default Projectwright state to ~/projects regardless of legacy directories

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
