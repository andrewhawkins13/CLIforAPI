"""Tests for spec loading and parsing."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from cliforapi.spec import ApiSpec, parse_spec, load_spec, clear_cache


class TestParseSpecV3:
    def test_basic_fields(self, petstore_raw: dict):
        spec = parse_spec(petstore_raw)
        assert spec.title == "Petstore"
        assert spec.version == "1.0.0"
        assert spec.base_url == "https://petstore.example.com/v1"

    def test_operations_discovered(self, petstore_raw: dict):
        spec = parse_spec(petstore_raw)
        methods_paths = [(op.method, op.path) for op in spec.operations]
        assert ("GET", "/pets") in methods_paths
        assert ("POST", "/pets") in methods_paths
        assert ("GET", "/pets/{petId}") in methods_paths
        assert ("DELETE", "/pets/{petId}") in methods_paths
        assert ("GET", "/users") in methods_paths

    def test_parameters_parsed(self, petstore_raw: dict):
        spec = parse_spec(petstore_raw)
        get_pet = next(op for op in spec.operations if op.operation_id == "getPet")
        assert len(get_pet.parameters) == 1
        assert get_pet.parameters[0].name == "petId"
        assert get_pet.parameters[0].location == "path"
        assert get_pet.parameters[0].required is True

    def test_request_body_detected(self, petstore_raw: dict):
        spec = parse_spec(petstore_raw)
        create_pet = next(op for op in spec.operations if op.operation_id == "createPet")
        assert create_pet.has_request_body is True

    def test_security_schemes(self, petstore_raw: dict):
        spec = parse_spec(petstore_raw)
        assert "bearerAuth" in spec.security_schemes
        assert spec.security_schemes["bearerAuth"].type == "http"
        assert spec.security_schemes["bearerAuth"].scheme == "bearer"
        assert "apiKey" in spec.security_schemes
        assert spec.security_schemes["apiKey"].type == "apiKey"


class TestParseSpecV2:
    def test_swagger2(self):
        raw = {
            "swagger": "2.0",
            "info": {"title": "Legacy API", "version": "0.1"},
            "host": "api.legacy.com",
            "basePath": "/v2",
            "schemes": ["https"],
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "listItems",
                        "parameters": [
                            {"name": "q", "in": "query", "type": "string"},
                        ],
                    },
                    "post": {
                        "operationId": "createItem",
                        "parameters": [
                            {"name": "body", "in": "body", "schema": {"type": "object"}},
                        ],
                    },
                },
            },
            "securityDefinitions": {
                "basicAuth": {"type": "basic"},
                "apiKey": {"type": "apiKey", "name": "Authorization", "in": "header"},
            },
        }
        spec = parse_spec(raw)
        assert spec.base_url == "https://api.legacy.com/v2"
        assert spec.security_schemes["basicAuth"].type == "http"
        assert spec.security_schemes["basicAuth"].scheme == "basic"

        create = next(op for op in spec.operations if op.operation_id == "createItem")
        assert create.has_request_body is True


class TestLoadSpec:
    def test_load_json_file(self, tmp_path: Path, petstore_raw: dict):
        clear_cache()
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(petstore_raw))
        spec = load_spec(str(spec_file))
        assert spec.title == "Petstore"

    def test_load_yaml_file(self, tmp_path: Path, petstore_raw: dict):
        clear_cache()
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml.dump(petstore_raw))
        spec = load_spec(str(spec_file))
        assert spec.title == "Petstore"

    def test_caching(self, tmp_path: Path, petstore_raw: dict):
        clear_cache()
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(petstore_raw))
        path = str(spec_file)
        spec1 = load_spec(path)
        spec2 = load_spec(path)
        assert spec1 is spec2  # same object from cache
