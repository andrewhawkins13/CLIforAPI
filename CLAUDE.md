# CLAUDE.md — CLIforAPI

## Project Overview

**CLIforAPI** is a runtime proxy CLI that reads any OpenAPI spec and dynamically exposes its endpoints as shell commands. Primary users are AI agents — output is token-efficient TOON by default with predictable exit codes and structured errors.

## Tech Stack

- **Language:** Python 3.10+
- **CLI framework:** Click (with `envvar` support for zero-flag workflows)
- **HTTP client:** httpx
- **Spec parsing:** pydantic models over raw dicts, with `$ref` resolution
- **TOON encoding:** `toons` (Rust-based, spec-compliant)
- **Config/secrets:** python-dotenv, `~/.cliforapi/<domain>.env`
- **Tests:** pytest + respx (httpx mocking)

## Project Structure

```
src/cliforapi/
├── cli.py       # Click entry point, subcommands (init, auth, list, HTTP methods)
├── CLIFORAPI.md # Bundled agent instruction template (written by `init` command)
├── spec.py      # OpenAPI 3.x / Swagger 2.0 loading, parsing, $ref resolution, caching
├── matcher.py   # 5-stage fuzzy route matching cascade
├── resolver.py  # Maps CLI args → HTTP method, path, params, body
├── auth.py      # Auth detection, .env persistence, precedence chain, gitignore protection
├── client.py    # HTTP execution via httpx
├── output.py    # TOON/JSON formatting via `toons` library, exit code mapping
└── config.py    # ~/.cliforapi/ directory management, credential protection
```

## Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests (77 tests, should all pass)
pytest

# Run CLI (env var or --spec flag)
export CLIFORAPI_SPEC=https://api.example.com/openapi.json
cliforapi list
cliforapi get /users/42
```

## Architecture Decisions

- **No codegen** — one universal CLI binary, reads specs at runtime
- **Env var-first config** — `CLIFORAPI_SPEC`, `CLIFORAPI_TOKEN`, `CLIFORAPI_API_KEY` eliminate repetitive flags; CLI flags override when set
- **TOON default output** — uses `toons` library (Rust-based). JSON via `--json` flag. Errors always JSON.
- **Relative server URLs** — resolved against spec source origin in `spec.py:_resolve_base_url()`
- **`$ref` resolution** — parameters using `$ref` pointers are resolved against the root spec document, enabling large specs like GitHub's (1080 endpoints)
- **Auth fallback** — `--token` always injects `Authorization: Bearer` header even when the spec declares no security schemes (many real-world specs omit scheme declarations)
- **Auth precedence** — CLI flags > `CLIFORAPI_*` env vars > `~/.cliforapi/<domain>.env`
- **Agent discovery** — `cliforapi init` writes `CLIFORAPI.md` to the project root so AI coding tools auto-discover CLIforAPI; canonical template lives at `skills/CLIFORAPI.md`, bundled copy at `src/cliforapi/CLIFORAPI.md` for `importlib.resources`
- **Credential protection** — `cliforapi auth` auto-adds `*.env` to `.gitignore` when config dir is in a git repo; warns on stderr otherwise
- **Route matching cascade** — exact → normalized → positional → fuzzy → suggestions (in `matcher.py`)
- **Exit codes** — 0=2xx, 1=CLI error, 2=auth, 3=4xx, 4=5xx, 5=network

## Conventions

- All modules use `from __future__ import annotations`
- Pydantic `BaseModel` for spec data models (not dicts)
- Custom exceptions carry a `.code` and `.message` (e.g. `ResolutionError`)
- Tests use `respx` for HTTP mocking, `click.testing.CliRunner` for CLI tests
- Spec cache (`_cache` in spec.py) must be cleared between tests via `clear_cache()`
- The `auth` subcommand is the only interactive command; everything else is non-interactive
- The canonical `CLIFORAPI.md` lives at `skills/CLIFORAPI.md`; `src/cliforapi/CLIFORAPI.md` is a copy bundled for `importlib.resources` - keep them in sync

## Testing

- 79 tests across 7 files
- `conftest.py` provides `petstore_raw` (dict) and `petstore_spec` (parsed `ApiSpec`) fixtures
- When testing CLI commands with `CliRunner`, always call `clear_cache()` first to avoid cross-test spec pollution
- `pytest.raises(match=...)` matches against exception message string, not `.code` — assert `.code` separately
- `TestProtectCredentials` tests require git to be installed (uses `git init` in tmp dirs)

## Tested Against

- Swagger 2.0 specs — CRUD operations, query params, positional params
- Large OpenAPI 3.0 specs (1000+ endpoints) — authenticated requests, `$ref` param resolution
- Hosted OpenAPI 3.0 specs — remote spec auto-loading
