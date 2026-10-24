"""
Sandbox executor for the "scripted function calls" interface row
(research_plan.md S1.2/S1.7, row 2): the model writes a single Python
script that calls the active-condition-named functions directly (e.g.
`result = grep("MIT", "/packages")`), with no shell grammar (no pipes,
flags, or glob-as-syntax) -- the single-shot counterpart to row 1
(sequential function-calling) that isolates turn-structure from
grammar-familiarity (S1.9).

Execution model: the script runs in a restricted namespace containing only
the active-condition name -> dispatch-bound-callable mapping, plus `print`
and builtins needed for basic data wrangling (len, sorted, set, etc). No
`import`, `open`, `exec`, `eval`, `__import__`, or filesystem/network access
is exposed -- this sandbox exists to execute untrusted-ish model-generated
code safely, not to be a general-purpose interpreter.

Only stdout (captured via `print`) is returned to the model, mirroring the
shell row's "only stdout/stderr returned" rule -- intermediate variables are
not visible unless printed, which is the entire point of the single-shot
condition.
"""

from __future__ import annotations

import io
import json as _json
import re as _re
import contextlib
from dataclasses import dataclass

from dispatch import Dispatcher


class _SafeRe:
    """Minimal read-only facade over the subset of `re` the model needs
    (search/match/findall/fullmatch/compile), exposed without requiring
    `import re` -- which is blocked by _FORBIDDEN_TOKENS below. No access
    to re.sub/compile-with-flags-that-execute-code or any other surface
    beyond pure pattern matching."""

    search = staticmethod(_re.search)
    match = staticmethod(_re.match)
    fullmatch = staticmethod(_re.fullmatch)
    findall = staticmethod(_re.findall)
    split = staticmethod(_re.split)


class _SafeJson:
    """Read-only facade over `json` (loads only -- no dump/dumps needed by
    any task, and no reason to let model-generated scripts write files)."""

    loads = staticmethod(_json.loads)


_ALLOWED_BUILTINS = {
    "len": len,
    "sorted": sorted,
    "set": set,
    "list": list,
    "dict": dict,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sum": sum,
    "min": min,
    "max": max,
    "any": any,
    "all": all,
    "print": print,
    "True": True,
    "False": False,
    "None": None,
    "Exception": Exception,
    "ValueError": ValueError,
    "KeyError": KeyError,
    "TypeError": TypeError,
    "IndexError": IndexError,
    "re": _SafeRe,
    "json": _SafeJson,
}

_FORBIDDEN_TOKENS = (
    "import", "__", "open(", "exec(", "eval(", "compile(", "globals(",
    "locals(", "getattr(", "setattr(", "delattr(", "input(",
)


@dataclass
class ScriptResult:
    ok: bool
    output: str = ""
    error: str = ""
    error_tag: str = ""  # "forbidden" | "invalid_name" | "runtime_error" | ""


class _DispatchFailure(RuntimeError):
    def __init__(self, error: str, error_tag: str):
        super().__init__(error)
        self.error_tag = error_tag


def _make_bound_fn(dispatcher: Dispatcher, name: str):
    def _fn(*args):
        result = dispatcher.call(name, list(args))
        if not result.ok:
            raise _DispatchFailure(result.error, result.error_tag)
        return result.value
    _fn.__name__ = name
    return _fn


def run_script(dispatcher: Dispatcher, script: str) -> ScriptResult:
    lowered = script.lower()
    for tok in _FORBIDDEN_TOKENS:
        if tok in lowered:
            return ScriptResult(
                ok=False,
                error=f"forbidden construct in script: {tok!r}",
                error_tag="forbidden",
            )

    namespace = dict(_ALLOWED_BUILTINS)
    for name in dispatcher.active_names():
        namespace[name] = _make_bound_fn(dispatcher, name)

    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            compiled = compile(script, "<model_script>", "exec")
            exec(compiled, {"__builtins__": {}}, namespace)
    except _DispatchFailure as e:
        return ScriptResult(ok=False, error=str(e), error_tag=e.error_tag, output=stdout.getvalue())
    except Exception as e:
        return ScriptResult(
            ok=False,
            error=f"{type(e).__name__}: {e}",
            error_tag="runtime_error",
            output=stdout.getvalue(),
        )

    return ScriptResult(ok=True, output=stdout.getvalue())
