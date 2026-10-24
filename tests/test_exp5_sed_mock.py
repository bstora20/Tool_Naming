"""
End-to-end smoke tests for exp5_sed.py's sequential and shell doc-robustness
harnesses, using a scripted mock LLM client (no real API calls) -- validates
control flow, doc-level manual rendering, schema leak-prevention, dispatch
(including old_form_grammar detection), and syntax-reversion detection before
spending API budget on the real model. Mirrors tests/test_harnesses_mock.py's
pattern.

Run with: python3 tests/test_exp5_sed_mock.py
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_gen import Graph  # noqa: E402
from vfs import VirtualFS  # noqa: E402
from llm_client import LLMResult, Usage  # noqa: E402
from exp5_sed import (  # noqa: E402
    run_sed_sequential_doc,
    run_sed_shell_doc,
    dispatch_sed,
    dispatch_sed_shell,
    _build_tool_schema,
    detect_syntax_reversion,
)

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


# ---- dispatch_sed: argument order + old_form_grammar detection ------------


def test_dispatch_sed_real_correct_order():
    vfs = load_vfs()
    res = dispatch_sed(vfs, "SED-real", "sed", ["s/license//p", "/packages/pkg-113/meta.json"])
    assert res.ok
    assert res.value == ["/packages/pkg-113/meta.json:GPL-3.0"]
    assert not res.old_form_grammar
    print("PASS: dispatch_sed SED-real with documented (script, path) order succeeds")


def test_dispatch_sed_swap_correct_order_no_old_form():
    vfs = load_vfs()
    res = dispatch_sed(vfs, "SED-swap", "sed", ["/packages/pkg-113/meta.json", "s/license//p"])
    assert res.ok
    assert res.value == ["/packages/pkg-113/meta.json:GPL-3.0"]
    assert not res.old_form_grammar
    print("PASS: dispatch_sed SED-swap with documented (path, script) order succeeds, no old_form flag")


def test_dispatch_sed_swap_reversion_detected():
    vfs = load_vfs()
    res = dispatch_sed(vfs, "SED-swap", "sed", ["s/license//p", "/packages/pkg-113/meta.json"])
    assert res.old_form_grammar
    print("PASS: dispatch_sed SED-swap with real-sed (script, path) order flags old_form_grammar")


def test_dispatch_sed_unsupported_script_errors():
    vfs = load_vfs()
    res = dispatch_sed(vfs, "SED-real", "sed", ["s/foo/bar/p", "/packages/pkg-113/meta.json"])
    assert not res.ok
    assert res.error_tag == "primitive_error"
    print("PASS: dispatch_sed with unsupported script returns primitive_error")


def test_dispatch_sed_shell_parses_quoted_script():
    vfs = load_vfs()
    res = dispatch_sed_shell(vfs, "SED-real", "sed 's/license//p' /packages/pkg-113/meta.json")
    assert res.ok
    assert res.value == ["/packages/pkg-113/meta.json:GPL-3.0"]
    print("PASS: dispatch_sed_shell parses quoted script + path correctly")


# ---- schema leak-prevention across doc levels -----------------------------


def test_schema_none_and_ordered_generic_use_generic_names():
    for doc_level in ("none", "ordered_generic"):
        schema = _build_tool_schema("SED-swap", doc_level)
        assert schema["input_schema"]["required"] == ["arg1", "arg2"], doc_level
        assert "path" not in schema["input_schema"]["properties"]
        assert "script" not in schema["input_schema"]["properties"]
    print("PASS: none/ordered_generic schemas use generic arg1/arg2 names (no order leak)")


def test_schema_named_and_terse_use_real_names_in_documented_order():
    for doc_level in ("named", "terse", "full"):
        schema = _build_tool_schema("SED-swap", doc_level)
        assert schema["input_schema"]["required"] == ["path", "script"], doc_level
    for doc_level in ("named", "terse", "full"):
        schema = _build_tool_schema("SED-real", doc_level)
        assert schema["input_schema"]["required"] == ["script", "path"], doc_level
    print("PASS: named/terse/full schemas use real names in each condition's documented order")


def test_schema_ordered_generic_description_states_order():
    schema = _build_tool_schema("SED-swap", "ordered_generic")
    assert "argument 1 is the file path" in schema["description"]
    assert "argument 2 is the sed script" in schema["description"]
    print("PASS: ordered_generic description states documented order in prose, using generic slots")


# ---- syntax-reversion detector --------------------------------------------


def test_syntax_reversion_detects_flags_and_global():
    assert detect_syntax_reversion("sed -n '/license/p' /packages/pkg-113/meta.json")
    assert detect_syntax_reversion("sed 's/license/x/g' /packages/pkg-113/meta.json")
    print("PASS: detect_syntax_reversion flags real-sed flags and global substitution")


def test_syntax_reversion_allows_toy_form():
    assert not detect_syntax_reversion("sed 's/license//p' /packages/pkg-113/meta.json")
    print("PASS: detect_syntax_reversion does not flag the toy-supported script form")


# ---- sequential doc-robustness harness ------------------------------------


def test_sequential_happy_path_named_real_order():
    vfs = load_vfs()
    client = MockClient([
        _tool_use("sed", {"script": "s/license//p", "path": "/packages/pkg-113/meta.json"}),
        _final_text("GPL-3.0"),
    ])
    outcome = run_sed_sequential_doc(client, vfs, "SED-real", "named", "what license does pkg-113 use?")
    assert outcome.final_answer == "GPL-3.0"
    assert not outcome.timed_out
    assert not outcome.old_form_grammar
    print("PASS: sequential sed harness happy path (named doc_level, SED-real)")


def test_sequential_swap_none_doc_level_reversion_flagged():
    vfs = load_vfs()
    # Under doc_level="none", schema uses generic arg1/arg2 -- model (mock)
    # supplies them in real-sed (script, path) order despite SED-swap's
    # documented (path, script) order; dispatch should flag old_form_grammar.
    client = MockClient([
        _tool_use("sed", {"arg1": "s/license//p", "arg2": "/packages/pkg-113/meta.json"}),
        _final_text("GPL-3.0"),
    ])
    outcome = run_sed_sequential_doc(client, vfs, "SED-swap", "none", "what license does pkg-113 use?")
    assert outcome.old_form_grammar
    print("PASS: sequential sed harness flags old_form_grammar under SED-swap/none when model reverts")


def test_sequential_timeout_when_max_turns_exceeded():
    vfs = load_vfs()
    client = MockClient([
        _tool_use("sed", {"script": "s/license//p", "path": "/packages/pkg-113/meta.json"})
        for _ in range(5)
    ])
    outcome = run_sed_sequential_doc(
        client, vfs, "SED-real", "named", "irrelevant", max_turns=3
    )
    assert outcome.timed_out
    assert outcome.turns_used == 3
    print("PASS: sequential sed harness times out correctly at max_turns")


# ---- shell doc-robustness harness ------------------------------------------


def test_shell_happy_path_no_repair():
    vfs = load_vfs()
    cmd_resp = _final_text("```sh\nsed 's/license//p' /packages/pkg-113/meta.json\n```")
    final_resp = _final_text("GPL-3.0")
    client = MockClient([cmd_resp, final_resp])

    outcome = run_sed_shell_doc(client, vfs, "SED-real", "full", "what license does pkg-113 use?")
    assert not outcome.timed_out
    assert not outcome.repaired
    assert outcome.final_answer == "GPL-3.0"
    assert not outcome.syntax_reversion
    print("PASS: shell sed harness happy path (no repair needed)")


def test_shell_repair_path():
    vfs = load_vfs()
    bad_cmd = _final_text("```sh\nsed -n '/license/p' /packages/pkg-113/meta.json\n```")
    good_cmd = _final_text("```sh\nsed 's/license//p' /packages/pkg-113/meta.json\n```")
    final_resp = _final_text("GPL-3.0")
    client = MockClient([bad_cmd, good_cmd, final_resp])

    outcome = run_sed_shell_doc(
        client, vfs, "SED-real", "full", "what license does pkg-113 use?", max_repairs=1
    )
    assert outcome.repaired
    assert not outcome.timed_out
    assert outcome.final_answer == "GPL-3.0"
    assert outcome.syntax_reversion  # first (failed) attempt used a real-sed flag
    print("PASS: shell sed harness repair path works (bad -> repaired -> answer), syntax_reversion flagged")


def test_shell_swap_reversion_flagged():
    vfs = load_vfs()
    # SED-swap documents (path, script); model (mock) writes real-sed order
    # (script, path) on the command line -- old_form_grammar should fire.
    cmd_resp = _final_text("```sh\nsed 's/license//p' /packages/pkg-113/meta.json\n```")
    final_resp = _final_text("GPL-3.0")
    client = MockClient([cmd_resp, final_resp])

    outcome = run_sed_shell_doc(client, vfs, "SED-swap", "none", "what license does pkg-113 use?")
    assert outcome.old_form_grammar
    print("PASS: shell sed harness flags old_form_grammar under SED-swap when model writes real-sed order")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\nAll {len(tests)} exp5_sed mock tests passed.")
