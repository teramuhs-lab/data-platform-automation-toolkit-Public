-- =============================================
-- Migration: V002
-- Description: Create inventory schema and server tracking tables
-- Author: dbops automation
-- =============================================
-- This is the core data model: a server inventory that a DBA team
-- would use to track SQL Server instances across environments.

IF NOT EXISTS (
    SELECT 1 FROM sys.schemas WHERE name = 'inventory'
)
BEGIN
    EXEC('CREATE SCHEMA inventory');
END
GO

-- -------------------------------------------------------------------
-- Environments (dev, staging, prod, dr)
-- -------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'environments' AND schema_id = SCHEMA_ID('inventory'))
BEGIN
    CREATE TABLE inventory.environments (
        environment_id  INT IDENTITY(1,1) PRIMARY KEY,
        name            VARCHAR(50)   NOT NULL UNIQUE,
        description     VARCHAR(255)  NULL,
        is_production   BIT           NOT NULL DEFAULT 0,
        created_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    );
    PRINT 'Created inventory.environments';
END
GO

-- -------------------------------------------------------------------
-- SQL Server instances
-- -------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'servers' AND schema_id = SCHEMA_ID('inventory'))
BEGIN
    CREATE TABLE inventory.servers (
        server_id       INT IDENTITY(1,1) PRIMARY KEY,
        hostname        VARCHAR(255)  NOT NULL,
        instance_name   VARCHAR(255)  NULL,       -- NULL = default instance
        port            INT           NOT NULL DEFAULT 1433,
        environment_id  INT           NOT NULL,
        edition         VARCHAR(100)  NULL,       -- Enterprise, Standard, Developer
        version         VARCHAR(50)   NULL,       -- e.g. 16.0.4135.4
        is_ag_primary   BIT           NOT NULL DEFAULT 0,
        last_checked    DATETIME2     NULL,
        notes           NVARCHAR(MAX) NULL,
        created_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_servers_environment
            FOREIGN KEY (environment_id) REFERENCES inventory.environments(environment_id),
        CONSTRAINT UQ_server_instance
            UNIQUE (hostname, instance_name)
    );
    PRINT 'Created inventory.servers';
END
GO

-- -------------------------------------------------------------------
-- Databases tracked on each server
-- -------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'databases' AND schema_id = SCHEMA_ID('inventory'))
BEGIN
    CREATE TABLE inventory.databases (
        database_id     INT IDENTITY(1,1) PRIMARY KEY,
        server_id       INT           NOT NULL,
        name            SYSNAME       NOT NULL,
        recovery_model  VARCHAR(20)   NULL,       -- FULL, SIMPLE, BULK_LOGGED
        compatibility   INT           NULL,       -- 160, 150, etc.
        size_mb         DECIMAL(12,2) NULL,
        owner           NVARCHAR(128) NULL,
        is_monitored    BIT           NOT NULL DEFAULT 1,
        created_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_databases_server
            FOREIGN KEY (server_id) REFERENCES inventory.servers(server_id),
        CONSTRAINT UQ_database_server
            UNIQUE (server_id, name)
    );
    PRINT 'Created inventory.databases';
END
GO
