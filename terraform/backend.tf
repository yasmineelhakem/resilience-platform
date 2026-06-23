terraform {
  backend "azurerm" {
    resource_group_name  = "rg-astro-backend"
    storage_account_name = "astrotfstate"     
    container_name       = "tfstate"
    key                  = "astro-cluster.tfstate" 
  }
}