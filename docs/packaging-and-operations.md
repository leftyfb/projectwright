# Debian packaging, installation and operations (0.1.0 release candidate)

This page documents the **0.1.0 release candidate**, not an already published release or a production deployment endorsement. Branch: `release/0.1.0`; Python project version `0.1.0`; Debian version `0.1.0-1`. Review [release-checklist.md](release-checklist.md) for current evidence and blockers.

## How the artifact is built

`pyproject.toml` declares a setuptools wheel of flat modules. `scripts/build-deb.sh` installs the built wheel into a Debian staging tree, writes executable wrappers and a `DEBIAN/control` file, adds integration assets, then produces `projectwright_0.1.0-1_all.deb`. The package is `Architecture: all` and declares `python3 (>= 3.10)` and `git`; the project metadata currently lists **no** Python runtime dependencies. Optional Hermes, Telegram and systemd integrations are deliberately configured outside the core package; their external environments and full production combinations are not covered by the Debian dependency declaration.

| Installed location | Responsibility |
|---|---|
| `/usr/bin/pw`, `pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify`, `pw-timer` | CLI wrappers using distribution Python |
| `/usr/lib/python3/dist-packages/` | Projectwright's flat canonical and compatibility modules |
| `/usr/share/projectwright/hermes/projectwright-approvals/` | Inert native Hermes plugin assets |
| `/usr/share/projectwright/systemd/user/` | Inert reference approval notifier unit files |

The Debian package does **not** install per-user secrets, create a configured project, enable timers, enable the Hermes plugin, restart the gateway, or publish an APT repository. The Hermes bridge must preserve the Hermes venv's import precedence and append the Debian module path only as a fallback; a regression test covers the previously observed `cryptography` conflict.

## Dependency audit (2026-10-26)

**Release operating-system support policy:** Ubuntu **24.04 LTS** (distribution Python 3.12) and **26.04 LTS** (distribution Python 3.14) only. Ubuntu 22.04 is explicitly out of scope. This is an OS support promise to validate with clean installs, separate from the wheel's Python >=3.10 syntax/runtime floor. The Debian `Architecture: all` setting describes pure-Python package content; it does not imply testing every Ubuntu release or CPU platform.

A source import audit of all 21 canonical `pw_*.py` modules found that the **core CLI, manager, planner, worker, Git/approval guards, notifier HTTP sender, quota client and notes tools use the Python standard library and local Projectwright modules**. The optional `pw_plugin.py` imports `telegram.ext.CallbackQueryHandler` when registering a callback into the Hermes gateway. The native Hermes adapter bridges to Debian's module directory after preserving the Hermes virtualenv's import precedence.

| Requirement | Debian packaging decision |
|---|---|
| Python 3.10+ | **Required:** declared as `python3 (>= 3.10)`; clean Debian install, CLI smoke and purge passed on Ubuntu 24.04/Python 3.12 and 26.04/Python 3.14 |
| Git CLI | **Required** for normal worktree operations; declared as `git` |
| Python third-party packages for core CLI | **None found in canonical runtime imports**; `dependencies = []` remains correct for the core wheel |
| Hermes executable and user configuration | **Required for supported 0.1.0 use:** separately installed, not declared as a Debian APT dependency; `pw setup` checks Hermes plugin discovery before onboarding |
| `python-telegram-bot` (`telegram.ext`) | **Optional Hermes gateway plugin dependency:** must be supplied compatibly in the gateway environment, not blindly installed into system Python |
| systemd user manager | **Optional scheduling/onboarding integration:** not required for manual CLI execution |
| Home Assistant | **Optional external HTTP service:** quota code uses `urllib`; no HA client package is required |
| Alternative command provider | **Optional local executable:** configured via absolute argv, not a Python package dependency |

The audit is a **source/import contract**. The hosted [Ubuntu LTS matrix 40428244006](https://github.com/leftyfb/projectwright/actions/runs/40428244006) separately verified clean installation, CLI smoke, and purge on both supported releases. The matrix does **not** exercise optional live Hermes/Telegram integrations on both releases; that remains a stable-release compatibility consideration.

## Build and inspect without installing

From a disposable checkout with wheel/build tools already available:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B scripts/validate-baseline.py --mode development
python3 -m pip wheel --no-deps --wheel-dir dist .
bash scripts/build-deb.sh dist/projectwright-0.1.0-py3-none-any.whl dist
```

The wheel filename above follows the current setuptools version; inspect the actual `dist/` wheel name before running the script. The build script requires exactly a wheel path and output directory; inspect it and `dpkg-deb --info`, `dpkg-deb --contents` and the resulting SHA-256 before any privileged operation. Prefer the exact GitHub-hosted, tested artifact over rebuilding with an unknown environment. Do not assume future versions provide automatic migration or rollback across unknown state-schema changes.

A safe metadata-only inspection is:

```sh
dpkg-deb --info /absolute/path/projectwright_0.1.0-1_all.deb
dpkg-deb --contents /absolute/path/projectwright_0.1.0-1_all.deb
sha256sum /absolute/path/projectwright_0.1.0-1_all.deb
```

## Explicit isolated install lifecycle

A package was installed, reinstalled and purged successfully in the dedicated `pw-test` LXD container (Actions run [40244321910](https://github.com/leftyfb/projectwright/actions/runs/40244321910)). An earlier synthetic lower Debian revision was upgraded and purged ([40244873728](https://github.com/leftyfb/projectwright/actions/runs/40244873728)); more importantly, a [genuine distinct-source upgrade 40427522957](https://github.com/leftyfb/projectwright/actions/runs/40427522957) then preserved the content hashes and permission modes of 35 disposable user-owned files through upgrade and purge. This does not guarantee future schema migration or downgrade behavior. Per-user timer onboarding, Hermes native plugin registration, gateway plugin loading, a real outbound Telegram request and a real inbound Approve callback were subsequently verified in that disposable environment. The cleanup run [40258658872](https://github.com/leftyfb/projectwright/actions/runs/40258658872) removed the test assets and preserved Hermes credentials.

The guarded `scripts/pw-test-deb-lifecycle.sh` intentionally demands root **inside the exact disposable LXD container**, refuses pre-existing Projectwright package/path state and obvious host mount hazards, and purges in an EXIT trap. **Do not run it on the `tux` host or an existing Hermes installation.** Its cleanup is designed for a temporary empty fixture; it is not a general-purpose production uninstaller.

No further `pw-test` self-hosted workflow should run while its container/runner is stopped. Do not start that container, elevate actions, install packages, send real Telegram messages or restart a gateway without explicit authorization.

## Per-user onboarding is separate from dpkg

The administrator installs a package for the OS; only the **intended ordinary user** can decide which Hermes account, bot, projects and systemd user manager to integrate. After installing the `.deb`, the **required Hermes user** runs the standard first-run check:

```sh
pw setup
```

This checks for a Hermes executable and `~/.hermes/` configuration directory, then runs a bounded read-only Hermes plugin-discovery command. It examines existing Telegram bot credentials and an authorized numeric user list without printing secrets. If both exist, it explains the plugin/timer changes and asks for confirmation (default No) before activating them. If Telegram is missing, setup explains how to configure it and leaves approvals disabled. `pw setup --no-telegram` deliberately defers integration; `pw setup --yes` is an explicit opt-in for unattended setup. The older `pw setup-user` and `pw-timer setup-user --enable-hermes-plugin` remain compatibility/advanced routes. Setup refuses root and conflicting or symlinked targets. A Hermes gateway restart/reload may separately be required for callback registration; setup does **not** do that automatically.

To disable the approval timer:

```sh
systemctl --user disable --now projectwright-approval-notify.timer
```

Plugin disabling, gateway reload and removal of user-owned unit files require a separately reviewed account-specific procedure. A package purge does not imply user secrets, projects, generated units or Git worktrees should be deleted.

## Upgrade, backup, removal and rollback principles

1. **Before upgrade:** record package version and SHA-256, `pw --help`, user unit/plugin state, selected configuration root, Git branch/HEAD, queue, work log, journals, recovery incidents, receipts and any custom paths. Back up user project directories and existing Hermes plugin/unit configuration by an explicit, privacy-preserving method. Never include bot tokens in CI logs.
2. **For an upgrade:** compare the two *real* package source versions and compatibility schemas, then perform a disposable account migration test. The tested historical-to-current source upgrade preserved 35 user-owned files, but future on-disk schema migrations and downgrade behavior still require version-specific validation.
3. **After upgrade:** validate every CLI, effective config resolution, plugin import/discovery, systemd user status, and a disposable Git task/approval loop. Keep scheduled execution disabled until reviewed.
4. **To stop:** disable per-user dispatch and notifier timers first, then stop/review any running job and gateway plugin configuration. Purging the Debian package removes package-owned files, **not** necessarily home-directory integration artifacts.
5. **For rollback:** retain exact older artifact and backups; never roll back across unknown state-schema changes by force. Investigate journals and Git first.

## Known limitations and later hardening work

- Core dependency audit and Ubuntu 24.04/26.04 clean-install matrix **passed**; verify optional Hermes/Telegram and Home Assistant combinations before a stable production support claim.
- Canonical `pw_*` import/entrypoint migration audit and consistent docs, scripts and systemd services.
- Installed entrypoint and config-free CLI checks **passed** in both supported Ubuntu containers; extended per-user onboarding/`pw setup-user` remains a separate live integration check.
- Deterministic per-user integration install/update/disable/uninstall workflow with existing-modification and symlink protection.
- True cross-source-version upgrade and 35-file preservation **passed** for the tested pair; document a downgrade/rollback policy and retest any future migrations.
- XDG config/state/cache convergence, provider-neutral execution/notification contract, and live isolated EDIT/TEST/COMMIT workflow.
- Live Approve and Reject **passed** in isolation; complete security review and remaining revoked/unauthorized, stale-request and recovery edge cases as warranted for stable production support.
- Install/backup/restore/failure-mode documentation validated against a clean disposable user account.

The release checklist is the authority for marking gates complete, with dated test evidence. Historical setup/development-wheel pages may contain snapshots superseded by later runs.
