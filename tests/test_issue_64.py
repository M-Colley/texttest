import logging
import threading
import unittest
from unittest import mock

from texttestlib.default.actionrunner import BaseActionRunner


class DummyRunner(BaseActionRunner):
    def __init__(self):
        super().__init__({}, logging.getLogger("test_issue_64"))
        self.started = []
        self.test1_started = threading.Event()
        self.allow_test1_finish = threading.Event()
        self.test2_started = threading.Event()

    def runTest(self, test):
        self.started.append(test.uniqueName)
        if test.uniqueName == "t1":
            self.test1_started.set()
            self.allow_test1_finish.wait(timeout=5)
        elif test.uniqueName == "t2":
            self.test2_started.set()
        state = mock.MagicMock()
        state.isComplete.return_value = True
        state.hasFailed.return_value = False
        test.state = state

    def cleanup(self):
        pass

    def killTests(self):
        pass


def _make_test(name):
    t = mock.MagicMock()
    t.classId.return_value = "test-case"
    t.uniqueName = name
    t.state.isComplete.return_value = False
    t.state.hasFailed.return_value = False
    t.changeState.side_effect = lambda s: setattr(t, "state", s)
    return t


class TestIssue64(unittest.TestCase):
    def test_pause_lets_running_test_finish_and_holds_next_until_continue(self):
        runner = DummyRunner()
        t1 = _make_test("t1")
        t2 = _make_test("t2")
        runner.notifyAdd(t1, True)
        runner.notifyAdd(t2, True)
        runner.notifyAllRead([])

        worker = threading.Thread(target=runner.runAllTests)
        worker.start()

        self.assertTrue(runner.test1_started.wait(timeout=2))
        runner.notifyPause()
        self.assertTrue(runner.paused)

        # Non-blocking queue fetch (used by grid slave reuse) returns None while paused
        self.assertIsNone(runner.getItemFromQueue(runner.testQueue, block=False))

        # Let t1 complete; t2 must remain held while paused
        runner.allow_test1_finish.set()
        self.assertFalse(runner.test2_started.wait(timeout=0.15))
        self.assertEqual(runner.started, ["t1"])

        # Continue dispatches t2 and finishes cleanly
        runner.notifyContinue()
        self.assertFalse(runner.paused)
        self.assertTrue(runner.test2_started.wait(timeout=2))
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(runner.started, ["t1", "t2"])

    def test_kill_processes_unblocks_paused_runner_and_cancels_queued_tests(self):
        runner = DummyRunner()
        t1 = _make_test("t1")
        runner.notifyAdd(t1, True)
        runner.notifyAllRead([])
        runner.notifyPause()

        worker = threading.Thread(target=runner.runAllTests)
        worker.start()

        runner.notifyKillProcesses()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(runner.started, [])
        self.assertEqual(t1.state.category, "cancelled")


if __name__ == "__main__":
    unittest.main()
