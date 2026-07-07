# Provider do ambiente de demonstração em VM + k3s (adendo do ADR-025).
#
# Módulo Terraform IRMÃO de `infra/azure-aks/` (AKS) e `infra/` (kind).
# Existe porque a subscription Azure for Students BLOQUEIA o AKS (o system
# pool exige SKUs v5-v7, todos com quota zero e pedido de aumento negado),
# mas NÃO restringe VMs avulsas — Standard_D2s_v3 tem quota e nenhuma
# restrição. A VM roda k3s (Kubernetes single-node) e recebe os MESMOS
# manifests do overlay cloud; só o provisionamento muda.
#
# Mesmo padrão do módulo AKS: estado local (make vm-up/down de uma máquina
# sob az login) e ARM_SUBSCRIPTION_ID vindo do ambiente.

terraform {
  required_version = ">= 1.7"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}
