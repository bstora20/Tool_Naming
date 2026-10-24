"""
Virtual path space over the dependency Graph.

This module defines the *only* notion of "path" and "file content" that the
rest of the system uses. Both the primitives (primitives.py) and the future
shell-over-VFS renderer read through this same abstraction, so a path like
`/packages/pkg-113/meta.json` means exactly one thing everywhere.

Layout:

    /
    /projects/
    /projects/<name>/
    /projects/<name>/deps.txt          one "pkg==version" per line (direct deps)
    /packages/
    /packages/<name>/
    /packages/<name>/meta.json          JSON: license, owner, last_updated, deprecated
    /packages/<name>/deps.txt           one "pkg==version" per line (this pkg's own deps)
    /packages/<name>/dependents.txt     one "project==version" per line (reverse index:
                                         which projects directly depend on this package,
                                         and at what version they pinned it)

No file on disk is created for any of this -- everything is computed on
demand (or cached at construction) from the in-memory Graph.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Dict, List

from data_gen import Graph


class VfsError(Exception):
    """Raised for any invalid path operation (missing path, wrong type, etc.)."""


class VirtualFS:
    def __init__(self, graph: Graph):
        self.graph = graph
        self._dependents = self._build_dependents_index(graph)

    @staticmethod
    def _build_dependents_index(graph: Graph) -> Dict[str, List[str]]:
        """pkg_name -> list of 'project==version' strings, one per project that
        directly depends on that package."""
        idx: Dict[str, List[str]] = defaultdict(list)
        for proj_name, info in graph.projects.items():
            for pkg, ver in info["deps"]:
                idx[pkg].append(f"{proj_name}=={ver}")
        return idx

    # ---- path classification -------------------------------------------------

    def _split(self, path: str) -> List[str]:
        path = path.strip()
        if not path.startswith("/"):
            raise VfsError(f"path must be absolute (start with '/'): {path!r}")
        parts = [p for p in path.split("/") if p != ""]
        return parts

    def is_dir(self, path: str) -> bool:
        parts = self._split(path)
        if len(parts) == 0:
            return True  # "/"
        if len(parts) == 1:
            return parts[0] in ("projects", "packages")
        if len(parts) == 2:
            kind, name = parts
            if kind == "projects":
                return name in self.graph.projects
            if kind == "packages":
                return name in self.graph.packages
            return False
        return False  # depth-3 paths are always files (or invalid)

    def is_file(self, path: str) -> bool:
        parts = self._split(path)
        if len(parts) != 3:
            return False
        kind, name, fname = parts
        if kind == "projects":
            return name in self.graph.projects and fname == "deps.txt"
        if kind == "packages":
            return name in self.graph.packages and fname in (
                "meta.json",
                "deps.txt",
                "dependents.txt",
            )
        return False

    def exists(self, path: str) -> bool:
        return self.is_dir(path) or self.is_file(path)

    # ---- directory listing -----------------------------------------------

    def list_dir(self, path: str) -> List[str]:
        """Return sorted entry names directly inside `path`. Raises VfsError
        if `path` is not a directory."""
        parts = self._split(path)

        if len(parts) == 0:
            return ["packages", "projects"]

        if len(parts) == 1:
            kind = parts[0]
            if kind == "projects":
                return sorted(self.graph.projects.keys())
            if kind == "packages":
                return sorted(self.graph.packages.keys())
            raise VfsError(f"no such directory: {path!r}")

        if len(parts) == 2:
            kind, name = parts
            if kind == "projects" and name in self.graph.projects:
                return ["deps.txt"]
            if kind == "packages" and name in self.graph.packages:
                return ["deps.txt", "dependents.txt", "meta.json"]
            raise VfsError(f"no such directory: {path!r}")

        raise VfsError(f"not a directory: {path!r}")

    # ---- file reads --------------------------------------------------------

    def read_file(self, path: str) -> str:
        """Return the full text content of the file at `path`. Raises
        VfsError if `path` is not a file."""
        parts = self._split(path)
        if len(parts) != 3:
            raise VfsError(f"not a file: {path!r}")
        kind, name, fname = parts

        if kind == "projects":
            if name not in self.graph.projects:
                raise VfsError(f"no such project: {name!r}")
            if fname != "deps.txt":
                raise VfsError(f"no such file: {path!r}")
            deps = self.graph.projects[name]["deps"]
            return "\n".join(f"{pkg}=={ver}" for pkg, ver in deps) + ("\n" if deps else "")

        if kind == "packages":
            if name not in self.graph.packages:
                raise VfsError(f"no such package: {name!r}")
            info = self.graph.packages[name]
            if fname == "meta.json":
                meta = {
                    "license": info["license"],
                    "owner": info["owner"],
                    "last_updated": info["last_updated"],
                    "deprecated": info["deprecated"],
                }
                return json.dumps(meta, indent=2) + "\n"
            if fname == "deps.txt":
                deps = info["deps"]
                return "\n".join(f"{pkg}=={ver}" for pkg, ver in deps) + ("\n" if deps else "")
            if fname == "dependents.txt":
                lines = sorted(self._dependents.get(name, []))
                return "\n".join(lines) + ("\n" if lines else "")
            raise VfsError(f"no such file: {path!r}")

        raise VfsError(f"no such file: {path!r}")

    def read_lines(self, path: str) -> List[str]:
        """Convenience: read_file split into non-empty lines."""
        content = self.read_file(path)
        return [line for line in content.split("\n") if line != ""]

    # ---- recursive walk (for `find`) --------------------------------------

    def walk_files(self, root: str) -> List[str]:
        """Return all file paths reachable under `root` (root itself
        included if it is already a file)."""
        if self.is_file(root):
            return [root]
        if not self.is_dir(root):
            raise VfsError(f"no such path: {root!r}")

        results: List[str] = []
        parts = self._split(root)

        if len(parts) == 0:
            for kind in ("projects", "packages"):
                results.extend(self.walk_files(f"/{kind}"))
            return results

        if len(parts) == 1:
            kind = parts[0]
            names = (
                self.graph.projects.keys() if kind == "projects" else self.graph.packages.keys()
            )
            for name in sorted(names):
                results.extend(self.walk_files(f"/{kind}/{name}"))
            return results

        if len(parts) == 2:
            for fname in self.list_dir(root):
                results.append(f"{root.rstrip('/')}/{fname}")
            return results

        raise VfsError(f"no such path: {root!r}")
