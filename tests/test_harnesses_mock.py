"""
End-to-end smoke tests for all three harnesses using a scripted mock LLM
client (no real API calls) -- validates control flow, prompt plumbing,
dispatch, and parsing logic before spending API budget on the real model.

Run with: python3 tests/test_harnesses_mock.py
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_gen import Graph  # noqa: E402
from vfs import VirtualFS  # noqa: E402
from dispatch import Dispatcher  # noqa: E402
from naming import build_specs, LOGICAL_IDS  # noqa: E402
from llm_client import LLMResult, Usage  # noqa: E402
from harness_sequential import run_sequential  # noqa: E402
from harness_scripted import run_scripted  # noqa: E402
from harness_shell import run_shell  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "graph_seed42.json"


def load_vfs() -> VirtualFS:
    with open(DATA_PATH) as f:
        return VirtualFS(Graph.from_dict(json.load(f)))


class MockClient:
    """Returns pre-scripted LLMResult objects in sequence, ignoring input."""

    def __init__(self, scripted_results: List[LLMResult]):
        self._results = list(scripted_results)
        self.calls = 0

    def call(self, system: str, messages: List[Dict[str, Any]], tools=None) -> LLMResult:
        self.calls += 1
        if not self._results:
            raise AssertionError("MockClient ran out of scripted results")
        return self._results.pop(0)


def _tool_use(name: str, input_: dict) -> LLMResult:
    return LLMResult(
        text="",
        tool_calls=[{"id": "call_1", "name": name, "input": input_}],
        stop_reason="tool_use",
        usage=Usage(prompt_tokens=100, completion_tokens=20),
        raw_content=[{"type": "tool_use", "id": "call_1", "name": name, "input": input_}],
    )


def _final_text(text: str) -> LLMResult:
    return LLMResult(
        text=text,
        tool_calls=[],
        stop_reason="end_turn",
        usage=Usage(prompt_tokens=50, completion_tokens=10),
        raw_content=[{"type": "text", "text": text}],
    )


# ---- sequential harness ----------------------------------------------------


def test_sequential_happy_path():
    vfs = load_vfs()
    condition = "A-full"
    dispatcher = Dispatcher(vfs, condition)
    ls_name = build_specs(condition)["P1"].name  # "ls"

    client = MockClient([
        _tool_use(ls_name, {"path": "/projects/project-000"}),
        _final_text("deps.txt"),
    ])
    outcome = run_sequential(client, dispatcher, condition, "list files in project-000")
    assert outcome.final_answer == "deps.txt"
    assert outcome.turns_used == 2
    assert not outcome.timed_out
    assert outcome.usage.total_tokens == (100 + 20) + (50 + 10)
    print("PASS: sequential harness happy path (1 tool call then final answer)")


def test_sequential_invalid_tool_name_logged():
    vfs = load_vfs()
    condition = "B"
    dispatcher = Dispatcher(vfs, condition)

    client = MockClient([
        _tool_use("totally_bogus", {"path": "/"}),
        _final_text("I don't know"),
    ])
    outcome = run_sequential(client, dispatcher, condition, "irrelevant")
    assert len(outcome.turn_log) == 1
    assert not outcome.turn_log[0].ok
    assert outcome.turn_log[0].error_tag == "invalid_name"
    print("PASS: sequential harness logs invalid_name error_tag correctly")


def test_sequential_binds_multiarg_tool_call_by_key_name_not_order():
    """
    Regression test for SKEPTIC_REVIEW.md #6: run_sequential() used to
    dispatch a tool call's JSON input dict via `list(tc["input"].values())`,
    relying entirely on the model's JSON key-emission order matching the
    schema's declared property order. A correctly-keyed, correctly-valued
    call whose keys are emitted in a different order (both are valid JSON/
    valid tool calls) must still be routed to the right positional slots.

    Uses P2 (find_by_pattern, real/documented order [root, pattern]) called
    with the keys deliberately reversed in the input dict -- {"pattern":
    ..., "root": ...} -- exactly mirroring the skeptic's own dispatcher-level
    repro. Before the fix this misrouted "*/meta.json" into the root slot
    and failed with "path must be absolute"; after the fix it must succeed.
    """
    vfs = load_vfs()
    condition = "A-full"
    dispatcher = Dispatcher(vfs, condition)
    find_name = build_specs(condition)["P2"].name  # "find"

    client = MockClient([
        _tool_use(find_name, {"pattern": "*/meta.json", "root": "/packages/pkg-113"}),
        _final_text("found it"),
    ])
    outcome = run_sequential(client, dispatcher, condition, "irrelevant")
    assert outcome.turn_log[0].ok, outcome.turn_log[0].error_tag
    assert outcome.final_answer == "found it"
    print("PASS: sequential harness binds multi-arg tool calls by key name, not JSON key order")


def test_sequential_timeout_when_max_turns_exceeded():
    vfs = load_vfs()
    condition = "A-full"
    dispatcher = Dispatcher(vfs, condition)
    ls_name = build_specs(condition)["P1"].name

    client = MockClient([_tool_use(ls_name, {"path": "/"}) for _ in range(5)])
    outcome = run_sequential(client, dispatcher, condition, "irrelevant", max_turns=3)
    assert outcome.timed_out
    assert outcome.turns_used == 3
    print("PASS: sequential harness times out correctly at max_turns")


# ---- scripted harness --------------------------------------------------------


def test_scripted_happy_path():
    vfs = load_vfs()
    condition = "B"
    dispatcher = Dispatcher(vfs, condition)

    script_resp = _final_text(
        '```python\nresult = list_entries("/projects/project-000")\nprint(result)\n```'
    )
    final_resp = _final_text("deps.txt")
    client = MockClient([script_resp, final_resp])

    outcome = run_scripted(client, dispatcher, condition, "irrelevant")
    assert not outcome.timed_out
    assert not outcome.repaired
    assert outcome.final_answer == "deps.txt"
    assert outcome.turns_used == 2
    print("PASS: scripted harness happy path (no repair needed)")


def test_scripted_repair_path():
    vfs = load_vfs()
    condition = "B"
    dispatcher = Dispatcher(vfs, condition)

    bad_script = _final_text("```python\nread_file(\"/nope\")\n```")
    good_script = _final_text(
        '```python\nresult = list_entries("/")\nprint(result)\n```'
    )
    final_resp = _final_text("packages, projects")
    client = MockClient([bad_script, good_script, final_resp])

    outcome = run_scripted(client, dispatcher, condition, "irrelevant")
    assert outcome.repaired
    assert not outcome.timed_out
    assert outcome.final_answer == "packages, projects"
    assert outcome.turns_used == 3
    print("PASS: scripted harness repair path works (bad script -> repaired -> answer)")


def test_scripted_double_failure_times_out():
    vfs = load_vfs()
    condition = "B"
    dispatcher = Dispatcher(vfs, condition)

    bad1 = _final_text("```python\nread_file(\"/nope\")\n```")
    bad2 = _final_text("```python\nread_file(\"/still/nope\")\n```")
    client = MockClient([bad1, bad2])

    outcome = run_scripted(client, dispatcher, condition, "irrelevant")
    assert outcome.timed_out
    assert outcome.final_error_tag == "primitive_error"
    print("PASS: scripted harness times out after repair also fails")


# ---- shell harness -----------------------------------------------------------


def test_shell_happy_path():
    vfs = load_vfs()
    condition = "A-full"
    dispatcher = Dispatcher(vfs, condition)

    cmd_resp = _final_text('```sh\nls /projects/project-000\n```')
    final_resp = _final_text("deps.txt")
    client = MockClient([cmd_resp, final_resp])

    outcome = run_shell(client, dispatcher, condition, "irrelevant")
    assert not outcome.timed_out
    assert not outcome.repaired
    assert outcome.final_answer == "deps.txt"
    print("PASS: shell harness happy path (no repair needed)")


def test_shell_pipeline_happy_path():
    vfs = load_vfs()
    condition = "A-full"
    dispatcher = Dispatcher(vfs, condition)

    cmd_resp = _final_text(
        '```sh\nfind / "*/meta.json" | grep MIT | wc\n```'
    )
    final_resp = _final_text("31")
    client = MockClient([cmd_resp, final_resp])

    outcome = run_shell(client, dispatcher, condition, "how many MIT packages?")
    assert outcome.final_answer == "31"
    print("PASS: shell harness handles a 3-stage pipeline correctly")


def test_shell_repair_path():
    vfs = load_vfs()
    condition = "B"
    dispatcher = Dispatcher(vfs, condition)

    bad_cmd = _final_text("```sh\nbogus_cmd /\n```")
    read_name = build_specs(condition)["P1"].name  # "list_entries"
    good_cmd = _final_text(f'```sh\n{read_name} /\n```')
    final_resp = _final_text("packages and projects")
    client = MockClient([bad_cmd, good_cmd, final_resp])

    outcome = run_shell(client, dispatcher, condition, "irrelevant")
    assert outcome.repaired
    assert not outcome.timed_out
    assert outcome.final_answer == "packages and projects"
    print("PASS: shell harness repair path works (bad command -> repaired -> answer)")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\nAll {len(tests)} harness smoke tests passed.")
