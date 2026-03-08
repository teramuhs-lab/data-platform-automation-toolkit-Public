"""Configuration loader for environment-specific YAML settings."""

import os
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file and resolve env var references."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    # Resolve password from environment variable
    password_env = config.get("sql", {}).get("password_env")
    if password_env:
        config["sql"]["password"] = os.environ.get(password_env, "")

    return config
