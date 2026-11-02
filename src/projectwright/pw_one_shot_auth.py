"""Ephemeral single-use handoffs for manually requested worker runs."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time

HANDOFF_ENV = "PROJECTWRIGHT_ONE_SHOT_HANDOFF"
_HANDOFF_DIR = ".projectwright-one-shot"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{40,}$")
_TTL_SECONDS = 900


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _constant_equal(left, right) -> bool:
    return hmac.compare_digest(
        json.dumps(left, sort_keys=True, separators=(",", ":")),
        json.dumps(right, sort_keys=True, separators=(",", ":")),
    )


def create(project_dir: Path, claims: dict) -> str:
    """Create a mode-600, single-use capability and return its bearer token."""
    handoff_dir = project_dir / _HANDOFF_DIR
    handoff_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if handoff_dir.is_symlink() or not handoff_dir.is_dir():
        raise ValueError("unsafe one-shot handoff directory")
    os.chmod(handoff_dir, 0o700)
    token = secrets.token_urlsafe(32)
    payload = {"token": token, "claims": claims, "created_at": time.time()}
    path = handoff_dir / f"{token}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return token


def is_present(project_dir: Path, token: str) -> bool:
    if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
        return False
    handoff_dir = project_dir / _HANDOFF_DIR
    path = handoff_dir / f"{token}.json"
    try:
        return handoff_dir.is_dir() and not handoff_dir.is_symlink() and path.is_file() and not path.is_symlink()
    except OSError:
        return False


def consume(project_dir: Path, token: str, claims: dict) -> None:
    """Validate and atomically consume a handoff. Caller must hold project lock."""
    if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
        raise ValueError("missing or invalid one-shot handoff")
    handoff_dir = project_dir / _HANDOFF_DIR
    if handoff_dir.is_symlink():
        raise ValueError("unsafe one-shot handoff directory")
    handoff_dir = handoff_dir.resolve()
    path = handoff_dir / f"{token}.json"
    if path.parent != handoff_dir:
        raise ValueError("invalid one-shot handoff path")
    try:
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, ValueError) as exc:
        raise ValueError("one-shot handoff is missing or already consumed") from exc
    created_at = payload.get("created_at") if isinstance(payload, dict) else None
    if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
        raise ValueError("one-shot handoff is stale or malformed")
    if created_at > time.time() or time.time() - created_at > _TTL_SECONDS:
        raise ValueError("one-shot handoff is stale or malformed")
    if (not isinstance(payload, dict) or payload.get("token") != token
            or not _constant_equal(payload.get("claims"), claims)):
        raise ValueError("one-shot handoff does not match live project state")
    consumed = handoff_dir / f"{token}.consumed"
    try:
        os.replace(path, consumed)
    except OSError as exc:
        raise ValueError("one-shot handoff could not be consumed") from exc
    try:
        consumed.unlink()
    except OSError:
        pass


def handoff_dir(project_dir: Path) -> Path:
    return project_dir / _HANDOFF_DIR
