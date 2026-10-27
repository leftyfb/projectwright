# Public repository readiness and visibility gate

**Status: preparation in progress. Do not switch visibility to public until every blocker below is resolved.**

GitHub's private-to-public conversion exposes all reachable branches, tags, full Git history, pull requests, and Actions logs. Removing a file from the current branch does not remove it from history. Public repositories may receive untrusted pull requests; a persistent self-hosted runner must not be attached to that trust boundary.

## Completed in this preparation branch

- [x] Replace outdated development-only README status with published `0.1.0` installation instructions and explicitly state that no signed APT feed exists yet.
- [x] Add security-reporting and contributor guidance.
- [x] Remove the legacy self-hosted `pw-test` and `tux` workflow definitions from the proposed default branch while preserving the historical commits for traceability. **This does not deactivate an existing runner or remove those workflows from old branches/tags.**

## Blocking before visibility changes

- [ ] **Disconnect/delete the `pw-test` repository self-hosted runner in GitHub Settings → Actions → Runners**, and verify no persistent runner or production Hermes machine is registered. The operator must perform/verify this in GitHub; deleting workflows alone is insufficient.
- [ ] **Audit the full Git history and every branch/tag**, including deleted-file history, Actions artifacts/logs, PR comments and committed fixtures, for secrets or private data. The GitHub connector cannot furnish an authenticated full clone or inspect private secret stores. Rotate any accidentally exposed credentials before publication; history rewriting requires a separately approved plan.
- [ ] **Choose and add an explicit OSS LICENSE** (e.g. MIT or Apache-2.0) with copyright holder approval. Without a license, public visibility does not grant reuse rights.
- [ ] Review every historical internal reference (`tux`, `pw-test`, local paths and identities) and decide whether their disclosure is acceptable; remove machine-specific testing instructions from active public docs if unnecessary.
- [ ] Review GitHub repository settings: default-branch protection/rulesets, Actions fork-PR approval, token permissions, secret access, environments, Pages publishing and private vulnerability reporting.
- [ ] Confirm `0.1.0` release notes, Debian artifact, `SHA256SUMS`, package contents, Python/Hermes dependency policy, and supported Ubuntu versions are public-safe.
- [ ] Independently review the proposed changes and run hosted CI before merging; **do not modify the existing `0.1.0` tag**.

## After visibility changes

Publish a signed GitHub Pages APT repository with `Packages`, `Release`/`InRelease`, package retention, a publicly distributed signing key, and an automated update path from verified GitHub Releases. Test repository-based install and upgrade on Ubuntu 24.04 and 26.04. Until this exists, instruct users to install the checked `.deb` manually.
