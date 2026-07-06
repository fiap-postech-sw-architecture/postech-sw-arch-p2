variable "resource_group_name" {
  description = "Resource group da VM de demo. Separado do RG do AKS — os dois trilhos coexistem."
  type        = string
  default     = "rg-pytstop-vm"
}

variable "location" {
  description = "Região Azure. eastus: permitida pela policy da conta de estudante, maior capacidade spot e ~menor preço (northcentralus é o fallback)."
  type        = string
  default     = "eastus"
}

variable "vm_size" {
  description = "SKU da VM. D2s_v3 (2 vCPU/8 GB): sem restrição na subscription, quota disponível e com oferta spot (B-series não suporta spot)."
  type        = string
  default     = "Standard_D2s_v3"
}

variable "spot" {
  description = "true = VM Spot (~80% de desconto; pode ser despejada por capacidade — watchdog religa). false = on-demand (janela crítica da banca)."
  type        = bool
  default     = true
}

variable "admin_username" {
  description = "Usuário administrativo da VM (SSH)."
  type        = string
  default     = "pytstop"
}

variable "admin_ssh_pubkey" {
  description = "Chave pública SSH do admin. O make gera um par dedicado (.vm-demo-ssh, git-ignored) e injeta este valor."
  type        = string
}

variable "ssh_allowed_cidr" {
  description = "CIDR autorizado no SSH (22). O make passa o IP público da máquina que opera (<ip>/32) — nunca abra 22 para o mundo."
  type        = string
}
