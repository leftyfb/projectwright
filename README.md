# Projectwright

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

## Start here: tutorial or ready-to-run demo

**[Getting started: create your own project](docs/getting-started.md)** is a
step-by-step guide to setting up your repository, drafting requirements,
planning a queue, executing tasks, and reviewing/approving milestones. For a
longer build-it-yourself exercise, see the
[Task Tracker walkthrough](examples/task_tracker/README.md).

**[Ready-to-run demo: counter library](examples/ready_demo/README.md)** is
different: it creates a disposable Git repository and Projectwright project
with prewritten requirements, acceptance tests, and a preplanned queue.
Run the bootstrap after installation, inspect the sample state, and manually
authorize the tasks with your configured Hermes:

```sh
bash /usr/share/doc/projectwright/examples/ready_demo/bootstrap.sh
export PROJECTWRIGHT_CONFIG_DIR="$HOME/projectwright-demo/state"
pw status --project demo-counter
pw start --project demo-counter
```

See the [demo guide](examples/ready_demo/README.md) for each file's role,
the four-task workflow, expected test and Git results, and limitations.
This is live agent execution, not a prerecorded success simulation; it may
use provider tokens. Human milestone acceptance still requires Telegram.
The package installs both guides under
`/usr/share/doc/projectwright/`.

## Quick start

1. Describe the project to Hermes or another LLM; use the prompt in the [onboarding guide](docs/llm-requirements-onboarding.md) to ask questions and draft requirements.
2. Review the draft, resolve open decisions, and save the approved Markdown draft locally as `requirements.md`.
3. Connect an existing, initialized Git repository and initialize Projectwright:

   ```sh
   pw init --project myproject --repo ~/repos/myproject
   ```

   Project state normally lives at `~/.config/projects/myproject`; the repository remains at `~/repos/myproject`. `pw init` does not create or modify the repository.
4. Put the reviewed draft at `~/.config/projects/myproject/requirements.md` (or use the actual configured project-state path), then explicitly plan:

   ```sh
   pw plan --project myproject
   ```

5. Review the generated queue and blockers:

   ```sh
   pw status --project myproject
   ```

   Inspect `queue.md` and proposed task scopes before proceeding.
6. Manually authorize one task:

   ```sh
   pw start --project myproject
   ```

   Confirm at the prompt. This runs one manual dispatcher cycle; it does not enable persistent or recurring execution.
7. Test the work and inspect its results and Git diff. A passing test or completed task is not milestone acceptance. Human milestone approval/rejection is supported through the configured Telegram callback flow; if that integration is not configured and enabled, acceptance remains blocked. There is no separate manual operator approval command documented.
8. Review the results and Git diff, update requirements if needed, then repeat planning, queue review, and one-task execution until complete.

See the [full onboarding guide](docs/llm-requirements-onboarding.md) for the requirements format, paths, approvals, and manual-versus-recurring execution. Recurring execution is a separate opt-in; see [CLI reference](docs/cli.md) and [operator manual](docs/manual.md).

## Documentation

- [LLM-assisted requirements and onboarding](docs/llm-requirements-onboarding.md)
- [CLI reference](docs/cli.md)
- [Workflow and milestone gates](docs/workflow.md)
- [Configuration and default paths](docs/configuration-home.md)
- [User and operator manual](docs/manual.md)
- [Provider adapters](docs/provider-adapters.md)
- [Telegram approval setup](docs/user-approval-setup.md)
- [APT installation](docs/apt-repository.md)
