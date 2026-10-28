"""Offline APT repository generation and release-integrity regressions."""

import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/build-apt-repository.py"
SPEC = importlib.util.spec_from_file_location("projectwright_apt_builder", MODULE_PATH)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


@unittest.skipUnless(shutil.which("dpkg-deb") and shutil.which("apt-ftparchive"),
                     "Debian APT packaging tools unavailable")
class AptRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="projectwright-apt-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.releases = self.root / "releases"
        self.releases.mkdir()

    def make_release(self, version):
        release = self.releases / version
        release.mkdir()
        stage = self.root / ("stage-" + version)
        (stage / "DEBIAN").mkdir(parents=True)
        (stage / "DEBIAN/control").write_text(
            f"Package: projectwright\nVersion: {version}-1\n"
            "Architecture: all\nMaintainer: Fixture <fixture@example.invalid>\n"
            "Description: Disposable APT test fixture\n")
        filename = f"projectwright_{version}-1_all.deb"
        package = release / filename
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(stage), str(package)],
                       check=True, capture_output=True)
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        (release / "SHA256SUMS").write_text(f"{digest}  {filename}\n")
        return package

    def test_verified_releases_make_installable_indexes(self):
        self.make_release("0.1.0")
        self.make_release("0.1.1")
        output = self.root / "site"
        self.assertEqual(BUILDER.build(self.releases, output, "Projectwright", "stable"), 2)
        for arch in ("amd64", "arm64"):
            index = (output / f"dists/stable/main/binary-{arch}/Packages").read_text()
            self.assertEqual(index.count("Package: projectwright"), 2)
            self.assertIn("Version: 0.1.0-1", index)
            self.assertIn("Version: 0.1.1-1", index)
            self.assertIn("pool/main/p/projectwright/", index)
            self.assertTrue((output / f"dists/stable/main/binary-{arch}/Packages.gz").is_file())
        release = (output / "dists/stable/Release").read_text()
        self.assertIn("Architectures: amd64 arm64", release)
        self.assertIn("SHA256:", release)
        self.assertTrue((output / ".nojekyll").exists())

    def test_refuses_modified_package_and_nonversion_directory(self):
        package = self.make_release("0.1.0")
        package.write_bytes(package.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            BUILDER.build(self.releases, self.root / "site", "Projectwright", "stable")
        shutil.rmtree(self.releases / "0.1.0")
        (self.releases / "v0.1.0").mkdir()
        with self.assertRaisesRegex(ValueError, "version-only"):
            BUILDER.build(self.releases, self.root / "site", "Projectwright", "stable")

    def test_refuses_nonempty_output(self):
        self.make_release("0.1.0")
        output = self.root / "site"
        output.mkdir()
        (output / "old-index").write_text("stale")
        with self.assertRaisesRegex(ValueError, "empty directory"):
            BUILDER.build(self.releases, output, "Projectwright", "stable")

    def test_refuses_package_version_different_from_release(self):
        package = self.make_release("0.1.0")
        other = self.make_release("0.1.1")
        package.write_bytes(other.read_bytes())
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        (package.parent / "SHA256SUMS").write_text(f"{digest}  {package.name}\n")
        with self.assertRaisesRegex(ValueError, "Debian Version mismatch"):
            BUILDER.build(self.releases, self.root / "site", "Projectwright", "stable")


if __name__ == "__main__":
    unittest.main()
