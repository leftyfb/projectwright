# Projectwright 0.2.6

Maintenance and distribution release since 0.2.5.

## Changes

- Run immediate planner by installed script path in both source and packaged gateways
- Expect immediately pinned but undelivered milestone approval in offline task-tracker test
- Align automatic planning and approval status guidance with immediate transitions
- Show the next queued TEST or COMMIT task in automatic status action
- Keep milestone approvals independent of worker progress Telegram preference
- Keep Git subprocess behavior intact in immediate notifier regression test
- Test immediate final-task approval delivery and durable failure handling
- Cover scoped immediate planning and retryable planning failures
- Test immediate replanning from approved Telegram callback
- Request verified milestone approval immediately after final worker task
- Plan the next milestone immediately following verified Telegram approval
- Clarify expected active Git-cycle status action
- Update timer minimum and compatibility tests for new install API
- Update timer minimum and compatibility tests for new install API
- Update timer minimum and compatibility tests for new install API
- Clarify timer install and enable in prominent automatic quickstart
- Clarify timer install and enable in prominent automatic quickstart
- Clarify timer install and enable in prominent automatic quickstart
- Fix test fixture queue newlines and Python continuation
- Regression-test busy status and live embedded journal task display

## Requirements

- Ubuntu 24.04 and 26.04 LTS. Ubuntu 22.04 is not supported.
- Hermes CLI and per-user configuration are required and installed separately.
- Telegram approvals are optional and require consent during `pw setup`.

## Installation and upgrade

Install the signed APT source using the [repository guide](https://github.com/leftyfb/projectwright/blob/main/docs/apt-repository.md), then run:

```sh
sudo apt update
sudo apt install projectwright
pw setup
```

The release also attaches the versioned Debian package and SHA256SUMS.
Package installation does not modify Hermes credentials or activate plugins or user timers. Refer to the packaging guide for removal and rollback.

## Verification

The exact tagged commit must pass the hosted Ubuntu 24.04/26.04 clean-install and purge matrix. Historical live Telegram callback tests do not guarantee all Hermes installations or configurations.
