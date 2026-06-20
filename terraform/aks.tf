# Documentation: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/kubernetes_cluster

resource "azurerm_kubernetes_cluster" "astro-cluster" {
  name                = "astro-aks1"
  location            = azurerm_resource_group.astro-rg.location
  resource_group_name = azurerm_resource_group.astro-rg.name
  dns_prefix          = "astroaks1"

  default_node_pool {
    name       = "default"
    vm_size    = var.node_vm_size

    auto_scaling_enabled = true
    min_count  = var.node_min_count
    max_count  = var.node_max_count
  }

  identity {
    type = "SystemAssigned"
  }

}

output "client_certificate" {
  value     = azurerm_kubernetes_cluster.astro-cluster.kube_config[0].client_certificate
  sensitive = true
}

output "kube_config" {
  value = azurerm_kubernetes_cluster.astro-cluster.kube_config_raw

  sensitive = true
}