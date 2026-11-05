# Per-user approval notification setup (development)

The Debian preview does **not** silently enable Telegram, Hermes plugins,
or systemd timers during `apt install`. A Debian `postinst` runs as root,
while the required user bus and Hermes plugin configuration belong to a
specific unprivileged account. There is no reliable way to select that
account from an unattended installation. The release checklist requires a
package-triggered, explicitly selected per-user onboarding mechanism before
stable deployment.

The standard first-run command is:

```bash
pw setup
```

Run it as the intended ordinary user, **not with sudo**. Hermes is required:
the command finds a `hermes` executable on PATH or in common user-local locations,
checks the user's `~/.hermes/` directory, and runs a 20-second read-only
`hermes plugins list --plain --no-bundled` probe. A failing or timed-out probe
refuses setup without printing Hermes output. When it detects both
`TELEGRAM_BOT_TOKEN` and a valid numeric `TELEGRAM_ALLOWED_USERS` list
in `~/.hermes/.env`, it explains the Hermes plugin and user timer changes,
then prompts **Enable Projectwright Hermes/Telegram approvals now? [y/N]**.
The default answer is No. Saying Yes installs the plugin and enables the
notifier timer; it does not silently restart the gateway.

If Telegram is not configured, `pw setup` reports how to configure it and
leaves Telegram integration inactive. To deliberately skip Telegram, use
`pw setup --no-telegram`. For explicitly approved noninteractive automation,
`pw setup --yes` bypasses the confirmation prompt; ordinary noninteractive
invocation with detected Telegram credentials refuses activation. `--minutes N`
sets the notification scan interval, 5 through 1440 minutes.

For older development installs, `pw-timer setup-user --enable-hermes-plugin`
and `pw setup-user --enable-hermes-plugin` remain direct compatibility entrypoints;
unlike `pw setup`, these advanced commands request activation without an
interactive confirmation.

Run it **as the intended ordinary user**, not with `sudo`. It verifies that
`~/.hermes/.env` contains a Telegram bot token and a valid authorized-user
allow-list, refuses root execution, refuses to overwrite modified systemd
units, optionally invokes
`hermes plugins enable projectwright-approvals`, and installs:

- `~/.config/systemd/user/projectwright-approval-notify.service`
- `~/.config/systemd/user/projectwright-approval-notify.timer`

It then calls `systemctl --user daemon-reload` and
`systemctl --user enable --now projectwright-approval-notify.timer`.
The default scan interval is ten minutes, adjustable with
`--minutes N` (5 through 1440). A repeated setup with identical unit
contents is safe; an existing modified unit is preserved and blocks setup.

The service runs the installed `pw_notify.py --send` and retains all existing
approval sender validation and deduplication rules. To stop it:

```bash
systemctl --user disable --now projectwright-approval-notify.timer
```

**Limitations:** When `--enable-hermes-plugin` is selected, setup copies the shipped native
`plugin.yaml` and `__init__.py` to the current user's
`~/.hermes/plugins/projectwright-approvals/` (refusing to overwrite custom
changes) before invoking `hermes plugins enable`. A gateway restart/reload is a separately reviewed action; isolated gateway callback loading and a real Approve callback were verified in `disposable-test-container` on 2026-10-25. A plugin installation
mechanism, explicit target-user selection from Debian installation, migration
of Hermes bot credentials to a generic Projectwright config, stable cross-source-version upgrades and general user cleanup are not complete. Regular hosted offline CI mocks Telegram, while separately authorized `disposable-test-container` LXD workflows have verified real installation, user timer setup, plugin registration, gateway loading, Telegram delivery, callback acceptance and cleanup. These are **not** routine CI jobs.

## Debian preview integration files

The development Debian package now includes **inactive** reference assets at
`/usr/share/projectwright/systemd/user/projectwright-approval-notify.service`,
`/usr/share/projectwright/systemd/user/projectwright-approval-notify.timer`,
and `/usr/share/projectwright/hermes/projectwright-approvals.py`.
The timer unit calls the packaged `/usr/bin/pw-notify --send` entry point.
These are package-managed source/template files, not automatically deployed
into any individual account, and these static files are **not an enabled per-user Hermes plugin**. The explicit `pw-timer setup-user`
command still generates its own per-user units, because automatic installation
and upgrades must handle existing user modifications safely.

The package now ships the native Hermes plugin directory under
`/usr/share/projectwright/hermes/projectwright-approvals/`, including
`plugin.yaml` and `__init__.py`. The latter calls Projectwright's existing
Telegram callback registration code and handles Debian modules not visible
inside a Hermes virtual environment. These integration assets are still
installed **inertly** by dpkg; the explicit non-root onboarding action is
required for each account. Isolated Hermes discovery/registration and live Approve callback have been verified; production rollout, Reject and other security edges remain separate acceptance gates.

**First-run interface:** new packages should use `pw setup`. Previously built preview artifacts may not include this command; `pw-timer setup-user` is the older direct onboarding route.

See [full manual](manual.md) and [packaging operations](packaging-and-operations.md).

### Ambiguous or stale milestone approvals

`pw notify --project PROJECT --send` refuses to select arbitrarily when
multiple completed milestones need acceptance. It reports which milestones
were previously approved but whose evidence is now stale, versus milestones
that have never been approved. To explicitly rerun acceptance for one eligible
milestone, use:

```bash
pw notify --project PROJECT --milestone REQUIREMENT-M1
pw notify --project PROJECT --milestone REQUIREMENT-M1 --send
```

The first command previews the eligible request without sending it; the second
pins the evidence and sends the Telegram buttons. Clicking Approve reruns the
configured acceptance command against the current clean Git worktree.
The pinned request is still checked for staleness under the project lock.
The explicit selection cannot bypass strict milestone sequencing.

A previously accepted scoped milestone is kept valid after a successor COMMIT
only when Projectwright can verify the exact successor commit chain through
acceptance policy scopes, completed queue tasks and an accepted receipt or
completed COMMIT journal. If that evidence is missing, the old approval stays
stale and requires explicit revalidation. Unscoped legacy receipts remain
HEAD-strict.


### Final project completion notification

After the last declared milestone is approved through the authorized Telegram
callback, Projectwright sends a separate **Projectwright — project complete**
message to the configured Telegram recipients. The summary contains the
project name, the number of accepted milestones and completed queue tasks,
the declared milestone titles, and the final Git commit. This is generated
deterministically from the project records; it makes no model call.

Projectwright sends this only if every declared milestone has a current,
verified acceptance receipt, no queue tasks are pending/blocked/invalid,
the Git worktree is clean and on the configured branch, and no worker/Git
cycle is active. An intermediate approval or rejected callback cannot
announce completion.

Delivery receipts are recorded per authorized Telegram user and completed
project revision in `telegram_completion_notified.json`. The existing
`pw notify --send` timer retries delivery when the callback's immediate
notification fails. As with milestone notification, a crash after Telegram
accepts a message but before the local receipt is saved may cause one repeat.
Telegram delivery failures never revoke or invalidate an approved milestone.
No Hermes service restart is initiated automatically.

