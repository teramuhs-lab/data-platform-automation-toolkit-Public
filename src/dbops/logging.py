"""Logging configuration for the dbops toolkit.

Outputs to:
  - Console: Rich-formatted with colors and status icons
  - File: ./logs/dbops.log with timestamps (auto-created)
  - JSON mode: machine-readable output when --json is passed
"""

import json
import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

# Global state for JSON mode
_json_mode = False
_json_results: list[dict] = []

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "dbops.log"
LOG_FORMAT = "%(asctime)s  %(name)-12s  %(levelname)-8s  %(message)s"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging to both console (Rich) and file."""
    logger = logging.getLogger("dbops")

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # --- Console handler (Rich) ---
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=True,
    )
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    # --- File handler ---
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# JSON mode helpers
# ---------------------------------------------------------------------------

def set_json_mode(enabled: bool) -> None:
    """Enable or disable JSON output mode."""
    global _json_mode, _json_results
    _json_mode = enabled
    _json_results = []


def is_json_mode() -> bool:
    """Check if JSON output mode is active."""
    return _json_mode


def add_json_result(section: str, status: str, data: dict | list | None = None) -> None:
    """Append a result entry for JSON output."""
    entry = {"section": section, "status": status}
    if data is not None:
        entry["data"] = data
    _json_results.append(entry)


def flush_json() -> None:
    """Print all collected JSON results to stdout and reset."""
    if _json_results:
        console = Console()
        console.print_json(json.dumps(_json_results, default=str))
    _json_results.clear()
