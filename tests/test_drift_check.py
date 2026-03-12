"""Tests for the schema drift detection command."""

from unittest.mock import MagicMock, patch

import pytest

from dbops.commands.drift_check import (
    _get_live_schemas,
    _get_live_tables,
    _get_live_procedures,
    EXPECTED_SCHEMA,
)


# -------------------------------------------------------------------
# EXPECTED_SCHEMA structure
# -------------------------------------------------------------------

class TestExpectedSchema:
    def test_has_schemas(self):
        assert "dbops" in EXPECTED_SCHEMA["schemas"]
        assert "inventory" in EXPECTED_SCHEMA["schemas"]

    def test_has_tables(self):
        assert "dbops.migration_history" in EXPECTED_SCHEMA["tables"]
        assert "inventory.servers" in EXPECTED_SCHEMA["tables"]
        assert "inventory.environments" in EXPECTED_SCHEMA["tables"]
        assert "inventory.databases" in EXPECTED_SCHEMA["tables"]
        assert "inventory.backup_history" in EXPECTED_SCHEMA["tables"]
        assert "inventory.alert_rules" in EXPECTED_SCHEMA["tables"]
        assert "inventory.incidents" in EXPECTED_SCHEMA["tables"]

    def test_has_procedures(self):
        assert "inventory.usp_register_backup" in EXPECTED_SCHEMA["procedures"]
        assert "inventory.usp_get_stale_backups" in EXPECTED_SCHEMA["procedures"]
        assert "inventory.usp_raise_incident" in EXPECTED_SCHEMA["procedures"]

    def test_table_columns_are_lists(self):
        for table, columns in EXPECTED_SCHEMA["tables"].items():
            assert isinstance(columns, list), f"{table} columns should be a list"
            assert len(columns) > 0, f"{table} should have at least one column"


# -------------------------------------------------------------------
# _get_live_schemas
# -------------------------------------------------------------------

class TestGetLiveSchemas:
    def test_returns_schema_names(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("dbops",), ("inventory",)]
        result = _get_live_schemas(cursor)
        assert result == ["dbops", "inventory"]

    def test_empty_when_no_schemas(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        result = _get_live_schemas(cursor)
        assert result == []


# -------------------------------------------------------------------
# _get_live_tables
# -------------------------------------------------------------------

class TestGetLiveTables:
    def test_returns_tables_with_columns(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ("inventory.servers", "server_id"),
            ("inventory.servers", "hostname"),
            ("inventory.environments", "environment_id"),
            ("inventory.environments", "name"),
        ]
        result = _get_live_tables(cursor)
        assert "inventory.servers" in result
        assert result["inventory.servers"] == ["server_id", "hostname"]
        assert result["inventory.environments"] == ["environment_id", "name"]

    def test_empty_when_no_tables(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        result = _get_live_tables(cursor)
        assert result == {}


# -------------------------------------------------------------------
# _get_live_procedures
# -------------------------------------------------------------------

class TestGetLiveProcedures:
    def test_returns_procedure_names(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ("inventory.usp_register_backup",),
            ("inventory.usp_get_stale_backups",),
            ("inventory.usp_raise_incident",),
        ]
        result = _get_live_procedures(cursor)
        assert len(result) == 3
        assert "inventory.usp_register_backup" in result

    def test_empty_when_no_procs(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        result = _get_live_procedures(cursor)
        assert result == []
