# PostgreSQL 16 dentro do cluster (ADR-017): StatefulSet de replica unica
# com PVC, Secret de credenciais e Service ClusterIP — infraestrutura-base
# declarada pelo provider kubernetes no mesmo apply que cria o cluster.
#
# Paridade com o docker-compose (RNF-019): mesma imagem postgres:16 e
# mesmas variaveis POSTGRES_*, movidas para Secret no cluster.

resource "kubernetes_namespace" "pytstop_infra" {
  metadata {
    name = "pytstop-infra"

    labels = {
      "app.kubernetes.io/part-of" = "pytstop"
    }
  }
}

resource "kubernetes_secret" "postgres_credentials" {
  metadata {
    name      = "postgres-credentials"
    namespace = kubernetes_namespace.pytstop_infra.metadata[0].name
  }

  # Consumido via env_from pelo StatefulSet; a DATABASE_URL do app (em
  # /k8s) aponta para o Service abaixo com estas credenciais.
  data = {
    POSTGRES_DB       = var.postgres_db
    POSTGRES_USER     = var.postgres_user
    POSTGRES_PASSWORD = var.postgres_password
  }
}

resource "kubernetes_stateful_set" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace.pytstop_infra.metadata[0].name

    labels = {
      app = "postgres"
    }
  }

  spec {
    service_name = kubernetes_service.postgres.metadata[0].name
    replicas     = 1

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    template {
      metadata {
        labels = {
          app = "postgres"
        }
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:16"

          port {
            name           = "postgres"
            container_port = 5432
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.postgres_credentials.metadata[0].name
            }
          }

          # Subdiretorio do mount point: o diretorio raiz de um volume
          # recem-provisionado pode nao estar vazio (ex.: lost+found), o
          # que faria o initdb recusar o diretorio de dados.
          env {
            name  = "PGDATA"
            value = "/var/lib/postgresql/data/pgdata"
          }

          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }

          # Mesmo probe do docker-compose, com -h 127.0.0.1 (TCP): o
          # servidor temporario do initdb escuta so no socket unix, entao
          # o probe via TCP nao marca Ready durante a inicializacao.
          readiness_probe {
            exec {
              command = [
                "/bin/sh",
                "-c",
                "pg_isready -h 127.0.0.1 -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\"",
              ]
            }

            initial_delay_seconds = 5
            period_seconds        = 10
            timeout_seconds       = 3
            failure_threshold     = 6
          }

          # Valores modestos para cluster local de demo; o limite de
          # memoria acomoda os 128MB default de shared_buffers do
          # postgres:16 com folga para work_mem.
          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }
        }
      }
    }

    # PVC de 1Gi na StorageClass padrao do kind (local-path): persistencia
    # independente do ciclo de vida do Pod — a demo de `kubectl delete pod`
    # com dados intactos do ADR-017.
    volume_claim_template {
      metadata {
        name = "postgres-data"
      }

      spec {
        access_modes = ["ReadWriteOnce"]

        resources {
          requests = {
            storage = "1Gi"
          }
        }
      }
    }
  }
}

# DNS interno consumido pelos manifests do app em /k8s:
# postgres.pytstop-infra.svc.cluster.local
resource "kubernetes_service" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace.pytstop_infra.metadata[0].name

    labels = {
      app = "postgres"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "postgres"
    }

    port {
      name        = "postgres"
      port        = 5432
      target_port = 5432
    }
  }
}
