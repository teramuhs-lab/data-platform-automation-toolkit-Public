-- =============================================
-- Database Tests: Schema Validation
-- Description: Verify all expected objects exist after migration
-- =============================================
-- These tests run in CI after migrations are applied.
-- Each test prints PASS/FAIL and the final query returns
-- a summary that the CLI parses for pass/fail counts.
--
-- Convention: 0 = PASS, non-zero = FAIL

DECLARE @failures INT = 0;
DECLARE @total    INT = 0;

-- -------------------------------------------------
-- Test 1: dbops schema exists
-- -------------------------------------------------
SET @total += 1;
IF EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dbops')
    PRINT 'PASS: dbops schema exists';
ELSE
BEGIN
    PRINT 'FAIL: dbops schema missing';
    SET @failures += 1;
END

-- -------------------------------------------------
-- Test 2: inventory schema exists
-- -------------------------------------------------
SET @total += 1;
IF EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'inventory')
    PRINT 'PASS: inventory schema exists';
ELSE
BEGIN
    PRINT 'FAIL: inventory schema missing';
    SET @failures += 1;
END

-- -------------------------------------------------
-- Test 3: migration_history table exists
-- -------------------------------------------------
SET @total += 1;
IF EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'dbops' AND t.name = 'migration_history'
)
    PRINT 'PASS: dbops.migration_history exists';
ELSE
BEGIN
    PRINT 'FAIL: dbops.migration_history missing';
    SET @failures += 1;
END

-- -------------------------------------------------
-- Test 4: All inventory tables exist
-- -------------------------------------------------
DECLARE @expected_tables TABLE (table_name VARCHAR(100));
INSERT INTO @expected_tables VALUES
    ('environments'), ('servers'), ('databases'),
    ('backup_history'), ('alert_rules'), ('incidents');

DECLARE @tbl VARCHAR(100);
DECLARE tbl_cursor CURSOR FOR SELECT table_name FROM @expected_tables;
OPEN tbl_cursor;
FETCH NEXT FROM tbl_cursor INTO @tbl;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @total += 1;
    IF EXISTS (
        SELECT 1 FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE s.name = 'inventory' AND t.name = @tbl
    )
        PRINT 'PASS: inventory.' + @tbl + ' exists';
    ELSE
    BEGIN
        PRINT 'FAIL: inventory.' + @tbl + ' missing';
        SET @failures += 1;
    END
    FETCH NEXT FROM tbl_cursor INTO @tbl;
END
CLOSE tbl_cursor;
DEALLOCATE tbl_cursor;

-- -------------------------------------------------
-- Test 5: Stored procedures exist
-- -------------------------------------------------
DECLARE @expected_procs TABLE (proc_name VARCHAR(100));
INSERT INTO @expected_procs VALUES
    ('usp_register_backup'), ('usp_get_stale_backups'), ('usp_raise_incident');

DECLARE @proc VARCHAR(100);
DECLARE proc_cursor CURSOR FOR SELECT proc_name FROM @expected_procs;
OPEN proc_cursor;
FETCH NEXT FROM proc_cursor INTO @proc;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @total += 1;
    IF EXISTS (
        SELECT 1 FROM sys.procedures p
        JOIN sys.schemas s ON p.schema_id = s.schema_id
        WHERE s.name = 'inventory' AND p.name = @proc
    )
        PRINT 'PASS: inventory.' + @proc + ' exists';
    ELSE
    BEGIN
        PRINT 'FAIL: inventory.' + @proc + ' missing';
        SET @failures += 1;
    END
    FETCH NEXT FROM proc_cursor INTO @proc;
END
CLOSE proc_cursor;
DEALLOCATE proc_cursor;

-- -------------------------------------------------
-- Test 6: Foreign key constraints exist
-- -------------------------------------------------
SET @total += 1;
DECLARE @fk_count INT;
SELECT @fk_count = COUNT(*)
FROM sys.foreign_keys fk
JOIN sys.schemas s ON fk.schema_id = s.schema_id
WHERE s.name = 'inventory';

IF @fk_count >= 4
    PRINT 'PASS: Found ' + CAST(@fk_count AS VARCHAR) + ' foreign keys in inventory schema';
ELSE
BEGIN
    PRINT 'FAIL: Expected >= 4 foreign keys, found ' + CAST(@fk_count AS VARCHAR);
    SET @failures += 1;
END

-- -------------------------------------------------
-- Test 7: Seed data loaded
-- -------------------------------------------------
SET @total += 1;
DECLARE @env_count INT;
SELECT @env_count = COUNT(*) FROM inventory.environments;
IF @env_count >= 4
    PRINT 'PASS: environments seeded (' + CAST(@env_count AS VARCHAR) + ' rows)';
ELSE
BEGIN
    PRINT 'FAIL: environments not seeded (found ' + CAST(@env_count AS VARCHAR) + ')';
    SET @failures += 1;
END

-- -------------------------------------------------
-- Summary
-- -------------------------------------------------
PRINT '';
PRINT '========================================';
PRINT 'DB Tests: ' + CAST(@total - @failures AS VARCHAR) + '/' + CAST(@total AS VARCHAR) + ' passed';
IF @failures > 0
BEGIN
    PRINT 'RESULT: FAIL';
    -- Return non-zero so the CLI / pipeline can detect failure
    THROW 50000, 'Database validation failed', 1;
END
ELSE
    PRINT 'RESULT: PASS';
GO
