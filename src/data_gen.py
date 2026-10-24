"""
Synthetic dependency-graph generator for the tool-naming study (Study 1).

Produces a deterministic (seeded) graph of projects and packages:

  packages[pkg_name] = {
      "license": str,
      "owner": str,
      "last_updated": "YYYY-MM-DD",
      "deprecated": bool,
      "deps": [ (pkg_name, version_str), ... ]   # package-level deps (can cycle)
  }

  projects[project_name] = {
      "deps": [ (pkg_name, version_str), ... ]   # direct deps only
  }

This is the canonical data source. The VFS renderer (vfs_render.py) and the
function-calling primitives (primitives.py) both read from this same
structure, so the underlying capability is held constant across all
interface/naming conditions.
"""

from __future__ import annotations

import datetime
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

LICENSES = ["MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause", "Proprietary"]
OWNERS = ["acme-labs", "coreteam", "dataworks", "openforge", "nimbus-io", "redshift-dev"]

VERSION_POOL = ["1.0.0", "1.2.0", "1.4.3", "2.0.0", "2.1.1", "3.0.0"]


@dataclass
class Graph:
    seed: int
    packages: Dict[str, dict] = field(default_factory=dict)
    projects: Dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "packages": self.packages,
            "projects": self.projects,
        }

    @staticmethod
    def from_dict(d: dict) -> "Graph":
        g = Graph(seed=d["seed"])
        g.packages = d["packages"]
        g.projects = d["projects"]
        return g


def _random_date(rng: random.Random, days_back: int = 1095) -> str:
    d = datetime.date.today() - datetime.timedelta(days=rng.randint(0, days_back))
    return d.isoformat()


def _make_package_names(m: int) -> List[str]:
    return [f"pkg-{i:03d}" for i in range(m)]


def _make_project_names(n: int) -> List[str]:
    return [f"project-{i:03d}" for i in range(n)]


def generate_packages(rng: random.Random, pkg_names: List[str]) -> Dict[str, dict]:
    packages: Dict[str, dict] = {}
    for name in pkg_names:
        packages[name] = {
            "license": rng.choice(LICENSES),
            "owner": rng.choice(OWNERS),
            "last_updated": _random_date(rng),
            "deprecated": rng.random() < 0.10,
            "deps": [],  # filled in by generate_package_deps
        }
    return packages


def generate_package_deps(
    rng: random.Random,
    packages: Dict[str, dict],
    pkg_names: List[str],
    max_deps_per_pkg: int = 2,
    n_forced_cycles: int = 2,
) -> None:
    """
    Adds package-level dependencies (mostly forming a DAG), then forces a
    small number of explicit cycles for the "find a cycle" task tier.
    Mutates `packages` in place.
    """
    order = pkg_names[:]  # topological-ish order: only allow deps on later index
    for i, name in enumerate(order):
        n_deps = rng.randint(0, max_deps_per_pkg)
        candidates = order[i + 1 :]
        if not candidates or n_deps == 0:
            continue
        chosen = rng.sample(candidates, min(n_deps, len(candidates)))
        packages[name]["deps"] = [(c, rng.choice(VERSION_POOL)) for c in chosen]

    def reaches(start: str, target: str) -> bool:
        """DFS reachability check over current package deps."""
        seen = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            for dep, _ in packages[node]["deps"]:
                stack.append(dep)
        return False

    # Force explicit cycles: find pairs (a, b) where a already reaches b via
    # existing deps, then add a back-edge b -> a, creating a genuine cycle
    # a -> ... -> b -> a. Falls back to a direct 2-cycle (a <-> b) if no
    # reachable pair is found within the attempt budget.
    forced = 0
    attempts = 0
    while forced < n_forced_cycles and attempts < 200:
        attempts += 1
        i = rng.randint(0, len(order) - 2)
        j = rng.randint(i + 1, len(order) - 1)
        a, b = order[i], order[j]
        if any(dep == a for dep, _ in packages[b]["deps"]):
            continue  # edge already exists
        if reaches(a, b):
            packages[b]["deps"].append((a, rng.choice(VERSION_POOL)))
            forced += 1

    # Fallback: if reachable pairs were too scarce, force direct 2-cycles.
    fallback_attempts = 0
    while forced < n_forced_cycles and fallback_attempts < 50:
        fallback_attempts += 1
        i = rng.randint(0, len(order) - 2)
        j = rng.randint(i + 1, len(order) - 1)
        a, b = order[i], order[j]
        if any(dep == a for dep, _ in packages[b]["deps"]):
            continue
        packages[a]["deps"].append((b, rng.choice(VERSION_POOL)))
        packages[b]["deps"].append((a, rng.choice(VERSION_POOL)))
        forced += 1


def generate_projects(
    rng: random.Random,
    project_names: List[str],
    pkg_names: List[str],
    min_deps: int = 3,
    max_deps: int = 8,
) -> Dict[str, dict]:
    projects: Dict[str, dict] = {}
    for name in project_names:
        n_deps = rng.randint(min_deps, max_deps)
        chosen = rng.sample(pkg_names, min(n_deps, len(pkg_names)))
        projects[name] = {"deps": [(pkg, rng.choice(VERSION_POOL)) for pkg in chosen]}
    return projects


def inject_version_conflicts(
    rng: random.Random,
    projects: Dict[str, dict],
    pkg_names: List[str],
    n_conflicts: int = 3,
) -> List[str]:
    """
    Guarantees that at least `n_conflicts` packages are depended on by two or
    more projects with *different* pinned versions. Returns the list of
    packages for which a conflict was forced (useful for oracle construction /
    sanity checks).
    """
    forced_pkgs: List[str] = []
    proj_names = list(projects.keys())
    attempts = 0
    while len(forced_pkgs) < n_conflicts and attempts < 100:
        attempts += 1
        pkg = rng.choice(pkg_names)
        if pkg in forced_pkgs:
            continue
        depending = [p for p in proj_names if any(d == pkg for d, _ in projects[p]["deps"])]
        if len(depending) < 2:
            # force it: add this pkg as a dep to two random projects with diff versions
            two = rng.sample(proj_names, 2)
            v1, v2 = rng.sample(VERSION_POOL, 2)
            projects[two[0]]["deps"].append((pkg, v1))
            projects[two[1]]["deps"].append((pkg, v2))
            forced_pkgs.append(pkg)
            continue
        versions = {v for p in depending for d, v in projects[p]["deps"] if d == pkg}
        if len(versions) >= 2:
            forced_pkgs.append(pkg)
        else:
            # bump one dependent project's version to create a real conflict
            target = depending[0]
            new_deps = []
            for d, v in projects[target]["deps"]:
                if d == pkg:
                    alt = rng.choice([x for x in VERSION_POOL if x != v])
                    new_deps.append((d, alt))
                else:
                    new_deps.append((d, v))
            projects[target]["deps"] = new_deps
            forced_pkgs.append(pkg)
    return forced_pkgs


def build_graph(seed: int, n_projects: int = 40, m_packages: int = 150) -> Graph:
    rng = random.Random(seed)
    pkg_names = _make_package_names(m_packages)
    project_names = _make_project_names(n_projects)

    packages = generate_packages(rng, pkg_names)
    generate_package_deps(rng, packages, pkg_names)

    projects = generate_projects(rng, project_names, pkg_names)
    inject_version_conflicts(rng, projects, pkg_names)

    return Graph(seed=seed, packages=packages, projects=projects)


def save_graph(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(graph.to_dict(), f, indent=2)


def load_graph(path: Path) -> Graph:
    with open(path) as f:
        return Graph.from_dict(json.load(f))


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent.parent / "data" / "graph_seed42.json"
    g = build_graph(seed=42, n_projects=40, m_packages=150)
    save_graph(g, out_path)
    print(f"Wrote graph to {out_path}")
    print(f"  {len(g.projects)} projects, {len(g.packages)} packages")
