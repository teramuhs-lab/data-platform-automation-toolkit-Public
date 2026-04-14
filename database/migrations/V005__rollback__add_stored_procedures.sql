-- =============================================================================
-- Rollback for V005__add_stored_procedures.sql
-- =============================================================================
-- Drops the operational stored procedures created by V005. Safe to re-run:
-- each DROP is guarded by IF EXISTS so partial rollbacks still complete.
--
-- Pairs with: V005__add_stored_procedures.sql
-- =============================================================================

IF OBJECT_ID('inventory.usp_register_backup', 'P') IS NOT NULL
BEGIN
    DROP PROCEDURE inventory.usp_register_backup;
    PRINT 'Dropped inventory.usp_register_backup';
END
GO

IF OBJECT_ID('inventory.usp_get_recent_backups', 'P') IS NOT NULL
BEGIN
    DROP PROCEDURE inventory.usp_get_recent_backups;
    PRINT 'Dropped inventory.usp_get_recent_backups';
END
GO

IF OBJECT_ID('inventory.usp_check_server_health', 'P') IS NOT NULL
BEGIN
    DROP PROCEDURE inventory.usp_check_server_health;
    PRINT 'Dropped inventory.usp_check_server_health';
END
GO
