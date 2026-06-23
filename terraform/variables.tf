variable "project_name" {
  description = "The name of the project. Used for naming resources."
  type        = string
  default     = "astro"
}

variable "location" {
  description = "The Azure region where resources will be created."
  type        = string
  default     = "francecentral"
}

variable "node_vm_size" {
  description = "The size of the VMs in the AKS node pool."
  type        = string
  default     = "Standard_D2s_v5"
}

variable "node_min_count" {
  description = "The minimum number of nodes in the AKS node pool."
  type        = number
  default     = 2
}

variable "node_max_count" {
  description = "The maximum number of nodes in the AKS node pool."
  type        = number
  default     = 5
}

variable "workpool_vm_size" {
  description = "VM size for the Astronomy Shop and load tests."
  type        = string
  default     = "Standard_D4s_v5"
}

variable "workpool_node_count_min" {
  description = "Minimum nodes dedicated to running target applications."
  type        = number
  default     = 1
}

variable "workpool_node_count_max" {
  description = "Maximum scaling limit for chaos workload nodes."
  type        = number
  default     = 4
}