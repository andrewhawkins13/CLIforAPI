# CLIforAPI

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

## Why CLIforAPI?

AI agents that need to call a REST API typically follow this workflow:

1. **Read the docs page** — fetch and parse the HTML documentation (hundreds to thousands of tokens depending on the page)
2. **Reason about the API** — figure out the base URL, HTTP method, path, auth mechanism, required headers
3. **Craft an HTTP request** — construct the correct curl/httpx/fetch call
4. **Parse the JSON response** — read the raw JSON body

CLIforAPI collapses all four steps into a single shell command with compact output.

### Full Workflow Comparison (measured against Tidy API)

**Without CLIforAPI** — agent reads docs, crafts request, parses JSON:

| Step | Tokens |
|------|--------|
| Read API docs page | ~386 |
| Reason about API + craft HTTP request | ~125 |
| Parse JSON response | ~365 |
| **Total** | **~876** |

**With CLIforAPI** — agent runs one command:

| Step | Tokens |
|------|--------|
| `cliforapi list` (discover endpoints, one-time) | ~56 |
| `cliforapi get /addresses` (TOON response) | ~308 |
| **Total** | **~364** |

**Result: 58% fewer tokens for the entire interaction.**

For tabular data the savings are even larger — **64%** — because TOON collapses repeated keys into a single header row and the agent skips the docs-reading step entirely.

*Measured with cl100k_base tokenizer against real Tidy API responses. Docs page token count is conservative — real readme.io pages with sidebar navigation, multi-language code examples, and full schemas are typically 2-5x larger.*

## Output

Default output uses [TOON](https://toonformat.dev/) format — significantly fewer tokens than JSON, which directly reduces cost and context usage for AI agents.

### Response Format Comparison (TOON vs JSON)

| Response | JSON | TOON | Saved |
|----------|------|------|-------|
| To-do lists (tabular) | 247 tokens | 134 tokens | **46%** |
| Addresses (nested) | 403 tokens | 308 tokens | **24%** |

*Measured with cl100k_base tokenizer. JSON numbers use equivalent body-only envelope.*

TOON's tabular format is where the biggest format savings come from — uniform lists of objects collapse key repetition into a single header row:

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

When credentials are saved via `cliforapi auth`, CLIforAPI automatically adds `*.env` to `.gitignore` if the config directory is inside a git repo. If not, it prints a warning about the plaintext credentials file.

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
- `$ref` parameter resolution

## Tests

```bash
pytest
```

77 tests across 7 files covering spec parsing, route matching, auth, HTTP client, output formatting, and CLI integration.
