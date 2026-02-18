"""Auth detection, credential storage, and precedence-chain resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from .config import env_path_for
from .spec import ApiSpec, SecurityScheme


@dataclass
class ResolvedAuth:
    """Resolved credentials ready to apply to an HTTP request."""
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# .env persistence (used by `cliforapi auth`)
# ---------------------------------------------------------------------------

def save_credentials(spec_ref: str, credentials: dict[str, str]) -> Path:
    """Write credentials to the domain-specific .env file."""
    env_file = env_path_for(spec_ref)
    lines: list[str] = []
    for key, value in credentials.items():
        # Simple .env quoting
        escaped = value.replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')
    env_file.write_text("\n".join(lines) + "\n")
    return env_file


def load_env_credentials(spec_ref: str) -> dict[str, str]:
    """Load credentials from the domain-specific .env file."""
    env_file = env_path_for(spec_ref)
    if not env_file.exists():
        return {}
    return {k: v for k, v in dotenv_values(env_file).items() if v is not None}


# ---------------------------------------------------------------------------
# Interactive auth setup (the only interactive command)
# ---------------------------------------------------------------------------

def detect_auth_requirements(spec: ApiSpec) -> list[tuple[str, SecurityScheme]]:
    """Return (name, scheme) pairs for security schemes the spec declares."""
    return list(spec.security_schemes.items())


def prompt_for_credentials(schemes: list[tuple[str, SecurityScheme]]) -> dict[str, str]:
    """Interactively prompt the user for credentials based on security schemes."""
    credentials: dict[str, str] = {}

    for name, scheme in schemes:
        if scheme.type == "http" and scheme.scheme == "bearer":
            token = input(f"Bearer token for '{name}': ").strip()
            credentials["BEARER_TOKEN"] = token

        elif scheme.type == "http" and scheme.scheme == "basic":
            username = input(f"Username for '{name}': ").strip()
            password = input(f"Password for '{name}': ").strip()
            credentials["BASIC_USERNAME"] = username
            credentials["BASIC_PASSWORD"] = password

        elif scheme.type == "apiKey":
            param_name = scheme.name or name
            value = input(f"API key ({param_name}): ").strip()
            credentials[f"API_KEY_{param_name.upper()}"] = value

        elif scheme.type == "oauth2":
            token = input(f"OAuth2 access token for '{name}': ").strip()
            credentials["OAUTH_TOKEN"] = token

    return credentials


# ---------------------------------------------------------------------------
# Auth resolution: CLI flags > env vars > .env file
# ---------------------------------------------------------------------------

def resolve_auth(
    spec: ApiSpec,
    spec_ref: str,
    cli_token: str | None = None,
    cli_api_key: str | None = None,
    cli_username: str | None = None,
    cli_password: str | None = None,
) -> ResolvedAuth:
    """Resolve auth credentials using the precedence chain.

    Priority: CLI flags > environment variables > .env file
    """
    env_creds = load_env_credentials(spec_ref)
    auth = ResolvedAuth()

    for _name, scheme in spec.security_schemes.items():
        if scheme.type == "http" and scheme.scheme == "bearer":
            token = (
                cli_token
                or os.environ.get("CLIFORAPI_BEARER_TOKEN")
                or env_creds.get("BEARER_TOKEN")
                or env_creds.get("OAUTH_TOKEN")
            )
            if token:
                auth.headers["Authorization"] = f"Bearer {token}"

        elif scheme.type == "http" and scheme.scheme == "basic":
            import base64
            username = (
                cli_username
                or os.environ.get("CLIFORAPI_BASIC_USERNAME")
                or env_creds.get("BASIC_USERNAME")
                or ""
            )
            password = (
                cli_password
                or os.environ.get("CLIFORAPI_BASIC_PASSWORD")
                or env_creds.get("BASIC_PASSWORD")
                or ""
            )
            if username:
                encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
                auth.headers["Authorization"] = f"Basic {encoded}"

        elif scheme.type == "apiKey":
            param_name = scheme.name or "api_key"
            env_key = f"API_KEY_{param_name.upper()}"
            value = (
                cli_api_key
                or os.environ.get(f"CLIFORAPI_{env_key}")
                or env_creds.get(env_key)
            )
            if value:
                if scheme.location == "header":
                    auth.headers[param_name] = value
                elif scheme.location == "query":
                    auth.query_params[param_name] = value

        elif scheme.type == "oauth2":
            token = (
                cli_token
                or os.environ.get("CLIFORAPI_BEARER_TOKEN")
                or env_creds.get("OAUTH_TOKEN")
                or env_creds.get("BEARER_TOKEN")
            )
            if token:
                auth.headers["Authorization"] = f"Bearer {token}"

    # CLI flags always apply, even if the spec declares no security schemes
    if "Authorization" not in auth.headers:
        token = cli_token or os.environ.get("CLIFORAPI_BEARER_TOKEN")
        if token:
            auth.headers["Authorization"] = f"Bearer {token}"

    if cli_api_key and not any(v == cli_api_key for v in auth.headers.values()):
        auth.headers["Authorization"] = f"Bearer {cli_api_key}"

    return auth
