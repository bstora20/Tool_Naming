"""
Sanity checks for scoring.score_answer against representative free-text
model responses, run against real oracle values from graph_seed42.json.

Run with: python3 tests/test_scoring.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_gen import Graph  # noqa: E402
from tasks import ALL_TASKS, get_task  # noqa: E402
from scoring import score_answer  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "graph_seed42.json"


def load_graph() -> Graph:
    with open(DATA_PATH) as f:
        return Graph.from_dict(json.load(f))


def test_all_tasks_compute_without_error():
    g = load_graph()
    for t in ALL_TASKS:
        t.oracle_fn(g)
    print(f"PASS: all {len(ALL_TASKS)} tasks compute an oracle value without error")


def test_list_scoring_accepts_prose_and_reordering():
    g = load_graph()
    t = get_task("T1-01")
    val = t.oracle_fn(g)
    assert score_answer(t, val, "pkg-113==3.0.0, pkg-088==2.0.0, pkg-076==3.0.0")
    assert score_answer(
        t, val, "The dependencies are: pkg-076==3.0.0 and pkg-088==2.0.0 and pkg-113==3.0.0."
    )
    assert not score_answer(t, val, "pkg-113==3.0.0")
    print("PASS: list scoring tolerates reordering/prose, rejects incomplete answers")


def test_int_scoring_extracts_number_from_prose():
    g = load_graph()
    t = get_task("T2-02")
    val = t.oracle_fn(g)
    assert score_answer(t, val, "There are 5 projects.")
    assert not score_answer(t, val, "4")
    print("PASS: int scoring extracts number from prose, rejects wrong number")


def test_int_scoring_prefers_answer_marked_number_over_earlier_number():
    """
    Regression test for SKEPTIC_REVIEW.md #4: _extract_int used to take the
    *first* regex-matched number in the response, which would silently
    misscore a correct answer if an earlier, irrelevant number appeared
    first (e.g. restating an input count before giving the final count).
    """
    g = load_graph()
    t = get_task("T2-02")
    val = t.oracle_fn(g)
    assert score_answer(t, val, f"Out of 12 total entries checked, the answer is {val}.")
    assert not score_answer(t, val, f"Out of {val} total entries checked, the answer is 99.")
    print("PASS: int scoring prefers an answer-marked number over an earlier unrelated one")


def test_bool_scoring_handles_yes_no_prose():
    g = load_graph()
    t = get_task("T3-02")
    val = t.oracle_fn(g)
    assert score_answer(t, val, "Yes, it does.")
    assert not score_answer(t, val, "No")
    print("PASS: bool scoring handles yes/no prose correctly")


def test_str_scoring_is_case_insensitive_but_requires_match():
    g = load_graph()
    t = get_task("T1-02")
    val = t.oracle_fn(g)
    assert score_answer(t, val, "gpl-3.0")
    assert score_answer(t, val, val)
    assert not score_answer(t, val, "MIT")
    print("PASS: str scoring is case-insensitive, rejects wrong value")


def test_str_scoring_handles_repr_quoted_oracle_value():
    """
    Regression test for SKEPTIC_REVIEW.md #2: result files log
    `repr(oracle_value)` (e.g. "'GPL-3.0'" with literal quote characters).
    Passing that repr'd string straight back into score_answer must still
    match a correct free-text answer.
    """
    g = load_graph()
    t = get_task("T1-02")
    val = t.oracle_fn(g)
    repr_val = repr(val)
    assert score_answer(t, repr_val, f"pkg-113 uses the {val} license.")
    assert score_answer(t, repr_val, val)
    print("PASS: str scoring matches correctly even when oracle_value is repr()-quoted")


def test_str_scoring_rejects_pure_negation_but_allows_self_correction():
    """
    Regression test for SKEPTIC_REVIEW.md #4: score_answer used to return
    True on a response that only mentions the correct value to negate it
    (e.g. "it's definitely not GPL-3.0"). It should still accept legitimate
    self-corrections where the model states the correct value affirmatively
    elsewhere in the same response.
    """
    g = load_graph()
    t = get_task("T1-02")
    val = t.oracle_fn(g)
    assert not score_answer(
        t, val, f"The license is definitely not {val}; it's actually Apache-2.0."
    )
    assert score_answer(t, val, f"Not GPL-2.0... actually it is {val}.")
    print("PASS: str scoring rejects pure negation, allows genuine self-correction")


def test_str_any_scoring_accepts_any_tied_oracle_candidate():
    """
    Regression test for SKEPTIC_REVIEW.md #5: T2-06's "fewest direct
    dependencies" oracle has an 11-way tie in graph_seed42.json. answer_type
    "str_any" must accept a response naming *any* one of the tied projects,
    not just the first one returned by the oracle_fn, and must also handle
    the oracle_value arriving as a repr()'d tuple string (as stored in
    results/*.jsonl) rather than a live tuple object.
    """
    g = load_graph()
    t = get_task("T2-06")
    val = t.oracle_fn(g)
    assert isinstance(val, tuple) and len(val) > 1, "expected a multi-way tie in the fixture graph"
    assert score_answer(t, val, f"The fewest is 3 direct dependencies: {val[0]}.")
    assert score_answer(t, val, f"The fewest is 3 direct dependencies: {val[-1]}.")
    assert not score_answer(t, val, "project-999")
    repr_val = repr(val)
    assert score_answer(t, repr_val, f"The fewest is 3 direct dependencies: {val[0]}.")
    assert score_answer(t, repr_val, f"The fewest is 3 direct dependencies: {val[-1]}.")
    assert not score_answer(t, repr_val, "project-999")
    print("PASS: str_any scoring accepts any tied oracle candidate, incl. repr()'d tuple")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\nAll {len(tests)} scoring tests passed.")
