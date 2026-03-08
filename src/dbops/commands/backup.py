"""Database backup command (MVP).

Behavior:
  - Takes --database (optional); defaults to all user databases
  - Creates .bak filename with timestamp
  - Runs BACKUP DATABASE ... WITH COPY_ONLY, COMPRESSION, CHECKSUM
  - Verifies backup with RESTORE VERIFYONLY ... WITH CHECKSUM
"""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel

from dbops.config import load_config
from dbops.db import get_connection
from dbops.logging import setup_logging

console = Console()

# System databases to exclude when backing up "all"
SYSTEM_DBS = {"master", "model", "msdb", "tempdb"}


def _get_user_databases(cursor) -> list[str]:
    """Return a list of all online user database names."""
    cursor.execute("""
        SELECT name FROM sys.databases
        WHERE state_desc = 'ONLINE'
          AND name NOT IN ('master', 'model', 'msdb', 'tempdb')
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]


def _backup_single(cursor, database: str, backup_dir: str, verify: bool) -> bool:
    """Back up a single database and optionally verify. Returns True on success."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{database}_{timestamp}.bak"
    filepath = f"{backup_dir}/{filename}"

    # --- Run backup ---
    console.print(f"  Backing up [cyan]{database}[/] → [dim]{filepath}[/]")
    backup_sql = (
        f"BACKUP DATABASE [{database}] "
        f"TO DISK = N'{filepath}' "
        f"WITH COPY_ONLY, COMPRESSION, CHECKSUM, FORMAT, "
        f"NAME = N'{database}-Full-{timestamp}'"
    )
    try:
        cursor.execute(backup_sql)
        while cursor.nextset():  # consume all result sets
            pass
        console.print(f"  [green]Backup OK[/]  {filename}")
    except Exception as e:
        console.print(f"  [bold red]Backup FAILED[/]  {e}")
        return False

    # --- Verify backup ---
    if verify:
        console.print(f"  Verifying [dim]{filepath}[/]")
        verify_sql = f"RESTORE VERIFYONLY FROM DISK = N'{filepath}' WITH CHECKSUM"
        try:
            cursor.execute(verify_sql)
            while cursor.nextset():
                pass
            console.print(f"  [green]Verify OK[/]  {filename}")
        except Exception as e:
            console.print(f"  [bold red]Verify FAILED[/]  {e}")
            return False

    return True


def run_backup(config_path: str, database: str | None = None, verify: bool = True):
    """Execute backup for one or all user databases."""
    log = setup_logging()
    config = load_config(config_path)
    backup_dir = config.get("backup", {}).get("backup_dir", "/tmp/backups")

    log.info("Connecting to SQL Server at %s", config["sql"]["server"])

    try:
        conn = get_connection(config)
        conn.autocommit = True  # BACKUP requires autocommit
    except Exception as e:
        console.print(Panel(
            f"[bold red]FAIL[/]  Could not connect\n{e}",
            title="Backup",
        ))
        raise SystemExit(1)

    cursor = conn.cursor()

    # Determine which databases to back up
    if database:
        databases = [database]
    else:
        databases = _get_user_databases(cursor)
        if not databases:
            console.print("[yellow]No user databases found. Nothing to back up.[/]")
            cursor.close()
            conn.close()
            return

    console.print(Panel(
        f"Databases: [cyan]{', '.join(databases)}[/]\n"
        f"Backup dir: [dim]{backup_dir}[/]\n"
        f"Verify: {'yes' if verify else 'no'}",
        title="Backup Plan",
    ))
    console.print()

    succeeded = 0
    failed = 0

    for db in databases:
        console.rule(f"[bold]{db}[/]")
        if _backup_single(cursor, db, backup_dir, verify):
            succeeded += 1
        else:
            failed += 1
        console.print()

    cursor.close()
    conn.close()

    # --- Summary ---
    console.rule("[bold]Summary[/]")
    console.print(f"  [green]Succeeded:[/] {succeeded}")
    if failed:
        console.print(f"  [red]Failed:[/]    {failed}")
    console.print()
    console.print("[bold green]Backup complete.[/]" if not failed
                  else "[bold red]Backup completed with errors.[/]")
