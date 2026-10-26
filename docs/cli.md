# Preliminary `pw` command interface

The current development wheel and Debian preview include `pw` as a
single command that routes to the existing, separately-tested flat-script
entrypoints. It is **not yet** the final CLI or a proof of standalone
harness independence.

| Command | Delegates to | Purpose |
|---|---|---|
| `pw tick --project NAME` | `pw_dispatch` | One planning/worker dispatch tick |
| `pw status --project NAME` | `project_queue_manager --status` | Inspect project decision and blockers |
| `pw plan --project NAME` | `project_queue_manager --once` | One planning decision |
| `pw worker --project NAME --once` | `project_task_worker` | Run at most one worker task |
| `pw notify` | `pw_notify` | Preview approval notifications; send only if explicitly requested |
| `pw timer ACTION PROJECT` | `pw_project_timer` | Inspect, install, enable or disable user timers |
| `pw init --project NAME [--no-config]` | `pw_init` | Create inert configured project or config-free queue/work-log skeleton |
| `pw defaults --project NAME` | `pw_defaults` | Read-only selected root and effective defaults |
| `pw setup-user` | `pw_project_timer setup-user` | Explicit non-root approval timer/plugin onboarding; also available as `pw-timer setup-user` |

Each command has its own `--help`, which `pw` forwards. `pw --help`
displays the routing summary without performing any action. The legacy
`pw-dispatch`, `pw-manager`, `pw-worker`, `pw-notify`, and
`pw-timer` entrypoints remain available during migration.

An explicit configuration home can be provided to `pw tick`,
`pw status`, `pw plan`, and `pw worker` through `--config-dir`.
See [configuration home](configuration-home.md). The full set of
subcommands still needs a shared configuration parser before 1.0.

The `pw` command merely delegates; it does not bypass the worker journal,
Git cycle validation, quota gate, acceptance guard or existing authorization
rules. A missing project configuration yields a disabled manager decision,
not permission to begin work.

## Additional operator commands

`pw worker --project NAME --dry-run` previews selection; `--journal-status` inspects durable task state; `--quota-check` evaluates optional quota; `--authorize-retry TASK_ID` is an explicit reviewed recovery action. `pw tick --no-telegram` suppresses legacy worker progress messages, not milestone acceptance. `pw notify` is a preview unless `--send` is supplied, which sends an actual Telegram approval request.

`pw-timer setup-user --minutes 10 --enable-hermes-plugin` is the verified non-root approval onboarding command; it can enable a user timer and plugin. It is separate from `pw timer check|install-disabled|enable|disable|status PROJECT`, which manages project dispatch timers. See [manual](manual.md) and [packaging operations](packaging-and-operations.md).
