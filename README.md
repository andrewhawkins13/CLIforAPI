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

Set `CLIFORAPI_SPEC` once to skip `--spec` on every call:

```bash
export CLIFORAPI_SPEC=https://petstore.swagger.io/v2/swagger.json

cliforapi list
cliforapi get /pet/{petId} --petId 1
cliforapi post /pet --body '{"name": "Fido", "status": "available"}'
cliforapi get /pet/1                    # positional params auto-detected
cliforapi --json get /pet/{petId} --petId 1  # JSON output
```

Or pass `--spec` directly:

```bash
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
cliforapi --token <bearer-token> get /protected
cliforapi --api-key <key> get /protected

# Or set env vars for a full zero-flag workflow
export CLIFORAPI_SPEC=https://api.example.com/openapi.json
export CLIFORAPI_TOKEN=your-token
cliforapi get /protected
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

## Real-World Example: GitHub API

Step-by-step walkthrough using the GitHub REST API (1080 endpoints, bearer token auth).

### 1. Get a GitHub token

Use an existing token or create one at https://github.com/settings/tokens. If you have the `gh` CLI:

```bash
export GH_TOKEN=$(gh auth token)
```

### 2. Explore available endpoints

```bash
SPEC=https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json

cliforapi --spec $SPEC list | head -20
```

### 3. Make an authenticated request

```bash
# Get your user profile
cliforapi --spec $SPEC --token $GH_TOKEN get /user

# List your repos
cliforapi --spec $SPEC --token $GH_TOKEN get /user/repos --per_page 3

# Get a specific repo
cliforapi --spec $SPEC --token $GH_TOKEN get /repos/{owner}/{repo} --owner andrewhawkins13 --repo cliforapi
```

### 4. Compare output formats

```bash
# TOON (default) — compact, token-efficient
cliforapi --spec $SPEC --token $GH_TOKEN get /user

# JSON — full envelope with all headers
cliforapi --spec $SPEC --token $GH_TOKEN --json get /user
```

### 5. Test without auth (see the error)

```bash
cliforapi --spec $SPEC get /user
# → status: 401, exit code: 3
```

## Spec Support

- OpenAPI 3.x (JSON/YAML)
- Swagger 2.0 (JSON/YAML)
- Remote URL or local file
- `$ref` parameter resolution

## Tests

```bash
pytest
```
