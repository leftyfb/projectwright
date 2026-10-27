# Projectwright 0.1.0 — release notes (candidate)

**Status:** candidate prepared from `release/0.1.0`; not yet tagged or published.
The GitHub Release and its artifact checksums must be generated from the **exact
tested release commit**, not copied from an earlier development build.

## What this release provides

- Hermes-based requirements-to-Git task orchestration: planning, bounded
  queue dispatch, READ and scoped EDIT/TEST/COMMIT execution, journal and recovery
  evidence, Git safeguards, and milestone acceptance.
- Unified `pw` CLI: `setup`, `init`, `defaults`, `status`, `plan`,
  `tick`, `worker`, `notify`, and `timer`, with legacy executable entrypoints.
- First-run `pw setup` checks Hermes availability and plugin discovery, then
  detects existing Hermes Telegram credentials and **asks before** installing
  Projectwright's Telegram approval plugin and user notification timer.
- Configuration-free project skeleton support and opt-in user systemd timers.
- Debian package shipping inert Hermes plugin and systemd integration assets,
  without touching a user's secrets, projects, timers, or running gateway during
  package installation or purge.

## Supported environment

- **Ubuntu 24.04 LTS** (distribution Python 3.12).
- **Ubuntu 26.04 LTS** (distribution Python 3.14).
- **Hermes CLI and per-user Hermes configuration required.** Hermes is installed
  separately and is not installed by the Projectwright Debian package.
- Git required. Telegram approval is expected but optional to activate. Existing
  valid bot token and numeric authorized-user settings are needed to enable it.
- Ubuntu 22.04 is **not** a supported target.

## Installation after publication

Download `projectwright_0.1.0-1_all.deb` and its published SHA-256 file from
the **Projectwright 0.1.0** GitHub Release. Verify the checksum first, then
install on a supported Ubuntu version:

```sh
sha256sum -c SHA256SUMS
sudo apt install ./projectwright_0.1.0-1_all.deb
pw --help
pw setup
```

Run `pw setup` as the intended ordinary Hermes user, not root. It does not
restart the Hermes gateway. If the user approves Telegram plugin activation,
review and separately perform any needed gateway reload/restart.

To inspect a project without enabling execution:

```sh
pw init --project demo
pw defaults --project demo
pw status --project demo
```

`pw init` defaults to an inert, disabled project. It does not create or
configure a model, Git worktree, or Telegram bot.

## Upgrade and removal

Before upgrading or uninstalling, back up user-owned project configurations,
Git worktrees, queue, journals, approval receipts, and Hermes integration state.
The Debian package intentionally does not delete a user's projects, credentials,
or custom systemd units on purge. Disable manually enabled user timers and review
plugin/gateway state before removing the package:

```sh
systemctl --user disable --now projectwright-approval-notify.timer
sudo apt remove projectwright
```

`apt remove` does **not** automatically disable a Hermes plugin in the user's
environment. Refer to [packaging operations](packaging-and-operations.md) for the
full upgrade, rollback and cleanup considerations.

## Verification and boundaries

Prior review-branch evidence includes hosted Ubuntu 24.04/26.04 installation
and purge, packaged fake-provider READ and EDIT/TEST/COMMIT, genuine distinct-source
Debian upgrade preserving 35 user-owned files, and isolated live Hermes/Telegram
Approve and Reject callbacks. The final `0.1.0` artifact requires its **own**
green release-branch CI and LTS matrix before tagging and publication.

These tests do not guarantee every Hermes version or Telegram configuration,
production installation scenario, future state migration, authorization edge
case, or live-model end-to-end task. The alternate command provider and
Home Assistant integration are not replacements for the required Hermes 0.1.0
workflow.

**Release tag:** `0.1.0` (no `v` prefix), to be created only after acceptance.
**Debian package version:** `0.1.0-1`.
