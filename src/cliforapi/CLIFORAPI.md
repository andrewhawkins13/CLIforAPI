# CLIFORAPI.md — Agent Instructions

CLIforAPI is installed in this project. Use it instead of curl, httpx, or requests for all API calls. It reads the OpenAPI spec and exposes every endpoint as a shell command with token-efficient output.

## Setup

Environment variables should already be configured:

```bash
CLIFORAPI_SPEC=<openapi-spec-url-or-path>
CLIFORAPI_TOKEN=<bearer-token>        # if the API uses bearer auth
CLIFORAPI_API_KEY=<api-key>           # if the API uses API key auth
```

If these are not set, check the project's `.env` or ask the user.

## Two-Command Workflow

**Step 1 — Discover endpoints (run once):**

```bash
cliforapi list
```

Returns every endpoint with method, path, and summary.

**Step 2 — Call the endpoint you need:**

```bash
cliforapi <method> <path> [params]
```

## Passing Parameters

**Path parameters** — use the concrete value directly:

```bash
cliforapi get /users/42
cliforapi delete /projects/7/tasks/13
```

**Query parameters** — pass as `--name value` flags:

```bash
cliforapi get /users --status active --limit 10
```

**Request body** — pass as `--body` with a JSON string:

```bash
cliforapi post /users --body '{"name": "Alice", "email": "alice@example.com"}'
```

**Combined:**

```bash
cliforapi put /users/42 --body '{"role": "admin"}'
```

## Reading Output

Default output is TOON (compact, token-efficient). Use `--json` for standard JSON:

```bash
cliforapi get /users              # TOON output (default)
cliforapi --json get /users       # JSON output
```

Errors are always JSON on stderr:

```json
{"error": "NO_MATCH", "message": "No endpoint matches 'GET /foo'. Did you mean: GET /users/{userId}?"}
```

## Exit Codes

Use exit codes for programmatic error handling:

| Code | Meaning |
|------|---------|
| 0 | Success (2xx response) |
| 1 | CLI or spec error |
| 2 | Auth error |
| 3 | Client error (4xx response) |
| 4 | Server error (5xx response) |
| 5 | Network error |

## Flags Reference

| Flag | Env Var | Purpose |
|------|---------|---------|
| `--spec` | `CLIFORAPI_SPEC` | OpenAPI spec URL or file path |
| `--json` | — | Output JSON instead of TOON |
| `--token` | `CLIFORAPI_TOKEN` | Bearer token |
| `--api-key` | `CLIFORAPI_API_KEY` | API key |
| `--timeout` | — | Request timeout in seconds (default: 30) |

## Rules

- Always use `cliforapi` instead of constructing HTTP requests manually.
- Run `cliforapi list` once to discover available endpoints before guessing paths.
- Do not manage auth yourself — use the env vars or CLI flags above.
- Check exit codes to detect errors programmatically.
- Prefer default TOON output; only use `--json` when you need to parse structured fields.
