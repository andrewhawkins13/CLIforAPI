"""Tests for auth module."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cliforapi.auth import (
    ResolvedAuth,
    load_env_credentials,
    resolve_auth,
    save_credentials,
)
from cliforapi.config import protect_credentials
from cliforapi.spec import ApiSpec, SecurityScheme


@pytest.fixture
def spec_with_bearer() -> ApiSpec:
    return ApiSpec(
        title="Test",
        version="1.0",
        base_url="https://api.test.com",
        security_schemes={
            "bearerAuth": SecurityScheme(type="http", scheme="bearer"),
        },
    )


@pytest.fixture
def spec_with_apikey() -> ApiSpec:
    return ApiSpec(
        title="Test",
        version="1.0",
        base_url="https://api.test.com",
        security_schemes={
            "apiKey": SecurityScheme(type="apiKey", name="X-API-Key", location="header"),
        },
    )


class TestSaveLoadCredentials:
    def test_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("cliforapi.config.CONFIG_DIR", tmp_path)
        spec_ref = "https://api.example.com/openapi.json"

        save_credentials(spec_ref, {"BEARER_TOKEN": "abc123"})
        creds = load_env_credentials(spec_ref)
        assert creds["BEARER_TOKEN"] == "abc123"

    def test_missing_env_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("cliforapi.config.CONFIG_DIR", tmp_path)
        creds = load_env_credentials("https://nonexistent.com/spec.json")
        assert creds == {}


class TestResolveAuth:
    def test_cli_token_takes_precedence(self, spec_with_bearer: ApiSpec):
        auth = resolve_auth(spec_with_bearer, "https://api.test.com/spec.json", cli_token="cli-tok")
        assert auth.headers["Authorization"] == "Bearer cli-tok"

    def test_env_var_fallback(self, spec_with_bearer: ApiSpec, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CLIFORAPI_BEARER_TOKEN", "env-tok")
        auth = resolve_auth(spec_with_bearer, "https://api.test.com/spec.json")
        assert auth.headers["Authorization"] == "Bearer env-tok"

    def test_dotenv_fallback(self, spec_with_bearer: ApiSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("cliforapi.config.CONFIG_DIR", tmp_path)
        monkeypatch.delenv("CLIFORAPI_BEARER_TOKEN", raising=False)
        save_credentials("https://api.test.com/spec.json", {"BEARER_TOKEN": "file-tok"})
        auth = resolve_auth(spec_with_bearer, "https://api.test.com/spec.json")
        assert auth.headers["Authorization"] == "Bearer file-tok"

    def test_apikey_header(self, spec_with_apikey: ApiSpec, monkeypatch: pytest.MonkeyPatch):
        auth = resolve_auth(spec_with_apikey, "https://api.test.com/spec.json", cli_api_key="key123")
        assert auth.headers["X-API-Key"] == "key123"

    def test_no_auth_returns_empty(self):
        spec = ApiSpec(title="Test", version="1.0", base_url="https://api.test.com")
        auth = resolve_auth(spec, "https://api.test.com/spec.json")
        assert auth.headers == {}
        assert auth.query_params == {}


class TestProtectCredentials:
    def test_adds_gitignore_in_git_repo(self, tmp_path: Path):
        # Init a git repo in tmp_path
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        env_file = tmp_path / "api.example.com.env"
        env_file.write_text('BEARER_TOKEN="abc"\n')

        result = protect_credentials(env_file)

        assert result is None  # no warning
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert "*.env" in gitignore.read_text()

    def test_idempotent_gitignore(self, tmp_path: Path):
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.env\n")
        env_file = tmp_path / "test.env"
        env_file.write_text("X=1\n")

        protect_credentials(env_file)

        # Should not duplicate the pattern
        lines = [l for l in gitignore.read_text().splitlines() if l == "*.env"]
        assert len(lines) == 1

    def test_warns_when_not_git_repo(self, tmp_path: Path):
        env_file = tmp_path / "api.example.com.env"
        env_file.write_text('BEARER_TOKEN="abc"\n')

        result = protect_credentials(env_file)

        assert result is not None
        assert "not inside a git repository" in result
        assert str(env_file) in result
