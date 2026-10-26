# Per-user approval notification setup (development)

The Debian preview does **not** silently enable Telegram, Hermes plugins,
or systemd timers during `apt install`. A Debian `postinst` runs as root,
while the required user bus and Hermes plugin configuration belong to a
specific unprivileged account. There is no reliable way to select that
account from an unattended installation. The release checklist requires a
package-triggered, explicitly selected per-user onboarding mechanism before
stable deployment.

A preliminary explicit setup command is available:

```bash
pw-timer setup-user --enable-hermes-plugin
```

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
changes) before invoking `hermes plugins enable`. A gateway restart/reload is a separately reviewed action; isolated gateway callback loading and a real Approve callback were verified in `pw-test` on 2026-10-25. A plugin installation
mechanism, explicit target-user selection from Debian installation, migration
of Hermes bot credentials to a generic Projectwright config, stable cross-source-version upgrades and general user cleanup are not complete. Regular hosted offline CI mocks Telegram, while separately authorized `pw-test` LXD workflows have verified real installation, user timer setup, plugin registration, gateway loading, Telegram delivery, callback acceptance and cleanup. These are **not** routine CI jobs.

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

**Unified alias caveat:** the current `pw setup-user` routing does not pass the required action argument to the timer module. Use `pw-timer setup-user` until fixed and retested.

See [full manual](manual.md) and [packaging operations](packaging-and-operations.md).
