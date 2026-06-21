terraform {
  backend "azurerm" {
    resource_group_name  = "rg-astro-backend"
    storage_account_name = "astrotfstate2026"     
    container_name       = "tfstate"
    key                  = "astro-cluster.tfstate" 
  }
}