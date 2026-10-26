# Projectwright final-release acceptance checklist

**Status:** release requirements, not a claim of implementation. No item below is
considered done merely because a development wheel or Debian preview builds.
A production release requires tests, docs, and an install/upgrade test against
a disposable account before a stable tag or deployment.

## Current verified state (2026-10-26)

- **Isolated extracted Debian CLI smoke PASSED:** [pw-test run 40352674907](https://github.com/leftyfb/projectwright/actions/runs/40352674907) consumed the successful hosted-CI artifact, verified all six packaged CLI wrappers, initialized a disposable config-free project, checked defaults/disabled status, and confirmed `pw setup-user` safely refused missing Telegram credentials. It used an isolated HOME and package extraction only; **no dpkg install, sudo, user-systemd change, Hermes gateway operation or Telegram send**. The first run exposed an unclear missing-credential error; the branch now fails clearly and rejects symlinked `.env` files, with hosted [CI 40352449079](https://github.com/leftyfb/projectwright/actions/runs/40352449079) passing its regression suite and package checks. Real fresh dpkg install of these latest bits remains a separate privileged gate.
- **Manual and CLI/package audit:** Reworked README and added [manual](manual.md), [file reference](file-reference.md), and [packaging operations](packaging-and-operations.md); legacy snapshot pages now indicate their historical scope. Fixed `pw setup-user` forwarding to the timer's explicit setup action and added route regression tests. [GitHub-hosted offline CI 40350096040](https://github.com/leftyfb/projectwright/actions/runs/40350096040) passed offline suite, development validator, wheel and Debian build/smoke checks, and artifact upload. This is **hosted-only** evidence; no `pw-test` runtime or live installation was exercised in this phase. The full documentation and production release checkboxes remain open pending clean-installed user walkthrough and complete audit.
- **Real Telegram Approve callback PASSED:** [pw-test receipt verification 40258567183](https://github.com/leftyfb/projectwright/actions/runs/40258567183) independently confirmed the acceptance receipt and pending-record consumption for a disposable milestone. This closes the isolated live Approve-path acceptance gate, **not** all rejection, authorization, migration, or release gates.
- **Disposable integration cleanup PASSED:** [pw-test cleanup 40258658872](https://github.com/leftyfb/projectwright/actions/runs/40258658872) removed the test-only plugin, service override, .deb and Git fixture; existing Hermes credentials were preserved.
- **Dependency-path fix:** The Hermes bridge appends Debian's package directory to `sys.path`, preserving Hermes virtualenv precedence. Hosted regression tests verify the change.
- **Environment availability:** The user plans to leave the `pw-test` LXD container stopped between test sessions. **Do not trigger any `pw-test` self-hosted Actions workflows while it is stopped.** Continue hosted-only CI and documentation; do not start the container or production services without specific authorization.
- **Historical notes below are chronological, not current status.** Earlier statements that live Telegram delivery or approval was blocked, or that cleanup was outstanding, were superseded by the successful runs above. Check the dated evidence, not an obsolete earlier gate description.

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

## Debian staging on pw-test (2026-10-25)

- A branch-scoped, deliberately triggered, non-root Debian staging workflow,
  `.github/workflows/pw-test-deb-staging.yml`, now **downloads the exact
  Debian package artifact from a successful GitHub-hosted CI run** instead of
  rebuilding from source inside the LXC container. It checks the container
  identity and artifact source (successful push on review branch), verifies
  package metadata, extracts into a temporary directory, runs CLI help and
  defaults, and checks bundled Hermes and systemd files.
- **Live staging passed:** GitHub Actions run
  [40242150486](https://github.com/leftyfb/projectwright/actions/runs/40242150486)
  on `pw-test-projectwright`. No `sudo`, `apt install`, `dpkg --install`,
  or changes to the production host were requested. **The container does not
  need `pip` for this workflow.**
- Earlier staging attempts [40241221573](https://github.com/leftyfb/projectwright/actions/runs/40241221573)
  and [40241284388](https://github.com/leftyfb/projectwright/actions/runs/40241284388)
  identified missing system `pip` and an incompatible CPU ISA requirement in
  a downloadable Python build. The artifact handoff eliminates both build
  prerequisites on `pw-test`.
- Real `dpkg` installation, upgrade, per-user Hermes setup, systemd
  enablement, and removal/purge **remain unverified**. Those require a
  separate guarded test with explicit container-scoped privileges and cleanup.

## Guarded Debian install lifecycle script (2026-10-25)

- Added `scripts/pw-test-deb-lifecycle.sh` for a **separately authorized,
  manual root invocation inside pw-test only**. It refuses mismatched
  hostname/virtualization, unexpected Debian package name/version, existing
  Projectwright installation or paths, and an obvious host bind mount.
  It installs, checks CLI entry points, reinstalls the same development
  version, and purges the package in an EXIT cleanup trap (including
  partially installed states). The GitHub runner never invokes sudo.
- The unprivileged refusal path was **executed successfully on pw-test** by
  [GitHub Actions 40242723597](https://github.com/leftyfb/projectwright/actions/runs/40242723597):
  the harness passed Bash syntax validation and rejected invocation from the
  ordinary runner account. The hosted-CI Debian artifact also passed staging.
- The root-only install/purge path remains **unexecuted on pw-test**. Successful staging
  [40242150486](https://github.com/leftyfb/projectwright/actions/runs/40242150486)
  does **not** validate real dpkg install or purge.
- A same-version reinstall is not an upgrade: testing a true upgrade
  requires two distinct package versions, a verified migration plan and
  separate authorization. User-level systemd/Hermes setup remains out of
  scope for this lifecycle script.

## Verified real Debian install/reinstall/purge (2026-10-25)

- **PASS:** [GitHub Actions 40244321910](https://github.com/leftyfb/projectwright/actions/runs/40244321910) ran the lifecycle inside `pw-test` with explicitly authorized `sudo -n`. It installed the hosted-CI `.deb`, verified installed commands, reinstalled the same version, and purged it via the trap. Post-run checks found no `/usr/bin/pw`, `/usr/share/projectwright`, or installed `projectwright` dpkg status. This is actual container installation evidence, not extraction-only validation.
- Still unverified: **true two-version upgrade**, standalone user-level systemd approval timer onboarding, live Hermes plugin and Telegram integration, and production installation. Do not mark these complete.

## Human-authorized dpkg lifecycle handoff (2026-10-25)

- The successful non-root staging job now also uploads the **exact tested
  Debian file** as a short-lived `pw-test-verified-deb-<run id>` Actions
  artifact. The workflow does not install the package or elevate privileges.
- For the first actual install, a human should download that artifact from
  the **successful pw-test Debian staging smoke run**, inspect its SHA-256,
  and extract its ZIP inside `pw-test` as `ubuntu`. Run the script below
  only after confirming the shell is **inside the disposable container**,
  not on `tux`:
  ```sh
  hostname -s
  systemd-detect-virt --container
  # Within pw-test, from the reviewed test/review-followups checkout:
  sha256sum /absolute/path/projectwright_0.1.0~dev0-1_all.deb
  sudo bash scripts/pw-test-deb-lifecycle.sh /absolute/path/projectwright_0.1.0~dev0-1_all.deb
  ```
  No sudo privileges have been granted to GitHub Actions. The lifecycle
  script refuses prior package remnants and invokes a purge cleanup trap.
- **Now performed:** privileged lifecycle invocation in `pw-test` (run
  40244321910). True two-version upgrade, live per-user timer, and Hermes
  integration remain outstanding. Logs and the output
  SHA-256 should be retained for release evidence. This handoff is a
  manual privileged operation; do not run it automatically on push.

## Verified synthetic Debian version upgrade (2026-10-25)

- **PASS:** [pw-test Actions run 40244873728](https://github.com/leftyfb/projectwright/actions/runs/40244873728) installed an older synthetic Debian revision `0.1.0~dev0-0`, upgraded with the hosted-CI package `0.1.0~dev0-1`, exercised CLI smoke checks, reinstalled and purged it inside the dedicated LXC container.
- The older package was **repacked from the current package with a lower Debian revision**, not built from an earlier Projectwright source release. This confirms dpkg's two-version transition and cleanup; **real historical-version migration and user-data retention remain unverified**.
- An initial workflow revision was invalid YAML and did not run; the corrected workflow completed successfully. No changes to `main` or production Hermes were requested.
- Next: validate per-user systemd onboarding in the container with isolated credentials/provider mocks, then test a real cross-source-version migration when an older releasable artifact exists.

## Verified live per-user systemd onboarding in LXD (2026-10-25)

- **PASS:** [pw-test Actions run 40245117718](https://github.com/leftyfb/projectwright/actions/runs/40245117718) installed the real Debian package, supplied **dummy Telegram credentials only**, ran `pw-timer setup-user --minutes 1440` as ordinary `ubuntu`, verified the user-level timer was enabled and active, disabled it, repeated setup for idempotency, and disabled it again.
- The test harness removes its dummy `~/.hermes/.env` and generated user units, reloads the systemd user daemon, and purges the Debian package. **No Hermes plugin was enabled and no Telegram message was sent**; live Hermes discovery and callbacks remain unverified.
- The first attempt [40245052174](https://github.com/leftyfb/projectwright/actions/runs/40245052174) failed because the harness called `pw setup-user` rather than the actual packaged `pw-timer setup-user` entry point. Corrected and rerun successfully.
- Documentation and CLI onboarding command consistency still requires review: `docs/user-approval-setup.md` currently gives `pw setup-user`, while the packaged `pw-timer setup-user` entry point was the one verified.

## Isolated Hermes CLI discovery on pw-test (2026-10-25)

- User reports a separately configured Hermes installation in `pw-test`.
- First read-only runner probe [40246157329](https://github.com/leftyfb/projectwright/actions/runs/40246157329) passed container and Projectwright validation but found no `hermes` command on the non-interactive runner PATH. No plugin or credentials were changed.
- Expanded read-only discovery to common user-local virtualenv locations; [run 40246253270](https://github.com/leftyfb/projectwright/actions/runs/40246253270) **passed**, confirming the dedicated runner can execute the Hermes plugin CLI. This does not establish a running Hermes gateway or successful Projectwright plugin registration.
- Next: verify user-local Hermes state and adapter discovery, then test plugin registration with isolated credentials and no Telegram network delivery. Never overwrite the test user's existing Hermes `.env` or reuse production secrets.

## Verified isolated Hermes native plugin registration (2026-10-25)

- **PASS:** [pw-test Actions run 40247054640](https://github.com/leftyfb/projectwright/actions/runs/40247054640) used the actual Hermes CLI in the dedicated LXD container to enable and inspect the packaged `projectwright-approvals` native plugin. The registry listed it as **enabled**, version `0.1.0`, source `user`.
- The fixture checks that the plugin directory did not exist beforehand, installs only the two Debian-shipped plugin assets, disables the plugin afterward and removes the test-created directory (including Hermes-generated cache); it purges the Debian package afterward. Existing `~/.hermes/.env` is preserved and no Telegram message was sent.
- First attempt [40246961109](https://github.com/leftyfb/projectwright/actions/runs/40246961109) verified registration but failed to clean generated plugin cache. The corrected full lifecycle **passed** in run 40247054640.
- Once test Hermes was configured, the earlier dummy-`.env` timer test correctly refused to overwrite existing credentials. The workflow now skips that specific fixture if the account already has Hermes credentials. The earlier live user-timer onboarding evidence remains valid.
- **Still unverified:** a live Hermes gateway loading the plugin callback handler; real Telegram inline button delivery and approval; full isolated EDIT/TEST/COMMIT provider workflow; historical upgrade migration.

## Hermes plugin runtime contract validation (2026-10-25)

- **PASS:** [pw-test Actions run 40247372924](https://github.com/leftyfb/projectwright/actions/runs/40247372924) ran `hermes plugins doctor projectwright-approvals` against the installed Debian plugin in the isolated test Hermes environment. Hermes reported **"OK: runtime discovery, manifest parsing, import, and registration passed"**. The test then disabled and removed its plugin directory and purged the Debian package.
- Doctor reports `0 tool(s), 0 hook(s)`; Projectwright's adapter registers a Telegram handler factory, not a tool/hook. The doctor result does **not** prove that the running gateway attached the callback handler or that a button was delivered/clicked.
- **Still open:** gateway-level Telegram callback registration and end-to-end approval interaction, isolated live provider execution, and production release/security gates. Do not use a real Telegram bot token merely to satisfy the doctor test.

## Installed adapter callback-factory test (2026-10-25)

- **PASS:** [pw-test Actions run 40247768747](https://github.com/leftyfb/projectwright/actions/runs/40247768747) installed the Debian package, validated the native plugin with Hermes doctor, and imported its packaged adapter under Ubuntu Python with an **in-memory Telegram transport stub**. A fake application received exactly one `CallbackQueryHandler`, which matched scoped Projectwright approve/reject callback IDs and refused an unrelated ID.
- The probe does **not** start or restart the Hermes gateway, connect to Telegram, test an actual bot message, or approve a real milestone. Those live gateway and end-to-end gates are still open.
- Initial probe [40247667905](https://github.com/leftyfb/projectwright/actions/runs/40247667905) failed because the Hermes CLI was a shell wrapper, not a Python interpreter. The corrected system-Python probe with stub Telegram transport passed. All package/plugin cleanup completed.

## Live isolated Hermes gateway discovery (2026-10-25)

- **PASS:** [pw-test Actions run 40248316763](https://github.com/leftyfb/projectwright/actions/runs/40248316763) verified via the real user-level systemd manager that `hermes-gateway.service` is **loaded, active, and running** in the `pw-test` LXC container. The Hermes CLI exposes `gateway status` and `gateway list`.
- This was **read-only**: no gateway stop, start, restart or configuration change. The earlier plugin-doctor and callback-factory tests removed their plugin fixtures afterward, so these findings **do not establish that the running gateway loaded Projectwright**.
- Next: plan a controlled installation and gateway restart/reload inside the disposable container, preserving existing user credentials and backing up test-only settings. Then verify Projectwright callback registration and approval behavior without sending messages to a production Telegram bot.

## Verified live Hermes gateway callback loading (2026-10-25)

- **PASS:** [pw-test Actions run 40248597007](https://github.com/leftyfb/projectwright/actions/runs/40248597007) installed the hosted-CI Debian package, enabled the `projectwright-approvals` native plugin, checked it with Hermes doctor, restarted the **already running isolated Hermes gateway**, and verified systemd reported it active. Hermes explicitly logged: `Gateway reloaded plugins — active in the running gateway now: callbacks.`
- The test then disabled and removed its plugin and restarted the gateway to return to its earlier configuration; it purged Projectwright. Existing `~/.hermes/.env` and test Hermes credentials were not rewritten.
- **Still open:** confirmation of a real Telegram callback press and authenticated milestone acceptance in a disposable Git repository. Gateway plugin-loading confirmation is not an end-to-end bot message or approval.
- The dedicated LXD gateway can be restarted for future explicitly authorized tests; do not apply this workflow to the production Hermes host.

## Disposable Git milestone approval through callback handler (2026-10-25)

- **PASS:** hosted [offline CI run 40249196488](https://github.com/leftyfb/projectwright/actions/runs/40249196488) and [pw-test LXD preflight 40249278923](https://github.com/leftyfb/projectwright/actions/runs/40249278923) exercised a new regression that creates a throwaway Git repo and pending milestone approval, constructs its signed/content-bound inline callback, registers Projectwright's callback factory in an in-memory Telegram application, and dispatches the **actual approval function** through that callback. It verifies the acceptance receipt is recorded and pending request removed, then checks repeated delivery is refused as stale.
- The test mocks the Telegram transport and configured authorized user; it does **not** send a network message, consume the real gateway's update stream, or verify bot routing/allowed-user settings in the live gateway. Those are still end-to-end acceptance gates.
- The test never uses production project files or bot credentials. The existing live `pw-test` Hermes gateway was not restarted as part of this callback/receipt regression.

## Test Telegram readiness and callback rejection (2026-10-25)

- A new disposable Git fixture drives the **real rejection callback**, verifies `telegram_approval_rejected.json` matches the pinned request, confirms the pending request is kept for human review, and asserts that no acceptance receipt or repeat notification is created. This complements the previously passing approval-and-replay test; check the latest hosted and LXD runs before calling this new case verified.
- A **read-only, redacted** readiness check on `pw-test` found Hermes `~/.hermes/.env`, but `TELEGRAM_ALLOWED_USERS` **does not satisfy Projectwright's numeric allow-list parser** ([diagnostic run 40249685686](https://github.com/leftyfb/projectwright/actions/runs/40249685686)). Neither its value nor Telegram token was printed, and no credential was changed. It may be missing or formatted differently than Projectwright expects; the current value is not a verified safe test-only destination.
- Live bot delivery is therefore **BLOCKED**, not passed. Do not send real Telegram notifications or alter the Hermes allow-list until the user explicitly identifies an isolated test bot and recipient. The workflow now reports this as `NOT READY` without failing unrelated container diagnostics.

## Telegram test follow-up (2026-10-25)

- **CONFIRMED by recipient:** the isolated `pw-test` bot connectivity message from [run 40251106706](https://github.com/leftyfb/projectwright/actions/runs/40251106706) arrived in Telegram. This confirms outbound delivery, not a button callback.
- **FIXED:** the one-time live `sendMessage` step was removed from `.github/workflows/pw-test-preflight.yml` in commit `96279b65`; ordinary branch preflight no longer sends a message. Verified with successful [read-only LXD run 40252303862](https://github.com/leftyfb/projectwright/actions/runs/40252303862).
- **Still gated:** before sending an actionable Approve button, the actual running Hermes gateway must point Projectwright to a **disposable project root** (for example via its service environment `HERMES_PROJECT_CONFIG_DIR`) and the handler must be installed for the duration of the callback. Never let an approval callback resolve production or other existing project directories. The previous gateway fixture removed the plugin and restored the gateway after testing.
- User reported stopping the competing production bot gateway on `tux`. The test runner cannot independently verify remote production process state; confirm no competing bot consumer before the interactive callback run.

## Real Telegram approval staged and delivered (2026-10-25)

- **PASS:** [pw-test staging run 40253261094](https://github.com/leftyfb/projectwright/actions/runs/40253261094) installed Projectwright, prepared one disposable Git milestone at `/home/ubuntu/projectwright-live-test/projects/pwtelecheck`, configured a user-level Hermes gateway service drop-in with `PROJECTWRIGHT_APPROVAL_ROOT=/home/ubuntu/projectwright-live-test/projects`, enabled the approvals plugin, restarted the test gateway, and verified its **actual running process environment** contained the scoped root. It did not send Telegram.
- **PASS (outbound request):** [pw-test send run 40253364020](https://github.com/leftyfb/projectwright/actions/runs/40253364020) verified the same live gateway isolation and used `pw-notify --root /home/ubuntu/projectwright-live-test/projects --send`. It reported `NOTIFIED pwtelecheck / DEMO-1-M1` and wrote the delivery marker. This was **an actionable test Approve/Reject message**, sent to the single configured Telegram recipient.
- **PENDING:** recipient must press Approve or Reject in Telegram; then invoke the read-only `pw-test Verify Live Approval` workflow to check for the verified milestone receipt or rejection state. **Do not mark real inbound callbacks verified until this inspection passes.**
- **CLEANUP REQUIRED AFTER TEST:** The staging workflow intentionally leaves Projectwright installed and the plugin enabled in the disposable `pw-test` gateway to receive the button. After the result is recorded, remove the test-only gateway drop-in, remove test plugin, restore gateway, purge package, and remove only the disposable fixture. Leave the shared Hermes credentials unchanged. **Never run the setup workflow a second time without reviewing its no-overwrite guards.**

## Hermes Telegram adapter import-path fix (2026-10-25)

- **ROOT CAUSE IDENTIFIED:** the Debian-installed Projectwright Hermes bridge prepended `/usr/lib/python3/dist-packages` to Hermes's virtual environment `sys.path`. Mixing Debian's pure-Python `cryptography` package with the Hermes venv's Rust extension prevented `telegram-platform` from importing. The gateway reported `No adapter available for telegram`. This was not a Telegram bot setup issue.
- **FIX COMMITTED:** plugin bridge now appends the Debian fallback path, preserving Hermes's existing virtual environment import precedence. Regression test asserts the fallback does not use `sys.path.insert`.
- **USER-REPORTED LIVE RESULT:** after the same plugin change and gateway restart in `pw-test`, Telegram began polling normally. **Still to verify:** the actual Telegram callback produces the pinned disposable Git milestone approval receipt. A GitHub Actions verifier workflow exists for the disposable milestone.

## Live Telegram approval fully verified and cleaned up (2026-10-25)

- **PASS:** After the Projectwright Python path precedence bug was fixed, the user successfully pressed Approve in Telegram. The independent read-only [pw-test verification run 40258567183](https://github.com/leftyfb/projectwright/actions/runs/40258567183) reported `PASS: Telegram callback wrote verified acceptance receipt; request consumed`, verifying a real Telegram callback, acceptance receipt, and pending-record removal for disposable milestone `pwtelecheck / DEMO-1-M1`.
- **PASS:** [pw-test cleanup run 40258658872](https://github.com/leftyfb/projectwright/actions/runs/40258658872) disabled and removed the test approval plugin, removed the gateway root override, restarted the test gateway with its prior environment, purged the temporary Debian package, and deleted the isolated disposable Git fixture. It reported both `PASS: gateway test-only environment override removed` and `PASS: disposable Projectwright assets removed; Hermes credentials preserved`. No production `tux` actions were performed.
- **Regression fix:** Hermes adapter's Debian fallback appends `/usr/lib/python3/dist-packages` rather than prepending it; this preserves Hermes's venv `cryptography` import precedence. An offline test prohibits reintroducing the prepend. Do not confuse success of the one-time live test with a production deployment or release approval.

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

- [x] Deliver milestone requests with Telegram inline **Approve / Reject**
  buttons. The button callback, not free-form chat parsing, is authoritative. Verified with disposable live Approve callback in run 40258567183; real Reject path remains a separate gate.
- [ ] Authorize users dynamically against the configured allow-list and private
  chats; stale, replayed, altered, revoked and rejected requests fail closed.
- [x] Run acceptance checks against current policy, queue and Git evidence
  under the project lock before producing an approval receipt. Verified by the live disposable callback receipt and offline stale-policy/Git regressions; broader threat-model audit remains open.
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
