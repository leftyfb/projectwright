# Debian packaging, installation and operations (development)

This page documents the **current preview**, not a production installation endorsement. Branch: `test/review-followups`; Python project version `0.1.0.dev0`; generated Debian revision `0.1.0~dev0-1`. Review [release-checklist.md](release-checklist.md) for current evidence and blockers.

## How the artifact is built

`pyproject.toml` declares a setuptools wheel of flat modules. `scripts/build-deb.sh` installs the built wheel into a Debian staging tree, writes executable wrappers and a `DEBIAN/control` file, adds integration assets, then produces `projectwright_0.1.0~dev0-1_all.deb`. The package is `Architecture: all` and declares `python3 (>= 3.10)` and `git`; the project metadata currently lists **no** Python runtime dependencies. This declaration is incomplete for every optional live integration and supported platform combination.

| Installed location | Responsibility |
|---|---|
| `/usr/bin/pw`, `pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify`, `pw-timer` | CLI wrappers using distribution Python |
| `/usr/lib/python3/dist-packages/` | Projectwright's flat canonical and compatibility modules |
| `/usr/share/projectwright/hermes/projectwright-approvals/` | Inert native Hermes plugin assets |
| `/usr/share/projectwright/systemd/user/` | Inert reference approval notifier unit files |

The Debian package does **not** install per-user secrets, create a configured project, enable timers, enable the Hermes plugin, restart the gateway, or publish an APT repository. The Hermes bridge must preserve the Hermes venv's import precedence and append the Debian module path only as a fallback; a regression test covers the previously observed `cryptography` conflict.

## Dependency audit (2026-10-26)

A source import audit of all 21 canonical `pw_*.py` modules found that the **core CLI, manager, planner, worker, Git/approval guards, notifier HTTP sender, quota client and notes tools use the Python standard library and local Projectwright modules**. The optional `pw_plugin.py` imports `telegram.ext.CallbackQueryHandler` when registering a callback into the Hermes gateway. The native Hermes adapter bridges to Debian's module directory after preserving the Hermes virtualenv's import precedence.

| Requirement | Debian packaging decision |
|---|---|
| Python 3.10+ | **Required:** declared as `python3 (>= 3.10)`; supported Ubuntu versions still need a distribution-level clean-install matrix |
| Git CLI | **Required** for normal worktree operations; declared as `git` |
| Python third-party packages for core CLI | **None found in canonical runtime imports**; `dependencies = []` remains correct for the core wheel |
| Hermes executable/model service | **Optional integration:** not a Debian dependency; required when `provider.type=hermes` is selected |
| `python-telegram-bot` (`telegram.ext`) | **Optional Hermes gateway plugin dependency:** must be supplied compatibly in the gateway environment, not blindly installed into system Python |
| systemd user manager | **Optional scheduling/onboarding integration:** not required for manual CLI execution |
| Home Assistant | **Optional external HTTP service:** quota code uses `urllib`; no HA client package is required |
| Alternative command provider | **Optional local executable:** configured via absolute argv, not a Python package dependency |

The audit is a **source/import contract**, not yet a verified clean install on every supported Ubuntu release. The earlier guarded LXD install/purge run proves the package works on that one Ubuntu container only. The release should declare the support matrix and verify optional Hermes/Telegram compatibility on the chosen target versions before a stable tag.

## Build and inspect without installing

From a disposable checkout with wheel/build tools already available:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B scripts/validate-baseline.py --mode development
python3 -m pip wheel --no-deps --wheel-dir dist .
bash scripts/build-deb.sh dist/projectwright-0.1.0.dev0-py3-none-any.whl dist
```

The wheel filename above follows the current setuptools version; inspect the actual `dist/` wheel name before running the script. The build script requires exactly a wheel path and output directory; inspect it and `dpkg-deb --info`, `dpkg-deb --contents` and the resulting SHA-256 before any privileged operation. Prefer the exact GitHub-hosted, tested artifact over rebuilding with an unknown environment. Never assume a `~dev0` package has a stable migration promise.

A safe metadata-only inspection is:

```sh
dpkg-deb --info /absolute/path/projectwright_0.1.0~dev0-1_all.deb
dpkg-deb --contents /absolute/path/projectwright_0.1.0~dev0-1_all.deb
sha256sum /absolute/path/projectwright_0.1.0~dev0-1_all.deb
```

## Explicit isolated install lifecycle

A package was installed, reinstalled and purged successfully in the dedicated `pw-test` LXD container (Actions run [40244321910](https://github.com/leftyfb/projectwright/actions/runs/40244321910)). A synthetic lower Debian revision was upgraded and purged ([40244873728](https://github.com/leftyfb/projectwright/actions/runs/40244873728)); **it was not built from genuinely older Projectwright source**. Per-user timer onboarding, Hermes native plugin registration, gateway plugin loading, a real outbound Telegram request and a real inbound Approve callback were subsequently verified in that disposable environment. The cleanup run [40258658872](https://github.com/leftyfb/projectwright/actions/runs/40258658872) removed the test assets and preserved Hermes credentials.

The guarded `scripts/pw-test-deb-lifecycle.sh` intentionally demands root **inside the exact disposable LXD container**, refuses pre-existing Projectwright package/path state and obvious host mount hazards, and purges in an EXIT trap. **Do not run it on the `tux` host or an existing Hermes installation.** Its cleanup is designed for a temporary empty fixture; it is not a general-purpose production uninstaller.

No further `pw-test` self-hosted workflow should run while its container/runner is stopped. Do not start that container, elevate actions, install packages, send real Telegram messages or restart a gateway without explicit authorization.

## Per-user onboarding is separate from dpkg

The administrator installs a package for the OS; only the **intended ordinary user** can decide which Hermes account, bot, projects and systemd user manager to integrate. After inspecting their `~/.hermes/.env`, existing plugin and user units, the explicit action is:

```sh
pw-timer setup-user --minutes 10 --enable-hermes-plugin
```

This can install matching user units, enable/start the approval notifier timer and enable the native Hermes plugin. It refuses root and conflicting/symlinked targets. A Hermes gateway restart/reload may be separately required for callback registration. This is an operational change, **not** a dry-run. The unified `pw setup-user` action forwarding was corrected on this development branch; previously built preview artifacts may still require the direct `pw-timer setup-user` form.

To disable the approval timer:

```sh
systemctl --user disable --now projectwright-approval-notify.timer
```

Plugin disabling, gateway reload and removal of user-owned unit files require a separately reviewed account-specific procedure. A package purge does not imply user secrets, projects, generated units or Git worktrees should be deleted.

## Upgrade, backup, removal and rollback principles

1. **Before upgrade:** record package version and SHA-256, `pw --help`, user unit/plugin state, selected configuration root, Git branch/HEAD, queue, work log, journals, recovery incidents, receipts and any custom paths. Back up user project directories and existing Hermes plugin/unit configuration by an explicit, privacy-preserving method. Never include bot tokens in CI logs.
2. **For an upgrade:** compare the two *real* package source versions and compatibility schemas, then perform a disposable account migration test. Synthetic Debian-revision reinstallation does not cover on-disk schema migration or preservation of old user state.
3. **After upgrade:** validate every CLI, effective config resolution, plugin import/discovery, systemd user status, and a disposable Git task/approval loop. Keep scheduled execution disabled until reviewed.
4. **To stop:** disable per-user dispatch and notifier timers first, then stop/review any running job and gateway plugin configuration. Purging the Debian package removes package-owned files, **not** necessarily home-directory integration artifacts.
5. **For rollback:** retain exact older artifact and backups; never roll back across unknown state-schema changes by force. Investigate journals and Git first.

## Known blockers before calling this a proper release

- Complete dependency and supported distribution/Python matrix, including Telegram/Hermes bridge and optional Home Assistant.
- Canonical `pw_*` import/entrypoint migration audit and consistent docs, scripts and systemd services.
- All installed entrypoints tested in a clean environment without source checkout/legacy script path; verify `pw setup-user` forwarding.
- Deterministic per-user integration install/update/disable/uninstall workflow with existing-modification and symlink protection.
- True cross-source-version upgrade, preserved user configuration/state, downgrade/rollback and purge policy.
- XDG config/state/cache convergence, provider-neutral execution/notification contract, and live isolated EDIT/TEST/COMMIT workflow.
- Rejection, revoked/unauthorized user, stale request and recovery cases under appropriately isolated live conditions, followed by security review.
- Install/backup/restore/failure-mode documentation validated against a clean disposable user account.

The release checklist is the authority for marking gates complete, with dated test evidence. Historical setup/development-wheel pages may contain snapshots superseded by later runs.
