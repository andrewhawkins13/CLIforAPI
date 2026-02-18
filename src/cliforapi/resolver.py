"""Map CLI arguments to HTTP method, path, params, and body."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .matcher import MatchResult, match_route, _extract_param_names
from .spec import ApiSpec, OperationSpec


class ResolutionError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class ResolvedRequest:
    method: str
    path: str  # fully interpolated, e.g. /pet/123
    query_params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: dict | list | str | None = None
    operation: OperationSpec | None = None


def resolve(
    method: str,
    path: str,
    cli_params: dict[str, str],
    body_str: str | None,
    spec: ApiSpec,
) -> ResolvedRequest:
    """Resolve user CLI input into a concrete HTTP request description."""
    result: MatchResult = match_route(method, path, spec)

    if result.operation is None:
        suggestions = result.suggestions or []
        hint = ""
        if suggestions:
            hint = " Did you mean: " + ", ".join(suggestions) + "?"
        raise ResolutionError(
            "NO_MATCH",
            f"No endpoint matches '{method.upper()} {path}'.{hint}",
        )

    op = result.operation

    # Start with any positionally-extracted path params
    path_params: dict[str, str] = dict(result.extracted_path_params or {})
    query_params: dict[str, str] = {}
    header_params: dict[str, str] = {}

    # Classify CLI params according to the spec
    spec_params = {p.name.lower(): p for p in op.parameters}
    path_param_names = {n.lower() for n in _extract_param_names(op.path)}

    for key, value in cli_params.items():
        key_lower = key.lower()
        if key_lower in spec_params:
            p = spec_params[key_lower]
            if p.location == "path":
                path_params[p.name] = value
            elif p.location == "header":
                header_params[p.name] = value
            else:
                query_params[p.name] = value
        elif key_lower in path_param_names:
            # Accept case-insensitive path param match
            path_params[key] = value
        else:
            # Unknown param — pass as query param
            query_params[key] = value

    # Validate required path params
    for name in _extract_param_names(op.path):
        name_lower = name.lower()
        # Check case-insensitively
        matched = None
        for k, v in path_params.items():
            if k.lower() == name_lower:
                matched = (k, v)
                break
        if matched is None:
            raise ResolutionError(
                "MISSING_PARAM",
                f"Required path parameter '{name}' is missing. "
                f"Pass it with --{name} <value>",
            )

    # Interpolate path
    resolved_path = op.path
    for name in _extract_param_names(op.path):
        # Find the value case-insensitively
        for k, v in path_params.items():
            if k.lower() == name.lower():
                resolved_path = resolved_path.replace(f"{{{name}}}", v)
                break

    # Parse body
    body = None
    if body_str:
        try:
            body = json.loads(body_str)
        except json.JSONDecodeError:
            body = body_str

    return ResolvedRequest(
        method=op.method,
        path=resolved_path,
        query_params=query_params,
        headers=header_params,
        body=body,
        operation=op,
    )
