# VM + k3s — veículo da demo pública quando o AKS está bloqueado (ADR-025,
# adendo). Uma VM D2s_v3 spot (~US$ 0,019/h) com k3s single-node recebe o
# overlay `k8s/overlays/vm-k3s/` — mesmos manifests, mesma ordem de deploy.
#
# Decisões deste módulo:
# - IP público como RECURSO SEPARADO da VM: sobrevive a eviction/recreate e
#   até à troca spot<->on-demand — a URL passada à banca não muda.
# - Spot com max_bid_price = -1: paga no máximo o preço on-demand, então a
#   eviction só acontece por falta de capacidade (nunca por preço). O
#   workflow vm-watchdog religa a VM despejada (eviction_policy=Deallocate
#   preserva discos).
# - cloud-init instala o k3s com --tls-san <ip público> (o kubeconfig
#   exportado pelo make valida TLS contra o IP público) e sem Traefik (os
#   Services LoadBalancer do overlay são atendidos pelo klipper-lb do k3s,
#   que binda as portas direto no IP do nó: 8080/8000/16686/9090).

locals {
  tags = {
    project    = "pytstop"
    purpose    = "demo-fase2-vm"
    managed-by = "terraform"
    adr        = "ADR-025"
  }
}

resource "azurerm_resource_group" "vm" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "vm" {
  name                = "vnet-pytstop-vm"
  address_space       = ["10.10.0.0/24"]
  location            = azurerm_resource_group.vm.location
  resource_group_name = azurerm_resource_group.vm.name
  tags                = local.tags
}

resource "azurerm_subnet" "vm" {
  name                 = "snet-pytstop-vm"
  resource_group_name  = azurerm_resource_group.vm.name
  virtual_network_name = azurerm_virtual_network.vm.name
  address_prefixes     = ["10.10.0.0/27"]
}

# IP público estático, separado da VM de propósito (ver cabeçalho).
resource "azurerm_public_ip" "vm" {
  name                = "pip-pytstop-vm"
  location            = azurerm_resource_group.vm.location
  resource_group_name = azurerm_resource_group.vm.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_network_security_group" "vm" {
  name                = "nsg-pytstop-vm"
  location            = azurerm_resource_group.vm.location
  resource_group_name = azurerm_resource_group.vm.name
  tags                = local.tags

  # SSH restrito ao operador (o make passa <ip-do-operador>/32).
  security_rule {
    name                       = "ssh-operador"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = var.ssh_allowed_cidr
    destination_address_prefix = "*"
  }

  # API server do k3s (6443), restrito ao operador: o make aplica os
  # manifests com kubectl DA MÁQUINA DO OPERADOR via kubeconfig exportado —
  # sem esta regra o kubectl trava (NSG só abria SSH + portas de demo).
  security_rule {
    name                       = "k8s-api-operador"
    priority                   = 105
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "6443"
    source_address_prefix      = var.ssh_allowed_cidr
    destination_address_prefix = "*"
  }

  # Superfícies da demo (ADR-025): UI (8080), API (8000), Jaeger (16686),
  # Prometheus (9090) abertas a `*` porque a banca acessa de IPs nao
  # conhecidos de antemao. UI e API sao seguras (production: /docs off, JWT
  # em todo endpoint, rate limit). Jaeger/Prometheus NAO tem auth — RISCO
  # ACEITO e' o mesmo do ADR-025: dados 100% ficticios, backend efemero em
  # memoria (zero persistencia, some no reboot), sem PII (scrubber + #180
  # tiraram placa/documento das URLs/spans). Para restringir a observabilidade
  # ao operador, mova 16686/9090 para uma regra com source = var.ssh_allowed_cidr.
  security_rule {
    name                       = "demo-publica"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["8080", "8000", "16686", "9090"]
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "vm" {
  name                = "nic-pytstop-vm"
  location            = azurerm_resource_group.vm.location
  resource_group_name = azurerm_resource_group.vm.name
  tags                = local.tags

  ip_configuration {
    name                          = "primary"
    subnet_id                     = azurerm_subnet.vm.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm.id
  }
}

resource "azurerm_network_interface_security_group_association" "vm" {
  network_interface_id      = azurerm_network_interface.vm.id
  network_security_group_id = azurerm_network_security_group.vm.id
}

resource "azurerm_linux_virtual_machine" "vm" {
  name                = "pytstop-vm"
  location            = azurerm_resource_group.vm.location
  resource_group_name = azurerm_resource_group.vm.name
  size                = var.vm_size
  admin_username      = var.admin_username
  tags                = local.tags

  network_interface_ids = [azurerm_network_interface.vm.id]

  # Spot: despejo só por capacidade (max_bid = on-demand); Deallocate
  # preserva discos — o watchdog religa e o k3s volta com os dados.
  priority        = var.spot ? "Spot" : "Regular"
  eviction_policy = var.spot ? "Deallocate" : null
  max_bid_price   = var.spot ? -1 : null

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_pubkey
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = 64
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  # k3s instalado no boot, com o IP público (recurso já criado) no TLS SAN.
  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tpl", {
    public_ip = azurerm_public_ip.vm.ip_address
  }))
}
