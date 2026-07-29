#!/usr/bin/env python3

# Determine whether the Tailwind build must run based on staged files.
# Reads null-separated paths from stdin, compares against @source globs in theme/static_src/src/styles.css

import os
import pathlib
import re
import sys


def expand_optional_dirs(pattern):
    """
    Python's Path.match() treats '**/' strictly — it requires at least one directory to match.
    But in globbing systems like Tailwind or bash, '**/' can also mean 'zero directories'.
    This function expands all combinations where each '**/' is either kept or removed,
    so that Path.match() can simulate this more flexible behavior.

    For example:
    'theme/**/templates/**/*.html' →
    [
        'theme/**/templates/**/*.html',
        'theme/templates/**/*.html',
        'theme/**/templates/*.html',
        'theme/templates/*.html',
    ]

    Use this to match paths more like Tailwind does, where '**' can mean "nothing here".
    """
    parts = pattern.split("**/")
    if len(parts) == 1:
        return [pattern]  # no '**/' present

    results = []

    # There are N-1 '**/' positions
    num_stars = len(parts) - 1

    # For each combination of keeping or removing the '**/' parts
    for bits in range(2 ** num_stars):
        new_pattern = parts[0]
        for i in range(num_stars):
            if (bits >> i) & 1:
                new_pattern += "**/"
            new_pattern += parts[i + 1]
        results.append(new_pattern)

    return results


def path_matches_glob(path, glob_pattern):
    """ Check if the given path matches any variant of the glob pattern (including '**'-as-nothing)."""
    for variant in expand_optional_dirs(glob_pattern):
        if pathlib.Path(path).match(variant):
            return True
    return False


def files_from_stdin():
    # Read from stdin as a single binary stream
    raw = sys.stdin.buffer.read()
    files = raw.decode("utf-8").split("\0")
    files = [f for f in files if f]  # Remove empty final item
    return files


def parse_tailwind_config():
    # Extract all '@source "...";' string literals from styles.css.
    css_path = pathlib.Path("theme/static_src/src/styles.css")
    text = css_path.read_text()
    return re.findall(r'@source\s+(["\'])(.*?)\1\s*;', text)


def globs_from_string_literals(string_literals):
    """Globs: resolve paths relative to the repo root instead of styles.css."""

    return [
        os.path.normpath(os.path.join("theme/static_src/src", string_literal))
        for _, string_literal in string_literals
    ]


def any_file_matches_globs(files, globs):
    for f in files:
        for g in globs:
            if path_matches_glob(f, g):
                return True
    return False


if __name__ == "__main__":
    files = files_from_stdin()
    if not files:
        print("no")
        sys.exit(0)

    if any(f.startswith("theme/static_src/") for f in files):
        print("yes")
        sys.exit(0)

    string_literals = parse_tailwind_config()
    globs = globs_from_string_literals(string_literals)

    if any_file_matches_globs(files, globs):
        print("yes")
        sys.exit(0)

    print("no")
