# Provider do ambiente cloud de demonstração (ADR-025).
#
# Módulo Terraform IRMÃO de `infra/` (kind), não seu substituto: este
# provisiona o AKS gerenciado que dá a URL pública da demo; o `infra/`
# do kind permanece intocado como CD canônico do RNF-022 (ADR-019).
#
# Estado LOCAL de propósito nesta fase: o caminho de operação é
# `make cloud-up`/`make cloud-down` de uma única máquina sob `az login`.
# O job de CD por OIDC (evolução, ver README) exigirá backend remoto
# (azurerm em Storage Account) para o estado sobreviver entre execuções;
# fica como delta do PR do pipeline, não deste módulo.
#
# subscription_id NÃO é fixado aqui: o azurerm 4.x lê `ARM_SUBSCRIPTION_ID`
# do ambiente (o `make cloud-up` a exporta a partir de `az account show`),
# mantendo o ID da assinatura fora do versionamento.

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
