# Running Projectwright tests on tux without exposing production Hermes

## Intended layout

Use a **dedicated disposable VM** hosted on tux, with its own unprivileged runner account and empty home directory. The host must **not** install the GitHub Actions runner as the normal `leftyfb` account or grant access to `~/.hermes`, Docker socket, SSH agent, Home Assistant tokens, production project folders, sudo, or host systemd user services.

The `.github/workflows/tux-isolated.yml` job is *manual-only*. It runs the same offline checks as GitHub-hosted CI, but on the isolated runner with a temporary HOME and project root. It uploads test logs as seven-day GitHub Actions artifacts, **not Git commits**.

This does **not** validate the actual running Hermes daemon, real Telegram, HA quotas, or systemd timers. Those require a separate, explicitly approved local integration procedure after offline tests are green.

## One-time setup (human-operated)

1. Provision a small Ubuntu VM on tux with Python 3.14, Git, outbound HTTPS and a non-sudo service account `pw-runner`. Keep VM host mounts and host sockets absent; restrict network access to services not required by the tests.
2. In GitHub, open **Settings → Actions → Runners → New self-hosted runner** for `leftyfb/projectwright`. Follow GitHub's **current Linux x64** instructions *inside the VM* as `pw-runner`. Generate the short-lived registration token in GitHub; do **not** paste the token into chat or commit it.
3. Register the custom runner label `projectwright-isolated` in addition to GitHub's automatic `self-hosted`, `linux`, `x64` labels. Avoid giving a generic runner this label. Never select a host-level runner under the same label.
4. Prefer an **ephemeral** runner/VM that is reset after every job, with no persistent secrets or writable shared files. For a persistent VM, wipe the checkout/work directory and rotate the runner as appropriate between jobs.
5. When the workflow is present on the repository default branch, use **Actions → Tux isolated verification → Run workflow** and select the intended development ref. GitHub requires a workflow-dispatch workflow to exist on the default branch before manual dispatch can be selected. Until this file is promoted to `main`, it is a proposed workflow and cannot be launched this way.
6. Review the GitHub Actions job result and artifact **tux-offline-logs-<run id>-<attempt>**. Artifacts expire after seven days; still avoid emitting secrets into logs.

## Safety boundaries

- No automatic trigger for the tux workflow, including `push` or `pull_request`.
- No live Telegram, Home Assistant, Hermes CLI, systemd, project credentials or production worktree.
- No privileged runner and no Docker socket.
- Only run code you trust: a self-hosted runner executes arbitrary code from whichever revision the workflow checks out.
- The isolated runner is for environmental parity, **not** live-host integration. Full real-host verification needs a separate reviewed harness.
- Do not use runner registration credentials or a broad personal GitHub token in test scripts.

## Separate issue

The latest tux result reports a failure in `test_cycle_gate_ignores_poisoned_global_queue_manager_module`. Treat that independently; adding this workflow does not fix the test or the underlying logic.
