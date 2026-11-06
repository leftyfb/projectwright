# Projectwright 0.2.7

Projectwright 0.2.7 improves first-time onboarding, Git initialization, local milestone approvals, and timer authorization.

## Changes

- Introduces `pw approve MILESTONE-ID` for local human approval without Telegram, using the existing acceptance guard and recorded Git/task evidence.
- Updates `pw status` to name the milestone awaiting approval and show the matching `pw approve` command.
- Makes `pw init` automatically create a clean initial Git commit for brand-new, empty repositories. Existing repositories retain their history and require the operator to review and commit any `.gitignore` changes. Failed automatic initial commits produce explicit recovery instructions and a nonzero exit.
- Makes `pw authorize-execution` install a disabled per-project systemd timer before enabling recurring-execution authorization, and clearly explains that scheduling only starts after `pw timer enable PROJECT`.
- Reworks the README around an introductory workflow diagram, tasks/milestones/approvals, and complete new-project and Task Tracker walkthroughs.
- Places signed APT source and signing-key verification directly in the README; separates maintainer packaging and release procedures.

## Requirements

- Ubuntu 24.04 or 26.04 LTS; Ubuntu 22.04 is not supported.
- A separately installed and configured Hermes CLI.
- Git and Python 3; systemd user services for optional scheduled execution.
- Telegram integration remains optional.

## Installation and upgrade

Follow the signed APT repository setup and pinned key fingerprint verification in the [main README](https://github.com/leftyfb/projectwright#1-install). Then:

```sh
sudo apt update
sudo apt install projectwright
pw setup
```

Run `pw setup` as your normal user, not with `sudo`. The release also attaches a versioned Debian package and `SHA256SUMS`. Package installation does not activate Hermes plugins, user timers, or application project execution.

## Verification and limitations

The published artifact must pass the exact-version Ubuntu 24.04 and Ubuntu 26.04 hosted compatibility matrix before release publication. The hosted CI checks cannot substitute for every manual Hermes, Telegram, or production-environment integration test. Human milestone approval is still required, even with recurring execution enabled.
