"""Resolve private assets (system prompt, mappings) from outside the repository."""
from __future__ import annotations

import os
from pathlib import Path


def resolve_private_path(env_var: str, default: Path, label: str) -> Path:
    """Return a private asset path from env var or default location."""
    env_value = os.getenv(env_var)
    if env_value:
        return Path(env_value)
    if default.exists():
        return default
    raise FileNotFoundError(
        f"No {label} found. Set {env_var} or create {default}."
    )
