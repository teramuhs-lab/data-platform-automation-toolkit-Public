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
    """Create the target database if it does not already exist.

    Skips gracefully on Azure SQL where CREATE DATABASE via master
    is restricted — databases are provisioned by Terraform instead.
    """
    sql = config["sql"]
    db_name = sql["database"]
    master_config = {**config, "sql": {**sql, "database": "master"}}
    try:
        conn = get_connection(master_config)
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"IF DB_ID(?) IS NULL CREATE DATABASE [{db_name}]", (db_name,))
        cursor.close()
        conn.close()
    except pyodbc.Error:
        pass  # Azure SQL — database must already exist (created by Terraform)


def get_connection(config: dict) -> pyodbc.Connection:
    """Create and return a pyodbc connection to SQL Server."""
    conn_str = build_connection_string(config)
    return pyodbc.connect(conn_str, timeout=10)
