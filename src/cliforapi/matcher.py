"""Fuzzy route-matching cascade for mapping user input to spec operations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .spec import ApiSpec, OperationSpec


@dataclass
class MatchResult:
    operation: OperationSpec | None = None
    extracted_path_params: dict[str, str] | None = None
    suggestions: list[str] | None = None


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

# Matches {param}, :param, <param>
_PARAM_RE = re.compile(r"\{(\w+)\}|:(\w+)|<(\w+)>")


def _normalize_path(path: str) -> str:
    """Normalize param styles to {name} and lowercase the path."""
    def _replace(m: re.Match) -> str:
        name = m.group(1) or m.group(2) or m.group(3)
        return f"{{{name.lower()}}}"
    return _PARAM_RE.sub(_replace, path).lower().rstrip("/")


def _extract_param_names(path: str) -> list[str]:
    """Extract ordered parameter names from a template path."""
    return [
        (m.group(1) or m.group(2) or m.group(3))
        for m in _PARAM_RE.finditer(path)
    ]


def _segments(path: str) -> list[str]:
    return [s for s in path.strip("/").split("/") if s]


# ---------------------------------------------------------------------------
# Levenshtein distance (simple impl, fine for short paths)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


# ---------------------------------------------------------------------------
# Singularisation (basic — just strip trailing 's'/'es')
# ---------------------------------------------------------------------------

def _singularize(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("ses") or word.endswith("xes") or word.endswith("zes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _fuzzy_path_equal(a_segs: list[str], b_segs: list[str]) -> bool:
    """Compare segments with singular/plural tolerance."""
    if len(a_segs) != len(b_segs):
        return False
    for sa, sb in zip(a_segs, b_segs):
        # If either is a param template, treat as match
        if sa.startswith("{") or sb.startswith("{"):
            continue
        if sa == sb:
            continue
        if _singularize(sa) == _singularize(sb):
            continue
        if _levenshtein(sa, sb) <= 1:
            continue
        return False
    return True


# ---------------------------------------------------------------------------
# Match strategies
# ---------------------------------------------------------------------------

def _exact_match(method: str, path: str, ops: list[OperationSpec]) -> OperationSpec | None:
    for op in ops:
        if op.method == method and op.path == path:
            return op
    return None


def _normalized_match(method: str, path: str, ops: list[OperationSpec]) -> OperationSpec | None:
    norm = _normalize_path(path)
    for op in ops:
        if op.method == method and _normalize_path(op.path) == norm:
            return op
    return None


def _positional_match(
    method: str, path: str, ops: list[OperationSpec]
) -> tuple[OperationSpec, dict[str, str]] | None:
    """Match /pet/1 against /pet/{petId} by detecting literal values in param slots."""
    user_segs = _segments(path)
    for op in ops:
        if op.method != method:
            continue
        op_segs = _segments(op.path)
        if len(user_segs) != len(op_segs):
            continue

        params: dict[str, str] = {}
        matched = True
        for u_seg, o_seg in zip(user_segs, op_segs):
            param_names = _extract_param_names(o_seg)
            if param_names:
                # This segment is a parameter — capture the value
                params[param_names[0]] = u_seg
            elif u_seg.lower() != o_seg.lower():
                matched = False
                break

        if matched and params:
            return op, params

    return None


def _fuzzy_match(method: str, path: str, ops: list[OperationSpec]) -> OperationSpec | None:
    """Singular/plural tolerance + minor typo tolerance."""
    user_segs = [s.lower() for s in _segments(path)]
    for op in ops:
        if op.method != method:
            continue
        op_segs = [s.lower() for s in _segments(_normalize_path(op.path))]
        if _fuzzy_path_equal(user_segs, op_segs):
            return op
    return None


def _closest_suggestions(method: str, path: str, ops: list[OperationSpec], n: int = 3) -> list[str]:
    """Return the n closest endpoint descriptions."""
    norm = _normalize_path(path)
    scored: list[tuple[int, str]] = []
    for op in ops:
        op_norm = _normalize_path(op.path)
        dist = _levenshtein(norm, op_norm)
        # Prefer same-method matches
        if op.method != method:
            dist += 3
        scored.append((dist, f"{op.method} {op.path}"))
    scored.sort(key=lambda t: t[0])
    return [desc for _, desc in scored[:n]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_route(method: str, path: str, spec: ApiSpec) -> MatchResult:
    """Try the matching cascade and return the best result.

    Cascade order: exact → normalized → positional → fuzzy → suggestions.
    """
    method = method.upper()
    ops = spec.operations

    # 1. Exact
    op = _exact_match(method, path, ops)
    if op:
        return MatchResult(operation=op)

    # 2. Normalized
    op = _normalized_match(method, path, ops)
    if op:
        return MatchResult(operation=op)

    # 3. Positional param detection
    pos = _positional_match(method, path, ops)
    if pos:
        return MatchResult(operation=pos[0], extracted_path_params=pos[1])

    # 4. Fuzzy
    op = _fuzzy_match(method, path, ops)
    if op:
        return MatchResult(operation=op)

    # 5. No match — suggest closest
    return MatchResult(suggestions=_closest_suggestions(method, path, ops))
