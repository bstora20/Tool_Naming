"""
Scoring: compares a model's free-text final answer against a Task's oracle
value. Deliberately lenient about formatting (whitespace, surrounding prose,
list ordering, case) since the research question is about tool-use success,
not output-formatting compliance -- but strict about the actual content.
"""

from __future__ import annotations

import re
from typing import Any, List

from tasks import Task


_BOOL_TRUE = {"yes", "true", "y", "1"}
_BOOL_FALSE = {"no", "false", "n", "0"}
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.=-]*")


def _normalize_token(s: str) -> str:
    return s.strip().strip(".,;:'\"()[]").strip().lower()


_PREFIX_RE = re.compile(r"^[a-z]+-")


def _token_prefix(tok: str) -> str:
    """
    Returns the leading alphabetic-prefix of a normalized token (e.g.
    "project-001" -> "project-", "pkg-113" -> "pkg-"). Used to distinguish
    different entity *kinds* that happen to share the "contains a digit"
    shape, so that e.g. a package name mentioned in prose while answering a
    projects-list question isn't mistaken for a list item.
    """
    m = _PREFIX_RE.match(tok)
    return m.group() if m else tok


def _extract_list_items(response: str, allowed_prefixes: set | None = None) -> List[str]:
    """
    Extract candidate list items from free-text prose. All current list-type
    oracle items (project-XXX, pkg-XXX, pkg==version) contain at least one
    digit, so this filters tokenized words down to digit-containing tokens --
    which strips out connective prose ("the", "dependencies", "are", "and")
    without needing a hand-maintained stopword list.

    If `allowed_prefixes` is given (the set of entity-kind prefixes present
    in the oracle answer, e.g. {"project-"}), tokens whose prefix isn't in
    that set are dropped. This prevents a different entity kind mentioned
    incidentally in the model's prose (e.g. "pkg-116" while listing the
    *projects* that depend on it) from being miscounted as a wrong/extra
    list item.
    """
    items = []
    for raw in _WORD_RE.findall(response):
        tok = _normalize_token(raw)
        if not tok or not any(c.isdigit() for c in tok):
            continue
        if allowed_prefixes is not None and _token_prefix(tok) not in allowed_prefixes:
            continue
        items.append(tok)
    return items


def _extract_int(response: str) -> int | None:
    m = re.search(r"-?\d+", response.replace(",", ""))
    return int(m.group()) if m else None


def _extract_bool(response: str) -> bool | None:
    tok = _normalize_token(response.split()[0]) if response.strip() else ""
    if tok in _BOOL_TRUE:
        return True
    if tok in _BOOL_FALSE:
        return False
    low = response.strip().lower()
    if low.startswith("yes"):
        return True
    if low.startswith("no"):
        return False
    return None


def score_answer(task: Task, oracle_value: Any, model_response: str) -> bool:
    """Return True iff model_response is judged correct against oracle_value."""
    if task.answer_type == "list":
        expected = {_normalize_token(x) for x in oracle_value}
        allowed_prefixes = {_token_prefix(x) for x in expected}
        got = set(_extract_list_items(model_response, allowed_prefixes=allowed_prefixes))
        return got == expected

    if task.answer_type == "int":
        got = _extract_int(model_response)
        return got is not None and got == int(oracle_value)

    if task.answer_type == "bool":
        got = _extract_bool(model_response)
        return got is not None and got == bool(oracle_value)

    if task.answer_type == "str":
        target = _normalize_token(str(oracle_value))
        if _normalize_token(model_response) == target:
            return True
        resp_norm = re.sub(r"\s+", " ", model_response.strip().lower())
        pattern = r"(?<![a-z0-9_])" + re.escape(target) + r"(?![a-z0-9_])"
        return re.search(pattern, resp_norm) is not None

    raise ValueError(f"unknown answer_type: {task.answer_type!r}")
