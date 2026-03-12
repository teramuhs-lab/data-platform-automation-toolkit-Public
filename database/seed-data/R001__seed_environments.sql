-- =============================================
-- Seed Data: R001 (Repeatable)
-- Description: Populate reference environments
-- =============================================
-- R-prefixed scripts are idempotent and re-run on every deploy.
-- They use MERGE to keep reference data in sync with source control.

MERGE inventory.environments AS target
USING (VALUES
    ('dev',     'Development environment',       0),
    ('staging', 'Pre-production staging',         0),
    ('prod',    'Production environment',         1),
    ('dr',      'Disaster recovery standby',      1)
) AS source (name, description, is_production)
ON target.name = source.name
WHEN MATCHED THEN
    UPDATE SET
        description   = source.description,
        is_production = source.is_production
WHEN NOT MATCHED THEN
    INSERT (name, description, is_production)
    VALUES (source.name, source.description, source.is_production);

PRINT 'Seed: environments synchronized';
GO
