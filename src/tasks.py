"""
The task set (research_plan.md S1.6): ~24 tasks across three difficulty
tiers, held byte-for-byte identical across every experimental cell. Only the
*interface* (how the model must invoke primitives) and the *naming
condition* (what the primitives are called) vary -- never the task prompt,
never the correct answer.

Each Task carries an `oracle_fn(graph) -> Any` that computes the ground-truth
answer directly from the canonical Graph (data_gen.py), NOT from the VFS or
primitives layer -- this keeps the oracle independent of any bug that might
exist in vfs.py/primitives.py, which is the right separation for a scoring
oracle.

`answer_type` controls how a model's free-text final answer is normalized
and compared against the oracle in scoring.py:
  - "list"  : order-independent set-of-strings comparison
  - "int"   : numeric comparison (ints parsed out of the response)
  - "bool"  : yes/no / true/false comparison
  - "str"   : single-token/short-string comparison (case-insensitive)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List

from data_gen import Graph


@dataclass(frozen=True)
class Task:
    id: str
    tier: int  # 1, 2, or 3
    prompt: str
    oracle_fn: Callable[[Graph], Any]
    answer_type: str  # "list" | "int" | "bool" | "str"


# ---- Tier 1: single-hop lookup (direct, one primitive call) ---------------

def _t1_deps(graph: Graph) -> List[str]:
    return [f"{p}=={v}" for p, v in graph.projects["project-000"]["deps"]]


def _t1_license(graph: Graph) -> str:
    return graph.packages["pkg-113"]["license"]


def _t1_owner(graph: Graph) -> str:
    return graph.packages["pkg-116"]["owner"]


def _t1_deprecated(graph: Graph) -> bool:
    return bool(graph.packages["pkg-002"]["deprecated"])


def _t1_pkg_deps(graph: Graph) -> List[str]:
    return [f"{p}=={v}" for p, v in graph.packages["pkg-113"]["deps"]]


def _t1_last_updated(graph: Graph) -> str:
    return graph.packages["pkg-029"]["last_updated"]


def _t1_project_count(graph: Graph) -> int:
    return len(graph.projects)


def _t1_package_count(graph: Graph) -> int:
    return len(graph.packages)


TIER1: List[Task] = [
    Task("T1-01", 1, "List the direct dependencies of project-000 (as pkg==version pairs).", _t1_deps, "list"),
    Task("T1-02", 1, "What license does pkg-113 use?", _t1_license, "str"),
    Task("T1-03", 1, "Who is the owner of pkg-116?", _t1_owner, "str"),
    Task("T1-04", 1, "Is pkg-002 deprecated? Answer yes or no.", _t1_deprecated, "bool"),
    Task("T1-05", 1, "List the direct dependencies of pkg-113 itself (not project-000).", _t1_pkg_deps, "list"),
    Task("T1-06", 1, "What is the last_updated date of pkg-029?", _t1_last_updated, "str"),
    Task("T1-07", 1, "How many projects are there in total?", _t1_project_count, "int"),
    Task("T1-08", 1, "How many packages are there in total?", _t1_package_count, "int"),
]


# ---- Tier 2: reverse / aggregate (requires scan or reverse index) ---------

def _t2_dependents(graph: Graph) -> List[str]:
    return sorted(
        p for p, info in graph.projects.items()
        if any(pkg == "pkg-116" for pkg, _ in info["deps"])
    )


def _t2_dependents_count(graph: Graph) -> int:
    return len(_t2_dependents(graph))


def _t2_mit_count(graph: Graph) -> int:
    return sum(1 for info in graph.packages.values() if info["license"] == "MIT")


def _t2_deprecated_list(graph: Graph) -> List[str]:
    return sorted(p for p, info in graph.packages.items() if info["deprecated"])


def _t2_max_deps_project(graph: Graph) -> str:
    return max(graph.projects.items(), key=lambda kv: len(kv[1]["deps"]))[0]


def _t2_min_deps_project(graph: Graph) -> str:
    return min(graph.projects.items(), key=lambda kv: len(kv[1]["deps"]))[0]


def _t2_owner_count(graph: Graph) -> int:
    return sum(1 for info in graph.packages.values() if info["owner"] == "openforge")


def _t2_proprietary_list(graph: Graph) -> List[str]:
    return sorted(p for p, info in graph.packages.items() if info["license"] == "Proprietary")


TIER2: List[Task] = [
    Task("T2-01", 2, "Which projects depend directly on pkg-116?", _t2_dependents, "list"),
    Task("T2-02", 2, "How many projects depend directly on pkg-116?", _t2_dependents_count, "int"),
    Task("T2-03", 2, "How many packages have license MIT?", _t2_mit_count, "int"),
    Task("T2-04", 2, "List all deprecated packages.", _t2_deprecated_list, "list"),
    Task("T2-05", 2, "Which project has the most direct dependencies?", _t2_max_deps_project, "str"),
    Task("T2-06", 2, "Which project has the fewest direct dependencies?", _t2_min_deps_project, "str"),
    Task("T2-07", 2, "How many packages are owned by openforge?", _t2_owner_count, "int"),
    Task("T2-08", 2, "List all packages with license Proprietary.", _t2_proprietary_list, "list"),
]


# ---- Tier 3: composed / multi-step ----------------------------------------

def _t3_mit_dependents_of_116(graph: Graph) -> List[str]:
    mit_pkgs = {p for p, info in graph.packages.items() if info["license"] == "MIT"}
    return sorted(
        proj for proj, info in graph.projects.items()
        if any(pkg in mit_pkgs for pkg, _ in info["deps"])
    )


def _t3_version_conflict_116(graph: Graph) -> bool:
    versions = {v for info in graph.projects.values() for p, v in info["deps"] if p == "pkg-116"}
    return len(versions) > 1


def _t3_has_cycle(graph: Graph) -> bool:
    visiting, visited = set(), set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep, _ in graph.packages[node]["deps"]:
            if dfs(dep):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    return any(dfs(n) for n in graph.packages)


def _t3_projects_depending_on_deprecated(graph: Graph) -> List[str]:
    deprecated = {p for p, info in graph.packages.items() if info["deprecated"]}
    return sorted(
        proj for proj, info in graph.projects.items()
        if any(pkg in deprecated for pkg, _ in info["deps"])
    )


def _t3_count_projects_depending_on_deprecated(graph: Graph) -> int:
    return len(_t3_projects_depending_on_deprecated(graph))


def _t3_transitive_deps_pkg113(graph: Graph) -> List[str]:
    seen, stack = set(), ["pkg-113"]
    while stack:
        node = stack.pop()
        for dep, _ in graph.packages[node]["deps"]:
            if dep not in seen:
                seen.add(dep)
                stack.append(dep)
    return sorted(seen)


def _t3_most_common_license_among_deps_of_project037(graph: Graph) -> str:
    deps = graph.projects["project-037"]["deps"]
    counts: dict = {}
    for pkg, _ in deps:
        lic = graph.packages[pkg]["license"]
        counts[lic] = counts.get(lic, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _t3_packages_with_multiple_conflicting_versions(graph: Graph) -> int:
    pkg_versions: dict = {}
    for info in graph.projects.values():
        for pkg, ver in info["deps"]:
            pkg_versions.setdefault(pkg, set()).add(ver)
    return sum(1 for versions in pkg_versions.values() if len(versions) > 1)


TIER3: List[Task] = [
    Task("T3-01", 3, "List all projects that depend on at least one MIT-licensed package.", _t3_mit_dependents_of_116, "list"),
    Task("T3-02", 3, "Does pkg-116 have a version conflict (i.e. is it pinned to more than one version across different projects)? Answer yes or no.", _t3_version_conflict_116, "bool"),
    Task("T3-03", 3, "Does the package dependency graph contain any cycle? Answer yes or no.", _t3_has_cycle, "bool"),
    Task("T3-04", 3, "List all projects that depend (directly) on at least one deprecated package.", _t3_projects_depending_on_deprecated, "list"),
    Task("T3-05", 3, "How many projects depend directly on at least one deprecated package?", _t3_count_projects_depending_on_deprecated, "int"),
    Task("T3-06", 3, "List all transitive (direct and indirect) package-level dependencies of pkg-113.", _t3_transitive_deps_pkg113, "list"),
    Task("T3-07", 3, "Among project-037's direct dependencies, which license appears most often?", _t3_most_common_license_among_deps_of_project037, "str"),
    Task("T3-08", 3, "How many packages are pinned to more than one distinct version across different projects (i.e. have a version conflict)?", _t3_packages_with_multiple_conflicting_versions, "int"),
]


ALL_TASKS: List[Task] = TIER1 + TIER2 + TIER3


def get_task(task_id: str) -> Task:
    for t in ALL_TASKS:
        if t.id == task_id:
            return t
    raise KeyError(f"no such task: {task_id!r}")
