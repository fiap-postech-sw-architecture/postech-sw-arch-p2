"""full_test: harness E2E contra instancia viva do PyTStop.

Suite paralela ao `tests/` do pytest. NAO compartilha fixtures, conftest ou
imports. Projetada para rodar via `make full-test` contra `docker compose up`,
exercitando 45 endpoints da API com N usuarios concorrentes simulados em
threads. Ver `full-test/README.md`.
"""
