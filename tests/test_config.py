"""Tests for configuration loading."""

import os

import pytest
import yaml

from dbops.config import load_config


@pytest.fixture
def dev_config_file(tmp_path):
    """Create a temporary dev config YAML file."""
    config = {
        "environment": "dev",
        "sql": {
            "driver": "ODBC Driver 18 for SQL Server",
            "server": "127.0.0.1,1433",
            "database": "master",
            "username": "sa",
            "password_env": "DBOPS_SQL_PASSWORD",
        },
        "options": {
            "encrypt": False,
            "trust_server_certificate": True,
        },
        "backup": {
            "backup_dir": "/backups",
        },
    }
    path = tmp_path / "env-dev.yml"
    path.write_text(yaml.dump(config))
    return str(path)


def test_load_config_returns_dict(dev_config_file):
    """Verify that load_config returns a dictionary."""
    os.environ["DBOPS_SQL_PASSWORD"] = "TestPass123"
    config = load_config(dev_config_file)
    assert isinstance(config, dict)
    os.environ.pop("DBOPS_SQL_PASSWORD", None)


def test_load_config_has_sql_section(dev_config_file):
    """Verify config contains the sql section with expected keys."""
    os.environ["DBOPS_SQL_PASSWORD"] = "TestPass123"
    config = load_config(dev_config_file)
    assert "sql" in config
    assert config["sql"]["server"] == "127.0.0.1,1433"
    assert config["sql"]["database"] == "master"
    assert config["sql"]["username"] == "sa"
    os.environ.pop("DBOPS_SQL_PASSWORD", None)


def test_load_config_resolves_password_from_env(dev_config_file):
    """Verify that password_env is resolved from the environment."""
    os.environ["DBOPS_SQL_PASSWORD"] = "SecretPass456"
    config = load_config(dev_config_file)
    assert config["sql"]["password"] == "SecretPass456"
    os.environ.pop("DBOPS_SQL_PASSWORD", None)


def test_load_config_missing_env_returns_empty_string(dev_config_file):
    """Verify that a missing env var resolves to empty string."""
    os.environ.pop("DBOPS_SQL_PASSWORD", None)
    config = load_config(dev_config_file)
    assert config["sql"]["password"] == ""


def test_load_config_missing_file_raises_error():
    """Verify that a missing config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/env-dev.yml")


def test_load_config_has_options_section(dev_config_file):
    """Verify config contains the options section."""
    os.environ["DBOPS_SQL_PASSWORD"] = "TestPass123"
    config = load_config(dev_config_file)
    assert config["options"]["encrypt"] is False
    assert config["options"]["trust_server_certificate"] is True
    os.environ.pop("DBOPS_SQL_PASSWORD", None)


def test_load_config_has_backup_section(dev_config_file):
    """Verify config contains the backup section."""
    os.environ["DBOPS_SQL_PASSWORD"] = "TestPass123"
    config = load_config(dev_config_file)
    assert config["backup"]["backup_dir"] == "/backups"
    os.environ.pop("DBOPS_SQL_PASSWORD", None)
