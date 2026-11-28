import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from texttestlib.default import extracttest, scripts


class TestIssue65(unittest.TestCase):
    def _make_fake_test(self, root_dir):
        src_dir = os.path.join(root_dir, "suite", "Test1")
        os.makedirs(src_dir)
        data_file = os.path.join(src_dir, "config_data.txt")
        with open(data_file, "w", encoding="utf-8") as f:
            f.write("alpha=42\n")
        stdin_file = os.path.join(src_dir, "input.myapp")
        with open(stdin_file, "w", encoding="utf-8") as f:
            f.write("hello stdin\n")

        tmp_sandbox = os.path.join(root_dir, "tt_tmp", "myapp", "Test1")

        app = mock.MagicMock()
        app.name = "myapp"
        app.writeDirectory = os.path.join(root_dir, "tt_tmp", "myapp")
        app.localWriteDirectory = app.writeDirectory
        app.getConfigEnvironment.return_value = ([], [])
        app.getConfigValue.side_effect = lambda k, **kw: "classic" if k == "filename_convention_scheme" else None
        app.getStdinName.return_value = "input"
        app.hasAutomaticCputimeChecking.return_value = False
        app.getRunMachine.return_value = "localhost"
        app.hasChanged.side_effect = lambda var, val: var in ("MY_VAR", "SANDBOX_REF")

        test = mock.MagicMock()
        test.name = "Test1"
        test.app = app
        test.properties = {}
        test.environment = {"MY_VAR": "custom_value", "SANDBOX_REF": tmp_sandbox + "/sub"}
        test.getIndent.return_value = ""
        test.getRelPath.return_value = "Test1"
        test.getDirectory.side_effect = lambda temporary=0, local=0, **kw: tmp_sandbox if temporary else src_dir

        def get_config(key, expandVars=True):
            mapping = {
                "copy_test_path": ["config_data.txt"],
                "copy_test_path_merge": [],
                "partial_copy_test_path": [],
                "link_test_path": [],
                "test_data_require": [],
                "test_data_environment": {},
                "extra_test_process_postfix": [],
                "interpreters": {},
                "executable": sys.executable,
                "remote_copy_program": "",
            }
            return mapping.get(key, [])

        test.getConfigValue.side_effect = get_config
        test.getCompositeConfigValue.return_value = ""
        test.getAllPathNames.side_effect = lambda fileName, *a: [os.path.join(src_dir, fileName)]
        test.getFileName.side_effect = lambda stem, *a: stdin_file if stem == "input" else None
        test.getRunEnvironment.return_value = dict(test.environment)
        test.getCommandLineOptions.side_effect = lambda stem="options": (
            ["-c", "import os, sys; print(os.environ['MY_VAR'], open('config_data.txt').read().strip(), sys.stdin.read().strip())"]
            if stem == "options"
            else []
        )
        return test

    def test_extract_test_api_generates_posix_and_windows_launchers(self):
        with tempfile.TemporaryDirectory() as root_dir:
            test = self._make_fake_test(root_dir)
            out_posix = os.path.join(root_dir, "extracted_posix")
            sh_path = extracttest.extractTest(test, out_posix, platformName="posix")

            self.assertEqual(sh_path, os.path.join(out_posix, "run_test.sh"))
            self.assertTrue(os.path.isfile(os.path.join(out_posix, "config_data.txt")))
            self.assertTrue(os.path.isfile(os.path.join(out_posix, "input.myapp")))
            sh_content = open(sh_path, encoding="utf-8").read()
            self.assertIn("MY_VAR=", sh_content)
            self.assertIn(out_posix + "/sub", sh_content)
            self.assertIn("< input.myapp", sh_content)

            out_win = os.path.join(root_dir, "extracted_win")
            bat_path = extracttest.extractTest(test, out_win, platformName="nt")
            self.assertEqual(bat_path, os.path.join(out_win, "run_test.bat"))
            bat_content = open(bat_path, encoding="utf-8").read()
            self.assertIn('set "MY_VAR=custom_value"', bat_content)
            self.assertIn("< input.myapp", bat_content)

            if os.name == "nt":
                res = subprocess.run(["cmd.exe", "/c", bat_path], capture_output=True, text=True, check=True)
            else:
                res = subprocess.run(["/bin/sh", sh_path], capture_output=True, text=True, check=True)
            self.assertEqual(res.stdout.strip(), "custom_value alpha=42 hello stdin")

    def test_extract_test_cli_script_handles_single_and_multiple_tests(self):
        with tempfile.TemporaryDirectory() as root_dir:
            test1 = self._make_fake_test(root_dir)
            dest_dir = os.path.join(root_dir, "cli_out")
            script = scripts.ExtractTest([f"dir={dest_dir}"])
            with mock.patch("texttestlib.plugins.log", mock.MagicMock()):
                script(test1)
            expected_ext = ".bat" if os.name == "nt" else ".sh"
            self.assertTrue(os.path.isfile(os.path.join(dest_dir, "Test1", "run_test" + expected_ext)))


if __name__ == "__main__":
    unittest.main()
