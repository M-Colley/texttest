import io
import os
import tempfile
import unittest

from texttestlib import plugins
from texttestlib.default import Config
from texttestlib.default.fpfilter import PatternFloatingPointFilter, fpfilterWithPatterns
from texttestlib.default.rundependent import FilterOnTempFile, FloatingPointFilter


class FakeApp:
    name = "app"


class FakeTest:
    def __init__(self, tmpDir, configValues):
        self.app = FakeApp()
        self._tmpDir = tmpDir
        self._configValues = configValues

    def getCompositeConfigValue(self, key, stem):
        return self._configValues.get(key, [] if key in ("run_dependent_text", "unordered_text", "floating_point_pattern") else "")

    def getConfigValue(self, key):
        return self._configValues.get(key, "locale")

    def getRelPath(self):
        return "suite/test1"

    def makeTmpFileName(self, name, forFramework=0):
        return os.path.join(self._tmpDir, name)

    def getFileName(self, stem):
        return os.path.join(self._tmpDir, stem + "." + self.app.name)


class TestIssue91FloatingPointPattern(unittest.TestCase):
    def test_line_pattern_filters_only_matching_lines(self):
        fromlines = [
            "id=1001 bits=010101\n",
            "metric=1.000\n",
            "id=2001 bits=111000\n",
        ]
        tolines = [
            "id=1002 bits=010100\n",
            "metric=1.005\n",
            "id=2001 bits=111001\n",
        ]
        out = io.StringIO()
        fpfilterWithPatterns(fromlines, tolines, out, tolerance=10.0, patterns=[r"^metric="])
        self.assertEqual(
            out.getvalue().splitlines(True),
            [
                "id=1002 bits=010100\n",
                "metric=1.000\n",
                "id=2001 bits=111001\n",
            ],
        )

    def test_group_pattern_filters_only_captured_groups_and_preserves_ids(self):
        fromlines = [
            '<vehicle id="1001" x="12.340" y="56.780" bits="010101"/>\n',
            '<vehicle id="2001" x="12.340" y="56.780" bits="010101"/>\n',
            '<vehicle id="3001" x="12.340" y="56.780" bits="010101"/>\n',
        ]
        tolines = [
            '<vehicle id="1001" x="12.345" y="56.775" bits="010101"/>\n',
            '<vehicle id="2002" x="12.345" y="56.775" bits="010101"/>\n',
            '<vehicle id="3001" x="12.345" y="56.775" bits="010100"/>\n',
        ]
        out = io.StringIO()
        fpfilterWithPatterns(
            fromlines,
            tolines,
            out,
            tolerance=10.0,
            patterns=[r'x="([^"]+)" y="([^"]+)"'],
        )
        self.assertEqual(
            out.getvalue().splitlines(True),
            [
                '<vehicle id="1001" x="12.340" y="56.780" bits="010101"/>\n',
                '<vehicle id="2002" x="12.345" y="56.775" bits="010101"/>\n',
                '<vehicle id="3001" x="12.345" y="56.775" bits="010100"/>\n',
            ],
        )

    def test_multiple_group_patterns_and_different_formatted_widths(self):
        fromlines = ['<edge id="42" speed="1.5" density="0.25"/>\n']
        tolines = ['<edge id="42" speed="1.5001" density="0.25005"/>\n']
        out = io.StringIO()
        fpfilterWithPatterns(
            fromlines,
            tolines,
            out,
            tolerance=0.001,
            patterns=[r'speed="([^"]+)"', r'density="([^"]+)"'],
        )
        self.assertEqual(out.getvalue(), fromlines[0])

    def test_repeated_matches_on_single_line_and_relative_tolerance(self):
        fromlines = ["id=99 val=100.0 val=200.0\n", "id=99 val=100.0 val=200.0\n"]
        tolines = ["id=99 val=100.5 val=201.0\n", "id=99 val=100.5 val=220.0\n"]
        out = io.StringIO()
        fpfilterWithPatterns(
            fromlines,
            tolines,
            out,
            tolerance=None,
            relTolerance=0.01,
            patterns=[r"val=([0-9.eE+-]+)"],
        )
        self.assertEqual(
            out.getvalue().splitlines(True),
            [
                "id=99 val=100.0 val=200.0\n",
                "id=99 val=100.5 val=220.0\n",
            ],
        )

    def test_named_and_optional_groups_and_split_option(self):
        fromlines = ["coords=1.0,2.0 label=ok\n"]
        tolines = ["coords=1.005,1.995 label=ok\n"]
        out = io.StringIO()
        fpfilterWithPatterns(
            fromlines,
            tolines,
            out,
            tolerance=0.01,
            split=",",
            patterns=[r"coords=(?P<vec>[^ ]+)(?: extra=([0-9.]+))?"],
        )
        self.assertEqual(out.getvalue(), fromlines[0])

    def test_difflib_mode_and_trailing_lines(self):
        fromlines = ["header id=1\n", "score=10.0\n", "footer id=2\n"]
        tolines = ["header id=1\n", "score=10.02\n", "footer id=2\n", "extra=99\n"]
        out = io.StringIO()
        fpfilterWithPatterns(fromlines, tolines, out, tolerance=0.05, useDifflib=True, patterns=[r"^score="])
        self.assertEqual(out.getvalue().splitlines(True), ["header id=1\n", "score=10.0\n", "footer id=2\n", "extra=99\n"])

    def test_invalid_regex_raises_texttest_error(self):
        out = io.StringIO()
        with self.assertRaises(plugins.TextTestError):
            fpfilterWithPatterns(["a\n"], ["b\n"], out, tolerance=0.1, patterns=["[unterminated"])

    def test_filter_on_temp_file_selects_pattern_filter_when_configured(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            origPath = os.path.join(tmpDir, "output.app")
            with open(origPath, "w", encoding="utf-8") as f:
                f.write("id=100 val=1.00\n")

            action = FilterOnTempFile()
            testWithPatterns = FakeTest(tmpDir, {
                "floating_point_tolerance": 0.1,
                "relative_float_tolerance": 0.0,
                "floating_point_split": "",
                "floating_point_pattern": [r"val=([0-9.]+)"],
                "file_encoding": "utf-8",
            })
            filters = action._makeAllFilters(testWithPatterns, "output", testWithPatterns.app)
            self.assertEqual(len(filters), 1)
            self.assertIsInstance(filters[0], PatternFloatingPointFilter)

            out = io.StringIO()
            filters[0].filterFile(io.StringIO("id=100 val=1.05\n"), out)
            self.assertEqual(out.getvalue(), "id=100 val=1.00\n")

            outDiffId = io.StringIO()
            filters[0].filterFile(io.StringIO("id=101 val=1.05\n"), outDiffId)
            self.assertEqual(outDiffId.getvalue(), "id=101 val=1.05\n")

            testWithoutPatterns = FakeTest(tmpDir, {
                "floating_point_tolerance": 0.1,
                "relative_float_tolerance": 0.0,
                "floating_point_split": "",
                "floating_point_pattern": [],
                "file_encoding": "utf-8",
            })
            defaultFilters = action._makeAllFilters(testWithoutPatterns, "output", testWithoutPatterns.app)
            self.assertEqual(len(defaultFilters), 1)
            self.assertIsInstance(defaultFilters[0], FloatingPointFilter)

    def test_config_registers_floating_point_pattern_default(self):
        recorded = {}

        class DummyApp:
            def setConfigDefault(self, key, value, docString="", **kw):
                recorded[key] = (value, docString)

            def setConfigAlias(self, *args):
                pass

            def addConfigEntry(self, *args):
                pass

        cfg = Config(plugins.OptionFinder([]))
        cfg.setComparisonDefaults(DummyApp(), "any", "classic")
        self.assertIn("floating_point_pattern", recorded)
        self.assertEqual(recorded["floating_point_pattern"][0], {"default": []})


if __name__ == "__main__":
    unittest.main()
