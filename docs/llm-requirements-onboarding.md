# LLM-assisted requirements and onboarding

Projectwright consumes a human-reviewed `requirements.md`, asks its configured planner to create a queue, and runs at most one manually authorized task per `pw start`. You can use Hermes or another LLM to draft the requirements; no LLM-generated document is trusted or executed automatically. Review the scope, commands, dependencies and open decisions before planning.

## Copyable project-drafting prompt

Paste the prompt below into Hermes or another LLM. Replace the bracketed project description with what you know. Answer clarification questions before asking for the final draft. If you do not know an answer, let the model mark it as unresolved rather than guessing.

```text
You are helping me draft requirements for Projectwright. Your output is a proposal for human review, not authorization to execute work.

PROJECT IDEA / CONTEXT:
[Describe the problem, intended users, desired outcome, known repository or environment, and constraints. Include what is already known; do not include secrets.]

WORKING STYLE
1. First, understand the idea and ask useful, prioritized clarification questions. Ask about goals, non-goals, users, observable outcomes, constraints, dependencies, deployment/runtime assumptions, data/security concerns, and how success can be verified. Ask only questions that materially affect scope or acceptance. Group related questions and explain why important answers matter. Do not write the final requirements until I answer, or explicitly ask you to produce a draft with unresolved decisions called out.
2. Translate the idea and my answers into a complete Markdown draft for a human to review and save as requirements.md. Do not claim the draft is approved or run anything.
3. Organize work into requirements and incremental milestones. Each milestone must be small enough to review independently and must deliver a useful, testable increment. Order dependencies explicitly; do not make later milestones depend on unbuilt capabilities without saying so.
4. For every milestone, write explicit, observable acceptance criteria and list its authorized repository paths. Keep scope narrow. Include only paths supported by the project information I supplied. Do not authorize the whole repository unless I explicitly request and justify that scope.
5. Use Projectwright's actual Markdown conventions exactly:
   - Requirement heading: `## PREFIX-1 — Short requirement title` (uppercase identifier, hyphen and em dash separator).
   - Milestone heading beneath its requirement: `### PREFIX-1-M1 — Short milestone title` (use sequential M1, M2, etc.).
   - Put ordinary, explicit acceptance-criteria bullets under the milestone.
   - Include this exact executable acceptance block for each milestone:
     `#### Acceptance`
     `- **Command:** ` followed by one literal command in inline backticks
     `- **Scope:** ` followed by one authorized, repository-relative literal path in inline backticks; add one Scope entry per path.
   - The Command value is parsed as an argv command and is not run through a shell. Do not use shell chaining, pipes, redirection, variable expansion or guessed command syntax.
   - Scope paths must be concrete relative paths, unique within that block, and must not use `..`, wildcards, absolute paths, or Git pathspec magic.
6. Never invent test commands, test frameworks, scripts, infrastructure, APIs, repository files, product capabilities, dependencies, versions, deployment targets, credentials or available services. Use only commands and capabilities established by my answers or supplied repository documentation. If a valid acceptance command or path cannot yet be established, identify the exact missing decision in a clearly marked `OPEN DECISIONS — HUMAN INPUT REQUIRED` section, explain what evidence is needed, and do not disguise a placeholder or guessed command/path as executable. Tell me that unresolved values must be completed and verified before planning.
7. Identify missing decisions, external/internal dependencies, assumptions, risks and non-goals. Distinguish confirmed facts from assumptions. Keep unknowns visible; do not resolve them by choosing a convenient default.
8. Make the final Markdown self-contained and complete: include project outcome, scope/non-goals, requirement and milestone IDs, dependencies/order, criteria, authorized paths, acceptance commands where verified, and open decisions. Do not omit content with ellipses or say “continue similarly.” Add no prose outside the draft when I request the final document.

Before drafting, ask your clarification questions. After I answer, summarize any remaining unresolved items and produce the complete Markdown draft. If I ask you to draft before answering, proceed only with explicit assumptions and an open-decisions section; never fabricate executable validation commands or authorized paths.
```

The prompt deliberately asks the model not to guess. Acceptance commands are consequential: Projectwright uses the configured command during explicit milestone acceptance. Confirm each command exists, is safe to run in your environment, and validates the stated outcome. If the repository does not yet establish a command or path, resolve that decision yourself before planning; do not leave a placeholder that looks executable.

## Requirements structure

Use uppercase IDs and an em dash (or hyphen) between each ID and title. Requirement headings begin with `##`; milestones begin with `###`, and milestone IDs use `-M1`, `-M2`, and so on. For example, `DEMO-1` may contain milestones `DEMO-1-M1` and `DEMO-1-M2`.

For strict milestone acceptance, each milestone needs an `#### Acceptance` subsection with exactly one `Command` entry and one or more `Scope` entries. The acceptance subsection may contain only those list entries. Keep human-readable acceptance criteria in ordinary bullets outside that subsection. A simplified shape is:

```markdown
## DEMO-1 — A verified project outcome

### DEMO-1-M1 — Deliver the first useful increment
- The user-visible behavior is observable and documented.
- The relevant failure case is handled.

#### Acceptance
- **Command:** `REPLACE WITH A VERIFIED COMMAND`
- **Scope:** `path/to/authorized/file`
- **Scope:** `path/to/authorized/test`

### DEMO-1-M2 — Add the next independently testable increment
- This builds on the accepted M1 behavior.

#### Acceptance
- **Command:** `REPLACE WITH A VERIFIED COMMAND`
- **Scope:** `path/to/authorized/file`
```

This is a format illustration, not a valid ready-to-run specification: replace every illustrative command and path with verified values for your repository. Projectwright validates requirement/milestone heading syntax and acceptance policy when planning; diagnostics must be resolved before planning can proceed. See [workflow and milestone gates](workflow.md) for acceptance-policy details.

## End-to-end manual workflow

Use an existing, initialized Git worktree with a named branch and a HEAD commit. Projectwright state and the application repository are distinct: by default, state is under `$XDG_CONFIG_HOME/projects/<id>/` (normally `~/.config/projects/<id>/`), while the repository can be at a path such as `~/repos/myproject`. `pw init --repo` connects the two; it does not clone, initialize or otherwise modify the Git repository. One Projectwright project coordinates one worktree, not multiple repositories as a single task.

1. Describe the project to Hermes or another LLM and answer its clarification questions.
2. Review the complete requirements draft, verify its commands and paths, settle decisions, and save it at `<project-state>/requirements.md`.
3. Initialize the Projectwright project against your existing repository:

   ```sh
   pw init --project myproject --repo ~/repos/myproject
   ```

4. If using the default state root, save/copy the reviewed draft to `~/.config/projects/myproject/requirements.md`. If using a different configuration home, pass the same absolute `--config-dir /absolute/config/home` to commands; the project state is in its `projects/myproject/` subdirectory.
5. Explicitly authorize planning and request a planning pass:

   ```sh
   pw plan --project myproject
   ```

   This enables planning only. It does not run a worker or enable execution. Planning requires valid requirements, a usable configured Git worktree and an available planner/provider.
6. Inspect status and blockers, then read `queue.md` in the project-state directory. Check that tasks match the requirements and remain within intended scope. Do not treat a proposed queue as permission to execute.

   ```sh
   pw status --project myproject
   ```

7. When ready, authorize a single manual dispatcher run interactively:

   ```sh
   pw start --project myproject
   ```

   Confirm the prompt. This is a one-run authorization and does not set persistent execution or install a timer. In a supervised non-interactive invocation, `pw start --project myproject --yes` is the explicit confirmation.
8. Review `pw status`, the work log/results, and `git diff`. Run or inspect the relevant tests. Completed tasks, commits, and passing tests do not themselves constitute milestone acceptance.
9. Explicitly review and approve or reject milestone acceptance when presented. Telegram approvals are optional. If configured, authorized recipients can use the notification's Approve/Reject buttons; without that integration, the gate remains blocked until a human decision is made through the available operator workflow. See [Telegram approval setup](user-approval-setup.md).
10. Resolve blockers, revise and re-review requirements if scope changes, then plan and inspect the queue again before manually starting another task. Repeat testing and human milestone approval until all work is complete.

The actual onboarding commands and flags are documented in the [`pw` CLI reference](cli.md). Other commands such as `pw tick` intentionally use the dispatcher path; do not substitute them for the explicit reviewed-queue/manual-start workflow unless you understand their behavior.

## Manual runs and recurring execution are different

`pw start` asks for confirmation and runs one manually authorized dispatcher cycle; it does not change `execution.enabled`, install a timer, or enable unattended recurrence. Repeat `pw start` when you have reviewed and authorized another manual cycle.

Recurring execution is a separate opt-in. It requires persistent execution authorization and separate installation and activation of a per-project systemd user timer:

```sh
pw authorize-execution --project myproject --yes
pw timer install-disabled myproject
pw timer enable myproject
```

`pw authorize-execution` changes the persistent project setting but does not schedule anything. `install-disabled` writes timer/service units without enabling the timer; `enable` activates the installed timer. Inspect or stop it with `pw timer status myproject` or `pw timer disable myproject`. Do not perform these recurring-execution steps unless unattended operation is intended. Review the [operator manual](manual.md) first.

## State, repository, and configuration paths

- Projectwright state: `$XDG_CONFIG_HOME/projects/<project-id>/`, normally `~/.config/projects/<project-id>/`. This contains `config.json`, `requirements.md`, `queue.md`, work logs and runtime state.
- Git worktree: the repository path supplied to `pw init --repo`; it can be outside the state directory. Projectwright does not make a duplicate worktree during initialization.
- Alternate configuration home: use the same absolute `--config-dir /absolute/config/home` for each `pw` command; Projectwright appends `projects/<project-id>` beneath it. Existing legacy roots are resolved according to the rules in [configuration-home.md](configuration-home.md); they are not migrated or deleted.

If your project ID is `myproject` and you use defaults, the requirements file is `~/.config/projects/myproject/requirements.md`; the repository could independently be `~/repos/myproject`. Keep source/test paths in acceptance scope relative to the Git worktree, not relative to the state directory.

## Optional Telegram approval

Telegram approval is an optional integration, but this workflow's human acceptance callback requires it to be configured and enabled. Without that integration, milestone acceptance remains blocked; do not treat task completion or a test pass as acceptance. See [user-approval-setup.md](user-approval-setup.md).

