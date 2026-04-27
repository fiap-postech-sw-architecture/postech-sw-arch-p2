# Dados seed -- credenciais e lookup pra acompanhamento (dev-only)

Quick-access pras credenciais de login e pros pares (placa, documento) que ficam populados depois de `make seed-users-docker` + `make seed-demo` (ou um unico `make reset-db`).

> **Dev-only.** Tudo aqui sao senhas e documentos sinteticos pra testes manuais da UI de simulacao. Nao promover. Documentos CPF/CNPJ passam validacao do `brutils` mas nao referenciam pessoas reais.

## Usuarios

`make seed-users-docker` (ou qualquer alvo que inclua `seed-users`) popula os 3 usuarios abaixo. Espelhados em `ui/config.py::_USUARIOS_SEED` e `scripts/seed_usuarios.py`.

| Papel     | E-mail                    | Senha                       |
| --------- | ------------------------- | --------------------------- |
| admin     | `admin@pytstop.dev`       | `admin-dev-pass-2026`       |
| atendente | `atendente@pytstop.dev`   | `atendente-dev-pass-2026`   |
| mecanico  | `mecanico@pytstop.dev`    | `mecanico-dev-pass-2026`    |

Na tela `/login` os atalhos **ADMIN** / **ATENDENTE** / **MECANICO** logam automaticamente sem digitar.

## OS pra testar `/acompanhamento`

A pagina publica `/acompanhamento` (sem auth) consulta o status de uma OS pelo par **(placa, CPF ou CNPJ apenas digitos)**. Apos `make seed-demo` (ou `make reset-db`) ficam disponiveis as 8 OS abaixo, uma por estado da `MaquinaDeStatus`:

| OS # | Status                  | Cliente                          | Documento (sem mascara)  | Placa     | Veiculo                   |
| ---- | ----------------------- | -------------------------------- | ------------------------ | --------- | ------------------------- |
| 1    | RECEBIDA                | Joao Silva                       | `11144477735`            | `ABC1D23` | Volkswagen Gol 2015       |
| 2    | RECEBIDA (com item)     | Maria Santos                     | `98765432100`            | `GHI3F45` | Toyota Corolla 2018       |
| 3    | EM_DIAGNOSTICO          | Carlos Mendes                    | `68657930480`            | `JKL4G56` | Fiat Strada 2019          |
| 4    | AGUARDANDO_APROVACAO    | Ana Beatriz Oliveira             | `11954083238`            | `PQR6I78` | Volkswagen Jetta 2021     |
| 5    | EM_EXECUCAO             | Joao Silva                       | `11144477735`            | `DEF2E34` | Honda Civic 2020          |
| 6    | FINALIZADA              | Rafael Costa                     | `02685509305`            | `STU7J89` | Ford Fiesta 2017          |
| 7    | ENTREGUE                | Oficina Boa Vida LTDA            | `11222333000181`         | `VWX8K90` | Fiat Strada 2020          |
| 8    | CANCELADA               | Transportadora Horizonte Ltda    | `19551396000193`         | `BCD0M23` | Mercedes-Benz Sprinter 2019 |

Exemplo: na tela `/acompanhamento` cole `STU7J89` em **Placa**, `02685509305` em **CPF ou CNPJ**, e clique **Consultar** -- deve voltar `Status: FINALIZADA`. Para um caminho 404 deliberado, qualquer combinacao que nao existe (ex.: `ZZZ0Z00` + `00000000000`) confirma o tratamento de "nenhuma OS encontrada".

Os mesmos dados estao em `ui/seed.py` -- esta tabela e gerada manualmente a partir das listas `_CLIENTES`, `_VEICULOS` e dos helpers `_criar_os_*`. Se o seed mudar, atualize aqui.

## URLs

| Servico              | URL                                       |
| -------------------- | ----------------------------------------- |
| UI NiceGUI (login)   | http://localhost:8080/login               |
| Acompanhamento       | http://localhost:8080/acompanhamento      |
| Backend Swagger      | http://localhost:8000/docs                |
| Health probe         | http://localhost:8000/api/v1/saude        |

## Como popular

Dentro do repo, no Git Bash:

```bash
make up                   # sobe postgres + backend + UI
make seed-users-docker    # popula os 3 usuarios acima
make seed-demo            # popula clientes/OS/catalogo/estoque
```

Ou tudo de uma vez (apaga o banco primeiro):

```bash
make reset-db
```
