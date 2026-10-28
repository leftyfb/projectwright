# Maintainer release procedure

Projectwright source and release automation live in the **public** repository.
That is intentional: build instructions, checks, and publishing policy should be
reviewable. Never put a signing key, passphrase, GitHub token, or Hermes/Telegram
credential in a release script, source commit, test, or workflow output.
GitHub Actions stores the APT signing material as configured secrets.

## What happens automatically

- **Development pull request into `main`:** required `offline` CI verifies
  regression tests, Python wheel and development Debian package. Merging the
  PR triggers `main` CI again. A merge by itself **does not** create a release,
  publish a tag, or touch the APT signing key.
- **Approved release publication:** the manual **Publish Projectwright release**
  workflow checks the exact tested `release/X.Y.Z` source commit, successful
  hosted Ubuntu 24.04/26.04 package matrix, version metadata, checksums, and
  absence of an existing release. It then creates the **version-only** tag
  `X.Y.Z` and publishes the exact tested Debian artifact.
- **After that workflow succeeds:** **Publish signed Projectwright APT repository**
  automatically downloads and verifies all stable release packages, regenerates
  and signs indexes, and deploys to GitHub Pages. A cancelled or failed release
  workflow does not authorize this operation.
- **Recovery:** the APT publishing workflow can still be dispatched manually
  from `main` with the confirmation `publish-apt`. No subscriber must edit
  their APT sources or re-import the signing key for a routine package update.

There is no trusted automatic rule that considers every commit to `main` a
stable release. Keeping a separate maintainer-reviewed release gate avoids
publishing unversioned development code and accidental signing-key use.

## From development branch to published Debian package

1. Open a PR from the development branch to `main`. Review the diff,
   confirm the required `offline` check passes, and merge. Do not bypass
   branch protection. Verify the post-merge `main` CI succeeds.
2. Create `release/X.Y.Z` **from current `main`** using GitHub's branch UI
   (or your normal Git client). The literal version must have three numeric
   components with **no `v` prefix**, and no existing tag/release may have it.
3. On the release branch, set the project's `version` in `pyproject.toml`
   to `X.Y.Z`. Update the version in `scripts/build-deb.sh` to `X.Y.Z-1`
   for both the Debian control field and output filename. Write the
   version-specific `docs/release-notes.md`, including changes, requirements,
   installation, known limitations, and any deferred testing. Keep everyday
   README/manual installation instructions version-independent.
4. Open **Actions → Ubuntu 24.04 and 26.04 Debian compatibility → Run
   workflow** and choose `release/X.Y.Z`. All three hosted jobs must pass:
   build/regression tests, Ubuntu 24.04 install/CLI/purge, and Ubuntu 26.04
   install/CLI/purge. Record this run ID and verify its **head SHA is exactly
   the current release-branch head**. Any release-branch change means rerun
   this matrix.
5. Open **Actions → Publish Projectwright release → Run workflow**.
   **Choose `main`**, not the release branch. Provide:
   - `version`: `X.Y.Z`
   - `source_sha`: complete 40-character SHA from step 4
   - `artifact_run_id`: successful workflow run ID from step 4

   This workflow does not rebuild a different source. It verifies the exact
   tested package artifact and refuses mismatches before tagging/publishing.
6. Wait for the release workflow to succeed and verify its GitHub Release has
   `projectwright_X.Y.Z-1_all.deb` and `SHA256SUMS`. The successful workflow
   automatically triggers the signed APT publishing workflow; verify that
   workflow and its GitHub Pages deployment also succeed.
7. On a disposable or otherwise authorized supported Ubuntu installation
   already subscribed to the signed feed, check:

   ```sh
   sudo apt update
   apt policy projectwright
   sudo apt upgrade
   dpkg-query -W projectwright
   ```

   A newer candidate should appear without changing the APT source or key.

Do not rewrite or reuse an existing version-only tag, replace release assets,
publish from an unreviewed branch, or dispatch the signing workflow from a PR.
Only Ubuntu **24.04** and **26.04** are supported. The hosted matrix is not a
substitute for every manual Hermes/Telegram or platform integration test.

## Optional command-line operations

These exact steps can be performed with the GitHub web UI; no local release
script or privileged workstation is required. Maintainers who prefer CLI
automation may use the official `gh` command and `git` after authenticating
their own account, but should keep the source-SHA verification and publication
approval separate. A public helper script would be appropriate if it contains
**only** these operations and no credentials; the repository's reviewed
GitHub Actions workflows remain the publishing authority.
