"""Database migration runner — applies versioned SQL scripts in order.

Follows a Flyway-like convention:
  V###__description.sql   → Versioned (run once, tracked by checksum)
  R###__description.sql   → Repeatable (re-run every deploy, e.g. seed data)

Migration state is stored in dbops.migration_history on the target database.
"""

import hashlib
import re
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dbops.config import load_config
from dbops.db import get_connection
from dbops.logging import add_json_result, flush_json, is_json_mode, setup_logging

console = Console()
logger = setup_logging()

MIGRATION_DIR = Path("database/migrations")
SEED_DIR = Path("database/seed-data")
TEST_DIR = Path("database/tests")

# Pattern: V001__description.sql or R001__description.sql
VERSION_PATTERN = re.compile(r"^(V|R)(\d{3})__(.+)\.sql$")


def _checksum(file_path: Path) -> str:
    """SHA-256 checksum of a SQL file."""
    return hashlib.sha256(file_path.read_text(encoding="utf-8").encode()).hexdigest()


def _parse_script_name(filename: str) -> dict | None:
    """Parse a migration filename into components."""
    match = VERSION_PATTERN.match(filename)
    if not match:
        return None
    return {
        "type": match.group(1),  # V or R
        "version": match.group(2),  # 001, 002, ...
        "description": match.group(3),  # human-readable
        "filename": filename,
    }


def _get_applied_versions(cursor) -> dict[str, str]:
    """Fetch already-applied migration versions and their checksums."""
    try:
        cursor.execute(
            "SELECT version, checksum FROM dbops.migration_history WHERE success = 1"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    except Exception:
        # Table doesn't exist yet — first run
        return {}


def _execute_sql_script(cursor, sql_text: str) -> None:
    """Execute a SQL script, splitting on GO batches."""
    batches = re.split(r"^\s*GO\s*$", sql_text, flags=re.MULTILINE | re.IGNORECASE)
    for batch in batches:
        batch = batch.strip()
        if batch:
            cursor.execute(batch)


def _record_migration(
    cursor,
    version: str,
    script_name: str,
    checksum: str,
    execution_ms: int,
    success: bool,
) -> None:
    """Insert a record into the migration history table."""
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
        success,
        version,
        script_name,
        checksum,
        execution_ms,
        success,
    )


def run_migrate(
    config_path: str,
    target_database: str | None = None,
    dry_run: bool = False,
    run_tests: bool = False,
) -> None:
    """Apply pending migrations, seed data, and optionally run DB tests."""
    config = load_config(config_path)
    if target_database:
        config["sql"]["database"] = target_database

    db_name = config["sql"]["database"]
    console.print(
        Panel(
            f"[bold]Database Migration[/bold]\n"
            f"Target: [cyan]{config['sql']['server']}[/cyan] / [cyan]{db_name}[/cyan]\n"
            f"Mode:   [yellow]{'DRY RUN' if dry_run else 'APPLY'}[/yellow]",
            title="dbops migrate",
        )
    )

    # ---- Discover scripts ----
    versioned = sorted(
        [f for f in MIGRATION_DIR.glob("V*.sql") if _parse_script_name(f.name)],
        key=lambda f: f.name,
    )
    repeatable = sorted(
        [f for f in SEED_DIR.glob("R*.sql") if _parse_script_name(f.name)],
        key=lambda f: f.name,
    )

    if not versioned and not repeatable:
        console.print("[yellow]No migration scripts found.[/yellow]")
        return

    # ---- Connect ----
    conn = get_connection(config)
    conn.autocommit = True
    cursor = conn.cursor()

    applied = _get_applied_versions(cursor)
    applied_count = 0
    skipped_count = 0
    failed_count = 0

    # ---- Status table ----
    table = Table(title="Migration Plan")
    table.add_column("Script", style="cyan")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Time (ms)", justify="right")

    # ---- Apply versioned migrations ----
    for script_path in versioned:
        info = _parse_script_name(script_path.name)
        version = info["version"]
        cs = _checksum(script_path)

        if version in applied:
            if applied[version] != cs:
                msg = f"CHECKSUM MISMATCH for {script_path.name} — already applied with different content"
                logger.error(msg)
                table.add_row(
                    script_path.name, version, "[red]CHECKSUM MISMATCH[/red]", "-"
                )
                failed_count += 1
                if is_json_mode():
                    add_json_result(
                        "migrate", "error", {"script": script_path.name, "error": msg}
                    )
                continue
            table.add_row(script_path.name, version, "[dim]already applied[/dim]", "-")
            skipped_count += 1
            continue

        if dry_run:
            table.add_row(
                script_path.name, version, "[yellow]pending (dry run)[/yellow]", "-"
            )
            applied_count += 1
            continue

        # Execute
        sql_text = script_path.read_text(encoding="utf-8")
        start = time.perf_counter()
        try:
            _execute_sql_script(cursor, sql_text)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
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
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            table.add_row(
                script_path.name, version, "[red]FAILED[/red]", str(elapsed_ms)
            )
            failed_count += 1
            logger.error("Failed %s: %s", script_path.name, exc)
            if is_json_mode():
                add_json_result(
                    "migrate", "error", {"script": script_path.name, "error": str(exc)}
                )

    # ---- Apply repeatable (seed) scripts ----
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

    # ---- Run DB tests if requested ----
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
                        "db_test", "fail", {"test": test_path.name, "error": str(exc)}
                    )

    # ---- Summary ----
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

    if failed_count > 0:
        raise SystemExit(1)
