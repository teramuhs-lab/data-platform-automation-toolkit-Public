"""Database health check command (MVP).

Checks:
  1. SQL connectivity (pass/fail + latency)
  2. Server name + version
  3. Database list with status and size
  4. Free disk via xp_fixeddrives
  5. AG replica status (if configured)
  6. Top 5 wait stats (basic perf snapshot)
"""

import time
from collections import OrderedDict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dbops.config import load_config
from dbops.db import get_connection
from dbops.logging import (
    add_json_result,
    flush_json,
    is_json_mode,
    setup_logging,
)

console = Console()


HEALTH_CHECKS = OrderedDict(
    {
        "Server Identity": """
        SELECT
            @@SERVERNAME  AS server_name,
            @@VERSION     AS server_version
    """,
        "Database List": """
        SELECT
            d.name,
            d.state_desc                                      AS status,
            d.recovery_model_desc                             AS recovery_model,
            CAST(SUM(mf.size) * 8.0 / 1024 AS DECIMAL(10,2)) AS size_mb
        FROM sys.databases d
        LEFT JOIN sys.master_files mf ON d.database_id = mf.database_id
        GROUP BY d.name, d.state_desc, d.recovery_model_desc
        ORDER BY d.name
    """,
        "Disk Space (xp_fixeddrives)": """
        EXEC xp_fixeddrives
    """,
        "AG Replica Status": """
        SELECT
            ag.name                   AS ag_name,
            ar.replica_server_name    AS replica,
            ars.role_desc             AS role,
            ars.synchronization_health_desc AS sync_health
        FROM sys.availability_groups ag
        JOIN sys.availability_replicas ar
            ON ag.group_id = ar.group_id
        JOIN sys.dm_hadr_availability_replica_states ars
            ON ar.replica_id = ars.replica_id
    """,
        "Top 5 Wait Stats": """
        SELECT TOP 5
            wait_type,
            CAST(wait_time_ms / 1000.0 AS DECIMAL(12,2))           AS wait_sec,
            CAST(signal_wait_time_ms / 1000.0 AS DECIMAL(12,2))    AS signal_wait_sec,
            waiting_tasks_count                                      AS wait_count
        FROM sys.dm_os_wait_stats
        WHERE wait_type NOT IN (
            'SLEEP_TASK', 'BROKER_TASK_STOP', 'BROKER_EVENTHANDLER',
            'CLR_AUTO_EVENT', 'CLR_MANUAL_EVENT', 'LAZYWRITER_SLEEP',
            'SQLTRACE_BUFFER_FLUSH', 'WAITFOR', 'XE_TIMER_EVENT',
            'XE_DISPATCHER_WAIT', 'FT_IFTS_SCHEDULER_IDLE_WAIT',
            'LOGMGR_QUEUE', 'CHECKPOINT_QUEUE', 'REQUEST_FOR_DEADLOCK_SEARCH',
            'HADR_FILESTREAM_IOMGR_IOCOMPLETION', 'BROKER_TO_FLUSH',
            'BROKER_RECEIVE_WAITFOR', 'SQLTRACE_INCREMENTAL_FLUSH_SLEEP',
            'DIRTY_PAGE_POLL', 'SP_SERVER_DIAGNOSTICS_SLEEP'
        )
        ORDER BY wait_time_ms DESC
    """,
    }
)


def _rows_to_dicts(columns: list[str], rows: list) -> list[dict]:
    """Convert cursor rows to a list of dictionaries."""
    return [{col: str(val).strip() for col, val in zip(columns, row)} for row in rows]


def _print_table(columns: list[str], rows: list) -> None:
    """Render a Rich table from column names and row data."""
    table = Table(show_header=True, show_lines=False)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(val).strip() for val in row])
    console.print(table)


def run_healthcheck(config_path: str):
    """Execute all health check queries and display structured output."""
    log = setup_logging()
    config = load_config(config_path)
    json_mode = is_json_mode()

    server = config["sql"]["server"]
    log.info("Connecting to SQL Server at %s", server)

    # --- 1. Connectivity check ---
    start = time.time()
    try:
        conn = get_connection(config)
    except Exception as e:
        if json_mode:
            add_json_result("connectivity", "fail", {"server": server, "error": str(e)})
            flush_json()
        else:
            console.print(
                Panel(
                    f"[bold red]FAIL[/]  Could not connect to {server}\n{e}",
                    title="Connectivity Check",
                )
            )
        raise SystemExit(1)

    elapsed = time.time() - start

    if json_mode:
        add_json_result(
            "connectivity", "ok", {"server": server, "latency_sec": round(elapsed, 3)}
        )
    else:
        console.print(
            Panel(
                f"[bold green]OK[/]  Connected to [cyan]{server}[/] in {elapsed:.3f}s",
                title="Connectivity Check",
            )
        )
        console.print()

    cursor = conn.cursor()
    passed = 0
    skipped = 0

    # --- 2-6. Run each health check ---
    for label, query in HEALTH_CHECKS.items():
        if not json_mode:
            console.rule(f"[bold]{label}[/]")
        try:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            if rows:
                if json_mode:
                    add_json_result(label, "ok", _rows_to_dicts(columns, rows))
                else:
                    _print_table(columns, rows)
                passed += 1
            else:
                if json_mode:
                    add_json_result(label, "skipped", None)
                else:
                    console.print("[dim]No data returned (not configured).[/]")
                skipped += 1
        except Exception as e:
            if json_mode:
                add_json_result(label, "skipped", {"error": str(e)})
            else:
                console.print(f"[yellow]Skipped:[/] {e}")
            skipped += 1

        if not json_mode:
            console.print()

    cursor.close()
    conn.close()

    # --- Summary ---
    if json_mode:
        add_json_result(
            "summary",
            "complete",
            {
                "passed": passed,
                "skipped": skipped,
                "server": server,
            },
        )
        flush_json()
    else:
        console.rule("[bold]Summary[/]")
        console.print(f"  [green]Passed:[/]  {passed}")
        console.print(f"  [yellow]Skipped:[/] {skipped}")
        console.print(f"  [cyan]Server:[/]  {server}")
        console.print()
        console.print("[bold green]Health check complete.[/]")
