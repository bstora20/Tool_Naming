"""
Harness, row 1: sequential function-calling (research_plan.md S1.2/S1.7).

Standard multi-turn tool-use loop using Anthropic's native tool-calling:
every tool result is returned to the model's context before it decides on
the next action. Tools are exposed under the active naming condition's
name/description (naming.py), and dispatched through the shared Dispatcher
(dispatch.py) so behavior is identical to the other two rows.

Stops when the model produces a final text answer with no further tool
calls, or after `max_turns` tool-calling turns (treated as a failure --
tagged "timeout" in the error taxonomy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from dispatch import Dispatcher, documented_arg_order
from llm_client import LLMClient, Usage
from naming import build_specs, LOGICAL_IDS

SYSTEM_PROMPT = (
    "You are an assistant that answers questions about a software project's "
    "dependency graph by calling the tools provided to you. Call tools as "
    "needed to gather information, then give a final concise answer as plain "
    "text (not a tool call) once you have enough information. Do not guess -- "
    "only answer based on information you have retrieved via tool calls."
)

_JSON_TYPE = {"path": "string", "root": "string", "pattern": "string"}

# Only P5's second positional arg (pattern) is optional across every
# condition's documented order; every other primitive requires all of its
# documented args. Keyed by logical id, not by argument name, so this stays
# correct even when documented_arg_order() returns condition D's swapped
# P2/P3 order (both of P2/P3's args are required either way).
_OPTIONAL_TRAILING_ARGS = {"P5": 1}


def _build_tool_schemas(condition: str) -> List[Dict[str, Any]]:
    """
    Build native Anthropic tool schemas for the active naming condition.

    Argument order/names come from dispatch.documented_arg_order(), the same
    single source of truth the Dispatcher itself uses to decide what order
    it will accept positional args in -- so under condition D, the schema
    shown to the model here now correctly matches D's documented swapped
    P2/P3 order instead of silently reverting to the real Unix order (the
    previous version of this function hardcoded its own non-D-aware
    arg_order/required dicts, duplicating dispatch.py's pre-D _ARG_ORDER).
    """
    specs = build_specs(condition)
    schemas = []
    for pid in LOGICAL_IDS:
        spec = specs[pid]
        order = documented_arg_order(condition, pid)
        n_optional = _OPTIONAL_TRAILING_ARGS.get(pid, 0)
        required_args = order[: len(order) - n_optional] if n_optional else order
        props = {arg: {"type": "string"} for arg in order}
        schemas.append(
            {
                "name": spec.name,
                "description": spec.manual or f"Primitive {spec.name}.",
                "input_schema": {
                    "type": "object",
                    "properties": props,
                    "required": required_args,
                },
            }
        )
    return schemas


@dataclass
class TurnLog:
    turn: int
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    error_tag: str = ""


@dataclass
class RunOutcome:
    final_answer: str = ""
    turns_used: int = 0
    usage: Usage = field(default_factory=Usage)
    timed_out: bool = False
    turn_log: List[TurnLog] = field(default_factory=list)
    old_form_grammar: bool = False  # condition D/D2 only: see dispatch.py
    delimiter_rule_violated: bool = False  # condition D2 only: see dispatch.py


def run_sequential(
    client: LLMClient,
    dispatcher: Dispatcher,
    condition: str,
    task_prompt: str,
    max_turns: int = 15,
) -> RunOutcome:
    tools = _build_tool_schemas(condition)
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
            # Bind the model's JSON tool-call input by *key name*, not by
            # raw dict/JSON key-emission order -- JSON objects are
            # semantically unordered, so a correctly-keyed, correctly-valued
            # call whose keys happen to be emitted in a different order than
            # input_schema.properties declared them would otherwise be
            # silently misrouted into the wrong positional slots. See
            # SKEPTIC_REVIEW.md #6. Falls back to raw .values() only when
            # the name doesn't resolve to a known primitive (in which case
            # dispatcher.call() below immediately returns an invalid_name
            # error without inspecting args).
            pid = dispatcher.pid_for_name(tc["name"])
            if pid is not None:
                arg_order = documented_arg_order(condition, pid)
                args = [tc["input"][k] for k in arg_order if k in tc["input"]]
            else:
                args = list(tc["input"].values())
            call_res = dispatcher.call(tc["name"], args)
            outcome.old_form_grammar = outcome.old_form_grammar or call_res.old_form_grammar
            outcome.delimiter_rule_violated = outcome.delimiter_rule_violated or call_res.delimiter_rule_violated
            log = TurnLog(turn=turn, tool_name=tc["name"], tool_args=tc["input"])
            if call_res.ok:
                content_str = str(call_res.value)
            else:
                content_str = f"ERROR: {call_res.error}"
                log.ok = False
                log.error_tag = call_res.error_tag
            outcome.turn_log.append(log)
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
