"""CLI entry point for the dbops toolkit."""

import typer

from dbops.commands.backup import run_backup
from dbops.commands.drift_check import run_drift_check
from dbops.commands.failover_test import run_failover_test
from dbops.commands.healthcheck import run_healthcheck
from dbops.commands.migrate import run_migrate
from dbops.commands.restore import run_restore
from dbops.logging import set_json_mode

app = typer.Typer(help="Data Platform Automation Toolkit (DBA DevOps CLI)")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output"
    ),
):
    """Data Platform Automation Toolkit (DBA DevOps CLI)."""
    if json_output:
        set_json_mode(True)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


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
    run_migrate(config, target_database=target_database,
                dry_run=dry_run, run_tests=run_tests)


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
        False, "--execute-failover",
        help="Actually trigger AG failover (use with caution)"
    ),
):
    """Validate database functionality and AG failover readiness."""
    run_failover_test(config, database=database, execute_failover=execute_failover)


if __name__ == "__main__":
    app()
