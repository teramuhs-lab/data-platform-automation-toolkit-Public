-- =============================================
-- Seed Data: R002 (Repeatable)
-- Description: Default alert rules for healthchecks
-- =============================================

MERGE inventory.alert_rules AS target
USING (VALUES
    ('Low Disk Space',       'disk_free_mb',     '<',  5000.0,  'CRITICAL'),
    ('Disk Warning',         'disk_free_mb',     '<',  20000.0, 'WARNING'),
    ('AG Not Healthy',       'ag_sync_health',   '!=', 1.0,     'CRITICAL'),
    ('Stale Backup',         'hours_since_backup','>', 24.0,    'WARNING'),
    ('Large Redo Queue',     'redo_queue_kb',    '>',  500000.0,'WARNING'),
    ('DB Offline',           'db_state',         '!=', 0.0,     'CRITICAL')
) AS source (name, metric, operator, threshold, severity)
ON target.name = source.name
WHEN MATCHED THEN
    UPDATE SET
        metric    = source.metric,
        operator  = source.operator,
        threshold = source.threshold,
        severity  = source.severity
WHEN NOT MATCHED THEN
    INSERT (name, metric, operator, threshold, severity)
    VALUES (source.name, source.metric, source.operator, source.threshold, source.severity);

PRINT 'Seed: alert_rules synchronized';
GO
