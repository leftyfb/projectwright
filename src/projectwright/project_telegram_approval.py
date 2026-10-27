"""Legacy approval bridge alias; preserve access to non-public helpers."""
import pw_telegram_approval as _impl
from pw_telegram_approval import *  # noqa: F401,F403

def __getattr__(name):
    return getattr(_impl, name)

def __dir__():
    return sorted(set(globals()) | set(dir(_impl)))

if __name__ == "__main__":
    raise SystemExit(main())
