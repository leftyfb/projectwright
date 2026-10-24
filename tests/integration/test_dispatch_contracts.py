"""Hermetic dispatcher, manager, planner, and timer regression contracts."""

import ast
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))
# Some Hermes test processes pre-import installed scripts. These tests are
# strictly source-tree tests, so discard only stale modules outside this repo.
for _module_name in ("project_queue_manager", "project_queue_planner", "pw_dispatch", "pw_project_timer", "project_task_worker"):
    _loaded = sys.modules.get(_module_name)
    if _loaded is not None and Path(getattr(_loaded, "__file__", "")).resolve().parent != SRC:
        sys.modules.pop(_module_name, None)

import project_queue_manager as manager
import project_queue_planner as planner
import pw_dispatch as dispatch
import pw_project_timer as timer
import project_task_worker as worker


class DispatchFixture(unittest.TestCase):
    """Small on-disk project and fake runner used by dispatcher contracts."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = "pw-sequence-test"
        self.project_dir = self.root / "projects" / self.project
        self.project_dir.mkdir(parents=True)
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        for name in ("project_queue_manager.py", "project_task_worker.py"):
            shutil.copy2(SRC / name, self.scripts / name)

    def config(self, *, queue_text="", cycle_file=None, worktree=None, **extra):
        queue = self.project_dir / "queue.md"
        queue.write_text(queue_text, encoding="utf-8")
        cfg = {
            "id": self.project,
            "queue": str(queue),
            "work_log": str(self.project_dir / "work_log.md"),
            "lock": str(self.project_dir / "worker.lock"),
            "run_log": str(self.project_dir / "run.log"),
            "result_dir": str(self.project_dir / "results"),
            "cycle_file": str(cycle_file or self.project_dir / "git_cycle.json"),
            "worktree": str(worktree or self.root),
            "branch": "main",
            "hermes": "/bin/false",
            "timeout_seconds": 60,
        }
        cfg.update(extra)
        (self.project_dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        return cfg

    def run_tick(self, report=None, *, manager_rc=None, worker_rc=0, worker_stdout="",
                 manager_stdout=None, manager_stderr=""):
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                stdout = manager_stdout
                if stdout is None:
                    payload = dict(report or {})
                    payload.setdefault("project", self.project)
                    if payload.get("decision") == "queued":
                        payload.setdefault("pending", 0)
                        payload.setdefault("added", 1)
                        payload.setdefault("task_ids", ["P101"])
                        payload.setdefault("planning_mode", "tactical")
                        payload.setdefault("notes_sync", "not_configured")
                    elif payload.get("decision") == "busy":
                        payload.setdefault("reason", "Project lock held; skip planning")
                    elif payload.get("decision") == "blocked":
                        payload.setdefault("reason", "planning blocked")
                    elif payload.get("decision") == "no_op":
                        payload.setdefault("pending", 0)
                    elif payload.get("decision") == "awaiting_acceptance":
                        payload.setdefault("pending", 0)
                        payload.setdefault("reason", "approval required")
                        payload.setdefault("milestones", ["TEST-001-M1"])
                    elif payload.get("decision") == "quota_blocked":
                        payload.setdefault("pending", 0)
                        payload.setdefault("quota", {"allowed": False})
                    elif payload.get("decision") == "planner_failed":
                        payload.setdefault("pending", 0)
                        payload.setdefault("reason", "planning failed")
                    stdout = json.dumps(payload)
                    actual_rc = dispatch.manager_exit_code(payload.get("decision"))
                else:
                    actual_rc = 0 if manager_rc is None else manager_rc
                if manager_rc is not None:
                    actual_rc = manager_rc
                return subprocess.CompletedProcess(args, actual_rc, stdout, manager_stderr)
            return subprocess.CompletedProcess(args, worker_rc, worker_stdout, "")

        with patch.dict(os.environ, {"HERMES_PROJECT_CONFIG_DIR": str(self.root / "projects")}):
            result = dispatch.run_tick(self.project, self.scripts, runner=runner)
        return result, calls


class TestTick(DispatchFixture):
    def test_manager_output_contract_rejects_ambiguous_responses(self):
        valid_queued = {
            "project": self.project, "decision": "queued", "pending": 0,
            "added": 1, "task_ids": ["P101"], "planning_mode": "tactical",
            "notes_sync": "not_configured",
        }
        malformed = [
            ("not-json", 0),
            ("", 0),
            (json.dumps({"project": self.project, "decision": "queued"}) + "\nnotice", 0),
            ('{"project": "fixture", "decision": }', 0),
            (json.dumps({**valid_queued, "pending": True}), 0),
            (json.dumps({**valid_queued, "project": "another-project"}), 0),
            (json.dumps({**valid_queued, "task_ids": ["NOT-A-TASK-ID"]}), 0),
            (json.dumps({**valid_queued, "notes_sync": ""}), 0),
            (json.dumps({**valid_queued, "notes_sync": "unexpected"}), 0),
            (json.dumps({**valid_queued, "branch": "main"}), 0),
            (json.dumps(valid_queued), 3),
            ('{"project": "fixture", "decision": "quota_blocked", "pending": 0, "quota": {"allowed": false, "remaining_percent": NaN}}', 4),
            (json.dumps({"project": self.project, "decision": "no_op", "pending": 0}), 0),
            (json.dumps({"project": self.project, "decision": "busy",
                         "reason": "Project lock held; skip planning"}), 0),
        ]
        for stdout, manager_rc in malformed:
            with self.subTest(stdout=stdout, manager_rc=manager_rc):
                with contextlib.redirect_stderr(io.StringIO()):
                    result, calls = self.run_tick(
                        manager_rc=manager_rc, manager_stdout=stdout,
                        manager_stderr="diagnostics stay on stderr",
                    )
            self.assertNotEqual(result, 0)
            self.assertEqual(len(calls), 1)

    def test_manager_contract_rejects_duplicate_json_keys(self):
        stdout = ('{"project": "fixture", "project": "fixture", '
                  '"decision": "no_op", "pending": 0}')
        with contextlib.redirect_stderr(io.StringIO()):
            result, calls = self.run_tick(manager_stdout=stdout, manager_rc=3)
        self.assertEqual((result, len(calls)), (21, 1))

    def test_manager_output_contract_accepts_supported_decision_shapes(self):
        reports = [
            (self.queued_report(), 0),
            ({"project": self.project, "decision": "busy",
              "reason": "Project lock held; skip planning"}, 2),
            ({"project": self.project, "decision": "blocked",
              "reason": "Requirements file missing"}, 2),
            ({"project": self.project, "decision": "no_op", "pending": 0}, 3),
            ({"project": self.project, "decision": "disabled"}, 3),
            ({"project": self.project, "decision": "awaiting_acceptance", "pending": 0,
              "reason": "approval required", "milestone": "TEST-001-M1"}, 3),
            ({"project": self.project, "decision": "awaiting_acceptance", "pending": 0,
              "reason": "approval required", "milestones": ["TEST-001-M1"]}, 3),
            ({"project": self.project, "decision": "quota_blocked", "pending": 0,
              "quota": {"allowed": False, "reason": "limited"}}, 4),
            ({"project": self.project, "decision": "planner_failed", "pending": 0,
              "reason": "planner unavailable"}, 4),
        ]
        for report, returncode in reports:
            with self.subTest(decision=report["decision"], report=report):
                self.assertEqual(
                    dispatch.parse_manager_response(json.dumps(report), self.project, returncode),
                    report,
                )

    def test_ready_for_planner_status_decision_is_refused(self):
        report = {
            "project": self.project,
            "decision": "ready_for_planner",
            "pending": 1,
        }
        with contextlib.redirect_stderr(io.StringIO()):
            result, calls = self.run_tick(
                manager_rc=4, manager_stdout=json.dumps(report),
            )
        self.assertEqual(result, 21)
        self.assertEqual(len(calls), 1)

    def test_queued_modes_accept_tactical_and_strategic(self):
        tactical = self.queued_report()
        strategic = {**tactical, "planning_mode": "strategic"}
        for report in (tactical, strategic):
            with self.subTest(planning_mode=report["planning_mode"]):
                self.assertEqual(
                    dispatch.parse_manager_response(json.dumps(report), self.project, 0),
                    report,
                )

    def queued_report(self):
        return {
            "project": self.project,
            "decision": "queued",
            "pending": 0,
            "added": 1,
            "task_ids": ["P101"],
            "planning_mode": "tactical",
            "notes_sync": "not_configured",
        }

    def test_plan_once_output_is_accepted_by_dispatcher(self):
        repo = self.root / "worktree"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        (repo / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
        subprocess.run([
            "git", "-C", str(repo), "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture",
        ], check=True)
        requirements = self.project_dir / "requirements.md"
        requirements.write_text(
            "## TEST-001 — Fixture requirement\n### TEST-001-M1 — Fixture milestone\n",
            encoding="utf-8",
        )
        cfg = self.config(worktree=repo, planning={
            "enabled": True,
            "requirements_file": str(requirements),
        })
        Path(cfg["work_log"]).write_text("", encoding="utf-8")

        def fake_planner(_cfg, _prompt, *, timeout):
            return {"tasks": [{
                "id": "P101", "kind": "READ",
                "description": "Review the fixture requirements and summarize next steps",
                "requirement_id": "TEST-001", "milestone_id": "TEST-001-M1",
            }]}

        report = planner.plan_once(
            self.project, self.root / "projects", planner=fake_planner,
            quota_evaluator=lambda _settings: {"allowed": True},
        )
        self.assertEqual(report["decision"], "queued")
        self.assertEqual(
            dispatch.parse_manager_response(json.dumps(report), self.project, manager.once_exit_code("queued")),
            report,
        )

    def test_valid_exit_code_contract_preserves_busy_and_no_op(self):
        expected = {
            "queued": 0, "busy": 2, "blocked": 2, "no_op": 3,
            "disabled": 3, "awaiting_acceptance": 3,
            "quota_blocked": 4, "planner_failed": 4,
        }
        for decision, code in expected.items():
            self.assertEqual(manager.once_exit_code(decision), code)
            self.assertEqual(dispatch.manager_exit_code(decision), code)
        self.assertEqual(manager.once_exit_code("unknown"), 4)
        self.assertEqual(manager.once_exit_code(None), 4)
        with contextlib.redirect_stdout(io.StringIO()):
            busy, busy_calls = self.run_tick(
                {"decision": "busy", "reason": "Project lock held; skip planning"},
                manager_rc=2,
            )
            no_op, no_op_calls = self.run_tick(
                {"decision": "no_op", "pending": 0}, manager_rc=3,
            )
        self.assertEqual((busy, len(busy_calls)), (0, 1))
        self.assertEqual((no_op, len(no_op_calls)), (0, 1))

    def test_queued_executes_one(self):
        result, calls = self.run_tick({"decision": "queued"})
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("project_task_worker.py", calls[1][2])

    def test_idle_never_invokes_worker(self):
        for mode in ("awaiting_acceptance", "disabled"):
            result, calls = self.run_tick({"decision": mode})
            self.assertEqual((result, len(calls)), (0, 1))

    def test_existing_pending_runs_worker(self):
        result, calls = self.run_tick({"decision": "no_op", "pending": 3})
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 2)

    def test_no_pending_does_not_run(self):
        result, calls = self.run_tick({"decision": "no_op", "pending": 0})
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)

    def test_untrusted_no_op_refuses(self):
        result, calls = self.run_tick(manager_stdout=json.dumps({
            "project": self.project, "decision": "no_op",
        }))
        self.assertNotEqual(result, 0)
        self.assertEqual(len(calls), 1)

    def test_planner_failed_never_executes(self):
        for mode in ("planner_failed", "blocked", "quota_blocked", "replenish"):
            result, calls = self.run_tick({"decision": mode})
            self.assertNotEqual(result, 0)
            self.assertEqual(len(calls), 1)
        result, calls = self.run_tick({"decision": "busy"})
        self.assertEqual((result, len(calls)), (0, 1))

    def test_nonzero_manager_fails_closed(self):
        result, calls = self.run_tick({"decision": "queued"}, manager_rc=2)
        self.assertNotEqual(result, 0)
        self.assertEqual(len(calls), 1)

    def test_worker_failure_propagates(self):
        result, calls = self.run_tick({"decision": "queued"}, worker_rc=2)
        self.assertNotEqual(result, 0)
        self.assertEqual(len(calls), 2)


class DispatcherHardening(DispatchFixture):
    def test_busy_is_deferred_without_worker(self):
        report = {"project": self.project, "decision": "busy",
                  "reason": "Project lock held; skip planning"}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result, calls = self.run_tick(report, manager_rc=2)
        self.assertEqual(result, 0)
        self.assertEqual([Path(call[2]).name for call in calls], ["project_queue_manager.py"])
        self.assertIn("DEFERRED", out.getvalue())

    def test_busy_malformed_or_mismatched_refused(self):
        reports = [
            ({"decision": "busy", "reason": "different", "project": self.project}, 2, 21),
            ({"decision": "busy", "reason": "Project lock held; skip planning", "project": "other"}, 2, 21),
            ({"decision": "busy", "reason": "Project lock held; skip planning", "project": self.project}, 1, 21),
            ({"decision": "blocked", "reason": "Project lock held; skip planning", "project": self.project}, 2, 20),
        ]
        for report, manager_rc, expected_rc in reports:
            with contextlib.redirect_stderr(io.StringIO()):
                result, calls = self.run_tick(report, manager_rc=manager_rc)
            self.assertEqual(result, expected_rc)
            self.assertEqual(len(calls), 1)

    def test_completed_task_summary(self):
        self.config(queue_text="- [x] **P105 — READ** M3: read\n- [ ] **P106 — EDIT** M3: edit\n")
        (self.project_dir / "worker_journal.json").write_text(
            json.dumps({"current_task": None, "last_completed_task": {"id": "P105", "kind": "READ"}})
        )
        report = {"decision": "no_op", "pending": 2}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result, calls = self.run_tick(report, worker_stdout="worker stdout")
        self.assertEqual(result, 0)
        self.assertIn("TASK SUMMARY last_completed=P105 kind=READ pending=1 blocked=0 invalid=0", out.getvalue())
        self.assertEqual(len(calls), 2)

    def test_observability_never_claims_completion_with_active_journal(self):
        self.config(queue_text="- [ ] **P106 — EDIT** edit\n")
        (self.project_dir / "worker_journal.json").write_text(
            json.dumps({"current_task": {"id": "P106"}, "last_completed_task": {"id": "P105", "kind": "READ"}})
        )
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result, calls = self.run_tick({"decision": "no_op", "pending": 1}, worker_stdout="ok")
        self.assertEqual(result, 0)
        self.assertIn("TASK SUMMARY unavailable", out.getvalue())
        self.assertEqual(len(calls), 2)


class NoOpContract(unittest.TestCase):
    def test_pending_assigned_from_validated_queue_inside_lock(self):
        tree = ast.parse((SRC / "pw_queue_planner.py").read_text())
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "plan_once")
        assigns = [
            n for n in ast.walk(func)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                    and t.value.id == "out" and isinstance(t.slice, ast.Constant)
                    and t.slice.value == "pending" for t in n.targets)
        ]
        self.assertEqual(len(assigns), 1)
        self.assertEqual(ast.unparse(assigns[0].value), "summary['pending_count']")
        self.assertTrue(any(isinstance(n, ast.With) and assigns[0] in list(ast.walk(n)) for n in ast.walk(func)))

    def test_final_noop_does_not_launch_worker(self):
        fixture = DispatchFixture("runTest")
        fixture.setUp()
        try:
            result, calls = fixture.run_tick({"project": fixture.project, "decision": "no_op", "pending": 0})
        finally:
            fixture.doCleanups()
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)

    def test_noop_without_count_remains_refused(self):
        fixture = DispatchFixture("runTest")
        fixture.setUp()
        try:
            result, calls = fixture.run_tick(manager_stdout=json.dumps({
                "project": fixture.project, "decision": "no_op",
            }))
        finally:
            fixture.doCleanups()
        self.assertEqual(result, 21)
        self.assertEqual(len(calls), 1)

    def test_pending_noop_still_routes_worker(self):
        fixture = DispatchFixture("runTest")
        fixture.setUp()
        try:
            result, calls = fixture.run_tick({"project": fixture.project, "decision": "no_op", "pending": 1}, worker_rc=1)
        finally:
            fixture.doCleanups()
        self.assertEqual(result, 23)
        self.assertEqual(len(calls), 2)


class BusyContract(unittest.TestCase):
    def test_planner_exact_response_under_held_lock(self):
        with tempfile.TemporaryDirectory(prefix="pw-busy-test-") as temp:
            root = Path(temp)
            project = root / "pw-e2e-lock-fixture"
            project.mkdir()
            lock = project / "worker.lock"
            queue = project / "queue.md"
            requirements = project / "requirements.md"
            queue.write_text("")
            requirements.write_text("## LOCK-001 — Test\n")
            cfg = {"id": project.name, "lock": str(lock), "queue": str(queue),
                   "cycle_file": str(project / "git_cycle.json"), "worktree": str(root),
                   "branch": "main", "planning": {"enabled": True,
                   "requirements_file": str(requirements)}}
            (project / "config.json").write_text(json.dumps(cfg))
            lock.touch()
            with lock.open("a+") as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = planner.plan_once(project.name, root)
            self.assertEqual(result, {"project": project.name, "decision": "busy",
                                      "reason": "Project lock held; skip planning"})

    def test_other_busy_forms_remain_refused(self):
        fixture = DispatchFixture("runTest")
        fixture.setUp()
        try:
            for response in ({"decision": "busy", "project": "x"},
                             {"decision": "busy", "project": "x", "reason": "wrong"},
                             {"decision": "busy", "project": "other", "reason": "Project lock held; skip planning"}):
                result, calls = fixture.run_tick(response, manager_rc=2)
                self.assertEqual(result, 21)
                self.assertEqual(len(calls), 1)
        finally:
            fixture.doCleanups()

    def test_only_intended_planner_line_changed(self):
        text = (SRC / "pw_queue_planner.py").read_text()
        self.assertEqual(text.count("return {**out, 'decision': 'busy', 'reason': 'Project lock held; skip planning'}"), 1)


class TimerTests(unittest.TestCase):
    def test_unit_execs_dispatcher_without_once(self):
        service, clock = timer.unit_strings("pw-sequence-test", 20, Path("/home/example/.hermes/scripts/pw_dispatch.py"))
        self.assertIn("ExecStart=/usr/bin/python3 -B /home/example/.hermes/scripts/pw_dispatch.py --project pw-sequence-test\n", service)
        self.assertNotIn("project_task_worker.py", service)
        self.assertNotIn("--once", service)
        self.assertIn("OnUnitInactiveSec=20min", clock)
        self.assertNotIn("WantedBy=", service)
        self.assertIn("WantedBy=timers.target", clock)

    def test_rejects_invalid_project_interval_path(self):
        for project, minutes, script in [("Bad!", 20, Path("/tmp/pw_dispatch.py")),
                                         ("valid", 1, Path("/tmp/pw_dispatch.py")),
                                         ("valid", 20, Path("pw_dispatch.py"))]:
            with self.assertRaises(ValueError):
                timer.unit_strings(project, minutes, script)

    def test_emitted_unit_files(self):
        service, clock = timer.unit_strings("pw-sequence-test", 20, Path("/home/leftyfb/.hermes/scripts/pw_dispatch.py"))
        with tempfile.TemporaryDirectory() as temp:
            service_file = Path(temp) / "projectwright-worker-pw-sequence-test.service"
            timer_file = Path(temp) / "projectwright-worker-pw-sequence-test.timer"
            service_file.write_text(service)
            timer_file.write_text(clock)
            self.assertIn("Type=oneshot", service_file.read_text())
            self.assertIn("ExecStart=/usr/bin/python3 -B /home/leftyfb/.hermes/scripts/pw_dispatch.py --project pw-sequence-test", service_file.read_text())
            self.assertNotIn("project_task_worker.py", service_file.read_text())
            self.assertNotIn("--once", service_file.read_text())
            self.assertIn("OnUnitInactiveSec=20min", timer_file.read_text())
            self.assertNotIn("ExecStart=", timer_file.read_text())


class CycleTests(DispatchFixture):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / "approval_probe.py").write_text("initial\n")
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts" / "test_approval_probe.py").write_text("test initial\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "initial"], check=True)
        self.head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        (self.repo / "approval_probe.py").write_text("modified\n")
        (self.repo / "scripts" / "test_approval_probe.py").write_text("test modified\n")
        self.queue_text = "- [x] **P101 — READ** read\n- [x] **P102 — EDIT** edit\n- [ ] **P103 — TEST** test\n- [ ] **P104 — COMMIT** commit\n"
        self.cfg = self.config(queue_text=self.queue_text, worktree=self.repo)
        self.record = {"version": 1, "phase": "active", "branch": "main", "head": self.head,
                       "last_task": "P102", "allowed": ["approval_probe.py", "scripts/test_approval_probe.py"],
                       "snapshot": self._tracked_state()}
        self.cycle = Path(self.cfg["cycle_file"])
        self._save_cycle()

    def _tracked_state(self):
        with patch.dict(os.environ, {"HERMES_PROJECT_CONFIG_DIR": str(self.root / "projects")}):
            worker.load_project(self.project)
            return worker.tracked_state()

    def _save_cycle(self):
        self.cycle.write_text(json.dumps(self.record))

    def test_test_then_commit_permitted(self):
        result, calls = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual((result, [Path(c[2]).name for c in calls]), (0, ["project_queue_manager.py", "project_task_worker.py"]))
        self.cfg_queue = Path(self.cfg["queue"])
        self.cfg_queue.write_text(self.queue_text.replace("[ ] **P103", "[x] **P103"))
        self.record["last_task"] = "P103"
        self._save_cycle()
        result, calls = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual((result, [Path(c[2]).name for c in calls]), (0, ["project_queue_manager.py", "project_task_worker.py"]))

    def test_stale_snapshot_refused(self):
        (self.repo / "approval_probe.py").write_text("unauthorized mutation\n")
        result, _ = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual(result, 20)

    def test_extra_untracked_file_refused(self):
        (self.repo / "intruder.txt").write_text("not authorized")
        result, _ = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual(result, 20)

    def test_wrong_head_branch_and_phase_refused(self):
        for key, value in [("head", "0" * 40), ("branch", "other"), ("phase", "restoring")]:
            original = self.record[key]
            self.record[key] = value
            self._save_cycle()
            result, _ = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
            self.assertEqual(result, 20, key)
            self.record[key] = original
            self._save_cycle()

    def test_wrong_previous_task_and_kind_refused(self):
        self.record["last_task"] = "P101"
        self._save_cycle()
        result, _ = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual(result, 20)
        self.record["last_task"] = "P102"
        self._save_cycle()
        Path(self.cfg["queue"]).write_text(self.queue_text.replace("P103 — TEST", "P103 — EDIT"))
        result, _ = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual(result, 20)

    def test_unrelated_blocker_or_missing_cycle_refused(self):
        result, _ = self.run_tick({"decision": "blocked", "reason": "active_git_cycle, invalid_queue"}, manager_rc=2)
        self.assertEqual(result, 20)
        self.cycle.unlink()
        result, _ = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual(result, 20)

    def test_active_journal_refused(self):
        (self.project_dir / "worker_journal.json").write_text(json.dumps({"current_task": {"id": "P103"}}))
        result, _ = self.run_tick({"decision": "blocked", "reason": "branch_or_worktree, active_git_cycle"}, manager_rc=2)
        self.assertEqual(result, 20)

    def test_manager_no_op_does_not_start_worker(self):
        calls = []

        def runner(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 3, json.dumps({"project": self.project, "decision": "no_op", "pending": 0}), "")

        result = dispatch.run_tick(self.project, self.scripts, runner=runner)
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
