"""
Standalone test sandbox extraction API for debugging and external execution.
"""

import os
import shlex
import shutil
from texttestlib import plugins
from . import sandbox
from .runtest import RunTest


class _StandaloneDirectoryPreparer(sandbox.PrepareWriteDirectory):
    def __init__(self, targetDir):
        sandbox.PrepareWriteDirectory.__init__(self, ignoreCatalogues=True)
        self.targetDir = targetDir

    def getTargetPath(self, test, configName):
        localName = os.path.basename(self.getPathFromEnvironment(configName, test))
        if localName:
            return os.path.join(self.targetDir, localName)

    def linkTestPath(self, test, fullPath, target):
        return self.copyTestPath(test, fullPath, target)

    def partialCopyTestPath(self, test, sourcePath, targetPath):
        return self.copyTestPath(test, sourcePath, targetPath)

    def copylink(self, srcname, dstname):
        realSrc = os.path.realpath(srcname)
        if os.path.isdir(realSrc):
            self.copytree(realSrc, dstname)
        elif os.path.exists(realSrc):
            self.copyfile(realSrc, dstname)


def _rewriteSandboxPaths(value, replacements):
    result = value
    for oldPath, newPath in replacements:
        if oldPath:
            result = result.replace(oldPath, newPath)
    return result


def _quoteBatchArg(arg):
    escaped = arg.replace("%", "%%")
    if not escaped:
        return '""'
    if any(ch in escaped for ch in ' \t"&|<>^()'):
        escaped = escaped.replace('"', '\\"')
        return '"' + escaped + '"'
    return escaped


def _writePosixRunner(scriptPath, envVars, cmdArgs, stdinLocalName):
    lines = ["#!/bin/sh", 'cd "$(dirname "$0")" || exit 1']
    for var, value in envVars:
        lines.append(f"export {var}={shlex.quote(value)}")
    cmdLine = " ".join(shlex.quote(arg) for arg in cmdArgs) + ' "$@"'
    if stdinLocalName:
        cmdLine += " < " + shlex.quote(stdinLocalName)
    lines.append("exec " + cmdLine)
    with open(scriptPath, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    try:
        os.chmod(scriptPath, 0o755)
    except OSError:
        pass


def _writeWindowsRunner(scriptPath, envVars, cmdArgs, stdinLocalName):
    lines = ["@echo off", 'cd /d "%~dp0"']
    for var, value in envVars:
        safeVal = value.replace("%", "%%").replace('"', '""')
        lines.append(f'set "{var}={safeVal}"')
    cmdLine = " ".join(_quoteBatchArg(arg) for arg in cmdArgs) + " %*"
    if stdinLocalName:
        cmdLine += " < " + _quoteBatchArg(stdinLocalName)
    lines.append(cmdLine)
    with open(scriptPath, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def extractTest(test, targetDir, platformName=None):
    """
    Materialize ``test``'s input sandbox into ``targetDir`` and generate an
    executable ``run_test.bat`` (Windows) or ``run_test.sh`` (POSIX) script.
    Returns the path to the primary generated run script.
    """
    targetDir = os.path.abspath(targetDir)
    plugins.ensureDirectoryExists(targetDir)
    platformName = platformName or os.name

    test.readEnvironment(test.app.getConfigEnvironment(test))
    preparer = _StandaloneDirectoryPreparer(targetDir)
    preparer.collateAllPaths(test, remoteCopy=None)

    for var, propDict in list(test.properties.items()):
        propFileName = os.path.join(targetDir, var + ".properties")
        with open(propFileName, "w", encoding="utf-8") as propFile:
            for subVar, subValue in list(propDict.items()):
                propFile.write(subVar + " = " + subValue + "\n")

    replacements = []
    for candidate in (
        test.getDirectory(temporary=1, local=1),
        test.getDirectory(temporary=1),
        getattr(test.app, "localWriteDirectory", ""),
        getattr(test.app, "writeDirectory", ""),
    ):
        if candidate and candidate != targetDir:
            replacements.append((candidate, targetDir))

    runner = RunTest()
    namingScheme = test.app.getConfigValue("filename_convention_scheme")
    primaryScript = None

    for postfix in runner.getTestRunPostfixes(test):
        inputStem = test.app.getStdinName(namingScheme) + postfix
        inputFile = test.getFileName(inputStem)
        stdinLocalName = None
        if inputFile and os.path.isfile(inputFile):
            stdinLocalName = os.path.basename(inputFile)
            dstInput = os.path.join(targetDir, stdinLocalName)
            if not os.path.exists(dstInput) or not plugins.samefile(inputFile, dstInput):
                shutil.copy2(inputFile, dstInput)
                plugins.makeWriteable(dstInput)

        rawEnv = runner.getEnvironmentChanges(test, postfix)
        envVars = [(k, _rewriteSandboxPaths(v, replacements)) for k, v in rawEnv]
        rawArgs = runner.getLocalExecuteCmdArgs(test, postfix, makeDirs=False)
        cmdArgs = [_rewriteSandboxPaths(a, replacements) for a in rawArgs]

        ext = ".bat" if platformName == "nt" else ".sh"
        scriptPath = os.path.join(targetDir, "run_test" + postfix + ext)
        if platformName == "nt":
            _writeWindowsRunner(scriptPath, envVars, cmdArgs, stdinLocalName)
        else:
            _writePosixRunner(scriptPath, envVars, cmdArgs, stdinLocalName)
        if primaryScript is None:
            primaryScript = scriptPath

    return primaryScript
