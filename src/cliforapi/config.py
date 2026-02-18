"""Manage ~/.cliforapi/ configuration directory."""

from __future__ import annotations

import re
import subprocess
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


def _is_git_repo(path: Path) -> bool:
    """Check if the given path is inside a git work tree."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # git not installed
        return False


def _gitignore_contains(gitignore: Path, pattern: str) -> bool:
    """Check if a .gitignore already contains the given pattern."""
    if not gitignore.exists():
        return False
    return pattern in gitignore.read_text().splitlines()


def protect_credentials(env_path: Path) -> str | None:
    """Ensure credentials won't be accidentally committed to git.

    Returns a warning message if the config dir is NOT in a git repo,
    or None if it is and was protected (or already protected).
    """
    config_dir = env_path.parent

    if _is_git_repo(config_dir):
        gitignore = config_dir / ".gitignore"
        pattern = "*.env"
        if not _gitignore_contains(gitignore, pattern):
            with gitignore.open("a") as f:
                if gitignore.exists() and gitignore.read_text() and not gitignore.read_text().endswith("\n"):
                    f.write("\n")
                f.write(f"{pattern}\n")
        return None

    return (
        f"Warning: {config_dir} is not inside a git repository. "
        f"Credentials are stored in plain text at {env_path}. "
        f"Do not copy this file into a git repo."
    )
