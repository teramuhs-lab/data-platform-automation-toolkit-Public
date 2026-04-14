"""Database migration runner — the heart of the toolkit.

What a "migration" is:
  A SQL script that changes the database schema (CREATE TABLE, ALTER TABLE,
  CREATE PROCEDURE, etc.). Migrations are version-controlled and applied
  in order, so every environment ends up with the same schema.

Naming convention (Flyway-inspired):
  V###__description.sql   → Versioned. Run once. Tracked by checksum.
                            Example: V001__create_users_table.sql
  R###__description.sql   → Repeatable. Run every deploy. Used for seed
                            data, views, procedures that can be re-applied.
                            Example: R001__seed_environments.sql

How we remember what's been run:
  After each successful migration, we insert a row into
  dbops.migration_history (version, checksum, applied_on, success).
  Next run, we read that table to skip already-applied scripts.

Safety check — checksums:
  If someone edits an already-applied V-script, the checksum on disk won't
  match what's in the history table. We catch that and fail loudly so
  nobody silently drifts between environments.
"""

import hashlib
import re
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dbops.config import load_config
from dbops.db import ensure_database, get_connection
from dbops.logging import add_json_result, flush_json, is_json_mode, setup_logging

# Rich is a terminal-formatting library — it gives us colored panels + tables.
console = Console()
logger = setup_logging()

# Where to find the SQL files. Paths are relative to the repo root
# (which is always the working directory when dbops is invoked).
MIGRATION_DIR = Path("database/migrations")
SEED_DIR = Path("database/seed-data")
TEST_DIR = Path("database/tests")

# Regex that matches valid migration filenames: V001__create_table.sql, R042__seed_data.sql, etc.
# Groups: (1) V or R, (2) 3-digit version, (3) description
VERSION_PATTERN = re.compile(r"^(V|R)(\d{3})__(.+)\.sql$")


def _checksum(file_path: Path) -> str:
    """Return the SHA-256 hash of a file's contents.

    We hash the script so we can detect if a file was modified after it
    was applied. Any byte change = different hash = we refuse to run.
    """
    return hashlib.sha256(file_path.read_text(encoding="utf-8").encode()).hexdigest()


def _parse_script_name(filename: str) -> dict | None:
    """Break 'V001__create_users.sql' into {type, version, description, filename}.

    Returns None if the filename doesn't match the convention. We use this
    as a filter — anything that doesn't parse is skipped silently.
    """
    match = VERSION_PATTERN.match(filename)
    if not match:
        return None
    return {
        "type": match.group(1),  # V (versioned) or R (repeatable)
        "version": match.group(2),  # "001", "002", etc.
        "description": match.group(3),  # e.g. "create_users"
        "filename": filename,
    }


def _get_applied_versions(cursor) -> dict[str, str]:
    """Read the migration_history table into a {version: checksum} dict.

    On first run the history table doesn't exist yet (it's created by
    V001). In that case we catch the error and return an empty dict.
    """
    try:
        cursor.execute(
            "SELECT version, checksum FROM dbops.migration_history WHERE success = 1"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    except Exception:
        # Table doesn't exist — this is the very first migration run.
        return {}


def _execute_sql_script(cursor, sql_text: str) -> None:
    """Run a SQL script, handling 'GO' batch separators.

    SQL Server scripts use 'GO' on its own line to separate batches
    (each batch is sent to the server as a single command). pyodbc
    doesn't understand GO natively, so we split on it ourselves and
    execute each batch in order.

    Example script:
        CREATE TABLE foo ...;
        GO
        CREATE TABLE bar ...;
        GO
        INSERT INTO foo ...;
    """
    # Split the script on lines that contain only 'GO' (case-insensitive).
    batches = re.split(r"^\s*GO\s*$", sql_text, flags=re.MULTILINE | re.IGNORECASE)
    for batch in batches:
        batch = batch.strip()
        if batch:  # skip empty batches (e.g. trailing GO)
            cursor.execute(batch)


def _record_migration(
    cursor,
    version: str,
    script_name: str,
    checksum: str,
    execution_ms: int,
    success: bool,
) -> None:
    """Write a row into dbops.migration_history.

    We use MERGE (SQL Server's upsert) so re-runs update the existing
    row instead of creating duplicates. This matters if a migration
    failed once, got fixed, and is being re-applied.
    """
    cursor.execute(
        """
        MERGE dbops.migration_history AS target
        USING (SELECT ? AS version) AS source
        ON target.version = source.version
        WHEN MATCHED THEN
            UPDATE SET checksum = ?, applied_on = SYSUTCDATETIME(),
                       execution_ms = ?, success = ?
        WHEN NOT MATCHED THEN
            INSERT (version, script_name, checksum, execution_ms, success)
            VALUES (?, ?, ?, ?, ?);
        """,
        version,
        checksum,
        execution_ms,
        success,  # MATCHED branch
        version,
        script_name,
        checksum,
        execution_ms,
        success,  # NOT MATCHED branch
    )


def run_migrate(
    config_path: str,
    target_database: str | None = None,
    dry_run: bool = False,
    run_tests: bool = False,
) -> None:
    """The main entry point — apply pending migrations and seed data.

    Steps:
      1. Load the config YAML (resolves env vars).
      2. Figure out which database we're targeting.
      3. Discover V and R scripts on disk.
      4. Make sure the target database exists (CREATE IF NOT EXISTS).
      5. Connect, read migration_history.
      6. For each V script: skip if already applied, otherwise run it.
      7. For each R script: always run it.
      8. Optionally run database tests (SQL scripts in database/tests/).
      9. Print a summary and exit with status code.
    """
    # -------------------- Step 1 + 2: load config, pick database --------------------
    config = load_config(config_path)
    if target_database:
        # --database flag overrides whatever's in the YAML
        config["sql"]["database"] = target_database

    db_name = config["sql"]["database"]

    # Print a banner so the user sees what's about to happen.
    console.print(
        Panel(
            f"[bold]Database Migration[/bold]\n"
            f"Target: [cyan]{config['sql']['server']}[/cyan] / [cyan]{db_name}[/cyan]\n"
            f"Mode:   [yellow]{'DRY RUN' if dry_run else 'APPLY'}[/yellow]",
            title="dbops migrate",
        )
    )

    # -------------------- Step 3: discover scripts on disk --------------------
    # sorted() makes sure V001 runs before V002, etc. We also filter out
    # files that don't match the naming convention.
    versioned = sorted(
        [f for f in MIGRATION_DIR.glob("V*.sql") if _parse_script_name(f.name)],
        key=lambda f: f.name,
    )
    repeatable = sorted(
        [f for f in SEED_DIR.glob("R*.sql") if _parse_script_name(f.name)],
        key=lambda f: f.name,
    )

    # If there are no scripts, there's nothing to do. Exit cleanly.
    if not versioned and not repeatable:
        console.print("[yellow]No migration scripts found.[/yellow]")
        return

    # -------------------- Step 4: make sure the database exists --------------------
    # Docker: creates the database if missing.
    # Azure SQL: no-op (Terraform already created it).
    ensure_database(config)

    # -------------------- Step 5: connect + read history --------------------
    conn = get_connection(config)
    # autocommit=True: each statement commits on its own. Simpler for DDL.
    conn.autocommit = True
    cursor = conn.cursor()

    # {version: checksum} for everything that's already been applied successfully.
    applied = _get_applied_versions(cursor)

    # Counters used in the final summary.
    applied_count = 0
    skipped_count = 0
    failed_count = 0

    # A Rich table that we fill in row-by-row and print at the end.
    table = Table(title="Migration Plan")
    table.add_column("Script", style="cyan")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Time (ms)", justify="right")

    # -------------------- Step 6: versioned migrations (V scripts) --------------------
    for script_path in versioned:
        info = _parse_script_name(script_path.name)
        version = info["version"]
        cs = _checksum(script_path)

        # Case A: this version was already applied.
        if version in applied:
            # Safety check — did someone edit the file after it ran?
            if applied[version] != cs:
                msg = (
                    f"CHECKSUM MISMATCH for {script_path.name} — "
                    f"already applied with different content"
                )
                logger.error(msg)
                table.add_row(
                    script_path.name, version, "[red]CHECKSUM MISMATCH[/red]", "-"
                )
                failed_count += 1
                if is_json_mode():
                    add_json_result(
                        "migrate",
                        "error",
                        {"script": script_path.name, "error": msg},
                    )
                continue

            # Already applied and unchanged — skip.
            table.add_row(script_path.name, version, "[dim]already applied[/dim]", "-")
            skipped_count += 1
            continue

        # Case B: dry run — we just say what we *would* do.
        if dry_run:
            table.add_row(
                script_path.name, version, "[yellow]pending (dry run)[/yellow]", "-"
            )
            applied_count += 1
            continue

        # Case C: actually run it.
        sql_text = script_path.read_text(encoding="utf-8")
        start = time.perf_counter()
        try:
            _execute_sql_script(cursor, sql_text)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            # Record the successful run in the history table.
            _record_migration(cursor, version, script_path.name, cs, elapsed_ms, True)
            table.add_row(
                script_path.name, version, "[green]applied[/green]", str(elapsed_ms)
            )
            applied_count += 1
            logger.info("Applied %s (%d ms)", script_path.name, elapsed_ms)
            if is_json_mode():
                add_json_result(
                    "migrate", "ok", {"script": script_path.name, "ms": elapsed_ms}
                )
        except Exception as exc:
            # Migration failed — log it, count it, and keep going to the next script.
            # We don't fail fast because the summary at the end is more useful
            # than stopping mid-way.
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            table.add_row(
                script_path.name, version, "[red]FAILED[/red]", str(elapsed_ms)
            )
            failed_count += 1
            logger.error("Failed %s: %s", script_path.name, exc)
            if is_json_mode():
                add_json_result(
                    "migrate",
                    "error",
                    {"script": script_path.name, "error": str(exc)},
                )

    # -------------------- Step 7: repeatable scripts (R scripts) --------------------
    # These always run. Useful for seed data and reference tables that
    # should exist in every environment.
    for script_path in repeatable:
        info = _parse_script_name(script_path.name)

        if dry_run:
            table.add_row(
                script_path.name,
                f"R{info['version']}",
                "[yellow]seed (dry run)[/yellow]",
                "-",
            )
            continue

        sql_text = script_path.read_text(encoding="utf-8")
        start = time.perf_counter()
        try:
            _execute_sql_script(cursor, sql_text)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            table.add_row(
                script_path.name,
                f"R{info['version']}",
                "[green]seeded[/green]",
                str(elapsed_ms),
            )
            logger.info("Seeded %s (%d ms)", script_path.name, elapsed_ms)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            table.add_row(
                script_path.name,
                f"R{info['version']}",
                "[red]FAILED[/red]",
                str(elapsed_ms),
            )
            failed_count += 1
            logger.error("Seed failed %s: %s", script_path.name, exc)

    console.print(table)

    # -------------------- Step 8: optional database tests --------------------
    # SQL-based smoke tests — each test file raises an error if something
    # is wrong (e.g. required table missing, bad data).
    if run_tests and not dry_run:
        console.print("\n[bold]Running database tests...[/bold]")
        test_scripts = sorted(TEST_DIR.glob("test_*.sql"))
        for test_path in test_scripts:
            console.print(f"  Running [cyan]{test_path.name}[/cyan]...")
            sql_text = test_path.read_text(encoding="utf-8")
            try:
                _execute_sql_script(cursor, sql_text)
                console.print(f"  [green]PASS[/green]: {test_path.name}")
                if is_json_mode():
                    add_json_result("db_test", "pass", {"test": test_path.name})
            except Exception as exc:
                console.print(f"  [red]FAIL[/red]: {test_path.name} — {exc}")
                failed_count += 1
                if is_json_mode():
                    add_json_result(
                        "db_test",
                        "fail",
                        {"test": test_path.name, "error": str(exc)},
                    )

    # -------------------- Step 9: summary + exit --------------------
    status = "FAIL" if failed_count > 0 else "OK"
    console.print(
        Panel(
            f"Applied: [green]{applied_count}[/green]  "
            f"Skipped: [dim]{skipped_count}[/dim]  "
            f"Failed: [red]{failed_count}[/red]",
            title=f"Migration {status}",
            border_style="red" if failed_count else "green",
        )
    )

    if is_json_mode():
        add_json_result(
            "summary",
            status.lower(),
            {
                "applied": applied_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
        )
        flush_json()

    cursor.close()
    conn.close()

    # Non-zero exit code tells CI/CD the deploy failed so it can halt the pipeline.
    if failed_count > 0:
        raise SystemExit(1)
