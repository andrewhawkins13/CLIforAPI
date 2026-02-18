"""Tests for fuzzy route matching."""

from __future__ import annotations

import pytest

from cliforapi.matcher import match_route
from cliforapi.spec import ApiSpec


class TestExactMatch:
    def test_exact_method_and_path(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/pets", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets"
        assert result.operation.method == "GET"

    def test_exact_with_template(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/pets/{petId}", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets/{petId}"


class TestNormalizedMatch:
    def test_colon_param_style(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/pets/:petId", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets/{petId}"

    def test_angle_bracket_param(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/pets/<petId>", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets/{petId}"

    def test_case_insensitive(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/Pets/{petId}", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets/{petId}"


class TestPositionalMatch:
    def test_literal_value_in_param_slot(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/pets/42", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets/{petId}"
        assert result.extracted_path_params == {"petId": "42"}

    def test_user_id_positional(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/users/99", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/users/{userId}"
        assert result.extracted_path_params == {"userId": "99"}


class TestFuzzyMatch:
    def test_singular_plural(self, petstore_spec: ApiSpec):
        # /pet should fuzzy-match /pets
        result = match_route("GET", "/pet", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets"

    def test_singular_with_param(self, petstore_spec: ApiSpec):
        # /pet/{petId} should fuzzy-match /pets/{petId}
        result = match_route("GET", "/pet/{petId}", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/pets/{petId}"

    def test_user_singular(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/user", petstore_spec)
        assert result.operation is not None
        assert result.operation.path == "/users"


class TestNoMatch:
    def test_no_match_gives_suggestions(self, petstore_spec: ApiSpec):
        result = match_route("GET", "/foobar", petstore_spec)
        assert result.operation is None
        assert result.suggestions is not None
        assert len(result.suggestions) > 0

    def test_wrong_method(self, petstore_spec: ApiSpec):
        # PATCH /pets doesn't exist
        result = match_route("PATCH", "/pets", petstore_spec)
        assert result.operation is None
        assert result.suggestions is not None
