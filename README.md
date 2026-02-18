# cliforapi

Universal CLI that reads any OpenAPI spec and exposes its endpoints as shell commands — optimized for AI agent consumption.

## Install

```bash
pip install .
```

Or for development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
# List all endpoints
cliforapi --spec https://petstore.swagger.io/v2/swagger.json list

# GET request
cliforapi --spec https://petstore.swagger.io/v2/swagger.json get /pet/{petId} --petId 1

# POST with body
cliforapi --spec https://petstore.swagger.io/v2/swagger.json post /pet --body '{"name": "Fido", "status": "available"}'

# Positional params (auto-detected)
cliforapi --spec https://petstore.swagger.io/v2/swagger.json get /pet/1

# JSON output instead of TOON
cliforapi --spec https://petstore.swagger.io/v2/swagger.json --json get /pet/{petId} --petId 1

# Local spec file
cliforapi --spec ./openapi.yaml get /users
```

## Output

Default output uses [TOON](https://toonformat.dev/) format (30-60% fewer tokens than JSON):

```
status: 200
elapsed_ms: 142
headers:
  "content-type": application/json
body:
  id: 1
  name: doggie
  status: available
```

Use `--json` for standard JSON envelope when you need machine-parseable output.

Errors are always JSON:

```json
{"error": "NO_MATCH", "message": "No endpoint matches 'GET /foo'. Did you mean: GET /pet/{petId}?", "status": null}
```

## Auth

```bash
# Interactive setup (stores creds in ~/.cliforapi/<domain>.env)
cliforapi auth --spec https://api.example.com/openapi.json

# Or pass directly
cliforapi --spec ... --token <bearer-token> get /protected
cliforapi --spec ... --api-key <key> get /protected

# Or set env vars
export CLIFORAPI_BEARER_TOKEN=abc123
```

Precedence: CLI flags > env vars > `.env` file.

## Route Matching

Routes are matched using a fuzzy cascade:

1. **Exact** — `/pet/{petId}` matches verbatim
2. **Normalized** — `:petId`, `<petId>` styles + case-insensitive
3. **Positional** — `/pet/1` matches `/pet/{petId}` (value captured)
4. **Fuzzy** — `/pets` matches `/pet` (singular/plural, typo tolerance)
5. **Suggestions** — no match returns top 3 closest endpoints

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (2xx) |
| 1 | CLI or spec error |
| 2 | Auth error |
| 3 | Client error (4xx) |
| 4 | Server error (5xx) |
| 5 | Network error |

## Spec Support

- OpenAPI 3.x (JSON/YAML)
- Swagger 2.0 (JSON/YAML)
- Remote URL or local file

## Tests

```bash
pytest
```
