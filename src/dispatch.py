"""
Shared dispatcher: resolves an active-condition name string back to a
logical primitive and calls it with positional args, against a given
VirtualFS. This is the one place all three interface harnesses (sequential
function-calling, scripted function-calls, shell-over-VFS) go through to
actually execute a primitive -- so naming-condition dispatch logic is
written once, not duplicated per harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from naming import name_to_logical_id
from primitives import (
    PrimitiveError,
    list_entries,
    find_by_pattern,
    search_content,
    read_record,
    count_matches,
)
from vfs import VirtualFS

_IMPLS = {
    "P1": list_entries,
    "P2": find_by_pattern,
    "P3": search_content,
    "P4": read_record,
    "P5": count_matches,
}

# Positional-argument order per logical primitive, matching primitives.py
# signatures exactly (vfs is always bound separately, not part of this list).
_ARG_ORDER = {
    "P1": ["path"],
    "P2": ["root", "pattern"],
    "P3": ["pattern", "path"],
    "P4": ["path"],
    "P5": ["path", "pattern"],
}

# Condition D ("near-miss grammar") documents a SWAPPED argument order for
# P2/P3 relative to the real convention above -- the dispatcher must accept
# calls in the DOCUMENTED (swapped) order for D, since that's what the model
# was told to use. This dict overrides _ARG_ORDER's entries only when
# condition is "D" or "D2" (D2 reuses D's order swap verbatim and adds a
# second, independent rule on top -- see _DELIMITER_RULE_PIDS below); all
# other primitives/conditions use _ARG_ORDER as-is.
_ARG_ORDER_D_OVERRIDES = {
    "P2": ["pattern", "root"],
    "P3": ["path", "pattern"],
}

# Condition D2's second combined rule, on top of D's order swap: the
# "pattern" argument for P2/P3 must be written wrapped in angle brackets
# (e.g. "<MIT>" not "MIT"). Unlike the order swap, this is enforced as a
# hard dispatch-level requirement -- omitting the brackets is a dispatch
# error, not merely a wrong *value* -- mirroring the "genuinely breaking if
# violated" flag-rename/quoting rules Experiment C combined with order
# changes at higher doses.
_DELIMITER_RULE_PIDS = {"P2", "P3"}


def _strip_pattern_delimiters(pid: str, kwargs: dict) -> tuple[bool, str]:
    """
    For condition D2 only: validate and strip the required <...> wrapping
    on the "pattern" kwarg. Returns (ok, value_or_error_message). Leaves
    kwargs untouched if pid has no pattern arg (shouldn't happen for
    P2/P3, which always include "pattern" in their documented order).
    """
    pattern = kwargs.get("pattern")
    if not isinstance(pattern, str) or len(pattern) < 2 or pattern[0] != "<" or pattern[-1] != ">":
        return False, f"pattern argument must be wrapped in angle brackets, e.g. <...>; got {pattern!r}"
    return True, pattern[1:-1]


class DispatchError(Exception):
    """Raised for an unknown command name or a wrong number of arguments.
    Distinct from PrimitiveError (invalid args to a *valid* primitive call)
    so error-taxonomy logging (research_plan.md S1.8) can separate
    "invalid tool name" / "wrong args" failure modes."""


@dataclass(frozen=True)
class CallResult:
    ok: bool
    value: Any = None
    error: str = ""
    error_tag: str = ""  # "invalid_name" | "wrong_args" | "primitive_error" | ""
    old_form_grammar: bool = False  # condition D/D2 only: True if the call's
    # argument order looks like the REAL/old convention rather than the
    # documented swapped order (heuristic; see _classify_old_form below).
    delimiter_rule_violated: bool = False  # condition D2 only: True if the
    # call's pattern argument was NOT wrapped in the required <...> form
    # (the hard-enforced second rule D2 adds on top of D's order swap).


def documented_arg_order(condition: str, pid: str) -> list:
    """
    The positional argument order the model was TOLD to use for `pid` under
    `condition` (i.e. what's in the manual/schema), as opposed to
    `_ARG_ORDER[pid]` which is always the real primitives.py order. Equal to
    `_ARG_ORDER[pid]` for every condition/primitive except condition D/D2's
    P2/P3 overrides. Exposed as a public helper so every harness (shell,
    scripted, sequential) can derive its tool-call argument/schema ordering
    from this single source instead of re-deriving or hardcoding it --
    harness_sequential.py previously duplicated a *non-D-aware* copy of
    _ARG_ORDER, which this helper replaces.
    """
    if condition in ("D", "D2") and pid in _ARG_ORDER_D_OVERRIDES:
        return _ARG_ORDER_D_OVERRIDES[pid]
    return _ARG_ORDER[pid]


def _looks_like_path(s: Any) -> bool:
    return isinstance(s, str) and s.startswith("/")


def _classify_old_form(pid: str, args: list) -> bool:
    """
    Heuristic "old-form" detector for condition D's P2/P3 near-miss grammar
    (mirrors experiments.txt Experiment C's "old form" tracking): did this
    call's first positional argument look like the REAL Unix convention
    (root/path first) rather than D's documented swapped convention
    (pattern first)?

    VFS paths are always absolute (start with "/", enforced by vfs.py), so
    "does the first arg start with '/'" is a reasonably reliable signal for
    which positional slot the model intended as "the path-like one" --
    though it is a heuristic, not a parse of named arguments, since the
    shell/scripted interfaces pass purely positional args.
    """
    if not args:
        return False
    first_is_path = _looks_like_path(args[0])
    if pid == "P2":  # real order: (root, pattern) -- root is path-like first
        return first_is_path
    if pid == "P3":  # real order: (pattern, path) -- pattern is NOT path-like first
        return not first_is_path
    return False


class Dispatcher:
    """Bound to one (vfs, naming_condition) pair for the duration of one
    task/harness run."""

    def __init__(self, vfs: VirtualFS, condition: str):
        self.vfs = vfs
        self.condition = condition
        self._name_to_pid = name_to_logical_id(condition)

    def active_names(self) -> List[str]:
        return list(self._name_to_pid.keys())

    def pid_for_name(self, name: str) -> str | None:
        return self._name_to_pid.get(name)

    def call(self, name: str, args: list) -> CallResult:
        pid = self._name_to_pid.get(name)
        if pid is None:
            return CallResult(
                ok=False,
                error=f"unknown command: {name!r} (not one of {self.active_names()})",
                error_tag="invalid_name",
            )

        # "documented" order: what the model was told the argument order is
        # under the active condition (differs from the real primitive order
        # only for condition D/D2's P2/P3 near-miss grammar overrides).
        documented_order = documented_arg_order(self.condition, pid)

        old_form = self.condition in ("D", "D2") and _classify_old_form(pid, args)

        if len(args) > len(documented_order):
            return CallResult(
                ok=False,
                error=f"{name!r} takes at most {len(documented_order)} argument(s), got {len(args)}",
                error_tag="wrong_args",
                old_form_grammar=old_form,
            )

        # Re-map from documented-order positional args back to the real
        # primitive-order kwargs expected by primitives.py's function
        # signature (identity re-map when documented_order == _ARG_ORDER[pid]).
        kwargs = dict(zip(documented_order, args))

        # Condition D2's second combined rule: pattern must be <...>-wrapped.
        # Enforced as a hard dispatch error (distinct error_tag) so it's
        # measurable separately from "wrong_args"/"invalid_name" and from
        # the order-swap's old_form_grammar heuristic.
        delimiter_violated = False
        if self.condition == "D2" and pid in _DELIMITER_RULE_PIDS and "pattern" in kwargs:
            ok, unwrapped_or_err = _strip_pattern_delimiters(pid, kwargs)
            if not ok:
                return CallResult(
                    ok=False,
                    error=unwrapped_or_err,
                    error_tag="primitive_error",
                    old_form_grammar=old_form,
                    delimiter_rule_violated=True,
                )
            kwargs["pattern"] = unwrapped_or_err

        real_order = _ARG_ORDER[pid]
        ordered_args = [kwargs[p] for p in real_order if p in kwargs]

        fn = _IMPLS[pid]
        try:
            result = fn(self.vfs, *ordered_args)
        except PrimitiveError as e:
            return CallResult(
                ok=False, error=str(e), error_tag="primitive_error",
                old_form_grammar=old_form, delimiter_rule_violated=delimiter_violated,
            )
        except TypeError as e:
            return CallResult(
                ok=False, error=str(e), error_tag="wrong_args",
                old_form_grammar=old_form, delimiter_rule_violated=delimiter_violated,
            )
        return CallResult(
            ok=True, value=result,
            old_form_grammar=old_form, delimiter_rule_violated=delimiter_violated,
        )
