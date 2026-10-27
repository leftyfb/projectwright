# Public repository readiness and visibility gate

**Status: preparation in progress. Do not switch visibility to public until every blocker below is resolved.**

GitHub's private-to-public conversion exposes all reachable branches, tags, full Git history, pull requests, and Actions logs. Removing a file from the current branch does not remove it from history. Public repositories may receive untrusted pull requests; a persistent self-hosted runner must not be attached to that trust boundary.

## Completed in this preparation branch

- [x] Replace outdated development-only README status with published `0.1.0` installation instructions and explicitly state that no signed APT feed exists yet.
- [x] Add an MIT LICENSE, security-reporting and contributor guidance.
- [x] Run the first read-only history scan on a GitHub-hosted runner: [Actions run 40517774799](https://github.com/leftyfb/projectwright/actions/runs/40517774799) checked 687 reachable Git blobs and 695 retained Actions run log archives with **no matches** for the scanner's credential patterns. 31 of 726 Actions runs returned inaccessible logs; the job intentionally reports an incomplete audit rather than a clean pass. The private summary artifact expires after seven days.
- [x] Remove the legacy self-hosted `disposable-test-container` and `isolated-test-host` workflow definitions from the proposed default branch while preserving the historical commits for traceability. **This does not deactivate an existing runner or remove those workflows from old branches/tags.**

## Blocking before visibility changes

- [x] **Runner removal reported by the maintainer:** both former self-hosted runners were deleted from GitHub and locally. Before visibility changes, visually confirm that Settings → Actions → Runners shows no registered runners; this integration cannot inspect the administrative runner inventory.
- [ ] **Complete the disclosure review for unavailable historical material:** investigate the 31 inaccessible Actions log archives, expired artifacts, issue/PR discussion content and any unreachable/dangling Git history. The automated scan covered all reachable branch/tag Git blobs but detects only defined token formats; manual review of private project details remains necessary. Rotate credentials if subsequently identified; history rewriting needs a separately approved plan.
- [x] **Choose and add an OSS LICENSE:** MIT, copyright (c) 2026 Mike Rushton, in this preparation PR.
- [x] Remove machine-specific names and retired live-test utilities from the active tree. Historical Git commits and old Actions logs can still reveal those names; removing them from Git history would require an explicit history-rewrite decision.
- [ ] Review GitHub repository settings: default-branch protection/rulesets, Actions fork-PR approval, token permissions, secret access, environments, Pages publishing and private vulnerability reporting.
- [ ] Confirm `0.1.0` release notes, Debian artifact, `SHA256SUMS`, package contents, Python/Hermes dependency policy, and supported Ubuntu versions are public-safe.
- [ ] Independently review the proposed changes and run hosted CI before merging; the offline regression suite passed on [run 40517242022](https://github.com/leftyfb/projectwright/actions/runs/40517242022). **Do not modify the existing `0.1.0` tag.**

## After visibility changes

Publish a signed GitHub Pages APT repository with `Packages`, `Release`/`InRelease`, package retention, a publicly distributed signing key, and an automated update path from verified GitHub Releases. Test repository-based install and upgrade on Ubuntu 24.04 and 26.04. Until this exists, instruct users to install the checked `.deb` manually.
