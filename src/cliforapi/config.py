"""Manage ~/.cliforapi/ configuration directory."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


CONFIG_DIR = Path.home() / ".cliforapi"


def ensure_config_dir() -> Path:
    """Create the config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def domain_from_spec(spec_ref: str) -> str:
    """Derive a domain/filename key from a spec URL or local file path.

    URLs  → hostname  (e.g. "api.example.com")
    Files → stem      (e.g. "petstore" from "./petstore.yaml")
    """
    if spec_ref.startswith(("http://", "https://")):
        parsed = urlparse(spec_ref)
        return parsed.hostname or "unknown"
    # Local file — use the filename stem, sanitised
    stem = Path(spec_ref).stem
    return re.sub(r"[^\w.-]", "_", stem)


def env_path_for(spec_ref: str) -> Path:
    """Return the .env file path for a given spec reference."""
    return ensure_config_dir() / f"{domain_from_spec(spec_ref)}.env"
