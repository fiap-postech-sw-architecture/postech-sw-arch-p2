#cloud-config
# Bootstrap do k3s na VM de demo (adendo do ADR-025). Roda uma única vez no
# primeiro boot. O k3s sobe como serviço systemd — sobrevive a reboot e à
# religada pós-eviction (spot).
#
# --disable traefik: os Services LoadBalancer do overlay são atendidos pelo
#   klipper-lb embutido (binda as portas no IP do nó); o Traefik só ocuparia
#   a 80/443 sem uso.
# --tls-san ${public_ip}: inclui o IP público no certificado do API server —
#   o kubeconfig que o make exporta aponta para esse IP e valida TLS.
package_update: true
runcmd:
  - |
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik --tls-san ${public_ip}" sh -
