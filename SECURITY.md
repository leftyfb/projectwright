# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for credential exposure, authorization bypass, unsafe execution, or other security vulnerabilities. Use GitHub's private vulnerability reporting feature if it is enabled for this repository; otherwise contact the maintainer privately through a contact channel they explicitly publish. Do not include tokens, `.env` contents, Telegram credentials, private worktree data, or GitHub Actions runner registration tokens in reports or public logs.

## Supported releases

The initial supported package line is `0.1.x` on Ubuntu 24.04 LTS and 26.04 LTS, with separately installed Hermes CLI. Ubuntu 22.04 is not supported. Security fixes may require upgrading Projectwright, Hermes, and the Telegram gateway environment independently.

## Trust boundaries

Projectwright can run provider-suggested commands in configured Git worktrees. Operators must review configuration and use disposable projects before enabling execution. Do not connect public pull-request workflows to persistent self-hosted machines, production Hermes, real Telegram credentials, or personal GitHub tokens. `pw setup` must not be executed as root and requires confirmation before Telegram integration is enabled.
