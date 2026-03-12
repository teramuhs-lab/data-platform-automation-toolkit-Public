"""Tests for the database migration runner."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from dbops.commands.migrate import (
    _checksum,
    _parse_script_name,
    _get_applied_versions,
    _execute_sql_script,
    MIGRATION_DIR,
    SEED_DIR,
    VERSION_PATTERN,
)


# -------------------------------------------------------------------
# _parse_script_name
# -------------------------------------------------------------------

class TestParseScriptName:
    def test_valid_versioned(self):
        result = _parse_script_name("V001__create_tables.sql")
        assert result == {
            "type": "V",
            "version": "001",
            "description": "create_tables",
            "filename": "V001__create_tables.sql",
        }

    def test_valid_repeatable(self):
        result = _parse_script_name("R001__seed_data.sql")
        assert result["type"] == "R"
        assert result["version"] == "001"

    def test_invalid_name_returns_none(self):
        assert _parse_script_name("random_file.sql") is None

    def test_invalid_no_double_underscore(self):
        assert _parse_script_name("V001_missing_underscore.sql") is None

    def test_invalid_too_few_digits(self):
        assert _parse_script_name("V01__short.sql") is None


# -------------------------------------------------------------------
# _checksum
# -------------------------------------------------------------------

class TestChecksum:
    def test_returns_sha256(self, tmp_path):
        sql_file = tmp_path / "V001__test.sql"
        sql_file.write_text("SELECT 1;", encoding="utf-8")

        expected = hashlib.sha256(b"SELECT 1;").hexdigest()
        assert _checksum(sql_file) == expected

    def test_different_content_different_checksum(self, tmp_path):
        file_a = tmp_path / "a.sql"
        file_b = tmp_path / "b.sql"
        file_a.write_text("SELECT 1;", encoding="utf-8")
        file_b.write_text("SELECT 2;", encoding="utf-8")

        assert _checksum(file_a) != _checksum(file_b)


# -------------------------------------------------------------------
# _get_applied_versions
# -------------------------------------------------------------------

class TestGetAppliedVersions:
    def test_returns_dict_of_version_checksum(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ("001", "abc123"),
            ("002", "def456"),
        ]
        result = _get_applied_versions(cursor)
        assert result == {"001": "abc123", "002": "def456"}

    def test_returns_empty_dict_when_table_missing(self):
        cursor = MagicMock()
        cursor.execute.side_effect = Exception("Invalid object name")
        result = _get_applied_versions(cursor)
        assert result == {}


# -------------------------------------------------------------------
# _execute_sql_script
# -------------------------------------------------------------------

class TestExecuteSqlScript:
    def test_splits_on_go_and_executes_batches(self):
        cursor = MagicMock()
        sql = "SELECT 1;\nGO\nSELECT 2;"
        _execute_sql_script(cursor, sql)
        assert cursor.execute.call_count == 2

    def test_skips_empty_batches(self):
        cursor = MagicMock()
        sql = "SELECT 1;\nGO\n\nGO\nSELECT 2;"
        _execute_sql_script(cursor, sql)
        assert cursor.execute.call_count == 2

    def test_single_batch_no_go(self):
        cursor = MagicMock()
        sql = "CREATE TABLE test (id INT);"
        _execute_sql_script(cursor, sql)
        cursor.execute.assert_called_once()

    def test_go_case_insensitive(self):
        cursor = MagicMock()
        sql = "SELECT 1;\ngo\nSELECT 2;\nGo\nSELECT 3;"
        _execute_sql_script(cursor, sql)
        assert cursor.execute.call_count == 3


# -------------------------------------------------------------------
# VERSION_PATTERN regex
# -------------------------------------------------------------------

class TestVersionPattern:
    @pytest.mark.parametrize("filename,expected_match", [
        ("V001__create_migration_tracking.sql", True),
        ("V999__final.sql", True),
        ("R001__seed_environments.sql", True),
        ("V01__too_short.sql", False),
        ("V0001__too_long.sql", False),
        ("X001__wrong_prefix.sql", False),
        ("V001_single_underscore.sql", False),
        ("V001__no_extension", False),
        ("readme.md", False),
    ])
    def test_pattern(self, filename, expected_match):
        match = VERSION_PATTERN.match(filename)
        assert bool(match) == expected_match


# -------------------------------------------------------------------
# Migration directory constants
# -------------------------------------------------------------------

class TestConstants:
    def test_migration_dir_path(self):
        assert MIGRATION_DIR == Path("database/migrations")

    def test_seed_dir_path(self):
        assert SEED_DIR == Path("database/seed-data")
