"""Tests for the health check command (mocked DB calls)."""

import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from dbops.commands.healthcheck import run_healthcheck, HEALTH_CHECKS


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config YAML file for testing."""
    config = {
        "environment": "test",
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
    }
    path = tmp_path / "env-test.yml"
    path.write_text(yaml.dump(config))
    os.environ["DBOPS_SQL_PASSWORD"] = "TestPass123"
    yield str(path)
    os.environ.pop("DBOPS_SQL_PASSWORD", None)


def test_health_checks_has_expected_sections():
    """Verify HEALTH_CHECKS contains all expected check names."""
    expected = [
        "Server Identity",
        "Database List",
        "Disk Space (xp_fixeddrives)",
        "AG Replica Status",
        "Top 5 Wait Stats",
    ]
    for name in expected:
        assert name in HEALTH_CHECKS


def test_health_checks_queries_are_strings():
    """Verify all health check values are SQL query strings."""
    for label, query in HEALTH_CHECKS.items():
        assert isinstance(query, str), f"{label} query is not a string"
        assert len(query.strip()) > 0, f"{label} query is empty"


@patch("dbops.commands.healthcheck.get_connection")
def test_healthcheck_connects_successfully(mock_get_conn, config_file):
    """Verify healthcheck connects and runs queries without error."""
    # Mock cursor with fake query results
    mock_cursor = MagicMock()
    mock_cursor.description = [("server_name",), ("server_version",)]
    mock_cursor.fetchall.return_value = [("TestServer", "SQL Server 2022")]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    # Should complete without raising
    run_healthcheck(config_file)

    mock_get_conn.assert_called_once()
    mock_conn.cursor.assert_called_once()
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("dbops.commands.healthcheck.get_connection")
def test_healthcheck_runs_all_queries(mock_get_conn, config_file):
    """Verify healthcheck executes a query for each health check."""
    mock_cursor = MagicMock()
    mock_cursor.description = [("col1",)]
    mock_cursor.fetchall.return_value = [("value1",)]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    run_healthcheck(config_file)

    # cursor.execute should be called once per health check
    assert mock_cursor.execute.call_count == len(HEALTH_CHECKS)


@patch(
    "dbops.commands.healthcheck.get_connection",
    side_effect=Exception("Connection refused"),
)
def test_healthcheck_exits_on_connection_failure(mock_get_conn, config_file):
    """Verify healthcheck exits with code 1 when connection fails."""
    with pytest.raises(SystemExit) as exc_info:
        run_healthcheck(config_file)
    assert exc_info.value.code == 1


@patch("dbops.commands.healthcheck.get_connection")
def test_healthcheck_handles_query_failure_gracefully(mock_get_conn, config_file):
    """Verify healthcheck skips a query that throws an exception."""
    mock_cursor = MagicMock()
    # First query succeeds, rest raise errors
    mock_cursor.execute.side_effect = [
        None,  # Server Identity succeeds
        Exception("permission denied"),  # Database List fails
        Exception("permission denied"),  # Disk Space fails
        Exception("permission denied"),  # AG Status fails
        Exception("permission denied"),  # Wait Stats fails
    ]
    mock_cursor.description = [("col1",)]
    mock_cursor.fetchall.return_value = [("value1",)]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    # Should NOT raise -- errors are caught and skipped
    run_healthcheck(config_file)
    mock_cursor.close.assert_called_once()


@patch("dbops.commands.healthcheck.get_connection")
@patch("dbops.commands.healthcheck.is_json_mode", return_value=True)
@patch("dbops.commands.healthcheck.flush_json")
@patch("dbops.commands.healthcheck.add_json_result")
def test_healthcheck_json_mode_collects_results(
    mock_add, mock_flush, mock_json_mode, mock_get_conn, config_file
):
    """Verify healthcheck adds JSON results and flushes in JSON mode."""
    mock_cursor = MagicMock()
    mock_cursor.description = [("col1",)]
    mock_cursor.fetchall.return_value = [("value1",)]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    run_healthcheck(config_file)

    # Should have: connectivity + 5 checks + summary = 7 calls
    assert mock_add.call_count == 7
    mock_flush.assert_called_once()
