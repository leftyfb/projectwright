# Public repository readiness and visibility gate

**Status: preparation in progress. Do not switch visibility to public until every blocker below is resolved.**

GitHub's private-to-public conversion exposes all reachable branches, tags, full Git history, pull requests, and Actions logs. Removing a file from the current branch does not remove it from history. Public repositories may receive untrusted pull requests; a persistent self-hosted runner must not be attached to that trust boundary.

## Completed in this preparation branch

- [x] Replace outdated development-only installation instructions with a latest-release link and version-independent package guidance and explicitly state that no signed APT feed exists yet.
- [x] Add an MIT LICENSE, security-reporting and contributor guidance.
- [x] Complete automated history and Actions-log pattern scans: 705 reachable Git blobs and 699 available Actions log archives were scanned, with zero credential-pattern matches. Of 30 initially unavailable log archives, 28 older failed runs had no GitHub jobs and therefore no job logs; the other two were running or newly completed at scan time. These results support, but cannot prove, absence of credentials. The scanner intentionally does not print secret values.
- [x] Remove the legacy self-hosted `disposable-test-container` and `isolated-test-host` workflow definitions from the proposed default branch while preserving the historical commits for traceability. **This does not deactivate an existing runner or remove those workflows from old branches/tags.**

## Blocking before visibility changes

- [x] **Runner removal reported by the maintainer:** both former self-hosted runners were deleted from GitHub and locally. Before visibility changes, visually confirm that Settings → Actions → Runners shows no registered runners; this integration cannot inspect the administrative runner inventory.
- [x] **Triage unavailable Actions logs:** 28 runs had no jobs, and two were transient; no evidence of exposed credentials was found. GitHub artifacts, issue/PR discussions, dangling objects and non-pattern secrets remain manual disclosure-review considerations; do not claim exhaustive coverage or rewrite published history without separate authorization.
- [x] **Choose and add an OSS LICENSE:** MIT, copyright (c) 2026 Mike Rushton, in this preparation PR.
- [x] Remove machine-specific names and retired live-test utilities from the active tree. Historical Git commits and old Actions logs can still reveal those names; removing them from Git history would require an explicit history-rewrite decision.
- [ ] Review GitHub repository settings: default-branch protection/rulesets, Actions fork-PR approval, token permissions, secret access, environments, Pages publishing and private vulnerability reporting.
- [ ] Confirm `0.1.0` release notes, Debian artifact, `SHA256SUMS`, package contents, Python/Hermes dependency policy, and supported Ubuntu versions are public-safe.
- [ ] Independently review the proposed changes and run hosted CI before merging; the offline regression suite previously passed on [run 40517242022](https://github.com/leftyfb/projectwright/actions/runs/40517242022); require a fresh green run at the final PR head. **Do not modify the existing `0.1.0` tag.**

## After visibility changes

Publish a signed GitHub Pages APT repository with `Packages`, `Release`/`InRelease`, package retention, a publicly distributed signing key, and an automated update path from verified GitHub Releases. Test repository-based install and upgrade on Ubuntu 24.04 and 26.04. Until this exists, instruct users to install the checked `.deb` manually.

## Maintainer disclosure tool

`scripts/audit-public-disclosure.py` remains a **manual, read-only maintainer tool**, not a Debian package asset or routine CI check. The opt-in `.github/workflows/public-history-audit.yml` invokes it on a hosted runner when explicitly dispatched. It scans reachable Git blobs and available Actions log ZIPs for selected token patterns and sensitive filenames, writes `public-disclosure-audit.json`, and prints only categories, locations and counts. Exit status 0 means no detected matches and no reported gaps; 2 means potential findings; 3 means incomplete coverage. It does **not** inspect unreachable Git objects, unavailable archives, expiring artifacts or arbitrary unrecognized secrets. Review reports privately because filenames and run IDs may still convey internal history. Do not enable it on public untrusted pull requests or add it to routine CI.
