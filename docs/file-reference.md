# File-by-file guide (current development branch)

This is the **current canonical source and repository map**, not the historical 18-file baseline. It covers every tracked runtime Python module and the surrounding packaging, CI and documentation surfaces. Source lives under `src/projectwright/` as flat installed modules; no `src/projectwright/__init__.py` package namespace is installed yet.

## Canonical runtime modules

| File | Responsibility; principal caller/side effect |
|---|---|
| `pw_dispatch.py` | Unified `pw` command router and bounded `pw tick` dispatcher. Runs manager and worker as subprocesses; validates manager JSON and exit code; enforces a narrow active Git-cycle continuation check. |
| `pw_config.py` | Shared optional-config loader, project paths/default values and prepared config-free worktree readiness. Used by runtime and inspect commands. |
| `pw_defaults.py` | Read-only `pw defaults` introspection of selected root, configured flag and effective defaults. |
| `pw_init.py` | `pw init` creates an inert private project or `--no-config` queue/work-log skeleton; refuses overwrites/symlinks. |
| `pw_queue_manager.py` | `pw-manager`, `pw status`, `pw plan`; lock, queue parsing, policy, Git, journal/recovery, quota and milestone gating. Invokes planner when authorized; returns machine-readable decision and exit status. |
| `pw_queue_planner.py` | Builds a bounded provider planning request, validates structured proposal and concurrent evidence, appends eligible queue tasks and planning state; optional notes synchronization. |
| `pw_task_worker.py` | `pw-worker`; selects one task, invokes provider, records result/journal, enforces Git cycle scopes and queue identity, handles notes/progress and safe recovery holds. Can intentionally change project worktree. |
| `pw_worker_journal.py` | Atomic persistent lifecycle journal for in-flight/last completed tasks; prevents silent duplicate execution after failures. |
| `pw_worker_progress.py` | Atomic `worker_state.json` progress read/write helper consumed by worker/notes. |
| `pw_recovery.py` | Recovery inspector and explicit incident recorder. Reads Git/journal evidence; does not automatically reset repo or approve retries. |
| `pw_milestone_sequence.py` | Strict ordered milestone policy; determines whether previous scoped milestones and receipts permit progression. |
| `pw_acceptance_gate.py` | Holds queue replanning/execution at required human acceptance boundary. |
| `pw_milestone_guard.py` | Validates pinned requirements, task and Git scope, configured acceptance command and receipt freshness; writes verified acceptance receipt. Also offers a direct guarded CLI. |
| `pw_quota.py` | Optional read-only Home Assistant quota sensor evaluation; can fail closed on unavailable required telemetry. |
| `pw_telegram_approval.py` | Local pending approval scanner and pinned evidence state, stale-request and replay defenses; does not itself send network messages. |
| `pw_buttons.py` | Telegram callback data generation, message text and approve/reject routing; invokes bridge and guard after checks. |
| `pw_notify.py` | `pw-notify`, `pw notify`: approval scan/deduplication and direct Bot API send only with `--send`; records delivery/rejection state. |
| `pw_plugin.py` | Hermes gateway callback-handler factory; restricts callbacks to authorized users/private chat and loads Telegram handler registration. |
| `pw_project_timer.py` | `pw-timer`, `pw timer`; per-project systemd user timer lifecycle and explicit per-user approval notifier/plugin onboarding. |
| `pw_notes_publisher.py` | Optional project progress-note publishing from worker journal/progress state. |
| `pw_notes_sync.py` | Optional conflict-aware notes mirror initialization, status and publish; records hash/manifest evidence. |

## Compatibility modules

Each `project_*.py` file below exists to preserve older import/script consumers during the naming migration. New integrations should use the corresponding `pw_*.py` implementation; do not delete shims until an upgrade and compatibility policy is established.

| Legacy file | Canonical implementation |
|---|---|
| `project_acceptance_gate.py` | `pw_acceptance_gate.py` |
| `project_milestone_guard.py` | `pw_milestone_guard.py` |
| `project_milestone_sequence.py` | `pw_milestone_sequence.py` |
| `project_notes_publisher.py` | `pw_notes_publisher.py` |
| `project_notes_sync.py` | `pw_notes_sync.py` |
| `project_queue_manager.py` | `pw_queue_manager.py` |
| `project_queue_planner.py` | `pw_queue_planner.py` |
| `project_quota.py` | `pw_quota.py` |
| `project_recovery.py` | `pw_recovery.py` |
| `project_task_worker.py` | `pw_task_worker.py` (aliases the **same module object** for mutable global/mock compatibility) |
| `project_telegram_approval.py` | `pw_telegram_approval.py` |
| `project_worker_journal.py` | `pw_worker_journal.py` |
| `project_worker_progress.py` | `pw_worker_progress.py` |

## Package and integration assets

| File | Function |
|---|---|
| `pyproject.toml` | setuptools wheel metadata, flat module list and six installed console scripts. Empty Python dependency list is a **known incomplete runtime declaration**. |
| `scripts/build-deb.sh` | Builds staging tree and Debian preview package from a wheel; installs wrappers, systemd templates, Hermes plugin assets and control metadata. |
| `packaging/hermes-plugin/projectwright-approvals/plugin.yaml` | Hermes native plugin declaration. |
| `packaging/hermes-plugin/projectwright-approvals/__init__.py` | Native plugin bridge; makes installed Debian modules discoverable in Hermes's virtual environment without taking precedence over Hermes dependencies. |
| `installed-source-manifest.json` | Immutable original 18-file source baseline; not a current canonical-module manifest. |
| `scripts/validate-baseline.py` | Baseline-vs-development source, import, syntax, dependency and offline-suite validator. |
| `scripts/preflight-pw-test.py` | Read-only SSH/container identity/systemd preflight with explicit `ubuntu@pw-test` target. |
| `scripts/pw-test-deb-lifecycle.sh` | Guarded root-only test-container dpkg install/reinstall/purge harness with cleanup trap. Never use on `tux` or production. |
| `scripts/pw-test-user-onboarding.sh` | Disposable installed package/user timer onboarding test harness and cleanup. |
| `scripts/pw-test-hermes-plugin.sh` | Disposable native Hermes plugin registration/doctor lifecycle and cleanup. |
| `scripts/pw-test-hermes-gateway.sh` | Isolated Hermes gateway plugin load/restart and restoration test harness. |
| `scripts/pw-test-hermes-callback.py` | Stub callback-handler registration/dispatch probe against installed bridge. |
| `scripts/pw-test-live-approval.py` | Disposable Git milestone fixture and real acceptance/callback test support. |

## CI and test files

| Path | Role |
|---|---|
| `.github/workflows/offline-tests.yml` | Hosted offline unit/integration/recovery/acceptance suite, validators, wheel and Debian preview smoke/artifacts. |
| `.github/workflows/tux-isolated.yml` | Manually triggered unprivileged source-based verification runner on `tux`; not production deployment. |
| `.github/workflows/pw-test-preflight.yml` | Dedicated LXD runner read-only identity and safety checks; ordinary preflight must not send Telegram. |
| `.github/workflows/pw-test-deb-staging.yml` | Container-scoped artifact staging/inspection and separately guarded package lifecycle fixtures. |
| `.github/workflows/pw-test-live-approval.yml` | Explicitly gated disposable project/gateway preparation for live Telegram approval. |
| `.github/workflows/pw-test-send-approval.yml` | Deliberate live actionable Telegram test-message send, not routine CI. |
| `.github/workflows/pw-test-verify-approval.yml` | Read-only inspection of callback receipt or rejection evidence. |
| `.github/workflows/pw-test-live-cleanup.yml` | Explicit cleanup of disposable Projectwright package, plugin, gateway override and Git fixture; credentials preserved. |
| `.github/pw-test-*-trigger.txt` | Branch-scoped, intentionally edited trigger files for workflows that cannot yet be manually dispatched from non-default branch. Editing one can trigger container work. |
| `tests/unit/` | Deterministic policy, quota, sequencing and validator tests. |
| `tests/integration/` | Mock/fake-provider dispatcher, manager, worker, delivery and Git lifecycle tests. |
| `tests/acceptance/` | Acceptance evidence, Telegram callback/authorization/replay contracts. |
| `tests/recovery/` | Interrupted journal and recovery safety tests. |
| `tests/test_*.py` | Targeted CLI, config-free, migration, packaging, plugin, setup and security regressions. |
| `tests/fixtures/README.md` | Fixture conventions. |

## Documentation map

| Document | Use |
|---|---|
| `README.md` | Project overview and start-here navigation. |
| `docs/manual.md` | Current user/operator manual and workflow. |
| `docs/file-reference.md` | This current file responsibility inventory. |
| `docs/packaging-and-operations.md` | Debian package contents, install lifecycle and test/production distinction. |
| `docs/cli.md` | Command router reference; cross-check `--help` while CLI evolves. |
| `docs/configuration-home.md` | Configuration resolution, defaults and prepared config-free mode. |
| `docs/provider-adapters.md` | Hermes and experimental command provider interface. |
| `docs/user-approval-setup.md` | Human account timer/Telegram integration. |
| `docs/workflow.md` | Detailed task/approval lifecycle. |
| `docs/module-naming-current.md` | Canonical/compatibility naming migration. |
| `docs/release-checklist.md` | Dated acceptance gates, evidence and remaining release blockers. |
| `docs/test-coverage-matrix.md`, `docs/e2e-test-gaps.md` | What tests actually prove and do not prove. |
| `docs/baseline-validation.md`, `docs/test-source-inventory.md` | Original source validation and test provenance. |
| `docs/architecture-current.md`, `docs/component-inventory.md`, `docs/runtime-entrypoints.md` | **Historical baseline snapshots**; some runtime claims are superseded by the current guide. |
| `docs/technical-debt.md`, `docs/independent-review-followups.md` | Audit findings and follow-up work. |
| `docs/tux-test-runner.md`, `docs/development-wheel.md` | Runner and preview-build context. |

## Ownership boundaries

- **Projectwright owns:** queue decisions, journal/recovery, Git safety policy, scope validation, approval evidence and optional dispatch timers.
- **Provider/Hermes owns:** model invocation and agent behavior. The command provider is a trusted local executable, not a security sandbox.
- **Git owns:** worktree/commit history; Projectwright verifies evidence but does not automatically undo unauthorized commits.
- **Human owns:** acceptance decision, explicit onboarding and review of unsafe/interrupted work.
- **Debian owns:** installed binaries and static assets; it deliberately does not own an arbitrary user's Hermes secrets or automatically enable their services.
