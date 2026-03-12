"""Schema drift detection — compares source-controlled schema against live database.

Drift detection answers the question every DBA dreads:
  "Did someone make changes directly in production without going through the pipeline?"

This command queries the live database catalog and compares it against
what the migration scripts should have created.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dbops.config import load_config
from dbops.db import get_connection
from dbops.logging import add_json_result, flush_json, is_json_mode, setup_logging

console = Console()
logger = setup_logging()

# What the migrations should have created (source of truth)
EXPECTED_SCHEMA = {
    "schemas": ["dbops", "inventory"],
    "tables": {
        "dbops.migration_history": [
            "id",
            "version",
            "script_name",
            "checksum",
            "applied_on",
            "applied_by",
            "execution_ms",
            "success",
        ],
        "inventory.environments": [
            "environment_id",
            "name",
            "description",
            "is_production",
            "created_at",
        ],
        "inventory.servers": [
            "server_id",
            "hostname",
            "instance_name",
            "port",
            "environment_id",
            "edition",
            "version",
            "is_ag_primary",
            "last_checked",
            "notes",
            "created_at",
            "updated_at",
        ],
        "inventory.databases": [
            "database_id",
            "server_id",
            "name",
            "recovery_model",
            "compatibility",
            "size_mb",
            "owner",
            "is_monitored",
            "created_at",
        ],
        "inventory.backup_history": [
            "backup_id",
            "database_id",
            "backup_type",
            "backup_path",
            "size_mb",
            "compressed",
            "verified",
            "started_at",
            "completed_at",
            "duration_sec",
            "initiated_by",
        ],
        "inventory.alert_rules": [
            "rule_id",
            "name",
            "metric",
            "operator",
            "threshold",
            "severity",
            "is_enabled",
            "created_at",
        ],
        "inventory.incidents": [
            "incident_id",
            "rule_id",
            "server_id",
            "database_id",
            "severity",
            "message",
            "detected_at",
            "acknowledged_at",
            "acknowledged_by",
            "resolved_at",
        ],
    },
    "procedures": [
        "inventory.usp_register_backup",
        "inventory.usp_get_stale_backups",
        "inventory.usp_raise_incident",
    ],
}


def _get_live_schemas(cursor) -> list[str]:
    """Get user-created schemas from the live database."""
    cursor.execute(
        "SELECT name FROM sys.schemas "
        "WHERE name NOT IN ('dbo','guest','INFORMATION_SCHEMA','sys') "
        "AND name NOT IN ('db_owner','db_accessadmin','db_securityadmin',"
        "'db_ddladmin','db_backupoperator','db_datareader','db_datawriter',"
        "'db_denydatareader','db_denydatawriter')"
    )
    return [row[0] for row in cursor.fetchall()]


def _get_live_tables(cursor) -> dict[str, list[str]]:
    """Get tables and their columns from user schemas."""
    cursor.execute("""
        SELECT
            s.name + '.' + t.name AS full_name,
            c.name AS column_name
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.columns c ON t.object_id = c.object_id
        WHERE s.name NOT IN ('dbo','guest','INFORMATION_SCHEMA','sys')
        ORDER BY full_name, c.column_id
    """)
    tables: dict[str, list[str]] = {}
    for row in cursor.fetchall():
        tables.setdefault(row[0], []).append(row[1])
    return tables


def _get_live_procedures(cursor) -> list[str]:
    """Get stored procedures from user schemas."""
    cursor.execute("""
        SELECT s.name + '.' + p.name
        FROM sys.procedures p
        JOIN sys.schemas s ON p.schema_id = s.schema_id
        WHERE s.name NOT IN ('dbo','guest','INFORMATION_SCHEMA','sys')
        ORDER BY s.name, p.name
    """)
    return [row[0] for row in cursor.fetchall()]


def run_drift_check(config_path: str, target_database: str | None = None) -> None:
    """Compare expected schema (from migrations) against live database."""
    config = load_config(config_path)
    if target_database:
        config["sql"]["database"] = target_database

    db_name = config["sql"]["database"]
    console.print(
        Panel(
            f"[bold]Schema Drift Detection[/bold]\n"
            f"Target: [cyan]{config['sql']['server']}[/cyan] / [cyan]{db_name}[/cyan]",
            title="dbops drift-check",
        )
    )

    conn = get_connection(config)
    cursor = conn.cursor()

    drifts: list[dict] = []

    # ---- Check schemas ----
    live_schemas = _get_live_schemas(cursor)
    for expected in EXPECTED_SCHEMA["schemas"]:
        if expected not in live_schemas:
            drifts.append(
                {
                    "type": "MISSING_SCHEMA",
                    "object": expected,
                    "detail": "Schema expected but not found in database",
                }
            )
    for live in live_schemas:
        if live not in EXPECTED_SCHEMA["schemas"]:
            drifts.append(
                {
                    "type": "EXTRA_SCHEMA",
                    "object": live,
                    "detail": "Schema exists in database but not in migrations",
                }
            )

    # ---- Check tables and columns ----
    live_tables = _get_live_tables(cursor)
    for table_name, expected_cols in EXPECTED_SCHEMA["tables"].items():
        if table_name not in live_tables:
            drifts.append(
                {
                    "type": "MISSING_TABLE",
                    "object": table_name,
                    "detail": "Table expected but not found",
                }
            )
            continue

        live_cols = live_tables[table_name]
        for col in expected_cols:
            if col not in live_cols:
                drifts.append(
                    {
                        "type": "MISSING_COLUMN",
                        "object": f"{table_name}.{col}",
                        "detail": "Column expected but not found",
                    }
                )
        for col in live_cols:
            if col not in expected_cols:
                drifts.append(
                    {
                        "type": "EXTRA_COLUMN",
                        "object": f"{table_name}.{col}",
                        "detail": "Column exists in DB but not in migrations",
                    }
                )

    for table_name in live_tables:
        if table_name not in EXPECTED_SCHEMA["tables"]:
            drifts.append(
                {
                    "type": "EXTRA_TABLE",
                    "object": table_name,
                    "detail": "Table exists in database but not in migrations",
                }
            )

    # ---- Check procedures ----
    live_procs = _get_live_procedures(cursor)
    for expected in EXPECTED_SCHEMA["procedures"]:
        if expected not in live_procs:
            drifts.append(
                {
                    "type": "MISSING_PROC",
                    "object": expected,
                    "detail": "Stored procedure expected but not found",
                }
            )
    for live in live_procs:
        if live not in EXPECTED_SCHEMA["procedures"]:
            drifts.append(
                {
                    "type": "EXTRA_PROC",
                    "object": live,
                    "detail": "Stored procedure exists but not in migrations",
                }
            )

    cursor.close()
    conn.close()

    # ---- Output results ----
    if drifts:
        table = Table(title="Schema Drift Detected")
        table.add_column("Type", style="red")
        table.add_column("Object", style="cyan")
        table.add_column("Detail")
        for d in drifts:
            table.add_row(d["type"], d["object"], d["detail"])
        console.print(table)

        console.print(
            Panel(
                f"[red bold]{len(drifts)} drift(s) found[/red bold] — "
                f"database does not match source-controlled migrations.",
                title="DRIFT DETECTED",
                border_style="red",
            )
        )

        if is_json_mode():
            add_json_result(
                "drift_check", "drift", {"drifts": drifts, "count": len(drifts)}
            )
            flush_json()

        logger.warning("Drift check found %d issue(s)", len(drifts))
        raise SystemExit(1)
    else:
        console.print(
            Panel(
                "[green bold]No drift detected[/green bold] — "
                "database matches source-controlled migrations.",
                title="CLEAN",
                border_style="green",
            )
        )

        if is_json_mode():
            add_json_result("drift_check", "clean", {"drifts": [], "count": 0})
            flush_json()

        logger.info("Drift check passed — no drift detected")
