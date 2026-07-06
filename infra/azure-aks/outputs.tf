output "resource_group_name" {
  description = "Resource group do ambiente de demo (alvo do `make cloud-down`)."
  value       = azurerm_resource_group.demo.name
}

output "cluster_name" {
  description = "Nome do cluster AKS."
  value       = azurerm_kubernetes_cluster.demo.name
}

output "get_credentials_command" {
  description = "Comando que funde o kubeconfig do cluster no ~/.kube/config (usado pelo make cloud-up)."
  value = format(
    "az aks get-credentials --resource-group %s --name %s --overwrite-existing",
    azurerm_resource_group.demo.name,
    azurerm_kubernetes_cluster.demo.name,
  )
}

# kube_admin_config NÃO é exposto como output (mesmo marcado sensitive,
# iria para o tfstate/logs): o make usa `az aks get-credentials`, que
# busca as credenciais sob demanda via API — nada de kubeconfig no estado.
