"""Server-only scheduler checks with fake processes; no scientific execution."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops/spatial_history"))
import public_geometry_workers as scheduler

REAL_SLEEP = scheduler.time.sleep


class FakeProcess:
    def __init__(self, task, harness):
        self.task = task
        self.harness = harness
        self.ready_at = harness.tick + task.get("ticks", 1)
        self.returncode = None
        self.waited = False

    def poll(self):
        if self.harness.tick >= self.ready_at and self.returncode is None:
            self.returncode = self.task.get("exit", 0)
        return self.returncode

    def wait(self):
        if self.poll() is None:
            raise AssertionError("wait called on a running child")
        self.waited = True
        return self.returncode


class Harness:
    def __init__(self):
        self.tick = 0
        self.handles = []
        self.receipts = []
        self.aborted = []
        self.peak_active = 0

    def sleep(self, _seconds):
        self.tick += 1

    def launch(self, task):
        handle = FakeProcess(task, self)
        self.handles.append(handle)
        self.peak_active = max(self.peak_active, sum(not child.waited for child in self.handles))
        return handle

    def completed(self, task, handle, error):
        if not handle.waited:
            raise AssertionError("receipt callback before wait")
        self.receipts.append((task["id"], error))
        if handle.returncode and error is None:
            raise ValueError("nonzero child exit")
        return task["id"]

    def abort(self, handle):
        self.aborted.append(handle.task["id"])
        handle.returncode = -9
        handle.wait()


class PublicGeometryWorkersTests(unittest.TestCase):
    def setUp(self):
        self.harness = Harness()
        sleeper = patch.object(scheduler.time, "sleep", self.harness.sleep)
        sleeper.start()
        self.addCleanup(sleeper.stop)
        # Signal behavior is covered separately without changing real masks in
        # this process or depending on the server's asynchronous signal load.
        masker = patch.object(scheduler.signal, "pthread_sigmask", return_value=set(), create=True)
        self.mask = masker.start()
        self.addCleanup(masker.stop)

    def run_tasks(self, tasks, workers=4, **callbacks):
        return scheduler.dispatch(tasks, workers,
                                  callbacks.get("launch", self.harness.launch),
                                  callbacks.get("completed", self.harness.completed),
                                  callbacks.get("checkpoint", lambda: None),
                                  callbacks.get("abort", self.harness.abort), interval_s=0)

    def check_concurrency(self, workers):
        tasks = [{"id": str(index)} for index in range(16)]
        self.assertEqual(self.run_tasks(tasks, workers), [task["id"] for task in tasks])
        self.assertEqual(self.harness.peak_active, workers)
        self.assertEqual(self.harness.aborted, [])
        self.assertTrue(all(child.waited for child in self.harness.handles))

    def test_one_worker(self):
        self.check_concurrency(1)

    def test_four_workers(self):
        self.check_concurrency(4)

    def test_sixteen_workers(self):
        self.check_concurrency(16)

    def test_out_of_order_completion_returns_registration_order(self):
        tasks = [{"id": str(index), "ticks": 4 - index} for index in range(4)]
        self.assertEqual(self.run_tasks(tasks), ["0", "1", "2", "3"])
        self.assertEqual([row[0] for row in self.harness.receipts], ["3", "2", "1", "0"])

    def test_nonzero_exit_stops_launches_and_reaps_active_children(self):
        tasks = [{"id": str(index), "ticks": 1 if index == 0 else 5,
                  "exit": 3 if index == 0 else 0} for index in range(8)]
        with self.assertRaisesRegex(ValueError, "nonzero"):
            self.run_tasks(tasks)
        self.assertEqual(len(self.harness.handles), 4)
        self.assertEqual(self.harness.aborted, ["1", "2", "3"])
        self.assertEqual(len(self.harness.receipts), 4)
        self.assertTrue(all(child.waited for child in self.harness.handles))
        self.assertTrue(all("cancelled after" in error for _, error in self.harness.receipts[1:]))

    def test_launch_failure_cleans_every_previously_launched_child(self):
        def launch(task):
            if task["id"] == "2":
                raise OSError("cannot launch")
            return self.harness.launch(task)
        with self.assertRaisesRegex(OSError, "cannot launch"):
            self.run_tasks([{"id": str(index)} for index in range(8)], launch=launch)
        self.assertEqual(self.harness.aborted, ["0", "1"])
        self.assertEqual(len(self.harness.receipts), 2)

    def test_checkpoint_failure_cleans_live_children_without_filling_slots(self):
        def checkpoint():
            if len(self.harness.handles) == 2:
                raise MemoryError("whole-stage memory")
        with self.assertRaisesRegex(MemoryError, "whole-stage"):
            self.run_tasks([{"id": str(index)} for index in range(8)], checkpoint=checkpoint)
        self.assertEqual(self.harness.aborted, ["0", "1"])
        self.assertEqual(len(self.harness.handles), 2)

    def test_completed_callback_failure_never_repeats_receipt(self):
        def completed(task, handle, error):
            self.harness.completed(task, handle, error)
            if task["id"] == "0":
                raise OSError("receipt write failed")
        with self.assertRaisesRegex(OSError, "receipt write"):
            self.run_tasks([{"id": str(index)} for index in range(4)], completed=completed)
        self.assertEqual([row[0] for row in self.harness.receipts].count("0"), 1)
        self.assertEqual(self.harness.aborted, ["1", "2", "3"])
        self.assertEqual(len(self.harness.receipts), 4)

    def test_invalid_worker_counts_are_rejected_before_launch(self):
        for value in (0, -1, 17, 4.0, True, "4", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_tasks([{"id": "a"}], value)
        self.assertEqual(self.harness.handles, [])

    def test_duplicate_or_missing_or_unhashable_ids_are_rejected(self):
        for tasks in ([{"id": "a"}, {"id": "a"}], [{}], ["a"], [{"id": []}]):
            with self.subTest(tasks=tasks), self.assertRaises(ValueError):
                self.run_tasks(tasks)
        self.assertEqual(self.harness.handles, [])

    def test_invalid_poll_interval_is_rejected_before_launch(self):
        for value in (-1, float("nan"), float("inf"), True, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                scheduler.dispatch([{"id": "a"}], 1, self.harness.launch, self.harness.completed,
                                   lambda: None, self.harness.abort, interval_s=value)
        self.assertEqual(self.harness.handles, [])

    def test_empty_tasks_do_not_call_callbacks(self):
        callback = Mock(side_effect=AssertionError("unexpected callback"))
        self.assertEqual(scheduler.dispatch([], 4, callback, callback, callback, callback), [])

    def test_failed_abort_does_not_prevent_other_children_cleanup(self):
        def checkpoint():
            if len(self.harness.handles) == 4:
                raise ValueError("stage stopped")
        def abort(handle):
            if handle.task["id"] == "0":
                self.harness.aborted.append("0")
                raise OSError("kill failed")
            self.harness.abort(handle)
        with self.assertRaisesRegex(ValueError, "stage stopped") as caught:
            self.run_tasks([{"id": str(index)} for index in range(8)],
                           checkpoint=checkpoint, abort=abort)
        self.assertEqual(self.harness.aborted, ["0", "1", "2", "3"])
        self.assertEqual([row[0] for row in self.harness.receipts], ["1", "2", "3"])
        self.assertIn("kill failed", "\n".join(caught.exception.__notes__))

    def test_abort_error_after_exit_can_still_reap_and_save_receipt(self):
        def checkpoint():
            if len(self.harness.handles) == 1:
                raise ValueError("stop")
        def abort(handle):
            handle.returncode = -9
            raise OSError("post-kill failure")
        with self.assertRaisesRegex(ValueError, "stop") as caught:
            self.run_tasks([{"id": "a"}], checkpoint=checkpoint, abort=abort)
        self.assertTrue(self.harness.handles[0].waited)
        self.assertEqual(len(self.harness.receipts), 1)
        self.assertIn("post-kill failure", "\n".join(caught.exception.__notes__))

    def test_cleanup_receipt_failure_does_not_prevent_later_cleanup(self):
        def checkpoint():
            if len(self.harness.handles) == 4:
                raise ValueError("stop")
        def completed(task, handle, error):
            self.harness.completed(task, handle, error)
            if task["id"] == "0":
                raise OSError("cancel receipt failed")
        with self.assertRaisesRegex(ValueError, "stop") as caught:
            self.run_tasks([{"id": str(index)} for index in range(4)],
                           checkpoint=checkpoint, completed=completed)
        self.assertEqual(self.harness.aborted, ["0", "1", "2", "3"])
        self.assertEqual(len(self.harness.receipts), 4)
        self.assertIn("cancel receipt failed", "\n".join(caught.exception.__notes__))

    def test_signal_after_launch_registration_does_not_orphan_child(self):
        restores = 0
        def mask(how, _signals):
            nonlocal restores
            if how == signal.SIG_SETMASK:
                restores += 1
                if restores == 1:
                    raise KeyboardInterrupt("pending signal")
            return set()
        self.mask.side_effect = mask
        with self.assertRaisesRegex(KeyboardInterrupt, "pending signal"):
            self.run_tasks([{"id": "a"}, {"id": "b"}])
        self.assertEqual(self.harness.aborted, ["a"])
        self.assertEqual(len(self.harness.receipts), 1)
        self.assertTrue(self.harness.handles[0].waited)

    def test_poll_failure_cleans_all_active_children(self):
        def launch(task):
            handle = self.harness.launch(task)
            if task["id"] == "a":
                handle.poll = Mock(side_effect=[OSError("poll failed"), -9])
            return handle
        with self.assertRaisesRegex(OSError, "poll failed"):
            self.run_tasks([{"id": "a"}, {"id": "b"}], launch=launch)
        self.assertEqual(self.harness.aborted, ["a", "b"])
        self.assertTrue(all(child.waited for child in self.harness.handles))

    def test_wait_failure_still_aborts_and_saves_one_cancelled_receipt(self):
        def launch(task):
            handle = self.harness.launch(task)
            original_wait = handle.wait
            calls = 0
            def wait():
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("wait interrupted")
                return original_wait()
            handle.wait = wait
            return handle
        with self.assertRaisesRegex(OSError, "wait interrupted"):
            self.run_tasks([{"id": "a"}], launch=launch)
        self.assertEqual(self.harness.aborted, ["a"])
        self.assertEqual(len(self.harness.receipts), 1)
        self.assertIn("cancelled after", self.harness.receipts[0][1])

    def test_signal_after_cleanup_is_not_allowed_to_hide_original_failure(self):
        restores = 0
        def mask(how, _signals):
            nonlocal restores
            if how == signal.SIG_SETMASK:
                restores += 1
                if restores == 2:
                    raise KeyboardInterrupt("second signal")
            return set()
        def checkpoint():
            if self.harness.handles:
                raise ValueError("original failure")
        self.mask.side_effect = mask
        with self.assertRaisesRegex(ValueError, "original failure") as caught:
            self.run_tasks([{"id": "a"}], checkpoint=checkpoint)
        self.assertEqual(self.harness.aborted, ["a"])
        self.assertEqual(len(self.harness.receipts), 1)
        self.assertIn("second signal", "\n".join(caught.exception.__notes__))

    def test_serial_and_four_real_children_produce_identical_independent_outputs(self):
        # This is a short server-only process smoke check, not a geometry run.
        launched = []
        code = ("import json, sys\n"
                "index = int(sys.argv[2])\n"
                "payload = json.dumps({'id': index, 'square': index * index}, sort_keys=True) + '\\n'\n"
                "with open(sys.argv[1], 'xb') as stream:\n"
                "    stream.write(payload.encode('utf-8'))\n")
        def abort(handle):
            if handle.poll() is None:
                os.killpg(handle.pid, signal.SIGKILL)
            handle.wait()
        results = []
        with tempfile.TemporaryDirectory() as temporary, patch.object(scheduler.time, "sleep", REAL_SLEEP):
            for workers in (1, 4):
                directory = Path(temporary) / str(workers)
                directory.mkdir()
                deadline = scheduler.time.monotonic() + 30
                def checkpoint():
                    if scheduler.time.monotonic() > deadline:
                        raise TimeoutError("standard-library child smoke deadline")
                def launch(task):
                    output = directory / f"task-{task['id']:02d}.json"
                    handle = subprocess.Popen([sys.executable, "-B", "-c", code, str(output), str(task["id"])],
                                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL, start_new_session=True)
                    launched.append(handle)
                    return handle
                def completed(task, handle, error):
                    self.assertIsNone(error)
                    self.assertEqual(handle.returncode, 0)
                    return (task["id"], (directory / f"task-{task['id']:02d}.json").read_bytes())
                result = scheduler.dispatch([{"id": index} for index in range(8)], workers,
                                            launch, completed, checkpoint, abort, interval_s=0.01)
                self.assertEqual([row[0] for row in result], list(range(8)))
                self.assertEqual(sorted(path.name for path in directory.iterdir()),
                                 [f"task-{index:02d}.json" for index in range(8)])
                results.append(result)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(launched), 16)
        self.assertTrue(all(handle.returncode == 0 for handle in launched))


if __name__ == "__main__":
    unittest.main()
