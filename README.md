# Projectwright

## Repository-local projects

New projects keep their Git repository and Projectwright state together, with configuration and operational files in `.pw/`. The default repository parent is `~/projects`, and you can choose another location during initialization. Existing external-state projects remain supported.


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

The Debian package installs the walkthrough, starter README, and ready-to-copy `requirements.md` under `/usr/share/doc/projectwright/examples/task_tracker/`. Open the walkthrough after `sudo apt install projectwright`:

```sh
less /usr/share/doc/projectwright/examples/task_tracker/README.md
```

The initial milestone can be worked and reviewed without Telegram. Advancing to the next milestone requires a real Telegram approval callback; the demo does not silently bypass the approval gate.

## Quick start

Initialize a repository at a location of your choice, then provide requirements and review the proposed work:

```sh
pw init ~/projects/myproject
cd ~/projects/myproject
```

Projectwright keeps its state in `.pw/` inside the repository. Commit your starting application files before running worker tasks. Use `pw requirements --project myproject --edit` for requirements, `pw plan --project myproject` to propose a queue, and `pw start --project myproject` to authorize one task.

For the **complete step-by-step example**, follow [examples/task_tracker/README.md](examples/task_tracker/README.md). The [CLI reference](docs/cli.md) describes available commands rather than duplicating the tutorial.

## Documentation

- [LLM-assisted requirements and onboarding](docs/llm-requirements-onboarding.md)
- [CLI reference](docs/cli.md)
- [Workflow and milestone gates](docs/workflow.md)
- [Configuration and default paths](docs/configuration-home.md)
- [User and operator manual](docs/manual.md)
- [Provider adapters](docs/provider-adapters.md)
- [Telegram approval setup](docs/user-approval-setup.md)
- [APT installation](docs/apt-repository.md)
