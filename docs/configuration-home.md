# Configuration home: initial XDG migration

Projectwright currently has an **initial XDG project-root selector**, not yet
complete configuration-free execution. New user configuration should live under
`$XDG_CONFIG_HOME/projectwright` (default `~/.config/projectwright`).
Project-specific state and config are currently discovered in its
`projects/<project-id>/` subdirectory.

The CLI accepts an explicit Projectwright config home with:

```bash
pw tick --project demo --config-dir /absolute/config/projectwright
pw status --project demo --config-dir /absolute/config/projectwright
pw worker --project demo --config-dir /absolute/config/projectwright --once
```

For `pw tick`, its dispatcher forwards the chosen root to manager and worker
subprocesses as `PROJECTWRIGHT_CONFIG_DIR`, so each sees the same project
directory. On a direct manager/worker invocation, `--config-dir` is also
supported.

Project directory resolution, when no explicit CLI root is supplied:

1. `PROJECTWRIGHT_CONFIG_DIR/projects` if set.
2. `HERMES_PROJECT_CONFIG_DIR` if set (backwards-compatible project-root override).
3. `$XDG_CONFIG_HOME/projectwright/projects`, or
   `~/.config/projectwright/projects` when `XDG_CONFIG_HOME` is unset.
4. If the XDG project root does not exist and the legacy
   `~/.hermes/projects` exists, use the legacy directory.

The selector never moves or rewrites an existing project. For the first
transition, retaining legacy data takes priority over silently changing live
behavior. Use an explicit `--config-dir` to select a new location.

**Missing configuration behavior:** `pw status` or `pw plan` for a
project without `config.json` returns a `disabled` decision and does not
create project data, run a provider, or send a message. The rest of the
config-free runtime defaults remain to be implemented; worker execution still
requires a validated project configuration. A missing configuration is never
interpreted as permission to start a task.

Current migration gaps: individual utilities (notifier, approval helpers,
notes sync, timer setup) still have legacy `~/.hermes` assumptions. The release
checklist tracks consolidating these behind one shared configuration API,
separating XDG data/state/cache directories, and adding first-run setup.
