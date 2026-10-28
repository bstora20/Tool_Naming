"""
Experiment 1 (follow-up to the Condition D near-miss-grammar study): does the
near-miss-grammar interference effect reproduce when the primitive in
question has a genuinely strong, "sticky" real-world calling convention --
as opposed to find/grep's comparatively weak documented-argument-order
convention, which Condition D showed produces NO measurable interference?

`jq` is the natural test case: real `jq` users have an unusually strong,
near-universal prior that the filter expression comes first and the file
comes second (`jq '.license' file.json`). Experiment C's "familiar name is
worse" finding was hypothesized (in the follow-up to the Condition-D report)
to be almost entirely attributable to jq specifically, rather than to a
general real-vs-random-name effect. This module tests that directly.

This is a SELF-CONTAINED module, deliberately NOT wired into naming.py's
LOGICAL_IDS / dispatch.py's _ARG_ORDER / _IMPLS tables. Those modules assume
exactly five primitives (P1-P5), fixed and identical across every condition
(A/B/C/D/D2) -- the jq-style primitive (P6, defined in primitives.py as
`jq_filter`) is architecturally a one-off addition only relevant to the two
conditions defined here, so threading it through the shared tables would
needlessly complicate code whose job is "same 5 primitives, different
names/grammar" with a sixth special case that doesn't fit that shape. This
module reuses VirtualFS/Graph (data_gen.py/vfs.py), the primitive itself
(primitives.py), the existing task/oracle/scoring machinery (tasks.py,
scoring.py -- the 8 tasks below are REUSED VERBATIM, unmodified, from
tasks.py, since their oracle values are exactly the meta.json fields
jq_filter extracts), and LLMClient (llm_client.py) -- only the naming/
dispatch/harness layer in between is new.

Two conditions, mirroring the A-full vs. D comparison but for the sticky
jq idiom instead of find/grep's weak one:

  JQ-real  tool name "jq", documented arg order (filter_expr, path) --
           matches the real jq CLI convention exactly (the "idiomatic,
           correctly-documented" condition, analogous to A-full).
  JQ-swap  tool name "jq" (same real idiom-triggering name), documented arg
           order (path, filter_expr) -- the near-miss: same strong-prior
           name, but the DOCUMENTED order is the opposite of what real jq
           users expect (analogous to Condition D's find/grep order-swap,
           but now applied to a genuinely sticky idiom instead of a weak
           one).

If the revised hypothesis (interference is idiom-specific, not general) is
right, JQ-swap should show measurably worse success and/or a measurable rate
of old-form-grammar reversion (model silently reverts to real jq's
filter-first order despite the documented path-first order) -- in contrast
to Condition D, which showed ~0% old-form reversion and no success-rate
penalty for find/grep's weaker convention.

Usage:
    python3 src/exp1_jq.py --api-key KEY [--pilot] [--conditions JQ-real,JQ-swap]
                            [--seeds 1,2,3] [--out results/exp1_jq.jsonl]
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from data_gen import Graph  # noqa: E402
from vfs import VirtualFS  # noqa: E402
from primitives import jq_filter, PrimitiveError, _JQ_SUPPORTED_FIELDS  # noqa: E402
from tasks import get_task, Task  # noqa: E402
from scoring import score_answer  # noqa: E402
from llm_client import make_client, LLMClient, Usage  # noqa: E402

DATA_PATH = SRC_DIR.parent / "data" / "graph_seed42.json"
RESULTS_DIR = SRC_DIR.parent / "results"

# These 8 existing tasks are reused verbatim: each one's oracle value is
# exactly a meta.json field (license/owner/last_updated/deprecated, single-
# file or aggregated-over-/packages), which is precisely jq_filter's domain.
# No new tasks/oracles are introduced -- same ground truth, same scoring.
JQ_TASK_IDS = ["T1-02", "T1-03", "T1-04", "T1-06", "T2-03", "T2-04", "T2-07", "T2-08"]

TOOL_NAME = "jq"

CONDITIONS = ["JQ-real", "JQ-swap"]

_DOCUMENTED_ORDER = {
    "JQ-real": ["filter_expr", "path"],
    "JQ-swap": ["path", "filter_expr"],
}

_SUPPORTED_FIELDS_STR = ", ".join(f"'{f}'" for f in sorted(_JQ_SUPPORTED_FIELDS))

_MANUAL = {
    "JQ-real": (
        f"{TOOL_NAME}(filter_expr, path)\n"
        "Extract one top-level JSON field from meta.json file(s).\n"
        f"filter_expr must be one of {_SUPPORTED_FIELDS_STR}. path may be a\n"
        "single meta.json file or a directory (searched recursively for\n"
        "every meta.json underneath it).\n"
        f"Takes the FILTER EXPRESSION FIRST and the PATH SECOND -- i.e.\n"
        f"{TOOL_NAME}(filter_expr, path), matching the standard jq command-line\n"
        f"convention `jq FILTER FILE`.\n"
        f"  {TOOL_NAME}('.license', '/packages/pkg-113/meta.json')\n"
        "      -> [\"/packages/pkg-113/meta.json:MIT\"]\n"
        f"  {TOOL_NAME}('.license', '/packages')\n"
        "      -> one \"path:license\" entry per package\n"
        "Returns a list of \"path:value\" strings. Raises an error if\n"
        "filter_expr is not a supported field, if path does not exist, or if\n"
        "no meta.json file is found under path."
    ),
    "JQ-swap": (
        f"{TOOL_NAME}(path, filter_expr)\n"
        "Extract one top-level JSON field from meta.json file(s).\n"
        f"filter_expr must be one of {_SUPPORTED_FIELDS_STR}. path may be a\n"
        "single meta.json file or a directory (searched recursively for\n"
        "every meta.json underneath it).\n"
        f"In this environment {TOOL_NAME} takes the PATH FIRST and the FILTER\n"
        f"EXPRESSION SECOND -- i.e. {TOOL_NAME}(path, filter_expr), NOT\n"
        f"{TOOL_NAME}(filter_expr, path).\n"
        f"  {TOOL_NAME}('/packages/pkg-113/meta.json', '.license')\n"
        "      -> [\"/packages/pkg-113/meta.json:MIT\"]\n"
        f"  {TOOL_NAME}('/packages', '.license')\n"
        "      -> one \"path:license\" entry per package\n"
        "Returns a list of \"path:value\" strings. Raises an error if\n"
        "filter_expr is not a supported field, if path does not exist, or if\n"
        "no meta.json file is found under path."
    ),
}

SYSTEM_PROMPT = (
    "You are an assistant that answers questions about a software project's "
    "dependency graph by calling the tool provided to you. Call the tool as "
    "needed to gather information, then give a final concise answer as plain "
    "text (not a tool call) once you have enough information. Do not guess -- "
    "only answer based on information you have retrieved via tool calls."
)

# ---- shell-text variant --------------------------------------------------
#
# The sequential (JSON tool-calling) harness above requires the model to
# produce NAMED parameters (filter_expr=..., path=...), which may
# structurally short-circuit the "sticky idiom" effect: there is no raw
# positional text for old-form muscle memory to leak into. Real jq's strong
# prior is specifically about POSITIONAL CLI TEXT (`jq '.license' file.json`)
# -- Condition D/D2 showed their (null/positive) results on the shell
# interface specifically, so for an apples-to-apples comparison, jq's idiom
# must also be tested as free-text shell command generation, not just
# structured tool-calling.

SHELL_SYSTEM_PROMPT_TEMPLATE = (
    "You are an assistant that answers questions about a software project's "
    "dependency graph via a Unix-like shell over a virtual file system. You "
    "do NOT have interactive tools -- instead, you must write a single shell "
    "command using the command described below, then see only its output "
    "(stdout/stderr).\n\n"
    "Available command:\n{manual}\n\n"
    "Respond with exactly one fenced shell code block (```sh ... ```) "
    "containing your command. Do not include any explanation outside the "
    "code block on this turn."
)

SHELL_REPAIR_PROMPT_TEMPLATE = (
    "Your command failed with this error:\n{error}\n\n"
    "Write a corrected single command in one fenced code block to fix this "
    "and get the information you need."
)

SHELL_FINAL_ANSWER_PROMPT = (
    "Based on the output above, give your final answer to the original "
    "question as a short plain-text response (no code)."
)

_CODE_BLOCK_RE = re.compile(r"```(?:sh|bash|shell)?\s*\n(.*?)```", re.DOTALL)


def _extract_command(text: str) -> str:
    m = _CODE_BLOCK_RE.search(text)
    raw = m.group(1).strip() if m else text.strip()
    return raw.splitlines()[0].strip() if raw else raw


def _looks_like_filter(s: Any) -> bool:
    return isinstance(s, str) and s.startswith(".")


def _looks_like_path(s: Any) -> bool:
    return isinstance(s, str) and s.startswith("/")


@dataclass
class CallResult:
    ok: bool
    value: Any = None
    error: str = ""
    error_tag: str = ""
    old_form_grammar: bool = False  # JQ-swap only: see dispatch_jq


def dispatch_jq(vfs: VirtualFS, condition: str, name: str, args: List[Any]) -> CallResult:
    """
    Minimal single-tool dispatcher for the jq-style primitive, mirroring
    dispatch.py's Dispatcher.call() but specialized to the one tool defined
    in this module (name is always "jq" regardless of condition -- the
    manipulation here is purely about documented ARGUMENT ORDER, not name
    familiarity, since both conditions use the real idiomatic name).
    """
    if name != TOOL_NAME:
        return CallResult(ok=False, error=f"unknown tool {name!r}", error_tag="invalid_name")

    order = _DOCUMENTED_ORDER[condition]
    if len(args) != 2:
        return CallResult(ok=False, error=f"expected 2 args, got {len(args)}", error_tag="wrong_args")

    old_form = False
    if condition == "JQ-swap":
        # Documented order is (path, filter_expr). old_form = model ignored
        # the documentation and reverted to the real jq idiom (filter first,
        # path second) despite being told the opposite order.
        old_form = _looks_like_filter(args[0]) and _looks_like_path(args[1])

    kwargs = dict(zip(order, args))
    filter_expr = kwargs.get("filter_expr")
    path = kwargs.get("path")

    try:
        value = jq_filter(vfs, filter_expr, path)
    except PrimitiveError as e:
        return CallResult(ok=False, error=str(e), error_tag="primitive_error", old_form_grammar=old_form)
    except TypeError as e:
        return CallResult(ok=False, error=str(e), error_tag="wrong_args", old_form_grammar=old_form)
    return CallResult(ok=True, value=value, old_form_grammar=old_form)


def _build_tool_schema(condition: str) -> Dict[str, Any]:
    order = _DOCUMENTED_ORDER[condition]
    props = {arg: {"type": "string"} for arg in order}
    return {
        "name": TOOL_NAME,
        "description": _MANUAL[condition],
        "input_schema": {"type": "object", "properties": props, "required": order},
    }


def _shell_manual(condition: str) -> str:
    """
    Shell-flavored rendering of the manual: shows the command as positional
    CLI usage (`jq ARG1 ARG2`) rather than the function-call notation used
    in the sequential-interface manual, since that's the form a shell
    command line actually takes.
    """
    order = _DOCUMENTED_ORDER[condition]
    usage = f"{TOOL_NAME} " + " ".join(f"<{arg}>" for arg in order)
    if condition == "JQ-real":
        example = f"  {TOOL_NAME} '.license' /packages/pkg-113/meta.json"
    else:
        example = f"  {TOOL_NAME} /packages/pkg-113/meta.json '.license'"
    return (
        f"{usage}\n"
        "Extract one top-level JSON field from meta.json file(s).\n"
        f"filter_expr must be one of {_SUPPORTED_FIELDS_STR}. path may be a\n"
        "single meta.json file or a directory (searched recursively for\n"
        "every meta.json underneath it).\n"
        f"Argument order is: {', '.join(order)}.\n"
        f"{example}\n"
        "      -> /packages/pkg-113/meta.json:MIT\n"
        "Prints one \"path:value\" line per matching file. Exits with an\n"
        "error if filter_expr is not a supported field, if path does not\n"
        "exist, or if no meta.json file is found under path."
    )


def dispatch_jq_shell(vfs: VirtualFS, condition: str, command_line: str) -> CallResult:
    """
    Parses a raw shell command line (e.g. `jq '.license' /packages/pkg-113`)
    via shlex, then delegates to dispatch_jq with the resulting positional
    args. This is the shell-text analogue of dispatch_jq's direct-kwargs
    call used by the sequential/tool-calling harness -- the key difference
    is that here the model had to produce raw positional CLI text itself,
    which is exactly the surface where real jq's sticky idiom could leak
    through as old-form reversion.
    """
    try:
        tokens = shlex.split(command_line)
    except ValueError as e:
        return CallResult(ok=False, error=f"parse error: {e}", error_tag="wrong_args")
    if not tokens:
        return CallResult(ok=False, error="empty command", error_tag="invalid_name")

    name, args = tokens[0], tokens[1:]
    return dispatch_jq(vfs, condition, name, args)


@dataclass
class RunOutcome:
    final_answer: str = ""
    turns_used: int = 0
    usage: Usage = field(default_factory=Usage)
    timed_out: bool = False
    repaired: bool = False
    old_form_grammar: bool = False
    final_error_tag: str = ""
    command_log: List[str] = field(default_factory=list)
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)


def run_jq_shell(
    client: LLMClient,
    vfs: VirtualFS,
    condition: str,
    task_prompt: str,
) -> RunOutcome:
    """
    Shell-text variant of run_jq_sequential, mirroring harness_shell.py's
    one-shot + one-repair-attempt + final-answer-prompt structure: the model
    must write a single `jq ...` command line as free text (inside a fenced
    ```sh block), rather than filling in named JSON tool-call parameters.
    """
    manual = _shell_manual(condition)
    system = SHELL_SYSTEM_PROMPT_TEMPLATE.format(manual=manual)
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task_prompt}]
    outcome = RunOutcome()

    result = client.call(system=system, messages=messages)
    outcome.usage.add(result.usage)
    messages.append({"role": "assistant", "content": result.text})

    command = _extract_command(result.text)
    outcome.command_log.append(command)
    call_res = dispatch_jq_shell(vfs, condition, command)
    outcome.old_form_grammar = outcome.old_form_grammar or call_res.old_form_grammar

    if not call_res.ok:
        outcome.repaired = True
        repair_prompt = SHELL_REPAIR_PROMPT_TEMPLATE.format(error=call_res.error)
        messages.append({"role": "user", "content": repair_prompt})
        result2 = client.call(system=system, messages=messages)
        outcome.usage.add(result2.usage)
        messages.append({"role": "assistant", "content": result2.text})

        command2 = _extract_command(result2.text)
        outcome.command_log.append(command2)
        call_res = dispatch_jq_shell(vfs, condition, command2)
        outcome.old_form_grammar = outcome.old_form_grammar or call_res.old_form_grammar

        if not call_res.ok:
            outcome.timed_out = True
            outcome.final_error_tag = call_res.error_tag
            outcome.turns_used = 2
            outcome.final_answer = ""
            return outcome

    messages.append(
        {
            "role": "user",
            "content": f"Command output:\n{call_res.value}\n\n{SHELL_FINAL_ANSWER_PROMPT}",
        }
    )
    result3 = client.call(system=system, messages=messages)
    outcome.usage.add(result3.usage)
    outcome.final_answer = result3.text
    outcome.turns_used = 3 if outcome.repaired else 2
    return outcome


def run_jq_sequential(
    client: LLMClient,
    vfs: VirtualFS,
    condition: str,
    task_prompt: str,
    max_turns: int = 15,
) -> RunOutcome:
    tools = [_build_tool_schema(condition)]
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task_prompt}]
    outcome = RunOutcome()

    for turn in range(1, max_turns + 1):
        result = client.call(system=SYSTEM_PROMPT, messages=messages, tools=tools)
        outcome.usage.add(result.usage)

        if not result.tool_calls:
            outcome.final_answer = result.text
            outcome.turns_used = turn
            return outcome

        messages.append({"role": "assistant", "content": result.raw_content})

        tool_results_content = []
        for tc in result.tool_calls:
            # Bind by key name, not raw JSON key-emission order -- see
            # SKEPTIC_REVIEW.md #6 (same defect class as
            # harness_sequential.py, independently present here since this
            # module's sequential dispatch loop is self-contained). The
            # schema's own "required" list is always declared in the
            # correct positional order, so it is the single source of
            # truth for name->position mapping, rather than re-deriving it.
            key_order = tools[0]["input_schema"]["required"]
            args = [tc["input"][k] for k in key_order if k in tc["input"]]
            outcome.tool_calls_log.append({"name": tc["name"], "input": tc["input"]})
            call_res = dispatch_jq(vfs, condition, tc["name"], args)
            outcome.old_form_grammar = outcome.old_form_grammar or call_res.old_form_grammar
            if call_res.ok:
                content_str = str(call_res.value)
            else:
                content_str = f"ERROR: {call_res.error}"
                outcome.final_error_tag = call_res.error_tag
            tool_results_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": content_str,
                    "is_error": not call_res.ok,
                }
            )
        messages.append({"role": "user", "content": tool_results_content})

    outcome.timed_out = True
    outcome.turns_used = max_turns
    return outcome


def load_graph() -> Graph:
    with open(DATA_PATH) as f:
        return Graph.from_dict(json.load(f))


def run_one_cell(
    client_kwargs: Dict[str, Any],
    condition: str,
    task_id: str,
    seed: int,
    graph: Graph,
    interface: str = "sequential",
) -> Dict[str, Any]:
    client = make_client(**client_kwargs)
    vfs = VirtualFS(graph)
    task = get_task(task_id)
    oracle_value = task.oracle_fn(graph)

    t0 = time.time()
    try:
        if interface == "shell":
            outcome = run_jq_shell(client, vfs, condition, task.prompt)
        else:
            outcome = run_jq_sequential(client, vfs, condition, task.prompt)
        correct = (not outcome.timed_out) and score_answer(task, oracle_value, outcome.final_answer)
    except Exception as e:  # defensive: never let one bad run kill the matrix
        return {
            "interface": interface,
            "condition": condition,
            "task_id": task_id,
            "seed": seed,
            "correct": False,
            "timed_out": True,
            "error_tag": "harness_exception",
            "old_form_grammar": False,
            "exception": f"{type(e).__name__}: {e}",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "turns_used": 0,
            "wall_clock_s": time.time() - t0,
            "final_answer": "",
            "oracle_value": repr(oracle_value),
            "model": client.model,
            "tool_calls": [],
        }

    return {
        "interface": interface,
        "condition": condition,
        "task_id": task_id,
        "seed": seed,
        "correct": correct,
        "timed_out": outcome.timed_out,
        "error_tag": outcome.final_error_tag if (outcome.timed_out or not correct) else "",
        "old_form_grammar": outcome.old_form_grammar,
        "prompt_tokens": outcome.usage.prompt_tokens,
        "completion_tokens": outcome.usage.completion_tokens,
        "total_tokens": outcome.usage.total_tokens,
        "turns_used": outcome.turns_used,
        "wall_clock_s": time.time() - t0,
        "final_answer": outcome.final_answer,
        "oracle_value": repr(oracle_value),
        "model": client.model,
        "tool_calls": outcome.tool_calls_log,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--application-source", default="tool_name_experiment")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--conditions", default=None, help="comma-separated, default: both")
    ap.add_argument("--tasks", default=None, help="comma-separated task IDs, default: all 8 jq tasks")
    ap.add_argument("--seeds", default="1", help="comma-separated seed ints, default: 1")
    ap.add_argument("--interface", default="sequential", choices=["sequential", "shell"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.pilot:
        conditions = CONDITIONS
        task_ids = JQ_TASK_IDS[:3]
        seeds = [1]
        default_name = f"pilot_exp1_jq_{args.interface}.jsonl" if args.interface == "shell" else "pilot_exp1_jq.jsonl"
        out_path = Path(args.out) if args.out else RESULTS_DIR / default_name
    else:
        conditions = args.conditions.split(",") if args.conditions else CONDITIONS
        task_ids = args.tasks.split(",") if args.tasks else JQ_TASK_IDS
        seeds = [int(s) for s in args.seeds.split(",")]
        default_name = f"exp1_jq_{args.interface}.jsonl" if args.interface == "shell" else "exp1_jq.jsonl"
        out_path = Path(args.out) if args.out else RESULTS_DIR / default_name

    RESULTS_DIR.mkdir(exist_ok=True)
    client_kwargs: Dict[str, Any] = {"api_key": args.api_key}
    if args.model:
        client_kwargs["model"] = args.model
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    if args.application_source:
        client_kwargs["application_source"] = args.application_source

    graph = load_graph()

    total = len(conditions) * len(task_ids) * len(seeds)
    done = 0
    print(f"Running {total} cells -> {out_path}")

    with open(out_path, "w") as f:
        for seed in seeds:
            for condition in conditions:
                for task_id in task_ids:
                    row = run_one_cell(client_kwargs, condition, task_id, seed, graph, interface=args.interface)
                    f.write(json.dumps(row) + "\n")
                    f.flush()
                    done += 1
                    status = "OK " if row["correct"] else ("TIMEOUT" if row["timed_out"] else "WRONG")
                    print(
                        f"[{done}/{total}] {condition:8s} {task_id:6s} "
                        f"seed={seed} -> {status} ({row['total_tokens']} tok, "
                        f"{row['turns_used']} turns, {row['wall_clock_s']:.1f}s, "
                        f"old_form={row['old_form_grammar']})"
                    )

    print(f"\nDone. Results written to {out_path}")


if __name__ == "__main__":
    main()
