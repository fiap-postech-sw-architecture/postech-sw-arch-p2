output "public_ip" {
  description = "IP público estático da VM — base das URLs da demo (UI :8080, API :8000, Jaeger :16686, Prometheus :9090)."
  value       = azurerm_public_ip.vm.ip_address
}

output "ssh_command" {
  description = "Acesso administrativo à VM (chave dedicada git-ignored)."
  value       = "ssh -i .vm-demo-ssh ${var.admin_username}@${azurerm_public_ip.vm.ip_address}"
}

output "vm_name" {
  description = "Nome da VM (alvo do watchdog: az vm start -g <rg> -n <vm>)."
  value       = azurerm_linux_virtual_machine.vm.name
}

output "resource_group_name" {
  description = "Resource group da VM (alvo do make vm-down / watchdog)."
  value       = azurerm_resource_group.vm.name
}
