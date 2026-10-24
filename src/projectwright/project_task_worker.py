"""Compatibility alias: legacy worker imports share canonical mutable state."""
import sys
import pw_task_worker as _impl

if __name__ == "__main__":
    raise SystemExit(_impl.main())
else:
    sys.modules[__name__] = _impl
