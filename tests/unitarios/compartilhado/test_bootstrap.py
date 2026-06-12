from __future__ import annotations

import importlib
from unittest.mock import patch

from src.compartilhado.infraestrutura import bootstrap


class TestBootstrap:
    def test_iniciar_todos_mapeamentos_chamado_apenas_uma_vez(self) -> None:
        """Garante que a flag idempotente funciona."""
        importlib.reload(bootstrap)  # Reseta o estado global falso

        with (
            patch(
                "src.autenticacao.infraestrutura.mapping.iniciar_mapeamentos"
            ) as mock_auth,
            patch(
                "src.catalogo_servicos.infraestrutura.mapping.iniciar_mapeamentos"
            ) as mock_cata,
            patch(
                "src.cliente_veiculo.infraestrutura.mapping.iniciar_mapeamentos"
            ) as mock_clie,
            patch(
                "src.estoque.infraestrutura.mapping.iniciar_mapeamentos"
            ) as mock_esto,
            patch(
                "src.ordem_servico.infraestrutura.mapping.iniciar_mapeamentos"
            ) as mock_os,
        ):
            # Primeira chamada: executa
            bootstrap.iniciar_todos_mapeamentos()
            mock_auth.assert_called_once()
            mock_cata.assert_called_once()
            mock_clie.assert_called_once()
            mock_esto.assert_called_once()
            mock_os.assert_called_once()

            # Segunda chamada: no-op em todos
            bootstrap.iniciar_todos_mapeamentos()
            assert mock_auth.call_count == 1
            assert mock_cata.call_count == 1
            assert mock_clie.call_count == 1
            assert mock_esto.call_count == 1
            assert mock_os.call_count == 1
