"""
Simplified shell-pipeline interpreter for the shell-over-VFS interface row.

This is NOT a real shell -- it supports exactly the subset of Unix pipeline
semantics needed for this task family: a first stage that reads from the
VFS (any of P1-P5 via the active naming condition), optionally followed by
one or more pipe stages that filter/count the previous stage's output as
*text lines*, mirroring how `grep`/`wc` behave when reading stdin instead of
a file argument.

Supported pipe-target semantics (by logical primitive id, regardless of the
active name string):
  - P3 (grep-like): first arg is treated as a regex pattern; filters the
    incoming lines, ignoring any second "path" arg (since input is piped,
    not read from a file).
  - P5 (wc-like): with no args, counts incoming lines; with one arg, treats
    it as a regex pattern and counts matching lines first.
Piping into P1/P2/P4 is not supported (not meaningful for this primitive
set) and raises ShellError, mirroring a real shell's "command not expecting
stdin" confusion.

Quoting is handled via shlex (POSIX-ish), so arguments like `"license": "MIT"`
can be passed as a single quoted token, as real shells require.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Any, List, Optional

from dispatch import CallResult, Dispatcher


class ShellError(Exception):
    pass


@dataclass
class ShellResult:
    ok: bool
    output: str = ""
    error: str = ""
    error_tag: str = ""
    old_form_grammar: bool = False  # condition D/D2 only: see dispatch.py
    delimiter_rule_violated: bool = False  # condition D2 only: see dispatch.py


def _value_to_lines(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, int):
        return [str(value)]
    if isinstance(value, str):
        return [l for l in value.split("\n") if l != ""]
    return [str(value)]


def _value_to_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value)


def run_pipeline(dispatcher: Dispatcher, command_line: str) -> ShellResult:
    stages_raw = [s.strip() for s in command_line.split("|")]
    if not stages_raw or stages_raw == [""]:
        return ShellResult(ok=False, error="empty command", error_tag="invalid_name")

    try:
        tokens0 = shlex.split(stages_raw[0])
    except ValueError as e:
        return ShellResult(ok=False, error=f"parse error: {e}", error_tag="wrong_args")
    if not tokens0:
        return ShellResult(ok=False, error="empty command", error_tag="invalid_name")

    name0, args0 = tokens0[0], tokens0[1:]
    result: CallResult = dispatcher.call(name0, args0)
    old_form_grammar = result.old_form_grammar
    delimiter_rule_violated = result.delimiter_rule_violated
    if not result.ok:
        return ShellResult(
            ok=False, error=result.error, error_tag=result.error_tag,
            old_form_grammar=old_form_grammar,
            delimiter_rule_violated=delimiter_rule_violated,
        )

    value: Any = result.value

    for stage in stages_raw[1:]:
        try:
            tokens = shlex.split(stage)
        except ValueError as e:
            return ShellResult(ok=False, error=f"parse error: {e}", error_tag="wrong_args")
        if not tokens:
            return ShellResult(ok=False, error="empty pipe stage", error_tag="invalid_name")

        name, args = tokens[0], tokens[1:]
        pid = dispatcher._name_to_pid.get(name)
        if pid is None:
            return ShellResult(
                ok=False,
                error=f"unknown command in pipeline: {name!r}",
                error_tag="invalid_name",
            )

        lines = _value_to_lines(value)

        if pid == "P3":  # grep-like: filter piped lines by regex
            if len(args) < 1:
                return ShellResult(ok=False, error=f"{name!r} requires a pattern", error_tag="wrong_args")
            try:
                regex = re.compile(args[0])
            except re.error as e:
                return ShellResult(ok=False, error=f"invalid pattern: {e}", error_tag="primitive_error")
            value = [l for l in lines if regex.search(l)]

        elif pid == "P5":  # wc-like: count piped lines, optionally pre-filtered
            if len(args) >= 1:
                try:
                    regex = re.compile(args[0])
                except re.error as e:
                    return ShellResult(ok=False, error=f"invalid pattern: {e}", error_tag="primitive_error")
                value = len([l for l in lines if regex.search(l)])
            else:
                value = len(lines)

        else:
            return ShellResult(
                ok=False,
                error=f"cannot pipe into {name!r} (only grep-like/wc-like commands accept piped input)",
                error_tag="wrong_args",
            )

    return ShellResult(
        ok=True, output=_value_to_text(value),
        old_form_grammar=old_form_grammar,
        delimiter_rule_violated=delimiter_rule_violated,
    )
