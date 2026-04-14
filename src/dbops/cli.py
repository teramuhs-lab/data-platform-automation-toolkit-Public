"""Command-line interface for the dbops toolkit.

This is the entry point when you run `dbops <command>` in a terminal.
Under the hood it's a Typer app — Typer turns Python functions into
CLI commands automatically, using the type hints and docstrings.

Installed commands:
  dbops healthcheck     — run health queries and print a report
  dbops backup          — back up user databases to .bak files
  dbops restore         — restore a database from a .bak file
  dbops migrate         — apply SQL migrations + seed data
  dbops drift-check     — compare source-controlled schema vs live schema
  dbops failover-test   — validate DB availability and optionally trigger AG failover
  dbops dashboard       — interactive terminal dashboard (TUI)

Global flag:
  --json   → switches output to machine-readable JSON (for CI pipelines)
"""

import typer

# Import each command's implementation. We only import the *function*, not
# the whole module, so the CLI stays decoupled from the internals.
from dbops.commands.backup import run_backup
from dbops.commands.dashboard import run_dashboard
from dbops.commands.drift_check import run_drift_check
from dbops.commands.failover_test import run_failover_test
from dbops.commands.healthcheck import run_healthcheck
from dbops.commands.migrate import run_migrate
from dbops.commands.restore import run_restore
from dbops.commands.rollback import run_rollback
from dbops.logging import set_json_mode

# Create the Typer app. The help text is shown when users run `dbops --help`.
app = typer.Typer(help="Data Platform Automation Toolkit (DBA DevOps CLI)")


# @app.callback runs before any subcommand. We use it to handle global flags
# that apply to every command (like --json output mode).
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output"
    ),
):
    """Data Platform Automation Toolkit (DBA DevOps CLI)."""
    # If --json was passed, flip the global logging mode so every command
    # produces JSON instead of colored console text.
    if json_output:
        set_json_mode(True)

    # If the user typed `dbops` with no subcommand, print the help text.
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# -----------------------------------------------------------------------------
# Each @app.command() below turns a Python function into a CLI subcommand.
# Typer inspects the type hints to generate --help, validate inputs, and
# parse arguments automatically.
# -----------------------------------------------------------------------------


@app.command()
def healthcheck(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
):
    """Run database health checks against SQL Server."""
    run_healthcheck(config)


@app.command()
def backup(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
    database: str = typer.Option(
        None, "--database", "-d", help="Database name (omit to back up all user DBs)"
    ),
    no_verify: bool = typer.Option(
        False, "--no-verify", help="Skip RESTORE VERIFYONLY after backup"
    ),
):
    """Back up one or all user databases with compression and checksum."""
    # `not no_verify` is cleaner than passing a double-negative further down.
    run_backup(config, database=database, verify=not no_verify)


@app.command()
def restore(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
    backup_file: str = typer.Option(
        ..., "--backup-file", "-f", help="Path to .bak file on the SQL Server host"
    ),
    target: str = typer.Option(
        None, "--target", "-t", help="Target database name (default: <source>_restored)"
    ),
    replace: bool = typer.Option(
        False, "--replace", help="Overwrite target if it already exists"
    ),
):
    """Restore a database from a backup file with WITH MOVE support."""
    run_restore(config, backup_file=backup_file, target=target, replace=replace)


@app.command()
def migrate(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
    target_database: str = typer.Option(
        None, "--database", "-d", help="Target database (overrides config)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be applied without executing"
    ),
    run_tests: bool = typer.Option(
        False, "--test", help="Run database tests after migration"
    ),
):
    """Apply versioned SQL migrations and seed data to the target database."""
    run_migrate(
        config, target_database=target_database, dry_run=dry_run, run_tests=run_tests
    )


@app.command()
def rollback(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
    target_database: str = typer.Option(
        None, "--database", "-d", help="Target database (overrides config)"
    ),
    steps: int = typer.Option(
        1, "--steps", "-s", help="How many of the most recent migrations to roll back"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show the rollback plan without executing it"
    ),
):
    """Roll back the last N applied migrations using their V###__rollback__*.sql scripts."""
    run_rollback(config, target_database=target_database, steps=steps, dry_run=dry_run)


@app.command(name="drift-check")
def drift_check(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
    target_database: str = typer.Option(
        None, "--database", "-d", help="Target database (overrides config)"
    ),
):
    """Detect schema drift between source-controlled migrations and live database."""
    run_drift_check(config, target_database=target_database)


@app.command(name="failover-test")
def failover_test(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
    database: str = typer.Option(
        "master", "--database", "-d", help="Database for write/read test"
    ),
    execute_failover: bool = typer.Option(
        False,
        "--execute-failover",
        help="Actually trigger AG failover (use with caution)",
    ),
):
    """Validate database functionality and AG failover readiness."""
    run_failover_test(config, database=database, execute_failover=execute_failover)


@app.command()
def dashboard(
    config: str = typer.Option(
        "config/env-dev.yml", "--config", "-c", help="Path to YAML config file"
    ),
    refresh: int = typer.Option(
        30, "--refresh", "-r", help="Auto-refresh interval in seconds"
    ),
):
    """Launch an interactive TUI dashboard for real-time server monitoring."""
    run_dashboard(config, refresh=refresh)


# Standard Python idiom — only run app() when this file is executed directly,
# not when it's imported as a module. But in practice, Typer's entry point
# hooked up in pyproject.toml calls app() through a different path.
if __name__ == "__main__":
    app()
