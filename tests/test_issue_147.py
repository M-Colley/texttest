import os
import tempfile
import unittest
from unittest import mock

from texttestlib import plugins
from texttestlib.default import sandbox


class TestIssue147(unittest.TestCase):
    def test_windows_prefers_real_python_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv_bin = os.path.join(tmp, "venv", "Scripts")
            os.makedirs(venv_bin)
            py_exe = os.path.join(venv_bin, "python.exe")
            with open(py_exe, "wb") as f:
                f.write(b"MZ")

            with mock.patch.object(plugins.os, "name", "nt"), mock.patch.object(
                plugins.os, "pathsep", ";"
            ), mock.patch("shutil.which", side_effect=lambda cmd, path=None: py_exe if path and venv_bin in path else None):
                self.assertEqual(plugins.getInterpreter("collate.py", env={"PATH": venv_bin}), "python")

    def test_windows_skips_zero_byte_windowsapps_stub_and_falls_back_cleanly(self):
        stub = r"C:\Users\Alice\AppData\Local\Microsoft\WindowsApps\python.exe"
        real = r"C:\Python312\python.exe"

        def fake_which(cmd, path=None):
            if not path:
                return None
            parts = path.split(";")
            for part in parts:
                if "WindowsApps" in part:
                    return stub
                if "Python312" in part:
                    return real
            return None

        with mock.patch.object(plugins.os, "name", "nt"), mock.patch.object(
            plugins.os, "pathsep", ";"
        ), mock.patch.object(plugins.os.path, "getsize", side_effect=lambda p: 0 if p == stub else 1024), mock.patch(
            "shutil.which", side_effect=fake_which
        ):
            # Stub comes first on PATH, so full path to real python is returned to bypass the stub
            env = {"PATH": r"C:\Users\Alice\AppData\Local\Microsoft\WindowsApps;C:\Python312"}
            self.assertEqual(plugins.getInterpreter("myscript.py", env=env), real)

            # Only stub on PATH + unfrozen Python (including paths with spaces) -> falls back to sys.executable
            stub_only = {"PATH": r"C:\Users\Alice\AppData\Local\Microsoft\WindowsApps"}
            for exe_path in (r"C:\Program Files\Python313\python.exe", r"C:\Custom Dir\Python313\python.exe"):
                with mock.patch.object(plugins.sys, "frozen", False, create=True), mock.patch.object(
                    plugins.sys, "executable", exe_path
                ):
                    interp = plugins.getInterpreter("myscript.py", env=stub_only)
                    self.assertEqual(plugins.splitcmd(interp), [exe_path])

            # Frozen TextTest.exe without Python on PATH -> falls back to py -3
            with mock.patch.object(plugins.sys, "frozen", True, create=True), mock.patch.object(
                plugins.sys, "executable", r"C:\TextTest\bin\texttest.exe"
            ):
                self.assertEqual(plugins.getInterpreter("myscript.py", env=stub_only), "py -3")

    def test_run_collation_script_passes_test_run_env_path(self):
        collator = sandbox.CollateFiles()
        test = mock.MagicMock()
        test.getRunEnvironment.return_value = {"PATH": r"C:\CustomVenv\Scripts"}
        test.getDirectory.return_value = r"C:\tmp\sandbox"

        with mock.patch.object(sandbox.os, "name", "nt"), mock.patch.object(
            sandbox.plugins, "getInterpreter", return_value="python"
        ) as mock_get_interp, mock.patch.object(sandbox.subprocess, "Popen") as mock_popen:
            collator.runCollationScript(["extract.py", "raw.log"], test, None, None, None)

        mock_get_interp.assert_called_once()
        _, kwargs = mock_get_interp.call_args
        self.assertIn(r"C:\CustomVenv\Scripts", kwargs["env"]["PATH"])
        called_args = mock_popen.call_args.args[0]
        self.assertEqual(called_args, ["python", "extract.py", "raw.log"])


if __name__ == "__main__":
    unittest.main()
