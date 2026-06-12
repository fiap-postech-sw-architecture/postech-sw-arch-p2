# Cluster kind da fase 2 (ADR-016): plataforma unica para dev local,
# demo do video e CI efemero — o mesmo `terraform apply` em todos.
#
# node_image fixada por tag + digest para reprodutibilidade: e a imagem
# default da lib kind v0.31 embutida no provider, tornada explicita para
# que upgrades do provider nao troquem a versao do Kubernetes em silencio.
resource "kind_cluster" "pytstop" {
  name           = var.cluster_name
  node_image     = var.node_image
  wait_for_ready = true
}
