"""
Harness, row 3: shell over virtual file system (research_plan.md
S1.2/S1.7/S1.9).

Single-shot, like row 2, but the model is told it has a Unix-like shell and
must write one command or pipeline (ls/find/grep/cat/wc under whatever names
are active for this condition) rather than a scripting-call convention. This
is the row that is both single-shot *and* grammar-familiar, isolating the
grammar-familiarity effect from turn-structure (S1.9: row 2 vs. row 3).

Execution goes through shell_sim.run_pipeline, which supports the subset of
pipe/filter/count semantics needed for this primitive set. One repair turn
is allowed on error, mirroring harness_scripted.py and the shell row's
protocol in S1.7 step 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from dispatch import Dispatcher
from llm_client import LLMClient, Usage
from naming import render_full_manual
from shell_sim import run_pipeline

SYSTEM_PROMPT_TEMPLATE = (
    "You are an assistant that answers questions about a software project's "
    "dependency graph via a Unix-like shell over a virtual file system. You "
    "do NOT have interactive tools -- instead, you must write a single shell "
    "command or pipeline using the commands described below, then see only "
    "its output (stdout/stderr).\n\n"
    "Available commands:\n{manual}\n\n"
    "You may pipe output from one command into grep-like or wc-like commands "
    "(e.g. `find / \"*/meta.json\" | grep MIT | wc`) using '|'. "
    "Respond with exactly one fenced shell code block (```sh ... ```) "
    "containing your command/pipeline. Do not include any explanation "
    "outside the code block on this turn."
)

REPAIR_PROMPT_TEMPLATE = (
    "Your command failed with this error:\n{error}\n\n"
    "Write a corrected single command/pipeline in one fenced code block to "
    "fix this and get the information you need."
)

FINAL_ANSWER_PROMPT = (
    "Based on the output above, give your final answer to the original "
    "question as a short plain-text response (no code)."
)

import re

_CODE_BLOCK_RE = re.compile(r"```(?:sh|bash|shell)?\s*\n(.*?)```", re.DOTALL)


def _extract_command(text: str) -> str:
    m = _CODE_BLOCK_RE.search(text)
    raw = m.group(1).strip() if m else text.strip()
    return raw.splitlines()[0].strip() if raw else raw


@dataclass
class RunOutcome:
    final_answer: str = ""
    turns_used: int = 0
    usage: Usage = field(default_factory=Usage)
    timed_out: bool = False
    repaired: bool = False
    final_error_tag: str = ""
    command_log: List[str] = field(default_factory=list)
    old_form_grammar: bool = False  # condition D/D2 only: see dispatch.py
    delimiter_rule_violated: bool = False  # condition D2 only: see dispatch.py


def run_shell(
    client: LLMClient,
    dispatcher: Dispatcher,
    condition: str,
    task_prompt: str,
) -> RunOutcome:
    manual = render_full_manual(condition)
    system = SYSTEM_PROMPT_TEMPLATE.format(manual=manual)
    messages = [{"role": "user", "content": task_prompt}]
    outcome = RunOutcome()

    result = client.call(system=system, messages=messages)
    outcome.usage.add(result.usage)
    messages.append({"role": "assistant", "content": result.text})

    command = _extract_command(result.text)
    outcome.command_log.append(command)
    shell_result = run_pipeline(dispatcher, command)
    outcome.old_form_grammar = outcome.old_form_grammar or shell_result.old_form_grammar
    outcome.delimiter_rule_violated = outcome.delimiter_rule_violated or shell_result.delimiter_rule_violated

    if not shell_result.ok:
        outcome.repaired = True
        repair_prompt = REPAIR_PROMPT_TEMPLATE.format(error=shell_result.error)
        messages.append({"role": "user", "content": repair_prompt})
        result2 = client.call(system=system, messages=messages)
        outcome.usage.add(result2.usage)
        messages.append({"role": "assistant", "content": result2.text})

        command2 = _extract_command(result2.text)
        outcome.command_log.append(command2)
        shell_result = run_pipeline(dispatcher, command2)
        outcome.old_form_grammar = outcome.old_form_grammar or shell_result.old_form_grammar
        outcome.delimiter_rule_violated = outcome.delimiter_rule_violated or shell_result.delimiter_rule_violated

        if not shell_result.ok:
            outcome.timed_out = True
            outcome.final_error_tag = shell_result.error_tag
            outcome.turns_used = 2
            outcome.final_answer = ""
            return outcome

    messages.append(
        {
            "role": "user",
            "content": f"Command output:\n{shell_result.output}\n\n{FINAL_ANSWER_PROMPT}",
        }
    )
    result3 = client.call(system=system, messages=messages)
    outcome.usage.add(result3.usage)
    outcome.final_answer = result3.text
    outcome.turns_used = 3 if outcome.repaired else 2
    return outcome
