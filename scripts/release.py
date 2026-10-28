#!/usr/bin/env python3
"""Prepare and publish a verified Projectwright release from release/X.Y.Z.

Run from a clean local checkout with git and authenticated GitHub CLI:
    python3 scripts/release.py 0.1.2
    python3 scripts/release.py 0.1.2 --notes-file /path/to/reviewed-notes.md

No private signing key or release token is handled by this script.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = "leftyfb/projectwright"
MATRIX = "ubuntu-lts-compatibility.yml"
PUBLISH = "publish-release.yml"
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ROOT = Path(__file__).resolve().parents[1]


class ReleaseError(Exception):
    pass


def command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReleaseError(f"{' '.join(args[:3])} failed: {detail}")
    return result


def output(*args: str) -> str:
    return command(*args).stdout.strip()


def require_clean_release_branch(version: str) -> tuple[str, str]:
    branch = f"release/{version}"
    if output("git", "branch", "--show-current") != branch:
        raise ReleaseError(f"Check out {branch} before running this script")
    if command("git", "status", "--porcelain").stdout.strip():
        raise ReleaseError("Worktree is not clean; commit or stash your changes first")
    repository = output("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    if repository != REPO:
        raise ReleaseError(f"Expected {REPO}, found {repository}")
    local = output("git", "rev-parse", "HEAD")
    remote = output("git", "ls-remote", "origin", f"refs/heads/{branch}").split()
    if not remote or remote[0] != local:
        raise ReleaseError(f"{branch} must exist on origin at the same commit; fetch/pull first")
    if output("git", "ls-remote", "--tags", "origin", f"refs/tags/{version}"):
        raise ReleaseError(f"Tag {version} already exists; never overwrite a release")
    if command("gh", "release", "view", version, "-R", REPO, check=False).returncode == 0:
        raise ReleaseError(f"GitHub Release {version} already exists")
    return branch, local


def one_replace(text: str, pattern: str, replacement: str, label: str) -> str:
    changed, count = re.subn(pattern, lambda _: replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise ReleaseError(f"Expected one {label} field, found {count}")
    return changed


def proposed_files(version: str, notes_path: Path | None) -> dict[Path, str]:
    py = ROOT / "pyproject.toml"
    deb = ROOT / "scripts" / "build-deb.sh"
    notes = ROOT / "docs" / "release-notes.md"
    metadata = one_replace(py.read_text(), r'^version = "[^"]+"$',
                           f'version = "{version}"', "Python version")
    metadata = metadata.replace("Project task orchestration (development preview)",
                                "Hermes-based project task orchestration")
    package = one_replace(deb.read_text(), r'^Version: [^\n]+$',
                          f"Version: {version}-1", "Debian version")
    filename = re.compile(r"projectwright_[0-9A-Za-z.~+-]+_all\.deb")
    matches = filename.findall(package)
    if len(matches) != 2:
        raise ReleaseError(f"Expected two Debian filename references, found {len(matches)}")
    package = filename.sub(f"projectwright_{version}-1_all.deb", package)
    package = package.replace("Build an uninstalled Debian preview",
                              "Build a Debian package")
    package = package.replace(
        "Description: Development preview of project task orchestration\n"
        " A pre-release packaging checkpoint for Projectwright. External agent\n"
        " services and project configuration are not provisioned by this package.",
        "Description: Hermes-based project task orchestration\n"
        " Projectwright coordinates planning, execution and approval workflows.\n"
        " Hermes and user project configuration are provisioned separately.")
    if "Development preview of project task orchestration" in package:
        raise ReleaseError("Could not replace preview Debian description")

    if notes_path is not None:
        release_notes = notes_path.read_text()
        if not release_notes.strip():
            raise ReleaseError("Release notes file is empty")
    else:
        release_notes = generated_notes(version)
    if not release_notes.endswith("\n"):
        release_notes += "\n"
    return {py: metadata, deb: package, notes: release_notes}


def generated_notes(version: str) -> str:
    releases = json.loads(output("gh", "release", "list", "-R", REPO,
                                 "--json", "tagName", "--limit", "100"))
    previous = [item["tagName"] for item in releases if
                VERSION.fullmatch(item["tagName"]) and
                tuple(map(int, item["tagName"].split("."))) <
                tuple(map(int, version.split(".")))]
    previous.sort(key=lambda tag: tuple(map(int, tag.split("."))))
    base = previous[-1] if previous else None
    if base:
        command("git", "fetch", "--quiet", "origin", f"refs/tags/{base}:refs/tags/{base}")
    history = output("git", "log", "--no-merges", "--format=%s",
                     f"{base}..HEAD" if base else "HEAD", "-30")
    subjects = [line.strip() for line in history.splitlines() if line.strip()]
    changes = "\n".join(f"- {line}" for line in subjects[:20])
    if not changes:
        changes = "- Maintenance and packaging updates."
    previous_text = f" since {base}" if base else ""
    return (f"# Projectwright {version}\n\n"
            f"Maintenance and distribution release{previous_text}.\n\n"
            f"## Changes\n\n{changes}\n\n"
            "## Requirements\n\n"
            "- Ubuntu 24.04 and 26.04 LTS. Ubuntu 22.04 is not supported.\n"
            "- Hermes CLI and per-user configuration are required and installed separately.\n"
            "- Telegram approvals are optional and require consent during `pw setup`.\n\n"
            "## Installation and upgrade\n\n"
            "Install the signed APT source using the [repository guide]"
            "(https://github.com/leftyfb/projectwright/blob/main/docs/apt-repository.md), "
            "then run:\n\n"
            "```sh\nsudo apt update\nsudo apt install projectwright\npw setup\n```\n\n"
            "The release also attaches the versioned Debian package and SHA256SUMS.\n"
            "Package installation does not modify Hermes credentials or activate "
            "plugins or user timers. Refer to the packaging guide for removal and rollback.\n\n"
            "## Verification\n\n"
            "The exact tagged commit must pass the hosted Ubuntu 24.04/26.04 "
            "clean-install and purge matrix. Historical live Telegram callback "
            "tests do not guarantee all Hermes installations or configurations.\n")


def dispatch_run(workflow: str, ref: str, sha: str,
                 fields: tuple[str, ...] = ()) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    result = output("gh", "workflow", "run", workflow, "-R", REPO,
                    "--ref", ref, *fields)
    match = re.search(r"/actions/runs/([0-9]+)", result)
    if match:
        return int(match.group(1))
    # Older gh releases do not always print a run URL. Find the new exact-SHA run.
    for _ in range(30):
        runs = json.loads(output("gh", "run", "list", "-R", REPO,
                                 "--workflow", workflow, "--branch", ref,
                                 "--event", "workflow_dispatch", "--limit", "30",
                                 "--json", "databaseId,headSha,createdAt,event"))
        eligible = []
        for run in runs:
            created = dt.datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
            if run["headSha"] == sha and created >= now - dt.timedelta(seconds=10):
                eligible.append(run)
        if len(eligible) == 1:
            return int(eligible[0]["databaseId"])
        if len(eligible) > 1:
            raise ReleaseError(f"Ambiguous {workflow} runs; inspect GitHub Actions")
        time.sleep(2)
    raise ReleaseError(f"Could not identify {workflow} run; inspect GitHub Actions")


def watch_run(run_id: int) -> None:
    print(f"Watching https://github.com/{REPO}/actions/runs/{run_id}", flush=True)
    command("gh", "run", "watch", str(run_id), "-R", REPO, "--exit-status")
    details = json.loads(output("gh", "run", "view", str(run_id), "-R", REPO,
                                "--json", "status,conclusion"))
    if details["status"] != "completed" or details["conclusion"] != "success":
        raise ReleaseError(f"Workflow run {run_id} was not successful")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Numeric version such as 0.1.2 (no v)")
    parser.add_argument("--notes-file", type=Path,
                        help="Reviewed Markdown release notes; otherwise generate from commits")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the interactive confirmation (for deliberate automation)")
    args = parser.parse_args(argv)
    if not VERSION.fullmatch(args.version):
        parser.error("Version must be X.Y.Z without a v prefix")
    try:
        branch, _ = require_clean_release_branch(args.version)
        changes = proposed_files(args.version, args.notes_file)
        print(f"Release: {args.version}\nSource branch: {branch}")
        print(f"Debian version: {args.version}-1\n")
        print(changes[ROOT / "docs" / "release-notes.md"])
        if not args.yes:
            if not sys.stdin.isatty():
                raise ReleaseError("Terminal confirmation required; use --yes only deliberately")
            answer = input(f"Type 'publish {args.version}' to commit, test, tag and publish: ")
            if answer != f"publish {args.version}":
                raise ReleaseError("Release cancelled without file changes")

        for path, contents in changes.items():
            path.write_text(contents)
        relative = [str(path.relative_to(ROOT)) for path in changes]
        command("git", "add", "--", *relative)
        command("git", "commit", "-m", f"release: prepare Projectwright {args.version}")
        sha = output("git", "rev-parse", "HEAD")
        command("git", "push", "origin", branch)
        print(f"Release source: {sha}", flush=True)
        matrix_run = dispatch_run(MATRIX, branch, sha)
        watch_run(matrix_run)
        # Use the current main commit because the release publisher is dispatched
        # from main; it checks out SHA from the release branch internally.
        main_sha = output("git", "ls-remote", "origin", "refs/heads/main").split()[0]
        publish_run = dispatch_run(PUBLISH, "main", main_sha, (
            "-f", f"version={args.version}",
            "-f", f"source_sha={sha}",
            "-f", f"artifact_run_id={matrix_run}",
        ))
        watch_run(publish_run)
        release = json.loads(output("gh", "release", "view", args.version, "-R", REPO,
                                    "--json", "tagName,assets,url,isDraft,isPrerelease"))
        assets = {asset["name"] for asset in release["assets"]}
        required = {f"projectwright_{args.version}-1_all.deb", "SHA256SUMS"}
        if (release["tagName"] != args.version or release["isDraft"] or
                release["isPrerelease"] or not required.issubset(assets)):
            raise ReleaseError("Release published, but assets/status need manual verification")
        print(f"Published {release['url']}")
        print("Signed APT update is triggered automatically after successful "
              "release publication. Verify the Publish signed Projectwright APT "
              "repository workflow and GitHub Pages deployment.")
        return 0
    except (ReleaseError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
