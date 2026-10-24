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
