"""Legacy compatibility entrypoint for pw_recovery."""
from pw_recovery import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())
