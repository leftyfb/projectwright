# Signed APT repository (maintainer setup and subscriber guide)

The signed repository is published at `https://leftyfb.github.io/projectwright/`.
Projectwright can be installed and upgraded through ordinary Ubuntu APT once the
subscriber has configured the source and verified its archive signing key.
Initial deployment and key provisioning are complete; the maintainer setup below
is retained for recovery and future key rotation.

## Repository format and trust boundary

- Suite `stable`, component `main`, architectures `amd64` and `arm64`. The
  `projectwright` Debian package itself has `Architecture: all`.
- `pool/main/p/projectwright/` retains each verified, version-only GitHub
  Release `.deb`, beginning with the existing `0.1.0` package unchanged.
- `dists/stable/` contains `Release`, `InRelease`, `Release.gpg`, and compressed
  and uncompressed `Packages` indexes for each supported architecture.
- Only the separate APT **metadata** is signed. The `.deb` integrity is bound
  to the signed metadata via SHA-256 hashes. No private signing key is placed in
  Git, the published Pages site, the Debian package, or CI test fixtures.
- Releases are downloaded afresh; each release's `SHA256SUMS` is checked before
  indexing. The generator also validates the Debian package name, version and
  architecture and refuses changed/mismatched artifacts.

## Maintainer: initial setup (already completed)

1. Create a dedicated **APT-only** GPG signing key on a trusted maintainer
   system. Keep a protected offline recovery copy. Do not reuse Git commit,
   Hermes, Telegram or personal email-signing credentials.
   For example, on a trusted Linux machine with GnuPG installed:

   ```sh
   gpg --quick-generate-key 'Projectwright APT Archive' rsa4096 sign 2y
   gpg --list-secret-keys --with-fingerprint
   ```

   Record the primary key's 40-character fingerprint. Substitute it for
   `FINGERPRINT` below, and transfer the private export **only** to the Actions
   secret through GitHub's protected Settings UI:

   ```sh
   umask 077
   gpg --armor --export-secret-keys FINGERPRINT | base64 -w0 > projectwright-apt-key.b64
   ```

   This file contains sensitive private-key material. Never commit, email or
   attach it to an issue, PR or chat. Remove the temporary export securely
   after confirming the secret is configured; retain a separately protected
   recovery backup. Store a passphrase in the separate Actions secret.
2. In repository **Settings → Secrets and variables → Actions**, configure:
   - Secret `APT_SIGNING_KEY_B64`: base64-encoded exported **private** key.
   - Secret `APT_SIGNING_PASSPHRASE`: key passphrase, if one was set.
   - Variable `APT_SIGNING_FINGERPRINT`: the exact 40-hex-character fingerprint
     of that key. Verify it independently before distributing the public key.
3. In **Settings → Pages**, set *Build and deployment → Source* to **GitHub
   Actions**. Confirm the `github-pages` environment allows the intended
   maintainer deployment workflow.
4. For initial deployment or a recovery republish, manually dispatch
   **Publish signed Projectwright APT repository** from `main` and enter
   `publish-apt` as the confirmation. Never dispatch it from a PR or
   unreviewed branch. Normal release publication triggers this workflow
   automatically after its guarded release-publishing workflow succeeds.
5. Inspect the public key fingerprint, signatures, indexes and downloaded
   package checksums from the deployed site. The hosted Ubuntu 24.04/26.04
   container matrix is part of each release gate; an APT install and upgrade
   on Ubuntu 26.04 has also been verified. Manual Ubuntu 24.04 APT install
   testing remains deferred.

A successful run of **Publish Projectwright release** triggers APT republishing
through GitHub Actions `workflow_run`. A failed, cancelled or untrusted run
cannot trigger signing; merging a PR to `main` alone does not publish a release
or touch the signing key. Maintainers retain an explicit manual dispatch for
recovery. The APT job rebuilds indexes from **all** published stable version-only
release assets; it never rebuilds or overwrites the GitHub Release packages.
Release assets must provide the expected `.deb` and `SHA256SUMS`.

See [release procedure](release-process.md) for the supported development-to-release
sequence and explicit release authorization controls.

The workflow fails closed if the signing key, fingerprint, release assets, or
package verification are missing. Manual recovery runs additionally require the
exact confirmation text; automatic runs require a successful manually dispatched
release-publishing workflow on `main`. It requires Pages deployment
permissions only in the deployment job. The signing private key is restricted to
the build job, and the public key is exported to the Pages output.

## Subscriber: installation and updates

Check the signing fingerprint against a maintainer-published value over an
independent channel; **do not trust the downloaded key solely because the file
is served over HTTPS**. After verification, on supported Ubuntu systems:

```sh
curl -fsSLo projectwright-archive-keyring.gpg \
  https://leftyfb.github.io/projectwright/projectwright-archive-keyring.gpg
gpg --show-keys --with-fingerprint projectwright-archive-keyring.gpg
sudo install -m 0644 projectwright-archive-keyring.gpg \
  /usr/share/keyrings/projectwright-archive-keyring.gpg
echo 'deb [signed-by=/usr/share/keyrings/projectwright-archive-keyring.gpg] https://leftyfb.github.io/projectwright/ stable main' \
  | sudo tee /etc/apt/sources.list.d/projectwright.list
sudo apt update
sudo apt install projectwright
pw setup
```

Run `pw setup` as the ordinary Hermes user, never under `sudo`. Hermes is
required but installed/configured separately. Telegram approval remains
optional and requires confirmation. Future upgrades use ordinary `apt upgrade`
after the signed repository is republished with a verified newer release.

## Release and key lifecycle

- Keep published old package versions in the pool for controlled rollback and
  upgrade tests. Test the first repository-based upgrade from `0.1.0` to a
  subsequently published version; do not create a replacement `0.1.0`.
- If a signing key must rotate, publish an authenticated transition announcement
  and explicitly install the replacement key; do not silently overwrite trust.
- When removing the repository from a machine, remove the dedicated `.list`
  and keyring files after reviewing any other consumers, then `apt update`.
- GitHub Pages is a distribution channel, not the package signing authority.
  Keep the signing private key and recovery material outside GitHub Pages.
