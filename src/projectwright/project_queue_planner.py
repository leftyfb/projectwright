"""Legacy queue planner compatibility alias."""
import pw_queue_planner as _impl
from pw_queue_planner import *  # noqa: F401,F403

def __getattr__(name):
    return getattr(_impl, name)

def __dir__():
    return sorted(set(globals()) | set(dir(_impl)))
