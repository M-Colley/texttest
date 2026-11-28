import pathlib
import re
import shutil
import subprocess
import unittest


JS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "texttestlib"
    / "default"
    / "batch"
    / "testoverview_javascript"
)


class TestIssue121(unittest.TestCase):
    def test_bundled_jquery_is_3_7_or_newer(self):
        jquery_text = (JS_DIR / "jquery.js").read_text(encoding="utf-8")
        match = re.search(r"jQuery v(\d+)\.(\d+)\.(\d+)", jquery_text)
        self.assertIsNotNone(match, "Expected jQuery version header in jquery.js")
        version = tuple(int(part) for part in match.groups())
        self.assertGreaterEqual(version, (3, 7, 1))

    def test_report_scripts_avoid_removed_jquery_1x_apis(self):
        removed_patterns = [
            r"\.\bsize\s*\(",
            r"\.\bbind\s*\(",
            r"\.\bunbind\s*\(",
            r"\.\blive\s*\(",
            r"\.\bdie\s*\(",
            r"\.\bandSelf\s*\(",
            r"\$\.find\s*\(",
            r"<table><table>",
        ]
        for script_name in ("filter.js", "comment.js", "commentlist.js"):
            content = (JS_DIR / script_name).read_text(encoding="utf-8")
            # Row.prototype.size() is a custom method on Row (`row.size()`), not jQuery
            filtered = content.replace("Row.prototype.size", "Row_size").replace("row.size()", "row_size()")
            for pattern in removed_patterns:
                self.assertIsNone(
                    re.search(pattern, filtered),
                    f"Found deprecated/removed jQuery pattern {pattern!r} in {script_name}",
                )

    def test_javascript_syntax_valid_when_node_present(self):
        node = shutil.which("node")
        if not node:
            return
        for script_name in ("jquery.js", "filter.js", "comment.js", "commentlist.js"):
            res = subprocess.run([node, "--check", str(JS_DIR / script_name)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == "__main__":
    unittest.main()
