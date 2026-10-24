"""Legacy compatibility module for pw_milestone_guard.

Preserve private helper access for existing approval consumers during migration.
"""
import pw_milestone_guard as _impl
from pw_milestone_guard import *  # noqa: F401,F403


def __getattr__(name):
    return getattr(_impl, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_impl)))


if __name__ == "__main__":
    main()
