"""
Validate the five primitives against known values from graph_seed42.json,
and validate the naming layer produces consistent, well-formed output.

Run with: python3 tests/test_primitives.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_gen import Graph  # noqa: E402
from vfs import VirtualFS, VfsError  # noqa: E402
from primitives import (  # noqa: E402
    list_entries,
    find_by_pattern,
    search_content,
    read_record,
    count_matches,
    PrimitiveError,
)
from naming import build_specs, render_full_manual, name_to_logical_id, LOGICAL_IDS  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "graph_seed42.json"


def load_vfs() -> VirtualFS:
    with open(DATA_PATH) as f:
        d = json.load(f)
    return VirtualFS(Graph.from_dict(d))


# ---- VFS + P1 (list_entries / ls) -----------------------------------------


def test_list_root():
    vfs = load_vfs()
    assert list_entries(vfs, "/") == ["packages", "projects"]
    print("PASS: list_entries('/') == ['packages', 'projects']")


def test_list_projects_count():
    vfs = load_vfs()
    entries = list_entries(vfs, "/projects")
    assert len(entries) == 40
    assert "project-000" in entries
    print(f"PASS: list_entries('/projects') has {len(entries)} entries")


def test_list_project_dir():
    vfs = load_vfs()
    assert list_entries(vfs, "/projects/project-000") == ["deps.txt"]
    print("PASS: list_entries('/projects/project-000') == ['deps.txt']")


def test_list_package_dir():
    vfs = load_vfs()
    entries = list_entries(vfs, "/packages/pkg-113")
    assert set(entries) == {"deps.txt", "dependents.txt", "meta.json"}
    print("PASS: list_entries('/packages/pkg-113') has all 3 files")


def test_list_on_file_raises():
    vfs = load_vfs()
    try:
        list_entries(vfs, "/projects/project-000/deps.txt")
        assert False, "expected PrimitiveError"
    except PrimitiveError:
        print("PASS: list_entries on a file raises PrimitiveError")


# ---- P4 (read_record / cat) -------------------------------------------------


def test_read_project_deps():
    vfs = load_vfs()
    content = read_record(vfs, "/projects/project-000/deps.txt")
    lines = [l for l in content.split("\n") if l]
    assert set(lines) == {"pkg-113==3.0.0", "pkg-088==2.0.0", "pkg-076==3.0.0"}
    print(f"PASS: read_record project-000/deps.txt == {lines}")


def test_read_package_meta():
    vfs = load_vfs()
    content = read_record(vfs, "/packages/pkg-113/meta.json")
    meta = json.loads(content)
    assert meta["license"] == "GPL-3.0"
    assert meta["owner"] == "openforge"
    assert meta["deprecated"] is False
    print(f"PASS: read_record pkg-113/meta.json == {meta}")


def test_read_missing_raises():
    vfs = load_vfs()
    try:
        read_record(vfs, "/packages/pkg-999/meta.json")
        assert False, "expected PrimitiveError"
    except PrimitiveError:
        print("PASS: read_record on missing package raises PrimitiveError")


# ---- P3 (search_content / grep) --------------------------------------------


def test_grep_mit_packages():
    vfs = load_vfs()
    results = search_content(vfs, r'"license": "MIT"', "/packages")
    # every match should be a meta.json line
    assert all("meta.json" in r for r in results)
    matched_pkgs = {r.split("/")[2] for r in results}
    with open(DATA_PATH) as f:
        d = json.load(f)
    expected = {p for p, info in d["packages"].items() if info["license"] == "MIT"}
    assert matched_pkgs == expected
    print(f"PASS: grep MIT license matches {len(matched_pkgs)} packages, matches expected set")


def test_grep_single_file():
    vfs = load_vfs()
    results = search_content(vfs, "pkg-113", "/projects/project-000/deps.txt")
    assert len(results) == 1
    assert "pkg-113==3.0.0" in results[0]
    print(f"PASS: grep on single file: {results}")


def test_grep_invalid_pattern_raises():
    vfs = load_vfs()
    try:
        search_content(vfs, "(unclosed[", "/packages")
        assert False, "expected PrimitiveError"
    except PrimitiveError:
        print("PASS: grep with invalid regex raises PrimitiveError")


# ---- P2 (find_by_pattern / find) -------------------------------------------


def test_find_all_meta_json():
    vfs = load_vfs()
    results = find_by_pattern(vfs, "/", "*/meta.json")
    assert len(results) == 150
    print(f"PASS: find '*/meta.json' under / found {len(results)} files")


def test_find_all_project_deps():
    vfs = load_vfs()
    results = find_by_pattern(vfs, "/projects", "*/deps.txt")
    assert len(results) == 40
    print(f"PASS: find '*/deps.txt' under /projects found {len(results)} files")


def test_find_scoped_to_one_package():
    vfs = load_vfs()
    results = find_by_pattern(vfs, "/packages/pkg-113", "*")
    assert len(results) == 3
    print(f"PASS: find '*' under /packages/pkg-113 found {results}")


# ---- P5 (count_matches / wc) -----------------------------------------------


def test_count_dependents_of_known_package():
    vfs = load_vfs()
    with open(DATA_PATH) as f:
        d = json.load(f)
    from collections import defaultdict

    idx = defaultdict(list)
    for pname, info in d["projects"].items():
        for pkg, ver in info["deps"]:
            idx[pkg].append(pname)
    # pick a package with known dependents from the earlier exploration
    pkg = "pkg-116"
    expected_count = len(idx[pkg])
    actual = count_matches(vfs, f"/packages/{pkg}/dependents.txt")
    assert actual == expected_count, f"expected {expected_count}, got {actual}"
    print(f"PASS: count_matches dependents of {pkg} == {actual}")


def test_count_mit_packages():
    vfs = load_vfs()
    with open(DATA_PATH) as f:
        d = json.load(f)
    expected = sum(1 for info in d["packages"].values() if info["license"] == "MIT")
    actual = count_matches(vfs, "/packages", pattern=r'"license": "MIT"')
    assert actual == expected
    print(f"PASS: count_matches MIT packages == {actual} (matches direct count)")


# ---- cross-check: read_record vs dependents index consistency -------------


def test_dependents_txt_matches_forward_deps():
    """Cross-validate the VFS's dependents.txt reverse index against the
    forward project->deps data, for one specific package."""
    vfs = load_vfs()
    with open(DATA_PATH) as f:
        d = json.load(f)
    pkg = "pkg-116"
    forward = {
        f"{pname}=={ver}"
        for pname, info in d["projects"].items()
        for p, ver in info["deps"]
        if p == pkg
    }
    reverse_content = read_record(vfs, f"/packages/{pkg}/dependents.txt")
    reverse_lines = {l for l in reverse_content.split("\n") if l}
    assert forward == reverse_lines, f"{forward} != {reverse_lines}"
    print(f"PASS: dependents.txt for {pkg} matches forward-computed set: {reverse_lines}")


# ---- naming layer -----------------------------------------------------------


def test_naming_all_conditions_produce_5_specs():
    for cond in ("A-full", "A-zero", "B", "C"):
        specs = build_specs(cond)
        assert set(specs.keys()) == set(LOGICAL_IDS)
        print(f"PASS: condition {cond} produces specs for all 5 logical primitives")


def test_naming_a_zero_has_no_manual_text():
    specs = build_specs("A-zero")
    for pid in LOGICAL_IDS:
        assert specs[pid].manual == ""
    print("PASS: A-zero specs have empty manual text")


def test_naming_b_and_c_names_exact_length_match():
    from naming import NAMES

    for pid in LOGICAL_IDS:
        assert len(NAMES["B"][pid]) == len(NAMES["C"][pid]), (
            f"{pid}: name length mismatch B={NAMES['B'][pid]!r} "
            f"C={NAMES['C'][pid]!r}"
        )
    print("PASS: every B/C name pair has exactly matching character length")


def test_naming_b_and_c_manuals_exact_length_match():
    specs_b = build_specs("B")
    specs_c = build_specs("C")
    for pid in LOGICAL_IDS:
        len_b = len(specs_b[pid].manual)
        len_c = len(specs_c[pid].manual)
        assert len_b == len_c, f"{pid}: manual length mismatch ({len_b} vs {len_c})"
    print("PASS: B and C manuals are EXACTLY identical length per primitive")


def test_naming_names_are_distinct_across_conditions():
    names_a = set(build_specs("A-full")[pid].name for pid in LOGICAL_IDS)
    names_b = set(build_specs("B")[pid].name for pid in LOGICAL_IDS)
    names_c = set(build_specs("C")[pid].name for pid in LOGICAL_IDS)
    assert names_a.isdisjoint(names_b)
    assert names_a.isdisjoint(names_c)
    assert names_b.isdisjoint(names_c)
    print("PASS: naming conditions A/B/C use disjoint name sets (no leakage)")


def test_name_to_logical_id_roundtrip():
    for cond in ("A-full", "A-zero", "B", "C"):
        specs = build_specs(cond)
        rev = name_to_logical_id(cond)
        for pid in LOGICAL_IDS:
            assert rev[specs[pid].name] == pid
    print("PASS: name_to_logical_id correctly inverts build_specs for all conditions")


def test_render_full_manual_a_zero_is_short():
    manual_a_zero = render_full_manual("A-zero")
    manual_b = render_full_manual("B")
    assert len(manual_a_zero) < len(manual_b) / 4
    print(
        f"PASS: A-zero manual ({len(manual_a_zero)} chars) is much shorter "
        f"than B's ({len(manual_b)} chars)"
    )


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\nAll {len(tests)} primitive/naming tests passed.")
