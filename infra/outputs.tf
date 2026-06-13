output "cluster_name" {
  description = "Nome do cluster kind criado."
  value       = kind_cluster.pytstop.name
}

output "cluster_endpoint" {
  description = "Endpoint do API server do cluster."
  value       = kind_cluster.pytstop.endpoint
}

output "kubeconfig_path" {
  description = "Caminho do kubeconfig que o provider exporta para este cluster."
  value       = kind_cluster.pytstop.kubeconfig_path
}

output "postgres_service_dns" {
  description = "DNS interno do PostgreSQL, consumido pelos manifests do app em /k8s."
  value       = "${kubernetes_service.postgres.metadata[0].name}.${kubernetes_namespace.pytstop_infra.metadata[0].name}.svc.cluster.local"
}
