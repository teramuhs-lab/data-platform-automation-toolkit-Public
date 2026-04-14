"""Tests for the rollback command.

These tests don't touch a real database. We use unittest.mock to stand in
for the pyodbc connection and cursor, and tmp_path to create fake SQL files.
"""

from unittest.mock import MagicMock, patch

import pytest

from dbops.commands.rollback import (
    ROLLBACK_PATTERN,
    _execute_sql_script,
    _find_rollback_script,
    run_rollback,
)


# -----------------------------------------------------------------------------
# ROLLBACK_PATTERN — the filename regex
# -----------------------------------------------------------------------------


class TestRollbackPattern:
    """Verify the regex matches valid rollback filenames and nothing else."""

    def test_matches_standard_rollback(self):
        match = ROLLBACK_PATTERN.match("V003__rollback__add_email.sql")
        assert match is not None
        assert match.group(1) == "003"
        assert match.group(2) == "add_email"

    def test_does_not_match_forward_migration(self):
        assert ROLLBACK_PATTERN.match("V003__add_email.sql") is None

    def test_does_not_match_repeatable(self):
        assert ROLLBACK_PATTERN.match("R001__seed_data.sql") is None

    def test_does_not_match_random_file(self):
        assert ROLLBACK_PATTERN.match("readme.md") is None

    def test_requires_three_digit_version(self):
        # 2 digits → rejected
        assert ROLLBACK_PATTERN.match("V01__rollback__x.sql") is None
        # 4 digits → rejected
        assert ROLLBACK_PATTERN.match("V0001__rollback__x.sql") is None


# -----------------------------------------------------------------------------
# _find_rollback_script
# -----------------------------------------------------------------------------


class TestFindRollbackScript:
    """Uses monkeypatch to swap MIGRATION_DIR for a temporary folder."""

    def test_finds_existing_rollback(self, tmp_path, monkeypatch):
        # Put a fake rollback file in a temp folder.
        (tmp_path / "V007__rollback__drop_table.sql").write_text("-- rollback")
        monkeypatch.setattr("dbops.commands.rollback.MIGRATION_DIR", tmp_path)

        result = _find_rollback_script("007")
        assert result is not None
        assert result.name == "V007__rollback__drop_table.sql"

    def test_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dbops.commands.rollback.MIGRATION_DIR", tmp_path)
        assert _find_rollback_script("999") is None

    def test_picks_first_alphabetically_when_duplicates(self, tmp_path, monkeypatch):
        # Shouldn't happen in practice, but we want deterministic behavior.
        (tmp_path / "V007__rollback__b.sql").write_text("-- b")
        (tmp_path / "V007__rollback__a.sql").write_text("-- a")
        monkeypatch.setattr("dbops.commands.rollback.MIGRATION_DIR", tmp_path)

        result = _find_rollback_script("007")
        assert result.name == "V007__rollback__a.sql"


# -----------------------------------------------------------------------------
# _execute_sql_script — same shape as in migrate.py but kept local
# -----------------------------------------------------------------------------


class TestExecuteSqlScript:
    def test_splits_on_go_and_executes_batches(self):
        cursor = MagicMock()
        _execute_sql_script(cursor, "DROP TABLE foo;\nGO\nDROP TABLE bar;")
        assert cursor.execute.call_count == 2

    def test_skips_empty_batches(self):
        cursor = MagicMock()
        _execute_sql_script(cursor, "DROP TABLE foo;\nGO\n\nGO\n")
        # Only the first batch has content; the two empty ones are skipped.
        assert cursor.execute.call_count == 1

    def test_go_case_insensitive(self):
        cursor = MagicMock()
        _execute_sql_script(cursor, "DROP TABLE a;\ngo\nDROP TABLE b;")
        assert cursor.execute.call_count == 2


# -----------------------------------------------------------------------------
# run_rollback — end-to-end flow with mocked connection
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_config(tmp_path):
    """A minimal YAML config file that load_config can parse."""
    config_file = tmp_path / "env-test.yml"
    config_file.write_text(
        """
environment: test
sql:
  driver: "ODBC Driver 18 for SQL Server"
  server: "localhost"
  database: "test_db"
  username: "sa"
  password_env: "DBOPS_SQL_PASSWORD"
options:
  encrypt: false
  trust_server_certificate: true
"""
    )
    return str(config_file)


def test_rollback_no_migrations_applied(mock_config, tmp_path, monkeypatch):
    """If migration_history is empty, the command exits cleanly with no work."""
    monkeypatch.setattr("dbops.commands.rollback.MIGRATION_DIR", tmp_path)

    # Cursor returns an empty list when asked for recent migrations.
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with patch("dbops.commands.rollback.get_connection", return_value=conn):
        # Should NOT raise SystemExit — empty history is not an error.
        run_rollback(mock_config, steps=1, dry_run=False)

    cursor.close.assert_called()
    conn.close.assert_called()


def test_rollback_aborts_when_script_missing(mock_config, tmp_path, monkeypatch):
    """If any rollback script is missing, we refuse to proceed."""
    monkeypatch.setattr("dbops.commands.rollback.MIGRATION_DIR", tmp_path)

    cursor = MagicMock()
    # One applied migration, but no rollback file on disk.
    cursor.fetchall.return_value = [("007", "V007__add_thing.sql")]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with patch("dbops.commands.rollback.get_connection", return_value=conn):
        with pytest.raises(SystemExit):
            run_rollback(mock_config, steps=1, dry_run=False)


def test_rollback_dry_run_does_not_execute(mock_config, tmp_path, monkeypatch):
    """Dry run should print the plan but not call any SQL on the rollback."""
    # Create the matching rollback script so dry run has something to show.
    (tmp_path / "V007__rollback__add_thing.sql").write_text("DROP TABLE thing;")
    monkeypatch.setattr("dbops.commands.rollback.MIGRATION_DIR", tmp_path)

    cursor = MagicMock()
    cursor.fetchall.return_value = [("007", "V007__add_thing.sql")]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with patch("dbops.commands.rollback.get_connection", return_value=conn):
        run_rollback(mock_config, steps=1, dry_run=True)

    # Only the SELECT from migration_history should have been called.
    # No DROP TABLE, no DELETE FROM migration_history.
    assert cursor.execute.call_count == 1


def test_rollback_executes_and_deletes_history(mock_config, tmp_path, monkeypatch):
    """Happy path: rollback SQL runs, history row is deleted."""
    (tmp_path / "V007__rollback__add_thing.sql").write_text("DROP TABLE thing;")
    monkeypatch.setattr("dbops.commands.rollback.MIGRATION_DIR", tmp_path)

    cursor = MagicMock()
    cursor.fetchall.return_value = [("007", "V007__add_thing.sql")]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with patch("dbops.commands.rollback.get_connection", return_value=conn):
        run_rollback(mock_config, steps=1, dry_run=False)

    # Expected calls: SELECT + DROP TABLE + DELETE FROM migration_history = 3
    assert cursor.execute.call_count == 3
