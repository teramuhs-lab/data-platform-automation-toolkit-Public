# Data Platform Automation Toolkit

A Database DevOps automation toolkit for DBAs and DevOps engineers to automate operational tasks across SQL Server environments.

## Features

- **Health Checks** -- Automated database health monitoring and diagnostics
- **Backup Automation** -- Scheduled and on-demand database backups
- **Restore Validation** -- Automated restore testing to verify backup integrity
- **Failover Testing** -- Controlled failover validation for high-availability configurations

## Project Structure

```
data-platform-automation-toolkit/
├── README.md                  # Project overview and documentation
├── pyproject.toml             # Python project metadata and dependencies
├── .gitignore                 # Git ignore rules
├── .env.example               # Environment variable template
│
├── docker/                    # Container configuration
│   ├── Dockerfile             # Application container image
│   └── docker-compose.yml     # Multi-container orchestration
│
├── config/                    # Environment-specific configuration
│   ├── env-dev.yml            # Development environment settings
│   └── env-prod.yml           # Production environment settings
│
├── src/
│   └── dbops/                 # Core application package
│       ├── __init__.py        # Package initialization
│       ├── cli.py             # CLI entry point (Click/Typer)
│       ├── config.py          # Configuration loader
│       ├── db.py              # Database connection management
│       ├── logging.py         # Logging configuration
│       │
│       └── commands/          # CLI command modules
│           ├── healthcheck.py # Database health check logic
│           ├── backup.py      # Backup automation logic
│           ├── restore.py     # Restore validation logic
│           └── failover_test.py # Failover testing logic
│
└── tests/                     # Unit and integration tests
    ├── test_config.py         # Tests for config loading
    └── test_healthcheck.py    # Tests for health check commands
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional, for containerized execution)
- Access to a SQL Server instance

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/data-platform-automation-toolkit.git
cd data-platform-automation-toolkit

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in development mode
pip install -e ".[dev]"
```

### Configuration

```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your database credentials and settings
```

### Usage

```bash
# Run a health check
dbops healthcheck --env dev

# Run a backup
dbops backup --env prod --database my_database

# Validate a restore
dbops restore --env dev --backup-file /path/to/backup.bak

# Run failover test
dbops failover-test --env dev --cluster my_cluster
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/ tests/

# Run type checking
mypy src/
```

## Docker

```bash
# Build the image
docker build -f docker/Dockerfile -t dbops:latest .

# Run with docker-compose
docker compose -f docker/docker-compose.yml up
```

## License

MIT
