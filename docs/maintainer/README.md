# Developer and maintainer documentation

**This section is for contributors and Projectwright repository maintainers, not users installing or running `pw`.**

If you just want to use Projectwright, return to the [README](../../README.md), which contains the complete APT installation, first-project setup, Task Tracker walkthrough, approval, and scheduling instructions. You do **not** need anything below.

## Build, package, and publish Projectwright

- [Contributing guidelines](../../CONTRIBUTING.md) — changes, test requirements, and pull requests
- [Package building and distribution](../packaging-and-operations.md) — how source becomes the wheel and Debian package
- [Signed APT repository publishing](apt-publishing.md) — maintainer signing keys, CI secrets, release metadata, and recovery
- [Release procedure](../release-process.md) — branch/tag/release workflow
- [Release checklist and test record](../release-checklist.md) — maintainer validation history

## Source, CI, and internal design

- [Architecture](../architecture-current.md)
- [Module and source inventory](../file-reference.md)
- [Runtime entrypoints](../runtime-entrypoints.md)
- [Baseline validation](../baseline-validation.md)
- [Test coverage](../test-coverage-matrix.md)
- [Engineering notes](../technical-debt.md)

These are reference material for developing and maintaining Projectwright itself. GitHub Actions configuration, signing-key generation, packaging internals, and repository publishing are intentionally **not part of the end-user setup instructions**.
