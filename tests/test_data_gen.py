"""
Sanity checks for the synthetic dependency-graph generator.

Run with: python3 -m pytest tests/test_data_gen.py -v
(or just: python3 tests/test_data_gen.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_gen import build_graph  # noqa: E402


def find_cycle(packages):
    """Returns a cycle (list of pkg names) if one exists, else None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {p: WHITE for p in packages}
    stack_path = []

    def dfs(node):
        color[node] = GRAY
        stack_path.append(node)
        for dep, _ in packages[node]["deps"]:
            if color[dep] == GRAY:
                cyc_start = stack_path.index(dep)
                return stack_path[cyc_start:] + [dep]
            if color[dep] == WHITE:
                result = dfs(dep)
                if result:
                    return result
        stack_path.pop()
        color[node] = BLACK
        return None

    for p in packages:
        if color[p] == WHITE:
            cyc = dfs(p)
            if cyc:
                return cyc
    return None


def find_version_conflicts(projects):
    """Returns {pkg: {versions}} for packages depended-on with >1 version."""
    pkg_versions = {}
    for proj, info in projects.items():
        for pkg, ver in info["deps"]:
            pkg_versions.setdefault(pkg, set()).add(ver)
    return {p: v for p, v in pkg_versions.items() if len(v) > 1}


def test_determinism():
    g1 = build_graph(seed=42, n_projects=40, m_packages=150)
    g2 = build_graph(seed=42, n_projects=40, m_packages=150)
    assert g1.to_dict() == g2.to_dict(), "Same seed must produce identical graphs"
    print("PASS: determinism (same seed -> identical graph)")


def test_different_seeds_differ():
    g1 = build_graph(seed=42, n_projects=40, m_packages=150)
    g2 = build_graph(seed=43, n_projects=40, m_packages=150)
    assert g1.to_dict() != g2.to_dict(), "Different seeds should produce different graphs"
    print("PASS: different seeds produce different graphs")


def test_has_cycle():
    g = build_graph(seed=42, n_projects=40, m_packages=150)
    cyc = find_cycle(g.packages)
    assert cyc is not None, "Expected at least one forced cycle in package deps"
    print(f"PASS: found cycle: {' -> '.join(cyc)}")


def test_has_version_conflicts():
    g = build_graph(seed=42, n_projects=40, m_packages=150)
    conflicts = find_version_conflicts(g.projects)
    assert len(conflicts) >= 3, f"Expected >=3 version conflicts, found {len(conflicts)}"
    print(f"PASS: found {len(conflicts)} version-conflicted packages: {conflicts}")


def test_all_projects_have_deps():
    g = build_graph(seed=42, n_projects=40, m_packages=150)
    for name, info in g.projects.items():
        assert len(info["deps"]) >= 3, f"{name} has too few deps"
    print("PASS: all projects have >=3 deps")


def test_all_dep_targets_exist():
    g = build_graph(seed=42, n_projects=40, m_packages=150)
    for name, info in g.projects.items():
        for pkg, _ in info["deps"]:
            assert pkg in g.packages, f"Project {name} depends on unknown package {pkg}"
    for name, info in g.packages.items():
        for pkg, _ in info["deps"]:
            assert pkg in g.packages, f"Package {name} depends on unknown package {pkg}"
    print("PASS: all dependency targets reference existing packages")


if __name__ == "__main__":
    test_determinism()
    test_different_seeds_differ()
    test_has_cycle()
    test_has_version_conflicts()
    test_all_projects_have_deps()
    test_all_dep_targets_exist()
    print("\nAll sanity checks passed.")
