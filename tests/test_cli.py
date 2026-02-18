"""Tests for CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
import yaml
from click.testing import CliRunner

from cliforapi.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def spec_file(tmp_path: Path) -> str:
    from tests.conftest import PETSTORE_RAW
    spec_path = tmp_path / "petstore.json"
    spec_path.write_text(json.dumps(PETSTORE_RAW))
    return str(spec_path)


class TestCli:
    def test_help(self, runner: CliRunner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "cliforapi" in result.output

    def test_version(self, runner: CliRunner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestListCommand:
    def test_list_toon(self, runner: CliRunner, spec_file: str):
        from cliforapi.spec import clear_cache
        clear_cache()
        result = runner.invoke(main, ["--spec", spec_file, "list"])
        assert result.exit_code == 0
        assert "endpoints[" in result.output
        assert "/pets" in result.output

    def test_list_json(self, runner: CliRunner, spec_file: str):
        from cliforapi.spec import clear_cache
        clear_cache()
        result = runner.invoke(main, ["--spec", spec_file, "--json", "list"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert any(ep["path"] == "/pets" for ep in parsed)

    def test_list_no_spec(self, runner: CliRunner):
        result = runner.invoke(main, ["list"])
        assert result.exit_code != 0


class TestGetCommand:
    @respx.mock
    def test_get_success(self, runner: CliRunner, spec_file: str):
        from cliforapi.spec import clear_cache
        clear_cache()
        respx.get("https://petstore.example.com/v1/pets").mock(
            return_value=httpx.Response(200, json=[{"id": 1, "name": "Fido"}])
        )
        result = runner.invoke(main, ["--spec", spec_file, "get", "/pets"])
        assert result.exit_code == 0
        assert "200" in result.output

    @respx.mock
    def test_get_with_path_param(self, runner: CliRunner, spec_file: str):
        from cliforapi.spec import clear_cache
        clear_cache()
        respx.get("https://petstore.example.com/v1/pets/42").mock(
            return_value=httpx.Response(200, json={"id": 42, "name": "Rex"})
        )
        result = runner.invoke(main, ["--spec", spec_file, "get", "/pets/{petId}", "--petId", "42"])
        assert result.exit_code == 0
        assert "Rex" in result.output

    @respx.mock
    def test_get_json_flag(self, runner: CliRunner, spec_file: str):
        from cliforapi.spec import clear_cache
        clear_cache()
        respx.get("https://petstore.example.com/v1/pets").mock(
            return_value=httpx.Response(200, json=[{"id": 1}])
        )
        result = runner.invoke(main, ["--spec", spec_file, "--json", "get", "/pets"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == 200

    @respx.mock
    def test_get_404(self, runner: CliRunner, spec_file: str):
        from cliforapi.spec import clear_cache
        clear_cache()
        respx.get("https://petstore.example.com/v1/pets/99999").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        result = runner.invoke(main, ["--spec", spec_file, "get", "/pets/{petId}", "--petId", "99999"])
        assert result.exit_code == 3  # EXIT_4XX

    def test_get_no_spec(self, runner: CliRunner):
        result = runner.invoke(main, ["get", "/pets"])
        assert result.exit_code != 0


class TestPostCommand:
    @respx.mock
    def test_post_with_body(self, runner: CliRunner, spec_file: str):
        from cliforapi.spec import clear_cache
        clear_cache()
        respx.post("https://petstore.example.com/v1/pets").mock(
            return_value=httpx.Response(201, json={"id": 2, "name": "Rex"})
        )
        result = runner.invoke(main, [
            "--spec", spec_file, "post", "/pets",
            "--body", '{"name": "Rex"}',
        ])
        assert result.exit_code == 0
        assert "Rex" in result.output
