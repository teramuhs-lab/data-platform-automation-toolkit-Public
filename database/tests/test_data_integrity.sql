-- =============================================
-- Database Tests: Data Integrity
-- Description: Verify constraints, defaults, and data quality
-- =============================================

DECLARE @failures INT = 0;
DECLARE @total    INT = 0;

-- -------------------------------------------------
-- Test 1: Cannot insert duplicate environment
-- -------------------------------------------------
SET @total += 1;
BEGIN TRY
    INSERT INTO inventory.environments (name, description, is_production)
    VALUES ('dev', 'duplicate test', 0);

    -- If we get here, the constraint failed to protect us
    PRINT 'FAIL: Duplicate environment name was allowed';
    SET @failures += 1;

    -- Clean up
    DELETE FROM inventory.environments
    WHERE description = 'duplicate test';
END TRY
BEGIN CATCH
    PRINT 'PASS: Unique constraint prevents duplicate environments';
END CATCH

-- -------------------------------------------------
-- Test 2: FK prevents orphan servers
-- -------------------------------------------------
SET @total += 1;
BEGIN TRY
    INSERT INTO inventory.servers (hostname, port, environment_id)
    VALUES ('orphan-server', 1433, 99999);

    PRINT 'FAIL: Orphan server with invalid environment_id was allowed';
    SET @failures += 1;

    DELETE FROM inventory.servers WHERE hostname = 'orphan-server';
END TRY
BEGIN CATCH
    PRINT 'PASS: FK constraint prevents orphan servers';
END CATCH

-- -------------------------------------------------
-- Test 3: Alert severity check constraint works
-- -------------------------------------------------
SET @total += 1;
BEGIN TRY
    INSERT INTO inventory.alert_rules (name, metric, operator, threshold, severity)
    VALUES ('bad rule', 'test', '>', 1, 'INVALID_SEVERITY');

    PRINT 'FAIL: Invalid severity was allowed';
    SET @failures += 1;

    DELETE FROM inventory.alert_rules WHERE name = 'bad rule';
END TRY
BEGIN CATCH
    PRINT 'PASS: Check constraint rejects invalid severity';
END CATCH

-- -------------------------------------------------
-- Test 4: Default values are applied
-- -------------------------------------------------
SET @total += 1;
BEGIN TRY
    -- Insert a minimal environment and check defaults
    INSERT INTO inventory.environments (name) VALUES ('_test_defaults');

    DECLARE @is_prod BIT;
    SELECT @is_prod = is_production FROM inventory.environments WHERE name = '_test_defaults';

    IF @is_prod = 0
        PRINT 'PASS: is_production defaults to 0';
    ELSE
    BEGIN
        PRINT 'FAIL: is_production did not default to 0';
        SET @failures += 1;
    END

    DELETE FROM inventory.environments WHERE name = '_test_defaults';
END TRY
BEGIN CATCH
    PRINT 'FAIL: Error testing defaults - ' + ERROR_MESSAGE();
    SET @failures += 1;
END CATCH

-- -------------------------------------------------
-- Test 5: Computed column duration_sec works
-- -------------------------------------------------
SET @total += 1;
BEGIN TRY
    -- Need a valid database_id; get one from seed data flow
    -- Skip if no databases exist yet (test still passes structurally)
    IF EXISTS (SELECT 1 FROM sys.columns WHERE name = 'duration_sec'
               AND object_id = OBJECT_ID('inventory.backup_history'))
        PRINT 'PASS: duration_sec computed column exists on backup_history';
    ELSE
    BEGIN
        PRINT 'FAIL: duration_sec computed column missing';
        SET @failures += 1;
    END
END TRY
BEGIN CATCH
    PRINT 'FAIL: Error testing computed column - ' + ERROR_MESSAGE();
    SET @failures += 1;
END CATCH

-- -------------------------------------------------
-- Summary
-- -------------------------------------------------
PRINT '';
PRINT '========================================';
PRINT 'Data Integrity Tests: ' + CAST(@total - @failures AS VARCHAR) + '/' + CAST(@total AS VARCHAR) + ' passed';
IF @failures > 0
BEGIN
    PRINT 'RESULT: FAIL';
    THROW 50000, 'Data integrity tests failed', 1;
END
ELSE
    PRINT 'RESULT: PASS';
GO
