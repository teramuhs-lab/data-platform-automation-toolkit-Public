"""Database rollback runner — undoes the most recent migrations.

How rollback works:

  Every forward migration V###__description.sql can have a matching rollback
  script V###__rollback__description.sql in the same folder. The rollback
  script UNDOES what the forward script did.

  Examples:
    V003__add_email_column.sql             forward  — adds 'email' column
    V003__rollback__add_email_column.sql   rollback — drops 'email' column

  When you run `dbops rollback --steps 2`, the tool:
    1. Reads migration_history to see what's applied, newest first
    2. Picks the top 2
    3. For each, runs its matching rollback script
    4. Deletes the row from migration_history so the version is "un-applied"

  If a rollback script is missing, we refuse to proceed — no half-rolled-back
  state. You either have a rollback path for every applied migration, or
  you fix it before trying again.

Convention enforced by the glob pattern:
  Forward: V###__(anything not starting with 'rollback__').sql
  Rollback: V###__rollback__(anything).sql
"""

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

# Same folder as forward migrations — easier to find the rollback next to the script it undoes.
MIGRATION_DIR = Path("database/migrations")

# Pattern for rollback scripts: V###__rollback__<description>.sql
# The double underscore after 'rollback' is intentional — it makes the regex
# unambiguous and prevents collisions with a forward migration someone might
# name "V003__rollback_admin_access.sql" (feature name containing "rollback").
ROLLBACK_PATTERN = re.compile(r"^V(\d{3})__rollback__(.+)\.sql$")


def _execute_sql_script(cursor, sql_text: str) -> None:
    """Execute a SQL script, splitting on GO batches.

    Same logic as in migrate.py — we can't just import it from there because
    we want rollback to be readable as a standalone file. Duplicating 4 lines
    of code is fine; the alternative (a shared helper module) adds more
    cognitive load than it saves.
    """
    batches = re.split(r"^\s*GO\s*$", sql_text, flags=re.MULTILINE | re.IGNORECASE)
    for batch in batches:
        batch = batch.strip()
        if batch:
            cursor.execute(batch)


def _find_rollback_script(version: str) -> Path | None:
    """Look for V###__rollback__*.sql in the migrations folder.

    Returns the Path if found, None if not. We don't enforce a specific
    description suffix — if someone names it V003__rollback__anything.sql,
    we'll find it.
    """
    # glob gives us every file starting with "V<version>__rollback__"
    matches = list(MIGRATION_DIR.glob(f"V{version}__rollback__*.sql"))
    if not matches:
        return None
    # If somehow there are multiple (shouldn't happen with proper reviews),
    # we pick the first alphabetically — deterministic is better than random.
    return sorted(matches)[0]


def run_rollback(
    config_path: str,
    target_database: str | None = None,
    steps: int = 1,
    dry_run: bool = False,
) -> None:
    """Roll back the last N applied migrations.

    Args:
        config_path     — path to env YAML (same as migrate uses)
        target_database — override the database name from config
        steps           — how many migrations to roll back (default: 1)
        dry_run         — just print the plan without executing
    """
    # ---- Load config + figure out target database ----
    config = load_config(config_path)
    if target_database:
        config["sql"]["database"] = target_database
    db_name = config["sql"]["database"]

    # Banner so the user can see what's about to happen.
    console.print(
        Panel(
            f"[bold]Database Rollback[/bold]\n"
            f"Target: [cyan]{config['sql']['server']}[/cyan] / [cyan]{db_name}[/cyan]\n"
            f"Steps:  [yellow]{steps}[/yellow]\n"
            f"Mode:   [yellow]{'DRY RUN' if dry_run else 'APPLY'}[/yellow]",
            title="dbops rollback",
            border_style="yellow",
        )
    )

    # ---- Connect ----
    conn = get_connection(config)
    conn.autocommit = True
    cursor = conn.cursor()

    # ---- Find the most recent N applied migrations ----
    # We order by applied_on DESC so the newest comes first — that's the
    # correct rollback order (undo V005 before V004).
    try:
        cursor.execute(
            """
            SELECT TOP (?) version, script_name
            FROM dbops.migration_history
            WHERE success = 1
            ORDER BY applied_on DESC
            """,
            steps,
        )
        to_rollback = cursor.fetchall()
    except Exception as exc:
        console.print(f"[red]Could not read migration_history: {exc}[/red]")
        console.print("[dim]Is this database managed by dbops?[/dim]")
        cursor.close()
        conn.close()
        raise SystemExit(1)

    if not to_rollback:
        console.print("[yellow]No migrations to roll back.[/yellow]")
        cursor.close()
        conn.close()
        return

    # ---- Verify every rollback script exists BEFORE we start ----
    # We want all-or-nothing safety: if any rollback script is missing,
    # we stop before touching the database. No half-rolled-back state.
    plan = []
    for row in to_rollback:
        version, script_name = row[0], row[1]
        rollback_path = _find_rollback_script(version)
        plan.append((version, script_name, rollback_path))

    # If anything in the plan is missing a rollback script, print the whole
    # plan with errors and exit.
    missing = [p for p in plan if p[2] is None]
    if missing:
        console.print("[red]Cannot proceed — rollback scripts missing:[/red]")
        for version, script_name, _ in missing:
            console.print(
                f"  [red]✗[/red] {script_name} — expected V{version}__rollback__*.sql"
            )
        cursor.close()
        conn.close()
        raise SystemExit(1)

    # ---- Show the plan ----
    table = Table(title="Rollback Plan")
    table.add_column("Version")
    table.add_column("Original script", style="cyan")
    table.add_column("Rollback script", style="yellow")
    table.add_column("Status")
    table.add_column("Time (ms)", justify="right")

    if dry_run:
        for version, script_name, rollback_path in plan:
            table.add_row(
                version,
                script_name,
                rollback_path.name,
                "[yellow]would roll back[/yellow]",
                "-",
            )
        console.print(table)
        cursor.close()
        conn.close()
        return

    # ---- Execute rollbacks, one at a time ----
    rolled_back = 0
    failed = 0

    for version, script_name, rollback_path in plan:
        sql_text = rollback_path.read_text(encoding="utf-8")
        start = time.perf_counter()
        try:
            # Run the rollback SQL.
            _execute_sql_script(cursor, sql_text)

            # Remove the row from migration_history so this version is
            # considered un-applied and will run again on the next migrate.
            cursor.execute(
                "DELETE FROM dbops.migration_history WHERE version = ?",
                version,
            )

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            table.add_row(
                version,
                script_name,
                rollback_path.name,
                "[green]rolled back[/green]",
                str(elapsed_ms),
            )
            rolled_back += 1
            logger.info("Rolled back %s (%d ms)", script_name, elapsed_ms)
            if is_json_mode():
                add_json_result(
                    "rollback",
                    "ok",
                    {
                        "version": version,
                        "script": rollback_path.name,
                        "ms": elapsed_ms,
                    },
                )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            table.add_row(
                version,
                script_name,
                rollback_path.name,
                "[red]FAILED[/red]",
                str(elapsed_ms),
            )
            failed += 1
            logger.error("Rollback failed for %s: %s", script_name, exc)
            if is_json_mode():
                add_json_result(
                    "rollback",
                    "error",
                    {
                        "version": version,
                        "script": rollback_path.name,
                        "error": str(exc),
                    },
                )
            # Stop on first failure — rolling back out of order is dangerous.
            break

    console.print(table)

    # ---- Summary ----
    status = "FAIL" if failed > 0 else "OK"
    console.print(
        Panel(
            f"Rolled back: [green]{rolled_back}[/green]  Failed: [red]{failed}[/red]",
            title=f"Rollback {status}",
            border_style="red" if failed else "green",
        )
    )

    if is_json_mode():
        add_json_result(
            "summary",
            status.lower(),
            {"rolled_back": rolled_back, "failed": failed},
        )
        flush_json()

    cursor.close()
    conn.close()

    if failed > 0:
        raise SystemExit(1)
