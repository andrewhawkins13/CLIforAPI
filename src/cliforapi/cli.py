"""Click entry point — dynamic command routing, auth, and list subcommands."""

from __future__ import annotations

import json
import sys

import click

from . import __version__
from .auth import (
    detect_auth_requirements,
    prompt_for_credentials,
    resolve_auth,
    save_credentials,
)
from .client import ApiResponse, NetworkError, execute
from .output import (
    EXIT_AUTH_ERROR,
    EXIT_CLI_ERROR,
    EXIT_NETWORK,
    encode_json,
    encode_toon,
    exit_code_for_status,
    format_error,
    print_error,
    print_response,
)
from .resolver import ResolutionError, resolve
from .spec import ApiSpec, load_spec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_or_fail(spec_ref: str) -> ApiSpec:
    try:
        return load_spec(spec_ref)
    except FileNotFoundError:
        print_error("SPEC_NOT_FOUND", f"Spec file not found: {spec_ref}")
        sys.exit(EXIT_CLI_ERROR)
    except Exception as e:
        print_error("SPEC_LOAD_ERROR", f"Failed to load spec: {e}")
        sys.exit(EXIT_CLI_ERROR)


def _parse_extra_params(args: tuple[str, ...]) -> tuple[dict[str, str], str | None]:
    """Parse remaining Click args into param dict + optional body string.

    Expects pairs like: --name value --body '{...}'
    """
    params: dict[str, str] = {}
    body: str | None = None
    i = 0
    args_list = list(args)
    while i < len(args_list):
        arg = args_list[i]
        if arg.startswith("--"):
            key = arg.lstrip("-")
            if i + 1 < len(args_list) and not args_list[i + 1].startswith("--"):
                value = args_list[i + 1]
                i += 2
            else:
                value = "true"
                i += 1
            if key == "body":
                body = value
            else:
                params[key] = value
        else:
            i += 1
    return params, body


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--spec", required=False, help="OpenAPI spec URL or file path")
@click.option("--json-output", "--json", "use_json", is_flag=True, help="Output raw JSON instead of TOON")
@click.option("--token", default=None, help="Bearer token for auth")
@click.option("--api-key", default=None, help="API key for auth")
@click.option("--timeout", default=30.0, type=float, help="Request timeout in seconds")
@click.version_option(__version__)
@click.pass_context
def main(ctx: click.Context, spec: str | None, use_json: bool, token: str | None, api_key: str | None, timeout: float) -> None:
    """cliforapi — Universal CLI for any OpenAPI spec."""
    ctx.ensure_object(dict)
    ctx.obj["spec_ref"] = spec
    ctx.obj["use_json"] = use_json
    ctx.obj["token"] = token
    ctx.obj["api_key"] = api_key
    ctx.obj["timeout"] = timeout

    if ctx.invoked_subcommand is None:
        # No subcommand — print help
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# `auth` subcommand (interactive)
# ---------------------------------------------------------------------------

@main.command()
@click.option("--spec", required=True, help="OpenAPI spec URL or file path")
@click.pass_context
def auth(ctx: click.Context, spec: str) -> None:
    """Set up auth credentials for an API (interactive)."""
    api_spec = _load_or_fail(spec)
    schemes = detect_auth_requirements(api_spec)

    if not schemes:
        click.echo("This API does not declare any security schemes.")
        return

    click.echo(f"Detected {len(schemes)} security scheme(s):")
    for name, scheme in schemes:
        click.echo(f"  - {name}: {scheme.type}" + (f" ({scheme.scheme})" if scheme.scheme else ""))

    credentials = prompt_for_credentials(schemes)
    if credentials:
        env_path = save_credentials(spec, credentials)
        click.echo(f"\nCredentials saved to {env_path}")

        from .config import protect_credentials
        warning = protect_credentials(env_path)
        if warning:
            click.echo(click.style(warning, fg="yellow"), err=True)
        else:
            click.echo("Added *.env to .gitignore to protect credentials.")
    else:
        click.echo("\nNo credentials provided.")


# ---------------------------------------------------------------------------
# `list` subcommand
# ---------------------------------------------------------------------------

@main.command(name="list")
@click.pass_context
def list_endpoints(ctx: click.Context) -> None:
    """List all available endpoints from the spec."""
    spec_ref = ctx.obj.get("spec_ref")
    if not spec_ref:
        print_error("SPEC_REQUIRED", "The --spec option is required. Usage: cliforapi --spec <url> list")
        sys.exit(EXIT_CLI_ERROR)

    use_json = ctx.obj.get("use_json", False)
    api_spec = _load_or_fail(spec_ref)

    endpoints = []
    for op in api_spec.operations:
        endpoints.append({
            "method": op.method,
            "path": op.path,
            "summary": op.summary or "",
        })

    endpoints.sort(key=lambda e: (e["path"], e["method"]))

    if use_json:
        print(json.dumps(endpoints, indent=2))
    else:
        # TOON tabular format
        cols = ["method", "path", "summary"]
        print(f"endpoints[{len(endpoints)}]{{{','.join(cols)}}}:")
        for ep in endpoints:
            vals = [ep[c] for c in cols]
            print(" " + ",".join(vals))


# ---------------------------------------------------------------------------
# HTTP method commands (get, post, put, delete, patch, options, head)
# ---------------------------------------------------------------------------

def _make_method_command(method: str) -> click.Command:
    @click.command(
        name=method,
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )
    @click.argument("path")
    @click.pass_context
    def method_cmd(ctx: click.Context, path: str) -> None:
        parent = ctx.parent
        if parent is None:
            print_error("INTERNAL", "Missing parent context")
            sys.exit(EXIT_CLI_ERROR)

        spec_ref = parent.obj.get("spec_ref")
        if not spec_ref:
            print_error("SPEC_REQUIRED", "The --spec option is required. Usage: cliforapi --spec <url> get /path")
            sys.exit(EXIT_CLI_ERROR)

        use_json = parent.obj.get("use_json", False)
        token = parent.obj.get("token")
        api_key_val = parent.obj.get("api_key")
        timeout = parent.obj.get("timeout", 30.0)

        api_spec = _load_or_fail(spec_ref)

        # Parse extra args
        params, body_str = _parse_extra_params(tuple(ctx.args))

        # Resolve route
        try:
            request = resolve(method.upper(), path, params, body_str, api_spec)
        except ResolutionError as e:
            print_error(e.code, e.message)
            sys.exit(EXIT_CLI_ERROR)

        # Resolve auth
        resolved_auth = resolve_auth(
            api_spec, spec_ref,
            cli_token=token,
            cli_api_key=api_key_val,
        )

        # Execute
        try:
            response = execute(request, api_spec.base_url, auth=resolved_auth, timeout=timeout)
        except NetworkError as e:
            print_error("NETWORK_ERROR", e.message)
            sys.exit(EXIT_NETWORK)

        exit_code = print_response(response, use_json=use_json)
        sys.exit(exit_code)

    method_cmd.__doc__ = f"Execute an HTTP {method.upper()} request."
    return method_cmd


for _method in ("get", "post", "put", "delete", "patch", "options", "head"):
    main.add_command(_make_method_command(_method))
