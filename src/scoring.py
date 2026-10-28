"""
Scoring: compares a model's free-text final answer against a Task's oracle
value. Deliberately lenient about formatting (whitespace, surrounding prose,
list ordering, case) since the research question is about tool-use success,
not output-formatting compliance -- but strict about the actual content.
"""

from __future__ import annotations

import ast
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


_ANSWER_MARKED_INT_RE = re.compile(
    r"(?:is|are|=|:|be|equals?)\s*-?\d+(?![a-zA-Z0-9])", re.IGNORECASE
)
_INT_RE = re.compile(r"-?\d+")


def _extract_int(response: str) -> int | None:
    """
    Prefer a number immediately preceded by answer-marking language (e.g.
    "there are 5 projects" / "count = 12" / "the answer is: 3"), taking the
    *last* such marked match if there are several (closest to a final
    answer). Falls back to the first number in the response if no
    answer-marked number is found, to preserve prior behavior on responses
    that are just a bare number.

    This is a heuristic hardening, not a guarantee: free-form model prose
    can still in principle state an irrelevant number using one of these
    marker words before the real answer. See SKEPTIC_REVIEW.md #4 for the
    known failure mode this defends against (oracle number not being the
    first number mentioned).
    """
    cleaned = response.replace(",", "")
    marked = list(_ANSWER_MARKED_INT_RE.finditer(cleaned))
    if marked:
        last = marked[-1].group()
        m = _INT_RE.search(last)
        if m:
            return int(m.group())
    m = _INT_RE.search(cleaned)
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
        # oracle_value may arrive as a Python repr() string (e.g. "'GPL-3.0'"
        # with literal quote characters) when read back from a results file
        # that logged `repr(oracle_value)` -- _normalize_token's quote-
        # stripping handles this, but be defensive here too in case a caller
        # passes a repr'd value directly. See SKEPTIC_REVIEW.md #2.
        target = _normalize_token(str(oracle_value))
        return _str_matches(target, model_response)

    if task.answer_type == "str_any":
        # The oracle is a *set* of equally-acceptable tokens (e.g. all
        # projects tied for "fewest dependencies") -- a response naming any
        # one of them is correct. See SKEPTIC_REVIEW.md #5. oracle_value may
        # arrive as an actual tuple/list, or as a repr()'d string read back
        # from a results file (e.g. "('project-000', 'project-007')"); in
        # the latter case we parse it back with ast.literal_eval. If the
        # oracle only ever had one acceptable value and was repr()'d as a
        # plain string (not a tuple/list literal), ast.literal_eval raises
        # and we fall back to treating the whole string as the single
        # candidate, matching plain "str" behavior.
        candidates: tuple
        if isinstance(oracle_value, (list, tuple, set)):
            candidates = tuple(oracle_value)
        elif isinstance(oracle_value, str):
            try:
                parsed = ast.literal_eval(oracle_value)
            except (ValueError, SyntaxError):
                parsed = oracle_value
            candidates = tuple(parsed) if isinstance(parsed, (list, tuple, set)) else (parsed,)
        else:
            candidates = (oracle_value,)
        return any(_str_matches(_normalize_token(str(c)), model_response) for c in candidates)

    raise ValueError(f"unknown answer_type: {task.answer_type!r}")


def _str_matches(target: str, model_response: str) -> bool:
    """
    Core str-comparison logic shared by answer_type "str" and "str_any":
    exact-normalized match, or a whole-word substring match guarded against
    pure negation (but allowing genuine self-correction). See
    SKEPTIC_REVIEW.md #4.
    """
    if _normalize_token(model_response) == target:
        return True
    resp_norm = re.sub(r"\s+", " ", model_response.strip().lower())
    pattern = r"(?<![a-z0-9_])" + re.escape(target) + r"(?![a-z0-9_])"
    match = re.search(pattern, resp_norm)
    if match is None:
        return False
    # Negation guard: reject if a negation word appears shortly before
    # the match with no intervening clause break, UNLESS the response
    # later affirms the correct value in its own right (self-correction
    # pattern, e.g. "not X... actually Y" where Y == target) -- see
    # SKEPTIC_REVIEW.md #4. We approximate "later affirms" by requiring
    # at least one occurrence of the target that is NOT itself preceded
    # by a negation word within the lookback window.
    negation_re = re.compile(r"\b(?:not|isn't|n't|never|no)\b")
    clause_break_re = re.compile(r"[.;:,]|\bbut\b|\bactually\b|\bhowever\b")
    for m in re.finditer(pattern, resp_norm):
        window_start = max(0, m.start() - 20)
        window = resp_norm[window_start:m.start()]
        last_break = max(
            (b.end() for b in clause_break_re.finditer(window)), default=0
        )
        pre_negation_zone = window[last_break:]
        if not negation_re.search(pre_negation_zone):
            return True
    return False
