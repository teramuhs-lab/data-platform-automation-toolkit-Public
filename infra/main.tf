# =============================================
# Azure SQL Infrastructure — Database DevOps Lab
# =============================================
# Provisions: Resource Group, SQL Server, two databases (staging + prod)
# Free tier: 100k vCore seconds/month per database
#
# Usage:
#   cd infra
#   terraform init
#   terraform plan
#   terraform apply

terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# -----------------------------------------------
# Variables
# -----------------------------------------------
variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "dbops"
}

variable "sql_admin_login" {
  description = "SQL Server admin username"
  type        = string
  default     = "dbopsadmin"
}

variable "sql_admin_password" {
  description = "SQL Server admin password"
  type        = string
  sensitive   = true
}

# -----------------------------------------------
# Resource Group
# -----------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-lab"
  location = var.location

  tags = {
    project     = var.project_name
    environment = "lab"
    managed_by  = "terraform"
  }
}

# -----------------------------------------------
# Azure SQL Server
# -----------------------------------------------
resource "azurerm_mssql_server" "main" {
  name                         = "${var.project_name}-sql-${random_id.suffix.hex}"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0"
  administrator_login          = var.sql_admin_login
  administrator_login_password = var.sql_admin_password

  tags = azurerm_resource_group.main.tags
}

resource "random_id" "suffix" {
  byte_length = 4
}

# -----------------------------------------------
# Firewall: Allow Azure services + GitHub Actions
# -----------------------------------------------
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

# -----------------------------------------------
# Databases — Free tier (GeneralPurpose Serverless)
# -----------------------------------------------
resource "azurerm_mssql_database" "staging" {
  name      = "dbops_staging"
  server_id = azurerm_mssql_server.main.id
  sku_name  = "GP_S_Gen5_1"

  min_capacity                = 0.5
  max_size_gb                 = 32
  auto_pause_delay_in_minutes = 60
  zone_redundant              = false

  tags = merge(azurerm_resource_group.main.tags, {
    environment = "staging"
  })

  lifecycle {
    prevent_destroy = false
  }
}

resource "azurerm_mssql_database" "prod" {
  name      = "dbops_prod"
  server_id = azurerm_mssql_server.main.id
  sku_name  = "GP_S_Gen5_1"

  min_capacity                = 0.5
  max_size_gb                 = 32
  auto_pause_delay_in_minutes = 60
  zone_redundant              = false

  tags = merge(azurerm_resource_group.main.tags, {
    environment = "prod"
  })

  lifecycle {
    prevent_destroy = false
  }
}

# -----------------------------------------------
# Outputs — used by CI/CD pipeline
# -----------------------------------------------
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
