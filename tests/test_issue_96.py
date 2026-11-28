import os
import struct
import tempfile
import unittest
import zlib
from unittest import mock

from texttestlib.default import comparefile, imagecompare


def _write_png(path, width, height, rgb_rows, text_comment=b""):
    def chunk(ctype, cdata):
        crc = zlib.crc32(ctype + cdata) & 0xFFFFFFFF
        return struct.pack(">I", len(cdata)) + ctype + cdata + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    for row in rgb_rows:
        raw.append(0)  # filter None
        for r, g, b in row:
            raw.extend((r, g, b))
    chunks = [b"\x89PNG\r\n\x1a\n", chunk(b"IHDR", ihdr)]
    if text_comment:
        chunks.append(chunk(b"tEXt", b"Comment\x00" + text_comment))
    chunks.append(chunk(b"IDAT", zlib.compress(bytes(raw))))
    chunks.append(chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(b"".join(chunks))


def _make_mock_test(tmp_dir, float_tol=0.0, rel_tol=0.0):
    test = mock.MagicMock()
    test.app.name = "imgapp"
    test.configValueMatches.return_value = False
    test.makeTmpFileName.side_effect = lambda name, **kw: os.path.join(tmp_dir, "fw", name)

    def get_cfg(key):
        return {
            "lines_of_text_difference": 30,
            "max_width_text_difference": 500,
            "text_diff_program": "diff",
        }[key]

    def get_comp_cfg(key, sub):
        return {
            "failure_severity": 1,
            "failure_display_priority": 99,
            "file_encoding": "locale",
            "max_file_size": "-1",
            "floating_point_tolerance": float_tol,
            "relative_float_tolerance": rel_tol,
        }[key]

    test.getConfigValue.side_effect = get_cfg
    test.getCompositeConfigValue.side_effect = get_comp_cfg
    return test


class TestIssue96(unittest.TestCase):
    def test_identical_pixels_with_different_png_metadata_compare_equal(self):
        with tempfile.TemporaryDirectory() as tmp:
            std_png = os.path.join(tmp, "screenshot.imgapp")
            tmp_png = os.path.join(tmp, "tmp_screenshot.imgapp")
            rows = [[(10, 20, 30), (40, 50, 60)], [(70, 80, 90), (100, 110, 120)]]
            _write_png(std_png, 2, 2, rows, text_comment=b"baseline-2025")
            _write_png(tmp_png, 2, 2, rows, text_comment=b"run-2026")

            self.assertNotEqual(open(std_png, "rb").read(), open(tmp_png, "rb").read())
            self.assertTrue(imagecompare.isImageFile(std_png))

            test = _make_mock_test(tmp)
            comp = comparefile.FileComparison(test, "screenshot", std_png, tmp_png)
            self.assertFalse(comp.hasDifferences())
            self.assertTrue(comp.hasSucceeded())

    def test_pixel_differences_report_metrics_and_respect_tolerance(self):
        with tempfile.TemporaryDirectory() as tmp:
            std_png = os.path.join(tmp, "screenshot.imgapp")
            tmp_png = os.path.join(tmp, "tmp_screenshot.imgapp")
            rows_std = [[(10, 20, 30), (40, 50, 60)], [(70, 80, 90), (100, 110, 120)]]
            rows_tmp = [[(10, 20, 30), (40, 55, 60)], [(70, 80, 90), (100, 110, 120)]]
            _write_png(std_png, 2, 2, rows_std)
            _write_png(tmp_png, 2, 2, rows_tmp)

            # Strict comparison reports 1/4 differing pixel and max delta 5.00
            strict_test = _make_mock_test(tmp, float_tol=0.0)
            strict_comp = comparefile.FileComparison(strict_test, "screenshot", std_png, tmp_png)
            self.assertTrue(strict_comp.hasDifferences())
            body = strict_comp.getFreeTextBody()
            self.assertIn("Images differ (2x2 pixels):", body)
            self.assertIn("Differing pixels : 1 / 4 (25.00%)", body)
            self.assertIn("Max channel diff : 5.00", body)

            # Tolerance >= 5.0 accepts minor rendering variation
            tol_test = _make_mock_test(tmp, float_tol=5.0)
            tol_comp = comparefile.FileComparison(tol_test, "screenshot", std_png, tmp_png)
            self.assertFalse(tol_comp.hasDifferences())

    def test_dimension_mismatch_and_new_image_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            std_png = os.path.join(tmp, "plot.imgapp")
            tmp_png = os.path.join(tmp, "tmp_plot.imgapp")
            _write_png(std_png, 2, 2, [[(0, 0, 0), (0, 0, 0)], [(0, 0, 0), (0, 0, 0)]])
            _write_png(tmp_png, 3, 1, [[(0, 0, 0), (0, 0, 0), (0, 0, 0)]])

            test = _make_mock_test(tmp)
            comp = comparefile.FileComparison(test, "plot", std_png, tmp_png)
            self.assertTrue(comp.hasDifferences())
            self.assertIn("Image dimensions differ: 2x2 vs 3x1 pixels.", comp.getFreeTextBody())

            new_comp = comparefile.FileComparison(test, "plot", None, tmp_png)
            self.assertTrue(new_comp.newResult())
            self.assertIn("New image file (3x1 pixels,", new_comp.getFreeTextBody())


if __name__ == "__main__":
    unittest.main()
