"""Load, parse, and cache OpenAPI / Swagger specs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Lightweight models – we only pull out what we need for routing & resolution
# ---------------------------------------------------------------------------

class ParamSpec(BaseModel):
    name: str
    location: str  # "path", "query", "header", "cookie"
    required: bool = False
    schema_type: str = "string"


class SecurityScheme(BaseModel):
    type: str          # "apiKey", "http", "oauth2", "openIdConnect"
    name: str | None = None       # header/query param name (apiKey)
    location: str | None = None   # "header" | "query" | "cookie" (apiKey)
    scheme: str | None = None     # "bearer", "basic" (http)


class OperationSpec(BaseModel):
    method: str
    path: str
    operation_id: str | None = None
    summary: str | None = None
    parameters: list[ParamSpec] = []
    has_request_body: bool = False
    security: list[dict[str, list[str]]] | None = None


class ApiSpec(BaseModel):
    title: str = ""
    version: str = ""
    base_url: str = ""
    operations: list[OperationSpec] = []
    security_schemes: dict[str, SecurityScheme] = {}
    global_security: list[dict[str, list[str]]] = []


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a JSON pointer $ref like '#/components/parameters/foo'."""
    if not ref.startswith("#/"):
        return {}
    parts = ref[2:].split("/")
    node: Any = root
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part, {})
        else:
            return {}
    return node if isinstance(node, dict) else {}


def _parse_params(
    raw_params: list[dict[str, Any]],
    root: dict[str, Any] | None = None,
) -> list[ParamSpec]:
    out: list[ParamSpec] = []
    for p in raw_params:
        # Resolve $ref if present
        if "$ref" in p and root:
            p = _resolve_ref(p["$ref"], root)
        if "name" not in p:
            continue  # skip unresolvable refs
        schema = p.get("schema", {})
        out.append(ParamSpec(
            name=p["name"],
            location=p.get("in", "query"),
            required=p.get("required", False),
            schema_type=schema.get("type", "string") if isinstance(schema, dict) else "string",
        ))
    return out


def _parse_security_schemes_v3(components: dict[str, Any]) -> dict[str, SecurityScheme]:
    schemes: dict[str, SecurityScheme] = {}
    for name, raw in components.get("securitySchemes", {}).items():
        schemes[name] = SecurityScheme(
            type=raw.get("type", ""),
            name=raw.get("name"),
            location=raw.get("in"),
            scheme=raw.get("scheme"),
        )
    return schemes


def _parse_security_schemes_v2(raw: dict[str, Any]) -> dict[str, SecurityScheme]:
    schemes: dict[str, SecurityScheme] = {}
    for name, defn in raw.get("securityDefinitions", {}).items():
        sec_type = defn.get("type", "")
        # Swagger 2.0 uses "basic" as a type, map to http/basic
        if sec_type == "basic":
            schemes[name] = SecurityScheme(type="http", scheme="basic")
        elif sec_type == "apiKey":
            schemes[name] = SecurityScheme(
                type="apiKey",
                name=defn.get("name"),
                location=defn.get("in"),
            )
        elif sec_type == "oauth2":
            schemes[name] = SecurityScheme(type="oauth2")
        else:
            schemes[name] = SecurityScheme(type=sec_type)
    return schemes


def _build_base_url_v3(raw: dict[str, Any]) -> str:
    servers = raw.get("servers", [])
    if servers:
        return servers[0].get("url", "")
    return ""


def _build_base_url_v2(raw: dict[str, Any]) -> str:
    host = raw.get("host", "")
    base_path = raw.get("basePath", "")
    schemes = raw.get("schemes", ["https"])
    scheme = schemes[0] if schemes else "https"
    if host:
        return f"{scheme}://{host}{base_path}"
    return base_path


HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}


def parse_spec(raw: dict[str, Any]) -> ApiSpec:
    """Parse a raw OpenAPI 3.x or Swagger 2.0 dict into an ApiSpec."""
    is_v2 = raw.get("swagger", "").startswith("2")

    info = raw.get("info", {})
    title = info.get("title", "")
    version = info.get("version", "")

    if is_v2:
        base_url = _build_base_url_v2(raw)
        security_schemes = _parse_security_schemes_v2(raw)
    else:
        base_url = _build_base_url_v3(raw)
        security_schemes = _parse_security_schemes_v3(raw.get("components", {}))

    global_security = raw.get("security", [])

    operations: list[OperationSpec] = []
    for path, path_item in raw.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        # Path-level parameters
        path_params = _parse_params(path_item.get("parameters", []), root=raw)

        for method in HTTP_METHODS:
            op_raw = path_item.get(method)
            if not op_raw or not isinstance(op_raw, dict):
                continue

            # Merge path-level + operation-level params (operation wins)
            op_params = _parse_params(op_raw.get("parameters", []), root=raw)
            seen = {p.name for p in op_params}
            merged = op_params + [p for p in path_params if p.name not in seen]

            has_body = False
            if is_v2:
                has_body = any(p.get("in") == "body" for p in op_raw.get("parameters", []))
            else:
                has_body = "requestBody" in op_raw

            operations.append(OperationSpec(
                method=method.upper(),
                path=path,
                operation_id=op_raw.get("operationId"),
                summary=op_raw.get("summary"),
                parameters=merged,
                has_request_body=has_body,
                security=op_raw.get("security"),
            ))

    return ApiSpec(
        title=title,
        version=version,
        base_url=base_url,
        operations=operations,
        security_schemes=security_schemes,
        global_security=global_security,
    )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

_cache: dict[str, ApiSpec] = {}


def _load_raw(spec_ref: str) -> dict[str, Any]:
    """Load raw dict from URL or file."""
    if spec_ref.startswith(("http://", "https://")):
        resp = httpx.get(spec_ref, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "yaml" in content_type or spec_ref.endswith((".yaml", ".yml")):
            return yaml.safe_load(resp.text)
        return resp.json()

    path = Path(spec_ref).expanduser().resolve()
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    return json.loads(text)


def _resolve_base_url(base_url: str, spec_ref: str) -> str:
    """Resolve a relative server URL against the spec's source URL."""
    if base_url.startswith(("http://", "https://")):
        return base_url
    if spec_ref.startswith(("http://", "https://")):
        parsed = urlparse(spec_ref)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return origin + base_url
    return base_url


def load_spec(spec_ref: str) -> ApiSpec:
    """Load and parse an OpenAPI spec, with in-memory caching."""
    if spec_ref not in _cache:
        raw = _load_raw(spec_ref)
        spec = parse_spec(raw)
        spec.base_url = _resolve_base_url(spec.base_url, spec_ref)
        _cache[spec_ref] = spec
    return _cache[spec_ref]


def clear_cache() -> None:
    _cache.clear()
