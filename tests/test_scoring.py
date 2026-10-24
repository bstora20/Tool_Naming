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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\nAll {len(tests)} scoring tests passed.")
