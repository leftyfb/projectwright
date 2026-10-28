#!/usr/bin/env python3
"""Build unsigned APT metadata from immutable, checksum-verified releases.

Signing is intentionally a separate maintainer-controlled publishing step.
"""

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess


VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
CHECKSUM = re.compile(r"([0-9a-fA-F]{64})  (projectwright_[^/\s]+_all\.deb)\Z")
ARCHITECTURES = ("amd64", "arm64")


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def validate_release(directory):
    version = directory.name
    if not VERSION.fullmatch(version):
        raise ValueError(f"invalid version-only release directory: {version}")
    checksum_file = directory / "SHA256SUMS"
    if not checksum_file.is_file() or checksum_file.is_symlink():
        raise ValueError(f"missing or linked SHA256SUMS: {version}")
    lines = [line for line in checksum_file.read_text().splitlines() if line]
    if len(lines) != 1 or not (match := CHECKSUM.fullmatch(lines[0])):
        raise ValueError(f"expected one Debian checksum entry: {version}")
    digest, filename = match.groups()
    expected_name = f"projectwright_{version}-1_all.deb"
    if filename != expected_name:
        raise ValueError(f"release filename/version mismatch: {version}")
    package = directory / filename
    if not package.is_file() or package.is_symlink():
        raise ValueError(f"missing or linked Debian package: {version}")
    if hashlib.sha256(package.read_bytes()).hexdigest().lower() != digest.lower():
        raise ValueError(f"Debian checksum mismatch: {version}")
    for field, expected in (("Package", "projectwright"),
                            ("Version", f"{version}-1"), ("Architecture", "all")):
        actual = run("dpkg-deb", "--field", str(package), field)
        if actual != expected:
            raise ValueError(f"Debian {field} mismatch: {version}")
    return package


def build(releases, output, origin, suite):
    if not shutil.which("apt-ftparchive") or not shutil.which("dpkg-deb"):
        raise RuntimeError("apt-ftparchive and dpkg-deb are required")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output must be an empty directory")
    dirs = sorted((p for p in releases.iterdir() if p.is_dir()), key=lambda p: p.name)
    if not dirs:
        raise ValueError("no release directories provided")
    packages = [validate_release(p) for p in dirs]
    pool = output / "pool/main/p/projectwright"
    pool.mkdir(parents=True)
    for package in packages:
        shutil.copyfile(package, pool / package.name)

    package_index = run("apt-ftparchive", "packages", "pool/main/p/projectwright", cwd=output)
    if package_index.count("Package: projectwright") != len(packages):
        raise RuntimeError("APT index does not contain every verified package")
    import gzip
    for arch in ARCHITECTURES:
        index_dir = output / f"dists/{suite}/main/binary-{arch}"
        index_dir.mkdir(parents=True)
        (index_dir / "Packages").write_text(package_index + "\n")
        with (index_dir / "Packages.gz").open("wb") as target:
            with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as zipped:
                zipped.write((package_index + "\n").encode())

    release_dir = output / "dists" / suite
    options = [
        "-o", f"APT::FTPArchive::Release::Origin={origin}",
        "-o", f"APT::FTPArchive::Release::Label={origin}",
        "-o", f"APT::FTPArchive::Release::Suite={suite}",
        "-o", f"APT::FTPArchive::Release::Codename={suite}",
        "-o", "APT::FTPArchive::Release::Architectures=amd64 arm64",
        "-o", "APT::FTPArchive::Release::Components=main",
        "-o", "APT::FTPArchive::Release::Description=Signed Projectwright Debian packages",
    ]
    metadata = run("apt-ftparchive", *options, "release", f"dists/{suite}", cwd=output)
    (release_dir / "Release").write_text(metadata + "\n")
    (output / ".nojekyll").touch()
    return len(packages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--releases-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--origin", default="Projectwright")
    parser.add_argument("--suite", default="stable")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.suite):
        parser.error("suite must be a simple lowercase name")
    try:
        count = build(args.releases_dir, args.output, args.origin, args.suite)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"APT repository build refused: {exc}\n")
    print(f"Indexed {count} verified Projectwright release package(s); unsigned until publishing")


if __name__ == "__main__":
    main()
