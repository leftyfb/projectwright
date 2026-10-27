# Independent review follow-up tests

Branch: `test/review-followups`, based on `fix/contract-hardening`.

The new `tests/integration/test_review_followups.py` contains three **expected-failure specifications**. They must not be counted as fixes or as successful live integration validation:

1. **Notification revocation during transport.** A request is removed after the notifier's last pending-record check but before its injected send completes; the current implementation can still record the delivery marker. Preventing already-started network delivery from being recalled is impossible. The long-term contract should specify whether to revalidate immediately before sending and how to handle mid-send invalidation.
2. **Callback allowed-user configuration refresh.** The Hermes callback plugin captures the allowed IDs when the handler is registered; changing the configuration without recreating the handler leaves the old policy in force until plugin/gateway reload. Determine whether runtime refresh is required or whether restart-on-change is an explicit supported operational contract.
3. **Dispatcher dynamic import isolation.** The active Git-cycle gate can obtain `project_queue_manager` from `sys.modules`, rather than guaranteeing the helper came from the selected scripts directory. A preloaded unrelated module can change the decision. Prefer source-scoped import resolution while retaining fail-closed Git-cycle validation.

## Validation on isolated-test-host

No tests were executed by the GitHub file-editing operation. After fetching this branch, run:

```sh
cd ~/repos/projectwright
git fetch origin
git switch test/review-followups
python3 -B -m unittest tests.integration.test_review_followups -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B scripts/validate-baseline.py --mode development
git diff --check
```

Expected failures remain `XFAIL` until an independently verified source fix changes that behavior. If an expected failure unexpectedly succeeds, inspect it; unittest reports `unexpected success` as a nonpassing outcome.

Do not run live Telegram, Home Assistant, Hermes, or systemd tests through this suite. Do not install or merge development source as part of these checks.
