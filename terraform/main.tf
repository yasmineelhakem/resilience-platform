# Documentation: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/subnet
# https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/virtual_network

# Create a resource group
resource "azurerm_resource_group" "astro-rg" {
  name     = "rg-${var.project_name}"
  location = var.location
}

# Create a virtual network within the resource group
resource "azurerm_virtual_network" "astro-vnet" {
  name                = "astro-vnet"
  resource_group_name = azurerm_resource_group.astro-rg.name
  location            = azurerm_resource_group.astro-rg.location
  address_space       = ["10.0.0.0/16"]
}


resource "azurerm_subnet" "astro-subnet" {
  name                 = "astro-subnet"
  resource_group_name  = azurerm_resource_group.astro-rg.name
  virtual_network_name = azurerm_virtual_network.astro-vnet.name
  address_prefixes     = ["10.0.1.0/24"]

  delegation {
    name = "delegation"

    service_delegation {
      name    = "Microsoft.ContainerInstance/containerGroups"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action", "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action"]
    }
  }
}
