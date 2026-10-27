#!/usr/bin/env python3
"""Reusable, fail-closed project quota policy for workers and planners."""
from __future__ import annotations
import json
import os
import urllib.request
from pathlib import Path

# Optional gate: project config takes precedence; this environment default is
# intentionally unset so a generic install is not bound to one HA instance.
RATE_LIMITED_ENTITY_ENV = 'PROJECTWRIGHT_RATE_LIMITED_ENTITY'
DEFAULT_RATE_LIMITED_ENTITY = None


class QuotaError(RuntimeError):
    pass

def evaluate(settings: dict, *, home: Path | None = None) -> dict:
    """Return a decision. Missing/stale/unavailable readings BLOCK when enabled."""
    settings = settings or {}
    enabled = settings.get('enabled', True)
    if not isinstance(enabled, bool):
        raise QuotaError('quota.enabled must be boolean')
    if not enabled:
        return {'enabled': False, 'allowed': True, 'reason': 'disabled', 'remaining_percent': None}
    threshold = settings.get('minimum_remaining_percent', 10)
    if isinstance(threshold, bool) or not isinstance(threshold, (int,float)) or not (0 <= threshold <= 100):
        raise QuotaError('quota.minimum_remaining_percent must be between 0 and 100')
    base = Path(home or Path.home()) / '.hermes'
    secret_path = Path(os.path.expanduser(settings.get('ha_env_file', str(base / 'secrets/ha.env'))))
    env = {}
    try:
        for line in secret_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('export '): line = line[7:].strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v = line.split('=', 1)
            if k.strip() in ('HA_URL','HA_TOKEN'): env[k.strip()] = v.strip().strip('"\'')
        ha_url = env['HA_URL'].rstrip('/')
        # Never permit arbitrary plain HTTP URLs to receive the HA bearer token.
        # An opt-in exception allows Home Assistant's exact mDNS hostname.
        from urllib.parse import urlsplit
        url = urlsplit(ha_url)
        allow_local_http = settings.get('allow_local_http', False)
        if not isinstance(allow_local_http, bool):
            raise QuotaError('quota.allow_local_http must be boolean')
        if url.username or url.password or url.path or url.query or url.fragment:
            raise QuotaError('HA_URL must contain only scheme, hostname and optional port')
        try:
            port = url.port  # Also validates the numeric port range.
        except ValueError as exc:
            raise QuotaError('invalid HA_URL port') from exc
        host = (url.hostname or '').lower()
        if url.scheme == 'https' and host:
            pass
        elif url.scheme == 'http' and host in ('localhost', '127.0.0.1', '::1'):
            pass
        elif (url.scheme == 'http' and allow_local_http
              and host == 'homeassistant.local' and port is not None):
            pass
        else:
            raise QuotaError('HA_URL requires HTTPS, loopback HTTP, or explicitly enabled homeassistant.local HTTP')
        token = env['HA_TOKEN']
        timeout = float(settings.get('timeout_seconds', 10))
        if not 0 < timeout <= 30: raise QuotaError('quota timeout must be >0 and <=30')
        def state(entity: str) -> dict:
            if not isinstance(entity,str) or not entity.startswith(('sensor.','binary_sensor.')) or '/' in entity:
                raise QuotaError('invalid Home Assistant entity identifier')
            request = urllib.request.Request(ha_url+'/api/states/'+entity, headers={'Authorization': 'Bearer '+token})
            with urllib.request.urlopen(request,timeout=timeout) as response:
                return json.load(response)
        remaining_entity = settings.get('remaining_entity', 'sensor.codex_usage_weekly_remaining')
        remaining = float(state(remaining_entity)['state'])
        import math
        if not math.isfinite(remaining) or not (0 <= remaining <= 100):
            raise QuotaError('invalid remaining quota reading')
        # Explicit project null disables the optional gate. Otherwise resolve
        # the configured entity, then the installation environment default.
        limited_entity = settings.get(
            'rate_limited_entity',
            os.environ.get(RATE_LIMITED_ENTITY_ENV, DEFAULT_RATE_LIMITED_ENTITY),
        )
        limited = False
        if limited_entity is not None:
            if not isinstance(limited_entity, str) or not limited_entity:
                raise QuotaError('quota.rate_limited_entity must be an entity ID or null')
            value = str(state(limited_entity)['state']).lower()
            if value not in ('on','off'): raise QuotaError('rate limited sensor state unknown')
            limited = value == 'on'
        allowed = (remaining > threshold) and not limited
        reason = 'ok' if allowed else ('rate_limited' if limited else 'threshold_reached')
        return {'enabled': True, 'allowed': allowed, 'reason': reason,
                'remaining_percent': remaining, 'minimum_remaining_percent': threshold,
                'rate_limited': limited}
    except Exception as exc:
        return {'enabled': True, 'allowed': False, 'reason': 'quota_unavailable',
                'detail': str(exc), 'remaining_percent': None}
