# Projectwright final-release acceptance checklist

**Status:** release requirements, not a claim of implementation. No item below is
considered done merely because a development wheel or Debian preview builds.
A production release requires tests, docs, and an install/upgrade test against
a disposable account before a stable tag or deployment.

## Current development handoff (2026-10-24)

**Up-to-date canonical module reference:** [module-naming-current.md](module-naming-current.md). Historical inventories document the original baseline, not the current naming.

- **Repository:** `leftyfb/projectwright`; **working branch:**
  `test/review-followups`. Do not modify `main`, the user's installed
  Hermes environment, or production project data without explicit direction.
- **Last verified CI prior to this documentation update:** GitHub Actions run
  [40108642704](https://github.com/leftyfb/projectwright/actions/runs/40108642704)
  at commit `7af7ff9a319c058a9750453961bb13b767bdf145`
  (successful offline tests, development wheel and Debian preview checks).
- **Naming migration:** `pw_task_worker.py`, `pw_queue_manager.py`,
  `pw_queue_planner.py`, `pw_milestone_guard.py`,
  `pw_telegram_approval.py`, `pw_notes_sync.py` and previously migrated
  `pw_*` utilities are canonical. Legacy `project_*` modules remain as
  compatibility shims; the worker shim aliases the canonical module so
  runtime globals and mocks retain identity. Review *all remaining* mixed
  names, service units and documentation before checking off section 1.
- **Config-free tests:** Missing `config.json` is supported for explicitly
  prepared projects with an existing Git worktree, HEAD commit, queue and work
  log; `requirements.md` enables explicit planning. `pw init --no-config`,
  `pw defaults`, manual worker/dispatcher, READ and EDIT/TEST/COMMIT cycle,
  and milestone acceptance gating have passing disposable tests. This does
  **not** establish live Hermes compatibility, all CLI combinations, or a
  production release.
- **Next priorities:** (1) finalize per-user setup hardening and disposable
  Debian install/upgrade/uninstall coverage (symlink refusal now has tests);
  (2) final naming/reference audit and file-by-file
  workflow documentation; (3) Hermes approval plugin registration,
  systemd timer and Telegram callback tests under a disposable account;
  (4) harness-neutral provider contract and a live, isolated Hermes
  end-to-end run; (5) release/security and migration verification.
- **Method:** Continue implementation on this branch, use compatibility
  adapters where needed, run GitHub Actions, and fix failures before marking
  each acceptance gate complete. Update this handoff and checkboxes as work
  is verified; no deploy/merge without user direction.

## Container-based installation test status (2026-10-25)

- The user has provisioned an **LXD container named `pw-test` on `tux`**
  with the ordinary account `ubuntu`.
- Hermes reported successful read-only SSH connectivity (`ssh ... pw-test true`,
  exit code 0). This confirms reachability only, **not** installed software,
  container isolation, plugin registration, or package lifecycle behavior.
- A repository-owned read-only verifier, `scripts/preflight-pw-test.py`,
  now checks the explicit `ubuntu@pw-test` target, ordinary user identity,
  container virtualization and available systemd indicators. Its test suite
  stubs SSH; no remote test was executed from this ChatGPT session.
- **Live preflight passed (user-run on tux, 2026-10-25):** SSH returned `user=ubuntu`, `uid=1000`, `hostname=pw-test`, `virt=lxc`, `os=ubuntu`, and `systemd=running`. No remote modifications were reported. The original parser also included unwanted shell environment fields; this has been corrected in the script and tested.
- Next: review the preflight evidence, then explicitly authorize a contained install test;
  review results before allowing any write, package installation, or
  user-timer changes. Never install into `tux` itself.

## Dedicated pw-test Actions runner (2026-10-25)

- User reports runner **`pw-test-projectwright`** installed and running
  **in the foreground** inside LXD `pw-test` as the `ubuntu` account.
  Registration and required label have now been verified by GitHub Actions
  [40240865792](https://github.com/leftyfb/projectwright/actions/runs/40240865792),
  which completed **successfully** on the container.
- Added `.github/workflows/pw-test-preflight.yml`: a deliberately triggered,
  read-only job with a required `projectwright-lxd-install` runner label,
  exact runner-name/host/user/container checks, and no sudo or package writes.
  The required custom runner label is working.
- A push trigger limited to changes to `.github/pw-test-preflight-trigger.txt`
  on `test/review-followups` enables execution without changing `main`.
  `workflow_dispatch` remains available once GitHub's default-branch
  registration requirement is met. Initial push-trigger run **passed**.
- Running in the foreground is sufficient for initial testing; if that
  process stops, queued jobs cannot begin. System-wide Debian installation
  and removal testing is still unapproved and **not** part of this preflight.
- Next: verify the runner label and successful manual preflight, then
  separately design controlled Debian install/upgrade/uninstall jobs and
  confirm that `pw-test` has no sensitive host bind mounts or privileges.

## 1. Consistent filenames, modules, and commands

- [x] Select one canonical internal naming scheme. The unified `pw`
  CLI now routes canonical implementations; `pw_*` is standard, with legacy shims documented in [module-naming-current.md](module-naming-current.md). Initially seven canonical modules had shims and tests:
  `pw_worker_progress.py`, `pw_milestone_sequence.py`,
  `pw_acceptance_gate.py`, `pw_quota.py`, `pw_recovery.py`,
  `pw_worker_journal.py`, and `pw_notes_publisher.py`. **Proposed:** `pw_*.py` for
  the existing flat Python scripts, `projectwright` for the installable package
  namespace, and `pw` for the primary CLI. Retain `project_*.py` only as documented compatibility modules pending an upgrade/deprecation policy.
- [ ] Refactor all internal imports, subprocess entrypoints, plugin registration,
  timer units, packaging manifests and fixtures in one versioned migration.
- [x] Provide explicitly documented compatibility wrappers/aliases for existing
  Hermes project scripts during migration; see [module-naming-current.md](module-naming-current.md). Retirement by policy remains an open release decision.
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
- [ ] Work **without `config.json`**: shared built-in defaults and a
  prepared-worktree manual `pw worker` / `pw tick` path are implemented,
  alongside `pw init --no-config` and read-only `pw defaults` preflight.
  Disposable READ, EDIT/TEST/COMMIT and milestone-gating tests now pass without
  a JSON file. Remaining: live-provider and install tests, full CLI combinations,
  and positive/negative unattended authorization proofs.
- [ ] Preserve explicit project-specific overrides and provide migration from
  existing `~/.hermes/projects` configurations without overwriting files.
- [ ] Fail closed when a required credential or authorizing policy is missing;
  do not silently invent a Telegram recipient or approve a milestone.

## 4. Harness-independent execution

- [ ] Complete a versioned provider interface covering planning, execution,
  health checks, result envelopes, timeouts and cancellation. A first validated
  `command` argv/stdin adapter exists for planning and tasks, alongside Hermes.
- [ ] Keep Hermes as one adapter; select a different provider via configuration
  or CLI, without source changes or forced legacy model IDs.
- [ ] Fully validate a non-Hermes provider across EDIT/TEST/COMMIT and approval.
  The current disposable command provider passes unit tests and a READ
  subprocess chain; task/journal/Git checks remain in the shared worker.
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

- [ ] Verify **live discovery and registration** of the packaged Hermes
  `projectwright-approvals` plugin. The Debian preview now includes a native
  `plugin.yaml` and `__init__.py` in
  `/usr/share/projectwright/hermes/projectwright-approvals/`, plus inert timer
  templates under `/usr/share/projectwright/systemd/user/`. The per-user
  setup installs these manifest/entrypoint files with conflict protection
  before running `hermes plugins enable`; actual gateway reload and callback
  delivery still require an isolated live installation test.
- [ ] Complete per-user Hermes plugin onboarding. An explicit
  `pw setup-user --enable-hermes-plugin` implementation now runs
  `hermes plugins enable projectwright-approvals` under the selected non-root
  account, but packaging/registration of the plugin itself is outstanding.
- [x] **Per-user command implementation:** `pw setup-user` generates
  `~/.config/systemd/user/projectwright-approval-notify.*`, runs
  `systemctl --user daemon-reload`, and enables/starts the user timer.
  Config and non-root checks are enforced; symlinked units and plugin files
  are refused (disposable regression tests). Changes are idempotent;
  installed-service/live-operation tests remain outside the offline suite.
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
