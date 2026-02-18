"""TOON / JSON formatting and exit-code mapping."""

from __future__ import annotations

import json
import sys
from typing import Any

import toons

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
# TOON encoder (via `toons` — Rust-based, spec-compliant)
# ---------------------------------------------------------------------------

def _build_envelope(response: ApiResponse) -> dict[str, Any]:
    """Build the response envelope dict for encoding."""
    envelope: dict[str, Any] = {
        "status": response.status,
        "elapsed_ms": response.elapsed_ms,
    }
    ct = response.headers.get("content-type")
    if ct:
        envelope["headers"] = {"content-type": ct}
    if response.body is not None:
        envelope["body"] = response.body
    return envelope


def encode_toon(response: ApiResponse) -> str:
    """Encode an API response as TOON format."""
    return toons.dumps(_build_envelope(response))


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
