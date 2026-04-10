"""Tests for database connection string builder."""

import pytest
from unittest.mock import patch, MagicMock

from dbops.db import build_connection_string, get_connection


@pytest.fixture
def sample_config():
    """Standard dev config for testing."""
    return {
        "sql": {
            "driver": "ODBC Driver 18 for SQL Server",
            "server": "127.0.0.1,1433",
            "database": "master",
            "username": "sa",
            "password": "TestPass123",
        },
        "options": {
            "encrypt": False,
            "trust_server_certificate": True,
        },
    }


def test_build_connection_string_contains_driver(sample_config):
    """Verify connection string includes the ODBC driver."""
    conn_str = build_connection_string(sample_config)
    assert "DRIVER={ODBC Driver 18 for SQL Server}" in conn_str


def test_build_connection_string_contains_server(sample_config):
    """Verify connection string includes the server."""
    conn_str = build_connection_string(sample_config)
    assert "SERVER=127.0.0.1,1433" in conn_str


def test_build_connection_string_contains_database(sample_config):
    """Verify connection string includes the database."""
    conn_str = build_connection_string(sample_config)
    assert "DATABASE=master" in conn_str


def test_build_connection_string_contains_credentials(sample_config):
    """Verify connection string includes UID and PWD."""
    conn_str = build_connection_string(sample_config)
    assert "UID=sa" in conn_str
    assert "PWD=TestPass123" in conn_str


def test_build_connection_string_encrypt_no(sample_config):
    """Verify Encrypt=no when encrypt is False."""
    conn_str = build_connection_string(sample_config)
    assert "Encrypt=no" in conn_str


def test_build_connection_string_encrypt_yes(sample_config):
    """Verify Encrypt=yes when encrypt is True."""
    sample_config["options"]["encrypt"] = True
    conn_str = build_connection_string(sample_config)
    assert "Encrypt=yes" in conn_str


def test_build_connection_string_trust_cert_yes(sample_config):
    """Verify TrustServerCertificate=yes when enabled."""
    conn_str = build_connection_string(sample_config)
    assert "TrustServerCertificate=yes" in conn_str


def test_build_connection_string_trust_cert_no(sample_config):
    """Verify TrustServerCertificate=no when disabled."""
    sample_config["options"]["trust_server_certificate"] = False
    conn_str = build_connection_string(sample_config)
    assert "TrustServerCertificate=no" in conn_str


def test_build_connection_string_no_options_uses_defaults(sample_config):
    """Verify defaults when options section is missing."""
    del sample_config["options"]
    conn_str = build_connection_string(sample_config)
    assert "Encrypt=no" in conn_str
    assert "TrustServerCertificate=yes" in conn_str


@patch("dbops.db.pyodbc.connect")
def test_get_connection_calls_pyodbc(mock_connect, sample_config):
    """Verify get_connection calls pyodbc.connect with the right string."""
    mock_connect.return_value = MagicMock()
    get_connection(sample_config)
    mock_connect.assert_called_once()
    call_args = mock_connect.call_args
    assert "DRIVER={ODBC Driver 18 for SQL Server}" in call_args[0][0]
    assert call_args[1]["timeout"] == 30


@patch("dbops.db.pyodbc.connect", side_effect=Exception("Connection refused"))
def test_get_connection_raises_on_failure(mock_connect, sample_config):
    """Verify get_connection propagates connection errors."""
    with pytest.raises(Exception, match="Connection refused"):
        get_connection(sample_config)
