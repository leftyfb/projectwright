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
6. Use only commands, files, infrastructure, dependencies and capabilities established by my answers or supplied repository evidence as existing facts. For a greenfield project, you MAY propose tests, new test files, implementation paths, test frameworks or infrastructure as future deliverables when they help meet the stated goal. Mark each such item clearly as `PROPOSED — NOT IMPLEMENTED/VERIFIED`; distinguish it from existing, confirmed capabilities, and never claim a proposed or nonexistent test has run or is working. Do not silently turn a proposal into an accepted decision: ask me to confirm consequential choices, or list them under `OPEN DECISIONS — HUMAN INPUT REQUIRED`.
   - You may put proposed future paths and commands in the required `Scope` and `Command` entries so the requirements draft is complete, but precede each affected `#### Acceptance` block with an ordinary milestone bullet stating that the block is proposed and not yet verified. Such a block is a planning proposal, not authorization to execute. Before planning or acceptance, a human must verify the command's syntax, availability, safety and relevance; confirm framework/infrastructure choices; and confirm that proposed scope paths are implemented/tracked as required. If those checks cannot yet be done, keep the draft explicitly marked not ready for planning and explain what evidence or decision is missing.
   - Never invent an acceptance command and imply it already exists or passes. For an existing project, inspect supplied repository documentation or ask me for evidence before describing a command as verified. If proposing a command for a greenfield or not-yet-configured project, label it proposed and state its assumptions; don't say it works until it has actually been run successfully.
   - The Command value is parsed as argv and is not run through a shell. Avoid shell chaining, pipes, redirection, variable expansion and guessed syntax presented as verified. Scope paths must be concrete, relative, unique within the block, and must not use `..`, wildcards, absolute paths or Git pathspec magic.
7. Identify missing decisions, external/internal dependencies, assumptions, risks and non-goals. Distinguish confirmed facts from assumptions. Keep unknowns visible; do not resolve them by choosing a convenient default.
8. Make the final Markdown self-contained and complete: include project outcome, scope/non-goals, requirement and milestone IDs, dependencies/order, criteria, authorized paths, acceptance commands where verified, and open decisions. Do not omit content with ellipses or say “continue similarly.” Add no prose outside the draft when I request the final document.

Before drafting, ask your clarification questions. After I answer, summarize any remaining unresolved items and produce the complete Markdown draft. If I ask you to draft before answering, proceed only with explicit assumptions and an open-decisions section. Clearly label proposed commands and paths; never state that an unverified command exists, runs successfully, or is ready to execute.
```

The prompt distinguishes confirmed capabilities from proposals. Acceptance commands are consequential: Projectwright runs the configured command during milestone acceptance. A proposed command may appear in a greenfield draft as a future deliverable, but is not evidence that it exists or works, and is not authorization to run it. A human must verify its syntax, availability, safety and relevance, settle required framework/infrastructure decisions, and confirm paths before planning or acceptance. Keep unresolved decisions visible; do not disguise a placeholder as verified.

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

## End-to-end workflow: repository-local projects

Use the same repository-local workflow as the [README](../README.md). Projectwright state lives under `.pw/` inside the Git repository, not in a separate project directory.

1. Describe the intended application and ask Hermes or another LLM to draft incremental requirements using the prompt above.
2. Review every scope, command, and open decision. Save the completed requirements at `.pw/requirements.md`.
3. In a new project run `pw init ~/projects/myproject` followed by `cd ~/projects/myproject`. In an existing Git repository, run `pw init .` from the repository root.
4. Run `pw requirements --edit` to enter the reviewed draft. Commit your starting application files and ensure Git has a HEAD commit.
5. Choose strict milestone sequencing with `pw config set planning.milestone_sequence strict`, then run `pw plan`.
6. Review `pw status` and `cat .pw/queue.md`. Planning authorizes no worker execution.
7. To run one task with an interactive confirmation, run `pw start`; inspect `git status --short`, `pw status`, and `.pw/work_log.md` after each step.
8. When a milestone's tasks are complete, review its code, commits, and acceptance command; run `pw approve --milestone MILESTONE-ID` to approve it locally **without Telegram**. The approval guard verifies completed tasks, a clean Git tree, tracked authorized scope, and a passing acceptance command before recording a receipt.
9. Run `pw plan` after approval when there are additional milestones, and repeat the cycle.

## Optional unattended execution

Running `pw start` never enables a recurring schedule. To authorize persistent execution and create a **disabled** systemd user timer, run:

```sh
pw authorize-execution --yes --minutes 5
```

The command explicitly reports that the timer was created but left disabled and prints the activation command. Only when you are ready, run `pw timer enable myproject`. Use `pw timer status myproject` to inspect it and `pw timer disable myproject` to stop future activations. A completed milestone still requires local or Telegram approval; automatic execution does not bypass the guard.

For the concrete end-to-end sample see the [self-contained Task Tracker steps in the README](../README.md#3-try-the-complete-task-tracker-example). For advanced settings see the [CLI reference](cli.md).
