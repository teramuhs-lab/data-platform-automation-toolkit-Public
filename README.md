# Data Platform Automation Toolkit

A production-grade **Database DevOps CLI** built in Python for automating SQL Server operations -- health checks, backups, restores, and failover validation.

Built for DBAs and DevOps engineers who need reliable, repeatable database automation instead of ad-hoc scripts.

## The Problem

Database operations in most organizations are manual, error-prone, and undocumented:

- Health checks are run by hand (or not at all)
- Backups succeed but are never verified
- Restores are tested only during actual disasters
- Failover readiness is assumed, not validated

This toolkit automates all of it through a single CLI with structured output, file logging, and JSON mode for CI/CD integration.

## Features

| Command | What it does |
|---------|-------------|
| `dbops healthcheck` | Server identity, database states, disk space, AG status, top wait stats |
| `dbops backup` | Full backup with `COMPRESSION`, `CHECKSUM`, and `RESTORE VERIFYONLY` |
| `dbops restore` | Restore with auto `WITH MOVE`, target naming, and status verification |
| `dbops failover-test` | Write/read validation + AG replica health + optional failover trigger |

**Additional capabilities:**

- **Rich console output** -- Tables, panels, and color-coded status icons
- **File logging** -- Every run logged to `./logs/dbops.log`
- **JSON mode** -- `dbops --json healthcheck` for machine-readable output
- **YAML config** -- Environment-specific settings (dev/prod/docker)
- **Docker support** -- Containerized CLI + SQL Server 2022 dev environment
- **CI/CD pipeline** -- GitHub Actions with tests, linting, and Docker build

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/teramuhs-lab/data-platform-automation-toolkit-Public.git
cd data-platform-automation-toolkit-Public

pip install -e .
```

### 2. Start SQL Server (Docker)

```bash
docker compose --env-file .env.example -f docker/docker-compose.yml up -d
```

This spins up SQL Server 2022 Developer Edition on `localhost:1433`.

### 3. Run a health check

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops healthcheck
```

Output:

```
Connectivity Check: OK  Connected to 127.0.0.1,1433 in 0.05s

Server Identity
 server_name   | server_version
 ee5c1fca0e7c  | Microsoft SQL Server 2022 (RTM-CU23)

Database List
 name    | status  | recovery_model | size_mb
 master  | ONLINE  | SIMPLE         | 6.25
 model   | ONLINE  | FULL           | 16.00
 msdb    | ONLINE  | SIMPLE         | 16.56
 tempdb  | ONLINE  | SIMPLE         | 72.00

Disk Space
 drive | MB free
 C     | 880244

Health check complete.
```

## Command Examples

```bash
# Health check (default config)
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops healthcheck

# Health check with JSON output (for CI/CD)
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops --json healthcheck

# Backup a specific database
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops backup --database MyDB

# Backup all user databases
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops backup

# Backup without verification
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops backup --database MyDB --no-verify

# Restore to a new database
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops restore -f /backups/MyDB_20260308.bak -t MyDB_Dev

# Restore with overwrite
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops restore -f /backups/MyDB_20260308.bak -t MyDB_Dev --replace

# Failover validation (write/read test + AG check)
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops failover-test --database MyDB

# Use a different config
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops healthcheck --config config/env-prod.yml
```

## Project Structure

```
data-platform-automation-toolkit/
├── .github/workflows/ci.yml    # GitHub Actions CI pipeline
├── .env.example                # Password + env vars (single source of truth)
├── pyproject.toml              # Python project config (Typer, PyYAML, pyodbc, Rich)
│
├── docker/
│   ├── Dockerfile              # Containerized dbops CLI with ODBC Driver 18
│   └── docker-compose.yml      # SQL Server 2022 + dbops
│
├── config/
│   ├── env-dev.yml             # Dev: localhost, debug logging
│   ├── env-prod.yml            # Prod: trusted connections, retention policies
│   └── env-docker.yml          # Docker: container-to-container networking
│
├── src/dbops/
│   ├── cli.py                  # Typer CLI with 4 subcommands
│   ├── config.py               # YAML loader + env var resolution
│   ├── db.py                   # pyodbc connection string builder
│   ├── logging.py              # Rich console + file log + JSON mode
│   └── commands/
│       ├── healthcheck.py      # 6 diagnostic queries
│       ├── backup.py           # BACKUP DATABASE with VERIFYONLY
│       ├── restore.py          # RESTORE with auto WITH MOVE
│       └── failover_test.py    # Write/read test + AG validation
│
└── tests/
    ├── test_config.py          # 7 tests: config loading + env resolution
    ├── test_db.py              # 11 tests: connection string builder
    └── test_healthcheck.py     # 7 tests: mocked DB healthcheck
```

## Configuration

Secrets live in `.env.example` (never hardcoded in config files):

```
DBOPS_SQL_PASSWORD=DevStr0ngPass2026
```

Environment configs in `config/` reference secrets by name:

```yaml
sql:
  password_env: "DBOPS_SQL_PASSWORD"   # resolved at runtime from os.environ
```

## Architecture & Build Documentation

For a detailed walkthrough of every design decision, implementation step, and the reasoning behind each component, see:

**[docs/architecture.md](docs/architecture.md)**

This document covers all 15 build steps, from repository initialization through CI/CD pipeline setup, and explains why this project demonstrates Database DevOps expertise.

## CI/CD

GitHub Actions pipeline runs on every push/PR to `main`:

| Job | What it does |
|-----|-------------|
| **test** | `pytest` on Python 3.11 + 3.12 with coverage |
| **lint** | `ruff check` + `ruff format --check` |
| **docker** | Build image + verify CLI runs |

## Tech Stack

- **Python 3.11+** -- CLI and automation logic
- **Typer** -- CLI framework (built on Click)
- **Rich** -- Terminal tables, panels, and formatting
- **pyodbc** -- SQL Server connectivity via ODBC Driver 18
- **PyYAML** -- Environment configuration
- **Docker** -- Containerized SQL Server 2022 + CLI image
- **pytest** -- 25 unit tests with mocked DB calls
- **GitHub Actions** -- CI/CD pipeline

## Roadmap

- [ ] Scheduled backup cron job via Docker
- [ ] Email/Slack alerting on healthcheck failures
- [ ] Multi-server support (run checks across a fleet)
- [ ] Full restore chain validation (Full + Diff + Log)
- [ ] AG failover with automatic rollback
- [ ] Prometheus metrics endpoint for monitoring integration
- [ ] Interactive TUI dashboard for real-time server status
- [ ] Azure Key Vault integration for secrets management

## License

MIT
