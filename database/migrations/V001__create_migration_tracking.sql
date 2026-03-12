-- =============================================
-- Migration: V001
-- Description: Create migration tracking table
-- Author: dbops automation
-- =============================================
-- This table tracks which migrations have been applied to the database.
-- It is the foundation of the migration framework itself.

IF NOT EXISTS (
    SELECT 1 FROM sys.schemas WHERE name = 'dbops'
)
BEGIN
    EXEC('CREATE SCHEMA dbops');
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'dbops' AND t.name = 'migration_history'
)
BEGIN
    CREATE TABLE dbops.migration_history (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        version         VARCHAR(10)   NOT NULL,
        script_name     VARCHAR(255)  NOT NULL,
        checksum        VARCHAR(64)   NOT NULL,
        applied_on      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        applied_by      NVARCHAR(128) NOT NULL DEFAULT SUSER_SNAME(),
        execution_ms    INT           NULL,
        success         BIT           NOT NULL DEFAULT 1,

        CONSTRAINT UQ_migration_version UNIQUE (version)
    );

    PRINT 'Created dbops.migration_history table.';
END
ELSE
BEGIN
    PRINT 'dbops.migration_history already exists — skipping.';
END
GO
