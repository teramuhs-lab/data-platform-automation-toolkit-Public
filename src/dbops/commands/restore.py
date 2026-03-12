"""Database restore command (MVP).

Behavior:
  - Accept --backup-file (path to .bak on the SQL Server host)
  - Restore to a target database name (--target)
  - Auto-detect logical file names via RESTORE FILELISTONLY
  - Support WITH MOVE mapping for dev restores
  - Print status updates throughout the process
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dbops.config import load_config
from dbops.db import get_connection
from dbops.logging import setup_logging

console = Console()


def _get_file_list(cursor, backup_file: str) -> list[dict]:
    """Read logical/physical file mappings from the backup file."""
    cursor.execute(f"RESTORE FILELISTONLY FROM DISK = N'{backup_file}'")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def _build_move_clauses(
    file_list: list[dict], target_db: str, data_dir: str, log_dir: str
) -> str:
    """Build MOVE clauses to relocate data/log files for the target database."""
    moves = []
    for f in file_list:
        logical = f["LogicalName"]
        file_type = f["Type"]  # D = data, L = log, S = filestream
        if file_type == "L":
            physical = f"{log_dir}/{target_db}_{logical}.ldf"
        else:
            physical = f"{data_dir}/{target_db}_{logical}.mdf"
        moves.append(f"MOVE N'{logical}' TO N'{physical}'")
    return ", ".join(moves)


def run_restore(
    config_path: str,
    backup_file: str,
    target: str | None = None,
    replace: bool = False,
):
    """Restore a database from a backup file."""
    log = setup_logging()
    config = load_config(config_path)

    # Default data/log dirs (SQL Server on Linux defaults)
    data_dir = config.get("restore", {}).get("data_dir", "/var/opt/mssql/data")
    log_dir = config.get("restore", {}).get("log_dir", "/var/opt/mssql/data")

    log.info("Connecting to SQL Server at %s", config["sql"]["server"])

    try:
        conn = get_connection(config)
        conn.autocommit = True  # RESTORE requires autocommit
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]FAIL[/]  Could not connect\n{e}",
                title="Restore",
            )
        )
        raise SystemExit(1)

    cursor = conn.cursor()

    # --- Step 1: Read file list from backup ---
    console.rule("[bold]Step 1: Reading backup file list[/]")
    try:
        file_list = _get_file_list(cursor, backup_file)
    except Exception as e:
        console.print(f"[bold red]Failed to read backup:[/] {e}")
        raise SystemExit(1)

    table = Table(title="Logical Files in Backup")
    table.add_column("LogicalName")
    table.add_column("Type")
    table.add_column("Size (MB)")
    for f in file_list:
        ftype = "Data" if f["Type"] == "D" else "Log" if f["Type"] == "L" else f["Type"]
        size_mb = str(round(f["Size"] / 1024 / 1024, 2))
        table.add_row(f["LogicalName"], ftype, size_mb)
    console.print(table)
    console.print()

    # Infer source database name from the first data file
    source_db = file_list[0]["LogicalName"]
    if not target:
        target = f"{source_db}_restored"
        console.print(f"[yellow]No --target specified. Using:[/] [cyan]{target}[/]")

    # --- Step 2: Build and execute RESTORE ---
    console.rule(f"[bold]Step 2: Restoring to [{target}][/]")
    move_clauses = _build_move_clauses(file_list, target, data_dir, log_dir)

    restore_sql = (
        f"RESTORE DATABASE [{target}] "
        f"FROM DISK = N'{backup_file}' "
        f"WITH {move_clauses}, "
        f"STATS = 10"
    )

    if replace:
        restore_sql += ", REPLACE"

    console.print(f"  Backup file: [dim]{backup_file}[/]")
    console.print(f"  Target DB:   [cyan]{target}[/]")
    console.print(f"  Replace:     {'yes' if replace else 'no'}")
    console.print()

    try:
        cursor.execute(restore_sql)
        while cursor.nextset():
            pass
        console.print(f"  [bold green]Restore OK[/]  → {target}")
    except Exception as e:
        console.print(f"  [bold red]Restore FAILED[/]  {e}")
        cursor.close()
        conn.close()
        raise SystemExit(1)
    console.print()

    # --- Step 3: Verify restored database is online ---
    console.rule("[bold]Step 3: Verifying database status[/]")
    cursor.execute("SELECT name, state_desc FROM sys.databases WHERE name = ?", target)
    row = cursor.fetchone()
    if row and row[1] == "ONLINE":
        console.print(f"  [bold green]ONLINE[/]  {row[0]}")
    elif row:
        console.print(f"  [bold yellow]{row[1]}[/]  {row[0]}")
    else:
        console.print(f"  [bold red]Database {target} not found after restore[/]")

    cursor.close()
    conn.close()

    console.print()
    console.print("[bold green]Restore complete.[/]")
