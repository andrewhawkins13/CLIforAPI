# CLIforAPI

Point this CLI at any OpenAPI spec. Every endpoint becomes a shell command — with output compressed for AI agents.

## Before / After

Without CLIforAPI — read docs, craft curl, parse JSON:

```bash
# 1. Read the API docs to find the right endpoint       (~386 tokens)
# 2. Figure out method, path, auth, headers              (~125 tokens)
curl -s https://api.example.com/users/42 \
  -H "Authorization: Bearer $TOKEN" | jq .              # (~365 tokens)
# Total: ~876 tokens
```

With CLIforAPI:

```bash
cliforapi get /users/42                                  # ~308 tokens
# Total: ~364 tokens (including one-time `list` call)
```

**58% fewer tokens for the same result.**

## Why This Exists

AI agents calling REST APIs burn tokens on four steps: reading docs, reasoning about the API, crafting HTTP requests, and parsing JSON responses. CLIforAPI collapses all four into one command.

### Full Workflow Comparison

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
| `cliforapi get /users` (TOON response) | ~308 |
| **Total** | **~364** |

For tabular data the savings hit **64%** because TOON collapses repeated keys into a single header row.

*Measured with cl100k_base tokenizer against a real API. Docs page token count is conservative — real documentation pages with navigation, code examples, and full schemas are typically 2-5x larger.*

## Quick Start

```bash
pip install .
export CLIFORAPI_SPEC=https://api.example.com/openapi.json

cliforapi list                                        # discover endpoints
cliforapi get /users/42                               # positional params auto-detected
cliforapi post /users --body '{"name": "Alice"}'      # create
cliforapi --json get /users/42                        # JSON output instead of TOON
```

Spec can also be a local file: `cliforapi --spec ./openapi.yaml get /users`

## Output Format

Default output is [TOON](https://toonformat.dev/). Pass `--json` for standard JSON. Errors are always JSON.

### TOON vs JSON

| Response | JSON | TOON | Saved |
|----------|------|------|-------|
| Users (tabular) | 247 tokens | 134 tokens | **46%** |
| Orders (nested) | 403 tokens | 308 tokens | **24%** |

*Measured with cl100k_base tokenizer. JSON numbers use equivalent body-only envelope.*

Tabular data is where the biggest savings come from — uniform lists collapse key repetition into a single header row:

```
# TOON — 134 tokens
status: 200
elapsed_ms: 152
body:
  object: list
  data[2]{id,name,email,role,status,department,manager_id,office_id,created_at}:
    1,"Alice Johnson","alice@example.com",admin,active,engineering,null,null,"2024-01-15T09:30:00+00:00"
    2,"Bob Smith","bob@example.com",member,active,marketing,null,null,"2024-03-22T14:15:00+00:00"
```

```json
// JSON — 247 tokens
{
  "status": 200,
  "body": {
    "object": "list",
    "data": [
      {
        "id": 1,
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "role": "admin",
        "status": "active",
        "department": "engineering",
        "manager_id": null,
        "office_id": null,
        "created_at": "2024-01-15T09:30:00+00:00"
      },
      {
        "id": 2,
        "name": "Bob Smith",
        "email": "bob@example.com",
        "role": "member",
        "status": "active",
        "department": "marketing",
        "manager_id": null,
        "office_id": null,
        "created_at": "2024-03-22T14:15:00+00:00"
      }
    ]
  }
}
```

Error output is always JSON:

```json
{"error": "NO_MATCH", "message": "No endpoint matches 'GET /foo'. Did you mean: GET /users/{userId}?", "status": null}
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

## Environment Variables

All flags can be set via env vars for a zero-flag workflow:

| Env Var | Flag | Purpose |
|---------|------|---------|
| `CLIFORAPI_SPEC` | `--spec` | OpenAPI spec URL or file path |
| `CLIFORAPI_TOKEN` | `--token` | Bearer token for auth |
| `CLIFORAPI_API_KEY` | `--api-key` | API key for auth |

CLI flags always override env vars when both are set.

## Route Matching

Routes are matched using a fuzzy cascade:

1. **Exact** — `/users/{userId}` matches verbatim
2. **Normalized** — `:userId`, `<userId>` styles + case-insensitive
3. **Positional** — `/users/42` matches `/users/{userId}` (value captured)
4. **Fuzzy** — `/user` matches `/users` (singular/plural, typo tolerance)
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
