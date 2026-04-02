"""Interactive TUI dashboard for real-time SQL Server monitoring.

Uses Textual to display live-updating panels for:
  - Server identity and connectivity
  - Database list with status and size
  - Disk space usage
  - AG replica status
  - Top wait stats
"""

import time

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static

from dbops.commands.healthcheck import HEALTH_CHECKS
from dbops.config import load_config
from dbops.db import get_connection


class StatusPanel(Static):
    """A panel showing connection status and server identity."""

    DEFAULT_CSS = """
    StatusPanel {
        height: auto;
        border: solid green;
        padding: 1 2;
        margin: 0 1 1 1;
    }
    """


class CheckTable(Static):
    """A container for a labeled DataTable."""

    DEFAULT_CSS = """
    CheckTable {
        height: auto;
        max-height: 16;
        border: solid $accent;
        margin: 0 1 1 1;
    }
    """

    def __init__(self, title: str, table_id: str, **kwargs):
        super().__init__(**kwargs)
        self.border_title = title
        self._table_id = table_id

    def compose(self) -> ComposeResult:
        yield DataTable(id=self._table_id)


class DashboardApp(App):
    """SQL Server real-time monitoring dashboard."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #top-row {
        height: auto;
    }

    #bottom-row {
        height: auto;
    }

    #left-col {
        width: 1fr;
    }

    #right-col {
        width: 1fr;
    }

    #left-col-bottom {
        width: 1fr;
    }

    #right-col-bottom {
        width: 1fr;
    }

    DataTable {
        height: auto;
        max-height: 14;
    }

    #refresh-status {
        dock: bottom;
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, config_path: str, refresh_interval: int = 30):
        super().__init__()
        self.config_path = config_path
        self.refresh_interval = refresh_interval
        self._config = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatusPanel(id="status-panel")
        yield Horizontal(
            Vertical(
                CheckTable("Databases", "db-table"),
                id="left-col",
            ),
            Vertical(
                CheckTable("Disk Space", "disk-table"),
                id="right-col",
            ),
            id="top-row",
        )
        yield Horizontal(
            Vertical(
                CheckTable("AG Replica Status", "ag-table"),
                id="left-col-bottom",
            ),
            Vertical(
                CheckTable("Top 5 Wait Stats", "wait-table"),
                id="right-col-bottom",
            ),
            id="bottom-row",
        )
        yield Static(id="refresh-status")
        yield Footer()

    def on_mount(self) -> None:
        """Load config and start auto-refresh."""
        self.title = "dbops dashboard"
        self.sub_title = self.config_path
        self._config = load_config(self.config_path)
        self._do_refresh()
        self.set_interval(self.refresh_interval, self._do_refresh)

    def action_refresh(self) -> None:
        """Manual refresh triggered by 'r' key."""
        self._do_refresh()

    def _do_refresh(self) -> None:
        """Fetch all health data from SQL Server and update the dashboard."""
        status_panel = self.query_one("#status-panel", StatusPanel)
        refresh_label = self.query_one("#refresh-status", Static)

        # -- Connectivity --
        start = time.time()
        try:
            conn = get_connection(self._config)
        except Exception as e:
            status_panel.update(
                f"[bold red]DISCONNECTED[/]\n{e}"
            )
            status_panel.styles.border = ("solid", "red")
            refresh_label.update(f"  Last attempt: {time.strftime('%H:%M:%S')}  |  Press [bold]r[/] to retry  |  [bold]q[/] to quit")
            return

        elapsed = time.time() - start
        server = self._config["sql"]["server"]

        # -- Server identity --
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT @@SERVERNAME AS server_name, @@VERSION AS server_version")
            row = cursor.fetchone()
            name = row.server_name.strip()
            # Grab just the first line of @@VERSION
            version_line = row.server_version.strip().split("\n")[0]
        except Exception:
            name = "unknown"
            version_line = "unknown"

        status_panel.update(
            f"[bold green]CONNECTED[/]  to [cyan]{server}[/]  ({elapsed:.3f}s)\n"
            f"[bold]{name}[/]  —  {version_line}"
        )
        status_panel.styles.border = ("solid", "green")

        # -- Refresh each section --
        section_map = {
            "Database List": "db-table",
            "Disk Space (xp_fixeddrives)": "disk-table",
            "AG Replica Status": "ag-table",
            "Top 5 Wait Stats": "wait-table",
        }

        for label, table_id in section_map.items():
            query = HEALTH_CHECKS[label]
            table = self.query_one(f"#{table_id}", DataTable)
            table.clear(columns=True)

            try:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                for col in columns:
                    table.add_column(col, key=col)

                if rows:
                    for row in rows:
                        table.add_row(*[str(val).strip() for val in row])
                else:
                    table.add_column("info", key="info")
                    table.add_row("No data (not configured)")
            except Exception as e:
                table.add_column("status", key="status")
                table.add_row(f"Skipped: {e}")

        cursor.close()
        conn.close()

        refresh_label.update(
            f"  Last refresh: {time.strftime('%H:%M:%S')}  |  "
            f"Auto-refresh: {self.refresh_interval}s  |  "
            f"Press [bold]r[/] to refresh  |  [bold]q[/] to quit"
        )


def run_dashboard(config_path: str, refresh: int = 30) -> None:
    """Launch the TUI dashboard."""
    app = DashboardApp(config_path=config_path, refresh_interval=refresh)
    app.run()
