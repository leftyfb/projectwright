# Projectwright 0.1.1

Projectwright 0.1.1 is a maintenance and distribution release of the Hermes-based project task orchestration system. It does not introduce a new orchestration feature set.

## Changes since 0.1.0

- Prepare Projectwright for public development: MIT license, security reporting and contributor guidance, and public-facing documentation.
- Retire the old self-hosted GitHub Actions runners and host-specific automation; use hosted CI and explicit maintainer-driven publication.
- Add and validate a signed APT archive on GitHub Pages, so supported Ubuntu systems can receive Projectwright updates through normal package management.
- Update release and packaging checks while preserving the opt-in configuration model.

## Requirements and supported systems

- Ubuntu **24.04 LTS** and **26.04 LTS** (Ubuntu 22.04 is not supported).
- Hermes CLI and its per-user configuration are required and installed separately.
- Git is required. Telegram approvals are optional: `pw setup` detects configured Hermes Telegram integration and asks for consent before enabling Projectwright's plugin and user notifier timer.

## Install and upgrade

**Preferred: signed APT repository.** Follow the current repository setup instructions in the [README](../README.md) and [packaging guide](packaging-and-operations.md). After registering the signed Projectwright APT source:

```sh
sudo apt update
sudo apt install projectwright
pw --help
pw setup
```

If Projectwright is already installed from that APT source, `sudo apt upgrade` will install the new package when the APT repository is republished with 0.1.1.

**Manual package download:** The release attaches `projectwright_0.1.1-1_all.deb` and `SHA256SUMS`. Download both from the [0.1.1 GitHub Release](https://github.com/leftyfb/projectwright/releases/tag/0.1.1), then verify and install:

```sh
sha256sum -c SHA256SUMS
sudo apt install ./projectwright_0.1.1-1_all.deb
pw setup
```

Run `pw setup` as the intended ordinary Hermes user, not as root. Debian package installation does not automatically configure Hermes, enable user systemd services, or modify Telegram credentials.

## Verification and limitations

Publication requires the **exact release-branch commit** to pass the hosted Ubuntu 24.04/26.04 Debian clean-install, command smoke, and purge matrix. The release workflow refuses a different source SHA or CI artifact and validates the Debian package checksum and metadata before tagging. The separate signed APT publication workflow must be rerun after this GitHub Release is available.

The existing 0.1.0 acceptance record includes real isolated Telegram Approve and Reject callbacks, packaged task execution and Debian lifecycle tests. These are prior regression evidence, not a claim that every Hermes version, live model, production deployment, Telegram configuration, or migration scenario has been retested for 0.1.1. Manual APT installation on Ubuntu 24.04 remains deferred.

User-owned projects, Git worktrees, journals, Hermes credentials, plugins and user timers are outside Debian package ownership. Back up important user-owned state before major changes; review the [packaging and operations guide](packaging-and-operations.md) before removal or rollback.
