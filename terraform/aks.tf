# Documentation: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/kubernetes_cluster
# https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/kubernetes_cluster_node_pool

resource "azurerm_kubernetes_cluster" "astro-cluster" {
  name                = "astro-aks1"
  location            = azurerm_resource_group.astro-rg.location
  resource_group_name = azurerm_resource_group.astro-rg.name
  dns_prefix          = "astroaks1"
  sku_tier            = "Free" 

  default_node_pool {
    name       = "default"
    vm_size    = var.node_vm_size
    vnet_subnet_id = azurerm_subnet.astro-subnet.id  # places nodes inside the vnet subnet

    node_count = 1
    only_critical_addons_enabled  = true
    temporary_name_for_rotation = "systmp"

    node_labels = {
      "platform-tier" = "control-plane"
    }
  }
  


  identity {
    type = "SystemAssigned"
  }

}

resource "azurerm_kubernetes_cluster_node_pool" "workpool" {
  name                  = "workpool"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.astro-cluster.id
  vm_size               = var.workpool_vm_size
  vnet_subnet_id        = azurerm_subnet.astro-subnet.id

  auto_scaling_enabled = true
  min_count             = var.workpool_node_count_min
  max_count             = var.workpool_node_count_max

  priority        = "Regular" 
  os_disk_size_gb = 100

  node_labels = {
    "platform-tier"  = "workload"
    "chaos-eligible" = "true"
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