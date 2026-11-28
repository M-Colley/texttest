import io
import os
import tokenize
import unittest

LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "texttestlib")


def linesInsideStrings(source):
    protected = set()
    fstringStarts = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.STRING and tok.start[0] != tok.end[0]:
            protected.update(range(tok.start[0], tok.end[0]))
        elif getattr(tokenize, "FSTRING_START", None) == tok.type:
            fstringStarts.append(tok.start[0])
        elif getattr(tokenize, "FSTRING_END", None) == tok.type and fstringStarts:
            protected.update(range(fstringStarts.pop(), tok.end[0]))
    return protected


def findTrailingWhitespace(source):
    protected = linesInsideStrings(source)
    return [number for number, line in enumerate(source.splitlines(), start=1)
            if number not in protected and line != line.rstrip(" \t")]


class TestIssue29TrailingWhitespace(unittest.TestCase):
    def test_checker_ignores_string_contents(self):
        source = 'x = 1  \ny = """a  \nb"""  \n\tz = 2\t\n'
        self.assertEqual(findTrailingWhitespace(source), [1, 3, 4])

    def test_library_sources_have_no_trailing_whitespace(self):
        offenders = []
        for root, _, files in os.walk(LIB_DIR):
            for fileName in sorted(files):
                if fileName.endswith(".py"):
                    path = os.path.join(root, fileName)
                    with open(path, encoding="utf-8") as f:
                        lines = findTrailingWhitespace(f.read())
                    if lines:
                        offenders.append((os.path.relpath(path, LIB_DIR), lines))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
