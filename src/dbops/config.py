"""Configuration loader for environment-specific YAML settings.

How configuration works in this project:

  1. Each environment has its own YAML file in config/ (env-dev.yml, etc.)
  2. The YAML can reference environment variables with ${VAR_NAME} — these
     get filled in from the real shell environment at load time.
  3. The SQL password is special: the YAML stores the *name* of the env var
     holding it (in `password_env`), and we look up the actual value here.

Why two patterns? The ${VAR_NAME} style is generic (works on any field).
The password_env indirection exists for backwards compatibility with older
configs. Either works for the password.
"""

import os
import re
from pathlib import Path

import yaml


def _resolve_env_vars(value):
    """Recursively replace ${VAR_NAME} references with real env var values.

    The config might be a dict, a list, a string, or anything else. We walk
    the whole structure, and for any string that looks like "${SOMETHING}"
    (even if it's just part of a longer string like "prefix-${X}-suffix"),
    we substitute the matching environment variable.

    If a referenced variable isn't set, we leave the ${NAME} placeholder
    as-is — better than silently injecting an empty string.
    """
    # Strings are the only thing we actually substitute into.
    if isinstance(value, str):
        # re.sub finds every ${WORD} match and replaces it using the lambda.
        # os.environ.get returns the env var value, or the original placeholder
        # (m.group(0)) if the variable isn't defined.
        return re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )

    # Dicts — walk every value (keys don't need substitution).
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}

    # Lists — walk every element.
    if isinstance(value, list):
        return [_resolve_env_vars(v) for v in value]

    # Anything else (int, bool, None) — return as-is.
    return value


def load_config(config_path: str) -> dict:
    """Read a YAML config file and resolve environment variable references.

    Returns a plain Python dict. The dict will always have:
      config["sql"]["server"]   — hostname
      config["sql"]["database"] — database name
      config["sql"]["username"] — login name
      config["sql"]["password"] — password (resolved from env)
    """
    # Fail loudly if someone points at a missing file.
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # yaml.safe_load parses YAML into Python types (dict, list, str, int).
    # "safe" means it refuses to construct arbitrary Python objects —
    # important if you ever load YAML from an untrusted source.
    with open(path) as f:
        config = yaml.safe_load(f)

    # Substitute every ${VAR_NAME} in the whole config tree.
    config = _resolve_env_vars(config)

    # Special case: if the config says password_env: DBOPS_SQL_PASSWORD,
    # read the actual password from that env var and store it at sql.password.
    # Missing env var → empty string (connection will fail with a clear error).
    password_env = config.get("sql", {}).get("password_env")
    if password_env:
        config["sql"]["password"] = os.environ.get(password_env, "")

    return config
