# Contributing

Projectwright is currently being prepared for public source availability. Before opening a pull request:

1. Discuss behavioral changes in an issue; never include secrets or private project data.
2. Run `python3 -B -m unittest discover -s tests -p 'test_*.py' -v` and `python3 -B scripts/validate-baseline.py --mode development`.
3. Keep provider, Hermes, and Telegram tests isolated and deterministic. Do not run live approvals, send Telegram messages, or assume access to `isolated-test-host` or `disposable-test-container`.
4. Document changed CLI behavior and installed file paths in `docs/manual.md` and `docs/file-reference.md`.
5. Never add workflows that execute outside GitHub-hosted runners without a security review.

Release branches use `release/MAJOR.MINOR.PATCH`; GitHub tags contain only the version number, e.g. `0.1.0`, without `v`. See `docs/release-checklist.md` for the test record. The project uses the MIT license. Ensure any submitted material can be distributed under that license.
