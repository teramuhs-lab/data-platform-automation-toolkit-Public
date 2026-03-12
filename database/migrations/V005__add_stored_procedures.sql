-- =============================================
-- Migration: V005
-- Description: Create operational stored procedures
-- Author: dbops automation
-- =============================================
-- Reusable stored procedures that the dbops CLI and
-- scheduled jobs can call for common operations.

-- -------------------------------------------------------------------
-- Register a completed backup
-- -------------------------------------------------------------------
CREATE OR ALTER PROCEDURE inventory.usp_register_backup
    @database_id    INT,
    @backup_type    VARCHAR(20),
    @backup_path    NVARCHAR(500),
    @size_mb        DECIMAL(12,2),
    @compressed     BIT,
    @verified       BIT,
    @started_at     DATETIME2,
    @completed_at   DATETIME2
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO inventory.backup_history
        (database_id, backup_type, backup_path, size_mb, compressed, verified, started_at, completed_at)
    VALUES
        (@database_id, @backup_type, @backup_path, @size_mb, @compressed, @verified, @started_at, @completed_at);

    SELECT SCOPE_IDENTITY() AS backup_id;
END
GO

-- -------------------------------------------------------------------
-- Get servers missing a recent backup (> N hours)
-- -------------------------------------------------------------------
CREATE OR ALTER PROCEDURE inventory.usp_get_stale_backups
    @hours_threshold INT = 24
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        s.hostname,
        s.instance_name,
        d.name AS database_name,
        e.name AS environment,
        bh.last_backup,
        DATEDIFF(HOUR, bh.last_backup, SYSUTCDATETIME()) AS hours_since_backup
    FROM inventory.databases d
    JOIN inventory.servers s ON d.server_id = s.server_id
    JOIN inventory.environments e ON s.environment_id = e.environment_id
    LEFT JOIN (
        SELECT database_id, MAX(completed_at) AS last_backup
        FROM inventory.backup_history
        WHERE verified = 1 AND completed_at IS NOT NULL
        GROUP BY database_id
    ) bh ON d.database_id = bh.database_id
    WHERE d.is_monitored = 1
      AND (bh.last_backup IS NULL
           OR DATEDIFF(HOUR, bh.last_backup, SYSUTCDATETIME()) > @hours_threshold)
    ORDER BY hours_since_backup DESC;
END
GO

-- -------------------------------------------------------------------
-- Raise an incident from a healthcheck finding
-- -------------------------------------------------------------------
CREATE OR ALTER PROCEDURE inventory.usp_raise_incident
    @rule_id      INT = NULL,
    @server_id    INT,
    @database_id  INT = NULL,
    @severity     VARCHAR(20),
    @message      NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;

    -- Avoid duplicate open incidents for the same rule+server+database
    IF NOT EXISTS (
        SELECT 1 FROM inventory.incidents
        WHERE ISNULL(rule_id, -1) = ISNULL(@rule_id, -1)
          AND server_id = @server_id
          AND ISNULL(database_id, -1) = ISNULL(@database_id, -1)
          AND resolved_at IS NULL
    )
    BEGIN
        INSERT INTO inventory.incidents (rule_id, server_id, database_id, severity, message)
        VALUES (@rule_id, @server_id, @database_id, @severity, @message);
    END
END
GO
