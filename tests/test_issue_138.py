import os
import tempfile
import unittest
from unittest import mock

from texttestlib import logconfiggen, plugins
from texttestlib.default import performance, sandbox
from texttestlib.queuesystem import sge


class TestIssue138(unittest.TestCase):
    def test_cp1252_locale_reads_and_writes_utf8_bytes_with_0x90_without_crash(self):
        # UTF-8 U+0190 ('Ɛ') encodes as b'\xc6\x90', containing byte 0x90 which is undefined in cp1252
        utf8_line = "CPU time   :       2.5 sec. on host-\u0190\n".encode("utf-8")
        self.assertIn(0x90, utf8_line)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            plugins, "getLocaleEncoding", return_value="cp1252"
        ):
            perf_file = os.path.join(tmp, "performance.myapp")
            with open(perf_file, "wb") as f:
                f.write(utf8_line)

            self.assertEqual(performance.getPerformance(perf_file), 2.5)
            desc = performance.describePerformance(perf_file)
            self.assertIn("2 seconds", desc)

            # ExtractPerformanceFiles.findValues + saveFile under cp1252
            log_file = os.path.join(tmp, "output.myapp")
            with open(log_file, "wb") as f:
                f.write("prefix-\u0190 Metric: 12.34 seconds\n".encode("utf-8"))

            test = mock.MagicMock()
            test.getCompositeConfigValue.return_value = "locale"
            extractor = sandbox.ExtractPerformanceFiles(mock.MagicMock())
            vals = extractor.findValues(test, log_file, "Metric:")
            self.assertEqual(vals, [12.34])

            out_perf = os.path.join(tmp, "saved_perf.myapp")
            extractor.saveFile(out_perf, "Total Metric  :      12.3 seconds on host-\u0190\n")
            self.assertEqual(performance.getPerformance(out_perf), 12.3)

            # logconfiggen.findLoggerNames on UTF-8 source containing 0x90
            src_py = os.path.join(tmp, "sample.py")
            with open(src_py, "wb") as f:
                f.write('# comment \u0190\nlogging.getLogger("MyDiagLogger")\n'.encode("utf-8"))
            self.assertEqual(logconfiggen.findLoggerNames(src_py), ["MyDiagLogger"])

            # SGE error and hostfile readers under cp1252
            err_file = os.path.join(tmp, "slave_start_errors")
            with open(err_file, "wb") as f:
                f.write("slave error \u0190\n".encode("utf-8"))
            qs = object.__new__(sge.QueueSystem)
            qs.getSlaveStartErrorFile = lambda: err_file
            qs.makeHeader = lambda h: f"=== {h} ===\n"
            msg = qs.getSlaveStartErrorMessage()
            self.assertIn("slave error", msg)


if __name__ == "__main__":
    unittest.main()
