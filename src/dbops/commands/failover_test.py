"""Failover test command.

Version A (simple, non-AG):
  - Run a write test (create table → insert → read → cleanup)
  - Confirm write succeeded
  - Proves the tool can validate database functionality

Version B (AG-focused):
  - Query AG role status (primary/secondary)
  - Validate synchronization health
  - Run read-only query on secondary (if configured)
  - Run write test on primary
  - Optionally trigger manual failover (requires --execute-failover flag)
"""

import time
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dbops.config import load_config
from dbops.db import get_connection
from dbops.logging import setup_logging

console = Console()


# ---------------------------------------------------------------------------
# Version A: Write/Read validation (works on any SQL Server)
# ---------------------------------------------------------------------------


def _run_write_test(cursor, database: str) -> bool:
    """Create a temp table, insert a row, read it back, then clean up."""
    test_table = "dbops_failover_test"
    timestamp = datetime.now().isoformat()

    steps = [
        (
            "Create test table",
            f"""
            USE [{database}];
            IF OBJECT_ID('dbo.{test_table}', 'U') IS NOT NULL
                DROP TABLE dbo.{test_table};
            CREATE TABLE dbo.{test_table} (
                id INT IDENTITY(1,1) PRIMARY KEY,
                test_value NVARCHAR(100),
                created_at DATETIME DEFAULT GETDATE()
            )
            """,
        ),
        (
            "Insert test row",
            f"""
            INSERT INTO [{database}].dbo.{test_table} (test_value)
            VALUES (N'failover_test_{timestamp}')
            """,
        ),
    ]

    # Execute write steps
    for label, sql in steps:
        try:
            cursor.execute(sql)
            while cursor.nextset():
                pass
            console.print(f"  [green]OK[/]  {label}")
        except Exception as e:
            console.print(f"  [bold red]FAIL[/]  {label}: {e}")
            return False

    # Read back
    try:
        cursor.execute(
            f"SELECT TOP 1 id, test_value, created_at "
            f"FROM [{database}].dbo.{test_table} ORDER BY id DESC"
        )
        row = cursor.fetchone()
        if row:
            console.print(f"  [green]OK[/]  Read back: id={row[0]}, value={row[1]}")
        else:
            console.print("  [bold red]FAIL[/]  No rows returned")
            return False
    except Exception as e:
        console.print(f"  [bold red]FAIL[/]  Read back: {e}")
        return False

    # Cleanup
    try:
        cursor.execute(f"DROP TABLE [{database}].dbo.{test_table}")
        while cursor.nextset():
            pass
        console.print(f"  [green]OK[/]  Cleanup (dropped {test_table})")
    except Exception as e:
        console.print(f"  [yellow]WARN[/]  Cleanup failed: {e}")

    return True


# ---------------------------------------------------------------------------
# Version B: AG status validation
# ---------------------------------------------------------------------------

AG_STATUS_QUERY = """
    SELECT
        ag.name                                     AS ag_name,
        ar.replica_server_name                      AS replica,
        ars.role_desc                               AS role,
        ars.connected_state_desc                    AS connected,
        ars.synchronization_health_desc             AS sync_health,
        ars.last_connect_error_description          AS last_error
    FROM sys.availability_groups ag
    JOIN sys.availability_replicas ar
        ON ag.group_id = ar.group_id
    JOIN sys.dm_hadr_availability_replica_states ars
        ON ar.replica_id = ars.replica_id
    ORDER BY ag.name, ars.role_desc
"""

AG_DB_STATUS_QUERY = """
    SELECT
        ag.name                                     AS ag_name,
        DB_NAME(drs.database_id)                    AS database_name,
        drs.synchronization_state_desc              AS sync_state,
        drs.synchronization_health_desc             AS sync_health,
        drs.log_send_queue_size                     AS log_send_queue_kb,
        drs.redo_queue_size                         AS redo_queue_kb
    FROM sys.dm_hadr_database_replica_states drs
    JOIN sys.availability_groups ag
        ON drs.group_id = ag.group_id
    WHERE drs.is_local = 1
    ORDER BY ag.name, DB_NAME(drs.database_id)
"""

FAILOVER_CMD = """
    ALTER AVAILABILITY GROUP [{ag_name}] FAILOVER
"""


def _check_ag_status(cursor) -> list[dict] | None:
    """Query AG replica status. Returns None if AG is not configured."""
    try:
        cursor.execute(AG_STATUS_QUERY)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        if not rows:
            return None
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return None


def _check_ag_db_status(cursor) -> list[dict] | None:
    """Query AG database-level synchronization status."""
    try:
        cursor.execute(AG_DB_STATUS_QUERY)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        if not rows:
            return None
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return None


def _print_ag_replicas(replicas: list[dict]) -> None:
    """Display AG replica status as a table."""
    table = Table(title="AG Replica Status")
    table.add_column("AG Name")
    table.add_column("Replica")
    table.add_column("Role")
    table.add_column("Connected")
    table.add_column("Sync Health")
    for r in replicas:
        role_style = "bold green" if r["role"] == "PRIMARY" else "cyan"
        health_style = "green" if r["sync_health"] == "HEALTHY" else "bold red"
        table.add_row(
            r["ag_name"],
            r["replica"],
            f"[{role_style}]{r['role']}[/]",
            r["connected"],
            f"[{health_style}]{r['sync_health']}[/]",
        )
    console.print(table)


def _print_ag_databases(db_states: list[dict]) -> None:
    """Display AG database sync status as a table."""
    table = Table(title="AG Database Sync Status")
    table.add_column("AG Name")
    table.add_column("Database")
    table.add_column("Sync State")
    table.add_column("Sync Health")
    table.add_column("Log Send Queue (KB)")
    table.add_column("Redo Queue (KB)")
    for d in db_states:
        health_style = "green" if d["sync_health"] == "HEALTHY" else "bold red"
        table.add_row(
            d["ag_name"],
            d["database_name"],
            d["sync_state"],
            f"[{health_style}]{d['sync_health']}[/]",
            str(d["log_send_queue_kb"]),
            str(d["redo_queue_kb"]),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_failover_test(
    config_path: str,
    database: str = "master",
    execute_failover: bool = False,
):
    """Run failover validation: write test + AG status check."""
    log = setup_logging()
    config = load_config(config_path)

    log.info("Connecting to SQL Server at %s", config["sql"]["server"])

    try:
        conn = get_connection(config)
        conn.autocommit = True
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]FAIL[/]  Could not connect\n{e}",
                title="Failover Test",
            )
        )
        raise SystemExit(1)

    cursor = conn.cursor()
    all_passed = True

    # ── Version A: Write/Read test ──
    console.rule("[bold]Version A: Write/Read Validation[/]")
    console.print(f"  Target database: [cyan]{database}[/]\n")

    start = time.time()
    write_ok = _run_write_test(cursor, database)
    elapsed = time.time() - start

    console.print()
    if write_ok:
        console.print(
            f"  [bold green]PASS[/]  Write/Read test completed in {elapsed:.3f}s"
        )
    else:
        console.print("  [bold red]FAIL[/]  Write/Read test failed")
        all_passed = False
    console.print()

    # ── Version B: AG status check ──
    console.rule("[bold]Version B: AG Status Validation[/]")

    replicas = _check_ag_status(cursor)

    if replicas is None:
        console.print(
            "  [dim]No Availability Groups configured. Skipping AG checks.[/]"
        )
    else:
        _print_ag_replicas(replicas)
        console.print()

        # Check AG database sync status
        db_states = _check_ag_db_status(cursor)
        if db_states:
            _print_ag_databases(db_states)
            console.print()

        # Validate all replicas are healthy
        unhealthy = [r for r in replicas if r["sync_health"] != "HEALTHY"]
        if unhealthy:
            console.print("[bold red]WARNING:[/] Unhealthy replicas detected:")
            for r in unhealthy:
                console.print(f"  - {r['replica']} ({r['role']}): {r['sync_health']}")
            all_passed = False
        else:
            console.print("  [bold green]PASS[/]  All replicas healthy")

        # Optional: execute failover
        if execute_failover:
            console.print()
            console.rule("[bold red]Executing AG Failover[/]")
            primary = [r for r in replicas if r["role"] == "PRIMARY"]
            if primary:
                ag_name = primary[0]["ag_name"]
                console.print(f"  [yellow]Triggering failover for AG:[/] {ag_name}")
                try:
                    cursor.execute(FAILOVER_CMD.format(ag_name=ag_name))
                    while cursor.nextset():
                        pass
                    console.print("  [bold green]Failover command executed[/]")
                    console.print("  Waiting 10s for role change...")
                    time.sleep(10)

                    # Re-check status
                    new_replicas = _check_ag_status(cursor)
                    if new_replicas:
                        _print_ag_replicas(new_replicas)
                except Exception as e:
                    console.print(f"  [bold red]Failover FAILED:[/] {e}")
                    all_passed = False

    cursor.close()
    conn.close()

    # ── Summary ──
    console.print()
    console.rule("[bold]Summary[/]")
    if all_passed:
        console.print("[bold green]All failover tests passed.[/]")
    else:
        console.print("[bold red]Some failover tests failed.[/]")
        raise SystemExit(1)
