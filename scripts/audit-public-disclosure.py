#!/usr/bin/env python3
"""Read-only public-disclosure audit. Never print credential values."""
import collections
import concurrent.futures
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

REPO = os.environ.get("GITHUB_REPOSITORY", "leftyfb/projectwright")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_SIZE = 8 * 1024 * 1024
PATTERNS = {
    "private_key": re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"),
    "github_token": re.compile(rb"\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{20,}"),
    "aws_access_key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "openai_key": re.compile(rb"\bsk-[A-Za-z0-9_-]{24,}"),
    "telegram_bot_token": re.compile(rb"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b"),
    "credential_url": re.compile(rb"https?://[^\s/@]+:[^\s/@]+@"),
    "secret_assignment": re.compile(rb"(?im)^\s*(?:export\s+)?(?:[A-Z_]*(?:SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z_]*)\s*[:=]\s*[A-Za-z0-9+/_=-]{24,}"),
}
SENSITIVE_PATH = re.compile(r"(^|/)(?:\.env(?:\.[^/]*)?|id_(?:rsa|ed25519)|[^/]*\.(?:pem|p12|pfx|key)|credentials(?:\.[^/]*)?)$", re.I)
REPORT = {"git": {"objects_scanned": 0, "skipped": [], "findings": [], "refs": []},
          "actions": {"runs_total": 0, "runs_checked": 0, "unavailable": [], "findings": []}}


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def labels(data):
    return [label for label, regex in PATTERNS.items() if regex.search(data)]


def report_findings(kind, identifier, data):
    found = labels(data)
    if found:
        REPORT[kind]["findings"].append({"location": identifier, "categories": found})


def scan_git():
    REPORT["git"]["refs"] = git("for-each-ref", "--format=%(refname)").decode().splitlines()
    objects = git("rev-list", "--objects", "--all").decode(errors="replace").splitlines()
    by_oid = {}
    for line in objects:
        sha, _, path = line.partition(" ")
        by_oid.setdefault(sha, path)
    for oid, path in by_oid.items():
        if git("cat-file", "-t", oid).strip() != b"blob":
            continue
        size = int(git("cat-file", "-s", oid))
        if size > MAX_SIZE:
            REPORT["git"]["skipped"].append({"path": path, "reason": "large_blob", "bytes": size})
            continue
        data = git("cat-file", "blob", oid)
        REPORT["git"]["objects_scanned"] += 1
        report_findings("git", path or oid[:12], data)
        if SENSITIVE_PATH.search(path):
            REPORT["git"]["findings"].append({"location": path, "categories": ["sensitive_filename"]})
    # Ref history alone does not include unreachable commits or GitHub Actions artifacts.


def request(url):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "projectwright-private-release-audit",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def scan_run(item):
    run_id = item["id"]
    url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/logs"
    for attempt in range(3):
        try:
            data = request(url)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                found = collections.defaultdict(set)
                for name in archive.namelist():
                    if name.endswith("/") or archive.getinfo(name).file_size > MAX_SIZE:
                        continue
                    for category in labels(archive.read(name)):
                        found[name].add(category)
            return (run_id, [{"location": f"run/{run_id}/{name}", "categories": sorted(categories)}
                             for name, categories in found.items()], None)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404, 410, 429, 502, 503, 504) and attempt < 2:
                time.sleep(1 + attempt)
                continue
            return (run_id, [], f"http_{exc.code}")
        except Exception as exc:
            return (run_id, [], type(exc).__name__)


def scan_actions():
    if not TOKEN:
        REPORT["actions"]["unavailable"].append({"reason": "no_token"})
        return
    runs = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{REPO}/actions/runs?per_page=100&page={page}"
        obj = json.loads(request(url))
        if page == 1:
            REPORT["actions"]["runs_total"] = obj["total_count"]
        batch = obj["workflow_runs"]
        runs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 40:
            REPORT["actions"]["unavailable"].append({"reason": "pagination_limit"})
            break
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for run_id, found, error in executor.map(scan_run, runs):
            if error:
                REPORT["actions"]["unavailable"].append({"run_id": run_id, "reason": error})
            else:
                REPORT["actions"]["runs_checked"] += 1
                REPORT["actions"]["findings"].extend(found)


def main():
    scan_git()
    scan_actions()
    Path("public-disclosure-audit.json").write_text(json.dumps(REPORT, indent=2) + "\n")
    for area in ("git", "actions"):
        results = REPORT[area]
        print(f"{area}: matches={len(results['findings'])}, inaccessible={len(results.get('unavailable', results.get('skipped', [])))}")
        for record in results["findings"][:60]:
            print("  " + record["location"] + ": " + ",".join(record["categories"]))
    print("git objects scanned:", REPORT["git"]["objects_scanned"])
    print("actions logs scanned:", REPORT["actions"]["runs_checked"], "/", REPORT["actions"]["runs_total"])
    print("unavailable log reasons:", dict(collections.Counter(item["reason"] for item in REPORT["actions"]["unavailable"])))
    print("unavailable run IDs:", [item["run_id"] for item in REPORT["actions"]["unavailable"] if "run_id" in item])
    if REPORT["git"]["findings"] or REPORT["actions"]["findings"]:
        return 2
    if REPORT["git"]["skipped"] or REPORT["actions"]["unavailable"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
