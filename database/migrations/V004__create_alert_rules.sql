-- =============================================
-- Migration: V004
-- Description: Create alert rules and incident log
-- Author: dbops automation
-- =============================================
-- Defines threshold-based alert rules and logs incidents
-- detected by the healthcheck command.

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'alert_rules' AND schema_id = SCHEMA_ID('inventory'))
BEGIN
    CREATE TABLE inventory.alert_rules (
        rule_id         INT IDENTITY(1,1) PRIMARY KEY,
        name            VARCHAR(100)  NOT NULL,
        metric          VARCHAR(100)  NOT NULL,   -- e.g. disk_free_mb, ag_sync_health
        operator        VARCHAR(10)   NOT NULL,   -- >, <, =, >=, <=
        threshold       DECIMAL(18,4) NOT NULL,
        severity        VARCHAR(20)   NOT NULL DEFAULT 'WARNING',  -- WARNING, CRITICAL
        is_enabled      BIT           NOT NULL DEFAULT 1,
        created_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT CK_alert_severity
            CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
        CONSTRAINT CK_alert_operator
            CHECK (operator IN ('>', '<', '=', '>=', '<=', '!='))
    );
    PRINT 'Created inventory.alert_rules';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'incidents' AND schema_id = SCHEMA_ID('inventory'))
BEGIN
    CREATE TABLE inventory.incidents (
        incident_id     INT IDENTITY(1,1) PRIMARY KEY,
        rule_id         INT           NULL,
        server_id       INT           NOT NULL,
        database_id     INT           NULL,
        severity        VARCHAR(20)   NOT NULL,
        message         NVARCHAR(MAX) NOT NULL,
        detected_at     DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        acknowledged_at DATETIME2     NULL,
        acknowledged_by NVARCHAR(128) NULL,
        resolved_at     DATETIME2     NULL,

        CONSTRAINT FK_incident_rule
            FOREIGN KEY (rule_id) REFERENCES inventory.alert_rules(rule_id),
        CONSTRAINT FK_incident_server
            FOREIGN KEY (server_id) REFERENCES inventory.servers(server_id)
    );

    CREATE NONCLUSTERED INDEX IX_incidents_open
        ON inventory.incidents (server_id, detected_at DESC)
        WHERE resolved_at IS NULL;

    PRINT 'Created inventory.incidents with filtered index';
END
GO
