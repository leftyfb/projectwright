"""Legacy worker CLI and import compatibility alias."""
import pw_task_worker as _impl
from pw_task_worker import *  # noqa: F401,F403

def __getattr__(name):
    return getattr(_impl, name)

def __dir__():
    return sorted(set(globals()) | set(dir(_impl)))

if __name__ == "__main__":
    raise SystemExit(main())
