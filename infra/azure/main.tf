# Ambiente cloud de demonstração — AKS tier Free, node único (ADR-025).
#
# Escopo deste módulo: SÓ o cluster gerenciado (resource group + AKS).
# Postgres, app e observabilidade sobem pelo overlay kustomize
# (`k8s/overlays/cloud/`), aplicado por `make cloud-up` via kubectl —
# diferente do kind, onde o postgres é Terraform (`infra/postgres.tf`).
# O motivo é a ordem de criação: configurar o provider kubernetes a
# partir de um cluster criado no MESMO apply é frágil no AKS (o plan das
# cargas roda antes do cluster existir); separar cluster (Terraform) de
# cargas (kubectl/kustomize) é o padrão robusto.

locals {
  tags = {
    project    = "pytstop"
    purpose    = "demo-fase2"
    managed-by = "terraform"
    adr        = "ADR-025"
  }
}

resource "azurerm_resource_group" "demo" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_kubernetes_cluster" "demo" {
  name                = var.cluster_name
  location            = azurerm_resource_group.demo.location
  resource_group_name = azurerm_resource_group.demo.name
  dns_prefix          = var.cluster_name

  # tier Free: control plane sem custo e sem SLA — adequado a uma demo
  # efêmera (ADR-025). O custo do ambiente é só o node + o LB/IP público.
  sku_tier = "Free"

  # null => AKS escolhe a versão default da região (evita pin quebrando
  # o apply quando a versão sai de suporte). Pine via var para repro estrita.
  kubernetes_version = var.kubernetes_version

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = var.node_size
    # Disco OS gerenciado no menor tamanho útil; o PVC do postgres é
    # separado (managed-csi, no overlay). 32 GB cobre a imagem + logs.
    os_disk_size_gb = 32
  }

  # Managed Identity: sem service principal com secret estático (ADR-025).
  identity {
    type = "SystemAssigned"
  }

  tags = local.tags
}
