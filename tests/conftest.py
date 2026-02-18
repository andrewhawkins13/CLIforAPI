"""Shared fixtures for cliforapi tests."""

from __future__ import annotations

import pytest

from cliforapi.spec import ApiSpec, OperationSpec, ParamSpec, SecurityScheme


PETSTORE_RAW = {
    "openapi": "3.0.0",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "servers": [{"url": "https://petstore.example.com/v1"}],
    "security": [{"bearerAuth": []}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                    {"name": "status", "in": "query", "schema": {"type": "string"}},
                ],
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}},
                ],
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "parameters": [
                    {"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}},
                ],
            },
        },
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List users",
            },
        },
        "/users/{userId}": {
            "get": {
                "operationId": "getUser",
                "summary": "Get a user",
                "parameters": [
                    {"name": "userId", "in": "path", "required": True, "schema": {"type": "integer"}},
                ],
            },
        },
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
            },
            "apiKey": {
                "type": "apiKey",
                "name": "X-API-Key",
                "in": "header",
            },
        },
    },
}


@pytest.fixture
def petstore_raw() -> dict:
    return PETSTORE_RAW.copy()


@pytest.fixture
def petstore_spec() -> ApiSpec:
    from cliforapi.spec import parse_spec
    return parse_spec(PETSTORE_RAW)
