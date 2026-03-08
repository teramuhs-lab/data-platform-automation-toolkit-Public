FROM python:3.11-slim AS base

LABEL maintainer="your-email@example.com"
LABEL description="Data Platform Automation Toolkit (dbops CLI)"

# ── Install ODBC Driver 18 for SQL Server ──
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        unixodbc-dev \
        apt-transport-https && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | \
        gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ── Install dbops CLI ──
WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

# ── Mount points for config and logs ──
VOLUME ["/app/config", "/app/logs"]

ENTRYPOINT ["dbops"]
CMD ["--help"]
