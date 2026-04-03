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


def ensure_database(config: dict) -> None:
    """Create the target database if it does not already exist."""
    sql = config["sql"]
    db_name = sql["database"]
    # Connect to 'master' to check/create the target database
    master_config = {**config, "sql": {**sql, "database": "master"}}
    conn = get_connection(master_config)
    conn.autocommit = True
    cursor = conn.cursor()
    # DB_ID() accepts a parameter, but CREATE DATABASE requires a literal.
    # Bracket-quoting prevents SQL injection for identifiers.
    cursor.execute(f"IF DB_ID(?) IS NULL CREATE DATABASE [{db_name}]", (db_name,))
    cursor.close()
    conn.close()


def get_connection(config: dict) -> pyodbc.Connection:
    """Create and return a pyodbc connection to SQL Server."""
    conn_str = build_connection_string(config)
    return pyodbc.connect(conn_str, timeout=10)
