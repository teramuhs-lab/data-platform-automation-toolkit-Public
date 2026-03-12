# Data Platform Automation Toolkit

## Architecture & Build Documentation

This document explains how the Data Platform Automation Toolkit was designed and implemented step-by-step.

The goal of the project is to demonstrate **Database DevOps practices**, including:

- **CI/CD for SQL Server** -- automated deployment pipelines across Azure DevOps, GitLab CI, and GitHub Actions
- **Schema as Code** -- versioned SQL migrations tracked in git
- **Database testing** -- automated validation that runs post-deploy
- **Drift detection** -- catch unauthorized changes to production
- **Operational automation** -- health checks, backups, restores, failover testing
- Config-driven infrastructure and secure credential management

The toolkit automates the full database lifecycle:

- Schema migrations and seed data deployment
- Post-deploy testing and drift detection
- Health checks, backups, restore validation, and failover testing
- All driven by CI/CD pipelines with approval gates

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

59 unit tests across five test files:

| File | Tests | What it validates |
|------|-------|------------------|
| `test_config.py` | 7 | Config loading, env var resolution, error handling |
| `test_db.py` | 11 | Connection string builder, pyodbc integration, error propagation |
| `test_healthcheck.py` | 7 | Mocked DB queries, JSON mode, connection failure handling |
| `test_migrate.py` | 20 | Script naming, checksums, GO splitting, version pattern regex |
| `test_drift_check.py` | 14 | Expected schema structure, live catalog queries |

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

## Step 15 -- Database Migrations (`migrate.py`)

### Objective

Manage SQL Server schema changes as versioned, source-controlled scripts -- the same way application code is managed.

### The Problem This Solves

As a DBA, you've probably done this:

1. Someone asks for a new table
2. You open SSMS, write `CREATE TABLE`, hit Execute
3. Maybe you save the script somewhere. Maybe you don't.
4. Three months later, nobody remembers what changed, when, or why
5. Dev, staging, and production have different schemas and nobody knows which is "right"

This is the #1 problem Database DevOps solves. **Every schema change becomes a file in git.**

### How Migrations Work

A migration is just a SQL file with a specific naming convention:

```
database/migrations/
├── V001__create_migration_tracking.sql     ← Runs first  (version 001)
├── V002__create_inventory_schema.sql       ← Runs second (version 002)
├── V003__create_backup_history.sql         ← Runs third  (version 003)
├── V004__create_alert_rules.sql            ← Runs fourth (version 004)
└── V005__add_stored_procedures.sql         ← Runs fifth  (version 005)
```

**The naming convention is critical:**

```
V001__create_migration_tracking.sql
│││    │
││└── Three digits — the version number (determines execution order)
│└── "V" means versioned (runs once, never again)
│
└── Double underscore separates version from description
```

When you run `dbops migrate`, the tool:

1. Reads all `V###__*.sql` files from `database/migrations/`
2. Connects to the database and checks which versions have already been applied (stored in `dbops.migration_history`)
3. For each unapplied script: runs it, records a SHA-256 checksum, logs the execution time
4. If a script was already applied but the file content changed (checksum mismatch), it **stops and warns you** -- this prevents silent corruption

```bash
# See what would run (without actually running it)
dbops migrate --database dbops_dev --dry-run

# Apply all pending migrations
dbops migrate --database dbops_dev

# Apply migrations + run database tests afterward
dbops migrate --database dbops_dev --test
```

### Repeatable Scripts (Seed Data)

Some data needs to be re-applied on every deployment -- lookup tables, default configuration, reference data. These use the `R` prefix:

```
database/seed-data/
├── R001__seed_environments.sql     ← Re-runs every deploy
└── R002__seed_alert_rules.sql      ← Re-runs every deploy
```

These scripts use `MERGE` statements to be **idempotent** -- they can run 100 times and produce the same result. This is important because unlike versioned migrations (which run once), seed scripts run on every deployment.

### The Migration History Table

The very first migration (`V001`) creates a tracking table:

```sql
dbops.migration_history
├── id              -- Auto-increment
├── version         -- "001", "002", etc.
├── script_name     -- Full filename
├── checksum        -- SHA-256 of file contents
├── applied_on      -- When it was applied (UTC)
├── applied_by      -- Who ran it (SUSER_SNAME())
├── execution_ms    -- How long it took
└── success         -- Did it work?
```

This table is the **source of truth** for what's been deployed. When you run `dbops migrate`, the tool compares this table against the files on disk to determine what's pending.

### GO Batch Splitting

SQL Server requires `GO` to separate certain statements (like `CREATE SCHEMA` from `CREATE TABLE`). The migration runner automatically splits scripts on `GO` boundaries and executes each batch separately -- just like SSMS does.

### What This Accomplishes

- Every schema change is tracked in git with a commit history
- You can recreate any database from scratch by running all migrations in order
- You always know what's deployed where (check `dbops.migration_history`)
- The checksum prevents anyone from silently modifying an already-applied migration

---

## Step 16 -- Schema Drift Detection (`drift_check.py`)

### Objective

Detect when the live database schema doesn't match what's in source control.

### The Problem This Solves

Drift happens when someone makes changes directly in the database without going through the migration pipeline:

- A developer adds a column in SSMS "just to test something" and forgets to remove it
- A DBA creates an index in production during an incident and never scripts it
- Someone drops a stored procedure that "wasn't being used"

Now your source-controlled migrations say one thing, but the database has something different. **This is drift**, and it's one of the most common causes of deployment failures.

### How Drift Detection Works

The `drift_check.py` command maintains a Python dictionary of what the migrations **should** have created:

```python
EXPECTED_SCHEMA = {
    "schemas": ["dbops", "inventory"],
    "tables": {
        "inventory.servers": ["server_id", "hostname", "port", ...],
        "inventory.environments": ["environment_id", "name", ...],
        ...
    },
    "procedures": [
        "inventory.usp_register_backup",
        ...
    ],
}
```

When you run `dbops drift-check`, it:

1. Queries the live database catalog (`sys.schemas`, `sys.tables`, `sys.columns`, `sys.procedures`)
2. Compares every schema, table, column, and stored procedure against the expected list
3. Reports what's **missing** (expected but not in DB) and what's **extra** (in DB but not expected)

```bash
dbops drift-check --database dbops_dev
```

**Clean output (no drift):**
```
┌──────┐
│CLEAN │ No drift detected — database matches source-controlled migrations.
└──────┘
```

**Drift detected:**
```
┌──────────────────────────────────┐
│ Type           │ Object          │ Detail                              │
│ EXTRA_COLUMN   │ inventory.servers.temp_flag │ Column exists but not in migrations │
│ MISSING_PROC   │ inventory.usp_register_backup │ Stored procedure expected but not found │
└──────────────────────────────────┘
DRIFT DETECTED — 2 drift(s) found
```

### When Drift Detection Runs

In all three CI/CD pipelines, drift detection runs **immediately after migration**:

```
dbops migrate --database dbops_dev    ← Apply changes
dbops drift-check --database dbops_dev   ← Verify everything matches
```

If drift is detected, the pipeline **fails** -- this forces the team to resolve the discrepancy before deploying further.

---

## Step 17 -- Database Testing

### Objective

Automatically verify that the database is in the correct state after migrations run.

### The Problem This Solves

Migrations can succeed (no SQL errors) but still leave the database in a bad state:

- A table was created but a foreign key was missed
- A stored procedure references a column that was renamed
- Seed data wasn't loaded
- A check constraint was defined incorrectly

Database tests catch these issues **before** the deployment reaches staging or production.

### How Database Tests Work

Test scripts live in `database/tests/` and follow a simple convention:

```sql
-- Each test increments a counter and prints PASS or FAIL
DECLARE @failures INT = 0;
DECLARE @total    INT = 0;

-- Test 1: Does the table exist?
SET @total += 1;
IF EXISTS (SELECT 1 FROM sys.tables WHERE name = 'servers')
    PRINT 'PASS: inventory.servers exists';
ELSE
BEGIN
    PRINT 'FAIL: inventory.servers missing';
    SET @failures += 1;
END

-- At the end: fail if any test failed
IF @failures > 0
    THROW 50000, 'Database validation failed', 1;
```

### What Gets Tested

**Schema validation** (`test_schema_validation.sql`):
- All schemas exist (`dbops`, `inventory`)
- All 7 tables exist with their expected columns
- All 3 stored procedures exist
- Foreign key count is correct
- Seed data is loaded

**Data integrity** (`test_data_integrity.sql`):
- Unique constraints prevent duplicates
- Foreign keys prevent orphan records
- Check constraints reject invalid data
- Default values are applied correctly
- Computed columns work

### How Tests Run in the Pipeline

```bash
# The --test flag runs database tests after applying migrations
dbops migrate --database dbops_dev --test
```

The migration runner finds all `test_*.sql` files in `database/tests/`, executes them, and reports PASS/FAIL. If any test fails, the pipeline stops.

---

## Step 18 -- CI/CD Pipelines (What They Are and How They Work)

### What is a CI/CD Pipeline?

If you're coming from a DBA background, think of a CI/CD pipeline as a **checklist that runs automatically every time someone changes the code**.

**CI (Continuous Integration):** Every time you push code to git, automated checks run to make sure you didn't break anything -- linting, unit tests, Docker builds. This happens on every push.

**CD (Continuous Delivery/Deployment):** After CI passes, the changes are automatically deployed to environments -- dev first, then staging, then production. Each step can have approval gates where a human reviews and clicks "approve" before it continues.

**Without CI/CD (the old way):**
1. Developer writes SQL script
2. Emails it to the DBA
3. DBA opens SSMS, runs it manually in dev
4. If it works, DBA runs it in staging
5. Waits for change window, runs it in prod
6. If it fails at step 5, everyone panics

**With CI/CD (what this project demonstrates):**
1. Developer writes SQL migration file and pushes to git
2. Pipeline automatically validates, deploys to dev, tests, deploys to staging
3. Senior DBA clicks "approve" for production
4. Pipeline deploys to prod and runs health checks
5. If anything fails, the pipeline stops and reports exactly what went wrong

### The Pipeline Stages

All three pipelines (Azure DevOps, GitLab CI, GitHub Actions) implement the same stages:

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  STAGE 1: VALIDATE (runs on every push and pull request)            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐    │
│  │ Lint Python  │  │ Unit Tests   │  │ Validate SQL Naming     │    │
│  │ (ruff)       │  │ (59 tests)   │  │ (V###__*.sql pattern)   │    │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘    │
│         │                │                      │                   │
│         └────────────────┼──────────────────────┘                   │
│                          ▼                                          │
│  ┌──────────────────────────────────┐                               │
│  │ Docker Build (build image,       │                               │
│  │ verify CLI runs in container)    │                               │
│  └──────────────────────────────────┘                               │
│                          │                                          │
│                          ▼                                          │
│  STAGE 2: DEPLOY DEV (automatic — no human approval needed)         │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 1. dbops migrate --dry-run     ← Preview changes        │       │
│  │ 2. dbops migrate               ← Apply migrations       │       │
│  │ 3. dbops migrate --test        ← Run DB tests           │       │
│  │ 4. dbops drift-check           ← Verify schema matches  │       │
│  │ 5. dbops healthcheck           ← Verify DB is healthy   │       │
│  └──────────────────────────────────────────────────────────┘       │
│                          │                                          │
│                     ┌────┴────┐                                     │
│                     │ APPROVE │  ← Human clicks "approve"           │
│                     └────┬────┘                                     │
│                          ▼                                          │
│  STAGE 3: DEPLOY STAGING (same steps as dev)                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 1. dbops migrate --dry-run                               │       │
│  │ 2. dbops migrate --test                                  │       │
│  │ 3. dbops drift-check                                     │       │
│  └──────────────────────────────────────────────────────────┘       │
│                          │                                          │
│                     ┌────┴────┐                                     │
│                     │ APPROVE │  ← Senior DBA / Change Advisory     │
│                     └────┬────┘                                     │
│                          ▼                                          │
│  STAGE 4: DEPLOY PRODUCTION                                         │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 1. dbops migrate --dry-run     ← REVIEW THIS CAREFULLY  │       │
│  │ 2. dbops migrate --test        ← Apply + validate       │       │
│  │ 3. dbops drift-check           ← Confirm schema matches │       │
│  │ 4. dbops healthcheck           ← Final health check     │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### What Triggers the Pipeline?

Every pipeline starts when a specific event happens in git:

| Event | What happens |
|-------|-------------|
| You push code to `main` | Full pipeline runs: validate → deploy dev → staging → prod |
| You open a pull request | Only validation runs: lint, tests, SQL naming check |
| You push to a `release/*` branch | Full pipeline runs (Azure DevOps only) |

This is configured at the top of each pipeline file:

```yaml
# Azure DevOps
trigger:
  branches:
    include:
      - main
      - release/*
  paths:
    include:
      - database/**      # Only trigger if database files changed
      - src/**

# GitLab CI
rules:
  - if: $CI_COMMIT_BRANCH == "main"
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"

# GitHub Actions
on:
  push:
    branches: [main]
    paths: ['database/**', 'src/**']
  pull_request:
    branches: [main]
```

### How Secrets Work in Pipelines

Your database password can't be hardcoded in the pipeline file -- that would be visible to anyone with repo access. Each platform has its own way to store secrets securely:

| Platform | Where secrets live | How they're accessed |
|----------|-------------------|---------------------|
| **Azure DevOps** | Variable Groups (`dbops-secrets`) | `$(DBOPS_SQL_PASSWORD)` |
| **GitLab CI** | Settings → CI/CD → Variables (masked) | `$DBOPS_SQL_PASSWORD` |
| **GitHub Actions** | Settings → Secrets → Repository secrets | `${{ secrets.DBOPS_SQL_PASSWORD }}` |

In all three cases, the secret is injected as an environment variable at runtime. The pipeline file only references the variable name, never the actual password.

### How Approval Gates Work

Approval gates are the "are you sure?" step before deploying to staging or production. Each platform implements this differently:

**Azure DevOps:**
- You create "Environments" in the Azure DevOps portal (e.g., `dbops-staging`, `dbops-prod`)
- On each environment, you add "Approvals and checks"
- You specify who can approve (e.g., "DBA Team" group)
- When the pipeline reaches that stage, it pauses and sends a notification
- An approver reviews the dry-run output and clicks "Approve" or "Reject"

**GitLab CI:**
- Uses `when: manual` on the deploy jobs
- The pipeline shows a "play" button next to the staging/prod jobs
- Someone with the right permissions clicks it to proceed
- In GitLab Premium, you can add "Protected Environments" with required approvals

**GitHub Actions:**
- You create "Environments" in the repository settings
- On each environment, you add "Required reviewers"
- The pipeline pauses and creates a review request
- An approver clicks "Approve" in the GitHub UI

---

## Step 19 -- Azure DevOps Pipeline (PowerShell)

### File: `pipelines/azure-pipelines.yml`

### Why PowerShell?

Azure DevOps + SQL Server is a Windows-first ecosystem. In the real world:

- Azure DevOps agents are often Windows machines (self-hosted or `windows-latest`)
- DBAs already know PowerShell from managing SQL Server
- PowerShell has native SQL Server cmdlets (`Invoke-Sqlcmd`, `SqlServer` module)
- Using PowerShell in Azure DevOps shows you understand the platform's native tooling

This is why the Azure DevOps pipeline uses `pwsh:` (PowerShell Core) while the GitLab and GitHub pipelines use bash.

### Key Azure DevOps Concepts

**Stages:** Top-level grouping of work. Our pipeline has four stages: `Build`, `DeployDev`, `DeployStaging`, `DeployProd`. Stages run in sequence by default.

```yaml
stages:
  - stage: Build            # Runs first
  - stage: DeployDev        # Runs after Build succeeds
    dependsOn: Build
  - stage: DeployStaging    # Runs after DeployDev succeeds
    dependsOn: DeployDev
  - stage: DeployProd       # Runs after DeployStaging succeeds
    dependsOn: DeployStaging
```

**Jobs:** Units of work within a stage. Jobs in the same stage can run in parallel.

```yaml
# These three jobs run at the same time within the Build stage:
jobs:
  - job: Lint               # Checks code style
  - job: UnitTests          # Runs pytest
  - job: DockerBuild        # Builds container image
    dependsOn: UnitTests    # ...but this one waits for UnitTests
```

**Deployment Jobs:** Special jobs that target an "environment." This is what enables approval gates.

```yaml
- deployment: DeployProdDB
  environment: 'dbops-prod'     # ← This name links to approvals in Azure DevOps portal
  strategy:
    runOnce:
      deploy:
        steps:
          - pwsh: dbops migrate ...
```

**Variable Groups:** Shared secret storage. You create a variable group called `dbops-secrets` in Azure DevOps, add `DBOPS_SQL_PASSWORD` as a secret variable, and reference it in the pipeline:

```yaml
variables:
  - group: dbops-secrets     # Makes all variables in this group available
```

**`pwsh:` vs `script:`:** The `pwsh:` task runs PowerShell Core (cross-platform). The `script:` task runs bash on Linux or cmd on Windows. We use `pwsh:` everywhere for consistency.

### PowerShell Patterns Used

**Exit code checking** -- PowerShell doesn't automatically fail a pipeline step when a command returns a non-zero exit code (unlike bash with `set -e`). You must check `$LASTEXITCODE` explicitly:

```powershell
dbops migrate --config "$(targetConfig)" --database "$(targetDB)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Migration failed."
    exit 1
}
```

**Colored output** -- `Write-Host -ForegroundColor` makes pipeline logs easier to scan:

```powershell
Write-Host "=== PROD: Migration Dry Run ===" -ForegroundColor Yellow
Write-Host "Migrations applied successfully." -ForegroundColor Green
Write-Error "PRODUCTION MIGRATION FAILED — investigate immediately."
```

**File validation with `Get-ChildItem`** -- PowerShell's native way to iterate files and validate naming:

```powershell
$migrations = Get-ChildItem -Path "database/migrations" -Filter "*.sql"
foreach ($file in $migrations) {
    if ($file.Name -notmatch '^V\d{3}__.+\.sql$') {
        Write-Error "Invalid migration name: $($file.Name)"
    }
}
```

---

## Step 20 -- GitLab CI Pipeline (Bash)

### File: `.gitlab-ci.yml`

### Key GitLab CI Concepts

**Stages:** Defined at the top of the file. Jobs in the same stage run in parallel; stages run in sequence.

```yaml
stages:
  - validate       # lint + tests + SQL naming (all run in parallel)
  - build          # Docker image
  - deploy-dev     # automatic
  - test-db        # database tests against dev
  - deploy-staging # manual approval
  - deploy-prod    # manual approval
```

**YAML Anchors (`&` and `*`):** GitLab supports YAML anchors to avoid repeating setup steps. We define a hidden job (prefixed with `.`) and reuse it:

```yaml
# Define once:
.python-setup: &python-setup
  image: python:${PYTHON_VERSION}-slim
  before_script:
    - pip install -e .

# Reuse many times:
migrate-dev:
  <<: *python-setup        # ← Inherits image + before_script
  script:
    - dbops migrate ...
```

This is the GitLab equivalent of Azure DevOps templates.

**`when: manual`:** This is how GitLab does approval gates. The job shows a "play" button in the GitLab UI:

```yaml
migrate-staging:
  when: manual              # ← Pipeline pauses here; someone must click "play"
  allow_failure: false      # ← Pipeline won't continue if this is skipped
```

**`needs:`:** Controls job dependencies. Without `needs`, jobs wait for all jobs in the previous stage:

```yaml
db-tests-dev:
  needs:
    - migrate-dev           # ← Only waits for this specific job, not the whole stage
```

**`rules:`:** Controls when a job runs. More flexible than `only/except`:

```yaml
rules:
  - if: $CI_COMMIT_BRANCH == "main"
    changes:
      - database/**         # ← Only run if database files changed
```

**Environments:** Links a job to a deployment target for tracking:

```yaml
migrate-staging:
  environment:
    name: staging
    url: https://staging.example.com
```

**Artifacts and Reports:** GitLab can display test results and coverage directly in merge requests:

```yaml
artifacts:
  reports:
    junit: report.xml       # ← Shows test results in MR UI
    coverage_report:
      coverage_format: cobertura
      path: coverage.xml    # ← Shows coverage in MR UI
```

---

## Step 21 -- GitHub Actions Pipeline (Bash)

### File: `.github/workflows/ci.yml`

### Key GitHub Actions Concepts

**Jobs (not stages):** GitHub Actions doesn't have "stages" as a first-class concept. Instead, jobs declare dependencies with `needs:`:

```yaml
jobs:
  lint:           # Runs immediately
  validate-sql:   # Runs immediately (parallel with lint)
  unit-tests:     # Runs immediately (parallel with lint)
  docker-build:
    needs: [unit-tests]     # ← Waits for unit-tests
  deploy-dev:
    needs: [lint, validate-sql, unit-tests, docker-build]  # ← Waits for all four
  deploy-staging:
    needs: [deploy-dev]     # ← Waits for dev deployment
  deploy-prod:
    needs: [deploy-staging] # ← Waits for staging deployment
```

**Environments:** Similar to Azure DevOps. You create environments in GitHub Settings → Environments and add protection rules:

```yaml
deploy-prod:
  environment:
    name: production        # ← Links to GitHub environment with required reviewers
```

To configure approval gates:
1. Go to Repository → Settings → Environments → "production"
2. Check "Required reviewers" and add team members
3. Optionally add a "Wait timer" (e.g., 15 minutes) for cooling-off period

**Concurrency:** Prevents multiple deployments from running at the same time:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # ← If a new push happens, cancel the old run
```

This prevents the scenario where you push twice in quick succession and two deployments race each other.

**Path Filters:** Only trigger the pipeline when relevant files change:

```yaml
on:
  push:
    paths:
      - 'database/**'       # ← Migration scripts changed
      - 'src/**'             # ← Python code changed
      - '.github/workflows/**'  # ← Pipeline itself changed
```

**Matrix Strategy:** Run the same tests across multiple Python versions in parallel:

```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12']  # ← Creates two parallel jobs
```

**GitHub-Specific Error Annotations:** The `::error` syntax creates clickable error messages in the GitHub PR UI:

```bash
echo "::error file=$f::Invalid migration name: $basename"
```

This makes validation failures easy to find -- GitHub highlights the exact file in the pull request.

---

## Step 22 -- Pipeline Comparison (Side by Side)

This is the educational payoff -- understanding that CI/CD is a **concept**, not a vendor. All three pipelines do the same thing with different syntax:

### Comparison: "Run a command"

```yaml
# Azure DevOps (PowerShell)
- pwsh: |
    dbops migrate --config "$(targetConfig)" --database "$(targetDB)"
    if ($LASTEXITCODE -ne 0) { exit 1 }
  displayName: 'Apply migrations'
  env:
    DBOPS_SQL_PASSWORD: $(DBOPS_SQL_PASSWORD)

# GitLab CI (Bash)
migrate-dev:
  script:
    - dbops migrate --config $TARGET_CONFIG --database $TARGET_DB
  variables:
    TARGET_CONFIG: "config/env-dev.yml"

# GitHub Actions (Bash)
- name: Apply migrations
  run: dbops migrate --config config/env-dev.yml --database dbops_dev
  env:
    DBOPS_SQL_PASSWORD: ${{ secrets.DBOPS_SQL_PASSWORD }}
```

### Comparison: "Require approval before deploying"

```yaml
# Azure DevOps
- deployment: DeployProdDB
  environment: 'dbops-prod'     # ← Approvals configured in portal

# GitLab CI
migrate-prod:
  when: manual                  # ← "Play" button in UI
  allow_failure: false

# GitHub Actions
deploy-prod:
  environment:
    name: production            # ← Required reviewers in settings
```

### Comparison: "Only run when database files change"

```yaml
# Azure DevOps
trigger:
  paths:
    include:
      - database/**

# GitLab CI
rules:
  - changes:
      - database/**

# GitHub Actions
on:
  push:
    paths:
      - 'database/**'
```

### Comparison: "Store and access secrets"

| Concept | Azure DevOps | GitLab CI | GitHub Actions |
|---------|-------------|-----------|----------------|
| Where to create | Pipelines → Library → Variable Groups | Settings → CI/CD → Variables | Settings → Secrets → Actions |
| Mark as secret | Check "Keep this value secret" | Check "Mask variable" | Secrets are always masked |
| Access in YAML | `$(DBOPS_SQL_PASSWORD)` | `$DBOPS_SQL_PASSWORD` | `${{ secrets.DBOPS_SQL_PASSWORD }}` |
| Scope | Variable group linked to pipeline | Project, group, or instance level | Repository or environment level |

### Full Platform Comparison

| Feature | Azure DevOps | GitLab CI | GitHub Actions |
|---------|-------------|-----------|----------------|
| Config file | `azure-pipelines.yml` | `.gitlab-ci.yml` | `.github/workflows/*.yml` |
| Execution unit | `pwsh:` / `script:` | `script:` | `run:` |
| Grouping | Stages → Jobs → Steps | Stages → Jobs | Jobs → Steps |
| Parallelism | Jobs in same stage | Jobs in same stage | Jobs without `needs:` |
| Dependencies | `dependsOn:` | `needs:` | `needs:` |
| DRY/reuse | Templates (separate files) | YAML anchors (`&` / `*`) | Reusable workflows / composite actions |
| Approval gates | Environment checks | `when: manual` / protected envs | Environment protection rules |
| Secret injection | Variable groups + `$(VAR)` | CI/CD variables + `$VAR` | Secrets + `${{ secrets.VAR }}` |
| Test reporting | `PublishTestResults@2` | `reports: junit:` | Upload artifact (no native display) |
| Coverage | `PublishCodeCoverageResults@2` | `coverage_report:` | Third-party actions |
| Container registry | Azure Container Registry | GitLab Container Registry | GitHub Container Registry |
| Runner | Microsoft-hosted or self-hosted | Shared or self-hosted | GitHub-hosted or self-hosted |
| Best for | SQL Server / Windows / Azure shops | Self-hosted / enterprise GitLab | Open source / GitHub-native teams |

---

## Step 15 (original) -- CI/CD Pipeline (Legacy Section)

> **Note:** This was the original CI/CD section covering the basic GitHub Actions pipeline.
> It has been superseded by Steps 18-22 above, which cover all three pipelines in detail.
> Kept here for historical reference.

GitHub Actions pipeline with the original three jobs:

| Job | Trigger | What it does |
|-----|---------|-------------|
| **test** | Push/PR to `main` | `pytest` on Python 3.11 + 3.12 with coverage |
| **lint** | Push/PR to `main` | `ruff check` + `ruff format --check` |
| **docker** | After tests pass | Build Docker image + verify CLI runs |

---

## Final Architecture

The toolkit follows a layered architecture:

```
┌──────────────────────────────────────────────────────────────┐
│                    CI/CD Pipelines                            │
│  Azure DevOps (PowerShell) │ GitLab CI │ GitHub Actions      │
│  Trigger → Validate → Deploy Dev → Staging → Production      │
└──────────────────────┬───────────────────────────────────────┘
                       │ calls
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    CLI Layer (cli.py + Typer)                 │
│  dbops migrate │ drift-check │ healthcheck │ backup │ ...    │
└──────────────────────┬───────────────────────────────────────┘
                       │ delegates to
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Command Layer                              │
│  migrate.py │ drift_check.py │ healthcheck.py │ backup.py    │
│  restore.py │ failover_test.py                               │
└──────────────────────┬───────────────────────────────────────┘
                       │ uses
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Database Layer (db.py + pyodbc)            │
│  Connection string builder │ SQL Server via ODBC Driver 18   │
└──────────────────────┬───────────────────────────────────────┘
                       │ configured by
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Configuration Layer                        │
│  config.py + YAML (env-dev/staging/prod/docker) + env vars   │
└──────────────────────────────────────────────────────────────┘
                       │ schema defined in
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Database Schema (database/)                │
│  migrations/ (V001-V005) │ seed-data/ (R001-R002)            │
│  tests/ (schema validation + data integrity)                 │
└──────────────────────────────────────────────────────────────┘
```

This separation ensures:

- **Modular design** -- each layer can be modified independently
- **Testability** -- database calls are mockable at every layer
- **Extensibility** -- new commands plug in without changing existing code
- **Pipeline portability** -- all three CI/CD platforms call the same CLI commands

---

## Why This Project Demonstrates Database DevOps Expertise

This project goes beyond writing scripts. It demonstrates the engineering practices that separate a DBA who runs scripts from a Database DevOps Engineer who builds systems:

| Practice | How it's demonstrated |
|----------|----------------------|
| **Schema as Code** | 5 versioned SQL migrations + 2 seed scripts tracked in git |
| **Database CI/CD** | Three pipelines (Azure DevOps, GitLab, GitHub Actions) with multi-stage deployment |
| **Approval Gates** | Staging and production require manual approval before deployment |
| **Drift Detection** | Automated comparison of live schema vs. source-controlled migrations |
| **Database Testing** | SQL validation scripts verify schema, constraints, and data post-deploy |
| **Infrastructure as Code** | Docker Compose provisions SQL Server with one command |
| **Configuration Management** | YAML configs with environment separation (dev/staging/prod/docker) |
| **Secret Management** | Passwords in env vars / variable groups / CI secrets, never in code |
| **Operational Automation** | Six CLI commands replacing manual DBA procedures |
| **Testing** | 59 unit tests with mocked database calls |
| **Observability** | Structured logging (console + file + JSON) |
| **Containerization** | CLI packaged as a Docker image with ODBC drivers |
| **Cross-Platform Fluency** | Azure DevOps (PowerShell), GitLab CI (bash), GitHub Actions (bash) |
| **Documentation** | Architecture decisions documented with reasoning |

The toolkit is not a demo -- it connects to a real SQL Server, runs real T-SQL, and produces real operational output. Every command has been tested against SQL Server 2022 running in Docker.

---

## Future Enhancements

- [ ] Rollback migrations (`U###` undo scripts)
- [ ] Dynamic drift detection (parse expected schema from migration files instead of hardcoding)
- [ ] Azure DevOps pipeline templates (reusable YAML for deploy stages)
- [ ] Docker Compose auto-migration on startup
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
