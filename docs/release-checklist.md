# Projectwright final-release acceptance checklist

**Status:** release requirements, not a claim of implementation. No item below is
considered done merely because a development wheel or Debian preview builds.
A production release requires tests, docs, and an install/upgrade test against
a disposable account before a stable tag or deployment.

## 1. Consistent filenames, modules, and commands

- [ ] Select one canonical internal naming scheme. **Proposed:** `pw_*.py` for
  the existing flat Python scripts, `projectwright` for the installable package
  namespace, and `pw` for the primary CLI. Remove mixed `project_*.py` names.
- [ ] Refactor all internal imports, subprocess entrypoints, plugin registration,
  timer units, packaging manifests and fixtures in one versioned migration.
- [ ] Provide explicitly documented compatibility wrappers/aliases for existing
  Hermes project scripts during migration, then retire them by policy.
- [ ] Test all entrypoints in a freshly installed wheel and Debian package,
  including cross-module imports and absent legacy script paths.

## 2. Complete documentation

- [ ] Overview, purpose and lifecycle of **every shipped file**, grouped into
  CLI, runtime, state, providers, approvals, notification, package and units.
- [ ] Workflow from requirements -> planning -> queue -> READ/EDIT/TEST/COMMIT
  -> verification -> milestone approval/rejection -> follow-on planning.
- [ ] Config reference with defaults, environment variables, command-line
  precedence, paths, privacy/security boundaries and example profiles.
- [ ] Install, upgrade, uninstall, backup, restore, recovery, failure modes,
  systemd units, and Telegram setup/authorization instructions.
- [ ] Provider API/adapter contract and a worked non-Hermes backend example.

## 3. XDG-compatible local configuration and defaults

- [x] **Initial project-root resolver:** defaults to
  `$XDG_CONFIG_HOME/projectwright/projects` or `~/.config/projectwright/projects`,
  with a legacy-root fallback. Remaining components still require migration.
- [ ] Expand explicit `--config-dir` support beyond dispatcher; current
  dispatcher supports it and `PROJECTWRIGHT_CONFIG_DIR` is recognized by its
  manager and worker subprocesses. Precedence: dispatcher CLI argument >
  `PROJECTWRIGHT_CONFIG_DIR` > legacy `HERMES_PROJECT_CONFIG_DIR` > XDG default.
  This is partial until all entry points and utilities share one resolver.
- [ ] Keep state, cache, log and project-root locations separate, with
  documented overrides (prefer XDG state/cache conventions).
- [ ] Work **without `config.json`**: validated built-in defaults for every
  optional setting; defaults must never implicitly enable unsafe execution,
  unattended Git commits, external messaging or timers.
- [ ] Preserve explicit project-specific overrides and provide migration from
  existing `~/.hermes/projects` configurations without overwriting files.
- [ ] Fail closed when a required credential or authorizing policy is missing;
  do not silently invent a Telegram recipient or approve a milestone.

## 4. Harness-independent execution

- [ ] Define a provider interface for planning, task execution, health checks,
  result envelopes, timeouts and cancellation.
- [ ] Keep Hermes as one adapter; select a different provider via configuration
  or CLI, without source changes or forced legacy model IDs.
- [ ] Implement and test at least one non-Hermes provider with equal task and
  journal validation. Providers must not bypass approval, scope or Git checks.
- [ ] Provider-specific dependencies and secrets remain outside core state.

## 5. Telegram approval experience

- [ ] Deliver milestone requests with Telegram inline **Approve / Reject**
  buttons. The button callback, not free-form chat parsing, is authoritative.
- [ ] Authorize users dynamically against the configured allow-list and private
  chats; stale, replayed, altered, revoked and rejected requests fail closed.
- [ ] Run acceptance checks against current policy, queue and Git evidence
  under the project lock before producing an approval receipt.
- [ ] Provide review context (project, requirement/milestone, commit, scope,
  task summary and how to inspect the diff) in the Telegram UI.
- [ ] Preserve pending requests for review on errors, record rejections durably,
  and document duplicate/at-least-once delivery limitations.
- [ ] Add disposable integration tests for callback, notifier, timeout,
  concurrent changes, and recipient revocation. Live Telegram acceptance
  is a separate explicitly opted-in test.

## 6. Debian installation and optional user integration

- [ ] Ship a packaged Hermes plugin named `projectwright-approvals` and a
  `projectwright-approval-notify.service` plus `.timer`.
- [ ] During **explicit per-user onboarding**, run
  `hermes plugins enable projectwright-approvals` as the intended non-root
  account, without replacing the user's Hermes/provider configuration.
- [ ] During that same per-user setup, create
  `~/.config/systemd/user`, install the shipped notify units, run
  `systemctl --user daemon-reload`, then
  `systemctl --user enable --now projectwright-approval-notify.timer`.
- [ ] The requested setup should happen as part of the Debian installation
  **only when the target user is unambiguously selected and user-session
  systemd/Hermes are available**. A Debian `postinst` runs as root and cannot
  safely guess the interactive desktop user or reliable `systemctl --user`
  bus. Design an idempotent `pw setup-user` command and a package-triggered,
  explicitly approved per-user setup flow, with deferred completion when no
  user session is available.
- [ ] Support a no-Hermes installation mode; do not require enabling Hermes
  when an alternate provider or approval channel is selected.
- [ ] Confirm timer and plugin enablement after setup; ensure retries,
  upgrades, removals and user-selected opt-out behave predictably.
- [ ] Debian control lists all runtime dependencies actually needed; verify
  package installs/removes cleanly in a disposable Ubuntu user/container.
- [ ] Publish signed, versioned .deb artifacts through GitHub Actions and an
  authenticated, documented APT repository; do not publish development
  previews to a stable channel.

## Release gate

- [ ] End-to-end tests cover the default configuration, custom paths,
  Hermes and alternate provider, Telegram approvals, recovery, and full
  EDIT -> TEST -> COMMIT -> approval behavior.
- [ ] Install/upgrade/uninstall verified with no modification of a real
  `~/.hermes` installation, even when an older legacy layout exists.
- [ ] All CI green; audit security-sensitive defaults and secrets handling.
- [ ] Stable version, changelog, migration guide, supported environments and
  release artifacts complete.

## Existing evidence (not a release sign-off)

The development branch already has offline callback/guard tests, a working
source-checkout runner on `tux`, a development wheel and a Debian preview.
The flat module names, default `~/.hermes` assumptions and Telegram/Hermes
coupling are **not** yet fully migrated, and no live install lifecycle has
been tested. See `docs/e2e-test-gaps.md` and `docs/development-wheel.md`.
