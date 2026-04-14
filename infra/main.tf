# =============================================================================
# Azure SQL Infrastructure — Database DevOps Lab
# =============================================================================
# This file is Infrastructure as Code (IaC). Instead of clicking around in the
# Azure portal, we describe every resource here and run `terraform apply` to
# create them. If we ever need to rebuild the lab, we just run apply again.
#
# What this file creates (in order):
#   1. Resource Group      — a folder in Azure that groups related resources
#   2. Azure SQL Server    — the database engine (holds many databases)
#   3. Key Vault           — secure place to store the SQL password
#   4. Log Analytics       — central place to collect logs and metrics
#   5. Diagnostic settings — wires the databases to Log Analytics
#   6. Alerts              — fires when prod CPU gets too high
#   7. Firewall rules      — controls who can connect to the SQL Server
#   8. Databases           — the actual staging and prod databases
#
# Usage:
#   cd infra
#   terraform init                                           # download providers
#   terraform plan  -var="sql_admin_password=YourPassword"   # preview changes
#   terraform apply -var="sql_admin_password=YourPassword"   # create resources
#   terraform destroy -var="sql_admin_password=YourPassword" # tear it all down
# =============================================================================

# -----------------------------------------------------------------------------
# Terraform block — tells Terraform which providers we need
# -----------------------------------------------------------------------------
# A provider is a plugin that knows how to talk to a cloud (Azure, AWS, etc.).
# We pin to major version 4 so future breaking changes don't surprise us.
terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# The azurerm provider authenticates using the Azure CLI login (`az login`).
# subscription_id picks which Azure subscription these resources belong to.
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# -----------------------------------------------------------------------------
# Variables — inputs you can change without editing the file
# -----------------------------------------------------------------------------
# Actual values live in terraform.tfvars (gitignored for secrets).

variable "subscription_id" {
  description = "Azure subscription ID — where resources will be created"
  type        = string
}

variable "location" {
  description = "Azure region (e.g., westus2, eastus, canadacentral)"
  type        = string
  default     = "eastus"
}

variable "project_name" {
  description = "Short name used as a prefix for all resources (e.g., 'dbops')"
  type        = string
  default     = "dbops"
}

variable "sql_admin_login" {
  description = "SQL Server admin username"
  type        = string
  default     = "dbopsadmin"
}

variable "sql_admin_password" {
  description = "SQL Server admin password — passed at apply time, never stored"
  type        = string
  sensitive   = true # hides the value in logs and Terraform output
}

# -----------------------------------------------------------------------------
# 1. Resource Group — the container for everything else
# -----------------------------------------------------------------------------
# Every Azure resource must belong to a resource group. Deleting the group
# deletes everything inside it — handy for cleaning up the lab in one command.
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-lab"
  location = var.location

  # Tags help identify and organize resources (and track cost by project).
  tags = {
    project     = var.project_name
    environment = "lab"
    managed_by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Random suffix — keeps global resource names unique
# -----------------------------------------------------------------------------
# Some Azure resources (SQL Server, Key Vault) need globally-unique names.
# We append 8 random hex characters (e.g., "ea9ebe49") so the name is unlikely
# to collide with anyone else's resource.
resource "random_id" "suffix" {
  byte_length = 4 # 4 bytes = 8 hex characters
}

# -----------------------------------------------------------------------------
# 2. Azure SQL Server — the database engine
# -----------------------------------------------------------------------------
# Think of this as the "instance" that holds one or more databases.
# It has an admin login, a version, and firewall rules.
resource "azurerm_mssql_server" "main" {
  name                         = "${var.project_name}-sql-${random_id.suffix.hex}"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0" # latest available on Azure SQL
  administrator_login          = var.sql_admin_login
  administrator_login_password = var.sql_admin_password

  tags = azurerm_resource_group.main.tags
}

# -----------------------------------------------------------------------------
# 3. Azure Key Vault — secure secret storage
# -----------------------------------------------------------------------------
# Instead of keeping passwords in plain text or in GitHub Secrets forever,
# we store them here. Access is controlled by Azure AD identities and
# every read/write is logged.

# Fetch info about whoever is running Terraform (tenant + object ID).
# We need this to grant ourselves permission on the vault below.
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = "${var.project_name}-kv-${random_id.suffix.hex}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  # tenant_id = the Azure AD tenant that owns this vault
  tenant_id = data.azurerm_client_config.current.tenant_id
  sku_name  = "standard" # "standard" is fine for lab; "premium" for HSM-backed keys

  # Soft-delete keeps deleted secrets recoverable for N days (safety net).
  soft_delete_retention_days = 7
  # purge_protection prevents permanent deletion — disabled here so we can
  # fully reset the lab. For prod, set this to true.
  purge_protection_enabled = false

  tags = azurerm_resource_group.main.tags
}

# Access policy — who can do what with the vault.
# We grant the current user (the one running terraform) permission to manage
# secrets. Without this, even the creator can't write secrets to the vault.
resource "azurerm_key_vault_access_policy" "terraform" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge", "Recover"]
}

# Store the SQL admin password as a secret in the vault.
# depends_on ensures the access policy is created first — otherwise this
# write would be denied.
resource "azurerm_key_vault_secret" "sql_password" {
  name         = "dbops-sql-password"
  value        = var.sql_admin_password
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.terraform]
}

# -----------------------------------------------------------------------------
# 4. Log Analytics Workspace — where diagnostic data gets stored
# -----------------------------------------------------------------------------
# This is a managed "log database" you can query with KQL (Kusto Query Language).
# Every diagnostic log and metric from the SQL databases gets shipped here.
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.project_name}-logs-${random_id.suffix.hex}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018" # pay per GB ingested (first 5 GB/month free)
  retention_in_days   = 30          # how long logs are kept

  tags = azurerm_resource_group.main.tags
}

# -----------------------------------------------------------------------------
# 5. Diagnostic Settings — connect the databases to Log Analytics
# -----------------------------------------------------------------------------
# By itself, Log Analytics is empty. We have to tell each database what to
# send. These blocks route SQL logs + metrics into the workspace.

resource "azurerm_monitor_diagnostic_setting" "staging" {
  name                       = "diag-staging"
  target_resource_id         = azurerm_mssql_database.staging.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  # Which log categories to ship. Each one is a different kind of signal.
  enabled_log { category = "SQLInsights" } # query performance data
  enabled_log { category = "Errors" }      # SQL errors raised to the client
  enabled_log { category = "Timeouts" }    # query timeouts
  enabled_log { category = "Deadlocks" }   # deadlock graphs
  enabled_log { category = "Blocks" }      # blocking sessions

  # Metrics are numeric (CPU, DTU, connections). Basic covers the common ones.
  enabled_metric { category = "Basic" }
  enabled_metric { category = "InstanceAndAppAdvanced" }
}

resource "azurerm_monitor_diagnostic_setting" "prod" {
  name                       = "diag-prod"
  target_resource_id         = azurerm_mssql_database.prod.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log { category = "SQLInsights" }
  enabled_log { category = "Errors" }
  enabled_log { category = "Timeouts" }
  enabled_log { category = "Deadlocks" }
  enabled_log { category = "Blocks" }

  enabled_metric { category = "Basic" }
  enabled_metric { category = "InstanceAndAppAdvanced" }
}

# -----------------------------------------------------------------------------
# 6. Alerts — notify us when something goes wrong
# -----------------------------------------------------------------------------
# An "action group" is a reusable list of who to notify. We leave it empty
# for the lab (just stores alert history), but you'd add email/SMS/webhooks here.
resource "azurerm_monitor_action_group" "main" {
  name                = "${var.project_name}-alerts"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "dbopsalerts" # shown in email/SMS, must be <= 12 chars
  tags                = azurerm_resource_group.main.tags
}

# A metric alert evaluates a metric on a schedule and fires when the criteria
# are met. This one fires if prod CPU average stays above 80% for 15 minutes.
resource "azurerm_monitor_metric_alert" "prod_high_cpu" {
  name                = "prod-high-cpu"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_mssql_database.prod.id]
  description         = "Alert when prod database CPU exceeds 80%"
  severity            = 2       # 0 = critical ... 4 = verbose
  frequency           = "PT5M"  # check every 5 minutes
  window_size         = "PT15M" # evaluate against the last 15 minutes

  # The actual condition we're watching.
  criteria {
    metric_namespace = "Microsoft.Sql/servers/databases"
    metric_name      = "cpu_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  # When the alert fires, run the action group (notify folks).
  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }

  tags = azurerm_resource_group.main.tags
}

# -----------------------------------------------------------------------------
# 7. Firewall rules — who can connect to the SQL Server
# -----------------------------------------------------------------------------
# By default, Azure SQL blocks ALL connections, even from Azure itself.
# We add two rules for the lab:
#   - Allow traffic from Azure services (special IP range 0.0.0.0 → 0.0.0.0)
#   - Allow all public IPs (0.0.0.0 → 255.255.255.255)
#
# The "allow all" rule is ONLY appropriate for a lab. For production, you'd
# restrict to specific IPs (your office, CI runners, VPN range).
resource "azurerm_mssql_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_mssql_firewall_rule" "allow_all" {
  name             = "AllowAll-Lab"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "255.255.255.255"
}

# -----------------------------------------------------------------------------
# 8. Databases — staging and prod, both on the same SQL Server
# -----------------------------------------------------------------------------
# We use the "GeneralPurpose Serverless Gen5 1-vCore" tier:
#   - Scales from 0.5 to 1 vCore automatically
#   - Auto-pauses after 60 min of no activity (saves money on idle labs)
#   - Wakes up on the first connection (takes ~30-60 seconds)
#
# This is the cheapest viable tier for a lab. For production, you'd pick a
# provisioned tier with a fixed vCore count for predictable performance.

resource "azurerm_mssql_database" "staging" {
  name      = "dbops_staging"
  server_id = azurerm_mssql_server.main.id
  sku_name  = "GP_S_Gen5_1" # GeneralPurpose, Serverless, Gen5 hardware, 1 vCore

  min_capacity                = 0.5 # minimum vCores (fractional allowed on serverless)
  max_size_gb                 = 32  # max database size
  auto_pause_delay_in_minutes = 60  # pause after this many idle minutes
  zone_redundant              = false

  tags = merge(azurerm_resource_group.main.tags, { environment = "staging" })
}

resource "azurerm_mssql_database" "prod" {
  name      = "dbops_prod"
  server_id = azurerm_mssql_server.main.id
  sku_name  = "GP_S_Gen5_1"

  min_capacity                = 0.5
  max_size_gb                 = 32
  auto_pause_delay_in_minutes = 60
  zone_redundant              = false

  tags = merge(azurerm_resource_group.main.tags, { environment = "prod" })
}

# -----------------------------------------------------------------------------
# Outputs — values printed after `terraform apply` (used by CI/CD pipeline)
# -----------------------------------------------------------------------------
# These get shown on the command line and can also be read with
# `terraform output <name>`.

output "sql_server_fqdn" {
  description = "Azure SQL Server fully qualified domain name"
  value       = azurerm_mssql_server.main.fully_qualified_domain_name
}

output "staging_database" {
  description = "Staging database name"
  value       = azurerm_mssql_database.staging.name
}

output "prod_database" {
  description = "Production database name"
  value       = azurerm_mssql_database.prod.name
}

output "sql_admin_login" {
  description = "SQL admin username"
  value       = azurerm_mssql_server.main.administrator_login
}

output "key_vault_name" {
  description = "Azure Key Vault name"
  value       = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  description = "Azure Key Vault URI (for the Azure CLI, SDKs, etc.)"
  value       = azurerm_key_vault.main.vault_uri
}

output "log_analytics_workspace" {
  description = "Log Analytics Workspace name (for KQL queries)"
  value       = azurerm_log_analytics_workspace.main.name
}
