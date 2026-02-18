"""TOON / JSON formatting and exit-code mapping."""

from __future__ import annotations

import json
import sys
from typing import Any

from .client import ApiResponse


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_CLI_ERROR = 1
EXIT_AUTH_ERROR = 2
EXIT_4XX = 3
EXIT_5XX = 4
EXIT_NETWORK = 5


def exit_code_for_status(status: int | None) -> int:
    if status is None:
        return EXIT_NETWORK
    if 200 <= status < 300:
        return EXIT_SUCCESS
    if 400 <= status < 500:
        return EXIT_4XX
    if 500 <= status < 600:
        return EXIT_5XX
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# TOON encoder (built-in — no external dependency needed)
# ---------------------------------------------------------------------------

def _toon_value(value: Any) -> str:
    """Encode a single scalar value for TOON."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _is_uniform_list_of_dicts(data: Any) -> bool:
    """Check if data is a list of dicts with the same keys (→ tabular TOON)."""
    if not isinstance(data, list) or len(data) == 0:
        return False
    if not all(isinstance(item, dict) for item in data):
        return False
    keys = set(data[0].keys())
    return all(set(item.keys()) == keys for item in data)


def _toon_tabular(key: str, rows: list[dict[str, Any]]) -> str:
    """Encode a uniform list of dicts as TOON tabular format."""
    if not rows:
        return f"{key}[0]:\n"
    cols = list(rows[0].keys())
    header = f"{key}[{len(rows)}]{{{','.join(cols)}}}:"
    lines = [header]
    for row in rows:
        vals = [_toon_value(row.get(c)) for c in cols]
        lines.append(" " + ",".join(vals))
    return "\n".join(lines)


def _toon_object(data: dict[str, Any], indent: int = 0) -> str:
    """Encode a dict as TOON key-value pairs."""
    lines: list[str] = []
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_toon_object(value, indent + 1))
        elif _is_uniform_list_of_dicts(value):
            lines.append(f"{prefix}{_toon_tabular(key, value)}")
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}[{len(value)}]:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix} -")
                    lines.append(_toon_object(item, indent + 2))
                else:
                    lines.append(f"{prefix} {_toon_value(item)}")
        else:
            lines.append(f"{prefix}{key}: {_toon_value(value)}")
    return "\n".join(lines)


def encode_toon(response: ApiResponse) -> str:
    """Encode an API response as TOON format."""
    lines: list[str] = []
    lines.append(f"status: {response.status}")
    lines.append(f"elapsed_ms: {response.elapsed_ms}")

    # Headers — abbreviated to most useful ones
    ct = response.headers.get("content-type")
    if ct:
        lines.append("headers:")
        lines.append(f" content-type: {ct}")

    # Body
    body = response.body
    if isinstance(body, dict):
        lines.append("body:")
        lines.append(_toon_object(body, indent=1))
    elif _is_uniform_list_of_dicts(body):
        lines.append(_toon_tabular("body", body))
    elif isinstance(body, list):
        lines.append(f"body[{len(body)}]:")
        for item in body:
            if isinstance(item, dict):
                lines.append(" -")
                lines.append(_toon_object(item, indent=2))
            else:
                lines.append(f" {_toon_value(item)}")
    elif body is not None:
        lines.append(f"body: {_toon_value(body)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON envelope
# ---------------------------------------------------------------------------

def encode_json(response: ApiResponse) -> str:
    """Encode an API response as JSON envelope."""
    envelope = {
        "status": response.status,
        "headers": response.headers,
        "body": response.body,
        "elapsed_ms": response.elapsed_ms,
    }
    return json.dumps(envelope, indent=2, default=str)


# ---------------------------------------------------------------------------
# Error formatting (always JSON)
# ---------------------------------------------------------------------------

def format_error(code: str, message: str, status: int | None = None) -> str:
    return json.dumps({
        "error": code,
        "message": message,
        "status": status,
    })


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def print_response(response: ApiResponse, use_json: bool = False) -> int:
    """Print the formatted response and return the appropriate exit code."""
    if use_json:
        print(encode_json(response))
    else:
        print(encode_toon(response))
    return exit_code_for_status(response.status)


def print_error(code: str, message: str, status: int | None = None) -> None:
    print(format_error(code, message, status), file=sys.stderr)
