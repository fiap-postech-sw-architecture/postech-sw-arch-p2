# Providers da infraestrutura da fase 2 (RNF-021).
#
# Versoes fixadas em required_providers (Terraform, Aula 02; ADR-016) e
# pinadas no .terraform.lock.hcl commitado. O provider kubernetes e
# configurado a partir das credenciais que o recurso do cluster kind
# exporta — e o encadeamento que permite cluster + banco num unico
# `terraform apply` (ADR-017; RFC-002 §2, risco 4).

terraform {
  required_version = ">= 1.7"

  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.9"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.31"
    }
  }
}

provider "kind" {}

provider "kubernetes" {
  host                   = kind_cluster.pytstop.endpoint
  client_certificate     = kind_cluster.pytstop.client_certificate
  client_key             = kind_cluster.pytstop.client_key
  cluster_ca_certificate = kind_cluster.pytstop.cluster_ca_certificate
}
