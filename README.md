# Projectwright

## Repository-local projects

New projects can live entirely under `~/projects/task-tracker-example/` (or a selected repository location), with Projectwright state in `.pw/`. See [repository-local projects](docs/embedded-projects.md) for initialization, shared Git configuration, callback registration. Existing external-state projects remain supported.


Projectwright turns your requirements into a reviewable queue of small development tasks, then coordinates Hermes to work through that queue in a Git repository. It tracks progress and Git changes, checks worker reports, and can pause for human milestone approval.

Hermes is the AI developer: it plans and edits using your configured model and tools. Projectwright manages the requirements, queue, safety checks, progress and approval gates. Planning proposes work; it does not authorize execution. Execution is a separate, explicit action.

## Let an LLM draft your requirements

You do not need to write a large specification from scratch. Describe your project to Hermes or another LLM, ask it to clarify uncertainties, and have it draft a complete `requirements.md` using the [copyable prompt in the onboarding guide](docs/llm-requirements-onboarding.md). For a greenfield project, the LLM may propose tests, files, and acceptance commands as future deliverables—but proposals must be clearly marked and verified before use. Review every decision and authorized path yourself; never present nonexistent tests or unverified commands as already working. Save the reviewed draft as the Projectwright project's `requirements.md` before planning.

## Install and set up

Configure the [signed APT repository](docs/apt-repository.md), including verifying its signing-key fingerprint, then run as your normal user:

```sh
sudo apt update
sudo apt install projectwright
pw setup
```

Do not run `pw setup` with sudo. Hermes CLI must already be installed and configured. Telegram setup is optional.

## Try the Task Tracker example

A disposable, beginner-friendly [Task Tracker walkthrough](examples/task_tracker/README.md) demonstrates `pw init`, requirements, planning, a one-task Hermes run, and review. The task tracker is **not prebuilt**: Projectwright generates it from the example requirements.

The Debian package also installs this walkthrough and the starter README under `/usr/share/doc/projectwright/examples/task_tracker/`. Open the walkthrough after `sudo apt install projectwright`:

```sh
less /usr/share/doc/projectwright/examples/task_tracker/README.md
```

The initial milestone can be worked and reviewed without Telegram. Advancing to the next milestone requires a real Telegram approval callback; the demo does not silently bypass the approval gate.

## Quick start

1. Draft and review project requirements using Hermes or another LLM. See the [requirements onboarding guide](docs/llm-requirements-onboarding.md).
2. Initialize the Git repository and its embedded Projectwright state:

   ```sh
   pw init ~/projects/myproject
   cd ~/projects/myproject
   ```

   For an existing Git repository, run `pw init .` at its root. The repository name is also the Projectwright project ID. Initialization creates `.pw/` but leaves planning, execution, and timers disabled.
3. Create a baseline Git commit (skip this if the existing repository already has one), then save the reviewed requirements:

   ```sh
   printf '# My project\n' > README.md
   git add README.md .gitignore
   git commit -m "Initialize myproject"
   pw requirements --project myproject --edit
   ```

   The requirements belong in `.pw/requirements.md`, not in a separate Projectwright state tree.
4. Review planning and authorize one task at a time:

   ```sh
   pw plan --project myproject
   pw status --project myproject
   cat .pw/queue.md
   pw start --project myproject
   ```

   Confirm the one-shot execution prompt. It does not enable unattended execution.
5. Inspect Git changes and run tests. Human milestone acceptance is through the configured Telegram callback; without Telegram the gate remains blocked. Never manually create approval records.

For the complete working example, including starter files and requirements, follow the [Task Tracker walkthrough](examples/task_tracker/README.md). See [repository-local projects](docs/embedded-projects.md) and the [CLI reference](docs/cli.md).

## Documentation

- [LLM-assisted requirements and onboarding](docs/llm-requirements-onboarding.md)
- [CLI reference](docs/cli.md)
- [Workflow and milestone gates](docs/workflow.md)
- [Configuration and default paths](docs/configuration-home.md)
- [User and operator manual](docs/manual.md)
- [Provider adapters](docs/provider-adapters.md)
- [Telegram approval setup](docs/user-approval-setup.md)
- [APT installation](docs/apt-repository.md)
