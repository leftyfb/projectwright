# Projectwright

**Requirements-to-Git task orchestration with explicit safety gates and human milestone approval.**

Projectwright turns `requirements.md` and an ordered `queue.md` into bounded planning and agent tasks, validates structured completion reports and Git evidence, and pauses at configured milestones for acceptance. Hermes CLI and its per-user configuration are required for the supported 0.1.0 experience; a command-based adapter is experimental, not a supported replacement. Telegram approval is expected and offered during first-run setup when Hermes Telegram settings are detected, but enabling it is optional and requires confirmation. Home Assistant quota telemetry, notes mirroring and user-level project dispatch timers are optional integrations.

> **Release status:** `0.1.0` is published as a [GitHub Release](https://github.com/leftyfb/projectwright/releases/tag/0.1.0) with a tested Debian artifact for Ubuntu 24.04 and 26.04. It is an early release: install in a non-production environment first. A signed APT feed is **not yet available**; until then, installation and upgrades require the downloadable `.deb`. No install step automatically alters Hermes credentials, project files, plugins, or timers.

## Start here

| If you want to… | Read |
|---|---|
| Understand how it works and run a safe first project | **[Full user and operator manual](docs/manual.md)** |
| See the role of **every source, packaging, workflow and test file** | **[Current file-by-file reference](docs/file-reference.md)** |
| Install or inspect the Debian release, plan upgrades/uninstalls | **[Packaging and operations](docs/packaging-and-operations.md)** |
| Follow requirements → planning → work → Git → human acceptance | [Workflow](docs/workflow.md) |
| Find CLI commands and options | [CLI reference](docs/cli.md) |
| Understand project roots, XDG paths, defaults and config-free mode | [Configuration guide](docs/configuration-home.md) |
| Configure Hermes or experimental non-Hermes execution | [Provider adapters](docs/provider-adapters.md) |
| Set up per-user Telegram approval and systemd | [Approval setup](docs/user-approval-setup.md) |
| See precisely what has passed or is still blocked | [Release acceptance checklist](docs/release-checklist.md) |
| Understand tests and what they do **not** prove | [Coverage matrix](docs/test-coverage-matrix.md) and [E2E gaps](docs/e2e-test-gaps.md) |

## In one minute

```text
requirements.md -> planner -> queue.md -> dispatcher/manager gates
                                          |
                                    one worker task
                                          |
                              provider report + Git checks
                                          |
                          queue/progress or recovery hold
                                          |
                       milestone acceptance (optional Telegram)
                                          |
                             verified receipt -> next work
```

`pw status` inspects a project; `pw plan` can request new queue items; `pw tick` plans when allowed and executes at most one task; `pw worker` runs a single task; `pw notify` previews approval requests (only `--send` transmits). A configured agent can change the selected Git worktree; always test against disposable data first. For the exact safeguards and execution types, see the [manual](docs/manual.md).

## Install the 0.1.0 Debian release

Download `projectwright_0.1.0-1_all.deb` and `SHA256SUMS` from [the 0.1.0 release](https://github.com/leftyfb/projectwright/releases/tag/0.1.0) into the same directory. Verify the download, then install it:

```sh
sha256sum -c SHA256SUMS
sudo apt install ./projectwright_0.1.0-1_all.deb
pw setup
```

Run `pw setup` as your ordinary Hermes user (not via `sudo`). An APT repository for automatic updates is planned but **not yet deployed**. Hermes CLI and a configured Hermes account are required for supported use; Telegram setup is offered with confirmation when detected.

## Inspect and test the development source

For source development, requires Python 3.10+ and Git. The **supported Debian installation targets are Ubuntu 24.04 LTS and 26.04 LTS only** (22.04 is not supported). From the repository root:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B scripts/validate-baseline.py --mode development
```

After installing the Debian package, run **`pw setup` as your ordinary Hermes user** to verify Hermes plugin discovery with a bounded read-only CLI command and optionally activate detected Telegram approval integration. The command explains changes and asks before enabling the plugin or approval notifier timer; use `pw setup --no-telegram` to defer Telegram. A gateway restart remains a separate manual step.

Read-only CLI exploration in an environment where Projectwright is installed:

```sh
pw --help
pw defaults --project demo
pw status --project demo
```

To create an inert private project, `pw init --project demo` disables execution by default. To create only a queue/work-log skeleton without `config.json`, use `pw init --project demo --no-config`; then you must separately prepare a Git worktree and valid queue before manual execution. Projectwright does not provision a model, Git repository, Telegram bot or systemd schedule for you.

## Repository orientation

- `src/projectwright/pw_*.py` — current runtime and integration implementations.
- `src/projectwright/project_*.py` — retained legacy compatibility imports.
- `packaging/`, `pyproject.toml`, `scripts/build-deb.sh` — build and inert installation assets.
- `tests/` — offline unit, integration, acceptance, recovery and migration regressions.
- `.github/workflows/` — hosted offline CI and guarded release publishing. Historical isolated LXD testing is archived in Git history; do not reconnect a self-hosted runner without a new security review.
- `docs/` — operating manual, reference, acceptance evidence and historical audit records.

The older [component inventory](docs/component-inventory.md), [architecture snapshot](docs/architecture-current.md) and [runtime entrypoint snapshot](docs/runtime-entrypoints.md) describe the original 18-file audit; consult the **current file reference** for the newer canonical modules and branch behavior.

## Safety and current status

The isolated `disposable-test-container` LXD environment verified Debian install/purge, user timer onboarding, Hermes plugin/gateway loading, Telegram delivery, real Approve and Reject callbacks, receipt verification and cleanup. Hosted tests also passed clean package installation/purge on Ubuntu 24.04 and 26.04, packaged fake-provider READ and EDIT/TEST/COMMIT execution, and a genuine two-source Debian upgrade preserving 35 user-owned files. These checks do **not** establish a stable package, all authorization/recovery edge cases, future schema migrations, a live-model EDIT/TEST/COMMIT run, or production installation. No self-hosted `disposable-test-container` workflow should be triggered while its runner/container is intentionally stopped.

For public contributions, follow [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Before changing repository visibility, complete the [public-release readiness checklist](docs/public-release-readiness.md). The [release checklist](docs/release-checklist.md) preserves historical testing evidence; do not run against production Hermes without explicit authorization.
