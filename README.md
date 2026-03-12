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
- [ ] Interactive TUI dashboard for real-time server status
- [ ] Azure Key Vault integration for secrets management
- [ ] Kubernetes deployment manifests
- [ ] Rollback migration support (U### prefix)

## License

MIT
