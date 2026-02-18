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
cliforapi get /pet/1                         # positional params auto-detected
cliforapi --json get /pet/{petId} --petId 1  # JSON output
```

Or pass `--spec` directly:

```bash
cliforapi --spec ./openapi.yaml get /users
```

## Environment Variables

All flags can be set via env vars for a zero-flag workflow:

| Env Var | Flag | Purpose |
|---------|------|---------|
| `CLIFORAPI_SPEC` | `--spec` | OpenAPI spec URL or file path |
| `CLIFORAPI_TOKEN` | `--token` | Bearer token for auth |
| `CLIFORAPI_API_KEY` | `--api-key` | API key for auth |

CLI flags always override env vars when both are set.

## Output

Default output uses [TOON](https://toonformat.dev/) format — significantly fewer tokens than JSON, which directly reduces cost and context usage for AI agents.

### Token Savings (real-world, measured against Tidy API)

| Response | JSON | TOON | Saved |
|----------|------|------|-------|
| To-do lists (tabular) | 247 tokens | 134 tokens | **46%** |
| Addresses (nested) | 403 tokens | 308 tokens | **24%** |

*Measured with cl100k_base tokenizer. JSON numbers use equivalent body-only envelope for a fair comparison.*

TOON's tabular format is where the biggest savings come from — uniform lists of objects collapse key repetition into a single header row:

```
# TOON — 134 tokens
status: 200
elapsed_ms: 286
body:
  object: list
  data[2]{object,id,title,before_after_photos_state,state,is_address_favorite,is_address_default,address_id,created_at}:
    to_do_list,196459,Northeast 24th Avenue List,inactive,active,null,null,null,"2022-06-21T15:50:25+00:00"
    to_do_list,300524,Northeast 43rd Avenue List,null,active,null,null,null,"2023-08-08T22:46:16+00:00"
```

```json
// JSON — 247 tokens
{
  "status": 200,
  "body": {
    "object": "list",
    "data": [
      {
        "object": "to_do_list",
        "id": 196459,
        "title": "Northeast 24th Avenue List",
        "before_after_photos_state": "inactive",
        "state": "active",
        "is_address_favorite": null,
        "is_address_default": null,
        "address_id": null,
        "created_at": "2022-06-21T15:50:25+00:00"
      },
      {
        "object": "to_do_list",
        "id": 300524,
        "title": "Northeast 43rd Avenue List",
        "before_after_photos_state": null,
        "state": "active",
        "is_address_favorite": null,
        "is_address_default": null,
        "address_id": null,
        "created_at": "2023-08-08T22:46:16+00:00"
      }
    ]
  }
}
```

Use `--json` when you need standard JSON output. Errors are always JSON:

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

When credentials are saved via `cliforapi auth`, the tool automatically adds `*.env` to `.gitignore` if the config directory is inside a git repo. If not, it prints a warning about the plaintext credentials file.

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

### 1. Set up

Use an existing token or create one at https://github.com/settings/tokens. If you have the `gh` CLI:

```bash
export CLIFORAPI_SPEC=https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json
export CLIFORAPI_TOKEN=$(gh auth token)
```

### 2. Explore available endpoints

```bash
cliforapi list | head -20
```

### 3. Make authenticated requests

```bash
# Get your user profile
cliforapi get /user

# List your repos
cliforapi get /user/repos --per_page 3

# Get a specific repo
cliforapi get /repos/{owner}/{repo} --owner octocat --repo Hello-World
```

### 4. Compare output formats

```bash
# TOON (default) — compact, token-efficient
cliforapi get /user

# JSON — full envelope with all headers
cliforapi --json get /user
```

### 5. Test without auth (see the error)

```bash
CLIFORAPI_TOKEN= cliforapi get /user
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

73 tests across 7 files covering spec parsing, route matching, auth, HTTP client, output formatting, and CLI integration.
