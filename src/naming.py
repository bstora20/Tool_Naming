"""
Naming layer: maps each logical primitive (P1-P5) to the name string and
manual/description text that should be shown to the model under a given
naming condition.

This module contains ZERO behavioral logic -- it only defines names and
descriptions. The actual function objects always come from primitives.py
and are identical across every condition. Swapping which "name" points to
which function happens in the interface harnesses (built later), not here;
this module is only the lookup table of names/descriptions per condition.

Naming conditions (per research_plan.md S1.5):

    A-full  : exact Unix names, full manual (same length as B/C)
    A-zero  : exact Unix names, NO manual (bare name only)
    B       : sensible non-Unix names, full manual
    C       : random names, full manual (same length as B)
    D       : exact Unix names (ls/find/grep/cat/wc), full manual, but the
              documented argument order for find (P2) and grep (P3) is
              SWAPPED from the real Unix convention (root<->pattern for
              find, path<->pattern for grep). This is the "near-miss
              grammar" condition: a familiar name paired with a slightly
              wrong (but fully documented) calling convention, added to
              directly test whether familiar-name grammar interference
              costs more than a condition with no prior grammar at all
              (research_plan.md ad-hoc extension, see experiments.txt
              Experiment C for the methodology this generalizes).
    D2      : exact Unix names, full manual, with TWO combined rule changes
              on find (P2) and grep (P3) rather than D's single change:
              (1) the same argument-order swap as D, PLUS (2) a mandatory
              literal delimiter-wrapping convention for the pattern
              argument (must be written as "<pattern>", not "pattern").
              This "doses" a second simultaneous rule change on top of D's
              single order-swap, mirroring experiments.txt Experiment C's
              dose levels (0/1/2/4/all rules changed at once), to test
              whether a single swapped rule's null effect (see Condition D)
              changes once a second, genuinely-breaking-if-violated rule is
              layered on top of it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PrimitiveSpec:
    logical_id: str          # stable key, e.g. "P1" -- never shown to the model
    name: str                # the name string shown to the model under this condition
    signature: str           # e.g. "list_entries(path: str) -> list[str]"
    manual: str               # full description text (empty string for A-zero)


# ---- canonical logical primitive metadata (condition-independent) --------

_SIGNATURES = {
    "P1": "(path: str) -> list[str]",
    "P2": "(root: str, pattern: str) -> list[str]",
    "P3": "(pattern: str, path: str) -> list[str]",
    "P4": "(path: str) -> str",
    "P5": "(path: str, pattern: str = None) -> int",
}

# Full manuals are written to be near-identical in length/informativeness
# across B and C (and reused verbatim for A-full), differing only in which
# name/example-name-usage is substituted. This is the "description-length
# control" required by S1.5.

_MANUAL_TEMPLATES = {
    "P1": (
        "{name}{sig}\n"
        "List the direct entries (files or subdirectories) at the given path.\n"
        "  {name}(\"/\") -> [\"packages\", \"projects\"]\n"
        "  {name}(\"/projects\") -> list of all project names\n"
        "  {name}(\"/projects/project-000\") -> [\"deps.txt\"]\n"
        "Raises an error if the path does not exist or is a file."
    ),
    "P2": (
        "{name}{sig}\n"
        "Recursively list all file paths under root whose path matches the\n"
        "given glob pattern (supports * and ? wildcards).\n"
        "  {name}(\"/\", \"*/meta.json\") -> every package's meta.json path\n"
        "  {name}(\"/projects\", \"*/deps.txt\") -> every project's deps.txt path\n"
        "Raises an error if root does not exist."
    ),
    "P3": (
        "{name}{sig}\n"
        "Search file contents for lines matching a regular expression pattern.\n"
        "Path may be a single file or a directory (searched recursively).\n"
        "Returns a list of \"path:matching_line\" strings.\n"
        "  {name}(\"MIT\", \"/packages\") -> lines mentioning MIT across all packages\n"
        "Raises an error if path does not exist or pattern is invalid."
    ),
    "P4": (
        "{name}{sig}\n"
        "Return the full text content of the file at the given path.\n"
        "  {name}(\"/packages/pkg-113/meta.json\") -> the JSON text of that file\n"
        "Raises an error if path does not exist or is a directory."
    ),
    "P5": (
        "{name}{sig}\n"
        "Count matching lines. If pattern is omitted, counts non-empty lines\n"
        "in the file at path. If pattern is given, path may be a file or\n"
        "directory, and this counts matching lines across all files found.\n"
        "  {name}(\"/packages/pkg-116/dependents.txt\") -> count of dependents\n"
        "  {name}(\"/packages\", \"MIT\") -> count of MIT-related matching lines\n"
        "Raises an error if path does not exist or pattern is invalid."
    ),
}

# ---- Condition D overrides: "near-miss grammar" ---------------------------
#
# D reuses the exact A (real-Unix) names, but documents a SWAPPED argument
# order for P2 (find-like) and P3 (grep-like) relative to both the real Unix
# convention and this project's own A/B/C convention (which happens to match
# real find/grep ordering already: find ROOT then PATTERN; grep PATTERN then
# FILE). P1/P4/P5 are left untouched since there is no real near-Unix
# ambiguity to exploit for single-argument commands.
#
# This directly operationalizes experiments.txt Experiment C ("a familiar
# command's rules are changed and documented -- does the familiar name make
# the model worse than an unfamiliar name taught the same rules?") inside
# this project's own harness, so it can be compared apples-to-apples against
# the existing A-full/B/C shell cells already in results/full_run_n3_rescored.jsonl.

_SIGNATURES_D_OVERRIDES = {
    "P2": "(pattern: str, root: str) -> list[str]",
    "P3": "(path: str, pattern: str) -> list[str]",
}

_MANUAL_TEMPLATES_D_OVERRIDES = {
    "P2": (
        "{name}{sig}\n"
        "Recursively list all file paths under root whose path matches the\n"
        "given glob pattern (supports * and ? wildcards).\n"
        "In this environment {name} takes the PATTERN first and the ROOT\n"
        "path second -- i.e. {name}(pattern, root), NOT {name}(root, pattern).\n"
        "  {name}(\"*/meta.json\", \"/\") -> every package's meta.json path\n"
        "  {name}(\"*/deps.txt\", \"/projects\") -> every project's deps.txt path\n"
        "Raises an error if root does not exist."
    ),
    "P3": (
        "{name}{sig}\n"
        "Search file contents for lines matching a regular expression pattern.\n"
        "Path may be a single file or a directory (searched recursively).\n"
        "Returns a list of \"path:matching_line\" strings.\n"
        "In this environment {name} takes the PATH first and the PATTERN\n"
        "second -- i.e. {name}(path, pattern), NOT {name}(pattern, path).\n"
        "  {name}(\"/packages\", \"MIT\") -> lines mentioning MIT across all packages\n"
        "Raises an error if path does not exist or pattern is invalid."
    ),
}

# ---- Condition D2 overrides: "dosed near-miss grammar" (D + 2nd rule) ----
#
# D2 reuses D's argument-order swap verbatim, PLUS a second, independent,
# mandatory rule: the pattern argument must be written wrapped in angle
# brackets, e.g. <MIT> instead of MIT. Unlike the order swap (which merely
# produces a wrong *value* when violated), omitting the brackets is treated
# as a hard dispatch-level error by the Dispatcher (see dispatch.py's
# _unwrap_pattern), so this rule is "genuinely breaking" the way some of
# Experiment C's flag-rename/quoting-rule changes were -- giving D2 a
# second, independently-enforceable rule to combine with D's order swap,
# mirroring Experiment C's multi-rule "dose" methodology (dose=2 here).

_MANUAL_TEMPLATES_D2_OVERRIDES = {
    "P2": (
        "{name}{sig}\n"
        "Recursively list all file paths under root whose path matches the\n"
        "given glob pattern (supports * and ? wildcards).\n"
        "In this environment {name} takes the PATTERN first and the ROOT\n"
        "path second -- i.e. {name}(pattern, root), NOT {name}(root, pattern).\n"
        "The pattern must be written wrapped in angle brackets, e.g. <*/meta.json>,\n"
        "NOT a bare */meta.json -- this is a hard requirement, not cosmetic.\n"
        "  {name}(\"<*/meta.json>\", \"/\") -> every package's meta.json path\n"
        "  {name}(\"<*/deps.txt>\", \"/projects\") -> every project's deps.txt path\n"
        "Raises an error if root does not exist, or if pattern is not wrapped\n"
        "in angle brackets."
    ),
    "P3": (
        "{name}{sig}\n"
        "Search file contents for lines matching a regular expression pattern.\n"
        "Path may be a single file or a directory (searched recursively).\n"
        "Returns a list of \"path:matching_line\" strings.\n"
        "In this environment {name} takes the PATH first and the PATTERN\n"
        "second -- i.e. {name}(path, pattern), NOT {name}(pattern, path).\n"
        "The pattern must be written wrapped in angle brackets, e.g. <MIT>,\n"
        "NOT a bare MIT -- this is a hard requirement, not cosmetic.\n"
        "  {name}(\"/packages\", \"<MIT>\") -> lines mentioning MIT across all packages\n"
        "Raises an error if path does not exist, pattern is invalid, or pattern\n"
        "is not wrapped in angle brackets."
    ),
}

# ---- per-condition name tables --------------------------------------------

_NAMES_A: Dict[str, str] = {  # exact Unix names (used by both A-full and A-zero)
    "P1": "ls",
    "P2": "find",
    "P3": "grep",
    "P4": "cat",
    "P5": "wc",
}

_NAMES_B: Dict[str, str] = {  # sensible non-Unix names
    "P1": "list_entries",
    "P2": "search_by_name",
    "P3": "search_content",
    "P4": "read_file",
    "P5": "count_items",
}

LOGICAL_IDS: List[str] = ["P1", "P2", "P3", "P4", "P5"]

_NAME_RNG_SEED = 20260929  # fixed seed: random-name generation is deterministic


def _generate_random_names(reference: Dict[str, str]) -> Dict[str, str]:
    """
    Generate pronounceable-but-meaningless names, each EXACTLY the same
    character length as the corresponding name in `reference` (the B/sensible
    condition). This guarantees the naming-condition manuals differ only in
    which token is substituted, never in raw character count -- required by
    the description-length control in research_plan.md S1.5.

    Names are built by alternating consonant/vowel so they are pronounceable
    (avoids confounding "random" with "unpronounceable"/"un-tokenizable"),
    while carrying no semantic content related to the underlying primitive.
    """
    consonants = "bcdfgklmnprstvz"
    vowels = "aeiou"
    rng = random.Random(_NAME_RNG_SEED)

    used: set = set()
    result: Dict[str, str] = {}
    for pid in LOGICAL_IDS:
        target_len = len(reference[pid])
        while True:
            chars = []
            for i in range(target_len):
                pool = consonants if i % 2 == 0 else vowels
                chars.append(rng.choice(pool))
            candidate = "".join(chars)
            if candidate not in used and candidate not in reference.values():
                used.add(candidate)
                result[pid] = candidate
                break
    return result


_NAMES_C: Dict[str, str] = _generate_random_names(_NAMES_B)

NAMES: Dict[str, Dict[str, str]] = {
    "A": _NAMES_A,
    "B": _NAMES_B,
    "C": _NAMES_C,
}


def build_specs(condition: str) -> Dict[str, PrimitiveSpec]:
    """
    Build the {logical_id: PrimitiveSpec} table for a given naming condition.

    condition: one of "A-full", "A-zero", "B", "C", "D", "D2"
    """
    if condition not in ("A-full", "A-zero", "B", "C", "D", "D2"):
        raise ValueError(f"unknown naming condition: {condition!r}")

    name_key = "A" if condition.startswith("A") or condition in ("D", "D2") else condition
    names = NAMES[name_key]

    specs: Dict[str, PrimitiveSpec] = {}
    for pid in LOGICAL_IDS:
        name = names[pid]
        if condition in ("D", "D2") and pid in _SIGNATURES_D_OVERRIDES:
            sig = _SIGNATURES_D_OVERRIDES[pid]
        else:
            sig = _SIGNATURES[pid]
        if condition == "A-zero":
            manual = ""  # bare name only -- no description at all
        elif condition == "D2" and pid in _MANUAL_TEMPLATES_D2_OVERRIDES:
            manual = _MANUAL_TEMPLATES_D2_OVERRIDES[pid].format(name=name, sig=sig)
        elif condition == "D" and pid in _MANUAL_TEMPLATES_D_OVERRIDES:
            manual = _MANUAL_TEMPLATES_D_OVERRIDES[pid].format(name=name, sig=sig)
        else:
            manual = _MANUAL_TEMPLATES[pid].format(name=name, sig=sig)
        specs[pid] = PrimitiveSpec(
            logical_id=pid, name=name, signature=sig, manual=manual
        )
    return specs


def render_full_manual(condition: str) -> str:
    """
    Render the complete interface description block shown to the model for
    a given naming condition -- e.g. what goes into the system prompt before
    the task. For A-zero this is just the bare name list (per the
    prior-knowledge-skips-description-cost hypothesis in the plan, S1.5).
    """
    specs = build_specs(condition)
    if condition == "A-zero":
        names = ", ".join(specs[pid].name for pid in LOGICAL_IDS)
        return f"Available commands: {names}"
    blocks = [specs[pid].manual for pid in LOGICAL_IDS]
    return "\n\n".join(blocks)


def name_to_logical_id(condition: str) -> Dict[str, str]:
    """Inverse lookup: {active_name_string: logical_id} for a condition.
    Used by interface harnesses to dispatch an incoming call by name back to
    the correct primitive implementation."""
    name_key = "A" if condition.startswith("A") or condition in ("D", "D2") else condition
    return {name: pid for pid, name in NAMES[name_key].items()}
