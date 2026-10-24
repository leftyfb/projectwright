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
pw setup-user --enable-hermes-plugin
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

**Limitations:** The Hermes approval plugin must already be installed and
registered before `--enable-hermes-plugin` can succeed. A plugin installation
mechanism, explicit target-user selection from Debian installation, migration
of Hermes bot credentials to a generic Projectwright config, upgrades and
uninstalls are not complete. No live setup or Telegram send is part of CI;
tests substitute the systemctl and Hermes executables.

## Debian preview integration files

The development Debian package now includes **inactive** reference assets at
`/usr/share/projectwright/systemd/user/projectwright-approval-notify.service`,
`/usr/share/projectwright/systemd/user/projectwright-approval-notify.timer`,
and `/usr/share/projectwright/hermes/projectwright-approvals.py`.
The timer unit calls the packaged `/usr/bin/pw-notify --send` entry point.
These are package-managed source/template files, not automatically deployed
into any individual account, and the Hermes plugin source is **not yet a
registered Hermes plugin installation**. The explicit `pw setup-user`
command still generates its own per-user units, because automatic installation
and upgrades must handle existing user modifications safely.
