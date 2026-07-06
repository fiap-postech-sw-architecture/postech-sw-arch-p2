variable "resource_group_name" {
  description = "Resource group que contém o cluster de demonstração. `make cloud-down` destrói tudo aqui dentro."
  type        = string
  default     = "rg-pytstop-demo"
}

variable "location" {
  description = "Região Azure. brazilsouth reduz latência para a banca no Brasil; troque para eastus2 se faltar cota do node."
  type        = string
  default     = "brazilsouth"
}

variable "cluster_name" {
  description = "Nome do cluster AKS (também usado como dns_prefix)."
  type        = string
  default     = "pytstop-demo"
}

variable "node_size" {
  description = "SKU do único node. B2als_v2 (2 vCPU/4 GB, burstável) é o mais barato que roda o stack — o mesmo que já cabe no kind."
  type        = string
  default     = "Standard_B2als_v2"
}

variable "kubernetes_version" {
  description = "Versão do Kubernetes do AKS. Vazio = default da região (recomendado para demo); pine para reprodutibilidade estrita."
  type        = string
  default     = null
}
