"""
Experiment 5: replication of the Experiment 1/4/4b/4c "sticky idiom"
doc-robustness paradox on a SECOND, independent strong real-world idiom --
`sed` -- to test whether the pattern found for `jq` (interference only with
total absence of documentation; real parameter names fully suppress it;
explicit prose order-statements paradoxically perform WORSE than no
information at all) is specific to jq, or generalizes to other tools with an
equally strong, but structurally distinct, calling convention.

Real `sed` users have an equally strong, near-universal prior that the
SCRIPT/expression comes first and the FILE comes second (`sed 's/foo/bar/'
file.txt`) -- structurally analogous to jq's "filter before file" convention,
but a genuinely different idiom (substitution-script syntax rather than a
dot-path query), so this is not simply "jq again with a new name."

This module is SELF-CONTAINED, mirroring exp1_jq.py's architecture (not
wired into naming.py/dispatch.py's shared P1-P5 tables), but also folds in
exp4_doc_robustness.py's full doc-level matrix directly, rather than
splitting across two files, since the doc-level matrix is the central
question being tested here (there is no separate "just test jq/sed-real vs
swap with full docs" phase needed -- that is simply the doc_level="full"
slice of this same matrix).

Toy semantics deliberately reuse jq_filter's domain (meta.json top-level
fields: license/owner/last_updated/deprecated) via the new sed_filter
primitive (primitives.py P7), so the exact same 8 tasks/oracles from
tasks.py (JQ_TASK_IDS, reused verbatim here as SED_TASK_IDS) can be reused
unmodified -- same ground truth, same scoring, only the tool/idiom differs.

Two conditions, mirroring JQ-real/JQ-swap:

  SED-real  tool name "sed", documented arg order (script, path) --
            matches the real sed CLI convention exactly.
  SED-swap  tool name "sed" (same real idiom-triggering name), documented
            arg order (path, script) -- the near-miss: same strong-prior
            name, but the DOCUMENTED order is the opposite of what real sed
            users expect.

Doc levels (identical structure to exp4_doc_robustness.py), from least to
most in-context signal:
    none < {ordered_generic, named} < terse < full

Usage:
    python3 src/exp5_sed.py --api-key KEY [--pilot]
        [--doc-levels terse,none] [--interfaces sequential,shell]
        [--conditions SED-real,SED-swap] [--seeds 1,2,3]
        [--shell-max-repairs 1] [--out results/exp5_sed.jsonl]
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from data_gen import Graph  # noqa: E402
from vfs import VirtualFS  # noqa: E402
from primitives import sed_filter, PrimitiveError, _SED_SUPPORTED_FIELDS  # noqa: E402
from tasks import get_task  # noqa: E402
from scoring import score_answer  # noqa: E402
from llm_client import make_client, LLMClient, Usage  # noqa: E402

DATA_PATH = SRC_DIR.parent / "data" / "graph_seed42.json"
RESULTS_DIR = SRC_DIR.parent / "results"

# Reused verbatim from tasks.py (same 8 tasks exp1_jq.py uses): each one's
# oracle value is exactly a meta.json field, precisely sed_filter's domain.
SED_TASK_IDS = ["T1-02", "T1-03", "T1-04", "T1-06", "T2-03", "T2-04", "T2-07", "T2-08"]

TOOL_NAME = "sed"

CONDITIONS = ["SED-real", "SED-swap"]

_DOCUMENTED_ORDER = {
    "SED-real": ["script", "path"],
    "SED-swap": ["path", "script"],
}

DOC_LEVELS = ["full", "terse", "named", "ordered_generic", "none"]

_SUPPORTED_SCRIPTS_STR = ", ".join(f"'{s}'" for s in sorted(_SED_SUPPORTED_FIELDS))

_ORDER_SENTENCE_LABELS = {"path": "the file path", "script": "the sed script"}


def _order_sentence(condition: str, arg_names: List[str]) -> str:
    order = _DOCUMENTED_ORDER[condition]
    parts = [
        f"argument {i + 1} is {_ORDER_SENTENCE_LABELS[sem]}" for i, sem in enumerate(order)
    ]
    return "; ".join(parts) + "."


SEQUENTIAL_SYSTEM_PROMPT = (
    "You are an assistant that answers questions about a software project's "
    "dependency graph by calling the tool provided to you. Call the tool as "
    "needed to gather information, then give a final concise answer as plain "
    "text (not a tool call) once you have enough information. Do not guess -- "
    "only answer based on information you have retrieved via tool calls."
)

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


def _looks_like_script(s: Any) -> bool:
    return isinstance(s, str) and s.startswith("s/")


def _looks_like_path(s: Any) -> bool:
    return isinstance(s, str) and s.startswith("/")


# ---- doc-level manual rendering (sequential interface) ---------------------


def _full_manual_fn(condition: str) -> str:
    if condition == "SED-real":
        return (
            f"{TOOL_NAME}(script, path)\n"
            "Extract one top-level JSON field from meta.json file(s).\n"
            f"script must be one of {_SUPPORTED_SCRIPTS_STR}. path may be a\n"
            "single meta.json file or a directory (searched recursively for\n"
            "every meta.json underneath it).\n"
            f"Takes the SCRIPT FIRST and the PATH SECOND -- i.e.\n"
            f"{TOOL_NAME}(script, path), matching the standard sed command-line\n"
            f"convention `sed SCRIPT FILE`.\n"
            f"  {TOOL_NAME}('s/license//p', '/packages/pkg-113/meta.json')\n"
            "      -> [\"/packages/pkg-113/meta.json:MIT\"]\n"
            "Returns a list of \"path:value\" strings."
        )
    return (
        f"{TOOL_NAME}(path, script)\n"
        "Extract one top-level JSON field from meta.json file(s).\n"
        f"script must be one of {_SUPPORTED_SCRIPTS_STR}. path may be a\n"
        "single meta.json file or a directory (searched recursively for\n"
        "every meta.json underneath it).\n"
        f"In this environment {TOOL_NAME} takes the PATH FIRST and the SCRIPT\n"
        f"SECOND -- i.e. {TOOL_NAME}(path, script), NOT\n"
        f"{TOOL_NAME}(script, path).\n"
        f"  {TOOL_NAME}('/packages/pkg-113/meta.json', 's/license//p')\n"
        "      -> [\"/packages/pkg-113/meta.json:MIT\"]\n"
        "Returns a list of \"path:value\" strings."
    )


def _terse_manual_fn(condition: str) -> str:
    order = _DOCUMENTED_ORDER[condition]
    sig = f"{TOOL_NAME}(" + ", ".join(order) + ")"
    return f"{sig}\nExtracts a JSON field from meta.json file(s)."


def _named_manual_fn(condition: str) -> str:
    return ""


def _ordered_generic_manual_fn(condition: str) -> str:
    order = _DOCUMENTED_ORDER[condition]
    return _order_sentence(condition, order)


def _none_manual_fn(condition: str) -> str:
    return TOOL_NAME


_SEQ_MANUAL_FNS = {
    "full": _full_manual_fn,
    "terse": _terse_manual_fn,
    "named": _named_manual_fn,
    "ordered_generic": _ordered_generic_manual_fn,
    "none": _none_manual_fn,
}


# ---- doc-level manual rendering (shell interface) ---------------------------


def _full_shell_manual_fn(condition: str) -> str:
    order = _DOCUMENTED_ORDER[condition]
    usage = f"{TOOL_NAME} " + " ".join(f"<{arg}>" for arg in order)
    if condition == "SED-real":
        example = f"  {TOOL_NAME} 's/license//p' /packages/pkg-113/meta.json"
    else:
        example = f"  {TOOL_NAME} /packages/pkg-113/meta.json 's/license//p'"
    return (
        f"{usage}\n"
        "Extract one top-level JSON field from meta.json file(s).\n"
        f"script must be one of {_SUPPORTED_SCRIPTS_STR}. path may be a\n"
        "single meta.json file or a directory (searched recursively for\n"
        "every meta.json underneath it).\n"
        f"Argument order is: {', '.join(order)}.\n"
        f"{example}\n"
        "      -> /packages/pkg-113/meta.json:MIT\n"
        "Prints one \"path:value\" line per matching file."
    )


def _terse_shell_manual_fn(condition: str) -> str:
    order = _DOCUMENTED_ORDER[condition]
    usage = f"{TOOL_NAME} " + " ".join(f"<{arg}>" for arg in order)
    return f"{usage}\nExtracts a JSON field from meta.json file(s)."


def _named_shell_manual_fn(condition: str) -> str:
    order = _DOCUMENTED_ORDER[condition]
    return f"{TOOL_NAME} " + " ".join(f"<{arg}>" for arg in order)


def _ordered_generic_shell_manual_fn(condition: str) -> str:
    order = _DOCUMENTED_ORDER[condition]
    usage = f"{TOOL_NAME} " + " ".join(f"<arg{i + 1}>" for i in range(len(order)))
    return f"{usage}\n{_order_sentence(condition, order)}"


def _none_shell_manual_fn(condition: str) -> str:
    return f"{TOOL_NAME} - available command."


_SHELL_MANUAL_FNS = {
    "full": _full_shell_manual_fn,
    "terse": _terse_shell_manual_fn,
    "named": _named_shell_manual_fn,
    "ordered_generic": _ordered_generic_shell_manual_fn,
    "none": _none_shell_manual_fn,
}


def _build_tool_schema(condition: str, doc_level: str) -> Dict[str, Any]:
    """
    See exp4_doc_robustness.py's identical function for the rationale: for
    doc_level in {"none", "ordered_generic"}, parameter names must NOT be
    the real semantic names (script/path), since a JSON tool schema's
    `required` array necessarily lists parameter names in call order --
    using real names would leak the correct argument order through the
    schema regardless of description text. Generic arg1/arg2 names are used
    instead for both levels.
    """
    order = _DOCUMENTED_ORDER[condition]
    if doc_level in ("none", "ordered_generic"):
        generic_order = [f"arg{i + 1}" for i in range(len(order))]
        props = {arg: {"type": "string"} for arg in generic_order}
        description = _SEQ_MANUAL_FNS[doc_level](condition) if doc_level == "ordered_generic" else ""
        return {
            "name": TOOL_NAME,
            "description": description,
            "input_schema": {"type": "object", "properties": props, "required": generic_order},
        }
    props = {arg: {"type": "string"} for arg in order}
    manual = _SEQ_MANUAL_FNS[doc_level](condition)
    return {
        "name": TOOL_NAME,
        "description": manual,
        "input_schema": {"type": "object", "properties": props, "required": order},
    }


# Markers of REAL sed's full feature set (flags, addresses, chained commands,
# backreferences, transliteration, extended-regex metacharacters, global/
# in-place modifiers) -- none of which this harness's toy script vocabulary
# supports (it only accepts one of 4 fixed bare "s/FIELD//p" tokens; see
# primitives._SED_SUPPORTED_FIELDS). A command matching any of these is
# evidence the model reverted to its real-world sed prior for SCRIPT SYNTAX,
# a distinct failure mode from old_form_grammar's ARGUMENT ORDER check --
# both can fire independently, mirroring exp4_doc_robustness.py's
# detect_syntax_reversion for jq.
_SED_REAL_SYNTAX_MARKERS = [
    re.compile(r"^\s*-[a-zA-Z]"),       # leading flag, e.g. -i, -n, -e, -r
    re.compile(r"\s-[inrzE]\b"),        # flags appearing mid-command
    re.compile(r"-e\s+['\"]"),          # multiple -e script fragments
    re.compile(r"^\s*\d+[,\d]*\s*[sdp]"),  # leading address/line-range before a command
    re.compile(r"/[^/]*/\s*[,;]"),       # /pattern/ address before another command
    re.compile(r";\s*s/"),               # chained commands via semicolon
    re.compile(r"/g\b"),                 # global substitution flag
    re.compile(r"/[0-9]+\b"),            # occurrence-number flag, e.g. /2
    re.compile(r"\\\d"),                 # backreferences \1, \2, ...
    re.compile(r"\by/"),                 # transliterate command
    re.compile(r"&"),                    # whole-match backreference in replacement
    re.compile(r"\\\+|\\\?|\\\|"),       # extended-regex metacharacters
]


def detect_syntax_reversion(command: str) -> bool:
    """
    True if `command` (a raw shell command-line string, e.g.
    "sed -n '/license/p' file.json") contains any marker of real sed's full
    feature set, which this harness's toy sed does not support. Only
    meaningful for the shell interface, where the model must write raw
    script text itself.
    """
    return any(pat.search(command) for pat in _SED_REAL_SYNTAX_MARKERS)


@dataclass
class CallResult:
    ok: bool
    value: Any = None
    error: str = ""
    error_tag: str = ""
    old_form_grammar: bool = False  # SED-swap only: see dispatch_sed


def dispatch_sed(vfs: VirtualFS, condition: str, name: str, args: List[Any]) -> CallResult:
    """
    Minimal single-tool dispatcher for the sed-style primitive, mirroring
    exp1_jq.py's dispatch_jq but specialized to sed (name is always "sed"
    regardless of condition -- the manipulation is purely about documented
    ARGUMENT ORDER, not name familiarity).
    """
    if name != TOOL_NAME:
        return CallResult(ok=False, error=f"unknown tool {name!r}", error_tag="invalid_name")

    order = _DOCUMENTED_ORDER[condition]
    if len(args) != 2:
        return CallResult(ok=False, error=f"expected 2 args, got {len(args)}", error_tag="wrong_args")

    old_form = False
    if condition == "SED-swap":
        # Documented order is (path, script). old_form = model ignored the
        # documentation and reverted to the real sed idiom (script first,
        # path second) despite being told the opposite order.
        old_form = _looks_like_script(args[0]) and _looks_like_path(args[1])

    kwargs = dict(zip(order, args))
    script = kwargs.get("script")
    path = kwargs.get("path")

    try:
        value = sed_filter(vfs, script, path)
    except PrimitiveError as e:
        return CallResult(ok=False, error=str(e), error_tag="primitive_error", old_form_grammar=old_form)
    except TypeError as e:
        return CallResult(ok=False, error=str(e), error_tag="wrong_args", old_form_grammar=old_form)
    return CallResult(ok=True, value=value, old_form_grammar=old_form)


def dispatch_sed_shell(vfs: VirtualFS, condition: str, command_line: str) -> CallResult:
    """Shell-text analogue of dispatch_sed, mirroring dispatch_jq_shell."""
    try:
        tokens = shlex.split(command_line)
    except ValueError as e:
        return CallResult(ok=False, error=f"parse error: {e}", error_tag="wrong_args")
    if not tokens:
        return CallResult(ok=False, error="empty command", error_tag="invalid_name")

    name, args = tokens[0], tokens[1:]
    return dispatch_sed(vfs, condition, name, args)


@dataclass
class RunOutcome:
    final_answer: str = ""
    turns_used: int = 0
    usage: Usage = field(default_factory=Usage)
    timed_out: bool = False
    repaired: bool = False
    old_form_grammar: bool = False
    syntax_reversion: bool = False
    final_error_tag: str = ""
    command_log: List[str] = field(default_factory=list)
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)


def run_sed_sequential_doc(
    client: LLMClient,
    vfs: VirtualFS,
    condition: str,
    doc_level: str,
    task_prompt: str,
    max_turns: int = 15,
) -> RunOutcome:
    tools = [_build_tool_schema(condition, doc_level)]
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task_prompt}]
    outcome = RunOutcome()

    for turn in range(1, max_turns + 1):
        result = client.call(system=SEQUENTIAL_SYSTEM_PROMPT, messages=messages, tools=tools)
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
            # correct positional order (including the generic arg1/arg2
            # names used at doc_level in {none, ordered_generic}), so it is
            # the single source of truth for name->position mapping.
            key_order = tools[0]["input_schema"]["required"]
            args = [tc["input"][k] for k in key_order if k in tc["input"]]
            outcome.tool_calls_log.append({"name": tc["name"], "input": tc["input"]})
            call_res = dispatch_sed(vfs, condition, tc["name"], args)
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


def run_sed_shell_doc(
    client: LLMClient,
    vfs: VirtualFS,
    condition: str,
    doc_level: str,
    task_prompt: str,
    max_repairs: int = 1,
) -> RunOutcome:
    """max_repairs: number of repair/error-feedback attempts allowed after
    the initial command. See exp4_doc_robustness.py's run_jq_shell_doc for
    the rationale (floor-effect confound under degraded documentation)."""
    manual = _SHELL_MANUAL_FNS[doc_level](condition)
    system = SHELL_SYSTEM_PROMPT_TEMPLATE.format(manual=manual)
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task_prompt}]
    outcome = RunOutcome()

    result = client.call(system=system, messages=messages)
    outcome.usage.add(result.usage)
    messages.append({"role": "assistant", "content": result.text})

    command = _extract_command(result.text)
    outcome.command_log.append(command)
    outcome.syntax_reversion = outcome.syntax_reversion or detect_syntax_reversion(command)
    call_res = dispatch_sed_shell(vfs, condition, command)
    outcome.old_form_grammar = outcome.old_form_grammar or call_res.old_form_grammar

    attempts_used = 1
    while not call_res.ok and attempts_used <= max_repairs:
        outcome.repaired = True
        repair_prompt = SHELL_REPAIR_PROMPT_TEMPLATE.format(error=call_res.error)
        messages.append({"role": "user", "content": repair_prompt})
        result_n = client.call(system=system, messages=messages)
        outcome.usage.add(result_n.usage)
        messages.append({"role": "assistant", "content": result_n.text})

        command_n = _extract_command(result_n.text)
        outcome.command_log.append(command_n)
        outcome.syntax_reversion = outcome.syntax_reversion or detect_syntax_reversion(command_n)
        call_res = dispatch_sed_shell(vfs, condition, command_n)
        outcome.old_form_grammar = outcome.old_form_grammar or call_res.old_form_grammar
        attempts_used += 1

    if not call_res.ok:
        outcome.timed_out = True
        outcome.final_error_tag = call_res.error_tag
        outcome.turns_used = attempts_used
        outcome.final_answer = ""
        return outcome

    messages.append(
        {
            "role": "user",
            "content": f"Command output:\n{call_res.value}\n\n{SHELL_FINAL_ANSWER_PROMPT}",
        }
    )
    result_final = client.call(system=system, messages=messages)
    outcome.usage.add(result_final.usage)
    outcome.final_answer = result_final.text
    outcome.turns_used = attempts_used + 1
    return outcome


def load_graph() -> Graph:
    with open(DATA_PATH) as f:
        return Graph.from_dict(json.load(f))


def run_one_cell(
    client_kwargs: Dict[str, Any],
    condition: str,
    doc_level: str,
    interface: str,
    task_id: str,
    seed: int,
    graph: Graph,
    shell_max_repairs: int = 1,
) -> Dict[str, Any]:
    client = make_client(**client_kwargs)
    vfs = VirtualFS(graph)
    task = get_task(task_id)
    oracle_value = task.oracle_fn(graph)

    t0 = time.time()
    try:
        if interface == "shell":
            outcome = run_sed_shell_doc(
                client, vfs, condition, doc_level, task.prompt, max_repairs=shell_max_repairs
            )
        else:
            outcome = run_sed_sequential_doc(client, vfs, condition, doc_level, task.prompt)
        correct = (not outcome.timed_out) and score_answer(task, oracle_value, outcome.final_answer)
    except Exception as e:  # defensive: never let one bad run kill the matrix
        return {
            "interface": interface,
            "doc_level": doc_level,
            "condition": condition,
            "task_id": task_id,
            "seed": seed,
            "correct": False,
            "timed_out": True,
            "error_tag": "harness_exception",
            "old_form_grammar": False,
            "syntax_reversion": False,
            "exception": f"{type(e).__name__}: {e}",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "turns_used": 0,
            "wall_clock_s": time.time() - t0,
            "final_answer": "",
            "oracle_value": repr(oracle_value),
            "command_log": [],
            "model": client.model,
            "tool_calls": [],
        }

    return {
        "interface": interface,
        "doc_level": doc_level,
        "condition": condition,
        "task_id": task_id,
        "seed": seed,
        "correct": correct,
        "timed_out": outcome.timed_out,
        "error_tag": outcome.final_error_tag if (outcome.timed_out or not correct) else "",
        "old_form_grammar": outcome.old_form_grammar,
        "syntax_reversion": outcome.syntax_reversion,
        "prompt_tokens": outcome.usage.prompt_tokens,
        "completion_tokens": outcome.usage.completion_tokens,
        "total_tokens": outcome.usage.total_tokens,
        "turns_used": outcome.turns_used,
        "wall_clock_s": time.time() - t0,
        "final_answer": outcome.final_answer,
        "oracle_value": repr(oracle_value),
        "command_log": outcome.command_log,
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
    ap.add_argument("--doc-levels", default="terse,none", help="comma-separated subset of DOC_LEVELS")
    ap.add_argument("--interfaces", default="sequential,shell", help="comma-separated subset of: sequential,shell")
    ap.add_argument("--conditions", default=None, help="comma-separated, default: both")
    ap.add_argument("--tasks", default=None, help="comma-separated task IDs, default: all 8 sed tasks")
    ap.add_argument("--seeds", default="1", help="comma-separated seed ints, default: 1")
    ap.add_argument(
        "--shell-max-repairs",
        type=int,
        default=1,
        help="number of repair/error-feedback attempts allowed for the shell interface (default: 1)",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.pilot:
        conditions = CONDITIONS
        doc_levels = ["terse", "none"]
        interfaces = ["sequential", "shell"]
        task_ids = SED_TASK_IDS[:2]
        seeds = [1]
        out_path = Path(args.out) if args.out else RESULTS_DIR / "pilot_exp5_sed.jsonl"
    else:
        conditions = args.conditions.split(",") if args.conditions else CONDITIONS
        doc_levels = args.doc_levels.split(",")
        interfaces = args.interfaces.split(",")
        task_ids = args.tasks.split(",") if args.tasks else SED_TASK_IDS
        seeds = [int(s) for s in args.seeds.split(",")]
        out_path = Path(args.out) if args.out else RESULTS_DIR / "exp5_sed.jsonl"

    RESULTS_DIR.mkdir(exist_ok=True)
    client_kwargs: Dict[str, Any] = {"api_key": args.api_key}
    if args.model:
        client_kwargs["model"] = args.model
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    if args.application_source:
        client_kwargs["application_source"] = args.application_source

    graph = load_graph()

    total = len(conditions) * len(doc_levels) * len(interfaces) * len(task_ids) * len(seeds)
    done = 0
    print(f"Running {total} cells -> {out_path}")

    with open(out_path, "w") as f:
        for seed in seeds:
            for interface in interfaces:
                for doc_level in doc_levels:
                    for condition in conditions:
                        for task_id in task_ids:
                            row = run_one_cell(
                                client_kwargs,
                                condition,
                                doc_level,
                                interface,
                                task_id,
                                seed,
                                graph,
                                shell_max_repairs=args.shell_max_repairs,
                            )
                            f.write(json.dumps(row) + "\n")
                            f.flush()
                            done += 1
                            status = "OK " if row["correct"] else ("TIMEOUT" if row["timed_out"] else "WRONG")
                            print(
                                f"[{done}/{total}] {interface:10s} {doc_level:5s} {condition:8s} {task_id:6s} "
                                f"seed={seed} -> {status} ({row['total_tokens']} tok, "
                                f"{row['turns_used']} turns, {row['wall_clock_s']:.1f}s, "
                                f"old_form={row['old_form_grammar']})"
                            )

    print(f"\nDone. Results written to {out_path}")


if __name__ == "__main__":
    main()
