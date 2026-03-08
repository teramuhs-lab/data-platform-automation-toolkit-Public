"""Database connection management for SQL Server."""

import pyodbc


def build_connection_string(config: dict) -> str:
    """Build a pyodbc connection string from config dict."""
    sql = config["sql"]
    options = config.get("options", {})

    return (
        f"DRIVER={{{sql['driver']}}};"
        f"SERVER={sql['server']};"
        f"DATABASE={sql['database']};"
        f"UID={sql['username']};"
        f"PWD={sql['password']};"
        f"Encrypt={'yes' if options.get('encrypt', False) else 'no'};"
        f"TrustServerCertificate={'yes' if options.get('trust_server_certificate', True) else 'no'};"
    )


def get_connection(config: dict) -> pyodbc.Connection:
    """Create and return a pyodbc connection to SQL Server."""
    conn_str = build_connection_string(config)
    return pyodbc.connect(conn_str, timeout=10)
