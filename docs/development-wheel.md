> **Historical preview-build notes.** The package has since been installed, upgraded synthetically, purged and exercised with Hermes/Telegram in an isolated `pw-test` LXD container. Those passes do not make it a stable release. Read [packaging-and-operations.md](packaging-and-operations.md) and the dated [release-checklist.md](release-checklist.md) for current status.

# Development wheel preview

The repository defines a preliminary `projectwright` Python wheel in
`pyproject.toml`. It packages the original flat Python modules as installed
top-level modules and provides console entrypoints:

- `pw-dispatch`, `pw-manager`, `pw-worker`
- `pw-notify`, `pw-timer`

The GitHub-hosted offline workflow builds the wheel, installs it into an
ephemeral target directory, imports modules from that target, and checks
`--help` for every entrypoint. **It does not deploy to** `~/.hermes/scripts`
or alter any production projects or services.

## Development-only build

From a disposable checkout with Python packaging tools installed:

```bash
python3 -m pip wheel --no-deps --wheel-dir dist .
```

Do not install this wheel onto the live Hermes environment yet. The wheel is
an initial packaging contract, **not a standalone deployment release**.
Configuration and some helper paths still assume `~/.hermes`, the worker and
planner invoke the Hermes CLI, and notification/approval integrations remain
Hermes-specific. Optional Python dependencies and OS prerequisites have not
yet been represented as an installable complete runtime specification.

`pw-dispatch` now defaults to locating its sibling modules next to the
installed `pw_dispatch.py` module, while retaining the explicit `--scripts`
override. The timer manager likewise locates its dispatcher next to its
installed module when generating a disabled-by-default unit, rather than
assuming the user's Hermes scripts directory. These changes let source-tree
use and wheel-based invocation select coherent sibling modules. No timers are
enabled by packaging.

## Debian development preview

CI also uses `scripts/build-deb.sh` to assemble
`projectwright_0.1.0~dev0-1_all.deb` from the tested pure-Python wheel.
The package has five `/usr/bin/pw-*` wrappers using the distribution's
`/usr/bin/python3`, Python files under `/usr/lib/python3/dist-packages`,
and basic `python3` and `git` dependencies. A CI inspects the package, extracts it and smoke-tests wrappers. A **separate authorized LXD workflow** has also performed an actual dpkg lifecycle; no APT repository is published or production host installed.

This preview is not approved for production deployment. Isolated Hermes/Telegram and package lifecycle paths have been exercised, but supported Ubuntu/Python/dependency matrix, cross-source-version migration, user-data preservation and general production upgrade/uninstall behavior remain unverified.
