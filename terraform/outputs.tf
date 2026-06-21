# Output the Kubernetes cluster kube_config
output "client_certificate" {
  value     = azurerm_kubernetes_cluster.astro-cluster.kube_config[0].client_certificate
  sensitive = true
}

output "kube_config" {
  value = azurerm_kubernetes_cluster.astro-cluster.kube_config_raw
  sensitive = true
}

# Output the AKS cluster name and resource group
output "aks_cluster_name" {
  value       = azurerm_kubernetes_cluster.astro-cluster.name
  description = "The name of the AKS cluster"
}

output "resource_group_name" {
  value       = azurerm_resource_group.astro-rg.name
  description = "The name of the resource group"
}

output "key_vault_id" {
  value       = azurerm_key_vault.astro-kv.id
  description = "The ID of the Key Vault"
}
