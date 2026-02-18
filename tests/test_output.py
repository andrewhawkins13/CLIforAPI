"""Tests for TOON/JSON output formatting and exit codes."""

from __future__ import annotations

import json

import pytest

from cliforapi.client import ApiResponse
from cliforapi.output import (
    EXIT_4XX,
    EXIT_5XX,
    EXIT_SUCCESS,
    encode_json,
    encode_toon,
    exit_code_for_status,
    format_error,
)


class TestExitCodes:
    @pytest.mark.parametrize("status,expected", [
        (200, EXIT_SUCCESS),
        (201, EXIT_SUCCESS),
        (204, EXIT_SUCCESS),
        (400, EXIT_4XX),
        (401, EXIT_4XX),
        (404, EXIT_4XX),
        (500, EXIT_5XX),
        (503, EXIT_5XX),
    ])
    def test_status_mapping(self, status: int, expected: int):
        assert exit_code_for_status(status) == expected

    def test_none_status(self):
        from cliforapi.output import EXIT_NETWORK
        assert exit_code_for_status(None) == EXIT_NETWORK


class TestToonEncoding:
    def test_simple_object_body(self):
        resp = ApiResponse(
            status=200,
            headers={"content-type": "application/json"},
            body={"id": 123, "name": "Alice"},
            elapsed_ms=42,
        )
        toon = encode_toon(resp)
        assert "status: 200" in toon
        assert "elapsed_ms: 42" in toon
        assert "id: 123" in toon
        assert "name: Alice" in toon

    def test_tabular_body(self):
        resp = ApiResponse(
            status=200,
            headers={"content-type": "application/json"},
            body=[
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            elapsed_ms=89,
        )
        toon = encode_toon(resp)
        assert "body[2]{id,name}:" in toon
        assert "1,Alice" in toon
        assert "2,Bob" in toon

    def test_string_body(self):
        resp = ApiResponse(
            status=200,
            headers={"content-type": "text/plain"},
            body="Hello World",
            elapsed_ms=10,
        )
        toon = encode_toon(resp)
        assert "body: Hello World" in toon

    def test_nested_object(self):
        resp = ApiResponse(
            status=200,
            headers={"content-type": "application/json"},
            body={"user": {"id": 1, "name": "Alice"}},
            elapsed_ms=50,
        )
        toon = encode_toon(resp)
        assert "user:" in toon
        assert "id: 1" in toon

    def test_null_and_bool_values(self):
        resp = ApiResponse(
            status=200,
            headers={"content-type": "application/json"},
            body={"active": True, "deleted": False, "note": None},
            elapsed_ms=5,
        )
        toon = encode_toon(resp)
        assert "active: true" in toon
        assert "deleted: false" in toon
        assert "note: null" in toon


class TestJsonEncoding:
    def test_json_envelope(self):
        resp = ApiResponse(
            status=200,
            headers={"content-type": "application/json"},
            body={"id": 1},
            elapsed_ms=50,
        )
        output = encode_json(resp)
        parsed = json.loads(output)
        assert parsed["status"] == 200
        assert parsed["body"] == {"id": 1}
        assert parsed["elapsed_ms"] == 50
        assert "content-type" in parsed["headers"]


class TestErrorFormat:
    def test_error_json(self):
        output = format_error("AUTH_MISSING", "No token", status=None)
        parsed = json.loads(output)
        assert parsed["error"] == "AUTH_MISSING"
        assert parsed["message"] == "No token"
        assert parsed["status"] is None
