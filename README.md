# Projectwright

Projectwright turns human-written requirements into a reviewed, ordered queue of bounded tasks, then coordinates Hermes to carry them out in a Git repository. It checks task reports and Git changes, records progress, and can pause at milestone boundaries for human approval.

Hermes is the AI agent: it interprets prompts and performs planning or development using its configured model and tools. Projectwright is the workflow and safety layer: it stores requirements, plans, queue and progress; applies execution policy; validates results and Git evidence; and enforces milestone gates. Neither tool supplies the other's credentials or Git repository.

```text
requirements + milestones -> planning -> queue -> one worker task at a time
                                                   -> report and Git validation
                                                   -> progress or recovery hold
                                                   -> milestone authorization
                                                   -> completed-work acceptance
```

Planning can propose queue entries; review the generated queue before enabling execution. A worker can change files and create commits in the selected repository. Projectwright does not automatically configure Hermes, create/select your Git repository, enable execution, authorize milestones, accept completed milestones, or enable recurring runs. Those actions require explicit configuration or confirmation. Telegram notifications and approval callbacks are optional and separately configured.

## Install

Configure the [signed Projectwright APT repository](docs/apt-repository.md), verifying its signing-key fingerprint as described there. Then:

```sh
sudo apt update
sudo apt install projectwright
pw setup
```

Run `pw setup` as your normal Hermes user, not with `sudo`. Hermes CLI must already be installed and configured. Telegram is optional; setup asks before enabling its integration. See the [APT guide](docs/apt-repository.md) for repository setup and trust verification.

## First project

Use a disposable Git repository for your first run. These steps create Projectwright state in the default location and connect it to a Git repository elsewhere. Replace the example repository path with the absolute path to your own existing repository.

1. Create an inert project and inspect its selected paths:

```sh
pw init --project demo
pw defaults --project demo
```

By default, projects live under `$XDG_CONFIG_HOME/projectwright/projects` (normally `~/.config/projectwright/projects`). If that root does not exist but the legacy `~/.hermes/projects` does, Projectwright selects the legacy root. `--config-dir /absolute/config/home` selects a config home whose `projects/` child contains projects; pass it consistently to commands. See [configuration and path resolution](docs/configuration-home.md).

2. Edit `<project-directory>/config.json` to connect an existing repository outside the Projectwright directory:

```json
"worktree": "/absolute/path/to/my-existing-repository",
"branch": "main"
```

These are fields in the existing JSON object, not a replacement for it. Use a clean repository on its configured branch. Projectwright operates on one Git worktree per project. Coordinated work across multiple repositories is not supported as one task/project; use separate Projectwright projects and coordinate and accept them independently.

3. Create `<project-directory>/requirements.md` with human-authored intent and explicitly named milestones. For example:

```markdown
# Demo

## Requirement DEMO-1: Add a greeting

The application prints a greeting when run.

### DEMO-1-M1 — Greeting implementation
Implement the greeting, add a focused test, and verify it.
```

4. Enable planning while keeping execution disabled. In `config.json`, set:

```json
"planning": {
  "enabled": true,
  "requirements_file": "/absolute/path/to/project-directory/requirements.md"
},
"execution": {"enabled": false}
```

Keep all other existing configuration fields. `pw plan --project demo` requests planning; it may invoke Hermes and append validated proposals to `queue.md`. Review the queue, then inspect status:

```sh
pw plan --project demo
pw status --project demo
```

`pw plan` does not execute tasks. A newly initialized project remains execution-disabled; `pw tick` will not execute its queued work just because tasks exist. To proceed, explicitly set `"execution": {"enabled": true}` after reviewing the repository, queue, provider and policy.

5. Preview the selected task, then run one dispatcher cycle. A tick plans when permitted and executes at most one task:

```sh
pw worker --project demo --dry-run
pw tick --project demo
```

Check `pw status --project demo`, the project's `queue.md`, `work_log.md`, `results/`, `worker_journal.json`, and Git status/diff to review progress and changes. Do not use a real project for this walkthrough.

6. Optional recurring execution and Telegram approvals:

- Project timers are opt-in. Inspect `pw timer --help`; install and enable a per-project timer only after verifying one-shot behavior and its target.
- `pw setup` offers optional Telegram approval setup when Hermes Telegram credentials are detected. Notification and callback handling require separate explicit setup. See [approval setup](docs/user-approval-setup.md). `pw notify` previews by default; `pw notify --send` sends messages.

## Milestone authorization is not acceptance

Authorizing work on a milestone permits its planned work to proceed; it does not certify the result. Acceptance occurs only after milestone tasks complete and configured acceptance checks pass against the expected requirements, queue and Git evidence. A checked queue item or successful worker report is not an acceptance receipt. Telegram approval is optional and does not replace acceptance checks.

## More documentation

- [User and operator manual](docs/manual.md) — workflow, safety, recovery, operations
- [CLI reference](docs/cli.md) — commands and flags
- [Workflow and milestone gates](docs/workflow.md)
- [Configuration and default paths](docs/configuration-home.md)
- [Provider adapters](docs/provider-adapters.md)
- [Telegram approval setup](docs/user-approval-setup.md)
- [Tests and coverage boundaries](docs/test-coverage-matrix.md)
- [Security policy](SECURITY.md)

For source development and maintainer guidance, see [CONTRIBUTING.md](CONTRIBUTING.md).
