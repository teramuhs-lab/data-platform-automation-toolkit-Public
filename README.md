# Data Platform Automation Toolkit

A production-grade **Database DevOps CLI** built in Python for automating SQL Server operations -- CI/CD pipelines, schema migrations, drift detection, health checks, backups, restores, and failover validation.

Built for DBAs transitioning into Database DevOps Engineering who need to demonstrate CI/CD for SQL Server using real-world patterns across Azure DevOps, GitLab CI, and GitHub Actions.

## The Problem

Database operations in most organizations are manual, error-prone, and undocumented:

- Schema changes are applied by hand directly in production
- There's no version control for database objects
- Health checks are run by hand (or not at all)
- Backups succeed but are never verified
- Nobody knows if the live schema matches what's in source control (drift)
- CI/CD exists for application code but not for the database

This toolkit solves all of it through a single CLI with versioned migrations, automated testing, drift detection, and multi-platform CI/CD pipelines.

## Features

| Command | What it does |
|---------|-------------|
| `dbops migrate` | Apply versioned SQL migrations + seed data with checksum tracking |
| `dbops drift-check` | Detect schema drift between source control and live database |
| `dbops healthcheck` | Server identity, database states, disk space, AG status, top wait stats |
| `dbops backup` | Full backup with `COMPRESSION`, `CHECKSUM`, and `RESTORE VERIFYONLY` |
| `dbops restore` | Restore with auto `WITH MOVE`, target naming, and status verification |
| `dbops failover-test` | Write/read validation + AG replica health + optional failover trigger |
| `dbops dashboard` | Live TUI dashboard with auto-refresh for real-time server monitoring |

**CI/CD Pipelines (all three included):**

| Platform | File | Stages |
|----------|------|--------|
| **Azure DevOps** | `pipelines/azure-pipelines.yml` | Build → Deploy Dev → Deploy Staging (approval) → Deploy Prod (approval) |
| **GitLab CI** | `.gitlab-ci.yml` | Validate → Build → Deploy Dev → Test DB → Deploy Staging (manual) → Deploy Prod (manual) |
| **GitHub Actions** | `.github/workflows/ci.yml` | Validate → Build → Deploy Dev → Deploy Staging (environment protection) → Deploy Prod (environment protection) |

**Additional capabilities:**

- **Schema as Code** -- SQL migrations versioned in git with naming conventions
- **Database Testing** -- SQL validation scripts run post-deploy in the pipeline
- **Drift Detection** -- Compare live schema against source-controlled migrations
- **Seed Data Management** -- Reference data managed as repeatable scripts via MERGE
- **Rich console output** -- Tables, panels, and color-coded status icons
- **File logging** -- Every run logged to `./logs/dbops.log`
- **JSON mode** -- `dbops --json healthcheck` for machine-readable output
- **YAML config** -- Environment-specific settings (dev/staging/prod/docker)
- **Docker support** -- Containerized CLI + SQL Server 2022 dev environment

## Practical Use for SQL DBAs

This toolkit replaces manual, repetitive tasks you'd normally do in SSMS or with ad-hoc T-SQL.

### What it replaces in your daily work

**Morning health checks** -- Instead of opening SSMS, connecting to each server, and running queries one by one:
```bash
dbops healthcheck --config config/env-prod.yml
```
Connectivity, database status, disk space, AG replica health, and top wait stats in one shot. Add `--json` to pipe it into monitoring or a dashboard.

**Backup operations** -- Instead of right-clicking in SSMS or maintaining a patchwork of SQL Agent jobs with slightly different settings per server, you get a consistent backup with compression, checksum, and verification every time:
```bash
dbops backup --database MyApp
```

**Restore for dev/test refreshes** -- The restore command auto-detects data/log files and generates the WITH MOVE clauses for you. No more manually editing restore scripts when file paths differ between prod and dev:
```bash
dbops restore --source-backup /backups/MyApp.bak --target-data-dir /data/
```

**AG failover validation** -- Before a maintenance window, run a write/read test and check replica sync state programmatically, instead of manually querying DMVs:
```bash
dbops failover-test --config config/env-prod.yml
```

### Why CLI over SSMS

| Manual (SSMS) | This toolkit |
|---|---|
| Steps vary by who runs them | Same command, same result every time |
| Hard to audit | Commands logged with timestamps |
| Can't integrate with CI/CD | JSON output feeds into pipelines |
| One server at a time | Scriptable across environments |
| Knowledge lives in people's heads | Knowledge lives in config files and code |

### JSON Output for Monitoring and Dashboards

Every command supports `--json` for machine-readable output. This is what makes the toolkit useful beyond the terminal -- you can feed structured data into monitoring systems, dashboards, and alerting pipelines.

```bash
dbops --json healthcheck --config config/env-prod.yml
```

Output:

```json
[
  {
    "section": "connectivity",
    "status": "ok",
    "data": { "server": "prod-sql-01.corp.local,1433", "latency_sec": 0.045 }
  },
  {
    "section": "Server Identity",
    "status": "ok",
    "data": [
      { "server_name": "PROD-SQL-01", "server_version": "Microsoft SQL Server 2022 (RTM-CU23)" }
    ]
  },
  {
    "section": "Database List",
    "status": "ok",
    "data": [
      { "name": "AppDB", "status": "ONLINE", "recovery_model": "FULL", "size_mb": "2048.00" },
      { "name": "ReportDB", "status": "ONLINE", "recovery_model": "SIMPLE", "size_mb": "512.00" }
    ]
  },
  {
    "section": "Disk Space (xp_fixeddrives)",
    "status": "ok",
    "data": [
      { "drive": "C", "MB free": "102400" },
      { "drive": "D", "MB free": "524288" }
    ]
  },
  {
    "section": "AG Replica Status",
    "status": "ok",
    "data": [
      { "ag_name": "AG_Production", "replica": "PROD-SQL-01", "role": "PRIMARY", "sync_health": "HEALTHY" },
      { "ag_name": "AG_Production", "replica": "PROD-SQL-02", "role": "SECONDARY", "sync_health": "HEALTHY" }
    ]
  },
  {
    "section": "Top 5 Wait Stats",
    "status": "ok",
    "data": [
      { "wait_type": "CXPACKET", "wait_sec": "1234.56", "signal_wait_sec": "12.34", "wait_count": "98765" }
    ]
  },
  {
    "section": "summary",
    "status": "complete",
    "data": { "passed": 5, "skipped": 0, "server": "prod-sql-01.corp.local,1433" }
  }
]
```

#### Piping into monitoring and dashboards

**Log to file for Splunk/ELK ingestion:**
```bash
dbops --json healthcheck --config config/env-prod.yml > /var/log/dbops/healthcheck.json
```

**Quick disk space alert with jq:**
```bash
dbops --json healthcheck | jq -r '
  .[] | select(.section == "Disk Space (xp_fixeddrives)") |
  .data[] | select((.["MB free"] | tonumber) < 10240) |
  "WARNING: Drive \(.drive) has only \(.["MB free"]) MB free"
'
```

**Check for offline databases:**
```bash
dbops --json healthcheck | jq -r '
  .[] | select(.section == "Database List") |
  .data[] | select(.status != "ONLINE") |
  "ALERT: \(.name) is \(.status)"
'
```

**Feed into a cron job for scheduled monitoring:**
```bash
# crontab -e
*/15 * * * * DBOPS_SQL_PASSWORD=$(cat /run/secrets/sql_password) dbops --json healthcheck --config /opt/dbops/config/env-prod.yml >> /var/log/dbops/healthcheck.jsonl 2>&1
```

**Post results to a Slack webhook:**
```bash
RESULT=$(dbops --json healthcheck)
FAILED=$(echo "$RESULT" | jq '[.[] | select(.status == "fail")] | length')

if [ "$FAILED" -gt 0 ]; then
  curl -X POST "$SLACK_WEBHOOK_URL" \
    -H 'Content-Type: application/json' \
    -d "{\"text\": \"DB Health Check FAILED -- $FAILED check(s) down on prod-sql-01\"}"
fi
```

**Push metrics to Prometheus Pushgateway:**
```bash
dbops --json healthcheck | jq -r '
  .[] | select(.section == "Disk Space (xp_fixeddrives)") |
  .data[] | "dbops_disk_free_mb{drive=\"\(.drive)\"} \(.["MB free"])"
' | curl --data-binary @- http://pushgateway:9091/metrics/job/dbops
```

### The real value

**Operational consistency.** The #1 risk in DBA work isn't that the task is hard -- it's that someone skips the VERIFYONLY after a backup, restores to the wrong path, or forgets to check AG sync before a failover. This toolkit bakes those steps into the commands so they can't be skipped.

Once the roadmap items land (multi-server, alerting, scheduled jobs), it becomes a lightweight **self-service operations platform** -- on-call can run `dbops healthcheck` without needing deep SQL Server knowledge.

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

### 3. Run migrations

```bash
# Dry run — see what would be applied
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops migrate --dry-run

# Apply migrations + seed data to a database
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops migrate --database dbops_dev

# Apply migrations + run database tests
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops migrate --database dbops_dev --test
```

### 4. Check for drift

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops drift-check --database dbops_dev
```

### 5. Run a health check

```bash
DBOPS_SQL_PASSWORD=DevStr0ngPass2026 dbops healthcheck
```

## Database CI/CD Architecture

This is the core of the project — how database changes flow from a developer's branch to production:

```
Developer writes SQL migration (V006__add_audit_table.sql)
         │
         ▼
┌─────────────────────────────────┐
│  PR / Push to main              │
│  ┌───────────────────────────┐  │
│  │ Validate                  │  │
│  │  • Lint Python code       │  │
│  │  • Check SQL naming       │  │
│  │  • Run unit tests (59)    │  │
│  │  • Build Docker image     │  │
│  └──────────┬────────────────┘  │
│             ▼                   │
│  ┌───────────────────────────┐  │
│  │ Deploy Dev (automatic)    │  │
│  │  • dbops migrate --dry-run│  │
│  │  • dbops migrate          │  │
│  │  • dbops migrate --test   │  │
│  │  • dbops drift-check      │  │
│  │  • dbops healthcheck      │  │
│  └──────────┬────────────────┘  │
│             ▼                   │
│  ┌───────────────────────────┐  │
│  │ Deploy Staging (approval) │  │
│  │  • Same steps as dev      │  │
│  │  • Manual approval gate   │  │
│  └──────────┬────────────────┘  │
│             ▼                   │
│  ┌───────────────────────────┐  │
│  │ Deploy Prod (approval)    │  │
│  │  • Same steps as staging  │  │
│  │  • Manual approval gate   │  │
│  │  • Post-deploy healthcheck│  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### Migration Conventions

| Prefix | Pattern | Behavior |
|--------|---------|----------|
| `V` | `V001__create_tables.sql` | **Versioned** — runs once, tracked by SHA-256 checksum |
| `R` | `R001__seed_environments.sql` | **Repeatable** — re-runs every deploy (uses MERGE for idempotency) |

### What Gets Tested in the Pipeline

1. **Python unit tests** (59 tests) — CLI logic, config loading, migration parsing, drift detection
2. **SQL naming validation** — enforces `V###__description.sql` convention
3. **Database schema tests** — verify all tables, columns, FKs, and stored procedures exist post-migration
4. **Data integrity tests** — verify constraints, defaults, and computed columns work correctly
5. **Drift detection** — confirm live schema matches source control after deploy

## Command Examples

```bash
# ----- Migrations -----
# Dry run (preview changes)
dbops migrate --dry-run

# Apply to specific database
dbops migrate --database dbops_dev

# Apply + run DB tests
dbops migrate --database dbops_dev --test

# Use staging config
dbops migrate --config config/env-staging.yml --database dbops_staging

# ----- Drift Detection -----
dbops drift-check --database dbops_dev

# ----- Health Check -----
dbops healthcheck
dbops --json healthcheck    # JSON output for CI/CD

# ----- Backups -----
dbops backup --database MyDB
dbops backup                # all user databases
dbops backup --database MyDB --no-verify

# ----- Restore -----
dbops restore -f /backups/MyDB_20260308.bak -t MyDB_Dev
dbops restore -f /backups/MyDB_20260308.bak -t MyDB_Dev --replace

# ----- Failover -----
dbops failover-test --database MyDB

# ----- Config override -----
dbops healthcheck --config config/env-prod.yml

# ----- Dashboard -----
dbops dashboard                                          # auto-refreshes every 30s
dbops dashboard --config config/env-prod.yml --refresh 15
```

## Project Structure

```
data-platform-automation-toolkit/
├── .github/workflows/ci.yml       # GitHub Actions: full DB CI/CD pipeline
├── .gitlab-ci.yml                  # GitLab CI: full DB CI/CD pipeline
├── pipelines/
│   └── azure-pipelines.yml         # Azure DevOps: full DB CI/CD pipeline
│
├── database/
│   ├── migrations/                 # Versioned SQL migrations (V###__)
│   │   ├── V001__create_migration_tracking.sql
│   │   ├── V002__create_inventory_schema.sql
│   │   ├── V003__create_backup_history.sql
│   │   ├── V004__create_alert_rules.sql
│   │   └── V005__add_stored_procedures.sql
│   ├── seed-data/                  # Repeatable reference data (R###__)
│   │   ├── R001__seed_environments.sql
│   │   └── R002__seed_alert_rules.sql
│   └── tests/                      # SQL validation scripts for CI
│       ├── test_schema_validation.sql
│       └── test_data_integrity.sql
│
├── docker/
│   ├── Dockerfile                  # Containerized dbops CLI with ODBC Driver 18
│   └── docker-compose.yml          # SQL Server 2022 + dbops
│
├── config/
│   ├── env-dev.yml                 # Dev: localhost, debug logging
│   ├── env-staging.yml             # Staging: encrypted connections
│   ├── env-prod.yml                # Prod: trusted connections, retention policies
│   └── env-docker.yml              # Docker: container-to-container networking
│
├── src/dbops/
│   ├── cli.py                      # Typer CLI with 6 subcommands
│   ├── config.py                   # YAML loader + env var resolution
│   ├── db.py                       # pyodbc connection string builder
│   ├── logging.py                  # Rich console + file log + JSON mode
│   └── commands/
│       ├── migrate.py              # Migration runner (Flyway-style)
│       ├── drift_check.py          # Schema drift detection
│       ├── healthcheck.py          # 6 diagnostic queries
│       ├── backup.py               # BACKUP DATABASE with VERIFYONLY
│       ├── restore.py              # RESTORE with auto WITH MOVE
│       └── failover_test.py        # Write/read test + AG validation
│
├── tests/                          # 59 unit tests
│   ├── test_config.py              # Config loading + env resolution
│   ├── test_db.py                  # Connection string builder
│   ├── test_healthcheck.py         # Mocked DB healthcheck
│   ├── test_migrate.py             # Migration parsing, checksums, GO splitting
│   └── test_drift_check.py         # Expected schema + live catalog queries
│
├── .env.example                    # Password + env vars template
└── pyproject.toml                  # Python project config
```

## Configuration

Secrets live in `.env` (never hardcoded in config files):

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

## CI/CD Pipeline Comparison

All three pipelines implement the same deployment lifecycle, so you can compare platform syntax side-by-side:

| Concept | Azure DevOps | GitLab CI | GitHub Actions |
|---------|-------------|-----------|----------------|
| **Config file** | `azure-pipelines.yml` | `.gitlab-ci.yml` | `.github/workflows/ci.yml` |
| **Stages** | `stages:` | `stages:` | Jobs with `needs:` |
| **Environment protection** | Environment approvals | Protected environments | Environment protection rules |
| **Manual gates** | Environment checks | `when: manual` | Required reviewers |
| **Secrets** | Variable groups | CI/CD Variables | Repository secrets |
| **Artifacts** | `PublishPipelineArtifact` | `artifacts:` | `actions/upload-artifact` |
| **Test reporting** | `PublishTestResults` | `reports: junit:` | Upload artifact |
| **Docker build** | `Docker@2` task | `docker:dind` service | Direct `docker build` |

## Tech Stack

- **Python 3.11+** -- CLI and automation logic
- **Typer** -- CLI framework (built on Click)
- **Rich** -- Terminal tables, panels, and formatting
- **pyodbc** -- SQL Server connectivity via ODBC Driver 18
- **PyYAML** -- Environment configuration
- **Docker** -- Containerized SQL Server 2022 + CLI image
- **pytest** -- 59 unit tests with mocked DB calls
- **Azure DevOps / GitLab CI / GitHub Actions** -- CI/CD pipelines

## Roadmap

- [ ] Scheduled backup cron job via Docker
- [ ] Email/Slack alerting on healthcheck failures
- [ ] Multi-server support (run checks across a fleet)
- [ ] Full restore chain validation (Full + Diff + Log)
- [ ] AG failover with automatic rollback
- [ ] Prometheus metrics endpoint for monitoring integration
- [x] Interactive TUI dashboard for real-time server status
- [ ] Azure Key Vault integration for secrets management
- [ ] Kubernetes deployment manifests
- [ ] Rollback migration support (U### prefix)

## License

MIT
