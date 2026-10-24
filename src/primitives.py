"""
The five shared capability primitives (P1-P5), as plain Python functions.

Each primitive has FIXED semantics that are shared, byte-for-byte, across
every experimental cell. Only the *name* under which a primitive is exposed
to the model changes across naming conditions (see naming.py) -- the
implementation below is called identically no matter what name condition is
active.

Each primitive is deliberately given semantics that map naturally onto a
real Unix tool, so that the "exact Unix name" condition is not a forced or
misleading pairing:

    P1  list_entries(path)                     ~ ls
    P2  find_by_pattern(root, pattern)          ~ find
    P3  search_content(pattern, path)           ~ grep
    P4  read_record(path)                       ~ cat
    P5  count_matches(pattern, path)            ~ wc (wc -l after a filter)

All primitives operate over the VirtualFS abstraction (vfs.py), which itself
reads from the canonical Graph (data_gen.py). This is the single shared
capability layer referenced in the research plan (Study 1, S1.4).
"""

from __future__ import annotations

import fnmatch
import json
import re
from typing import List

from vfs import VirtualFS, VfsError


class PrimitiveError(Exception):
    """Raised when a primitive is called with invalid arguments or on an
    invalid path. Deliberately a single generic error type at this layer --
    interface-specific wrappers (shell exit codes, function-call error
    payloads, etc.) are added by each interface harness, not here."""


# ---- P1: list_entries (~ ls) ----------------------------------------------


def list_entries(vfs: VirtualFS, path: str = "/") -> List[str]:
    """
    List the direct entries at `path`.

      list_entries("/")                  -> ["packages", "projects"]
      list_entries("/projects")          -> [<all project names>]
      list_entries("/projects/proj-X")   -> ["deps.txt"]
      list_entries("/packages/pkg-Y")    -> ["deps.txt", "dependents.txt", "meta.json"]

    Raises PrimitiveError if `path` does not exist or is a file (use
    read_record for files).
    """
    try:
        if vfs.is_file(path):
            raise PrimitiveError(f"'{path}' is a file, not a directory")
        return vfs.list_dir(path)
    except VfsError as e:
        raise PrimitiveError(str(e)) from e


# ---- P2: find_by_pattern (~ find) -----------------------------------------


def find_by_pattern(vfs: VirtualFS, root: str, pattern: str) -> List[str]:
    """
    Recursively list all file paths under `root` whose path matches a glob
    `pattern` (fnmatch-style: `*`, `?`, `[seq]`).

      find_by_pattern("/", "*/meta.json")
          -> every package's meta.json path
      find_by_pattern("/projects", "*/deps.txt")
          -> every project's deps.txt path
      find_by_pattern("/packages/pkg-042", "*")
          -> all three files under pkg-042

    Raises PrimitiveError if `root` does not exist.
    """
    try:
        all_files = vfs.walk_files(root)
    except VfsError as e:
        raise PrimitiveError(str(e)) from e
    return [f for f in all_files if fnmatch.fnmatch(f, pattern)]


# ---- P3: search_content (~ grep) ------------------------------------------


def search_content(vfs: VirtualFS, pattern: str, path: str) -> List[str]:
    """
    Search file contents for lines matching `pattern` (a Python regex).
    `path` may be a single file or a directory (in which case all files
    under it are searched recursively).

    Returns a list of "path:line" strings for every matching line, mirroring
    `grep -r` output when a directory is given.

      search_content("license.: .MIT.", "/packages")
          -> one "path:line" per MIT-licensed package's meta.json
      search_content("pkg-113", "/projects/project-000/deps.txt")
          -> matching lines from that one file, if any

    Raises PrimitiveError if `path` does not exist or `pattern` is invalid.
    """
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise PrimitiveError(f"invalid pattern: {e}") from e

    try:
        if vfs.is_file(path):
            files = [path]
        else:
            files = vfs.walk_files(path)
    except VfsError as e:
        raise PrimitiveError(str(e)) from e

    results: List[str] = []
    for f in files:
        try:
            content = vfs.read_file(f)
        except VfsError as e:
            raise PrimitiveError(str(e)) from e
        for line in content.split("\n"):
            if line == "":
                continue
            if regex.search(line):
                results.append(f"{f}:{line}")
    return results


# ---- P4: read_record (~ cat) -----------------------------------------------


def read_record(vfs: VirtualFS, path: str) -> str:
    """
    Return the full text content of the file at `path`.

      read_record("/packages/pkg-113/meta.json")  -> the JSON text
      read_record("/projects/project-000/deps.txt") -> the deps listing

    Raises PrimitiveError if `path` does not exist or is a directory.
    """
    try:
        return vfs.read_file(path)
    except VfsError as e:
        raise PrimitiveError(str(e)) from e


# ---- P5: count_matches (~ wc) ----------------------------------------------


def count_matches(vfs: VirtualFS, path: str, pattern: str = None) -> int:
    """
    Count matching lines/entries.

    If `pattern` is None: counts non-empty lines in the file at `path`
    (mirrors `wc -l file`).

    If `pattern` is given: `path` may be a file or directory; counts lines
    across all matched files that match the regex `pattern` (mirrors
    `grep -r pattern path | wc -l`).

      count_matches("/packages/pkg-116/dependents.txt")
          -> number of projects depending on pkg-116
      count_matches("/packages", pattern='"license": "MIT"')
          -> number of MIT-licensed packages

    Raises PrimitiveError if `path` does not exist or `pattern` is invalid.
    """
    if pattern is None:
        try:
            return len(vfs.read_lines(path))
        except VfsError as e:
            raise PrimitiveError(str(e)) from e
    return len(search_content(vfs, pattern, path))


# ---- P6: jq_filter (~ jq) ---------------------------------------------------
#
# This primitive is deliberately modeled on `jq`'s single most distinctive,
# strongly idiomatic calling convention: a dot-path FILTER expression
# written FIRST, followed by the input (file/path) SECOND -- e.g.
# `jq '.license' file.json`. Real `jq` users have an unusually strong,
# near-universal prior for "filter comes before file" (this is the
# "sticky idiom" referenced in experiments.txt Experiment C's finding that
# its real-vs-random-name effect was almost entirely attributable to jq
# specifically). P6 exists so this project's own harness can test the same
# "near-miss grammar on a genuinely sticky idiom" question that D/D2 tested
# on find/grep's much weaker argument-order convention.

_JQ_SUPPORTED_FIELDS = {".license", ".owner", ".last_updated", ".deprecated"}


def jq_filter(vfs: VirtualFS, filter_expr: str, path: str) -> List[str]:
    """
    Extract one top-level JSON field from meta.json file(s), jq-style.

    `filter_expr` must be one of ".license", ".owner", ".last_updated",
    ".deprecated" (a restricted dot-path filter over this project's fixed
    meta.json schema). `path` may be a single meta.json file or a directory
    (searched recursively for every meta.json underneath it).

    Returns a list of "path:value" strings, one per meta.json file found
    (mirrors search_content's "path:line" output format).

      jq_filter(".license", "/packages/pkg-113/meta.json")
          -> ["/packages/pkg-113/meta.json:MIT"]
      jq_filter(".license", "/packages")
          -> one "path:license" entry per package

    Raises PrimitiveError if `filter_expr` is not a supported field, if
    `path` does not exist, or if no meta.json file is found under `path`.
    """
    if filter_expr not in _JQ_SUPPORTED_FIELDS:
        raise PrimitiveError(
            f"unsupported filter {filter_expr!r}; must be one of {sorted(_JQ_SUPPORTED_FIELDS)}"
        )
    field = filter_expr[1:]  # strip leading "."

    try:
        all_files = vfs.walk_files(path)
    except VfsError as e:
        raise PrimitiveError(str(e)) from e

    meta_files = [f for f in all_files if f.endswith("/meta.json")]
    if not meta_files:
        raise PrimitiveError(f"no meta.json file found under {path!r}")

    results: List[str] = []
    for f in meta_files:
        try:
            content = vfs.read_file(f)
        except VfsError as e:
            raise PrimitiveError(str(e)) from e
        obj = json.loads(content)
        results.append(f"{f}:{obj.get(field)}")
    return results


# ---- P7: sed_filter (~ sed) --------------------------------------------------
#
# This primitive mirrors P6's design, but models `sed`'s calling convention
# instead of jq's: a SCRIPT/expression written FIRST, followed by the input
# FILE SECOND -- e.g. `sed 's/foo/bar/' file.txt`. Real `sed` users have an
# equally strong, near-universal prior for "script comes before file" (just
# as strong as jq's "filter comes before file," but a structurally distinct
# idiom -- substitution-script syntax rather than a dot-path query). P7
# exists so the sticky-idiom experiment (previously tested only on jq) can
# be replicated on a second, independent strong idiom, to check whether the
# named-suppresses / ordered_generic-backfires pattern found for jq
# generalizes or is jq-specific.
#
# Toy semantics deliberately reuse jq_filter's domain (meta.json top-level
# fields) so the exact same 8 tasks/oracles can be reused unmodified: the
# "script" here is a restricted sed-style extraction expression of the form
# "s/FIELD//p" (print-the-field-value pattern, loosely evoking real sed's
# `s/pattern/replacement/p` substitute-and-print idiom) rather than a
# genuinely free-form regex substitution.

_SED_SUPPORTED_FIELDS = {
    "s/license//p": "license",
    "s/owner//p": "owner",
    "s/last_updated//p": "last_updated",
    "s/deprecated//p": "deprecated",
}


def sed_filter(vfs: VirtualFS, script: str, path: str) -> List[str]:
    """
    Extract one top-level JSON field from meta.json file(s), sed-style.

    `script` must be one of "s/license//p", "s/owner//p",
    "s/last_updated//p", "s/deprecated//p" (a restricted substitute-and-
    print expression over this project's fixed meta.json schema). `path`
    may be a single meta.json file or a directory (searched recursively for
    every meta.json underneath it).

    Returns a list of "path:value" strings, one per meta.json file found
    (mirrors jq_filter's "path:value" output format).

      sed_filter("s/license//p", "/packages/pkg-113/meta.json")
          -> ["/packages/pkg-113/meta.json:MIT"]
      sed_filter("s/license//p", "/packages")
          -> one "path:license" entry per package

    Raises PrimitiveError if `script` is not a supported expression, if
    `path` does not exist, or if no meta.json file is found under `path`.
    """
    if script not in _SED_SUPPORTED_FIELDS:
        raise PrimitiveError(
            f"unsupported script {script!r}; must be one of {sorted(_SED_SUPPORTED_FIELDS)}"
        )
    field = _SED_SUPPORTED_FIELDS[script]

    try:
        all_files = vfs.walk_files(path)
    except VfsError as e:
        raise PrimitiveError(str(e)) from e

    meta_files = [f for f in all_files if f.endswith("/meta.json")]
    if not meta_files:
        raise PrimitiveError(f"no meta.json file found under {path!r}")

    results: List[str] = []
    for f in meta_files:
        try:
            content = vfs.read_file(f)
        except VfsError as e:
            raise PrimitiveError(str(e)) from e
        obj = json.loads(content)
        results.append(f"{f}:{obj.get(field)}")
    return results
