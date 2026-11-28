import difflib
import re
from texttestlib import plugins
from texttestlib.default import fpdiff


def _compilePatterns(patterns):
    if isinstance(patterns, str):
        patterns = [patterns]
    linePatterns = []
    groupPatterns = []
    for pattern in patterns or ():
        if not pattern:
            continue
        if isinstance(pattern, re.Pattern):
            compiled = pattern
        else:
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise plugins.TextTestError(
                    "Invalid regular expression in floating_point_pattern: '"
                    + str(pattern) + "' (" + str(exc) + ")"
                )
        if compiled.groups > 0:
            groupPatterns.append(compiled)
        else:
            linePatterns.append(compiled)
    return linePatterns, groupPatterns


def _cmpSegment(seg1, seg2, tolerance, relTolerance, split):
    if seg1 == seg2:
        return True
    if split != '':
        fromSplit = seg1.split(split)
        toSplit = seg2.split(split)
        if len(fromSplit) != len(toSplit):
            return False
        for f, t in zip(fromSplit, toSplit):
            f, t = f.strip(), t.strip()
            if f != t and not fpdiff._fpequal(f, t, tolerance, relTolerance):
                return False
        return True
    return fpdiff._fpequal(seg1, seg2, tolerance, relTolerance)


def _extractGroupSpans(line, groupPatterns):
    spans = []
    for regex in groupPatterns:
        for match in regex.finditer(line):
            for idx in range(1, regex.groups + 1):
                span = match.span(idx)
                if span != (-1, -1):
                    spans.append(span)
    if not spans:
        return []
    spans.sort(key=lambda item: (item[0], -item[1]))
    merged = [spans[0]]
    for start, end in spans[1:]:
        prevStart, prevEnd = merged[-1]
        if start <= prevEnd:
            if end > prevEnd:
                merged[-1] = (prevStart, end)
        else:
            merged.append((start, end))
    return merged


def _linesEqualWithGroupPatterns(fromline, toline, tolerance, relTolerance, split, groupPatterns):
    fromSpans = _extractGroupSpans(fromline, groupPatterns)
    if not fromSpans:
        return False
    toSpans = _extractGroupSpans(toline, groupPatterns)
    if len(fromSpans) != len(toSpans):
        return False

    fromPos = 0
    toPos = 0
    for (fromStart, fromEnd), (toStart, toEnd) in zip(fromSpans, toSpans):
        if fromline[fromPos:fromStart] != toline[toPos:toStart]:
            return False
        if not _cmpSegment(fromline[fromStart:fromEnd], toline[toStart:toEnd], tolerance, relTolerance, split):
            return False
        fromPos = fromEnd
        toPos = toEnd
    return fromline[fromPos:] == toline[toPos:]


def _linesEqualWithPatterns(fromline, toline, tolerance, relTolerance, split, linePatterns, groupPatterns):
    if fromline == toline:
        return True
    for regex in linePatterns:
        if regex.search(fromline) and regex.search(toline):
            if _cmpSegment(fromline, toline, tolerance, relTolerance, split):
                return True
    if groupPatterns:
        return _linesEqualWithGroupPatterns(fromline, toline, tolerance, relTolerance, split, groupPatterns)
    return False


def _cmpLinesWithPatterns(fromlines, tolines, outlines, tolerance, relTolerance, split, linePatterns, groupPatterns, checkAbort=None):
    for fromline, toline in zip(fromlines, tolines):
        if checkAbort is not None:
            checkAbort()
        if _linesEqualWithPatterns(fromline, toline, tolerance, relTolerance, split, linePatterns, groupPatterns):
            outlines.write(fromline)
        else:
            outlines.write(toline)


def fpfilterWithPatterns(fromlines, tolines, outlines, tolerance, relTolerance=None, useDifflib=False, split='', patterns=(), checkAbort=None):
    linePatterns, groupPatterns = _compilePatterns(patterns)
    if not linePatterns and not groupPatterns:
        fpdiff.fpfilter(fromlines, tolines, outlines, tolerance, relTolerance, useDifflib=useDifflib, split=split)
        return
    if split == 'None':
        split = None
    if not useDifflib:
        _cmpLinesWithPatterns(fromlines, tolines, outlines, tolerance, relTolerance, split, linePatterns, groupPatterns, checkAbort=checkAbort)
        outlines.writelines(tolines[len(fromlines):])
        return
    s = difflib.SequenceMatcher(None, fromlines, tolines)
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if checkAbort is not None:
            checkAbort()
        if tag == "replace" and i2 - i1 == j2 - j1:
            _cmpLinesWithPatterns(fromlines[i1:i2], tolines[j1:j2], outlines, tolerance, relTolerance, split, linePatterns, groupPatterns, checkAbort=checkAbort)
        else:
            outlines.writelines(tolines[j1:j2])


class PatternFloatingPointFilter:
    postfix = "fpdiff"

    def __init__(self, origFileName, tolerance, relative, split, patterns, encoding="locale"):
        self.origFileName = origFileName
        self.encoding = encoding
        self.tolerance = tolerance if tolerance else None
        self.relative = relative if relative else None
        self.split = split
        self.patterns = patterns

    def filterFile(self, inFile, writeFile, checkAbort=None):
        with plugins.FileEncoding.forFile(self.origFileName, self.encoding).open(self.origFileName) as f:
            fromlines = f.readlines()
        tolines = inFile.readlines()
        fpfilterWithPatterns(
            fromlines,
            tolines,
            writeFile,
            self.tolerance,
            self.relative,
            split=self.split,
            patterns=self.patterns,
            checkAbort=checkAbort,
        )
