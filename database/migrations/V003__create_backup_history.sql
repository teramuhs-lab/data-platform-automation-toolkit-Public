-- =============================================
-- Migration: V003
-- Description: Create backup tracking table
-- Author: dbops automation
-- =============================================
-- Tracks backup operations run by the dbops CLI, providing
-- an audit trail separate from msdb.dbo.backupset.

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'backup_history' AND schema_id = SCHEMA_ID('inventory'))
BEGIN
    CREATE TABLE inventory.backup_history (
        backup_id       INT IDENTITY(1,1) PRIMARY KEY,
        database_id     INT           NOT NULL,
        backup_type     VARCHAR(20)   NOT NULL,   -- FULL, DIFF, LOG
        backup_path     NVARCHAR(500) NOT NULL,
        size_mb         DECIMAL(12,2) NULL,
        compressed      BIT           NOT NULL DEFAULT 1,
        verified        BIT           NOT NULL DEFAULT 0,
        started_at      DATETIME2     NOT NULL,
        completed_at    DATETIME2     NULL,
        duration_sec    AS DATEDIFF(SECOND, started_at, completed_at),
        initiated_by    NVARCHAR(128) NOT NULL DEFAULT SUSER_SNAME(),

        CONSTRAINT FK_backup_database
            FOREIGN KEY (database_id) REFERENCES inventory.databases(database_id)
    );

    CREATE NONCLUSTERED INDEX IX_backup_history_database
        ON inventory.backup_history (database_id, started_at DESC);

    PRINT 'Created inventory.backup_history with index';
END
GO
