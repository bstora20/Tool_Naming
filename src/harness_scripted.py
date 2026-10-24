"""
Harness, row 2: scripted function calls (research_plan.md S1.2/S1.7).

Single-shot: the model is shown the active-condition manual (as plain text,
not native tool schemas -- there is no tool-calling API involved here, since
the model is writing a *script*, not invoking tools turn-by-turn) and asked
to write one Python script that calls the named functions directly. The
script is executed in script_sandbox.py; only its stdout is returned. On
error, exactly one repair turn is allowed (S1.7 step 3), after which the
model must give a final plain-text answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from dispatch import Dispatcher
from llm_client import LLMClient, Usage
from naming import render_full_manual
from script_sandbox import run_script

SYSTEM_PROMPT_TEMPLATE = (
    "You are an assistant that answers questions about a software project's "
    "dependency graph. You do NOT have interactive tools -- instead, you must "
    "write a single Python script that calls the functions described below, "
    "then prints the information you need. The script will be executed for "
    "you and you will see only what it prints to stdout.\n\n"
    "Available functions:\n{manual}\n\n"
    "Respond with exactly one fenced Python code block (```python ... ```) "
    "containing your script. Do not include any explanation outside the code "
    "block on this turn."
)

REPAIR_PROMPT_TEMPLATE = (
    "Your script failed with this error:\n{error}\n\n"
    "Here is anything it printed before failing:\n{output}\n\n"
    "Write a corrected single Python script in one fenced code block to fix "
    "this and get the information you need."
)

FINAL_ANSWER_PROMPT = (
    "Based on the output above, give your final answer to the original "
    "question as a short plain-text response (no code)."
)

_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _extract_code(text: str) -> str:
    m = _CODE_BLOCK_RE.search(text)
    return m.group(1).strip() if m else text.strip()


@dataclass
class RunOutcome:
    final_answer: str = ""
    turns_used: int = 0
    usage: Usage = field(default_factory=Usage)
    timed_out: bool = False
    repaired: bool = False
    final_error_tag: str = ""
    script_log: List[str] = field(default_factory=list)


def run_scripted(
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

    script = _extract_code(result.text)
    outcome.script_log.append(script)
    script_result = run_script(dispatcher, script)

    if not script_result.ok:
        outcome.repaired = True
        repair_prompt = REPAIR_PROMPT_TEMPLATE.format(
            error=script_result.error, output=script_result.output
        )
        messages.append({"role": "user", "content": repair_prompt})
        result2 = client.call(system=system, messages=messages)
        outcome.usage.add(result2.usage)
        messages.append({"role": "assistant", "content": result2.text})

        script2 = _extract_code(result2.text)
        outcome.script_log.append(script2)
        script_result = run_script(dispatcher, script2)

        if not script_result.ok:
            outcome.timed_out = True
            outcome.final_error_tag = script_result.error_tag
            outcome.turns_used = 2
            outcome.final_answer = ""
            return outcome

    messages.append(
        {
            "role": "user",
            "content": f"Script output:\n{script_result.output}\n\n{FINAL_ANSWER_PROMPT}",
        }
    )
    result3 = client.call(system=system, messages=messages)
    outcome.usage.add(result3.usage)
    outcome.final_answer = result3.text
    outcome.turns_used = 3 if outcome.repaired else 2
    return outcome
