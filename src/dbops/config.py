"""Configuration loader for environment-specific YAML settings."""

import os
import re
from pathlib import Path

import yaml


def _resolve_env_vars(value):
    """Replace ${VAR_NAME} patterns with environment variable values."""
    if isinstance(value, str):
        return re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(v) for v in value]
    return value


def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file and resolve env var references."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    # Resolve ${VAR} references throughout the config
    config = _resolve_env_vars(config)

    # Resolve password from environment variable
    password_env = config.get("sql", {}).get("password_env")
    if password_env:
        config["sql"]["password"] = os.environ.get(password_env, "")

    return config
