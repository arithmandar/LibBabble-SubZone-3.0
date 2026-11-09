#!/usr/bin/env python3
"""Fail a pull request that changes runtime files without bumping MINOR_VERSION.

LibStub picks the copy with the highest MINOR_VERSION, so every change to the
files loaded in game must increase it. Otherwise two different builds with the
same version can be embedded, and whichever loads first wins.

Usage: check_minor_version.py <base-sha> <head-sha>
"""

import os
import re
import subprocess
import sys

CORE_FILE = "Core/Core.lua"
RUNTIME_PREFIXES = ("Core/", "Data/", "Locale/")
RUNTIME_FILES = ("lib.xml",)

# The last release before the move to GitHub derived MINOR_VERSION from the
# SVN $Rev$ keyword (r268, i.e. 100000 + 268).
LEGACY_REV_MINOR = 100268

FIXED_RE = re.compile(r"^local MINOR_VERSION = (\d+)\s*$", re.MULTILINE)
LEGACY_RE = re.compile(r"^local MINOR_VERSION = 100000 \+ tonumber\(\(\"\$Rev\$\"\)", re.MULTILINE)


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def read_minor(rev):
    text = git("show", f"{rev}:{CORE_FILE}")
    match = FIXED_RE.search(text)
    if match:
        return int(match.group(1)), "fixed"
    if LEGACY_RE.search(text):
        return LEGACY_REV_MINOR, "legacy $Rev$"
    return None, "unparseable"


def summary(line=""):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    print(line)


def main():
    base, head = sys.argv[1], sys.argv[2]
    changed = git("diff", "--name-only", f"{base}...{head}").split()
    runtime = [f for f in changed if f.startswith(RUNTIME_PREFIXES) or f in RUNTIME_FILES]

    summary("## MINOR_VERSION check")
    summary()
    if not runtime:
        summary("No runtime files changed. No version bump required.")
        return 0

    base_minor, base_kind = read_minor(base)
    head_minor, head_kind = read_minor(head)
    summary(f"- Runtime files changed: {len(runtime)}")
    summary(f"- Base MINOR_VERSION: {base_minor} ({base_kind})")
    summary(f"- Head MINOR_VERSION: {head_minor} ({head_kind})")
    summary()

    if head_minor is None:
        message = f"Could not read a fixed integer MINOR_VERSION from {CORE_FILE}."
    elif base_minor is not None and head_minor <= base_minor:
        message = (
            f"Runtime files changed but MINOR_VERSION was not increased "
            f"({base_minor} -> {head_minor}). Bump it in {CORE_FILE}."
        )
    else:
        summary(f"**PASSED**: MINOR_VERSION increased to {head_minor}.")
        return 0

    print(f"::error file={CORE_FILE}::{message}")
    summary(f"**FAILED**: {message}")
    summary()
    summary("Changed runtime files:")
    for name in runtime:
        summary(f"- `{name}`")
    return 1


if __name__ == "__main__":
    sys.exit(main())
