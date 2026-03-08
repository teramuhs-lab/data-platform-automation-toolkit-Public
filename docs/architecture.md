# Data Platform Automation Toolkit

## Architecture & Build Documentation

This document explains how the Data Platform Automation Toolkit was designed and implemented step-by-step.

The goal of the project is to demonstrate **Database DevOps practices**, including:

- Database automation
- Config-driven infrastructure
- Secure credential management
- CLI-based operational tooling
- DevOps-friendly project structure

The toolkit automates database operational tasks such as:

- Health checks
- Backups
- Restore validation
- Failover testing

---

## Step 1 -- Repository Initialization

### Objective

Create a professional DevOps project structure that is maintainable, scalable, and production-ready.

### What was implemented

A structured repository layout using the Python `src` pattern:

```
data-platform-automation-toolkit/
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── config/
│   ├── env-dev.yml
│   ├── env-prod.yml
│   └── env-docker.yml
├── src/dbops/
│   ├── cli.py
│   ├── config.py
│   ├── db.py
│   ├── logging.py
│   └── commands/
│       ├── healthcheck.py
│       ├── backup.py
│       ├── restore.py
│       └── failover_test.py
└── tests/
    ├── test_config.py
    ├── test_db.py
    └── test_healthcheck.py
```

### What this accomplishes

- Separates application code from configuration
- Supports CI/CD pipelines
- Makes the project easier to test
- Ensures Python packaging standards are followed

### Why this matters

Many automation tools fail because they grow into large scripts without structure.
This repository structure ensures the project can evolve into a maintainable DevOps tool.

---

## Step 2 -- Environment Configuration System

### Objective

Allow the toolkit to support multiple environments such as:

- Development (`env-dev.yml`)
- Production (`env-prod.yml`)
- Docker container-to-container (`env-docker.yml`)

### Implementation

Environment configuration is stored in YAML files under `config/`.

Example (`config/env-dev.yml`):

```yaml
environment: dev
sql:
  driver: "ODBC Driver 18 for SQL Server"
  server: "127.0.0.1,1433"
  database: "master"
  username: "sa"
  password_env: "DBOPS_SQL_PASSWORD"
options:
  encrypt: false
  trust_server_certificate: true
backup:
  backup_dir: "/backups"
```

### What this accomplishes

- Removes hardcoded infrastructure values
- Allows environment switching with a single flag
- Keeps the application configuration flexible

### Why this matters

DevOps tools should be environment-agnostic.
The same command works in multiple environments simply by changing the config file:

```bash
dbops healthcheck --config config/env-dev.yml
dbops healthcheck --config config/env-prod.yml
dbops healthcheck --config config/env-docker.yml
```

---

## Step 3 -- Secure Credential Management

### Objective

Prevent database passwords from being stored in source code or configuration files.

### Implementation

Passwords are loaded from environment variables at runtime.
The YAML config references the variable name, not the value:

```yaml
sql:
  password_env: "DBOPS_SQL_PASSWORD"   # resolved from os.environ at runtime
```

The password is stored in `.env.example` for local development and injected via `env_file` in Docker Compose.

Example command:

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops healthcheck
```

### What this accomplishes

- Prevents secrets from being committed to Git
- Allows integration with secret managers
- Follows DevSecOps best practices

### Why this matters

In production environments, credentials should be retrieved from:

- Environment variables
- Secret managers (HashiCorp Vault, Azure Key Vault, AWS Secrets Manager)
- CI/CD pipeline secrets

This project is structured to support all of these approaches without code changes.

---

## Step 4 -- CLI Interface Design

### Objective

Provide a command-line interface for database operations.

### Implementation

A CLI tool named `dbops` was created using **Typer** with four subcommands:

```bash
dbops healthcheck    # Database diagnostics
dbops backup         # Backup with compression + verification
dbops restore        # Restore with WITH MOVE support
dbops failover-test  # Write/read validation + AG checks
```

Global options:

```bash
dbops --json healthcheck   # Machine-readable JSON output
dbops --help               # Show all commands
```

### What this accomplishes

- Allows operations engineers to run database automation easily
- Provides a consistent interface for all database tasks
- Supports integration with automation pipelines and CI/CD

### Why this matters

CLI tools are the standard interface for DevOps automation.
They can be called from scripts, cron jobs, CI/CD pipelines, and monitoring systems.

---

## Step 5 -- Configuration Loader (`config.py`)

### Objective

Load and validate environment configuration from YAML files.

### Implementation

The `config.py` module:

- Reads YAML configuration files
- Validates the file exists
- Resolves secrets from environment variables
- Returns a structured configuration dictionary

```python
from dbops.config import load_config

config = load_config("config/env-dev.yml")
# config["sql"]["password"] is resolved from os.environ["DBOPS_SQL_PASSWORD"]
```

### What this accomplishes

- Centralized configuration management
- Validation of configuration errors at load time
- Clean separation of secrets from config

### Why this matters

Without configuration validation, applications fail unpredictably at runtime.
The config loader ensures errors are caught early with clear messages.

---

## Step 6 -- Database Connection Layer (`db.py`)

### Objective

Create a reusable database connection layer.

### Implementation

The `db.py` module:

- Builds SQL Server connection strings from config
- Connects using `pyodbc` with ODBC Driver 18
- Handles encryption and certificate trust settings
- Exposes `build_connection_string()` for testability

```python
from dbops.db import get_connection

conn = get_connection(config)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sys.databases")
```

### What this accomplishes

- Isolates database logic from command logic
- Simplifies command implementation
- Prevents duplicated connection code

### Why this matters

Separating database access from business logic improves:

- **Maintainability** -- connection logic changes in one place
- **Testability** -- commands can be tested with mocked connections
- **Reliability** -- consistent connection handling across all commands

---

## Step 7 -- Docker Development Environment

### Objective

Provide a one-command local development environment with SQL Server.

### Implementation

Docker Compose runs SQL Server 2022 Developer Edition:

```bash
docker compose --env-file .env.example -f docker/docker-compose.yml up -d
```

A separate `Dockerfile` packages the `dbops` CLI with ODBC Driver 18 for containerized execution:

```bash
docker run --rm --network docker_default \
  -v $(pwd)/config:/app/config:ro \
  -e DBOPS_SQL_PASSWORD=DevStr0ngPass2026 \
  dbops:latest healthcheck --config config/env-docker.yml
```

### What this accomplishes

- Zero-setup local development (no SQL Server installation needed)
- Reproducible environment across machines
- Container-to-container testing capability

### Why this matters

DevOps engineers expect infrastructure to be containerized and reproducible.
A working `docker compose up` demonstrates operational maturity.

---

## Step 8 -- Health Check Command

### Objective

Provide an automated way to verify database connectivity and operational status.

### Implementation

The `healthcheck` command runs six diagnostic checks:

| Check | SQL Source |
|-------|-----------|
| Connectivity | Connection latency measurement |
| Server Identity | `SELECT @@SERVERNAME, @@VERSION` |
| Database List | `sys.databases` + `sys.master_files` (with sizes) |
| Disk Space | `EXEC xp_fixeddrives` |
| AG Replica Status | `sys.availability_groups` + `sys.dm_hadr_availability_replica_states` |
| Top 5 Wait Stats | `sys.dm_os_wait_stats` (filtered for actionable waits) |

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops healthcheck
```

### What this accomplishes

- Verifies operational health of SQL Server environments
- Detects connectivity issues, disk pressure, and performance problems
- Provides baseline diagnostics for troubleshooting

---

## Step 9 -- Backup Automation

### Objective

Automate database backup operations with verification.

### Implementation

The `backup` command:

- Backs up a specific database or all user databases
- Creates timestamped `.bak` files (e.g., `TestDB_20260308_164735.bak`)
- Uses `COPY_ONLY, COMPRESSION, CHECKSUM` for safe, efficient backups
- Runs `RESTORE VERIFYONLY WITH CHECKSUM` to validate backup integrity

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops backup --database TestDB
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops backup                    # all user DBs
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops backup --no-verify        # skip verification
```

### What this accomplishes

- Automates manual DBA operations
- Standardizes backup procedures
- Verifies every backup is restorable

---

## Step 10 -- Restore Validation

### Objective

Verify that backups can be successfully restored to a target database.

### Implementation

The `restore` command:

- Reads logical file names via `RESTORE FILELISTONLY`
- Auto-generates `WITH MOVE` clauses for data and log files
- Restores to a named target or auto-generates `<source>_restored`
- Verifies the restored database comes ONLINE

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops restore -f /backups/TestDB_20260308.bak -t TestDB_Dev
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops restore -f /backups/TestDB_20260308.bak -t TestDB_Dev --replace
```

### What this accomplishes

- Ensures backup integrity through actual restore testing
- Validates disaster recovery procedures
- Supports dev environment provisioning from production backups

---

## Step 11 -- Failover Testing

### Objective

Validate database availability and high-availability readiness.

### Implementation

The `failover-test` command has two versions:

**Version A (any SQL Server):**

- Creates a test table, inserts a row, reads it back, cleans up
- Proves write/read functionality is working

**Version B (AG environments):**

- Queries AG replica status (primary/secondary roles)
- Validates synchronization health across replicas
- Shows log send queue and redo queue sizes
- Optionally triggers `ALTER AVAILABILITY GROUP ... FAILOVER`

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops failover-test --database TestDB
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops failover-test --execute-failover  # caution
```

### What this accomplishes

- Supports high-availability testing
- Improves disaster recovery readiness
- Validates database cluster health without waiting for a real failure

---

## Step 12 -- Logging System

### Objective

Provide consistent operational logging across all commands.

### Implementation

Three output modes:

| Output | Destination | Purpose |
|--------|-------------|---------|
| **Console** | Terminal | Rich-formatted tables, panels, color-coded status |
| **File** | `./logs/dbops.log` | Timestamped plain text for audit trails |
| **JSON** | stdout | Machine-readable for CI/CD and monitoring |

```bash
dbops healthcheck                 # Rich console output
dbops --json healthcheck          # JSON for pipelines
cat logs/dbops.log                # File log for auditing
```

### What this accomplishes

- Simplifies troubleshooting with structured logs
- Improves observability in production
- Supports integration with monitoring and alerting systems

---

## Step 13 -- Testing Framework

### Objective

Ensure reliability of toolkit components through automated testing.

### Implementation

25 unit tests across three test files:

| File | Tests | What it validates |
|------|-------|------------------|
| `test_config.py` | 7 | Config loading, env var resolution, error handling |
| `test_db.py` | 11 | Connection string builder, pyodbc integration, error propagation |
| `test_healthcheck.py` | 7 | Mocked DB queries, JSON mode, connection failure handling |

All database calls are mocked -- tests run without a live SQL Server.

```bash
pytest tests/ -v
```

### What this accomplishes

- Prevents regressions when adding new features
- Improves code quality through test-driven validation
- Supports CI/CD integration (tests run on every push)

---

## Step 14 -- Docker CLI Image

### Objective

Package the `dbops` CLI into a container for portable execution.

### Implementation

The `Dockerfile` builds a slim image with:

- Python 3.11
- Microsoft ODBC Driver 18 for SQL Server
- The `dbops` CLI installed via `pip install .`
- Mount points for `/app/config` and `/app/logs`

```bash
docker build -f docker/Dockerfile -t dbops:latest .
docker run --rm dbops:latest --help
```

### What this accomplishes

- Portable CLI that runs anywhere Docker runs
- No local Python or ODBC driver installation needed
- Consistent execution environment across teams

---

## Step 15 -- CI/CD Pipeline

### Objective

Automate testing, linting, and Docker builds on every code change.

### Implementation

GitHub Actions pipeline with three jobs:

| Job | Trigger | What it does |
|-----|---------|-------------|
| **test** | Push/PR to `main` | `pytest` on Python 3.11 + 3.12 with coverage |
| **lint** | Push/PR to `main` | `ruff check` + `ruff format --check` |
| **docker** | After tests pass | Build Docker image + verify CLI runs |

```
push/PR to main
    ├── test (Python 3.11) ──┐
    ├── test (Python 3.12) ──┼── docker (build + verify)
    └── lint ────────────────┘
```

### What this accomplishes

- Catches bugs before they reach production
- Enforces code quality standards
- Validates the Docker image builds correctly

---

## Final Architecture

The toolkit follows a layered architecture:

```
CLI Layer (cli.py + Typer)
    │
Command Layer (healthcheck, backup, restore, failover-test)
    │
Database Layer (db.py + pyodbc)
    │
Configuration Layer (config.py + YAML + env vars)
```

This separation ensures:

- **Modular design** -- each layer can be modified independently
- **Testability** -- database calls are mockable at every layer
- **Extensibility** -- new commands plug in without changing existing code

---

## Why This Project Demonstrates Database DevOps Expertise

This project goes beyond writing scripts. It demonstrates the engineering practices that separate junior automation from production-grade tooling:

| Practice | How it's demonstrated |
|----------|----------------------|
| **Infrastructure as Code** | Docker Compose provisions SQL Server with one command |
| **Configuration Management** | YAML configs with environment separation (dev/prod/docker) |
| **Secret Management** | Passwords in env vars, never in code or config files |
| **Automation** | Four CLI commands replacing manual DBA procedures |
| **Testing** | 25 unit tests with mocked database calls |
| **CI/CD** | GitHub Actions pipeline with test, lint, and build stages |
| **Observability** | Structured logging (console + file + JSON) |
| **Containerization** | CLI packaged as a Docker image with ODBC drivers |
| **Documentation** | Architecture decisions documented with reasoning |

The toolkit is not a demo -- it connects to a real SQL Server, runs real T-SQL, and produces real operational output. Every command has been tested against SQL Server 2022 running in Docker.

---

## Future Enhancements

- [ ] Scheduled backup cron job via Docker
- [ ] Email/Slack alerting on healthcheck failures
- [ ] Multi-server support (run checks across a fleet)
- [ ] Full restore chain validation (Full + Diff + Log)
- [ ] AG failover with automatic rollback
- [ ] Prometheus metrics endpoint for monitoring integration
- [ ] Interactive TUI dashboard for real-time server status
- [ ] Azure Key Vault / HashiCorp Vault integration
- [ ] Kubernetes CronJob for scheduled database operations
- [ ] Cloud database support (Azure SQL, AWS RDS)
