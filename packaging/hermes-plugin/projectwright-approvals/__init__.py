"""Hermes adapter for Projectwright's Telegram approval callbacks.

A Hermes gateway may use a private virtual environment whose sys.path omits
Debian's distribution modules. Resolve the package installed by the .deb.
"""
import sys

try:
    from pw_plugin import register
except ModuleNotFoundError as exc:
    if exc.name != "pw_plugin":
        raise
    sys.path.append("/usr/lib/python3/dist-packages")
    from pw_plugin import register
