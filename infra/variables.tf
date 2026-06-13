variable "cluster_name" {
  description = "Nome do cluster kind (o contexto kubectl vira kind-<nome>)."
  type        = string
  default     = "pytstop"
}

variable "node_image" {
  description = "Imagem de node do kind, fixada por tag + digest para reprodutibilidade."
  type        = string
  default     = "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"
}

variable "postgres_db" {
  description = "Nome do banco criado no primeiro boot do PostgreSQL."
  type        = string
  default     = "pytstop"
}

variable "postgres_user" {
  description = "Usuario do PostgreSQL."
  type        = string
  default     = "pytstop"
}

variable "postgres_password" {
  description = "Senha do PostgreSQL. Default apenas para demo local — sobrescreva via TF_VAR_postgres_password fora desse cenario."
  type        = string
  default     = "pytstop-demo"
  sensitive   = true
}
