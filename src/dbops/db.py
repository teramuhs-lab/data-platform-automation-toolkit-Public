"""Database connection management for SQL Server.

This module has three jobs:
  1. build_connection_string — turn a config dict into an ODBC connection string
  2. ensure_database         — create the target database if it doesn't exist
  3. get_connection          — open a connection (with retries for Azure SQL)

Everything uses pyodbc, the standard Python driver for SQL Server. pyodbc
speaks to SQL Server through the "ODBC Driver 18 for SQL Server" (an OS-level
driver we install separately — see the CI pipeline or Docker image).
"""

import time

import pyodbc


def build_connection_string(config: dict) -> str:
    """Turn a config dict into an ODBC connection string.

    An ODBC connection string is a semicolon-separated list of key=value
    pairs that tell the driver how to find and authenticate to the database.
    Example output:
      DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=master;...
    """
    # The config has two sections we care about:
    #   sql     — server, database, credentials (always required)
    #   options — encryption and cert flags (optional, have defaults)
    sql = config["sql"]
    options = config.get("options", {})

    # Build the string piece by piece. f-strings with double braces {{ }}
    # produce a literal single brace in the output — the driver name needs
    # to be wrapped in braces like {ODBC Driver 18 for SQL Server}.
    return (
        f"DRIVER={{{sql['driver']}}};"
        f"SERVER={sql['server']};"
        f"DATABASE={sql['database']};"
        f"UID={sql['username']};"
        f"PWD={sql['password']};"
        # Encrypt: Azure SQL requires 'yes'; local Docker SQL can use 'no'.
        f"Encrypt={'yes' if options.get('encrypt', False) else 'no'};"
        # TrustServerCertificate: skip cert validation. Fine for dev/lab,
        # but should be 'no' in production with a real certificate chain.
        f"TrustServerCertificate={'yes' if options.get('trust_server_certificate', True) else 'no'};"
    )


def ensure_database(config: dict) -> None:
    """Create the target database if it doesn't already exist.

    Why this exists: when the CI pipeline spins up a fresh Docker SQL Server,
    only the system databases (master, model, msdb, tempdb) exist. Our
    migrations need 'dbops_dev' to exist before they can run.

    For Azure SQL: CREATE DATABASE via 'master' is restricted for regular
    SQL logins, and the databases are already provisioned by Terraform.
    So if the connection to 'master' fails, we assume it's Azure SQL and
    quietly move on.
    """
    sql = config["sql"]
    db_name = sql["database"]

    # We can't run CREATE DATABASE while connected to the target database —
    # it doesn't exist yet. So we connect to 'master' (the system database
    # that always exists) and run the CREATE from there.
    master_config = {**config, "sql": {**sql, "database": "master"}}

    try:
        conn = get_connection(master_config)
        # autocommit=True means each statement commits immediately. This is
        # important because CREATE DATABASE can't run inside a transaction.
        conn.autocommit = True
        cursor = conn.cursor()
        # DB_ID() returns NULL if the database doesn't exist. We use a
        # parameter (?) for the check, but brackets for the CREATE because
        # SQL Server doesn't allow parameters on DDL statements.
        cursor.execute(f"IF DB_ID(?) IS NULL CREATE DATABASE [{db_name}]", (db_name,))
        cursor.close()
        conn.close()
    except pyodbc.Error:
        # Azure SQL case — database must already exist (Terraform created it).
        pass


def get_connection(
    config: dict, retries: int = 5, delay: int = 10
) -> pyodbc.Connection:
    """Open a pyodbc connection to SQL Server, with retries.

    Why retries: Azure SQL Serverless auto-pauses after 60 minutes of no
    activity to save money. Waking it up takes 30-60 seconds, during which
    the first connection attempt returns "database is not currently
    available". Retrying fixes it.

    Args:
        config   — the parsed YAML config (has sql + options sections)
        retries  — how many times to try before giving up
        delay    — seconds to wait between retries
    """
    conn_str = build_connection_string(config)

    # timeout here is how long each attempt waits for the TCP handshake.
    # Defaults to 30s. Configurable per environment via options.connection_timeout.
    timeout = config.get("options", {}).get("connection_timeout", 30)

    # Try up to `retries` times. If the last attempt still fails, re-raise.
    for attempt in range(1, retries + 1):
        try:
            return pyodbc.connect(conn_str, timeout=timeout)
        except pyodbc.Error:
            # If this was the final attempt, give up and propagate the error.
            if attempt == retries:
                raise
            # Otherwise, print what happened and wait before trying again.
            print(
                f"Connection attempt {attempt}/{retries} failed, "
                f"retrying in {delay}s..."
            )
            time.sleep(delay)
