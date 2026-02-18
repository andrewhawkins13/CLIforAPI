# CLAUDE.md — cliforapi

## Project Overview

**cliforapi** is a runtime proxy CLI that reads any OpenAPI spec and dynamically exposes its endpoints as shell commands. Primary users are AI agents — output is token-efficient TOON by default with predictable exit codes and structured errors.

## Tech Stack

- **Language:** Python 3.10+
- **CLI framework:** Click
- **HTTP client:** httpx
- **Spec parsing:** pydantic models over raw dicts
- **TOON encoding:** `toons` (Rust-based, spec-compliant)
- **Config/secrets:** python-dotenv, `~/.cliforapi/<domain>.env`
- **Tests:** pytest + respx (httpx mocking)

## Project Structure

```
src/cliforapi/
├── cli.py       # Click entry point, subcommands, dynamic method routing
├── spec.py      # OpenAPI 3.x / Swagger 2.0 loading, parsing, caching
├── matcher.py   # 5-stage fuzzy route matching cascade
├── resolver.py  # Maps CLI args → HTTP method, path, params, body
├── auth.py      # Auth detection, .env persistence, precedence chain
├── client.py    # HTTP execution via httpx
├── output.py    # TOON/JSON formatting, exit code mapping
└── config.py    # ~/.cliforapi/ directory management
```

## Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run CLI
cliforapi --spec <url-or-file> list
cliforapi --spec <url-or-file> get /path --param value
```

## Architecture Decisions

- **No codegen** — one universal CLI binary, reads specs at runtime
- **TOON default output** — uses `toons` library (Rust-based). JSON via `--json` flag. Errors always JSON.
- **Relative server URLs** — resolved against spec source origin in `spec.py:_resolve_base_url()`
- **Auth precedence** — CLI flags > `CLIFORAPI_*` env vars > `~/.cliforapi/<domain>.env`
- **Route matching cascade** — exact → normalized → positional → fuzzy → suggestions (in `matcher.py`)
- **Exit codes** — 0=2xx, 1=CLI error, 2=auth, 3=4xx, 4=5xx, 5=network

## Conventions

- All modules use `from __future__ import annotations`
- Pydantic `BaseModel` for spec data models (not dicts)
- Custom exceptions carry a `.code` and `.message` (e.g. `ResolutionError`)
- Tests use `respx` for HTTP mocking, `click.testing.CliRunner` for CLI tests
- Spec cache (`_cache` in spec.py) must be cleared between tests via `clear_cache()`
- The `auth` subcommand is the only interactive command; everything else is non-interactive

## Testing

- 70 tests across 7 files
- `conftest.py` provides `petstore_raw` (dict) and `petstore_spec` (parsed `ApiSpec`) fixtures
- When testing CLI commands with `CliRunner`, always call `clear_cache()` first to avoid cross-test spec pollution
- `pytest.raises(match=...)` matches against exception message string, not `.code` — assert `.code` separately
