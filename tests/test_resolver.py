"""Tests for request resolution."""

from __future__ import annotations

import pytest

from cliforapi.resolver import ResolutionError, resolve
from cliforapi.spec import ApiSpec


class TestResolve:
    def test_simple_get(self, petstore_spec: ApiSpec):
        req = resolve("GET", "/pets", {}, None, petstore_spec)
        assert req.method == "GET"
        assert req.path == "/pets"

    def test_path_param_interpolation(self, petstore_spec: ApiSpec):
        req = resolve("GET", "/pets/{petId}", {"petId": "42"}, None, petstore_spec)
        assert req.path == "/pets/42"

    def test_query_params(self, petstore_spec: ApiSpec):
        req = resolve("GET", "/pets", {"limit": "10", "status": "available"}, None, petstore_spec)
        assert req.query_params["limit"] == "10"
        assert req.query_params["status"] == "available"

    def test_body_json(self, petstore_spec: ApiSpec):
        body = '{"name": "Fido"}'
        req = resolve("POST", "/pets", {}, body, petstore_spec)
        assert req.body == {"name": "Fido"}

    def test_body_plain_string(self, petstore_spec: ApiSpec):
        req = resolve("POST", "/pets", {}, "not json", petstore_spec)
        assert req.body == "not json"

    def test_missing_path_param_raises(self, petstore_spec: ApiSpec):
        with pytest.raises(ResolutionError, match="missing") as exc_info:
            resolve("GET", "/pets/{petId}", {}, None, petstore_spec)
        assert exc_info.value.code == "MISSING_PARAM"

    def test_no_match_raises(self, petstore_spec: ApiSpec):
        with pytest.raises(ResolutionError, match="No endpoint matches") as exc_info:
            resolve("GET", "/nonexistent", {}, None, petstore_spec)
        assert exc_info.value.code == "NO_MATCH"

    def test_positional_path_params(self, petstore_spec: ApiSpec):
        req = resolve("GET", "/pets/7", {}, None, petstore_spec)
        assert req.path == "/pets/7"

    def test_case_insensitive_param(self, petstore_spec: ApiSpec):
        req = resolve("GET", "/pets/{petId}", {"petid": "5"}, None, petstore_spec)
        assert req.path == "/pets/5"
